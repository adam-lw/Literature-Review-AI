from fastapi import APIRouter

from literature_ai.search_service.api.models import (
    RagChunkRequest,
    RagChunkResponse,
    RagChunkResult,
)
from literature_ai.search_service.search.chunk_search import rag_paper_chunks

router = APIRouter(prefix="/rag-paper-chunks", tags=["rag-paper-chunks"])


@router.post("", response_model=RagChunkResponse)
def rag_paper_chunks_endpoint(request: RagChunkRequest) -> RagChunkResponse:
    result = rag_paper_chunks(
        paper_ids=request.paper_ids,
        query=request.query,
        n_results=request.n_results,
    )

    return RagChunkResponse(
        query=request.query,
        n_results=request.n_results,
        results=[RagChunkResult(**r) for r in result["results"]],
    )
