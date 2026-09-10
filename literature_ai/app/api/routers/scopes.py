from typing import Optional

from fastapi import APIRouter

from literature_ai.app import persistence_handling as db
from literature_ai.app.api import models

router = APIRouter(prefix="/scopes", tags=["scopes"])


@router.get("", response_model=models.ScopeListResponse)
def list_scopes(search: Optional[str] = None, limit: int = 10) -> models.ScopeListResponse:
    scopes = [models.ScopeSummaryOut(**s) for s in db.list_recent_scopes(search, limit)]
    return models.ScopeListResponse(scopes=scopes)
