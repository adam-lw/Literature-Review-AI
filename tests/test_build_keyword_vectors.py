import literature_ai.search_service.processing.build_keyword_vectors as module


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeBeginConn:
    def __init__(self, captured):
        self._captured = captured

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, stmt, params=None):
        self._captured["stmt"] = stmt
        self._captured["params"] = params


class _FakeEngine:
    def __init__(self, captured):
        self._captured = captured

    def begin(self):
        return _FakeBeginConn(self._captured)


def test_build_keyword_vectors_no_rows_is_noop(monkeypatch):
    monkeypatch.setattr(module, "execute_query", lambda sql: _FakeResult([]))
    captured = {}
    monkeypatch.setattr(module, "ENGINE", _FakeEngine(captured))

    n = module.build_keyword_vectors()

    assert n == 0
    assert captured == {}


def test_build_keyword_vectors_skips_unchanged_rows(monkeypatch):
    title, abstract = "T", "A"
    unchanged_hash = module._hash_content(title, abstract)

    call_queue = [
        _FakeResult([("p1", title, abstract)]),
        _FakeResult([("p1", unchanged_hash)]),
    ]
    monkeypatch.setattr(module, "execute_query", lambda sql: call_queue.pop(0))
    captured = {}
    monkeypatch.setattr(module, "ENGINE", _FakeEngine(captured))

    n = module.build_keyword_vectors()

    assert n == 0
    assert captured == {}


def test_build_keyword_vectors_upserts_new_and_changed_rows(monkeypatch):
    call_queue = [
        _FakeResult([("p1", "T1", "A1"), ("p2", "T2", "A2")]),
        _FakeResult([("p1", "stale-hash")]),  # p1 changed, p2 is entirely new
    ]
    monkeypatch.setattr(module, "execute_query", lambda sql: call_queue.pop(0))
    captured = {}
    monkeypatch.setattr(module, "ENGINE", _FakeEngine(captured))

    n = module.build_keyword_vectors()

    assert n == 2
    params = captured["params"]
    assert {p["paper_id"] for p in params} == {"p1", "p2"}
    p1_params = next(p for p in params if p["paper_id"] == "p1")
    assert p1_params["title"] == "T1"
    assert p1_params["abstract"] == "A1"
    assert p1_params["content_hash"] == module._hash_content("T1", "A1")
