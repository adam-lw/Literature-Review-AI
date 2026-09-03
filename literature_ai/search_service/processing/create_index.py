from loguru import logger
from sqlalchemy import text

from literature_ai.db import ENGINE
from literature_ai.search_service.processing.utils import TARGET_TABLES

_OPS = {
    "cosine": "vector_cosine_ops",
    "l2": "vector_l2_ops",
    "ip": "vector_ip_ops",
}


def create_hnsw_index(
    run_id: int,
    m: int = 16,
    ef_construction: int = 64,
    distance: str = "cosine",
) -> str:
    """Create a partial HNSW index for the given run_id.

    The index covers only rows where run_id matches, using the vector column
    determined by the run's n_dim, on whichever embeddings table matches the run's
    target (abstract_embeddings or chunk_embeddings). Idempotent — safe to call
    multiple times. Returns the index name.
    """
    if distance not in _OPS:
        raise ValueError(f"distance must be one of {list(_OPS)}, got {distance!r}")

    ops = _OPS[distance]

    with ENGINE.connect() as conn:
        row = conn.execute(
            text(
                "SELECT n_dim, target FROM processed.embedding_runs_metadata WHERE run_id = :rid"
            ),
            {"rid": run_id},
        ).fetchone()

    if row is None:
        raise ValueError(f"No embedding run found for run_id={run_id!r}")

    n_dim, target = row
    table = TARGET_TABLES[target]
    embedding_col = f"embedding_{n_dim}"
    index_name = f"hnsw_{run_id}"

    ddl = (
        f'CREATE INDEX IF NOT EXISTS "{index_name}" '
        f"ON {table} "
        f'USING hnsw ("{embedding_col}" {ops}) '
        f"WITH (m = {m}, ef_construction = {ef_construction}) "
        f"WHERE run_id = {run_id}"
    )

    with ENGINE.connect() as conn:
        n_rows = conn.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE run_id = :rid"),
            {"rid": run_id},
        ).scalar()

    logger.info(
        f"Creating HNSW index {index_name!r} over {n_rows:,} rows "
        f"(run_id={run_id}, col={embedding_col}, distance={distance}, m={m}, ef_construction={ef_construction})"
    )

    with ENGINE.begin() as conn:
        conn.execute(text(ddl))

    logger.info(f"HNSW index {index_name!r} ready")
    return index_name


def create_keyword_search_index() -> str:
    """Create the GIN index on abstract_keyword_vectors.search_vector.

    Idempotent — safe to call multiple times. Returns the index name.
    """
    index_name = "abstract_keyword_vectors_search_vector_idx"
    ddl = (
        f'CREATE INDEX IF NOT EXISTS "{index_name}" '
        f'ON processed.abstract_keyword_vectors USING GIN ("search_vector")'
    )

    with ENGINE.begin() as conn:
        conn.execute(text(ddl))

    logger.info(f"Keyword search GIN index {index_name!r} ready")
    return index_name
