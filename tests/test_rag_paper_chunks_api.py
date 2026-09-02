from fastapi.testclient import TestClient

import literature_ai.search_service.api.routers.rag_paper_chunks as rag_router
import main
from literature_ai.search_service.full_paper.service import (
    GrobidUnavailableError,
    PaperNotFoundError,
)


def test_rag_paper_chunks_success(monkeypatch):
    monkeypatch.setattr(main, "apply_schema", lambda path: None)
    monkeypatch.setattr(
        rag_router,
        "rag_paper_chunks",
        lambda paper_ids, query, embedding_model, n_results: {
            "run_id": 7,
            "results": [
                {
                    "paperId": "p1",
                    "chunk_index": 0,
                    "section_header": "Methodology",
                    "chunk_text": "some method text",
                    "distance": 0.12,
                }
            ],
        },
    )

    with TestClient(main.app) as client:
        response = client.post(
            "/api/rag-paper-chunks",
            json={"paper_ids": ["p1"], "query": "how", "embedding_model": "fake_model"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == 7
    assert body["results"][0]["paperId"] == "p1"


def test_rag_paper_chunks_unknown_paper_returns_404(monkeypatch):
    monkeypatch.setattr(main, "apply_schema", lambda path: None)

    def _raise(paper_ids, query, embedding_model, n_results):
        raise PaperNotFoundError("no such paper")

    monkeypatch.setattr(rag_router, "rag_paper_chunks", _raise)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/rag-paper-chunks",
            json={"paper_ids": ["missing"], "query": "q", "embedding_model": "fake_model"},
        )

    assert response.status_code == 404


def test_rag_paper_chunks_unsupported_model_returns_400(monkeypatch):
    monkeypatch.setattr(main, "apply_schema", lambda path: None)

    def _raise(paper_ids, query, embedding_model, n_results):
        raise NotImplementedError("embed_text not supported for this model")

    monkeypatch.setattr(rag_router, "rag_paper_chunks", _raise)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/rag-paper-chunks",
            json={"paper_ids": ["p1"], "query": "q", "embedding_model": "specter_v2"},
        )

    assert response.status_code == 400


def test_rag_paper_chunks_grobid_unavailable_returns_504(monkeypatch):
    monkeypatch.setattr(main, "apply_schema", lambda path: None)

    def _raise(paper_ids, query, embedding_model, n_results):
        raise GrobidUnavailableError("grobid down")

    monkeypatch.setattr(rag_router, "rag_paper_chunks", _raise)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/rag-paper-chunks",
            json={"paper_ids": ["p1"], "query": "q", "embedding_model": "fake_model"},
        )

    assert response.status_code == 504


def test_rag_paper_chunks_rejects_empty_paper_ids(monkeypatch):
    monkeypatch.setattr(main, "apply_schema", lambda path: None)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/rag-paper-chunks",
            json={"paper_ids": [], "query": "q", "embedding_model": "fake_model"},
        )

    assert response.status_code == 422
