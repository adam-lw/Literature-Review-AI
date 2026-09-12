from fastapi import APIRouter
from langfuse import observe

from literature_ai.agent_service.agent.llm.core import Messages, get_llm
from literature_ai.agent_service.api.models import CallLlmRequest, CallLlmResponse

router = APIRouter(prefix="/call-llm", tags=["agent"])


@router.post("", response_model=CallLlmResponse)
@observe(name="call_llm")
async def call_llm_endpoint(request: CallLlmRequest) -> CallLlmResponse:
    """Calls the named model with a single user message and returns its text output."""
    llm = get_llm(request.model)
    messages = Messages()
    messages.add_user(request.text)
    response = await llm.call(messages)
    return CallLlmResponse(output=response.content or "")
