"""Pydantic request/response models for the app-layer (projects) API."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectCreateRequest(BaseModel):
    queries: list[str] = Field(..., min_length=1)
    embedding_run_id: int = Field(..., gt=0)
    inclusion_criteria: Optional[str] = None
    n_results: int = Field(10, ge=1, le=100)


class AgentProjectCreateRequest(BaseModel):
    description: str = Field(..., min_length=1)
    inclusion_criteria: Optional[str] = None
    project_title: Optional[str] = None


class ProjectUpdateRequest(BaseModel):
    project_title: Optional[str] = None
    description: Optional[str] = None
    inclusion_criteria: Optional[str] = None
    embedding_run_id: Optional[int] = Field(None, gt=0)


class SearchCreateRequest(BaseModel):
    query: str = Field(..., min_length=1)
    n_results: int = Field(10, ge=1, le=100)


class InclusionUpdateRequest(BaseModel):
    included: bool


class InclusionBulkItem(BaseModel):
    result_id: UUID
    included: bool


class InclusionBulkRequest(BaseModel):
    items: list[InclusionBulkItem]


class ResultOut(BaseModel):
    result_id: UUID
    search_id: UUID
    paper_id: str
    type: str
    search_rank: int
    distance: Optional[float] = None
    distance_type: Optional[str] = None
    title: Optional[str] = None
    abstract: Optional[str] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    citation_count: Optional[int] = None
    url: Optional[str] = None
    doi: Optional[str] = None
    included: bool


class SearchOut(BaseModel):
    search_id: UUID
    project_id: UUID
    query: str
    n_results: int
    created_at: datetime
    results: list[ResultOut] = []


class ProjectOut(BaseModel):
    project_id: UUID
    project_title: str
    description: Optional[str] = None
    inclusion_criteria: Optional[str] = None
    embedding_run_id: Optional[int] = None
    project_mode: str
    created_at: datetime
    updated_at: datetime
    searches: list[SearchOut] = []


class ProjectSummaryOut(BaseModel):
    project_id: UUID
    project_title: str
    description: Optional[str] = None
    inclusion_criteria: Optional[str] = None
    embedding_run_id: Optional[int] = None
    project_mode: str
    created_at: datetime
    updated_at: datetime
    search_count: int
    paper_count: int
    included_count: int


class ProjectListResponse(BaseModel):
    projects: list[ProjectSummaryOut]


class ConversationOut(BaseModel):
    conversation_id: UUID
    project_id: UUID
    stage: str
    mode: str
    completed: bool
    author: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    role: str
    content: str
    # Set when this turn made a tool call (see app.tool_calls): `content` is then the agent's
    # thinking, not chat text, and the client renders the call itself - an `ask_user` question
    # becomes a question card rather than a printed turn.
    tool_name: Optional[str] = None
    tool_arguments: Optional[dict] = None
    created_at: datetime


class ConversationWithMessagesOut(BaseModel):
    conversation: Optional[ConversationOut] = None
    messages: list[MessageOut] = []


class ProjectConversationsResponse(BaseModel):
    scoping: ConversationWithMessagesOut
    review: ConversationWithMessagesOut
    writing: ConversationWithMessagesOut


class ConversationUpdateRequest(BaseModel):
    completed: bool


class MessageCreateRequest(BaseModel):
    role: str
    content: str
    tool_name: Optional[str] = None
    tool_arguments: Optional[dict] = None


class MessagesCreateRequest(BaseModel):
    # Persists what one agent_service invoke-agent call produced - see
    # agent_service/api/models.py's InvokeAgentResponse.new_messages, which this shape mirrors.
    messages: list[MessageCreateRequest] = Field(..., min_length=1)


class ScopeUpdateRequest(BaseModel):
    content: dict


class ReviewInput(BaseModel):
    paper_id: str
    reviewed: bool = False
    included: bool = False
    inclusion_reasoning: dict[str, dict] = Field(default_factory=dict)


class ReviewsSetRequest(BaseModel):
    # The complete current set of verdicts (not a diff) - see persistence_handling.set_reviews.
    reviews: list[ReviewInput]


class ScopeOut(BaseModel):
    content: dict
    created_at: datetime
    updated_at: datetime


class WrittenPaperOut(BaseModel):
    written_paper_id: UUID
    project_id: UUID
    agent_version: Optional[str] = None
    content: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class WrittenPaperCreateRequest(BaseModel):
    content: str
    agent_version: Optional[str] = None


class HealthResponse(BaseModel):
    ok: bool
