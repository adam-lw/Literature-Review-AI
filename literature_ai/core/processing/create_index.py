from loguru import logger
from sqlalchemy import text

from literature_ai.db import ENGINE

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
    """Create a partial HNSW index on abstract_embeddings for the given run_id.

    The index covers only rows where run_id matches, using the vector column
    determined by the run's n_dim. Idempotent — safe to call multiple times.
    Returns the index name.
    """
    if distance not in _OPS:
        raise ValueError(f"distance must be one of {list(_OPS)}, got {distance!r}")

    ops = _OPS[distance]

    with ENGINE.connect() as conn:
        row = conn.execute(
            text("SELECT n_dim FROM processed.embedding_runs_metadata WHERE run_id = :rid"),
            {"rid": run_id},
        ).fetchone()

    if row is None:
        raise ValueError(f"No embedding run found for run_id={run_id!r}")

    n_dim = row[0]
    embedding_col = f"embedding_{n_dim}"
    index_name = f"hnsw_{run_id}"

    ddl = (
        f'CREATE INDEX IF NOT EXISTS "{index_name}" '
        f"ON processed.abstract_embeddings "
        f'USING hnsw ("{embedding_col}" {ops}) '
        f"WITH (m = {m}, ef_construction = {ef_construction}) "
        f"WHERE run_id = {run_id}"
    )

    with ENGINE.connect() as conn:
        n_rows = conn.execute(
            text("SELECT COUNT(*) FROM processed.abstract_embeddings WHERE run_id = :rid"),
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
