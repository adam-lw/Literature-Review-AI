from fastapi import APIRouter
from langfuse import observe

from literature_ai.agent_service.api.models import (
    GenerateTitleRequest,
    GenerateTitleResponse,
)
from literature_ai.agent_service.utils.generate_project_title import generate_title

router = APIRouter(prefix="/generate-title", tags=["agent"])


@router.post("", response_model=GenerateTitleResponse)
@observe(name="generate_title")
async def generate_title_endpoint(request: GenerateTitleRequest) -> GenerateTitleResponse:
    """Generates a working title for a new project from the user's initial input."""
    title = await generate_title(request.user_input)
    return GenerateTitleResponse(title=title)
