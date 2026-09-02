from literature_ai.search_service.chunking.chunker import chunk_sections
from literature_ai.search_service.parsing.grobid_client import Section


def test_chunk_sections_accumulates_paragraphs_under_max_chars():
    sections = [Section(index=0, header="Introduction", paragraphs=["A" * 100, "B" * 100])]

    chunks = chunk_sections(sections, max_chars=500)

    assert len(chunks) == 1
    assert chunks[0].text == ("A" * 100) + "\n\n" + ("B" * 100)
    assert chunks[0].section_index == 0
    assert chunks[0].section_header == "Introduction"
    assert chunks[0].chunk_index == 0


def test_chunk_sections_splits_when_max_chars_exceeded():
    sections = [Section(index=0, header="Intro", paragraphs=["A" * 60, "B" * 60])]

    chunks = chunk_sections(sections, max_chars=100)

    assert len(chunks) == 2
    assert chunks[0].text == "A" * 60
    assert chunks[1].text == "B" * 60
    assert [c.chunk_index for c in chunks] == [0, 1]


def test_chunk_sections_never_splits_a_paragraph_that_fits():
    paragraph = "word " * 50  # well under max_chars
    sections = [Section(index=0, header=None, paragraphs=[paragraph])]

    chunks = chunk_sections(sections, max_chars=1000)

    assert len(chunks) == 1
    assert chunks[0].text == paragraph


def test_chunk_sections_hard_splits_an_oversized_single_paragraph():
    paragraph = " ".join(["word"] * 200)  # ~1000 chars, exceeds max_chars
    sections = [Section(index=0, header="Body", paragraphs=[paragraph])]

    chunks = chunk_sections(sections, max_chars=100)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.text) <= 100
        assert chunk.section_index == 0
        assert chunk.section_header == "Body"
    # No word content is lost across the hard split.
    assert " ".join(c.text for c in chunks).split() == paragraph.split()


def test_chunk_sections_merges_small_trailing_chunk_into_predecessor():
    # First paragraph fills most of the budget; second is tiny, forcing a small
    # trailing chunk that should be merged back into the first rather than left alone.
    sections = [Section(index=0, header="Intro", paragraphs=["A" * 95, "tiny"])]

    chunks = chunk_sections(sections, max_chars=100)

    assert len(chunks) == 1
    assert chunks[0].text == ("A" * 95) + "\n\ntiny"


def test_chunk_sections_does_not_cross_section_boundaries():
    sections = [
        Section(index=0, header="Introduction", paragraphs=["intro text"]),
        Section(index=1, header="Conclusion", paragraphs=["conclusion text"]),
    ]

    chunks = chunk_sections(sections, max_chars=1000)

    assert len(chunks) == 2
    assert chunks[0].section_header == "Introduction"
    assert chunks[1].section_header == "Conclusion"
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1


def test_chunk_sections_handles_empty_input():
    assert chunk_sections([], max_chars=500) == []


def test_chunk_sections_skips_section_with_no_paragraphs():
    sections = [Section(index=0, header="Empty Header", paragraphs=[])]

    assert chunk_sections(sections, max_chars=500) == []
