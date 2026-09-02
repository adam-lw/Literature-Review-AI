from dataclasses import dataclass

from literature_ai.search_service.parsing.grobid_client import Section

DEFAULT_MAX_CHARS = 2000
# Trailing chunks below this fraction of max_chars get merged into their predecessor
# (within the same section) rather than left as a near-empty chunk on their own.
_MIN_CHARS_RATIO = 0.15


@dataclass
class Chunk:
    chunk_index: int
    section_index: int | None
    section_header: str | None
    text: str


def chunk_sections(sections: list[Section], max_chars: int = DEFAULT_MAX_CHARS) -> list[Chunk]:
    """Split a paper's sections into RAG-sized chunks.

    Chunks never cross a section boundary, so `section_header` stays unambiguous per
    chunk. Within a section, paragraphs are accumulated greedily up to `max_chars`; a
    paragraph is only split mid-paragraph if it alone exceeds `max_chars`.
    `chunk_index` is contiguous across the whole paper (not reset per section).
    """
    chunks: list[Chunk] = []
    for section in sections:
        for text in _chunk_paragraphs(section.paragraphs, max_chars):
            chunks.append(
                Chunk(
                    chunk_index=len(chunks),
                    section_index=section.index,
                    section_header=section.header,
                    text=text,
                )
            )
    return chunks


def _chunk_paragraphs(paragraphs: list[str], max_chars: int) -> list[str]:
    texts: list[str] = []
    # Parallel to `texts`: whether each entry came from paragraph accumulation (safe to
    # merge with a neighbor) rather than a hard split (must keep its strict max_chars
    # bound, since that bound is the whole point of hard-splitting an oversized
    # paragraph - merging it back in would silently defeat that guarantee).
    mergeable: list[bool] = []
    buffer: list[str] = []
    buffer_len = 0

    def flush() -> None:
        nonlocal buffer, buffer_len
        if buffer:
            texts.append("\n\n".join(buffer))
            mergeable.append(True)
            buffer = []
            buffer_len = 0

    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            flush()
            for part in _hard_split(paragraph, max_chars):
                texts.append(part)
                mergeable.append(False)
            continue

        added_len = len(paragraph) + (2 if buffer else 0)  # "\n\n" join cost
        if buffer and buffer_len + added_len > max_chars:
            flush()
            added_len = len(paragraph)

        buffer.append(paragraph)
        buffer_len += added_len

    flush()
    return _merge_small_trailing(
        texts, mergeable, min_chars=max_chars * _MIN_CHARS_RATIO, max_chars=max_chars
    )


def _hard_split(paragraph: str, max_chars: int) -> list[str]:
    """Fallback for a single paragraph longer than max_chars: split on whitespace
    boundaries near the limit rather than mid-word."""
    parts = []
    remaining = paragraph
    while len(remaining) > max_chars:
        split_at = remaining.rfind(" ", 0, max_chars)
        if split_at <= 0:
            split_at = max_chars
        parts.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    if remaining:
        parts.append(remaining)
    return parts


def _merge_small_trailing(
    texts: list[str], mergeable: list[bool], min_chars: float, max_chars: int
) -> list[str]:
    if len(texts) < 2 or not (mergeable[-1] and mergeable[-2]):
        return texts
    last = texts[-1]
    if len(last) < min_chars and len(texts[-2]) + 2 + len(last) <= max_chars * 1.15:
        return texts[:-2] + [texts[-2] + "\n\n" + last]
    return texts
