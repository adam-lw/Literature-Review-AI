from sqlalchemy import text

from literature_ai.db import ENGINE

RAW_PAPERS_TABLE = "raw.raw_paper_searches"
CHUNKS_TABLE = "processed.paper_chunks"


def get_paper_metadata(paper_id: str) -> dict | None:
    """Look up a paper's bibliographic metadata (title, abstract, venue, year, ...)
    from raw.raw_paper_searches. Returns None if paper_id isn't present.
    """
    with ENGINE.connect() as conn:
        row = conn.execute(
            text(f'SELECT * FROM {RAW_PAPERS_TABLE} WHERE "paperId" = :id'),
            {"id": paper_id},
        ).mappings().fetchone()
    return dict(row) if row is not None else None


def get_section_headers(paper_id: str) -> list[dict]:
    """List a paper's distinct section headers, in document order.

    Each entry is {"section_index": int, "section_header": str | None}, derived from
    processed.paper_chunks (populated by process_papers_by_id). Returns [] if the paper
    hasn't been chunked yet.
    """
    with ENGINE.connect() as conn:
        rows = conn.execute(
            text(
                f'SELECT DISTINCT "section_index", "section_header" FROM {CHUNKS_TABLE} '
                'WHERE "paperId" = :id ORDER BY "section_index"'
            ),
            {"id": paper_id},
        ).fetchall()
    return [{"section_index": row[0], "section_header": row[1]} for row in rows]
