import os

import requests

from literature_ai.review_service.review.state import ReviewState, SearchResult

# Base URL of the search service, including whatever prefix it's actually served under - see
# the identical convention in agent_service/agent/tools/tools/search_tools.py.
# - Standalone `literature_ai.search_service.api` app: no prefix, e.g. "http://localhost:8000".
# - Combined `main.py` app (mounts the search router under "/api"): "http://localhost:8000/api".
SEARCH_SERVICE_URL = os.getenv("SEARCH_SERVICE_URL", "http://localhost:8000")


def search_papers(state: ReviewState) -> dict:
    """Calls the search service's semantic search endpoint for the search term at
    `term_index`, ranking results by similarity (1 - cosine distance) in the order returned -
    nearest first."""
    term = state["search_terms"][state["term_index"]]

    response = requests.post(
        f"{SEARCH_SERVICE_URL}/search",
        json={
            "query": term,
            "run_id": state["embedding_run_id"],
            "n_results": state["results_per_term"],
        },
        timeout=30,
    )
    response.raise_for_status()
    results = response.json()["results"]

    current_term_results: list[SearchResult] = [
        {
            "paper_id": result["paperId"],
            "title": result.get("title"),
            "abstract": result.get("abstract"),
            "year": result.get("year"),
            "venue": result.get("venue"),
            "citation_count": result.get("citationCount"),
            "url": result.get("url"),
            "doi": result.get("DOI"),
            "search_term": term,
            "rank": rank,
            "similarity": 1.0 - result["distance"],
        }
        for rank, result in enumerate(results, start=1)
    ]

    return {"current_term_results": current_term_results}
