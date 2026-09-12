from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send

from literature_ai.review_service.review.nodes.abstract_review import abstract_review
from literature_ai.review_service.review.nodes.compute_elbow import compute_elbow
from literature_ai.review_service.review.nodes.deduplicate_papers import deduplicate_papers
from literature_ai.review_service.review.nodes.prune_results import prune_results
from literature_ai.review_service.review.nodes.search_papers import search_papers
from literature_ai.review_service.review.state import ReviewState

DEFAULT_RESULTS_PER_TERM = 50


def _next_step(state: ReviewState) -> str:
    """Routes both the initial entry and the end of each search/elbow/prune pass: while search
    terms remain unprocessed, loop back to search the next one; once every term in the scope has
    been collected and pruned, move on to deduplication."""
    if state["term_index"] < len(state["search_terms"]):
        return "search_papers"
    return "deduplicate_papers"


def _fan_out_to_abstract_review(state: ReviewState) -> list[Send]:
    """Dispatches one parallel `abstract_review` task per deduplicated paper, once search/elbow/
    prune has run for every search term and deduplication has produced the final paper list."""
    specification = state["specification"]
    return [
        Send("abstract_review", {"paper": paper, "specification": specification})
        for paper in state["deduplicated_papers"]
    ]


def _build_graph() -> CompiledStateGraph:
    """Builds the review pipeline as a small graph of nodes wrapping existing codebase
    functionality, wired together with edges. langgraph stays encapsulated behind this module -
    nothing outside review_service should import it.

    search_papers -> compute_elbow -> prune_results loops once per search term in the scope.
    Once every term has been collected and pruned, deduplicate_papers runs once, then
    abstract_review runs once per deduplicated paper, in parallel."""
    builder = StateGraph(ReviewState)

    builder.add_node("search_papers", search_papers)
    builder.add_node("compute_elbow", compute_elbow)
    builder.add_node("prune_results", prune_results)
    builder.add_node("deduplicate_papers", deduplicate_papers)
    builder.add_node("abstract_review", abstract_review)

    builder.add_conditional_edges(START, _next_step)
    builder.add_edge("search_papers", "compute_elbow")
    builder.add_edge("compute_elbow", "prune_results")
    builder.add_conditional_edges("prune_results", _next_step)
    builder.add_conditional_edges("deduplicate_papers", _fan_out_to_abstract_review)
    builder.add_edge("abstract_review", END)

    return builder.compile()


async def generate_review(
    specification: dict[str, Any],
    embedding_run_id: int,
    results_per_term: int = DEFAULT_RESULTS_PER_TERM,
) -> dict[str, Any]:
    """Entry point for the review pipeline. Takes a finalized scoping specification (schema
    documented in `config/core/agent/prompts/agent_types/scoping.md`) and runs its
    `search_terms` through the review graph."""
    graph = _build_graph()

    initial_state: ReviewState = {
        "specification": specification,
        "embedding_run_id": embedding_run_id,
        "results_per_term": results_per_term,
        "search_terms": specification.get("search_terms") or [],
        "term_index": 0,
        "current_term_results": [],
        "current_term_elbow_rank": None,
        "collected_papers": [],
        "deduplicated_papers": [],
        "reviewed_papers": [],
    }

    result = await graph.ainvoke(initial_state)

    return {
        "collected_papers": result["collected_papers"],
        "deduplicated_papers": result["deduplicated_papers"],
        "reviewed_papers": result["reviewed_papers"],
    }
