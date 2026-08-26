from __future__ import annotations

from typing import Literal, Optional

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


class PaperList(BaseModel):
    name: str
    papers: list[PaperMetadata]


class CreateAgentRequest(BaseModel):
    stage: str
    content: str
    paper_lists: Optional[list[PaperList]] = None
    session_id: Optional[str] = None


class InvokeAgentRequest(BaseModel):
    stage: str
    messages: list[ChatMessage] = Field(..., min_length=1)
    paper_lists: Optional[list[PaperList]] = None
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
