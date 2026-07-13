import asyncio
import hashlib
import time
from datetime import datetime, timezone
from typing import Literal

from loguru import logger

from literature_ai.core.data_collect.get_ss_papers import _CONFIG, _SESSION
from literature_ai.db import execute_query, get_inspector, upsert_table
from literature_ai.core.processing.utils import create_embedding_run, resolve_embedding_run
from literature_ai.core.utils import get_project_root, load_dict

INPUT_TABLE = "processed.processed_abstracts"
EMBEDDINGS_TABLE = "processed.abstract_embeddings"

_EMBEDDINGS_CONFIG_DIR = get_project_root() / "config/core/embeddings"
_embedding_ndims: dict[str, int] = {
    load_dict(p)["embedding"]: load_dict(p)["embedding_ndim"]
    for p in _EMBEDDINGS_CONFIG_DIR.glob("*.yaml")
}

_last_call: float = 0.0


async def _collect_embedding_generator(
    ids: list[str],
    embedding: Literal["specter_v1", "specter_v2"],
):
    """Yields batches of {"paperId": str, "embedding": list[float]} dicts from the S2 batch API."""
    global _last_call

    endpoint = "graph/v1/paper/batch"

    for chunk in [ids[i : i + 500] for i in range(0, len(ids), 500)]:
        elapsed = time.time() - _last_call
        if elapsed < _CONFIG["delay_per_request"]:
            await asyncio.sleep(_CONFIG["delay_per_request"] - elapsed)

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: _SESSION.post(
                _CONFIG["url"] + endpoint,
                params={"fields": f"paperId,embedding.{embedding}"},
                json={"ids": chunk},
            ),
        )
        _last_call = time.time()

        if response.status_code != 200:
            logger.error(f"Error in API response. Status: {response.status_code}, body: {response.text[:500]}")
            break

        resp_data = response.json()
        if resp_data is None:
            logger.error(f"Empty response body for chunk starting at index {ids.index(chunk[0])}")
            break

        batch = []
        for paper in resp_data:
            if paper is None:
                logger.warning("Null value encountered in response")
                continue
            if paper.get("embedding") is None:
                logger.warning(f"No embedding for paperId {paper['paperId']}")
                continue
            batch.append(
                {
                    "paperId": paper["paperId"],
                    "embedding": paper["embedding"]["vector"],
                }
            )

        yield batch


def _hash_abstract(abstract: str | None) -> str:
    text = abstract or ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def collect_embeddings(embedding: Literal["specter_v1", "specter_v2"]) -> int | None:
    """Incrementally collect SPECTER embeddings for papers in INPUT_TABLE.

    The embedding vector is stored in a column named embedding_{ndim} in EMBEDDINGS_TABLE.
    The column is created via ALTER TABLE if it does not yet exist. Only processes rows
    that are new or whose abstract has changed since the last run.

    Returns the run_id used, or None if all rows were already up to date.
    """
    if embedding not in _embedding_ndims:
        raise ValueError(f"Unknown embedding '{embedding}'. Available: {list(_embedding_ndims)}")

    dim = _embedding_ndims[embedding]
    embedding_col = f"embedding_{dim}"

    inspector = get_inspector()
    existing_cols = [c["name"] for c in inspector.get_columns("abstract_embeddings", schema="processed")]
    if embedding_col not in existing_cols:
        logger.info(f"Adding column {embedding_col} VECTOR({dim}) to {EMBEDDINGS_TABLE}")
        execute_query(f'ALTER TABLE {EMBEDDINGS_TABLE} ADD COLUMN "{embedding_col}" VECTOR({dim})')

    input_result = execute_query(f'SELECT "paperId", "abstract" FROM {INPUT_TABLE}')
    input_hashes: dict[str, str] = {
        row[0]: _hash_abstract(row[1]) for row in input_result.fetchall()
    }

    try:
        run_id, _ = resolve_embedding_run(embedding, None, n_dim=dim, user_tags={})
    except ValueError:
        run_id = create_embedding_run(
            embedding_model=embedding,
            embedding_version=None,
            n_dim=dim,
            user_tags={},
            source="collect",
        )
    logger.info(f"collect_embeddings run_id: {run_id}")

    existing_result = execute_query(
        f'SELECT "paperId", content_hash FROM {EMBEDDINGS_TABLE} WHERE run_id = {run_id}'
    )
    existing_hashes: dict[str, str] = {
        row[0]: row[1] for row in existing_result.fetchall()
    }

    ids_to_process = [
        paper_id
        for paper_id, content_hash in input_hashes.items()
        if paper_id not in existing_hashes or existing_hashes[paper_id] != content_hash
    ]

    skipped = len(input_hashes) - len(ids_to_process)
    logger.info(f"collect_embeddings: {len(ids_to_process)} to process, {skipped} skipped (unchanged)")

    if not ids_to_process:
        return None

    async def _run():
        async for batch in _collect_embedding_generator(ids_to_process, embedding):
            now = datetime.now(timezone.utc)
            records = [
                {
                    "paperId": item["paperId"],
                    embedding_col: list(map(float, item["embedding"])),
                    "processed_at": now,
                    "content_hash": input_hashes[item["paperId"]],
                    "run_id": run_id,
                }
                for item in batch
            ]
            upsert_table(records, EMBEDDINGS_TABLE, conflict_cols=["paperId", "run_id"], do_update=True)
            logger.info(f"Upserted {len(records)} embeddings")

    asyncio.run(_run())
    logger.info("collect_embeddings complete")
    return run_id
