from fastapi import APIRouter
from langfuse import observe

from literature_ai.agent_service.api.models import (
    GenerateScopeDescriptionRequest,
    GenerateScopeDescriptionResponse,
)
from literature_ai.agent_service.utils.generate_scope_title import generate_scope_title
from literature_ai.agent_service.utils.generate_scope_description import (
    generate_scope_description as generate_scope_description_text,
)

router = APIRouter(prefix="/generate-scope-description", tags=["agent"])


@router.post("", response_model=GenerateScopeDescriptionResponse)
@observe(name="generate_scope_description")
async def generate_scope_description_endpoint(
    request: GenerateScopeDescriptionRequest,
) -> GenerateScopeDescriptionResponse:
    """Generates a title and description for a finalized scope specification, distinct from the
    project's own project_title/description."""
    scope_title = await generate_scope_title(request.specification)
    scope_description = await generate_scope_description_text(request.specification)
    return GenerateScopeDescriptionResponse(scope_title=scope_title, scope_description=scope_description)
