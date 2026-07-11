import asyncio
import hashlib
from datetime import datetime, timezone

from loguru import logger

from literature_ai.db import execute_query, get_inspector, upsert_table
from literature_ai.core.embeddings.core import get_embedding_model
from literature_ai.core.processing.utils import create_embedding_run, resolve_embedding_run

INPUT_TABLE = "processed.processed_abstracts"
EMBEDDINGS_TABLE = "processed.abstract_embeddings"
BATCH_SIZE = 64


def _hash_content(title: str | None, abstract: str | None) -> str:
    combined = (title or "") + (abstract or "")
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def generate_paper_embeddings(embedding_model: str) -> int | None:
    """Incrementally generate embeddings for papers in processed_abstracts.

    Uses get_embedding_model() to instantiate the model locally, embeds
    title + abstract via embed_paper(), and writes vectors to abstract_embeddings.
    Only processes rows whose title+abstract content hash has changed since the
    last run. Returns the run_id used, or None if all rows were already up to date.
    """
    model = get_embedding_model(embedding_model)
    dim = model.n_dim
    version = model.version
    embedding_col = f"embedding_{dim}"

    inspector = get_inspector()
    existing_cols = [c["name"] for c in inspector.get_columns("abstract_embeddings", schema="processed")]
    if embedding_col not in existing_cols:
        logger.info(f"Adding column {embedding_col} VECTOR({dim}) to {EMBEDDINGS_TABLE}")
        execute_query(f'ALTER TABLE {EMBEDDINGS_TABLE} ADD COLUMN "{embedding_col}" VECTOR({dim})')

    result = execute_query(
        f'SELECT "paperId", "title", "abstract" FROM {INPUT_TABLE}'
    )
    rows = result.fetchall()
    if not rows:
        logger.info("generate_paper_embeddings: no rows in processed_abstracts")
        return None

    input_hashes = {row[0]: _hash_content(row[1], row[2]) for row in rows}
    input_data = {row[0]: (row[1] or "", row[2] or "") for row in rows}

    existing_result = execute_query(
        f'SELECT "paperId", content_hash FROM {EMBEDDINGS_TABLE} WHERE "{embedding_col}" IS NOT NULL'
    )
    existing_hashes = {r[0]: r[1] for r in existing_result.fetchall()}

    ids_to_process = [
        pid for pid, h in input_hashes.items()
        if pid not in existing_hashes or existing_hashes[pid] != h
    ]
    skipped = len(input_hashes) - len(ids_to_process)
    logger.info(
        f"generate_paper_embeddings: {len(ids_to_process)} to process, {skipped} skipped (unchanged)"
    )

    if not ids_to_process:
        return None

    try:
        run_id, _ = resolve_embedding_run(embedding_model, version, n_dim=dim, user_tags={})
    except ValueError:
        run_id = create_embedding_run(
            embedding_model=embedding_model,
            embedding_version=version,
            n_dim=dim,
            user_tags={},
            source="generate",
        )
    logger.info(f"generate_paper_embeddings run_id: {run_id}")

    async def _run():
        for i in range(0, len(ids_to_process), BATCH_SIZE):
            batch_ids = ids_to_process[i : i + BATCH_SIZE]
            now = datetime.now(timezone.utc)
            tasks = [model.embed_paper(input_data[pid][0], input_data[pid][1]) for pid in batch_ids]
            vectors = await asyncio.gather(*tasks)
            records = [
                {
                    "paperId": pid,
                    embedding_col: list(map(float, vec)),
                    "processed_at": now,
                    "content_hash": input_hashes[pid],
                    "run_id": run_id,
                }
                for pid, vec in zip(batch_ids, vectors)
            ]
            upsert_table(records, EMBEDDINGS_TABLE, conflict_cols=["paperId"], do_update=True)
            logger.info(f"Upserted {len(records)} embeddings (batch {i // BATCH_SIZE + 1})")

    asyncio.run(_run())
    logger.info("generate_paper_embeddings complete")
    return run_id
