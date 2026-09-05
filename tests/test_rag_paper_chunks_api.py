from fastapi.testclient import TestClient

import literature_ai.search_service.api.routers.rag_paper_chunks as rag_router
import main


def test_rag_paper_chunks_success(monkeypatch):
    monkeypatch.setattr(main, "apply_schema", lambda path: None)
    monkeypatch.setattr(
        rag_router,
        "rag_paper_chunks",
        lambda paper_ids, query, n_results: {
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
            json={"paper_ids": ["p1"], "query": "how"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["results"][0]["paperId"] == "p1"


def test_rag_paper_chunks_unprocessed_paper_returns_no_results(monkeypatch):
    monkeypatch.setattr(main, "apply_schema", lambda path: None)
    monkeypatch.setattr(
        rag_router, "rag_paper_chunks", lambda paper_ids, query, n_results: {"results": []}
    )

    with TestClient(main.app) as client:
        response = client.post(
            "/api/rag-paper-chunks",
            json={"paper_ids": ["not_yet_processed"], "query": "q"},
        )

    assert response.status_code == 200
    assert response.json()["results"] == []


def test_rag_paper_chunks_rejects_empty_paper_ids(monkeypatch):
    monkeypatch.setattr(main, "apply_schema", lambda path: None)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/rag-paper-chunks",
            json={"paper_ids": [], "query": "q"},
        )

    assert response.status_code == 422
