import hashlib
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import text

from literature_ai.db import ENGINE, execute_query

INPUT_TABLE = "processed.processed_abstracts"
OUTPUT_TABLE = "processed.abstract_keyword_vectors"

# search_vector is a plain (non-generated) column, not a Postgres GENERATED column:
# it's derived from title+abstract in a *different* table (processed_abstracts), and
# GENERATED expressions can only reference columns in their own row/table. So this
# value is computed here, at write time, via a SQL expression bound into the upsert.
_UPSERT_SQL = text(f"""
    INSERT INTO {OUTPUT_TABLE} ("paperId", "search_vector", "content_hash", "processed_at")
    VALUES (
        :paper_id,
        setweight(to_tsvector('english', :title), 'A')
            || setweight(to_tsvector('english', :abstract), 'B'),
        :content_hash,
        :processed_at
    )
    ON CONFLICT ("paperId") DO UPDATE SET
        "search_vector" = EXCLUDED."search_vector",
        "content_hash" = EXCLUDED."content_hash",
        "processed_at" = EXCLUDED."processed_at"
""")


def _hash_content(title: str | None, abstract: str | None) -> str:
    combined = (title or "") + (abstract or "")
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def build_keyword_vectors() -> int:
    """Incrementally (re)build Postgres full-text search vectors for processed
    title+abstracts, writing to processed.abstract_keyword_vectors.

    Mirrors generate_paper_embeddings.py's incremental pattern: only (re)computes
    rows whose title+abstract content hash has changed since the last run. Returns
    the number of rows upserted.
    """
    result = execute_query(f'SELECT "paperId", "title", "abstract" FROM {INPUT_TABLE}')
    rows = result.fetchall()
    if not rows:
        logger.info("build_keyword_vectors: no rows in processed_abstracts")
        return 0

    input_hashes = {row[0]: _hash_content(row[1], row[2]) for row in rows}
    input_data = {row[0]: (row[1] or "", row[2] or "") for row in rows}

    existing_result = execute_query(f'SELECT "paperId", content_hash FROM {OUTPUT_TABLE}')
    existing_hashes = {r[0]: r[1] for r in existing_result.fetchall()}

    ids_to_process = [
        pid
        for pid, h in input_hashes.items()
        if pid not in existing_hashes or existing_hashes[pid] != h
    ]
    skipped = len(input_hashes) - len(ids_to_process)
    logger.info(
        f"build_keyword_vectors: {len(ids_to_process)} to process, {skipped} skipped (unchanged)"
    )

    if not ids_to_process:
        return 0

    now = datetime.now(timezone.utc)
    params = [
        {
            "paper_id": pid,
            "title": input_data[pid][0],
            "abstract": input_data[pid][1],
            "content_hash": input_hashes[pid],
            "processed_at": now,
        }
        for pid in ids_to_process
    ]

    with ENGINE.begin() as conn:
        conn.execute(_UPSERT_SQL, params)

    logger.info(f"build_keyword_vectors: upserted {len(params)} rows")
    return len(params)
