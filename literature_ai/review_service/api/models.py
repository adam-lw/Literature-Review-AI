from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from literature_ai.review_service.review.generate_review import DEFAULT_RESULTS_PER_TERM
from literature_ai.review_service.review.state import ReviewedPaper, SearchResult


class GenerateReviewRequest(BaseModel):
    specification: dict[str, Any]
    embedding_run_id: int
    results_per_term: int = DEFAULT_RESULTS_PER_TERM


class GenerateReviewResponse(BaseModel):
    collected_papers: list[SearchResult]
    deduplicated_papers: list[SearchResult]
    reviewed_papers: list[ReviewedPaper]
