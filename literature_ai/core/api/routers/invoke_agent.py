from typing import Optional

from fastapi import APIRouter, HTTPException

from literature_ai.core.agent.agent.agent_types import spawn_chatbot_agent
from literature_ai.core.agent.llm.messages import Messages
from literature_ai.core.agent.memory import MemoryObject, PaperMemoryObject, PaperRecord
from literature_ai.core.api.models import InvokeAgentRequest, InvokeAgentResponse, PaperList

router = APIRouter(prefix="/invoke-agent", tags=["agent"])


def _build_memory(paper_lists: Optional[list[PaperList]]) -> dict[str, MemoryObject]:
    """
    Builds a single `PaperMemoryObject` spanning every paper across the
    request's paper lists, keyed by paper id. Only `title`/`abstract` are
    carried into memory - the rest of each paper's metadata already lives in
    the request/DB and isn't what `retrieve_findings` is for.
    """
    papers_memory = PaperMemoryObject(id="papers")
    for paper_list in paper_lists or []:
        for paper in paper_list.papers:
            papers_memory.papers[paper.paperId] = PaperRecord(
                title=paper.title,
                abstract=paper.abstract,
            )

    if not papers_memory.papers:
        return {}
    return {papers_memory.id: papers_memory}


@router.post("", response_model=InvokeAgentResponse)
async def invoke_agent(request: InvokeAgentRequest) -> InvokeAgentResponse:
    """
    Stateless chatbot-agent entrypoint.

    Loads the full message history supplied by the caller into a `Messages`
    object and hands it to `spawn_chatbot_agent`, along with a memory store
    built from `paper_lists` so the agent can look up paper findings on
    demand via the `retrieve_findings` tool.
    """
    context = Messages([m.model_dump() for m in request.messages])
    memory = _build_memory(request.paper_lists)

    try:
        result = await spawn_chatbot_agent(context=context, memory=memory)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return InvokeAgentResponse(response=result)
