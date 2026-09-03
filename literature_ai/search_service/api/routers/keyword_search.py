from fastapi import APIRouter

from literature_ai.search_service.api.models import (
    KeywordSearchRequest,
    KeywordSearchResponse,
    KeywordSearchResult,
)
from literature_ai.search_service.search.keyword_search import keyword_search

router = APIRouter(prefix="/keyword-search", tags=["search"])


@router.post("", response_model=KeywordSearchResponse)
def search(request: KeywordSearchRequest) -> KeywordSearchResponse:
    raw = keyword_search(query=request.query, n_results=request.n_results)
    return KeywordSearchResponse(
        query=request.query,
        n_results=request.n_results,
        results=[KeywordSearchResult(**r) for r in raw],
    )
