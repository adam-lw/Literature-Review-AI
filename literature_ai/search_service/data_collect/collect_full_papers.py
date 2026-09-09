import asyncio
from datetime import datetime, timezone

import requests
from loguru import logger
from sqlalchemy import text

from literature_ai.db import ENGINE, upsert_table
from literature_ai.search_service.embeddings.core import EmbeddingModel, get_embedding_model
from literature_ai.search_service.processing.pdf_parsing import (
    DEFAULT_MAX_CHARS,
    GrobidParseError,
    GrobidUnavailableError,
    call_grobid_fulltext,
    extract_chunks,
    parse_tei_fulltext,
)
from literature_ai.search_service.retrieval.paper import get_paper_metadata
from literature_ai.search_service.session import make_session
from literature_ai.utils import PaperProcessingMetrics

FULLTEXT_TABLE = "raw.paper_fulltext"
CHUNKS_TABLE = "processed.paper_chunks"
CHUNK_EMBEDDING_MODEL = "text-embedding-3-small"

_pdf_session = make_session("pdf_download", max_retries=3, backoff_factor=2.0)


class PaperNotFoundError(ValueError):
    """Raised when paper_id is not present in raw.raw_paper_searches."""


def get_cached_fulltext(paper_id: str) -> tuple[str, str | None, str | None] | None:
    """Check raw.paper_fulltext for a parse result already recorded for paper_id, so
    process_papers_by_id can skip re-downloading/re-parsing it. Returns
    (status, full_text, tei_xml), or None if paper_id hasn't been processed yet.
    """
    with ENGINE.connect() as conn:
        row = conn.execute(
            text(
                f'SELECT "status", "full_text", "tei_xml" FROM {FULLTEXT_TABLE} '
                'WHERE "paperId" = :id'
            ),
            {"id": paper_id},
        ).fetchone()
    return tuple(row) if row is not None else None


def is_already_chunked(paper_id: str) -> bool:
    """Check whether paper_id already has rows in processed.paper_chunks, so
    process_papers_by_id can skip re-chunking/re-embedding it.
    """
    with ENGINE.connect() as conn:
        row = conn.execute(
            text(f'SELECT 1 FROM {CHUNKS_TABLE} WHERE "paperId" = :id LIMIT 1'),
            {"id": paper_id},
        ).fetchone()
    return row is not None


def resolve_pdf_urls(row: dict) -> list[str]:
    """Return candidate PDF URLs for a paper, in the order they should be tried.

    Prefers raw_paper_searches.url (Semantic Scholar's openAccessPdf.url), with the
    ArXiv-derived URL as a fallback candidate when an ArXiv ID is present - not just
    when `url` is absent, but also for download_pdf to fall through to if `url` turns
    out not to actually be downloadable. row must have flat "url"/"ArXiV" keys, matching
    the columns in raw.raw_paper_searches (not S2's nested openAccessPdf/externalIds
    response shape).
    """
    candidates = []
    if row.get("url"):
        candidates.append(row["url"])
    if row.get("ArXiV"):
        arxiv_url = f"https://arxiv.org/pdf/{row['ArXiV']}"
        if arxiv_url not in candidates:
            candidates.append(arxiv_url)
    return candidates


def download_pdf(pdf_urls: list[str]) -> tuple[str, bytes] | None:
    """Try each candidate URL in order, returning the first that downloads
    successfully as (pdf_url, pdf_bytes). Returns None once every candidate fails.
    """
    for pdf_url in pdf_urls:
        try:
            response = _pdf_session.get(pdf_url, timeout=30)
            response.raise_for_status()
            return pdf_url, response.content
        except requests.exceptions.RequestException as exc:
            logger.warning(f"Failed to download {pdf_url}: {exc}")
    return None


async def embed_chunk_texts(model: EmbeddingModel, texts: list[str]) -> list[list[float]]:
    """Embed each chunk's text with model, preserving order."""
    vectors = await asyncio.gather(*(model.embed_text(text) for text in texts))
    return [list(map(float, vector)) for vector in vectors]


