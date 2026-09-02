from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    run_id: int = Field(..., gt=0)
    n_results: int = Field(10, ge=1, le=100)


class SearchResult(BaseModel):
    paperId: str
    title: Optional[str] = None
    abstract: Optional[str] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    citationCount: Optional[int] = None
    url: Optional[str] = None
    DOI: Optional[str] = None
    distance: float


class SearchResponse(BaseModel):
    query: str
    run_id: int
    n_results: int
    results: list[SearchResult]


class EmbeddingRun(BaseModel):
    run_id: int
    ran_at: datetime
    embedding_model: str
    embedding_version: Optional[str] = None
    n_dim: int
    user_tags: dict
    source: str


class EmbeddingModelsResponse(BaseModel):
    runs: list[EmbeddingRun]


class FullPaperResponse(BaseModel):
    paperId: str
    status: str
    pdf_url: Optional[str] = None
    full_text: Optional[str] = None
    tei_xml: Optional[str] = None
    grobid_version: Optional[str] = None
    parsed_at: datetime


class RagChunkRequest(BaseModel):
    paper_ids: list[str] = Field(..., min_length=1)
    query: str = Field(..., min_length=1)
    embedding_model: str = Field(..., min_length=1)
    n_results: int = Field(5, ge=1, le=100)


class RagChunkResult(BaseModel):
    paperId: str
    chunk_index: int
    section_header: Optional[str] = None
    chunk_text: str
    distance: float


class RagChunkResponse(BaseModel):
    query: str
    run_id: int
    n_results: int
    results: list[RagChunkResult]


class PaperSectionResponse(BaseModel):
    paperId: str
    index: int
    header: Optional[str] = None
    section_text: str


class PaperSectionHeader(BaseModel):
    index: int
    header: str


class PaperSectionsResponse(BaseModel):
    paperId: str
    sections: list[PaperSectionHeader]
