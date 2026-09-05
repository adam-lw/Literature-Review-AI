from fastapi import APIRouter, HTTPException

from literature_ai.search_service.api.models import (
    FullPaperResponse,
    PaperSectionHeader,
    PaperSectionResponse,
    PaperSectionsResponse,
)
from literature_ai.search_service.data_collect.collect_full_papers import (
    PaperNotFoundError,
    get_or_create_full_paper,
)
from literature_ai.search_service.processing.pdf_parsing import (
    GrobidParseError,
    GrobidUnavailableError,
)
from literature_ai.search_service.retrieval.paper import get_section_headers
from literature_ai.search_service.retrieval.text import get_section_content

router = APIRouter(prefix="/full-paper", tags=["full-paper"])


def _get_or_create(paper_id: str) -> dict:
    try:
        return get_or_create_full_paper(paper_id)
    except PaperNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GrobidParseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except GrobidUnavailableError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc


@router.get("/{paper_id}", response_model=FullPaperResponse)
def get_full_paper(paper_id: str, include_tei_xml: bool = False) -> FullPaperResponse:
    result = _get_or_create(paper_id)
    return FullPaperResponse(
        paperId=result["paperId"],
        status=result["status"],
        pdf_url=result["pdf_url"],
        full_text=result["full_text"],
        tei_xml=result["tei_xml"] if include_tei_xml else None,
        grobid_version=result["grobid_version"],
        parsed_at=result["parsed_at"],
    )


@router.get("/{paper_id}/sections", response_model=PaperSectionsResponse)
def list_paper_sections(paper_id: str) -> PaperSectionsResponse:
    """List a paper's actual section headers, in document order.

    Papers do not share a standard set of section headers - GROBID extracts each
    header exactly as printed in the paper's own PDF. Use a returned `index` with
    `get_paper_section` to retrieve that section's text.
    """
    result = _get_or_create(paper_id)
    if result["status"] != "success":
        raise HTTPException(
            status_code=404,
            detail=f"No full text available for paperId={paper_id!r} (status={result['status']!r})",
        )
    headers = get_section_headers(paper_id)
    return PaperSectionsResponse(
        paperId=paper_id,
        sections=[
            PaperSectionHeader(index=h["section_index"], header=h["section_header"])
            for h in headers
            if h["section_header"]
        ],
    )


@router.get("/{paper_id}/sections/{index}", response_model=PaperSectionResponse)
def get_paper_section(paper_id: str, index: int) -> PaperSectionResponse:
    """Retrieve one section's text by its index, as returned by `list_paper_sections`."""
    result = _get_or_create(paper_id)
    if result["status"] != "success":
        raise HTTPException(
            status_code=404,
            detail=f"No full text available for paperId={paper_id!r} (status={result['status']!r})",
        )

    headers = get_section_headers(paper_id)
    header = next((h["section_header"] for h in headers if h["section_index"] == index), None)
    if header is None:
        raise HTTPException(
            status_code=404,
            detail=f"No section at index={index} for paperId={paper_id!r}",
        )

    section_text = get_section_content(paper_id, header)
    return PaperSectionResponse(
        paperId=paper_id,
        index=index,
        header=header,
        section_text=section_text or "",
    )
