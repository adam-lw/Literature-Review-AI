import asyncio

import pytest

import literature_ai.search_service.search.chunk_search as chunk_search


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
    def __init__(self, rows_per_call):
        self._queue = list(rows_per_call)

    def connect(self):
        return _FakeConn(self._queue.pop(0))


class _FakeModel:
    async def embed_query(self, query):
        return [0.1, 0.2]


def test_rag_paper_chunks_async_queries_scoped_to_run_and_papers(monkeypatch):
    meta_row = [("fake_model", 2, "chunk")]
    search_rows = [("p1", 0, "Methodology", "method text", 0.05)]
    monkeypatch.setattr(chunk_search, "ENGINE", _FakeEngine([meta_row, search_rows]))
    monkeypatch.setattr(chunk_search, "get_embedding_model", lambda name: _FakeModel())

    results = asyncio.run(
        chunk_search.rag_paper_chunks_async(["p1"], "query", run_id=1, n_results=5)
    )

    assert results == [
        {
            "paperId": "p1",
            "chunk_index": 0,
            "section_header": "Methodology",
            "chunk_text": "method text",
            "distance": 0.05,
        }
    ]


def test_rag_paper_chunks_async_raises_for_unknown_run(monkeypatch):
    monkeypatch.setattr(chunk_search, "ENGINE", _FakeEngine([[]]))

    with pytest.raises(ValueError, match="No embedding run found"):
        asyncio.run(chunk_search.rag_paper_chunks_async(["p1"], "query", run_id=99))


def test_rag_paper_chunks_async_rejects_abstract_target_run(monkeypatch):
    meta_row = [("fake_model", 2, "abstract")]
    monkeypatch.setattr(chunk_search, "ENGINE", _FakeEngine([meta_row]))

    with pytest.raises(ValueError, match="not a chunk-embedding run"):
        asyncio.run(chunk_search.rag_paper_chunks_async(["p1"], "query", run_id=1))


def test_rag_paper_chunks_orchestrates_generation_then_search(monkeypatch):
    monkeypatch.setattr(chunk_search, "generate_chunk_embeddings", lambda paper_ids, model: 5)

    async def _fake_search(paper_ids, query, run_id, n_results=5):
        return [{"paperId": "p1", "chunk_index": 0, "section_header": None,
                  "chunk_text": "t", "distance": 0.1}]

    monkeypatch.setattr(chunk_search, "rag_paper_chunks_async", _fake_search)

    result = chunk_search.rag_paper_chunks(["p1"], "query", "fake_model", n_results=3)

    assert result["run_id"] == 5
    assert result["results"][0]["paperId"] == "p1"
