import json
from typing import Literal

from sqlalchemy import text

from literature_ai.db import ENGINE

# Physical embeddings table for each run "target". Shared run bookkeeping
# (embedding_runs_metadata) distinguishes abstract vs. chunk runs via a "target"
# column, but each target's vectors live in its own table (abstract_embeddings is
# keyed one-row-per-paper, which can't represent many chunks per paper).
TARGET_TABLES: dict[str, str] = {
    "abstract": "processed.abstract_embeddings",
    "chunk": "processed.chunk_embeddings",
}


def resolve_embedding_run(
    model_name: str,
    model_version: str | None,
    n_dim: int | None = None,
    user_tags: dict | None = None,
    target: Literal["abstract", "chunk"] = "abstract",
) -> tuple[int, int]:
    """Resolve an existing embedding run to its run_id and n_dim.

    Parameters
    ----------
    model_name : str
        Value of ``embedding_model`` to match.
    model_version : str or None
        Value of ``embedding_version`` to match. ``None`` matches rows where
        ``embedding_version`` is ``NULL``.
    n_dim : int or None
        When provided, only rows with this dimensionality are considered.
        When ``None``, all rows matching the other criteria are considered;
        raises ``ValueError`` if they span more than one distinct
        dimensionality.
    user_tags : dict or None
        When provided, only rows whose ``user_tags`` exactly match are
        considered. When ``None``, rows with any tag set are included.
    target : {"abstract", "chunk"}
        Whether to resolve an abstract-embedding run or a chunk-embedding run.
        Defaults to ``"abstract"`` to preserve existing callers' behavior.

    Returns
    -------
    run_id : int
        The run_id of the resolved run (highest id when multiple runs share
        the same dimensionality).
    n_dim : int
        The resolved embedding dimensionality.

    Raises
    ------
    ValueError
        If no matching run is found, or if ``n_dim`` is ``None`` and the
        resolved rows span more than one distinct dimensionality.
    """
    tags_json = json.dumps(user_tags, sort_keys=True) if user_tags is not None else None
    sql = text("""
        SELECT run_id, n_dim
        FROM processed.embedding_runs_metadata
        WHERE embedding_model = :model
          AND embedding_version IS NOT DISTINCT FROM :version
          AND target = :target
          AND (:n_dim IS NULL OR n_dim = :n_dim)
          AND (:tags IS NULL OR user_tags = CAST(:tags AS jsonb))
    """)
    with ENGINE.connect() as conn:
        rows = conn.execute(
            sql,
            {
                "model": model_name,
                "version": model_version,
                "target": target,
                "n_dim": n_dim,
                "tags": tags_json,
            },
        ).fetchall()

    if not rows:
        detail = f"model={model_name!r}, version={model_version!r}"
        if n_dim is not None:
            detail += f", n_dim={n_dim}"
        if user_tags is not None:
            detail += f", user_tags={user_tags!r}"
        raise ValueError(f"No embedding run found for {detail}")

    distinct_dims = {row[1] for row in rows}
    if len(distinct_dims) > 1:
        raise ValueError(
            f"Ambiguous embedding run: model={model_name!r}, version={model_version!r} matches "
            f"multiple n_dims {sorted(distinct_dims)}. Specify n_dim to disambiguate."
        )

    run_id = max(row[0] for row in rows)
    return run_id, distinct_dims.pop()


def verify_index(run_id: int) -> None:
    """Verify that an HNSW index exists on the run's embeddings table for the given run_id.

    Parameters
    ----------
    run_id : int
        The embedding run to check.

    Raises
    ------
    ValueError
        If no matching run exists, or if no index named ``hnsw_{run_id}`` exists on
        the resolved embeddings table (``processed.abstract_embeddings`` or
        ``processed.chunk_embeddings``, depending on the run's ``target``).
    """
    with ENGINE.connect() as conn:
        meta_row = conn.execute(
            text("SELECT target FROM processed.embedding_runs_metadata WHERE run_id = :rid"),
            {"rid": run_id},
        ).fetchone()
        if meta_row is None:
            raise ValueError(f"No embedding run found for run_id={run_id!r}")
        table_name = TARGET_TABLES[meta_row[0]].split(".")[-1]

        row = conn.execute(
            text("""
                SELECT indexname FROM pg_indexes
                WHERE schemaname = 'processed'
                  AND tablename = :table_name
                  AND indexname = 'hnsw_' || :run_id
            """),
            {"run_id": run_id, "table_name": table_name},
        ).fetchone()
    if row is None:
        raise ValueError(
            f"No HNSW index found for run_id={run_id}. "
            "Run create_hnsw_index() before searching."
        )


def create_embedding_run(
    embedding_model: str,
    embedding_version: str | None,
    n_dim: int,
    user_tags: dict,
    source: Literal["collect", "generate"],
    target: Literal["abstract", "chunk"] = "abstract",
) -> int:
    """Create a new embedding run row and return its run_id.

    Parameters
    ----------
    embedding_model : str
        Embedding model name.
    embedding_version : str or None
        Model version string, or ``None``.
    n_dim : int
        Embedding dimensionality.
    user_tags : dict
        Arbitrary metadata tags to attach to the run.
    source : {"collect", "generate"}
        Whether embeddings were collected from an external API or generated
        locally.
    target : {"abstract", "chunk"}
        Whether this run is for abstract embeddings or full-paper-chunk
        embeddings. Defaults to ``"abstract"`` to preserve existing callers'
        behavior.

    Returns
    -------
    int
        The ``run_id`` of the newly created row.

    Raises
    ------
    ValueError
        If a run with the same parameter combination already exists.
    """
    tags_json = json.dumps(user_tags, sort_keys=True)
    check_sql = text("""
        SELECT run_id FROM processed.embedding_runs_metadata
        WHERE embedding_model = :model
          AND COALESCE(embedding_version, '') = COALESCE(:version, '')
          AND n_dim = :n_dim
          AND user_tags = CAST(:tags AS jsonb)
          AND source = :source
          AND target = :target
        LIMIT 1
    """)
    insert_sql = text("""
        INSERT INTO processed.embedding_runs_metadata
            (embedding_model, embedding_version, n_dim, user_tags, source, target)
        VALUES (:model, :version, :n_dim, CAST(:tags AS jsonb), :source, :target)
        RETURNING run_id
    """)
    params = {
        "model": embedding_model,
        "version": embedding_version,
        "n_dim": n_dim,
        "tags": tags_json,
        "source": source,
        "target": target,
    }
    with ENGINE.begin() as conn:
        existing = conn.execute(check_sql, params).fetchone()
        if existing is not None:
            raise ValueError(
                f"Embedding run already exists for model={embedding_model!r}, "
                f"version={embedding_version!r}, n_dim={n_dim}, "
                f"user_tags={user_tags!r}, source={source!r} (run_id={existing[0]})"
            )
        row = conn.execute(insert_sql, params).fetchone()
    assert row is not None
    return row[0]
