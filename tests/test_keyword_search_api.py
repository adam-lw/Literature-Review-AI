from fastapi.testclient import TestClient

import literature_ai.search_service.api.routers.keyword_search as keyword_search_router
import main


def test_keyword_search_success(monkeypatch):
    monkeypatch.setattr(main, "apply_schema", lambda path: None)
    monkeypatch.setattr(
        keyword_search_router,
        "keyword_search",
        lambda query, n_results: [
            {
                "paperId": "p1",
                "title": "T",
                "abstract": "A",
                "year": 2020,
                "venue": "V",
                "citationCount": 1,
                "url": "http://x",
                "DOI": "10.1/x",
                "rank": 0.5,
            }
        ],
    )

    with TestClient(main.app) as client:
        response = client.post("/api/keyword-search", json={"query": "test", "n_results": 5})

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "test"
    assert body["n_results"] == 5
    assert body["results"][0]["paperId"] == "p1"
    assert body["results"][0]["rank"] == 0.5


def test_keyword_search_rejects_empty_query(monkeypatch):
    monkeypatch.setattr(main, "apply_schema", lambda path: None)

    with TestClient(main.app) as client:
        response = client.post("/api/keyword-search", json={"query": "", "n_results": 5})

    assert response.status_code == 422


def test_keyword_search_rejects_out_of_range_n_results(monkeypatch):
    monkeypatch.setattr(main, "apply_schema", lambda path: None)

    with TestClient(main.app) as client:
        response = client.post("/api/keyword-search", json={"query": "test", "n_results": 0})

    assert response.status_code == 422
