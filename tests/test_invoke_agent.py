import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

import literature_ai.agent_service.api.routers.invoke_agent as invoke_agent_router
from literature_ai.agent_service.agent.agent.core.response import AgentResponse
from literature_ai.agent_service.agent.llm.core import Message, Messages
import main


def _row(role: str, content: str) -> dict:
    """One persisted turn as `db.list_messages` hands it back - see app.messages."""
    return {
        "role": role,
        "content": content,
        "tool_call_id": None,
        "tool_name": None,
        "tool_arguments": None,
        "created_at": datetime.now(timezone.utc),
    }


def _conversation(conversation_id: uuid.UUID) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "conversation_id": conversation_id,
        "project_id": uuid.uuid4(),
        "stage": "scoping",
        "mode": "agent",
        "completed": False,
        "author": None,
        "created_at": now,
        "updated_at": now,
    }


def _state_with(prior_pairs: list[tuple[str, str]], new_pairs: list[tuple[str, str]]) -> Messages:
    """Builds a fake ReactAgent.state: [system] + replayed prior turns + new turns, matching
    what `_run_phase_agent`'s `new_turns = state[1 + len(prior):]` slicing expects."""
    state = Messages()
    state.add_system("fake system prompt")
    for role, content in prior_pairs:
        state.append({"role": role, "content": content})
    for role, content in new_pairs:
        state.append({"role": role, "content": content})
    return state


def test_first_call_spawns_not_resumes(monkeypatch):
    """A stage's first turn (no persisted messages yet) must call spawn_agent, not resume_agent -
    resuming an empty conversation would have nothing to resume. The agent service itself writes
    nothing to Postgres (see invoke_agent.py) - it hands the new turns back in the response for
    the caller to persist, so this only asserts on the HTTP response, not on any db.* call."""
    monkeypatch.setattr(main, "apply_schema", lambda path: None)
    project_id = uuid.uuid4()
    conversation_id = uuid.uuid4()

    calls = {"spawn": 0, "resume": 0}

    async def fake_spawn_agent(name, instruction, memory_objects=None):
        calls["spawn"] += 1
        assert instruction == "hello"
        state = _state_with([], [("user", "hello"), ("assistant", "hi there")])
        return AgentResponse(status="completed", state=state, result=Message(role="assistant", content="hi there"))

    async def fake_resume_agent(*args, **kwargs):
        calls["resume"] += 1
        raise AssertionError("resume_agent should not be called on a conversation's first turn")

    monkeypatch.setattr(invoke_agent_router, "spawn_agent", fake_spawn_agent)
    monkeypatch.setattr(invoke_agent_router, "resume_agent", fake_resume_agent)
    monkeypatch.setattr(
        invoke_agent_router.db, "get_or_create_conversation", lambda pid, stage, mode: _conversation(conversation_id)
    )
    monkeypatch.setattr(invoke_agent_router.db, "list_messages", lambda cid: [])
    monkeypatch.setattr(invoke_agent_router.db, "get_conversation", lambda pid, stage: None)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/invoke-agent",
            json={"stage": "scoping", "project_id": str(project_id), "message": "hello"},
        )

    assert response.status_code == 200
    assert calls == {"spawn": 1, "resume": 0}
    body = response.json()
    # The project-scoped contract never resends history - `messages` stays empty - and hands
    # back exactly the turns this call produced, for the caller to persist itself.
    assert body["messages"] == []
    assert body["conversation_id"] == str(conversation_id)
    assert body["new_messages"] == [
        {"role": "user", "content": "hello", "tool_name": None, "tool_arguments": None},
        {"role": "assistant", "content": "hi there", "tool_name": None, "tool_arguments": None},
    ]


