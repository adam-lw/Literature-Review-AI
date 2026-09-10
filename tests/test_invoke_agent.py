import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

import literature_ai.agent_service.api.routers.invoke_agent as invoke_agent_router
from literature_ai.agent_service.agent.agent.core.response import AgentResponse, Question
from literature_ai.agent_service.agent.llm.core import Message, Messages
from literature_ai.agent_service.agent.tools import ToolCall
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
    resuming an empty conversation would have nothing to resume."""
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

    added = []
    monkeypatch.setattr(
        invoke_agent_router.db, "add_messages", lambda cid, messages: added.append((cid, messages))
    )

    with TestClient(main.app) as client:
        response = client.post(
            "/api/invoke-agent",
            json={"stage": "scoping", "project_id": str(project_id), "message": "hello"},
        )

    assert response.status_code == 200
    assert calls == {"spawn": 1, "resume": 0}
    assert added == [
        (
            str(conversation_id),
            [
                {"role": "user", "content": "hello", "tool_name": None, "tool_arguments": None},
                {"role": "assistant", "content": "hi there", "tool_name": None, "tool_arguments": None},
            ],
        )
    ]
    # The project-scoped contract never resends history - `messages` stays empty.
    assert response.json()["messages"] == []


def test_second_call_resumes_with_no_system_message_and_no_duplicate_turns(monkeypatch):
    """A stage's second turn must call resume_agent with `history` built purely from persisted
    prior turns (no synthetic system-role entry - spawn_agent/resume_agent now rebuild the system
    prompt fresh from (stage, memory) themselves, see spawn_agent.py), and must persist only the
    turns this call actually produced, not the replayed prior ones again."""
    monkeypatch.setattr(main, "apply_schema", lambda path: None)
    project_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

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

    added = []
    monkeypatch.setattr(
        invoke_agent_router.db, "add_messages", lambda cid, messages: added.append((cid, messages))
    )

    with TestClient(main.app) as client:
        response = client.post(
            "/api/invoke-agent",
            json={"stage": "scoping", "project_id": str(project_id), "message": "second message"},
        )

    assert response.status_code == 200
    assert calls == {"spawn": 0, "resume": 1}
    assert [m.role for m in captured_history["messages"]] == ["user", "assistant"]
    assert [m.content for m in captured_history["messages"]] == ["hello", "hi there"]
    assert added == [
        (
            str(conversation_id),
            [
                {"role": "user", "content": "second message", "tool_name": None, "tool_arguments": None},
                {"role": "assistant", "content": "second reply", "tool_name": None, "tool_arguments": None},
            ],
        )
    ]


def test_question_turn_persists_its_tool_call_not_its_text(monkeypatch):
    """A turn that asked the user something must persist the `ask_user` call structurally (name +
    arguments, for app.tool_calls) with only the agent's thinking as its content - otherwise the
    call is flattened into text and reloading the conversation renders it as a chat message."""
    monkeypatch.setattr(main, "apply_schema", lambda path: None)
    project_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    arguments = {
        "question": "Which databases should I search?",
        "options": {"a": "PubMed", "b": "Scopus"},
        "allows_freetext": True,
    }

    async def fake_spawn_agent(name, instruction, memory_objects=None):
        state = Messages()
        state.add_system("fake system prompt")
        state.add_user("hello")
        state.add(
            "I need to know the databases before searching.",
            role="assistant",
            tool_call=ToolCall(id="call_1", name="ask_user", arguments=arguments),
        )
        return AgentResponse(
            status="awaiting_input", state=state, result=Question(**arguments)
        )

    monkeypatch.setattr(invoke_agent_router, "spawn_agent", fake_spawn_agent)
    monkeypatch.setattr(
        invoke_agent_router.db, "get_or_create_conversation", lambda pid, stage, mode: _conversation(conversation_id)
    )
    monkeypatch.setattr(invoke_agent_router.db, "list_messages", lambda cid: [])
    monkeypatch.setattr(invoke_agent_router.db, "get_conversation", lambda pid, stage: None)

    added = []
    monkeypatch.setattr(
        invoke_agent_router.db, "add_messages", lambda cid, messages: added.append((cid, messages))
    )

    with TestClient(main.app) as client:
        response = client.post(
            "/api/invoke-agent",
            json={"stage": "scoping", "project_id": str(project_id), "message": "hello"},
        )

    assert response.status_code == 200
    assert response.json()["question"]["question"] == arguments["question"]
    _, persisted = added[0]
    assert persisted[-1] == {
        "role": "assistant",
        "content": "I need to know the databases before searching.",
        "tool_name": "ask_user",
        "tool_arguments": arguments,
    }


def test_resumed_conversation_replays_tool_calls_structurally(monkeypatch):
    """Persisted tool calls must come back as `ToolCall`s on resume, so an agent picking a
    conversation back up sees the calls it already made rather than a gap in its context."""
    monkeypatch.setattr(main, "apply_schema", lambda path: None)
    project_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    arguments = {"question": "Which databases?", "options": {}, "allows_freetext": True}

    prior = [
        _row("user", "hello"),
        {
            **_row("assistant", "I need the databases first."),
            "tool_call_id": uuid.uuid4(),
            "tool_name": "ask_user",
            "tool_arguments": arguments,
        },
    ]

    captured_history = {}

    async def fake_resume_agent(name, history, instruction, memory_objects=None):
        captured_history["messages"] = list(history)
        state = _state_with(
            [(m["role"], m["content"]) for m in prior], [("user", "PubMed"), ("assistant", "Searching PubMed.")]
        )
        return AgentResponse(
            status="completed", state=state, result=Message(role="assistant", content="Searching PubMed.")
        )

    monkeypatch.setattr(invoke_agent_router, "resume_agent", fake_resume_agent)
    monkeypatch.setattr(
        invoke_agent_router.db, "get_or_create_conversation", lambda pid, stage, mode: _conversation(conversation_id)
    )
    monkeypatch.setattr(invoke_agent_router.db, "list_messages", lambda cid: prior)
    monkeypatch.setattr(invoke_agent_router.db, "get_conversation", lambda pid, stage: None)
    monkeypatch.setattr(invoke_agent_router.db, "add_messages", lambda cid, messages: None)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/invoke-agent",
            json={"stage": "scoping", "project_id": str(project_id), "message": "PubMed"},
        )

    assert response.status_code == 200
    replayed = captured_history["messages"][-1]
    assert replayed.tool_call == ToolCall(
        id=str(prior[1]["tool_call_id"]), name="ask_user", arguments=arguments
    )
    # The LLM still sees the call, rendered into the turn's text alongside the thinking.
    assert replayed.to_dict()["content"] == (
        f"I need the databases first.\nCalled tool `ask_user` with arguments {arguments}"
    )
