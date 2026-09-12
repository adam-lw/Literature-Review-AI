import operator
from typing import Annotated, Any, Optional, TypedDict


class SearchResult(TypedDict):
    """One paper returned by a semantic search against a single search term, ranked and
    scored within that term's result set (see nodes/search_papers.py, nodes/compute_elbow.py)."""

    paper_id: str
    title: Optional[str]
    abstract: Optional[str]
    year: Optional[int]
    venue: Optional[str]
    citation_count: Optional[int]
    url: Optional[str]
    doi: Optional[str]
    search_term: str
    rank: int
    similarity: float


class ReviewedPaper(TypedDict):
    """A paper after title/abstract screening (see nodes/abstract_review.py)."""

    paper_id: str
    title: Optional[str]
    abstract: Optional[str]
    included: Optional[bool]
    reasoning: Optional[str]


class PaperReviewInput(TypedDict):
    """Per-paper input for one parallel `abstract_review` task - see
    nodes/abstract_review.py's fan-out over `deduplicated_papers`."""

    paper: SearchResult
    specification: dict[str, Any]


class ReviewState(TypedDict):
    # Inputs, set once at graph invocation and left untouched by every node.
    specification: dict[str, Any]
    embedding_run_id: int
    results_per_term: int

    # `search_terms`/`term_index` drive the search -> elbow -> prune loop: one term is
    # processed per pass, `term_index` advances in prune_results, and the loop exits once
    # every term in the scope's `search_terms` has been searched and pruned.
    search_terms: list[str]
    term_index: int

    # Scratch space for the term currently being processed - overwritten each pass.
    current_term_results: list[SearchResult]
    current_term_elbow_rank: Optional[int]

    # Accumulated across every completed pass, then carried through the rest of the pipeline.
    collected_papers: list[SearchResult]
    deduplicated_papers: list[SearchResult]

    # Written by parallel `abstract_review` tasks (one per paper - see fan-out in
    # generate_review.py) - the reducer merges each task's single-item list rather than one
    # overwriting another.
    reviewed_papers: Annotated[list[ReviewedPaper], operator.add]
