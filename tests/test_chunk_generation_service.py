from datetime import datetime, timezone

import literature_ai.search_service.chunking.service as service
from literature_ai.search_service.full_paper.service import FullPaperContent

_FULL_PAPER_TEI = """<?xml version="1.0"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
    <teiHeader>
        <fileDesc><titleStmt><title level="a" type="main">T</title></titleStmt></fileDesc>
    </teiHeader>
    <text><body>
        <div><head>Introduction</head><p>Some intro text here.</p></div>
        <div><head>Methodology</head><p>Some method text here.</p></div>
    </body></text>
</TEI>"""


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, *args, **kwargs):
        return _FakeResult(self._rows)


class _FakeEngine:
    """Returns one queued rows-list per successive .connect().execute() call."""

    def __init__(self, rows_per_call):
        self._queue = list(rows_per_call)

    def connect(self):
        return _FakeConn(self._queue.pop(0))


class _FakeModel:
    n_dim = 4
    version = "v1"

    async def embed_text(self, text):
        return [0.1, 0.2, 0.3, 0.4]


def _full_paper_content(**overrides) -> FullPaperContent:
    base = dict(
        paperId="p1", status="success", pdf_url="https://example.org/p.pdf",
        full_text="body", tei_xml=_FULL_PAPER_TEI, grobid_version="0.8.2",
        parsed_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return FullPaperContent(**base)


# --- ensure_paper_chunks -----------------------------------------------------------


def test_ensure_paper_chunks_cache_hit_returns_existing_rows(monkeypatch):
    now = datetime.now(timezone.utc)
    cached_rows = [("p1", 0, 0, "Introduction", "chunk text", 10, "hash1", now)]
    monkeypatch.setattr(service, "ENGINE", _FakeEngine([cached_rows]))
    upsert_called = {"called": False}
    monkeypatch.setattr(
        service, "upsert_table", lambda *a, **k: upsert_called.__setitem__("called", True)
    )

    result = service.ensure_paper_chunks("p1")

    assert len(result) == 1
    assert result[0]["chunk_text"] == "chunk text"
    assert upsert_called["called"] is False


def test_ensure_paper_chunks_no_pdf_returns_empty_without_persisting(monkeypatch):
    monkeypatch.setattr(service, "ENGINE", _FakeEngine([[]]))
    monkeypatch.setattr(
        service,
        "get_or_create_full_paper",
        lambda paper_id: _full_paper_content(status="no_pdf_available", tei_xml=None, full_text=None),
    )
    upsert_called = {"called": False}
    monkeypatch.setattr(
        service, "upsert_table", lambda *a, **k: upsert_called.__setitem__("called", True)
    )

    result = service.ensure_paper_chunks("p2")

    assert result == []
    assert upsert_called["called"] is False


def test_ensure_paper_chunks_computes_and_persists_on_cache_miss(monkeypatch):
    monkeypatch.setattr(service, "ENGINE", _FakeEngine([[]]))
    monkeypatch.setattr(service, "get_or_create_full_paper", lambda paper_id: _full_paper_content())
    captured = {}
    monkeypatch.setattr(
        service,
        "upsert_table",
        lambda records, *a, **k: captured.update({"records": records}),
    )

    result = service.ensure_paper_chunks("p3")

    assert len(result) == 2
    assert result[0]["section_header"] == "Introduction"
    assert result[1]["section_header"] == "Methodology"
    assert [c["chunk_index"] for c in result] == [0, 1]
    assert captured["records"] == result


# --- generate_chunk_embeddings ------------------------------------------------------


def test_generate_chunk_embeddings_resolves_existing_run_and_skips_embedded_chunks(monkeypatch):
    monkeypatch.setattr(service, "get_embedding_model", lambda name: _FakeModel())
    monkeypatch.setattr(service, "resolve_embedding_run", lambda *a, **k: (42, 4))
    create_called = {"called": False}
    monkeypatch.setattr(
        service, "create_embedding_run", lambda **k: create_called.__setitem__("called", True)
    )

    class _Inspector:
        def get_columns(self, table, schema):
            return [{"name": "embedding_4"}]

    monkeypatch.setattr(service, "get_inspector", lambda: _Inspector())
    alter_called = {"called": False}
    monkeypatch.setattr(
        service, "execute_query", lambda *a, **k: alter_called.__setitem__("called", True)
    )
    monkeypatch.setattr(
        service,
        "ensure_paper_chunks",
        lambda paper_id, max_chars=None: [
            {"paperId": "p1", "chunk_index": 0, "chunk_text": "a", "content_hash": "h0"},
        ],
    )
    # Already embedded for this run -> to_embed ends up empty.
    monkeypatch.setattr(service, "ENGINE", _FakeEngine([[("p1", 0)]]))
    upsert_called = {"called": False}
    monkeypatch.setattr(
        service, "upsert_table", lambda *a, **k: upsert_called.__setitem__("called", True)
    )

    run_id = service.generate_chunk_embeddings(["p1"], "fake_model")

    assert run_id == 42
    assert create_called["called"] is False
    assert alter_called["called"] is False
    assert upsert_called["called"] is False


def test_generate_chunk_embeddings_creates_run_when_none_exists(monkeypatch):
    monkeypatch.setattr(service, "get_embedding_model", lambda name: _FakeModel())

    def _raise(*a, **k):
        raise ValueError("no run found")

    monkeypatch.setattr(service, "resolve_embedding_run", _raise)
    monkeypatch.setattr(service, "create_embedding_run", lambda **k: 7)

    class _Inspector:
        def get_columns(self, table, schema):
            return []  # embedding_4 column missing

    monkeypatch.setattr(service, "get_inspector", lambda: _Inspector())
    alter_calls = []
    monkeypatch.setattr(service, "execute_query", lambda sql: alter_calls.append(sql))
    monkeypatch.setattr(
        service,
        "ensure_paper_chunks",
        lambda paper_id, max_chars=None: [
            {"paperId": "p1", "chunk_index": 0, "chunk_text": "a", "content_hash": "h0"},
        ],
    )
    monkeypatch.setattr(service, "ENGINE", _FakeEngine([[]]))  # nothing embedded yet
    upserted = {}
    monkeypatch.setattr(
        service, "upsert_table", lambda records, *a, **k: upserted.update({"records": records})
    )

    run_id = service.generate_chunk_embeddings(["p1"], "fake_model")

    assert run_id == 7
    assert any("embedding_4" in sql for sql in alter_calls)
    assert upserted["records"][0]["paperId"] == "p1"
    assert upserted["records"][0]["embedding_4"] == [0.1, 0.2, 0.3, 0.4]


def test_generate_chunk_embeddings_skips_papers_with_no_chunks(monkeypatch):
    monkeypatch.setattr(service, "get_embedding_model", lambda name: _FakeModel())
    monkeypatch.setattr(service, "resolve_embedding_run", lambda *a, **k: (42, 4))

    class _Inspector:
        def get_columns(self, table, schema):
            return [{"name": "embedding_4"}]

    monkeypatch.setattr(service, "get_inspector", lambda: _Inspector())
    monkeypatch.setattr(service, "ensure_paper_chunks", lambda paper_id, max_chars=None: [])
    upsert_called = {"called": False}
    monkeypatch.setattr(
        service, "upsert_table", lambda *a, **k: upsert_called.__setitem__("called", True)
    )

    run_id = service.generate_chunk_embeddings(["no_pdf_paper"], "fake_model")

    assert run_id == 42
    assert upsert_called["called"] is False
