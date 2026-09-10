from typing import Optional

from fastapi import APIRouter, HTTPException

from literature_ai.app import persistence_handling as db
from literature_ai.app.api import models
from literature_ai.search_service.search.vector_search import vector_search

router = APIRouter(prefix="/projects", tags=["projects"])
results_router = APIRouter(prefix="/results", tags=["projects"])


def _try_get_project(project_id: str) -> dict:
    project = db.get_project(project_id)
    if project is None:
        raise HTTPException(
            status_code=404, detail=f"No project found for project_id={project_id!r}"
        )
    return project


@router.get("", response_model=models.ProjectListResponse)
def list_projects() -> models.ProjectListResponse:
    projects = [models.ProjectSummaryOut(**p) for p in db.list_projects()]
    return models.ProjectListResponse(projects=projects)


@router.post("", response_model=models.ProjectOut)
def create_project(request: models.ProjectCreateRequest) -> models.ProjectOut:
    try:
        project = db.create_project(
            queries=request.queries,
            embedding_run_id=request.embedding_run_id,
            inclusion_criteria=request.inclusion_criteria,
            n_results=request.n_results,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return models.ProjectOut(**project)


@router.post("/agent-mode", response_model=models.ProjectOut)
def create_agent_project(request: models.AgentProjectCreateRequest) -> models.ProjectOut:
    project = db.create_agent_project(
        description=request.description,
        inclusion_criteria=request.inclusion_criteria,
        project_title=request.project_title,
    )
    return models.ProjectOut(**project)


@router.get("/{project_id}", response_model=models.ProjectOut)
def get_project(project_id: str) -> models.ProjectOut:
    return models.ProjectOut(**_try_get_project(project_id))


@router.patch("/{project_id}", response_model=models.ProjectOut)
def update_project(
    project_id: str, request: models.ProjectUpdateRequest
) -> models.ProjectOut:
    _try_get_project(project_id)
    project = db.update_project(project_id, **request.model_dump(exclude_unset=True))
    assert project is not None
    return models.ProjectOut(**project)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str) -> None:
    db.delete_project(project_id)


