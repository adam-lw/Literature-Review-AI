import asyncio
import hashlib
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import text

from literature_ai.db import ENGINE, execute_query, get_inspector, upsert_table
from literature_ai.search_service.chunking.chunker import DEFAULT_MAX_CHARS, chunk_sections
from literature_ai.search_service.embeddings.core import get_embedding_model
from literature_ai.search_service.full_paper.service import get_or_create_full_paper
from literature_ai.search_service.parsing.grobid_client import extract_sections
from literature_ai.search_service.processing.utils import (
    create_embedding_run,
    resolve_embedding_run,
)

CHUNKS_TABLE = "processed.paper_chunks"
CHUNK_EMBEDDINGS_TABLE = "processed.chunk_embeddings"
BATCH_SIZE = 64

_CHUNKS_COLUMNS = (
    '"paperId", "chunk_index", "section_index", "section_header", '
    '"chunk_text", "char_count", "content_hash", "chunked_at"'
)


def _hash_text(text_: str) -> str:
    return hashlib.sha256(text_.encode("utf-8")).hexdigest()


def _row_to_chunk_dict(row) -> dict:
    return {
        "paperId": row[0],
        "chunk_index": row[1],
        "section_index": row[2],
        "section_header": row[3],
        "chunk_text": row[4],
        "char_count": row[5],
        "content_hash": row[6],
        "chunked_at": row[7],
    }


def ensure_paper_chunks(paper_id: str, max_chars: int = DEFAULT_MAX_CHARS) -> list[dict]:
    """Ensure processed.paper_chunks rows exist for paper_id, computing and persisting
    them on first request.

    Cache-through, mirroring get_or_create_full_paper: any existing rows for paper_id
    are returned as-is (no recompute) - paper_chunks content is immutable once written,
    since raw.paper_fulltext.full_text never changes after first parse. Returns []
    (not an error) if the paper has no full text (status == "no_pdf_available"),
    mirroring how get_or_create_full_paper itself treats a missing PDF as a stable,
    cacheable outcome rather than a failure.

    Propagates PaperNotFoundError / PdfDownloadError / GrobidUnavailableError /
    GrobidParseError from get_or_create_full_paper unchanged.
    """
    with ENGINE.connect() as conn:
        existing = conn.execute(
            text(
                f'SELECT {_CHUNKS_COLUMNS} FROM {CHUNKS_TABLE} '
                f'WHERE "paperId" = :id ORDER BY chunk_index'
            ),
            {"id": paper_id},
        ).fetchall()
    if existing:
        return [_row_to_chunk_dict(row) for row in existing]

    full_paper = get_or_create_full_paper(paper_id)
    if not full_paper.tei_xml:
        return []

    sections = extract_sections(full_paper.tei_xml)
    chunks = chunk_sections(sections, max_chars=max_chars)
    if not chunks:
        return []

    now = datetime.now(timezone.utc)
    records = [
        {
            "paperId": paper_id,
            "chunk_index": chunk.chunk_index,
            "section_index": chunk.section_index,
            "section_header": chunk.section_header,
            "chunk_text": chunk.text,
            "char_count": len(chunk.text),
            "content_hash": _hash_text(chunk.text),
            "chunked_at": now,
        }
        for chunk in chunks
    ]
    upsert_table(records, CHUNKS_TABLE, conflict_cols=["paperId", "chunk_index"], do_update=True)
    return records


def generate_chunk_embeddings(
    paper_ids: list[str],
    embedding_model: str,
    user_tags: dict | None = None,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> int:
    """Ensure chunk embeddings exist for paper_ids under embedding_model, computing
    chunks/embeddings on demand as needed. Returns the run_id used.

    For each paper_id: ensure_paper_chunks() (papers with no PDF contribute no chunks,
    not an error). Resolves-or-creates a target="chunk" embedding run - mirrors
    generate_paper_embeddings.py's try/resolve-then-create pattern, keyed on the
    model's own reported version (model.version), not a caller-supplied override, for
    consistency with how abstract-embedding runs are versioned. Ensures the
    embedding_{dim} column exists on chunk_embeddings. Embeds only chunks not yet
    present in chunk_embeddings for this run (existence check, not content-hash
    comparison - paper_chunks content is immutable once written) via
    model.embed_text(), batched with asyncio.gather. Upserts and returns run_id.

    Note: model.embed_text() raises NotImplementedError for some models (e.g.
    SpecterV1Embedding/SpecterV2Embedding, which are paper-title+abstract-only) -
    callers should map that to a 4xx, not treat it as a transient failure.
    """
    model = get_embedding_model(embedding_model)
    dim = model.n_dim
    version = model.version
    embedding_col = f"embedding_{dim}"

    run_tags = dict(user_tags or {})
    run_tags.setdefault("chunk_max_chars", max_chars)

    try:
        run_id, _ = resolve_embedding_run(
            embedding_model, version, n_dim=dim, user_tags=run_tags, target="chunk"
        )
    except ValueError:
        run_id = create_embedding_run(
            embedding_model=embedding_model,
            embedding_version=version,
            n_dim=dim,
            user_tags=run_tags,
            source="generate",
            target="chunk",
        )
    logger.info(f"generate_chunk_embeddings run_id: {run_id}")

    inspector = get_inspector()
    existing_cols = [
        c["name"] for c in inspector.get_columns("chunk_embeddings", schema="processed")
    ]
    if embedding_col not in existing_cols:
        logger.info(f"Adding column {embedding_col} VECTOR({dim}) to {CHUNK_EMBEDDINGS_TABLE}")
        execute_query(
            f'ALTER TABLE {CHUNK_EMBEDDINGS_TABLE} ADD COLUMN "{embedding_col}" VECTOR({dim})'
        )

    all_chunks: list[dict] = []
    for paper_id in paper_ids:
        all_chunks.extend(ensure_paper_chunks(paper_id, max_chars=max_chars))

    if not all_chunks:
        return run_id

    with ENGINE.connect() as conn:
        existing_result = conn.execute(
            text(
                f'SELECT "paperId", chunk_index FROM {CHUNK_EMBEDDINGS_TABLE} '
                f'WHERE run_id = :run_id AND "paperId" = ANY(:paper_ids)'
            ),
            {"run_id": run_id, "paper_ids": paper_ids},
        ).fetchall()
    already_embedded = {(row[0], row[1]) for row in existing_result}

    to_embed = [
        chunk for chunk in all_chunks
        if (chunk["paperId"], chunk["chunk_index"]) not in already_embedded
    ]
    if not to_embed:
        return run_id

    async def _run():
        for i in range(0, len(to_embed), BATCH_SIZE):
            batch = to_embed[i : i + BATCH_SIZE]
            now = datetime.now(timezone.utc)
            tasks = [model.embed_text(chunk["chunk_text"]) for chunk in batch]
            vectors = await asyncio.gather(*tasks)
            records = [
                {
                    "paperId": chunk["paperId"],
                    "chunk_index": chunk["chunk_index"],
                    embedding_col: list(map(float, vector)),
                    "processed_at": now,
                    "content_hash": chunk["content_hash"],
                    "run_id": run_id,
                }
                for chunk, vector in zip(batch, vectors)
            ]
            upsert_table(
                records,
                CHUNK_EMBEDDINGS_TABLE,
                conflict_cols=["paperId", "chunk_index", "run_id"],
                do_update=True,
            )
            logger.info(
                f"Upserted {len(records)} chunk embeddings (batch {i // BATCH_SIZE + 1})"
            )

    asyncio.run(_run())
    logger.info(f"generate_chunk_embeddings complete for run_id={run_id}")
    return run_id