def test_second_call_resumes_with_no_system_message_and_no_duplicate_turns(monkeypatch):
    """A stage's second turn must call resume_agent with `history` built purely from persisted
    prior turns (no synthetic system-role entry - spawn_agent/resume_agent now rebuild the system
    prompt fresh from (stage, memory) themselves, see spawn_agent.py), and the response's
    `new_messages` must carry only the turns this call actually produced, not the replayed prior
    ones again."""
    monkeypatch.setattr(main, "apply_schema", lambda path: None)
    project_id = uuid.uuid4()
    conversation_id = uuid.uuid4()

    prior = [_row("user", "hello"), _row("assistant", "hi there")]

    calls = {"spawn": 0, "resume": 0}
    captured_history = {}

    async def fake_spawn_agent(*args, **kwargs):
        calls["spawn"] += 1
        raise AssertionError("spawn_agent should not be called once the conversation has prior turns")

    async def fake_resume_agent(name, history, instruction, memory_objects=None):
        calls["resume"] += 1
        captured_history["messages"] = list(history)
        assert instruction == "second message"
        state = _state_with(
            [(m["role"], m["content"]) for m in prior],
            [("user", "second message"), ("assistant", "second reply")],
        )
        return AgentResponse(
            status="completed", state=state, result=Message(role="assistant", content="second reply")
        )

    monkeypatch.setattr(invoke_agent_router, "spawn_agent", fake_spawn_agent)
    monkeypatch.setattr(invoke_agent_router, "resume_agent", fake_resume_agent)
    monkeypatch.setattr(
        invoke_agent_router.db, "get_or_create_conversation", lambda pid, stage, mode: _conversation(conversation_id)
    )
    monkeypatch.setattr(invoke_agent_router.db, "list_messages", lambda cid: prior)
    monkeypatch.setattr(invoke_agent_router.db, "get_conversation", lambda pid, stage: None)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/invoke-agent",
            json={"stage": "scoping", "project_id": str(project_id), "message": "second message"},
        )

    assert response.status_code == 200
    assert calls == {"spawn": 0, "resume": 1}
    assert [m.role for m in captured_history["messages"]] == ["user", "assistant"]
    assert [m.content for m in captured_history["messages"]] == ["hello", "hi there"]
    assert response.json()["new_messages"] == [
        {"role": "user", "content": "second message", "tool_name": None, "tool_arguments": None},
        {"role": "assistant", "content": "second reply", "tool_name": None, "tool_arguments": None},
    ]


def test_question_turn_comes_back_structured_not_as_raw_tool_call_text(monkeypatch):
    """A run that ends by asking the user something must hand back that turn as a structured
    `tool_name`/`tool_arguments` pair, not the raw `Called tool \\`ask_user\\` with arguments
    {...}` bookkeeping text `ReactAgent` puts in its own LLM-facing context - that flattened text
    reaching the persisted transcript is exactly what rendered as a raw tool call in the UI."""
    monkeypatch.setattr(main, "apply_schema", lambda path: None)
    project_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    from literature_ai.agent_service.agent.agent.core.response import Question

    async def fake_spawn_agent(name, instruction, memory_objects=None):
        # Matches react.py's actual shape for a turn that thinks and then calls a tool: the
        # thinking lands as its own plain turn first, immediately followed by the flattened
        # "Called tool ..." breadcrumb turn for the call itself.
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
    monkeypatch.setattr(
        invoke_agent_router.db, "get_or_create_conversation", lambda pid, stage, mode: _conversation(conversation_id)
    )
    monkeypatch.setattr(invoke_agent_router.db, "list_messages", lambda cid: [])
    monkeypatch.setattr(invoke_agent_router.db, "get_conversation", lambda pid, stage: None)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/invoke-agent",
            json={"stage": "scoping", "project_id": str(project_id), "message": "hello"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["question"]["question"] == "Which databases?"
    # The user turn plus exactly one structured ask_user turn - the leading plain-text thinking
    # turn `ReactAgent` also persisted must be folded in here, not left behind as a duplicate.
    assert body["new_messages"] == [
        {"role": "user", "content": "hello", "tool_name": None, "tool_arguments": None},
        {
            "role": "assistant",
            "content": "I need to know the databases before searching.",
            "tool_name": "ask_user",
            "tool_arguments": {
                "question": "Which databases?",
                "description": "",
                "options": {"a": "PubMed"},
                "allows_freetext": True,
            },
        },
    ]