@router.post("/{project_id}/searches", response_model=models.SearchOut)
def add_search(
    project_id: str, request: models.SearchCreateRequest
) -> models.SearchOut:
    project = _try_get_project(project_id)
    if project["embedding_run_id"] is None:
        raise HTTPException(
            status_code=422,
            detail=f"Project {project_id!r} has no embedding_run_id set",
        )

    query = request.query.strip()
    search = db.create_search(project_id, query, request.n_results)
    try:
        results = vector_search(
            query=query,
            run_id=project["embedding_run_id"],
            n_results=request.n_results,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.save_search_results(str(search["search_id"]), results)

    group = db.get_search(str(search["search_id"]))
    assert group is not None
    return models.SearchOut(**group)


@router.delete("/{project_id}/searches/{search_id}", status_code=204)
def delete_search(project_id: str, search_id: str) -> None:
    db.delete_search(project_id, search_id)


@router.patch("/{project_id}/inclusion")
def set_inclusion_bulk(project_id: str, request: models.InclusionBulkRequest) -> dict:
    _try_get_project(project_id)
    count = db.set_inclusion_bulk(project_id, [item.model_dump() for item in request.items])
    return {"updated": count}


@results_router.patch("/{result_id}/inclusion")
def set_inclusion(result_id: str, request: models.InclusionUpdateRequest) -> dict:
    db.set_inclusion(result_id, request.included)
    return {"result_id": result_id, "included": request.included}


def _conversation_with_messages(project_id: str, stage: str) -> models.ConversationWithMessagesOut:
    conversation = db.get_conversation(project_id, stage)
    if conversation is None:
        return models.ConversationWithMessagesOut()
    messages = db.list_messages(str(conversation["conversation_id"]))
    return models.ConversationWithMessagesOut(
        conversation=models.ConversationOut(**conversation),
        messages=[models.MessageOut(**m) for m in messages],
    )


@router.get("/{project_id}/conversations", response_model=models.ProjectConversationsResponse)
def get_project_conversations(project_id: str) -> models.ProjectConversationsResponse:
    _try_get_project(project_id)
    return models.ProjectConversationsResponse(
        scoping=_conversation_with_messages(project_id, "scoping"),
        review=_conversation_with_messages(project_id, "review"),
        writing=_conversation_with_messages(project_id, "writing"),
    )


@router.patch("/{project_id}/conversations/{stage}", response_model=models.ConversationOut)
def update_conversation(
    project_id: str, stage: str, request: models.ConversationUpdateRequest
) -> models.ConversationOut:
    """Marks a stage's conversation completed (or not) - the "Continue" button in the phase-flow
    UI calls this when advancing past a phase, so `phaseIndex`/`phaseStarted` can be reconstructed
    on reload from which conversations are completed rather than needing their own client-side
    persistence."""
    _try_get_project(project_id)
    conversation = db.get_conversation(project_id, stage)
    if conversation is None:
        raise HTTPException(
            status_code=404, detail=f"No {stage!r} conversation found for project_id={project_id!r}"
        )
    db.set_conversation_completed(str(conversation["conversation_id"]), request.completed)
    updated = db.get_conversation(project_id, stage)
    assert updated is not None
    return models.ConversationOut(**updated)


@router.post(
    "/{project_id}/conversations/{stage}/messages",
    response_model=models.ConversationWithMessagesOut,
)
def add_conversation_messages(
    project_id: str, stage: str, request: models.MessagesCreateRequest
) -> models.ConversationWithMessagesOut:
    """Appends turns an agent_service invoke-agent call produced (see that service's
    `InvokeAgentResponse.new_messages`) to a stage's conversation - the agent service itself
    writes no conversation content to Postgres, so this is how the caller persists what it got
    back, right after it gets it. Creates the conversation if this is its very first turn."""
    _try_get_project(project_id)
    conversation = db.get_or_create_conversation(project_id, stage, "agent")
    db.add_messages(
        str(conversation["conversation_id"]), [m.model_dump() for m in request.messages]
    )
    return _conversation_with_messages(project_id, stage)


@router.get("/{project_id}/scope", response_model=Optional[models.ScopeOut])
def get_project_scope(project_id: str) -> models.ScopeOut | None:
    _try_get_project(project_id)
    conversation = db.get_conversation(project_id, "scoping")
    if conversation is None:
        return None
    scope = db.get_scope(str(conversation["conversation_id"]))
    return models.ScopeOut(**scope) if scope is not None else None


@router.put("/{project_id}/scope", response_model=models.ScopeOut)
def set_project_scope(project_id: str, request: models.ScopeUpdateRequest) -> models.ScopeOut:
    """Persists a scope specification an invoke-agent call handed back (`InvokeAgentResponse.
    scope`) - see the scoping phase's `_run_phase_agent` for when that's set. Creates the
    scoping conversation if it doesn't exist yet (finalizing a scope is always that
    conversation's first turn or later)."""
    _try_get_project(project_id)
    conversation = db.get_or_create_conversation(project_id, "scoping", "agent")
    scope = db.upsert_scope(str(conversation["conversation_id"]), request.content)
    return models.ScopeOut(**scope)


@router.put("/{project_id}/reviews")
def set_project_reviews(project_id: str, request: models.ReviewsSetRequest) -> dict:
    """Persists the review stage's current verdicts an invoke-agent call handed back
    (`InvokeAgentResponse.reviews`) - a wholesale replacement, not a diff, matching
    `set_reviews`."""
    _try_get_project(project_id)
    conversation = db.get_or_create_conversation(project_id, "review", "agent")
    reviews = {
        r.paper_id: {
            "reviewed": r.reviewed,
            "included": r.included,
            "inclusion_reasoning": r.inclusion_reasoning,
        }
        for r in request.reviews
    }
    db.set_reviews(str(conversation["conversation_id"]), reviews)
    return {"updated": len(reviews)}


@router.get("/{project_id}/written-papers", response_model=list[models.WrittenPaperOut])
def list_written_papers(project_id: str) -> list[models.WrittenPaperOut]:
    _try_get_project(project_id)
    return [models.WrittenPaperOut(**p) for p in db.list_written_papers(project_id)]


@router.post("/{project_id}/written-papers", response_model=models.WrittenPaperOut)
def create_written_paper(
    project_id: str, request: models.WrittenPaperCreateRequest
) -> models.WrittenPaperOut:
    _try_get_project(project_id)
    paper = db.create_written_paper(
        project_id, content=request.content, agent_version=request.agent_version
    )
    return models.WrittenPaperOut(**paper)
