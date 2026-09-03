import requests

import literature_ai.search_service.data_collect.collect_full_papers as collect_module
from literature_ai.search_service.data_collect.collect_full_papers import (
    process_papers_by_id,
    resolve_pdf_urls,
)
from literature_ai.search_service.processing.pdf_parsing import GrobidUnavailableError

_TEI_XML = """<?xml version="1.0"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
    <teiHeader>
        <fileDesc><titleStmt><title level="a" type="main">T</title></titleStmt></fileDesc>
        <encodingDesc><appInfo><application ident="GROBID" version="0.8.2"/></appInfo></encodingDesc>
    </teiHeader>
    <text><body>
        <div><head>Introduction</head><p>intro text</p></div>
        <div><head>Methodology</head><p>method text</p></div>
    </body></text>
</TEI>"""


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
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
    """Returns one queued row per successive .connect().execute().fetchone() call."""

    def __init__(self, rows):
        self._rows = list(rows)

    def connect(self):
        return _FakeConn(self._rows.pop(0))


class _FakeResponse:
    def __init__(self, content: bytes = b"%PDF-1.4 fake"):
        self.content = content

    def raise_for_status(self):
        pass


class _FakeModel:
    async def embed_text(self, text):
        return [0.1, 0.2]


def _capture_upserts(monkeypatch):
    calls = []
    monkeypatch.setattr(
        collect_module,
        "upsert_table",
        lambda records, table_path, **kwargs: calls.append((table_path, records)),
    )
    return calls


def test_resolve_pdf_urls_lists_url_before_arxiv():
    assert resolve_pdf_urls({"url": "https://example.org/p.pdf", "ArXiV": "1234.5678"}) == [
        "https://example.org/p.pdf",
        "https://arxiv.org/pdf/1234.5678",
    ]


def test_resolve_pdf_urls_falls_back_to_arxiv_only():
    assert resolve_pdf_urls({"url": None, "ArXiV": "1706.03762"}) == [
        "https://arxiv.org/pdf/1706.03762"
    ]


def test_resolve_pdf_urls_returns_empty_when_neither_present():
    assert resolve_pdf_urls({"url": None, "ArXiV": None}) == []


def test_process_papers_by_id_success_persists_fulltext_and_chunk_offsets(monkeypatch):
    monkeypatch.setattr(
        collect_module,
        "ENGINE",
        _FakeEngine(
            [
                None,  # no cached row in raw.paper_fulltext
                ("https://example.org/p.pdf", None),  # raw_paper_searches candidate row
                None,  # not already chunked
            ]
        ),
    )
    monkeypatch.setattr(collect_module._pdf_session, "get", lambda *a, **k: _FakeResponse())
    monkeypatch.setattr(collect_module, "call_grobid_fulltext", lambda pdf_bytes: _TEI_XML)
    monkeypatch.setattr(collect_module, "get_embedding_model", lambda name: _FakeModel())
    calls = _capture_upserts(monkeypatch)

    metrics = process_papers_by_id(["p1"])

    assert metrics.total == 1
    assert metrics.inserted == 1
    assert metrics.errors == 0
    assert metrics.skipped == 0

    fulltext_calls = [c for c in calls if c[0] == collect_module.FULLTEXT_TABLE]
    chunk_calls = [c for c in calls if c[0] == collect_module.CHUNKS_TABLE]
    assert len(fulltext_calls) == 1
    assert fulltext_calls[0][1][0]["status"] == "success"
    full_text = fulltext_calls[0][1][0]["full_text"]

    assert len(chunk_calls) == 1
    chunk_records = chunk_calls[0][1]
    assert [r["section_header"] for r in chunk_records] == ["Introduction", "Methodology"]
    spans = [full_text[r["start_index"] : r["end_index"]] for r in chunk_records]
    assert spans == ["intro text", "method text"]
    assert [r["char_count"] for r in chunk_records] == [len(s) for s in spans]
    assert all(r["embedding"] == [0.1, 0.2] for r in chunk_records)


def test_process_papers_by_id_skips_already_cached_and_chunked(monkeypatch):
    cached_row = ("success", "full text", "<TEI/>")
    monkeypatch.setattr(
        collect_module,
        "ENGINE",
        _FakeEngine([cached_row, (1,)]),  # cached full text, already chunked
    )
    calls = _capture_upserts(monkeypatch)

    metrics = process_papers_by_id(["p1"])

    assert metrics.inserted == 1
    assert calls == []


def test_process_papers_by_id_unknown_paper_counts_as_error(monkeypatch):
    monkeypatch.setattr(collect_module, "ENGINE", _FakeEngine([None, None]))
    calls = _capture_upserts(monkeypatch)

    metrics = process_papers_by_id(["missing"])

    assert metrics.errors == 1
    assert metrics.inserted == 0
    assert calls == []


def test_process_papers_by_id_no_candidate_url_persists_no_pdf_available(monkeypatch):
    monkeypatch.setattr(
        collect_module,
        "ENGINE",
        _FakeEngine([None, (None, None)]),  # not cached, no url/ArXiV
    )
    calls = _capture_upserts(monkeypatch)

    metrics = process_papers_by_id(["p2"])

    assert metrics.skipped == 1
    assert metrics.errors == 0
    assert len(calls) == 1
    assert calls[0][1][0]["status"] == "no_pdf_available"


def test_process_papers_by_id_download_failure_persists_no_pdf_available(monkeypatch):
    monkeypatch.setattr(
        collect_module,
        "ENGINE",
        _FakeEngine([None, ("https://example.org/p.pdf", None)]),
    )

    def _raise(*a, **k):
        raise requests.exceptions.ConnectionError("boom")

    monkeypatch.setattr(collect_module._pdf_session, "get", _raise)
    calls = _capture_upserts(monkeypatch)

    metrics = process_papers_by_id(["p3"])

    assert metrics.skipped == 1
    assert calls[0][1][0]["status"] == "no_pdf_available"


def test_process_papers_by_id_grobid_failure_counts_as_error_and_does_not_persist(monkeypatch):
    monkeypatch.setattr(
        collect_module,
        "ENGINE",
        _FakeEngine([None, ("https://example.org/p.pdf", None)]),
    )
    monkeypatch.setattr(collect_module._pdf_session, "get", lambda *a, **k: _FakeResponse())

    def _raise(pdf_bytes):
        raise GrobidUnavailableError("grobid down")

    monkeypatch.setattr(collect_module, "call_grobid_fulltext", _raise)
    calls = _capture_upserts(monkeypatch)

    metrics = process_papers_by_id(["p4"])

    assert metrics.errors == 1
    assert calls == []


def test_process_papers_by_id_continues_after_one_id_errors(monkeypatch):
    monkeypatch.setattr(
        collect_module,
        "ENGINE",
        _FakeEngine(
            [
                None,  # p_bad: not cached
                None,  # p_bad: unknown paper
                ("success", "full text", "<TEI/>"),  # p_good: cached
                (1,),  # p_good: already chunked
            ]
        ),
    )
    calls = _capture_upserts(monkeypatch)

    metrics = process_papers_by_id(["p_bad", "p_good"])

    assert metrics.total == 2
    assert metrics.errors == 1
    assert metrics.inserted == 1
    assert calls == []
