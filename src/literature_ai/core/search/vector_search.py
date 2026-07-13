import asyncio
from typing import Optional

from sqlalchemy import text

from literature_ai.core.agent.tools import tool
from literature_ai.db import ENGINE
from literature_ai.core.embeddings import get_embedding_model
from literature_ai.core.processing.utils import resolve_embedding_run, verify_index

EMBEDDINGS_TABLE = "processed.abstract_embeddings"


async def vector_search_async(
    query: str,
    model_name: Optional[str] = None,
    run_id: Optional[int] = None,
    model_version: Optional[str] = None,
    n_dim: Optional[int] = None,
    n_results: int = 5,
) -> list[dict]:
    """Async implementation of vector search. Prefer this in async contexts (e.g. Jupyter)."""
    if run_id is not None:
        with ENGINE.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT embedding_model, n_dim FROM processed.embedding_runs_metadata"
                    " WHERE run_id = :run_id"
                ),
                {"run_id": run_id},
            ).fetchone()
        if row is None:
            raise ValueError(f"No embedding run found for run_id={run_id}")
        model_name, resolved_dim = row[0], row[1]
    else:
        if model_name is None:
            raise ValueError("Either model_name or run_id must be provided")
        run_id, resolved_dim = resolve_embedding_run(model_name, model_version, n_dim)
    verify_index(run_id)
    embedding_col = f"embedding_{resolved_dim}"

    model = get_embedding_model(model_name)
    query_embedding = await model.embed_query(query)
    query_vec_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    sql = text(f"""
        SELECT
            ae."paperId",
            r.title,
            r.abstract,
            r.year,
            r.venue,
            r."citationCount",
            ae."{embedding_col}" <-> CAST(:query_vec AS vector) AS distance
        FROM {EMBEDDINGS_TABLE} ae
        JOIN raw.raw_paper_searches r ON ae."paperId" = r."paperId"
        WHERE ae.run_id = :run_id
          AND ae."{embedding_col}" IS NOT NULL
        ORDER BY ae."{embedding_col}" <-> CAST(:query_vec AS vector)
        LIMIT :n_results
    """)

    with ENGINE.connect() as conn:
        rows = conn.execute(
            sql,
            {"query_vec": query_vec_str, "run_id": run_id, "n_results": n_results},
        ).fetchall()

    keys = ["paperId", "title", "abstract", "year", "venue", "citationCount", "distance"]
    return [dict(zip(keys, row)) for row in rows]


@tool(
    name="vector_search",
    description="Perform a vector search using embeddings to find similar documents",
)
def vector_search(
    query: str,
    model_name: Optional[str] = None,
    run_id: Optional[int] = None,
    model_version: Optional[str] = None,
    n_dim: Optional[int] = None,
    n_results: int = 5,
) -> list[dict]:
    """Perform a vector search over abstract embeddings.

    Parameters
    ----------
    query : str
        Natural-language search query.
    model_name : str or None
        Embedding model name (e.g. ``"specter_v2"``). Required when
        ``run_id`` is not provided.
    run_id : int or None
        Embedding run ID. When provided, model metadata is looked up
        directly and ``model_name`` / ``model_version`` / ``n_dim`` are
        ignored.
    model_version : str or None
        Model version string. ``None`` matches runs where ``embedding_version``
        is ``NULL``. Only used when ``run_id`` is ``None``.
    n_dim : int or None
        Embedding dimensionality. Only used when ``run_id`` is ``None``.
    n_results : int
        Number of nearest neighbours to return. Default is ``5``.

    Returns
    -------
    list of dict
        Each dict contains ``paperId``, ``title``, ``abstract``, ``year``,
        ``venue``, ``citationCount``, and ``distance`` (cosine distance to
        the query vector), ordered by ascending distance.

    Raises
    ------
    ValueError
        If neither ``model_name`` nor ``run_id`` is provided, or if no
        matching embedding run is found.
    """
    return asyncio.run(
        vector_search_async(query, model_name, run_id, model_version, n_dim, n_results)
    )
