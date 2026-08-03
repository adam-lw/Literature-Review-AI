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
