import literature_ai.search_service.search.keyword_search as module


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, rows, captured):
        self._rows = rows
        self._captured = captured

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, stmt, params=None):
        self._captured["params"] = params
        return _FakeResult(self._rows)


class _FakeEngine:
    def __init__(self, rows, captured):
        self._rows = rows
        self._captured = captured

    def connect(self):
        return _FakeConn(self._rows, self._captured)


def test_keyword_search_returns_correct_shape_and_binds_params(monkeypatch):
    rows = [("p1", "Title", "Abstract", 2020, "Venue", 5, "http://x", "10.1/doi", 0.42)]
    captured = {}
    monkeypatch.setattr(module, "ENGINE", _FakeEngine(rows, captured))

    results = module.keyword_search("query text", n_results=7)

    assert results == [
        {
            "paperId": "p1",
            "title": "Title",
            "abstract": "Abstract",
            "year": 2020,
            "venue": "Venue",
            "citationCount": 5,
            "url": "http://x",
            "DOI": "10.1/doi",
            "rank": 0.42,
        }
    ]
    assert captured["params"] == {"query": "query text", "n_results": 7}


def test_keyword_search_returns_empty_list_for_no_matches(monkeypatch):
    captured = {}
    monkeypatch.setattr(module, "ENGINE", _FakeEngine([], captured))

    assert module.keyword_search("nomatch") == []


def test_keyword_search_defaults_n_results_to_ten(monkeypatch):
    captured = {}
    monkeypatch.setattr(module, "ENGINE", _FakeEngine([], captured))

    module.keyword_search("query")

    assert captured["params"]["n_results"] == 10
