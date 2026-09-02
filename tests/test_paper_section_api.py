from datetime import datetime, timezone

from fastapi.testclient import TestClient

import literature_ai.search_service.api.routers.full_paper as full_paper_router
import main
from literature_ai.search_service.full_paper.service import FullPaperContent, PaperNotFoundError

_TEI_XML = """<?xml version="1.0"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
    <teiHeader>
        <fileDesc><titleStmt><title level="a" type="main">T</title></titleStmt></fileDesc>
    </teiHeader>
    <text><body>
        <div><head>Introduction</head><p>intro text</p></div>
        <div><head>Methodology</head><p>method text</p></div>
    </body></text>
</TEI>"""


def _content(**overrides) -> FullPaperContent:
    base = dict(
        paperId="p1", status="success", pdf_url="https://example.org/p.pdf",
        full_text="body", tei_xml=_TEI_XML, grobid_version="0.8.2",
        parsed_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return FullPaperContent(**base)


def test_get_paper_section_returns_section_by_index(monkeypatch):
    monkeypatch.setattr(main, "apply_schema", lambda path: None)
    monkeypatch.setattr(full_paper_router, "get_or_create_full_paper", lambda paper_id: _content())

    with TestClient(main.app) as client:
        response = client.get("/api/full-paper/p1/sections/1")

    assert response.status_code == 200
    body = response.json()
    assert body["header"] == "Methodology"
    assert body["section_text"] == "method text"
    assert body["index"] == 1


def test_get_paper_section_unknown_index_returns_404(monkeypatch):
    monkeypatch.setattr(main, "apply_schema", lambda path: None)
    monkeypatch.setattr(full_paper_router, "get_or_create_full_paper", lambda paper_id: _content())

    with TestClient(main.app) as client:
        response = client.get("/api/full-paper/p1/sections/5")

    assert response.status_code == 404


def test_get_paper_section_no_full_text_returns_404(monkeypatch):
    monkeypatch.setattr(main, "apply_schema", lambda path: None)
    monkeypatch.setattr(
        full_paper_router,
        "get_or_create_full_paper",
        lambda paper_id: _content(status="no_pdf_available", tei_xml=None, full_text=None),
    )

    with TestClient(main.app) as client:
        response = client.get("/api/full-paper/p1/sections/0")

    assert response.status_code == 404


def test_get_paper_section_unknown_paper_returns_404(monkeypatch):
    monkeypatch.setattr(main, "apply_schema", lambda path: None)

    def _raise(paper_id):
        raise PaperNotFoundError(f"No paper found for paperId={paper_id!r}")

    monkeypatch.setattr(full_paper_router, "get_or_create_full_paper", _raise)

    with TestClient(main.app) as client:
        response = client.get("/api/full-paper/missing/sections/0")

    assert response.status_code == 404


def test_list_paper_sections_returns_headers_in_order(monkeypatch):
    monkeypatch.setattr(main, "apply_schema", lambda path: None)
    monkeypatch.setattr(full_paper_router, "get_or_create_full_paper", lambda paper_id: _content())

    with TestClient(main.app) as client:
        response = client.get("/api/full-paper/p1/sections")

    assert response.status_code == 200
    body = response.json()
    assert body["paperId"] == "p1"
    assert [s["header"] for s in body["sections"]] == ["Introduction", "Methodology"]
    assert [s["index"] for s in body["sections"]] == [0, 1]


def test_get_full_paper_route_still_works_alongside_new_subroutes(monkeypatch):
    # Regression guard: /{paper_id} must not be shadowed by /{paper_id}/section(s).
    monkeypatch.setattr(main, "apply_schema", lambda path: None)
    monkeypatch.setattr(full_paper_router, "get_or_create_full_paper", lambda paper_id: _content())

    with TestClient(main.app) as client:
        response = client.get("/api/full-paper/p1")

    assert response.status_code == 200
    assert response.json()["status"] == "success"
