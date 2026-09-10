import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

import literature_ai.app.api as app_api
import literature_ai.app.api.routers.projects as projects_router
import literature_ai.search_service.api.routers.embedding_models as embedding_models_router
import literature_ai.search_service.api.routers.search as search_router
import main


def _fake_project(project_id: uuid.UUID, project_mode: str = "human") -> dict:
    now = datetime.now(timezone.utc)
    return {
        "project_id": project_id,
        "project_title": "Untitled project (2026-08-03 12:00)",
        "description": None,
        "inclusion_criteria": None,
        "embedding_run_id": 1,
        "project_mode": project_mode,
        "created_at": now,
        "updated_at": now,
        "searches": [],
    }


def _fake_search(
    project_id: uuid.UUID, search_id: uuid.UUID, result_id: uuid.UUID
) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "search_id": search_id,
        "project_id": project_id,
        "query": "oct computer vision",
        "n_results": 10,
        "created_at": now,
        "results": [
            {
                "result_id": result_id,
                "search_id": search_id,
                "paper_id": "abc123",
                "type": "embedding",
                "search_rank": 1,
                "distance": 0.12,
                "distance_type": "cosine",
                "title": "Deep learning for OCT segmentation",
                "abstract": "...",
                "year": 2021,
                "venue": "MICCAI",
                "citation_count": 42,
                "url": "https://example.org/paper.pdf",
                "doi": "10.1234/abc",
                "included": True,
            }
        ],
    }


def test_app_api_projects_endpoints(monkeypatch):
    monkeypatch.setattr(app_api, "apply_schema", lambda path: None)
    monkeypatch.setattr(projects_router, "vector_search", lambda **kwargs: [])

    project_id = uuid.uuid4()
    search_id = uuid.uuid4()
    result_id = uuid.uuid4()

    with TestClient(app_api.app) as client:
        monkeypatch.setattr(
            projects_router.db,
            "list_projects",
            lambda: [
                {
                    **_fake_project(project_id),
                    "search_count": 1,
                    "paper_count": 1,
                    "included_count": 1,
                }
            ],
        )
        response = client.get("/projects")
        assert response.status_code == 200
        assert len(response.json()["projects"]) == 1

        monkeypatch.setattr(
            projects_router.db,
            "create_project",
            lambda **kwargs: _fake_project(project_id),
        )
        response = client.post(
            "/projects",
            json={
                "queries": ["oct computer vision"],
                "embedding_run_id": 1,
            },
        )
        assert response.status_code == 200
        assert response.json()["project_id"] == str(project_id)

        monkeypatch.setattr(projects_router.db, "get_project", lambda pid: None)
        response = client.get(f"/projects/{project_id}")
        assert response.status_code == 404

        monkeypatch.setattr(
            projects_router.db, "get_project", lambda pid: _fake_project(project_id)
        )
        response = client.get(f"/projects/{project_id}")
        assert response.status_code == 200

        monkeypatch.setattr(
            projects_router.db,
            "create_search",
            lambda pid, query, n_results: {"search_id": search_id},
        )
        monkeypatch.setattr(
            projects_router.db, "save_search_results", lambda sid, rows: rows
        )
        monkeypatch.setattr(
            projects_router.db,
            "get_search",
            lambda sid: _fake_search(project_id, search_id, result_id),
        )
        response = client.post(
            f"/projects/{project_id}/searches", json={"query": "oct computer vision"}
        )
        assert response.status_code == 200
        assert response.json()["search_id"] == str(search_id)
        assert response.json()["results"][0]["included"] is True

        monkeypatch.setattr(
            projects_router.db, "set_inclusion_bulk", lambda pid, items: len(items)
        )
        response = client.patch(
            f"/projects/{project_id}/inclusion",
            json={"items": [{"result_id": str(result_id), "included": False}]},
        )
        assert response.status_code == 200
        assert response.json()["updated"] == 1

        monkeypatch.setattr(
            projects_router.db, "set_inclusion", lambda rid, included: None
        )
        response = client.patch(
            f"/results/{result_id}/inclusion", json={"included": False}
        )
        assert response.status_code == 200
        assert response.json()["included"] is False


def test_create_agent_project(monkeypatch):
    monkeypatch.setattr(app_api, "apply_schema", lambda path: None)
    project_id = uuid.uuid4()

    with TestClient(app_api.app) as client:
        captured = {}

        def fake_create_agent_project(description, inclusion_criteria=None, project_title=None):
            captured["description"] = description
            captured["inclusion_criteria"] = inclusion_criteria
            captured["project_title"] = project_title
            return _fake_project(project_id, project_mode="agent")

        monkeypatch.setattr(projects_router.db, "create_agent_project", fake_create_agent_project)

        response = client.post(
            "/projects/agent-mode",
            json={"description": "A review of transformer architectures."},
        )
        assert response.status_code == 200
        assert response.json()["project_mode"] == "agent"
        assert captured["description"] == "A review of transformer architectures."


