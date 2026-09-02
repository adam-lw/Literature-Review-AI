from datetime import datetime, timezone

import pytest
import requests

import literature_ai.search_service.full_paper.service as service
from literature_ai.search_service.full_paper.service import (
    PaperNotFoundError,
    PdfDownloadError,
    get_or_create_full_paper,
    resolve_pdf_urls,
)
from literature_ai.search_service.parsing.grobid_client import GrobidUnavailableError


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeConn:
    def __init__(self, rows):
        self._rows = list(rows)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, *args, **kwargs):
        return _FakeResult(self._rows.pop(0))


class _FakeEngine:
    """Returns one queued row per successive .connect().execute().fetchone() call."""

    def __init__(self, rows):
        self._rows = list(rows)

    def connect(self):
        row = self._rows.pop(0)
        return _FakeConn([row])


class _FakeResponse:
    def __init__(self, content: bytes = b"%PDF-1.4 fake"):
        self.content = content

    def raise_for_status(self):
        pass


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


def test_download_first_available_falls_through_to_second_candidate():
    calls = []

    def _get(url, timeout=30):
        calls.append(url)
        if url == "bad":
            raise requests.exceptions.ConnectionError("boom")
        return _FakeResponse(content=b"good pdf bytes")

    class _Session:
        get = staticmethod(_get)

    original_session = service._pdf_session
    service._pdf_session = _Session()
    try:
        pdf_url, pdf_bytes = service._download_first_available(["bad", "good"])
    finally:
        service._pdf_session = original_session

    assert calls == ["bad", "good"]
    assert pdf_url == "good"
    assert pdf_bytes == b"good pdf bytes"


def test_download_first_available_raises_with_all_failures_when_every_candidate_fails():
    def _raise(url, timeout=30):
        raise requests.exceptions.ConnectionError(f"boom for {url}")

    class _Session:
        get = staticmethod(_raise)

    original_session = service._pdf_session
    service._pdf_session = _Session()
    try:
        with pytest.raises(PdfDownloadError) as exc_info:
            service._download_first_available(["one", "two"])
    finally:
        service._pdf_session = original_session

    assert "one" in str(exc_info.value)
    assert "two" in str(exc_info.value)


def test_get_or_create_full_paper_cache_hit(monkeypatch):
    cached_row = (
        "p1",
        "success",
        "https://example.org/p.pdf",
        "full text",
        "<TEI/>",
        "0.8.2",
        datetime.now(timezone.utc),
    )
    monkeypatch.setattr(service, "ENGINE", _FakeEngine([cached_row]))
    called = {"upsert": False}
    monkeypatch.setattr(
        service, "upsert_table", lambda *a, **k: called.__setitem__("upsert", True)
    )

    result = get_or_create_full_paper("p1")

    assert result.paperId == "p1"
    assert result.status == "success"
    assert result.full_text == "full text"
    assert called["upsert"] is False


def test_get_or_create_full_paper_unknown_paper(monkeypatch):
    monkeypatch.setattr(service, "ENGINE", _FakeEngine([None, None]))

    with pytest.raises(PaperNotFoundError):
        get_or_create_full_paper("missing")


def test_get_or_create_full_paper_no_pdf_available(monkeypatch):
    monkeypatch.setattr(service, "ENGINE", _FakeEngine([None, (None, None)]))
    captured = {}
    monkeypatch.setattr(
        service,
        "upsert_table",
        lambda records, *a, **k: captured.update(records[0]),
    )

    result = get_or_create_full_paper("p2")

    assert result.status == "no_pdf_available"
    assert result.full_text is None
    assert captured["status"] == "no_pdf_available"


def test_get_or_create_full_paper_download_failure_not_persisted(monkeypatch):
    monkeypatch.setattr(
        service, "ENGINE", _FakeEngine([None, ("https://example.org/p.pdf", None)])
    )

    def _raise(*a, **k):
        raise requests.exceptions.ConnectionError("boom")

    monkeypatch.setattr(service._pdf_session, "get", _raise)
    upsert_called = {"called": False}
    monkeypatch.setattr(
        service, "upsert_table", lambda *a, **k: upsert_called.__setitem__("called", True)
    )

    with pytest.raises(PdfDownloadError):
        get_or_create_full_paper("p3")

    assert upsert_called["called"] is False


