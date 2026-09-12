from fastapi import APIRouter
from langfuse import observe

from literature_ai.review_service.api.models import (
    GenerateReviewRequest,
    GenerateReviewResponse,
)
from literature_ai.review_service.review.generate_review import generate_review

router = APIRouter(prefix="/generate-review", tags=["review"])


@router.post("", response_model=GenerateReviewResponse)
@observe(name="generate_review")
async def generate_review_endpoint(request: GenerateReviewRequest) -> GenerateReviewResponse:
    """Kicks off the review graph for a finalized scoping specification."""
    result = await generate_review(
        request.specification, request.embedding_run_id, request.results_per_term
    )
    return GenerateReviewResponse(**result)
