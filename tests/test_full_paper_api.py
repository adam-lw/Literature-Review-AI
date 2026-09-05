from datetime import datetime, timezone

from fastapi.testclient import TestClient

import literature_ai.search_service.api.routers.full_paper as full_paper_router
import main
from literature_ai.search_service.data_collect.collect_full_papers import PaperNotFoundError
from literature_ai.search_service.processing.pdf_parsing import (
    GrobidParseError,
    GrobidUnavailableError,
)


def _record(**overrides) -> dict:
    base = dict(
        paperId="p1",
        status="success",
        pdf_url="https://example.org/p.pdf",
        full_text="full text",
        tei_xml="<TEI/>",
        grobid_version="0.8.2",
        parsed_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return base


def test_get_full_paper_success_excludes_tei_xml_by_default(monkeypatch):
    monkeypatch.setattr(main, "apply_schema", lambda path: None)
    monkeypatch.setattr(full_paper_router, "get_or_create_full_paper", lambda paper_id: _record())

    with TestClient(main.app) as client:
        response = client.get("/api/full-paper/p1")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["full_text"] == "full text"
    assert body["tei_xml"] is None


def test_get_full_paper_includes_tei_xml_when_requested(monkeypatch):
    monkeypatch.setattr(main, "apply_schema", lambda path: None)
    monkeypatch.setattr(full_paper_router, "get_or_create_full_paper", lambda paper_id: _record())

    with TestClient(main.app) as client:
        response = client.get("/api/full-paper/p1?include_tei_xml=true")

    assert response.status_code == 200
    assert response.json()["tei_xml"] == "<TEI/>"


def test_get_full_paper_no_pdf_available_returns_200(monkeypatch):
    monkeypatch.setattr(main, "apply_schema", lambda path: None)
    monkeypatch.setattr(
        full_paper_router,
        "get_or_create_full_paper",
        lambda paper_id: _record(
            status="no_pdf_available", pdf_url=None, full_text=None, tei_xml=None
        ),
    )

    with TestClient(main.app) as client:
        response = client.get("/api/full-paper/p2")

    assert response.status_code == 200
    assert response.json()["status"] == "no_pdf_available"


def test_get_full_paper_unknown_paper_returns_404(monkeypatch):
    monkeypatch.setattr(main, "apply_schema", lambda path: None)

    def _raise(paper_id):
        raise PaperNotFoundError(f"No paper found for paperId={paper_id!r}")

    monkeypatch.setattr(full_paper_router, "get_or_create_full_paper", _raise)

    with TestClient(main.app) as client:
        response = client.get("/api/full-paper/missing")

    assert response.status_code == 404


def test_get_full_paper_grobid_parse_error_returns_502(monkeypatch):
    monkeypatch.setattr(main, "apply_schema", lambda path: None)

    def _raise(paper_id):
        raise GrobidParseError("bad tei")

    monkeypatch.setattr(full_paper_router, "get_or_create_full_paper", _raise)

    with TestClient(main.app) as client:
        response = client.get("/api/full-paper/p4")

    assert response.status_code == 502


def test_get_full_paper_grobid_unavailable_returns_504(monkeypatch):
    monkeypatch.setattr(main, "apply_schema", lambda path: None)

    def _raise(paper_id):
        raise GrobidUnavailableError("grobid down")

    monkeypatch.setattr(full_paper_router, "get_or_create_full_paper", _raise)

    with TestClient(main.app) as client:
        response = client.get("/api/full-paper/p5")

    assert response.status_code == 504
