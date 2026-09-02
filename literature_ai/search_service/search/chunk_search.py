import asyncio

from sqlalchemy import text

from literature_ai.db import ENGINE
from literature_ai.search_service.chunking.service import generate_chunk_embeddings
from literature_ai.search_service.embeddings.core import get_embedding_model

CHUNK_EMBEDDINGS_TABLE = "processed.chunk_embeddings"
CHUNKS_TABLE = "processed.paper_chunks"


async def rag_paper_chunks_async(
    paper_ids: list[str],
    query: str,
    run_id: int,
    n_results: int = 5,
) -> list[dict]:
    """Restricted vector search over chunk embeddings, scoped to paper_ids + a single
    run_id.

    Unlike vector_search.py's corpus-wide assumption (which requires a prebuilt HNSW
    index via verify_index), this deliberately skips that check: paper_ids bounds the
    candidate set to a small, caller-controlled size, so a plain sequential scan over
    the pre-filtered rows is fine.
    """
    with ENGINE.connect() as conn:
        meta_row = conn.execute(
            text(
                "SELECT embedding_model, n_dim, target FROM processed.embedding_runs_metadata "
                "WHERE run_id = :run_id"
            ),
            {"run_id": run_id},
        ).fetchone()
    if meta_row is None:
        raise ValueError(f"No embedding run found for run_id={run_id}")
    model_name, n_dim, target = meta_row
    if target != "chunk":
        raise ValueError(f"run_id={run_id} is a {target!r}-target run, not a chunk-embedding run")
    embedding_col = f"embedding_{n_dim}"

    model = get_embedding_model(model_name)
    query_embedding = await model.embed_query(query)
    query_vec_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    sql = text(f"""
        SELECT
            ce."paperId",
            ce.chunk_index,
            pc.section_header,
            pc.chunk_text,
            ce."{embedding_col}" <=> CAST(:query_vec AS vector) AS distance
        FROM {CHUNK_EMBEDDINGS_TABLE} ce
        JOIN {CHUNKS_TABLE} pc
          ON ce."paperId" = pc."paperId" AND ce.chunk_index = pc.chunk_index
        WHERE ce.run_id = :run_id
          AND ce."paperId" = ANY(:paper_ids)
          AND ce."{embedding_col}" IS NOT NULL
        ORDER BY ce."{embedding_col}" <=> CAST(:query_vec AS vector)
        LIMIT :n_results
    """)

    with ENGINE.connect() as conn:
        rows = conn.execute(
            sql,
            {
                "query_vec": query_vec_str,
                "run_id": run_id,
                "paper_ids": paper_ids,
                "n_results": n_results,
            },
        ).fetchall()

    keys = ["paperId", "chunk_index", "section_header", "chunk_text", "distance"]
    return [dict(zip(keys, row)) for row in rows]


def rag_paper_chunks(
    paper_ids: list[str],
    query: str,
    embedding_model: str,
    n_results: int = 5,
) -> dict:
    """Orchestrates generate_chunk_embeddings() (ensures the given papers are
    chunked+embedded, on demand) and rag_paper_chunks_async() (restricted similarity
    search). Returns {"run_id": int, "results": [...]}.

    Propagates PaperNotFoundError / PdfDownloadError / GrobidUnavailableError /
    GrobidParseError / NotImplementedError from the embedding generation step
    unchanged.
    """
    run_id = generate_chunk_embeddings(paper_ids, embedding_model)
    results = asyncio.run(rag_paper_chunks_async(paper_ids, query, run_id, n_results))
    return {"run_id": run_id, "results": results}
