import asyncio

from sqlalchemy import text

from literature_ai.db import ENGINE
from literature_ai.search_service.data_collect.collect_full_papers import CHUNK_EMBEDDING_MODEL
from literature_ai.search_service.embeddings.core import get_embedding_model

CHUNKS_TABLE = "processed.paper_chunks"
FULLTEXT_TABLE = "raw.paper_fulltext"


async def rag_paper_chunks_async(paper_ids: list[str], query: str, n_results: int = 5) -> list[dict]:
    """Vector search over already-embedded chunks, scoped to paper_ids.

    Chunks are embedded once, with the fixed CHUNK_EMBEDDING_MODEL, when
    process_papers_by_id first chunks a paper - this only searches over what's already
    there, it doesn't chunk or embed on demand. Papers that haven't been processed yet
    simply contribute no results.

    Deliberately skips the HNSW-index requirement vector_search.py assumes for a
    corpus-wide search: paper_ids bounds the candidate set to a small, caller-controlled
    size, so a plain sequential scan over the pre-filtered rows is fine.
    """
    model = get_embedding_model(CHUNK_EMBEDDING_MODEL)
    query_embedding = await model.embed_query(query)
    query_vec_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    sql = text(f"""
        SELECT
            pc."paperId",
            pc.chunk_index,
            pc.section_header,
            pc.start_index,
            pc.end_index,
            pf.full_text,
            pc."embedding" <=> CAST(:query_vec AS vector) AS distance
        FROM {CHUNKS_TABLE} pc
        JOIN {FULLTEXT_TABLE} pf ON pf."paperId" = pc."paperId"
        WHERE pc."paperId" = ANY(:paper_ids)
          AND pc."embedding" IS NOT NULL
        ORDER BY pc."embedding" <=> CAST(:query_vec AS vector)
        LIMIT :n_results
    """)

    with ENGINE.connect() as conn:
        rows = conn.execute(
            sql,
            {"query_vec": query_vec_str, "paper_ids": paper_ids, "n_results": n_results},
        ).fetchall()

    results = []
    for paper_id, chunk_index, section_header, start_index, end_index, full_text, distance in rows:
        results.append(
            {
                "paperId": paper_id,
                "chunk_index": chunk_index,
                "section_header": section_header,
                "chunk_text": full_text[start_index:end_index],
                "distance": distance,
            }
        )
    return results


def rag_paper_chunks(paper_ids: list[str], query: str, n_results: int = 5) -> dict:
    """Restricted semantic search over chunks process_papers_by_id has already produced
    for paper_ids. Returns {"results": [...]}.

    Does not fetch/chunk/embed on demand - callers should ensure paper_ids have been
    processed (e.g. via data_collect.collect_full_papers.process_papers_by_id) first.
    """
    results = asyncio.run(rag_paper_chunks_async(paper_ids, query, n_results))
    return {"results": results}
