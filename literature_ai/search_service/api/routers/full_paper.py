from fastapi import APIRouter, HTTPException

from literature_ai.search_service.api.models import (
    FullPaperResponse,
    PaperSectionHeader,
    PaperSectionResponse,
    PaperSectionsResponse,
)
from literature_ai.search_service.full_paper.service import (
    GrobidParseError,
    GrobidUnavailableError,
    PaperNotFoundError,
    PdfDownloadError,
    get_or_create_full_paper,
)
from literature_ai.search_service.processing.pdf_parsing import extract_sections

router = APIRouter(prefix="/full-paper", tags=["full-paper"])


@router.get("/{paper_id}", response_model=FullPaperResponse)
def get_full_paper(paper_id: str, include_tei_xml: bool = False) -> FullPaperResponse:
    try:
        result = get_or_create_full_paper(paper_id)
    except PaperNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PdfDownloadError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except GrobidParseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except GrobidUnavailableError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc

    return FullPaperResponse(
        paperId=result.paperId,
        status=result.status,
        pdf_url=result.pdf_url,
        full_text=result.full_text,
        tei_xml=result.tei_xml if include_tei_xml else None,
        grobid_version=result.grobid_version,
        parsed_at=result.parsed_at,
    )


def _get_sections(paper_id: str):
    try:
        result = get_or_create_full_paper(paper_id)
    except PaperNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PdfDownloadError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except GrobidParseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except GrobidUnavailableError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc

    if result.tei_xml is None:
        raise HTTPException(
            status_code=404,
            detail=f"No full text available for paperId={paper_id!r} (status={result.status!r})",
        )
    return extract_sections(result.tei_xml)


@router.get("/{paper_id}/sections", response_model=PaperSectionsResponse)
def list_paper_sections(paper_id: str) -> PaperSectionsResponse:
    """List a paper's actual section headers, in document order.

    Papers do not share a standard set of section headers - GROBID extracts each
    header exactly as printed in the paper's own PDF. Use a returned `index` with
    `get_paper_section` to retrieve that section's text.
    """
    sections = _get_sections(paper_id)
    return PaperSectionsResponse(
        paperId=paper_id,
        sections=[
            PaperSectionHeader(index=s["index"], header=s["header"]) for s in sections if s["header"]
        ],
    )


@router.get("/{paper_id}/sections/{index}", response_model=PaperSectionResponse)
def get_paper_section(paper_id: str, index: int) -> PaperSectionResponse:
    """Retrieve one section's text by its index, as returned by `list_paper_sections`."""
    sections = _get_sections(paper_id)
    section = next((s for s in sections if s["index"] == index), None)
    if section is None:
        raise HTTPException(
            status_code=404,
            detail=f"No section at index={index} for paperId={paper_id!r}",
        )
    return PaperSectionResponse(
        paperId=paper_id,
        index=section["index"],
        header=section["header"],
        section_text="\n\n".join(section["paragraphs"]),
    )
