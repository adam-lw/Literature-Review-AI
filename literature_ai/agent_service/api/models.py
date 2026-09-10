from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str


class PaperMetadata(BaseModel):
    paperId: str
    title: Optional[str] = None
    abstract: Optional[str] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    citationCount: Optional[int] = None
    url: Optional[str] = None
    DOI: Optional[str] = None


# Each request-side memory input carries a `type` discriminator naming which
# `MemoryObject` subclass it loads into (see `agent/memory/`). Adding a new
# memory type an agent can be given up front means adding a variant here and
# a matching case in `routers/invoke_agent.py`'s `_build_memory` - nowhere
# else, since `spawn_agent`/`resume_agent`/`ReactAgent`/the tool layer already
# consume `dict[str, MemoryObject]` generically.
class PaperListMemoryInput(BaseModel):
    type: Literal["paper_list"] = "paper_list"
    name: str
    papers: list[PaperMetadata]


class ScopingMemoryInput(BaseModel):
    type: Literal["scoping"] = "scoping"
    specification: dict[str, Any]


MemoryInput = Annotated[
    Union[PaperListMemoryInput, ScopingMemoryInput], Field(discriminator="type")
]


class CreateAgentRequest(BaseModel):
    stage: str
    content: str
    memory: Optional[list[MemoryInput]] = None
    session_id: Optional[str] = None


class InvokeAgentRequest(BaseModel):
    stage: str
    # Persisted 3-phase flow (scoping/scoping_chat/search_review/review_chat/writing/
    # writing_chat, collapsed onto app.conversations' 3-value stage enum - see
    # routers/invoke_agent.py's _STAGE_GROUP): pass `project_id` + `message` only. Conversation
    # history, scope, and review state are all loaded from and written to Postgres
    # server-side - the caller never resends history or memory on this path, and `messages`/
    # `memory` below are ignored if also set.
    project_id: Optional[UUID] = None
    message: Optional[str] = None
    # Legacy fully-stateless contract, still used by `chatbot`/`orchestrator` only (they sit
    # outside the persisted 3-phase flow): pass `messages` (the previous response's full
    # context, including its leading system-role entry, plus the caller's new turn appended)
    # and, optionally, `memory`.
    messages: Optional[list[ChatMessage]] = None
    memory: Optional[list[MemoryInput]] = None
    session_id: Optional[str] = None


class AgentQuestion(BaseModel):
    question: str
    description: str = ""
    options: dict[str, str] = Field(default_factory=dict)
    allows_freetext: bool = True


class NewMessage(BaseModel):
    """One turn this call produced, for the caller to persist (POST
    /projects/{project_id}/conversations/{stage}/messages) - the agent service itself never
    writes conversation content to Postgres. `tool_name`/`tool_arguments` are set when this turn
    was a tool call rather than chat text - see app.tool_calls."""

    role: str
    content: str
    tool_name: Optional[str] = None
    tool_arguments: Optional[dict[str, Any]] = None


class ReviewUpdate(BaseModel):
    """One paper's current verdict, for the caller to persist (PUT
    /projects/{project_id}/reviews) - mirrors AgentPaperReviewMemory.PaperReview."""

    paper_id: str
    reviewed: bool
    included: bool
    inclusion_reasoning: dict[str, dict[str, Any]]


class InvokeAgentResponse(BaseModel):
    status: Literal["completed", "awaiting_input", "error"]
    response: Optional[str] = None
    question: Optional[AgentQuestion] = None
    messages: list[ChatMessage]
    reasoning: Optional[str] = None
    # Persisted 3-phase flow only - what this call changed, for the caller to write to Postgres
    # itself (see routers/projects.py). Always empty/None on the legacy chatbot/orchestrator
    # contract, which persists nothing server-side at all.
    conversation_id: Optional[UUID] = None
    new_messages: list[NewMessage] = Field(default_factory=list)
    scope: Optional[dict[str, Any]] = None
    reviews: Optional[list[ReviewUpdate]] = None


class GenerateTitleRequest(BaseModel):
    user_input: str


class GenerateTitleResponse(BaseModel):
    title: str
