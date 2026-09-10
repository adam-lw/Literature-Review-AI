from typing import Optional
from uuid import UUID

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
    AgentPaperReviewMemory,
    CriterionReview,
    MemoryObject,
    PaperMemoryObject,
    PaperRecord,
    PaperReview,
    ScopingMemoryObject,
)
from literature_ai.agent_service.api.models import (
    AgentQuestion,
    ChatMessage,
    CreateAgentRequest,
    InvokeAgentRequest,
    InvokeAgentResponse,
    MemoryInput,
    NewMessage,
    PaperListMemoryInput,
    ReviewUpdate,
    ScopingMemoryInput,
)
from literature_ai.app import persistence_handling as db

router = APIRouter(prefix="/invoke-agent", tags=["agent"])

# Collapses the API-layer "<phase>"/"<phase>_chat" distinction onto app.conversations' 3-value
# stage enum - a phase-driving call (e.g. "search_review") and its companion chat call (e.g.
# "review_chat") for the same project log into the SAME conversation. `chatbot`/`orchestrator`
# aren't part of the 3-phase flow and are absent here - they stay on the legacy fully-stateless
# contract below, keyed off `request.messages` rather than `request.project_id`.
_STAGE_GROUP = {
    "scoping": "scoping",
    "scoping_chat": "scoping",
    "search_review": "review",
    "review_chat": "review",
    "writing": "writing",
    "writing_chat": "writing",
}


