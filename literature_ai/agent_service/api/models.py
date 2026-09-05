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
    messages: list[ChatMessage] = Field(..., min_length=1)
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


class GenerateTitleRequest(BaseModel):
    user_input: str


class GenerateTitleResponse(BaseModel):
    title: str
