import literature_ai.search_service.retrieval.text as text_module
from literature_ai.search_service.retrieval.text import get_section_content


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row

    def scalar(self):
        return self._row


class _FakeConn:
    def __init__(self, row):
        self._row = row

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, *args, **kwargs):
        return _FakeResult(self._row)


class _FakeEngine:
    """Returns one queued row per successive .connect().execute() call."""

    def __init__(self, rows):
        self._rows = list(rows)

    def connect(self):
        return _FakeConn(self._rows.pop(0))


def test_get_section_content_substrings_full_text_once_across_matching_chunks(monkeypatch):
    full_text = "## Methodology\n\nfirst part\n\nsecond part\n\n## Results\n\nresults text"
    start = full_text.index("first part")
    end = full_text.index("second part") + len("second part")
    monkeypatch.setattr(text_module, "ENGINE", _FakeEngine([(start, end), full_text]))

    result = get_section_content("p1", "Methodology")

    assert result == full_text[start:end]
    assert result == "first part\n\nsecond part"


def test_get_section_content_returns_none_when_no_matching_chunks(monkeypatch):
    monkeypatch.setattr(text_module, "ENGINE", _FakeEngine([(None, None)]))

    assert get_section_content("p1", "Nonexistent") is None


def test_get_section_content_returns_none_when_full_text_missing(monkeypatch):
    monkeypatch.setattr(text_module, "ENGINE", _FakeEngine([(0, 10), None]))

    assert get_section_content("p1", "Methodology") is None