def _build_memory(memory_inputs: Optional[list[MemoryInput]]) -> dict[str, MemoryObject]:
    """
    Converts a request's generic `memory` inputs into the `dict[str,
    MemoryObject]` shape `spawn_agent`/`resume_agent` load onto the agent.
    Used only by the legacy chatbot/orchestrator path - the persisted 3-phase
    flow loads its memory straight from Postgres via `_load_memory_for_stage`
    instead of trusting a client-supplied payload.

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


async def _load_memory_for_stage(project_id: str, group: str) -> dict[str, MemoryObject]:
    """
    Loads memory for the persisted 3-phase flow straight from Postgres, replacing the old
    client-seeded `paper_list`/`scoping` payloads for this path. The main `scoping` agent itself
    needs no memory (it has zero tools per config/core/agent/settings/scoping.yaml, and finalizes
    by emitting raw JSON instead - see `_run_phase_agent`'s scope handling), but `scoping_chat`
    DOES have `retrieve_scope`/`update_scope` tools, so the 'scoping' group always gets a
    `ScopingMemoryObject` seeded too - empty (`{}`) before any scope exists yet, so `update_scope`
    has something to mutate into existence from the very first chat turn. `review`/`writing` only
    get one if a scope has actually been finalized, since they only ever read it, never create it.
    They also get the project's collected papers and current per-paper review state - the last of
    these is what first makes `retrieve_review`/`record_criterion_review`/`finalize_review`
    (previously never-instantiated, dead tools) actually persist across turns.
    """
    memory: dict[str, MemoryObject] = {}

    scoping_conv = db.get_conversation(project_id, "scoping")
    scope_row = db.get_scope(str(scoping_conv["conversation_id"])) if scoping_conv else None
    if scope_row or group == "scoping":
        memory["scoping"] = ScopingMemoryObject(
            id="scoping", specification=scope_row["content"] if scope_row else {}
        )

    if group not in ("review", "writing"):
        return memory

    review_conv = db.get_conversation(project_id, "review")
    reviews_by_paper: dict[str, dict] = {}
    if review_conv is not None:
        reviews_by_paper = {
            r["paper_id"]: r["content"] for r in db.list_reviews(str(review_conv["conversation_id"]))
        }

    project = db.get_project(project_id)
    papers = PaperMemoryObject(id="papers")
    if project is not None:
        for search in project["searches"]:
            for result in search["results"]:
                # `writing` only sees papers the review stage actually kept.
                if group == "writing" and not reviews_by_paper.get(result["paper_id"], {}).get(
                    "included", True
                ):
                    continue
                papers.add_paper(
                    result["paper_id"], title=result.get("title"), abstract=result.get("abstract")
                )
    if papers.papers:
        memory["papers"] = papers

    review_memory = AgentPaperReviewMemory(id="reviews")
    for paper_id, content in reviews_by_paper.items():
        review_memory.reviews[paper_id] = PaperReview(
            reviewed=content.get("reviewed", False),
            included=content.get("included", False),
            inclusion_reasoning={
                criterion: CriterionReview(passed=v.get("passed", False), reason=v.get("reason", ""))
                for criterion, v in content.get("inclusion_reasoning", {}).items()
            },
        )
    memory["reviews"] = review_memory

    return memory


async def _run_phase_agent(
    project_id: str, stage: str, message: str, session_id: Optional[str]
) -> InvokeAgentResponse:
    """
    Drives one turn of the persisted 3-phase flow: looks up (or lazily creates) the project's
    conversation for this stage's group, replays its persisted history through spawn_agent (if
    this is the conversation's first turn) or resume_agent (otherwise), and hands back exactly
    what this turn produced - the new messages, and where relevant the current scope or review
    verdicts - for the CALLER to persist (see routers/projects.py). The agent service writes no
    conversation content to Postgres itself; `get_or_create_conversation` below only bootstraps
    the conversation's identity row, which is needed to know what history to replay against, not
    to record anything this run produces.
    """
    group = _STAGE_GROUP.get(stage)
    if group is None:
        raise HTTPException(
            status_code=422, detail=f"stage {stage!r} is not part of the persisted 3-phase flow"
        )

    conversation = db.get_or_create_conversation(project_id, group, "agent")
    conversation_id = str(conversation["conversation_id"])
    prior = db.list_messages(conversation_id)
    memory = await _load_memory_for_stage(project_id, group)

    with propagate_attributes(session_id=session_id or f"{project_id}:{group}", tags=[stage]):
        if not prior:
            agent_response = await spawn_agent(name=stage, instruction=message, memory_objects=memory)
        else:
            history = Messages([{"role": m["role"], "content": m["content"]} for m in prior])
            agent_response = await resume_agent(
                name=stage, history=history, instruction=message, memory_objects=memory
            )

    # `agent_response.state` is [system, ...prior turns replayed..., new user turn, ...turns
    # produced this run]. Skip the system entry (never persisted, see app.messages' CHECK) and
    # the replayed prior turns (the caller already has those) - what's left is exactly what's new.
    new_turns = list(agent_response.state)[1 + len(prior) :]
    new_messages = [NewMessage(role=m.role, content=m.content) for m in new_turns]

    # A run that ends by asking the user something returns before any of that reasoning becomes
    # a normal reply, so its last turn above is just the flattened "Called tool `ask_user` with
    # arguments {...}" bookkeeping text `ReactAgent` puts in its own LLM-facing context.
    # `agent_response.result` already carries the same call structurally - it's the `Question`
    # this response returns below - so that turn is swapped for the structured shape instead of
    # leaving the raw text as something the caller would persist and later render as chat.
    if isinstance(agent_response.result, Question) and new_messages:
        question = agent_response.result
        # `ReactAgent` unconditionally persists a tool call's accompanying thinking as its own
        # plain turn immediately before the call's own turn (see react.py) - fold that turn's
        # text in as this one's content instead of leaving both, or the thinking ends up shown
        # twice. Structurally, a turn immediately preceding another turn from the *same*
        # assistant iteration is always `role == "assistant"` (`ReactAgent` always puts a
        # `role == "tool"` turn between any two turns from *different* iterations), so that
        # check alone is enough to tell them apart.
        thinking = ""
        if len(new_messages) >= 2 and new_messages[-2].role == "assistant":
            thinking = new_messages.pop(-2).content
        new_messages[-1] = NewMessage(
            role="assistant",
            content=thinking,
            tool_name="ask_user",
            tool_arguments={
                "question": question.question,
                "description": question.description,
                "options": question.options,
                "allows_freetext": question.allows_freetext,
            },
        )

    scope: Optional[dict] = None
    if group == "scoping":
        # Two ways a scope can change: the main `scoping` agent (no tools) finalizes by emitting
        # raw JSON as its last message - the caller already knows how to recognise that
        # convention (see frontend `tryParseScope`, which does the same check for the identical
        # case on reload) - or `scoping_chat`'s `update_scope` tool mutates the
        # `ScopingMemoryObject` loaded above in place. Only the latter needs help from here,
        # since a tool call never shows up in the response text the caller already has.
        scope_memory = memory.get("scoping")
        if isinstance(scope_memory, ScopingMemoryObject) and scope_memory.specification:
            scope = scope_memory.specification

    reviews: Optional[list[ReviewUpdate]] = None
    if group == "review":
        review_memory = memory.get("reviews")
        if isinstance(review_memory, AgentPaperReviewMemory):
            reviews = [
                ReviewUpdate(
                    paper_id=paper_id,
                    reviewed=review.reviewed,
                    included=review.included,
                    inclusion_reasoning={
                        criterion: {"passed": v.passed, "reason": v.reason}
                        for criterion, v in review.inclusion_reasoning.items()
                    },
                )
                for paper_id, review in review_memory.reviews.items()
            ]

    return _to_response(
        agent_response,
        include_messages=False,
        conversation_id=conversation["conversation_id"],
        new_messages=new_messages,
        scope=scope,
        reviews=reviews,
    )


def _to_response(
    agent_response: AgentResponse,
    *,
    include_messages: bool,
    conversation_id: Optional[UUID] = None,
    new_messages: Optional[list[NewMessage]] = None,
    scope: Optional[dict] = None,
    reviews: Optional[list[ReviewUpdate]] = None,
) -> InvokeAgentResponse:
    """
    Shapes an `AgentResponse` into the HTTP response both endpoints share.

    `include_messages` is True only for the legacy chatbot/orchestrator contract, where
    `messages` carries the full react context back to the caller for them to resend (plus their
    next message) on the next turn, since that path keeps no server-side memory between calls.
    `conversation_id`/`new_messages`/`scope`/`reviews` are set only by the persisted 3-phase
    flow - what `_run_phase_agent` needs the caller to write to Postgres itself; the legacy
    contract persists nothing server-side at all, so they stay at their None/empty defaults there.
    """
    messages = (
        [ChatMessage(role=m.role, content=m.content) for m in agent_response.state]
        if include_messages
        else []
    )
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
            conversation_id=conversation_id,
            new_messages=new_messages or [],
            scope=scope,
            reviews=reviews,
        )

    return InvokeAgentResponse(
        status=agent_response.status,
        response=agent_response.result.content,
        messages=messages,
        reasoning=agent_response.reasoning,
        conversation_id=conversation_id,
        new_messages=new_messages or [],
        scope=scope,
        reviews=reviews,
    )


@router.post("/create", response_model=InvokeAgentResponse)
@observe(name="create_agent")
async def create_agent(request: CreateAgentRequest) -> InvokeAgentResponse:
    """
    Starts a new conversation on the legacy fully-stateless contract - only used by
    `chatbot`/`orchestrator` now. The persisted 3-phase flow no longer calls this endpoint at
    all; `invoke_agent` below decides create-vs-resume itself from what's already in Postgres
    for a given `(project_id, stage)`.
    """
    with propagate_attributes(session_id=request.session_id, tags=[request.stage]):
        memory = _build_memory(request.memory)

        try:
            agent_response = await spawn_agent(
                name=request.stage, instruction=request.content, memory_objects=memory
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _to_response(agent_response, include_messages=True)


@router.post("", response_model=InvokeAgentResponse)
@observe(name="invoke_agent")
async def invoke_agent(request: InvokeAgentRequest) -> InvokeAgentResponse:
    """
    Drives one turn of an agent conversation.

    Two contracts, dispatched on whether `project_id` is set:
    - Persisted 3-phase flow (scoping/scoping_chat/search_review/review_chat/writing/
      writing_chat): pass `project_id` + `message` only. See `_run_phase_agent`.
    - Legacy chatbot/orchestrator: pass `messages` (the previous response's full context,
      including its leading system-role entry, plus the caller's new turn appended) exactly as
      before - unchanged from the caller's perspective.
    """
    if request.project_id is not None:
        if not request.message:
            raise HTTPException(
                status_code=422, detail="`message` is required when `project_id` is set"
            )
        return await _run_phase_agent(
            str(request.project_id), request.stage, request.message, request.session_id
        )

    if not request.messages:
        raise HTTPException(
            status_code=422, detail="`messages` is required when `project_id` is not set"
        )

    with propagate_attributes(session_id=request.session_id, tags=[request.stage]):
        # request.messages[0] is the system prompt `_to_response` echoed back on the previous
        # call - resume_agent rebuilds the system prompt fresh itself now (see spawn_agent.py),
        # so it's dropped here rather than passed through as a fake history turn.
        history = Messages([m.model_dump() for m in request.messages[1:-1]])
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

    return _to_response(agent_response, include_messages=True)
