from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import requests
from sqlalchemy import text

from literature_ai.db import ENGINE, upsert_table
from literature_ai.search_service.parsing.grobid_client import (
    GrobidParseError,
    GrobidUnavailableError,
    call_grobid_fulltext,
    parse_tei_fulltext,
)
from literature_ai.search_service.session import make_session

RAW_PAPERS_TABLE = "raw.raw_paper_searches"
FULLTEXT_TABLE = "raw.paper_fulltext"

_pdf_session = make_session("pdf_download", max_retries=3, backoff_factor=2.0)

__all__ = [
    "FullPaperContent",
    "PaperNotFoundError",
    "PdfDownloadError",
    "GrobidParseError",
    "GrobidUnavailableError",
    "resolve_pdf_urls",
    "get_or_create_full_paper",
]


@dataclass
class FullPaperContent:
    paperId: str
    status: str
    pdf_url: Optional[str]
    full_text: Optional[str]
    tei_xml: Optional[str]
    grobid_version: Optional[str]
    parsed_at: datetime


class PaperNotFoundError(ValueError):
    """Raised when paper_id is not present in raw.raw_paper_searches."""


class PdfDownloadError(Exception):
    """Raised when the PDF could not be downloaded. Transient — never persisted."""


def resolve_pdf_urls(row: dict) -> list[str]:
    """Return candidate PDF URLs for a paper, in the order they should be tried.

    Prefers raw_paper_searches.url (Semantic Scholar's openAccessPdf.url), with the
    ArXiv-derived URL as a fallback candidate when an ArXiv ID is present - not just
    when `url` is absent, but also for get_or_create_full_paper to fall through to if
    `url` turns out not to actually be downloadable. row must have flat "url"/"ArXiV"
    keys, matching the columns in raw.raw_paper_searches (not S2's nested
    openAccessPdf/externalIds response shape).
    """
    candidates = []
    if row.get("url"):
        candidates.append(row["url"])
    if row.get("ArXiV"):
        arxiv_url = f"https://arxiv.org/pdf/{row['ArXiV']}"
        if arxiv_url not in candidates:
            candidates.append(arxiv_url)
    return candidates


def _download_first_available(pdf_urls: list[str]) -> tuple[str, bytes]:
    """Try each candidate URL in order, returning the first that downloads
    successfully as (pdf_url, pdf_bytes).

    Raises PdfDownloadError (not persisted, retryable) only once every candidate has
    failed, with details on each attempt.
    """
    errors = []
    for pdf_url in pdf_urls:
        try:
            response = _pdf_session.get(pdf_url, timeout=30)
            response.raise_for_status()
            return pdf_url, response.content
        except requests.exceptions.RequestException as exc:
            errors.append(f"{pdf_url}: {exc}")

    detail = "; ".join(errors)
    raise PdfDownloadError(f"Failed to download PDF from any candidate URL: {detail}")


_FULLTEXT_COLUMNS = (
    '"paperId", "status", "pdf_url", "full_text", "tei_xml", '
    '"grobid_version", "parsed_at"'
)


def _row_to_content(row) -> FullPaperContent:
    return FullPaperContent(
        paperId=row[0],
        status=row[1],
        pdf_url=row[2],
        full_text=row[3],
        tei_xml=row[4],
        grobid_version=row[5],
        parsed_at=row[6],
    )


def _persist(record: dict) -> FullPaperContent:
    upsert_table([record], FULLTEXT_TABLE, conflict_cols=["paperId"], do_update=True)
    return FullPaperContent(**record)


def get_or_create_full_paper(paper_id: str) -> FullPaperContent:
    """Return a paper's parsed full text, parsing and persisting it on first request.

    1. Cache hit -> return the stored row as-is.
    2. Unknown paper_id -> raise PaperNotFoundError.
    3. No candidate PDF URL -> persist and return status="no_pdf_available".
    4. Every candidate PDF URL fails to download -> raise PdfDownloadError (not
       persisted, retryable). If `url` fails but an ArXiv URL is also available, the
       ArXiv URL is tried next before giving up.
    5. GROBID call/parse fails -> raise GrobidUnavailableError/GrobidParseError
       (not persisted, retryable).
    6. Success -> persist and return status="success".
    """
    with ENGINE.connect() as conn:
        cached = conn.execute(
            text(f'SELECT {_FULLTEXT_COLUMNS} FROM {FULLTEXT_TABLE} WHERE "paperId" = :id'),
            {"id": paper_id},
        ).fetchone()
    if cached is not None:
        return _row_to_content(cached)

    with ENGINE.connect() as conn:
        paper = conn.execute(
            text(f'SELECT "url", "ArXiV" FROM {RAW_PAPERS_TABLE} WHERE "paperId" = :id'),
            {"id": paper_id},
        ).fetchone()
    if paper is None:
        raise PaperNotFoundError(f"No paper found for paperId={paper_id!r}")

    pdf_urls = resolve_pdf_urls({"url": paper[0], "ArXiV": paper[1]})
    if not pdf_urls:
        return _persist(
            {
                "paperId": paper_id,
                "status": "no_pdf_available",
                "pdf_url": None,
                "full_text": None,
                "tei_xml": None,
                "grobid_version": None,
                "parsed_at": datetime.now(timezone.utc),
            }
        )

    pdf_url, pdf_bytes = _download_first_available(pdf_urls)

    tei_xml = call_grobid_fulltext(pdf_bytes)
    parsed = parse_tei_fulltext(tei_xml)

    return _persist(
        {
            "paperId": paper_id,
            "status": "success",
            "pdf_url": pdf_url,
            "full_text": parsed["body_text"],
            "tei_xml": tei_xml,
            "grobid_version": parsed["grobid_version"],
            "parsed_at": datetime.now(timezone.utc),
        }
    )
