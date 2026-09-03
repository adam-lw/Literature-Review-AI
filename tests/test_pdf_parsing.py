from pathlib import Path

import pytest

from literature_ai.search_service.parsing.grobid_client import (
    GrobidParseError,
    extract_sections,
    parse_tei_fulltext,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "sample_tei.xml"


def test_parse_tei_fulltext_extracts_title_abstract_and_sections():
    tei_xml = _FIXTURE.read_text()
    parsed = parse_tei_fulltext(tei_xml)

    assert parsed["title"] == "Attention Is All You Need"
    assert "sequence transduction models" in parsed["abstract"]
    assert parsed["grobid_version"] == "0.8.2"

    body = parsed["body_text"]
    assert "## Introduction" in body
    assert "## Background" in body
    assert "Recurrent neural networks" in body
    assert "reducing sequential computation" in body
    # A div with no heading still contributes its paragraph text.
    assert "A paragraph with no section heading." in body
    # Sections appear in document order.
    assert body.index("## Introduction") < body.index("## Background")


def test_parse_tei_fulltext_raises_on_malformed_xml():
    with pytest.raises(GrobidParseError):
        parse_tei_fulltext("<TEI><unclosed>")


def test_parse_tei_fulltext_handles_missing_body():
    tei_xml = """<?xml version="1.0"?>
    <TEI xmlns="http://www.tei-c.org/ns/1.0">
        <teiHeader>
            <fileDesc><titleStmt><title level="a" type="main">No Body</title></titleStmt></fileDesc>
        </teiHeader>
        <text><body></body></text>
    </TEI>"""
    parsed = parse_tei_fulltext(tei_xml)
    assert parsed["title"] == "No Body"
    assert parsed["body_text"] == ""


def test_extract_sections_returns_structured_sections_in_order():
    tei_xml = _FIXTURE.read_text()
    sections = extract_sections(tei_xml)

    assert [s.header for s in sections] == ["Introduction", "Background", None]
    assert [s.index for s in sections] == [0, 1, 2]

    intro = sections[0]
    assert "Recurrent neural networks" in intro.paragraphs[0]
    assert "Numerous efforts" in intro.paragraphs[1]

    background = sections[1]
    assert "reducing sequential computation" in background.paragraphs[0]

    # A div with no heading still contributes its paragraph text.
    untitled = sections[2]
    assert untitled.paragraphs == ["A paragraph with no section heading."]


def test_extract_sections_raises_on_malformed_xml():
    with pytest.raises(GrobidParseError):
        extract_sections("<TEI><unclosed>")


def test_extract_sections_handles_missing_body():
    tei_xml = """<?xml version="1.0"?>
    <TEI xmlns="http://www.tei-c.org/ns/1.0">
        <teiHeader>
            <fileDesc><titleStmt><title level="a" type="main">No Body</title></titleStmt></fileDesc>
        </teiHeader>
        <text><body></body></text>
    </TEI>"""
    assert extract_sections(tei_xml) == []