def _process_one(paper_id: str, max_chars: int) -> tuple[str, str | None, str | None]:
    """Resolve, download, GROBID-parse, and chunk one paper id's full text.

    Persists parsed full text to raw.paper_fulltext and chunk boundaries (as character
    offsets into that full_text - chunks don't store their own text) to
    processed.paper_chunks. Idempotent: a paper_id already present in either table is
    not re-fetched/re-chunked. Returns (status, full_text, tei_xml).

    Raises PaperNotFoundError if paper_id isn't in raw.raw_paper_searches, or
    GrobidUnavailableError/GrobidParseError if GROBID processing fails - unlike
    process_papers_by_id, these propagate rather than being swallowed, so a single
    caller waiting on this paper_id (e.g. an on-demand API request) learns immediately
    rather than the failure only surfacing as a metrics count.
    """
    cached = get_cached_fulltext(paper_id)

    chunks = None  # populated below if extract_chunks already ran for this id
    if cached is not None:
        status, full_text, tei_xml = cached
    else:
        candidate_row = get_paper_metadata(paper_id)
        if candidate_row is None:
            raise PaperNotFoundError(f"No paper found for paperId={paper_id!r}")

        pdf_urls = resolve_pdf_urls(candidate_row)
        downloaded = download_pdf(pdf_urls) if pdf_urls else None

        now = datetime.now(timezone.utc)

        if downloaded is None:
            logger.error(f"Failed to collect pdf for paper ID {paper_id}")
            status, full_text, tei_xml = "no_pdf_available", None, None
            upsert_table(
                [
                    {
                        "paperId": paper_id,
                        "status": status,
                        "pdf_url": None,
                        "full_text": None,
                        "tei_xml": None,
                        "grobid_version": None,
                        "parsed_at": now,
                    }
                ],
                FULLTEXT_TABLE,
                conflict_cols=["paperId"],
                do_update=True,
            )
        else:
            logger.info(f"Successfully collected pdf for {paper_id}")
            pdf_url, pdf_bytes = downloaded
            tei_xml = call_grobid_fulltext(pdf_bytes)
            parsed = parse_tei_fulltext(tei_xml)
            full_text, chunks = extract_chunks(tei_xml, max_chars)
            status = "success"
            upsert_table(
                [
                    {
                        "paperId": paper_id,
                        "status": status,
                        "pdf_url": pdf_url,
                        "full_text": full_text,
                        "tei_xml": tei_xml,
                        "grobid_version": parsed["grobid_version"],
                        "parsed_at": now,
                    }
                ],
                FULLTEXT_TABLE,
                conflict_cols=["paperId"],
                do_update=True,
            )

    if status != "success":
        return status, full_text, tei_xml

    # status == "success" guarantees both were set together above.
    assert full_text is not None
    assert tei_xml is not None

    if not is_already_chunked(paper_id):
        if chunks is None:
            _, chunks = extract_chunks(tei_xml, max_chars)
        chunked_at = datetime.now(timezone.utc)

        model = get_embedding_model(CHUNK_EMBEDDING_MODEL)
        chunk_texts = [full_text[c["start_index"] : c["end_index"]] for c in chunks]
        embeddings = asyncio.run(embed_chunk_texts(model, chunk_texts)) if chunk_texts else []

        records = [
            {
                "paperId": paper_id,
                "chunk_index": chunk["index"],
                "section_index": chunk["section_index"],
                "section_header": chunk["section_header"],
                "start_index": chunk["start_index"],
                "end_index": chunk["end_index"],
                "char_count": chunk["char_count"],
                "embedding": embedding,
                "chunked_at": chunked_at,
            }
            for chunk, embedding in zip(chunks, embeddings)
        ]
        if records:
            upsert_table(
                records, CHUNKS_TABLE, conflict_cols=["paperId", "chunk_index"], do_update=True
            )

    return status, full_text, tei_xml


def process_papers_by_id(ids: list[str], max_chars: int = DEFAULT_MAX_CHARS) -> PaperProcessingMetrics:
    """Resolve, download, GROBID-parse, and chunk each paper id's full text.

    Idempotent: ids already present in either raw.paper_fulltext or
    processed.paper_chunks are not re-fetched/re-chunked. A failure on one id is
    logged and counted, not fatal to the rest of the batch.
    """
    metrics = PaperProcessingMetrics()

    for paper_id in ids:
        metrics.total += 1
        try:
            status, _, _ = _process_one(paper_id, max_chars)
            if status == "success":
                metrics.inserted += 1
            else:
                metrics.skipped += 1
        except PaperNotFoundError:
            logger.warning(f"paperId={paper_id!r} not found in raw_paper_searches")
            metrics.errors += 1
        except (GrobidUnavailableError, GrobidParseError) as exc:
            logger.warning(f"Failed to process paperId={paper_id!r}: {exc}")
            metrics.errors += 1
        except Exception as exc:
            logger.exception(f"Unexpected error processing paperId={paper_id!r}: {exc}")
            metrics.errors += 1

    logger.info(f"process_papers_by_id complete: {metrics}")
    return metrics


def get_full_paper_record(paper_id: str) -> dict | None:
    """Fetch a paper's full stored record from raw.paper_fulltext, or None if it
    hasn't been processed yet.
    """
    with ENGINE.connect() as conn:
        row = (
            conn.execute(
                text(
                    'SELECT "paperId", "status", "pdf_url", "full_text", "tei_xml", '
                    f'"grobid_version", "parsed_at" FROM {FULLTEXT_TABLE} WHERE "paperId" = :id'
                ),
                {"id": paper_id},
            )
            .mappings()
            .fetchone()
        )
    return dict(row) if row is not None else None


def get_or_create_full_paper(paper_id: str, max_chars: int = DEFAULT_MAX_CHARS) -> dict:
    """Return a paper's full-text record, resolving/downloading/parsing/chunking it on
    first request if it isn't already stored. See _process_one for the error semantics
    this surfaces (PaperNotFoundError, GrobidUnavailableError, GrobidParseError) that
    process_papers_by_id instead swallows for batch use.
    """
    cached = get_full_paper_record(paper_id)
    if cached is not None:
        return cached

    _process_one(paper_id, max_chars)

    record = get_full_paper_record(paper_id)
    assert record is not None, f"paperId={paper_id!r} was just processed but not found"
    return record
