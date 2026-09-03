from sqlalchemy import text

from literature_ai.db import ENGINE

KEYWORD_VECTORS_TABLE = "processed.abstract_keyword_vectors"


def keyword_search(query: str, n_results: int = 10) -> list[dict]:
    """Keyword search over paper title+abstracts via Postgres native full-text search.

    Uses ts_rank_cd (cover-density ranking) over search vectors built by
    processing/build_keyword_vectors.py - this is Postgres's own full-text search
    ranking, not the BM25 formula (different term-weighting/normalization). `rank`
    (higher = more relevant) is therefore NOT on a comparable scale to
    vector_search's `distance` (lower = more relevant); a future hybrid_search must
    combine the two result lists by row position (e.g. Reciprocal Rank Fusion), not
    by comparing raw scores.

    websearch_to_tsquery parses `query` with natural search syntax (quoted phrases,
    "-exclusion", "OR") and never raises on malformed input - a query that reduces to
    no lexemes (e.g. stopwords only) simply matches nothing, returning [].
    """
    sql = text(f"""
        SELECT
            akv."paperId",
            r.title,
            r.abstract,
            r.year,
            r.venue,
            r."citationCount",
            r.url,
            r."DOI",
            ts_rank_cd(akv.search_vector, websearch_to_tsquery('english', :query)) AS rank
        FROM {KEYWORD_VECTORS_TABLE} akv
        JOIN raw.raw_paper_searches r ON akv."paperId" = r."paperId"
        WHERE akv.search_vector @@ websearch_to_tsquery('english', :query)
        ORDER BY rank DESC
        LIMIT :n_results
    """)

    with ENGINE.connect() as conn:
        rows = conn.execute(sql, {"query": query, "n_results": n_results}).fetchall()

    keys = ["paperId", "title", "abstract", "year", "venue", "citationCount", "url", "DOI", "rank"]
    return [dict(zip(keys, row)) for row in rows]