def test_get_or_create_full_paper_falls_back_to_arxiv_when_url_download_fails(monkeypatch):
    monkeypatch.setattr(
        service, "ENGINE", _FakeEngine([None, ("https://example.org/p.pdf", "1706.03762")])
    )

    calls = []

    def _get(url, timeout=30):
        calls.append(url)
        if url == "https://example.org/p.pdf":
            raise requests.exceptions.ConnectionError("boom")
        return _FakeResponse()

    monkeypatch.setattr(service._pdf_session, "get", _get)
    monkeypatch.setattr(service, "call_grobid_fulltext", lambda pdf_bytes: "<TEI/>")
    monkeypatch.setattr(
        service,
        "parse_tei_fulltext",
        lambda tei_xml: {
            "title": "T", "abstract": "A", "body_text": "body", "grobid_version": "0.8.2",
        },
    )
    captured = {}
    monkeypatch.setattr(
        service, "upsert_table", lambda records, *a, **k: captured.update(records[0])
    )

    result = get_or_create_full_paper("p6")

    assert calls == ["https://example.org/p.pdf", "https://arxiv.org/pdf/1706.03762"]
    assert result.status == "success"
    assert result.pdf_url == "https://arxiv.org/pdf/1706.03762"
    assert captured["pdf_url"] == "https://arxiv.org/pdf/1706.03762"


def test_get_or_create_full_paper_all_candidates_fail_not_persisted(monkeypatch):
    monkeypatch.setattr(
        service, "ENGINE", _FakeEngine([None, ("https://example.org/p.pdf", "1706.03762")])
    )

    def _raise(*a, **k):
        raise requests.exceptions.ConnectionError("boom")

    monkeypatch.setattr(service._pdf_session, "get", _raise)
    upsert_called = {"called": False}
    monkeypatch.setattr(
        service, "upsert_table", lambda *a, **k: upsert_called.__setitem__("called", True)
    )

    with pytest.raises(PdfDownloadError) as exc_info:
        get_or_create_full_paper("p7")

    assert "example.org/p.pdf" in str(exc_info.value)
    assert "arxiv.org/pdf/1706.03762" in str(exc_info.value)
    assert upsert_called["called"] is False


def test_get_or_create_full_paper_grobid_failure_not_persisted(monkeypatch):
    monkeypatch.setattr(
        service, "ENGINE", _FakeEngine([None, ("https://example.org/p.pdf", None)])
    )
    monkeypatch.setattr(service._pdf_session, "get", lambda *a, **k: _FakeResponse())

    def _raise(*a, **k):
        raise GrobidUnavailableError("grobid down")

    monkeypatch.setattr(service, "call_grobid_fulltext", _raise)
    upsert_called = {"called": False}
    monkeypatch.setattr(
        service, "upsert_table", lambda *a, **k: upsert_called.__setitem__("called", True)
    )

    with pytest.raises(GrobidUnavailableError):
        get_or_create_full_paper("p4")

    assert upsert_called["called"] is False


def test_get_or_create_full_paper_success_persists(monkeypatch):
    monkeypatch.setattr(
        service, "ENGINE", _FakeEngine([None, ("https://example.org/p.pdf", None)])
    )
    monkeypatch.setattr(service._pdf_session, "get", lambda *a, **k: _FakeResponse())
    monkeypatch.setattr(service, "call_grobid_fulltext", lambda pdf_bytes: "<TEI/>")
    monkeypatch.setattr(
        service,
        "parse_tei_fulltext",
        lambda tei_xml: {
            "title": "T",
            "abstract": "A",
            "body_text": "body",
            "grobid_version": "0.8.2",
        },
    )
    captured = {}
    monkeypatch.setattr(
        service,
        "upsert_table",
        lambda records, *a, **k: captured.update(records[0]),
    )

    result = get_or_create_full_paper("p5")

    assert result.status == "success"
    assert result.full_text == "body"
    assert result.pdf_url == "https://example.org/p.pdf"
    assert captured["status"] == "success"
    assert captured["tei_xml"] == "<TEI/>"
