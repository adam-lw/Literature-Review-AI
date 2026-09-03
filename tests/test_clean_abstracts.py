from datetime import datetime, timezone

import pandas as pd

import literature_ai.search_service.processing.clean_abstracts as module


class _FakeResult:
    def __init__(self, rows=None, scalar=None):
        self._rows = rows or []
        self._scalar = scalar

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return (self._scalar,)


def test_clean_abstracts_populates_title_and_abstract_columns(monkeypatch):
    df = pd.DataFrame(
        [{"paperId": "p1", "title": "My Title", "abstract": "<p>Some abstract.</p>"}]
    )
    monkeypatch.setattr(module, "_load_candidates", lambda max_processed_at: df)

    call_queue = [
        _FakeResult(scalar=None),  # MAX(processed_at)
        _FakeResult(rows=[]),  # existing hashes, empty -> insert path
    ]
    monkeypatch.setattr(module, "execute_query", lambda sql: call_queue.pop(0))

    captured = {}
    monkeypatch.setattr(
        module, "upsert_table", lambda records, *a, **k: captured.update({"records": records})
    )

    metrics = module.clean_abstracts()

    assert metrics.inserted == 1
    record = captured["records"][0]
    assert record["title"] == "My Title"
    assert record["abstract"] == "Some abstract."
    assert "abstract_clean" not in record


def test_clean_abstracts_skips_rows_with_unchanged_content_hash(monkeypatch):
    df = pd.DataFrame([{"paperId": "p1", "title": "T", "abstract": "same abstract"}])
    monkeypatch.setattr(module, "_load_candidates", lambda max_processed_at: df)

    existing_hash = module._hash("same abstract")
    call_queue = [
        _FakeResult(scalar=datetime.now(timezone.utc)),
        _FakeResult(rows=[("p1", existing_hash)]),
    ]
    monkeypatch.setattr(module, "execute_query", lambda sql: call_queue.pop(0))

    upsert_called = {"called": False}
    monkeypatch.setattr(
        module, "upsert_table", lambda *a, **k: upsert_called.__setitem__("called", True)
    )

    metrics = module.clean_abstracts()

    assert metrics.skipped == 1
    assert upsert_called["called"] is False
