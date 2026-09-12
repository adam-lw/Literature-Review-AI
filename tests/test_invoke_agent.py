from fastapi.testclient import TestClient

import literature_ai.agent_service.api.routers.invoke_agent as invoke_agent_router
from literature_ai.agent_service.agent.agent.core.response import AgentResponse, Question
from literature_ai.agent_service.agent.llm.core import Message, Messages
import main


def _state_with(prior_pairs: list[tuple[str, str]], new_pairs: list[tuple[str, str]]) -> Messages:
    """Builds a fake ReactAgent.state: [system] + replayed prior turns + new turns."""
    state = Messages()
    state.add_system("fake system prompt")
    for role, content in prior_pairs:
        state.append({"role": role, "content": content})
    for role, content in new_pairs:
        state.append({"role": role, "content": content})
    return state


def test_create_agent_spawns_a_new_conversation(monkeypatch):
    """`create_agent` starts a brand new conversation - no history to resend yet - and hands
    back the full react state (system prompt included) plus the plain-text response. agent_service
    is fully stateless: it never touches Postgres and has no notion of "project" or "phase"."""
    monkeypatch.setattr(main, "apply_schema", lambda path: None)

    async def fake_spawn_agent(name, instruction, memory_objects=None):
        assert name == "scoping"
        assert instruction == "hello"
        state = _state_with([], [("user", "hello"), ("assistant", "hi there")])
        return AgentResponse(status="completed", state=state, result=Message(role="assistant", content="hi there"))

    monkeypatch.setattr(invoke_agent_router, "spawn_agent", fake_spawn_agent)

    with TestClient(main.app) as client:
        response = client.post("/api/invoke-agent/create", json={"stage": "scoping", "content": "hello"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["response"] == "hi there"
    assert [m["role"] for m in body["messages"]] == ["system", "user", "assistant"]
    assert body["memory"] == []


def test_invoke_agent_resumes_dropping_the_echoed_system_entry(monkeypatch):
    """A follow-up call must call resume_agent with `history` built purely from the caller's
    resent turns, minus the leading system-role entry `_to_response` echoed back on the previous
    call (resume_agent rebuilds the system prompt fresh itself - see spawn_agent.py) and minus
    the trailing new instruction, which is split out separately."""
    monkeypatch.setattr(main, "apply_schema", lambda path: None)

    calls = {"spawn": 0, "resume": 0}
    captured = {}

    async def fake_spawn_agent(*args, **kwargs):
        calls["spawn"] += 1
        raise AssertionError("spawn_agent should not be called on a follow-up turn")

    async def fake_resume_agent(name, history, instruction, memory_objects=None):
        calls["resume"] += 1
        captured["history"] = list(history)
        assert name == "scoping"
        assert instruction == "second message"
        state = _state_with(
            [("user", "hello"), ("assistant", "hi there")],
            [("user", "second message"), ("assistant", "second reply")],
        )
        return AgentResponse(
            status="completed", state=state, result=Message(role="assistant", content="second reply")
        )

    monkeypatch.setattr(invoke_agent_router, "spawn_agent", fake_spawn_agent)
    monkeypatch.setattr(invoke_agent_router, "resume_agent", fake_resume_agent)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/invoke-agent",
            json={
                "stage": "scoping",
                "messages": [
                    {"role": "system", "content": "stale echoed system prompt"},
                    {"role": "user", "content": "hello"},
                    {"role": "assistant", "content": "hi there"},
                    {"role": "user", "content": "second message"},
                ],
            },
        )

    assert response.status_code == 200
    assert calls == {"spawn": 0, "resume": 1}
    assert [m.role for m in captured["history"]] == ["user", "assistant"]
    assert [m.content for m in captured["history"]] == ["hello", "hi there"]
    assert response.json()["response"] == "second reply"


def test_question_result_returns_structured_question_and_unmodified_messages(monkeypatch):
    """A run that ends by asking the user something hands back that as a structured `question`
    field. `messages` (the full raw trace, including the "Called tool `ask_user` with arguments
    {...}" bookkeeping text `ReactAgent` puts in its own LLM-facing context) is returned
    unmodified - agent_service has no opinion on how a caller chooses to persist/render a turn;
    folding that bookkeeping text into something nicer for storage is the caller's job now."""
    monkeypatch.setattr(main, "apply_schema", lambda path: None)

    async def fake_spawn_agent(name, instruction, memory_objects=None):
        state = Messages()
        state.add_system("fake system prompt")
        state.add_user("hello")
        state.add("I need to know the databases before searching.", role="assistant")
        state.add(
            "Called tool `ask_user` with arguments "
            "{'question': 'Which databases?', 'options': {'a': 'PubMed'}}",
            role="assistant",
        )
        return AgentResponse(
            status="awaiting_input",
            state=state,
            result=Question(question="Which databases?", options={"a": "PubMed"}),
            reasoning="I need to know the databases before searching.",
        )

    monkeypatch.setattr(invoke_agent_router, "spawn_agent", fake_spawn_agent)

    with TestClient(main.app) as client:
        response = client.post("/api/invoke-agent/create", json={"stage": "scoping", "content": "hello"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "awaiting_input"
    assert body["question"]["question"] == "Which databases?"
    assert body["question"]["options"] == {"a": "PubMed"}
    assert [m["content"] for m in body["messages"][1:]] == [
        "hello",
        "I need to know the databases before searching.",
        "Called tool `ask_user` with arguments "
        "{'question': 'Which databases?', 'options': {'a': 'PubMed'}}",
    ]


def test_response_echoes_back_mutated_memory_generically(monkeypatch):
    """A tool can mutate a memory object in place during the turn (e.g. `scoping_chat`'s
    `update_scope`) - since agent_service holds nothing between calls, the only way the caller
    can observe that is if the response echoes back the current content of every memory object
    the turn ran with. This must happen for any stage/memory-type, not just `scoping` -
    agent_service has no special-cased notion of which memory type "matters"."""
    monkeypatch.setattr(main, "apply_schema", lambda path: None)

    async def fake_spawn_agent(name, instruction, memory_objects=None):
        # Simulates a tool mutating the caller-supplied memory object in place, the same way
        # ReactAgent._call_tool injects and mutates the live object by reference.
        memory_objects["scoping"].specification = {"research_questions": ["updated?"]}
        state = _state_with([], [("user", instruction), ("assistant", "updated the scope")])
        return AgentResponse(
            status="completed", state=state, result=Message(role="assistant", content="updated the scope")
        )

    monkeypatch.setattr(invoke_agent_router, "spawn_agent", fake_spawn_agent)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/invoke-agent/create",
            json={
                "stage": "scoping_chat",
                "content": "narrow the scope",
                "memory": [{"type": "scoping", "specification": {"research_questions": ["original?"]}}],
            },
        )

    assert response.status_code == 200
    assert response.json()["memory"] == [
        {"type": "scoping", "specification": {"research_questions": ["updated?"]}}
    ]


def test_review_memory_input_round_trips(monkeypatch):
    """A `review`-typed memory input (needed to resume `review_chat`/`writing_chat` with
    existing verdicts) builds an AgentPaperReviewMemory and echoes it back unchanged when no
    tool mutates it."""
    monkeypatch.setattr(main, "apply_schema", lambda path: None)

    async def fake_spawn_agent(name, instruction, memory_objects=None):
        assert "reviews" in memory_objects
        review = memory_objects["reviews"].reviews["paper-1"]
        assert review.reviewed is True
        assert review.included is True
        assert review.inclusion_reasoning["methodological_focus"].passed is True
        state = _state_with([], [("user", instruction), ("assistant", "ok")])
        return AgentResponse(status="completed", state=state, result=Message(role="assistant", content="ok"))

    monkeypatch.setattr(invoke_agent_router, "spawn_agent", fake_spawn_agent)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/invoke-agent/create",
            json={
                "stage": "review_chat",
                "content": "how's paper-1 looking?",
                "memory": [
                    {
                        "type": "review",
                        "reviews": {
                            "paper-1": {
                                "reviewed": True,
                                "included": True,
                                "inclusion_reasoning": {
                                    "methodological_focus": {"passed": True, "reason": "matches"}
                                },
                            }
                        },
                    }
                ],
            },
        )

    assert response.status_code == 200
    assert response.json()["memory"] == [
        {
            "type": "review",
            "reviews": {
                "paper-1": {
                    "reviewed": True,
                    "included": True,
                    "inclusion_reasoning": {
                        "methodological_focus": {"passed": True, "reason": "matches"}
                    },
                }
            },
        }
    ]
