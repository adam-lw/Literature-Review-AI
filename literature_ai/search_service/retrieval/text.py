from sqlalchemy import text as sql_text

from literature_ai.db import ENGINE

CHUNKS_TABLE = "processed.paper_chunks"
FULLTEXT_TABLE = "raw.paper_fulltext"


def get_section_content(paper_id: str, section: str) -> str | None:
    """Return one section's full text, by paperId + exact section_header match.

    A section's chunks are contiguous within raw.paper_fulltext.full_text (chunks never
    cross a section boundary, and are appended in document order as full_text is
    built), so this takes the min(start_index)/max(end_index) span across all chunks
    matching `section` and substrings full_text once, rather than joining separate
    chunk texts back together.

    Returns None if the paper has no full text yet, or no chunk's section_header
    matches `section` exactly.
    """
    with ENGINE.connect() as conn:
        span = conn.execute(
            sql_text(
                f'SELECT MIN("start_index"), MAX("end_index") FROM {CHUNKS_TABLE} '
                'WHERE "paperId" = :id AND "section_header" = :section'
            ),
            {"id": paper_id, "section": section},
        ).fetchone()

    if span is None or span[0] is None:
        return None
    start_index, end_index = span

    with ENGINE.connect() as conn:
        full_text = conn.execute(
            sql_text(f'SELECT "full_text" FROM {FULLTEXT_TABLE} WHERE "paperId" = :id'),
            {"id": paper_id},
        ).scalar()

    return full_text[start_index:end_index] if full_text is not None else None
