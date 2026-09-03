import os
import xml.etree.ElementTree as ET

import requests

from literature_ai.search_service.session import make_session

GROBID_URL = os.getenv("GROBID_URL", "http://localhost:8070")

_TEI_NS = {"tei": "http://www.tei-c.org/ns/1.0"}

_session = make_session(
    "grobid_client", max_retries=3, backoff_factor=5.0, cache_enabled=False
)


class GrobidError(Exception):
    """Base class for GROBID client errors."""


class GrobidUnavailableError(GrobidError):
    """GROBID could not be reached (connection error, timeout, or exhausted retries on 503)."""


class GrobidParseError(GrobidError):
    """GROBID rejected the document or returned malformed/empty TEI."""


def call_grobid_fulltext(pdf_bytes: bytes, *, timeout: float = 180.0) -> str:
    """Send a PDF to GROBID's full-text endpoint and return the raw TEI-XML response.

    consolidateHeader/consolidateCitations are left off (0): they enrich reference
    metadata via an external lookup service, which only slows this down without
    affecting the body-text structure this client extracts.
    """
    try:
        response = _session.post(
            f"{GROBID_URL}/api/processFulltextDocument",
            files={"input": ("paper.pdf", pdf_bytes, "application/pdf")},
            data={"consolidateHeader": "0", "consolidateCitations": "0"},
            timeout=timeout,
        )
    except requests.exceptions.RequestException as exc:
        raise GrobidUnavailableError(f"Failed to reach GROBID at {GROBID_URL}: {exc}") from exc

    if response.status_code != 200:
        raise GrobidParseError(
            f"GROBID returned {response.status_code} for processFulltextDocument: "
            f"{response.text[:500]}"
        )

    tei_xml = response.text
    if not tei_xml.strip():
        raise GrobidParseError("GROBID returned an empty response body")

    return tei_xml


def parse_tei_fulltext(tei_xml: str) -> dict:
    """Parse a GROBID TEI-XML response into title/abstract/grobid_version."""
    root = _parse_root(tei_xml)

    title = _text(root.find(".//tei:teiHeader/tei:fileDesc/tei:titleStmt/tei:title", _TEI_NS))

    abstract_paras = root.findall(
        ".//tei:teiHeader/tei:profileDesc/tei:abstract//tei:p", _TEI_NS
    )
    abstract = "\n\n".join(p for p in (_text(p) for p in abstract_paras) if p) or None

    version_el = root.find(
        ".//tei:teiHeader/tei:encodingDesc/tei:appInfo/"
        "tei:application[@ident='GROBID']",
        _TEI_NS,
    )
    grobid_version = version_el.get("version") if version_el is not None else None

    return {"title": title, "abstract": abstract, "grobid_version": grobid_version}


DEFAULT_MAX_CHARS = 2000
# Trailing chunks below this fraction of max_chars get merged into their predecessor
# (within the same section) rather than left as a near-empty chunk on their own.
_MIN_CHARS_RATIO = 0.15


def extract_chunks(tei_xml: str, max_chars: int = DEFAULT_MAX_CHARS) -> tuple[str, list[dict]]:
    """Parse TEI-XML into (full_text, chunks) in one pass.

    full_text is assembled from the same "## header" lines and paragraph text each
    chunk is built from, in document order, so every chunk's start_index/end_index
    (character offsets into the returned full_text) are known by construction as
    full_text is built - no separate step has to search for a chunk's text afterwards.

    Raises GrobidParseError on malformed XML. Returns ("", []) if there is no <body>
    element. Each chunk dict has "index" (contiguous across the whole paper),
    "section_index", "section_header" (the free-text heading exactly as GROBID
    extracted it, e.g. "Method", "3.2 Experimental Setup"; None for a div with
    paragraph content but no heading), "start_index", "end_index", and "char_count".
    Chunks never cross a section boundary. Within a section, paragraphs are
    accumulated greedily up to max_chars; a paragraph is only split mid-paragraph if it
    alone exceeds max_chars, at the last whitespace boundary before the limit.
    """
    root = _parse_root(tei_xml)
    body = root.find(".//tei:text/tei:body", _TEI_NS)

    parts: list[str] = []
    cursor = 0

    def append(piece: str) -> tuple[int, int]:
        nonlocal cursor
        if parts:
            parts.append("\n\n")
            cursor += 2
        start = cursor
        parts.append(piece)
        cursor += len(piece)
        return start, cursor

    chunks: list[dict] = []
    if body is None:
        return "", chunks

    section_index = 0
    for div in body.findall(".//tei:div", _TEI_NS):
        header = _text(div.find("tei:head", _TEI_NS))
        paragraphs = [p for p in (_text(p) for p in div.findall("tei:p", _TEI_NS)) if p]
        if not header and not paragraphs:
            continue

        if header:
            append(f"## {header}")

        spans: list[tuple[int, int]] = []
        mergeable: list[bool] = []
        buffer: list[str] = []
        buffer_len = 0

        def flush() -> None:
            nonlocal buffer, buffer_len
            if buffer:
                start, end = append("\n\n".join(buffer))
                spans.append((start, end))
                mergeable.append(True)
                buffer, buffer_len = [], 0

        for paragraph in paragraphs:
            if len(paragraph) > max_chars:
                flush()
                p_start, _ = append(paragraph)
                for local_start, local_end in _hard_split_spans(paragraph, max_chars):
                    spans.append((p_start + local_start, p_start + local_end))
                    mergeable.append(False)
                continue

            added_len = len(paragraph) + (2 if buffer else 0)
            if buffer and buffer_len + added_len > max_chars:
                flush()
                added_len = len(paragraph)

            buffer.append(paragraph)
            buffer_len += added_len

        flush()

        min_chars = max_chars * _MIN_CHARS_RATIO
        if len(spans) >= 2 and mergeable[-1] and mergeable[-2]:
            prev_len = spans[-2][1] - spans[-2][0]
            last_len = spans[-1][1] - spans[-1][0]
            if last_len < min_chars and prev_len + 2 + last_len <= max_chars * 1.15:
                spans = spans[:-2] + [(spans[-2][0], spans[-1][1])]

        for start, end in spans:
            chunks.append(
                {
                    "index": len(chunks),
                    "section_index": section_index,
                    "section_header": header,
                    "start_index": start,
                    "end_index": end,
                    "char_count": end - start,
                }
            )
        section_index += 1

    return "".join(parts), chunks


def _hard_split_spans(paragraph: str, max_chars: int) -> list[tuple[int, int]]:
    """Split a single oversized paragraph into (start, end) spans at whitespace
    boundaries near max_chars, rather than mid-word. Lossless: spans are contiguous
    and cover the whole paragraph (a split-point space stays attached to the fragment
    before it rather than being dropped).
    """
    spans = []
    pos, n = 0, len(paragraph)
    while n - pos > max_chars:
        split_at = paragraph.rfind(" ", pos, pos + max_chars)
        end = split_at + 1 if split_at > pos else pos + max_chars
        spans.append((pos, end))
        pos = end
    if pos < n:
        spans.append((pos, n))
    return spans


def _parse_root(tei_xml: str) -> ET.Element:
    try:
        return ET.fromstring(tei_xml)
    except ET.ParseError as exc:
        raise GrobidParseError(f"GROBID returned malformed XML: {exc}") from exc


def _text(el: ET.Element | None) -> str | None:
    if el is None:
        return None
    text = "".join(el.itertext()).strip()
    return text or None
