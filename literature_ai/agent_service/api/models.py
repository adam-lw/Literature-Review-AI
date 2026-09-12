from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, Union

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


class PaperListMemoryInput(BaseModel):
    type: Literal["paper_list"] = "paper_list"
    name: str
    papers: list[PaperMetadata]


class ScopingMemoryInput(BaseModel):
    type: Literal["scoping"] = "scoping"
    specification: dict[str, Any]


class ReviewMemoryInput(BaseModel):
    type: Literal["review"] = "review"
    reviews: dict[str, dict[str, Any]]


MemoryInput = Annotated[
    Union[PaperListMemoryInput, ScopingMemoryInput, ReviewMemoryInput],
    Field(discriminator="type"),
]


class CreateAgentRequest(BaseModel):
    stage: str
    content: str
    memory: Optional[list[MemoryInput]] = None
    session_id: Optional[str] = None


class InvokeAgentRequest(BaseModel):
    stage: str
    messages: list[ChatMessage]
    memory: Optional[list[MemoryInput]] = None
    session_id: Optional[str] = None


class AgentQuestion(BaseModel):
    question: str
    description: str = ""
    options: dict[str, str] = Field(default_factory=dict)
    allows_freetext: bool = True


class InvokeAgentResponse(BaseModel):
    status: Literal["completed", "awaiting_input", "error"]
    response: Optional[str] = None
    question: Optional[AgentQuestion] = None
    messages: list[ChatMessage]
    reasoning: Optional[str] = None
    memory: list[MemoryInput] = Field(default_factory=list)


class GenerateTitleRequest(BaseModel):
    user_input: str


class GenerateTitleResponse(BaseModel):
    title: str


class GenerateScopeDescriptionRequest(BaseModel):
    specification: dict[str, Any]


class GenerateScopeDescriptionResponse(BaseModel):
    scope_title: str
    scope_description: str


class CallLlmRequest(BaseModel):
    model: str
    text: str


class CallLlmResponse(BaseModel):
    output: str