def test_update_project_forwards_explicit_null(monkeypatch):
    """Regression test: PATCH /projects/{id} with an explicit null for an allowed field must
    reach db.update_project with that key present, not silently drop it - update_project's own
    filter (persistence_handling.py) used to also strip None values, which meant a client could
    never clear a field. The router-level `exclude_unset=True` is what should do the filtering,
    not a second None-check on top of it."""
    monkeypatch.setattr(app_api, "apply_schema", lambda path: None)
    project_id = uuid.uuid4()

    with TestClient(app_api.app) as client:
        captured = {}

        def fake_update_project(pid, **fields):
            captured.update(fields)
            return _fake_project(project_id)

        monkeypatch.setattr(projects_router.db, "get_project", lambda pid: _fake_project(project_id))
        monkeypatch.setattr(projects_router.db, "update_project", fake_update_project)

        response = client.patch(f"/projects/{project_id}", json={"inclusion_criteria": None})
        assert response.status_code == 200
        assert "inclusion_criteria" in captured
        assert captured["inclusion_criteria"] is None


def test_project_conversations_and_scope_endpoints(monkeypatch):
    monkeypatch.setattr(app_api, "apply_schema", lambda path: None)
    project_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    conversation = {
        "conversation_id": conversation_id,
        "project_id": project_id,
        "stage": "scoping",
        "mode": "agent",
        "completed": False,
        "author": None,
        "created_at": now,
        "updated_at": now,
    }

    with TestClient(app_api.app) as client:
        monkeypatch.setattr(projects_router.db, "get_project", lambda pid: _fake_project(project_id))

        def fake_get_conversation(pid, stage):
            return conversation if stage == "scoping" else None

        monkeypatch.setattr(projects_router.db, "get_conversation", fake_get_conversation)
        monkeypatch.setattr(
            projects_router.db,
            "list_messages",
            lambda cid: [{"role": "user", "content": "hello", "created_at": now}],
        )

        response = client.get(f"/projects/{project_id}/conversations")
        assert response.status_code == 200
        body = response.json()
        assert body["scoping"]["conversation"]["stage"] == "scoping"
        assert len(body["scoping"]["messages"]) == 1
        assert body["review"]["conversation"] is None
        assert body["review"]["messages"] == []

        monkeypatch.setattr(
            projects_router.db,
            "get_scope",
            lambda cid: {
                "scope_id": uuid.uuid4(),
                "conversation_id": cid,
                "content": {"research_questions": ["...?"]},
                "created_at": now,
                "updated_at": now,
            },
        )
        response = client.get(f"/projects/{project_id}/scope")
        assert response.status_code == 200
        assert response.json()["content"] == {"research_questions": ["...?"]}

        completed_conversation = {**conversation, "completed": True}
        monkeypatch.setattr(
            projects_router.db,
            "set_conversation_completed",
            lambda cid, completed: None,
        )
        monkeypatch.setattr(
            projects_router.db,
            "get_conversation",
            lambda pid, stage: completed_conversation if stage == "scoping" else None,
        )
        response = client.patch(f"/projects/{project_id}/conversations/scoping", json={"completed": True})
        assert response.status_code == 200
        assert response.json()["completed"] is True


def test_main_combined_wiring(monkeypatch):
    monkeypatch.setattr(main, "apply_schema", lambda path: None)
    monkeypatch.setattr(embedding_models_router, "ENGINE", _FakeEngine())
    monkeypatch.setattr(search_router, "vector_search", lambda **kwargs: [])
    monkeypatch.setattr(projects_router.db, "list_projects", lambda: [])

    with TestClient(main.app) as client:
        response = client.get("/api/embedding-models")
        assert response.status_code == 200
        assert response.json()["runs"] == []

        response = client.post("/api/search", json={"query": "oct", "run_id": 1})
        assert response.status_code == 200
        assert response.json()["results"] == []

        response = client.get("/api/projects")
        assert response.status_code == 200
        assert response.json()["projects"] == []


class _FakeResult:
    def fetchall(self):
        return []


class _FakeConn:
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, *args, **kwargs):
        return _FakeResult()


class _FakeEngine:
    def connect(self):
        return _FakeConn()
