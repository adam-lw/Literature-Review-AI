import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

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


@dataclass
class Section:
    """One TEI `<div>`'s header + paragraphs, in document order.

    `header` is exactly the free-text GROBID extracted from the paper's own PDF (e.g.
    "Method", "Our Approach", "3.2 Experimental Setup") - there is no controlled
    vocabulary and it is not known ahead of time. `header` is None for a div with
    paragraph content but no heading (e.g. leading, untitled prose).
    """

    index: int
    header: str | None
    paragraphs: list[str] = field(default_factory=list)


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


def _parse_root(tei_xml: str) -> ET.Element:
    try:
        return ET.fromstring(tei_xml)
    except ET.ParseError as exc:
        raise GrobidParseError(f"GROBID returned malformed XML: {exc}") from exc


def parse_tei_fulltext(tei_xml: str) -> dict:
    """Parse a GROBID TEI-XML response into title/abstract/body_text/grobid_version.

    body_text preserves section structure (headings + paragraph breaks) rather than
    flattening everything into one blob, so downstream consumers (including a future
    chunked-search stage) can split on real section/paragraph boundaries instead of
    re-parsing tei_xml or heuristically re-discovering structure in plain text.
    """
    root = _parse_root(tei_xml)

    title_el = root.find(
        ".//tei:teiHeader/tei:fileDesc/tei:titleStmt/tei:title", _TEI_NS
    )
    title = _text(title_el)

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

    body = root.find(".//tei:text/tei:body", _TEI_NS)
    body_text = _render_body(body) if body is not None else ""

    return {
        "title": title,
        "abstract": abstract,
        "body_text": body_text,
        "grobid_version": grobid_version,
    }


def extract_sections(tei_xml: str) -> list[Section]:
    """Parse TEI-XML into an ordered list of Section objects (header + paragraphs).

    Raises GrobidParseError on malformed XML, same as parse_tei_fulltext. Returns []
    if there is no <body> element. This is the structured counterpart to
    parse_tei_fulltext's flattened body_text - used by chunking and section lookup,
    which need real section boundaries rather than a "## Header" markdown blob.
    """
    root = _parse_root(tei_xml)
    body = root.find(".//tei:text/tei:body", _TEI_NS)
    return _sections_from_body(body) if body is not None else []


def _sections_from_body(body: ET.Element) -> list[Section]:
    sections: list[Section] = []
    for div in body.findall(".//tei:div", _TEI_NS):
        head = _text(div.find("tei:head", _TEI_NS))
        paragraphs = [p for p in (_text(p) for p in div.findall("tei:p", _TEI_NS)) if p]
        if not head and not paragraphs:
            continue
        sections.append(Section(index=len(sections), header=head, paragraphs=paragraphs))
    return sections


def _render_body(body: ET.Element) -> str:
    rendered = []
    for section in _sections_from_body(body):
        parts = [f"## {section.header}"] if section.header else []
        parts.extend(section.paragraphs)
        rendered.append("\n\n".join(parts))
    return "\n\n".join(rendered)


def _text(el: ET.Element | None) -> str | None:
    if el is None:
        return None
    text = "".join(el.itertext()).strip()
    return text or None
