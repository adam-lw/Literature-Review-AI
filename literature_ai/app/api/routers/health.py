from fastapi import APIRouter

from literature_ai.app.api.models import HealthResponse
from literature_ai.db import check_connection

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(ok=check_connection())
