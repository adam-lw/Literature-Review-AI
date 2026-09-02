from fastapi import APIRouter, HTTPException

from literature_ai.search_service.api.models import (
    RagChunkRequest,
    RagChunkResponse,
    RagChunkResult,
)
from literature_ai.search_service.full_paper.service import (
    GrobidParseError,
    GrobidUnavailableError,
    PaperNotFoundError,
    PdfDownloadError,
)
from literature_ai.search_service.search.chunk_search import rag_paper_chunks

router = APIRouter(prefix="/rag-paper-chunks", tags=["rag-paper-chunks"])


@router.post("", response_model=RagChunkResponse)
def rag_paper_chunks_endpoint(request: RagChunkRequest) -> RagChunkResponse:
    try:
        result = rag_paper_chunks(
            paper_ids=request.paper_ids,
            query=request.query,
            embedding_model=request.embedding_model,
            n_results=request.n_results,
        )
    except PaperNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PdfDownloadError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except GrobidParseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except GrobidUnavailableError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except NotImplementedError as exc:
        # e.g. an embedding_model whose embed_text() isn't supported (specter_v1/v2).
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return RagChunkResponse(
        query=request.query,
        run_id=result["run_id"],
        n_results=request.n_results,
        results=[RagChunkResult(**r) for r in result["results"]],
    )
