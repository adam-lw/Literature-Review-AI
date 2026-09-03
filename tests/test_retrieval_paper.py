import literature_ai.search_service.retrieval.paper as paper_module
from literature_ai.search_service.retrieval.paper import get_paper_metadata, get_section_headers


class _FakeMappingResult:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return _FakeMappingResult(self._rows)

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, *args, **kwargs):
        return _FakeResult(self._payload)


class _FakeEngine:
    def __init__(self, payload):
        self._payload = payload

    def connect(self):
        return _FakeConn(self._payload)


def test_get_paper_metadata_returns_row_as_dict(monkeypatch):
    row = {"paperId": "p1", "title": "T", "abstract": "A", "year": 2020}
    monkeypatch.setattr(paper_module, "ENGINE", _FakeEngine(row))

    result = get_paper_metadata("p1")

    assert result == row


def test_get_paper_metadata_returns_none_when_missing(monkeypatch):
    monkeypatch.setattr(paper_module, "ENGINE", _FakeEngine(None))

    assert get_paper_metadata("missing") is None


def test_get_section_headers_returns_distinct_headers_in_order(monkeypatch):
    rows = [(0, "Introduction"), (1, "Methodology"), (2, None)]
    monkeypatch.setattr(paper_module, "ENGINE", _FakeEngine(rows))

    result = get_section_headers("p1")

    assert result == [
        {"section_index": 0, "section_header": "Introduction"},
        {"section_index": 1, "section_header": "Methodology"},
        {"section_index": 2, "section_header": None},
    ]


def test_get_section_headers_returns_empty_when_not_chunked(monkeypatch):
    monkeypatch.setattr(paper_module, "ENGINE", _FakeEngine([]))

    assert get_section_headers("p1") == []
