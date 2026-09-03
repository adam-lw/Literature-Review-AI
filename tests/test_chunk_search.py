import asyncio

import literature_ai.search_service.search.chunk_search as chunk_search


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


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
    def __init__(self, rows):
        self._rows = rows

    def connect(self):
        return _FakeConn(self._rows)


class _FakeModel:
    async def embed_query(self, query):
        return [0.1, 0.2]


def test_rag_paper_chunks_async_scopes_to_paper_ids_and_substrings_chunk_text(monkeypatch):
    full_text = "## Methodology\n\nmethod text"
    start, end = full_text.index("method text"), len(full_text)
    search_rows = [("p1", 0, "Methodology", start, end, full_text, 0.05)]
    monkeypatch.setattr(chunk_search, "ENGINE", _FakeEngine(search_rows))
    monkeypatch.setattr(chunk_search, "get_embedding_model", lambda name: _FakeModel())

    results = asyncio.run(chunk_search.rag_paper_chunks_async(["p1"], "query", n_results=5))

    assert results == [
        {
            "paperId": "p1",
            "chunk_index": 0,
            "section_header": "Methodology",
            "chunk_text": "method text",
            "distance": 0.05,
        }
    ]


def test_rag_paper_chunks_async_empty_when_no_matching_chunks(monkeypatch):
    monkeypatch.setattr(chunk_search, "ENGINE", _FakeEngine([]))
    monkeypatch.setattr(chunk_search, "get_embedding_model", lambda name: _FakeModel())

    results = asyncio.run(chunk_search.rag_paper_chunks_async(["missing"], "query"))

    assert results == []


def test_rag_paper_chunks_wraps_async_search(monkeypatch):
    async def _fake_search(paper_ids, query, n_results=5):
        assert paper_ids == ["p1"]
        assert n_results == 3
        return [{"paperId": "p1", "chunk_index": 0, "section_header": None,
                  "chunk_text": "t", "distance": 0.1}]

    monkeypatch.setattr(chunk_search, "rag_paper_chunks_async", _fake_search)

    result = chunk_search.rag_paper_chunks(["p1"], "query", n_results=3)

    assert result == {
        "results": [
            {"paperId": "p1", "chunk_index": 0, "section_header": None,
             "chunk_text": "t", "distance": 0.1}
        ]
    }
