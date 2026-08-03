"""Pydantic request/response models for the app-layer (projects) API."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectCreateRequest(BaseModel):
    queries: list[str] = Field(..., min_length=1)
    embedding_run_id: int = Field(..., gt=0)
    inclusion_criteria: Optional[str] = None
    n_results: int = Field(10, ge=1, le=100)


class ProjectUpdateRequest(BaseModel):
    project_title: Optional[str] = None
    description: Optional[str] = None
    inclusion_criteria: Optional[str] = None
    embedding_run_id: Optional[int] = Field(None, gt=0)


class SearchCreateRequest(BaseModel):
    query: str = Field(..., min_length=1)
    n_results: int = Field(10, ge=1, le=100)


class InclusionUpdateRequest(BaseModel):
    included: bool


class InclusionBulkItem(BaseModel):
    result_id: UUID
    included: bool


class InclusionBulkRequest(BaseModel):
    items: list[InclusionBulkItem]


class ResultOut(BaseModel):
    result_id: UUID
    search_id: UUID
    paper_id: str
    type: str
    search_rank: int
    distance: Optional[float] = None
    distance_type: Optional[str] = None
    title: Optional[str] = None
    abstract: Optional[str] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    citation_count: Optional[int] = None
    url: Optional[str] = None
    doi: Optional[str] = None
    included: bool


class SearchOut(BaseModel):
    search_id: UUID
    project_id: UUID
    query: str
    n_results: int
    created_at: datetime
    results: list[ResultOut] = []


class ProjectOut(BaseModel):
    project_id: UUID
    project_title: str
    description: Optional[str] = None
    inclusion_criteria: Optional[str] = None
    embedding_run_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    searches: list[SearchOut] = []


class ProjectSummaryOut(BaseModel):
    project_id: UUID
    project_title: str
    description: Optional[str] = None
    inclusion_criteria: Optional[str] = None
    embedding_run_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    search_count: int
    paper_count: int
    included_count: int


class ProjectListResponse(BaseModel):
    projects: list[ProjectSummaryOut]


class HealthResponse(BaseModel):
    ok: bool
