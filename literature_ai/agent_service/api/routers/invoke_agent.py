from typing import Optional

from fastapi import APIRouter, HTTPException
from langfuse import observe, propagate_attributes

from literature_ai.agent_service.agent.agent.core.response import (
    AgentResponse,
    Question,
)
from literature_ai.agent_service.agent.agent.spawn_agent import (
    resume_agent,
    spawn_agent,
)
from literature_ai.agent_service.agent.llm.core import Messages
from literature_ai.agent_service.agent.memory import (
    MemoryObject,
    PaperMemoryObject,
    PaperRecord,
    ScopingMemoryObject,
)
from literature_ai.agent_service.api.models import (
    AgentQuestion,
    ChatMessage,
    CreateAgentRequest,
    InvokeAgentRequest,
    InvokeAgentResponse,
    MemoryInput,
    PaperListMemoryInput,
    ScopingMemoryInput,
)

router = APIRouter(prefix="/invoke-agent", tags=["agent"])


def _build_memory(memory_inputs: Optional[list[MemoryInput]]) -> dict[str, MemoryObject]:
    """
    Converts a request's generic `memory` inputs into the `dict[str,
    MemoryObject]` shape `spawn_agent`/`resume_agent` load onto the agent.
    Dispatches on each input's `type` discriminator to the matching
    `MemoryObject` subclass - add a case here (and a variant on `MemoryInput`
    in `api/models.py`) for each new memory type a request should be able to
    seed.

    All `paper_list` inputs merge into a single `PaperMemoryObject` keyed
    "papers", keyed by paper id, matching what `retrieve_paper` (and
    `ReactAgent`'s type-based memory lookup, which uses the first object of a
    matching type it finds) expects. Only `title`/`abstract` are carried into
    memory - the rest of each paper's metadata already lives in the
    request/DB and isn't what `retrieve_paper` is for.
    """
    memory: dict[str, MemoryObject] = {}
    papers_memory: Optional[PaperMemoryObject] = None

    for item in memory_inputs or []:
        if isinstance(item, PaperListMemoryInput):
            if papers_memory is None:
                papers_memory = PaperMemoryObject(id="papers")
                memory[papers_memory.id] = papers_memory
            for paper in item.papers:
                papers_memory.papers[paper.paperId] = PaperRecord(
                    title=paper.title,
                    abstract=paper.abstract,
                )
        elif isinstance(item, ScopingMemoryInput):
            memory["scoping"] = ScopingMemoryObject(
                id="scoping", specification=item.specification
            )

    if papers_memory is not None and not papers_memory.papers:
        del memory[papers_memory.id]

    return memory


def _to_response(agent_response: AgentResponse) -> InvokeAgentResponse:
    """
    Shapes an `AgentResponse` into the HTTP response both endpoints share.

    `messages` always carries the full react context back to the caller -
    it's what they must resend as `InvokeAgentRequest.messages` (plus their
    next message) to continue the conversation, since this endpoint keeps no
    server-side memory between calls.
    """
    messages = [
        ChatMessage(role=m.role, content=m.content) for m in agent_response.state
    ]

    if isinstance(agent_response.result, Question):
        return InvokeAgentResponse(
            status=agent_response.status,
            question=AgentQuestion(
                question=agent_response.result.question,
                description=agent_response.result.description,
                options=agent_response.result.options,
                allows_freetext=agent_response.result.allows_freetext,
            ),
            messages=messages,
            reasoning=agent_response.reasoning,
        )

    return InvokeAgentResponse(
        status=agent_response.status,
        response=agent_response.result.content,
        messages=messages,
        reasoning=agent_response.reasoning,
    )


@router.post("/create", response_model=InvokeAgentResponse)
@observe(name="create_agent")
async def create_agent(request: CreateAgentRequest) -> InvokeAgentResponse:
    """
    Starts a new agent conversation, dispatching by `request.stage`.

    """
    with propagate_attributes(session_id=request.session_id, tags=[request.stage]):
        memory = _build_memory(request.memory)

        try:
            agent_response = await spawn_agent(
                name=request.stage, instruction=request.content, memory_objects=memory
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _to_response(agent_response)


@router.post("", response_model=InvokeAgentResponse)
@observe(name="invoke_agent")
async def invoke_agent(request: InvokeAgentRequest) -> InvokeAgentResponse:
    """
    Continues an agent conversation started by `create_agent`.

    `request.messages` is the previous response's full context plus the
    caller's new turn appended (see `useAgentConversation.send`) - split back
    into the prior `history` and the new `instruction` for `resume_agent`.
    """
    with propagate_attributes(session_id=request.session_id, tags=[request.stage]):
        history = Messages([m.model_dump() for m in request.messages[:-1]])
        instruction = request.messages[-1].content
        memory = _build_memory(request.memory)

        try:
            agent_response = await resume_agent(
                name=request.stage,
                history=history,
                instruction=instruction,
                memory_objects=memory,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _to_response(agent_response)
