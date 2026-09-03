from pathlib import Path

import pytest

from literature_ai.search_service.processing.pdf_parsing import (
    GrobidParseError,
    extract_chunks,
    parse_tei_fulltext,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "sample_tei.xml"

_NO_BODY_TEI = """<?xml version="1.0"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
    <teiHeader>
        <fileDesc><titleStmt><title level="a" type="main">No Body</title></titleStmt></fileDesc>
    </teiHeader>
    <text><body></body></text>
</TEI>"""


def test_parse_tei_fulltext_extracts_title_abstract_and_version():
    parsed = parse_tei_fulltext(_FIXTURE.read_text())

    assert parsed["title"] == "Attention Is All You Need"
    assert "sequence transduction models" in parsed["abstract"]
    assert parsed["grobid_version"] == "0.8.2"


def test_parse_tei_fulltext_raises_on_malformed_xml():
    with pytest.raises(GrobidParseError):
        parse_tei_fulltext("<TEI><unclosed>")


def test_parse_tei_fulltext_handles_missing_body():
    parsed = parse_tei_fulltext(_NO_BODY_TEI)
    assert parsed["title"] == "No Body"


def test_extract_chunks_full_text_renders_headers_and_paragraphs_in_order():
    full_text, chunks = extract_chunks(_FIXTURE.read_text())

    assert "## Introduction" in full_text
    assert "## Background" in full_text
    assert "Recurrent neural networks" in full_text
    assert "reducing sequential computation" in full_text
    # A div with no heading still contributes its paragraph text.
    assert "A paragraph with no section heading." in full_text
    assert full_text.index("## Introduction") < full_text.index("## Background")
    assert len(chunks) > 0


def test_extract_chunks_offsets_substring_back_to_original_paragraphs():
    full_text, chunks = extract_chunks(_FIXTURE.read_text())

    assert [c["section_header"] for c in chunks] == ["Introduction", "Background", None]
    assert [c["index"] for c in chunks] == [0, 1, 2]
    assert [c["section_index"] for c in chunks] == [0, 1, 2]

    spans = [full_text[c["start_index"] : c["end_index"]] for c in chunks]
    assert "Recurrent neural networks" in spans[0]
    assert "Numerous efforts" in spans[0]
    assert "reducing sequential computation" in spans[1]
    assert spans[2] == "A paragraph with no section heading."
    for chunk, span in zip(chunks, spans):
        assert chunk["char_count"] == len(span)


def test_extract_chunks_raises_on_malformed_xml():
    with pytest.raises(GrobidParseError):
        extract_chunks("<TEI><unclosed>")


def test_extract_chunks_handles_missing_body():
    assert extract_chunks(_NO_BODY_TEI) == ("", [])


def test_extract_chunks_hard_splits_an_oversized_paragraph():
    paragraph = " ".join(["word"] * 200)  # ~1000 chars, exceeds max_chars
    tei_xml = f"""<?xml version="1.0"?>
    <TEI xmlns="http://www.tei-c.org/ns/1.0">
        <teiHeader><fileDesc><titleStmt><title level="a" type="main">T</title></titleStmt></fileDesc></teiHeader>
        <text><body><div><head>Body</head><p>{paragraph}</p></div></body></text>
    </TEI>"""

    full_text, chunks = extract_chunks(tei_xml, max_chars=100)

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk["char_count"] <= 100
        assert chunk["section_header"] == "Body"
    # No word content is lost across the hard split.
    spans = [full_text[c["start_index"] : c["end_index"]] for c in chunks]
    assert " ".join(spans).split() == paragraph.split()


def test_extract_chunks_never_splits_a_paragraph_that_fits():
    paragraph = "word " * 50  # well under max_chars
    tei_xml = f"""<?xml version="1.0"?>
    <TEI xmlns="http://www.tei-c.org/ns/1.0">
        <teiHeader><fileDesc><titleStmt><title level="a" type="main">T</title></titleStmt></fileDesc></teiHeader>
        <text><body><div><p>{paragraph}</p></div></body></text>
    </TEI>"""

    full_text, chunks = extract_chunks(tei_xml, max_chars=1000)

    assert len(chunks) == 1
    assert full_text[chunks[0]["start_index"] : chunks[0]["end_index"]] == paragraph.strip()
