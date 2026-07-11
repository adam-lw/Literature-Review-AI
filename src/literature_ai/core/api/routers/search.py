from fastapi import APIRouter, HTTPException

from literature_ai.core.api.models import SearchRequest, SearchResponse, SearchResult
from literature_ai.core.search.vector_search import vector_search

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    try:
        raw = vector_search(query=request.query, run_id=request.run_id, n_results=request.n_results)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SearchResponse(
        query=request.query,
        run_id=request.run_id,
        n_results=request.n_results,
        results=[SearchResult(**r) for r in raw],
    )
