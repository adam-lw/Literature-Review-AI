import os

import requests

from literature_ai.agent_service.agent.memory import PaperMemoryObject
from literature_ai.agent_service.agent.tools.decorators import tool

# Base URL of the search service, including whatever prefix it's actually served under.
# - Standalone `literature_ai.search_service.api` app: no prefix, e.g. "http://localhost:8000".
# - Combined `main.py` app (mounts the search router under "/api"): "http://localhost:8000/api".
SEARCH_SERVICE_URL = os.getenv("SEARCH_SERVICE_URL", "http://localhost:8000")


@tool(
    name="vector_search",
    description=(
        "Performs a vector search using embeddings to find papers similar "
        "to a query, and records each result's factual details (title, "
        "abstract) into memory. Returns a summary - paper id and title per "
        "result, and how many were new - rather than full paper bodies; "
        "call `retrieve_paper` with a paper id from the summary to view a "
        "specific result's full details."
    ),
    accepts_memory=True,
    memory_type=PaperMemoryObject,
)
def vector_search(query: str, run_id: int, memory: PaperMemoryObject, n_results: int = 5) -> str:
    """Perform a vector search over abstract embeddings by calling the search service's API.

    Parameters
    ----------
    query : str
        Natural-language search query.
    run_id : int
        Embedding run ID to search against.
    n_results : int
        Number of nearest neighbours to return. Default is ``5``.

    Raises
    ------
    requests.HTTPError
        If the search service request fails (e.g. no matching embedding run).
    """
    response = requests.post(
        f"{SEARCH_SERVICE_URL}/search",
        json={"query": query, "run_id": run_id, "n_results": n_results},
        timeout=30,
    )
    response.raise_for_status()
    results = response.json()["results"]

    if not results:
        return f"No papers found for query `{query}`."

    lines = []
    new_count = 0
    for result in results:
        paper_id = result["paperId"]
        if memory.add_paper(paper_id, title=result.get("title"), abstract=result.get("abstract")):
            new_count += 1
        lines.append(f"{paper_id}: {result.get('title') or '(no title recorded)'}")

    header = (
        f"Found {len(results)} papers ({new_count} new, "
        f"{len(results) - new_count} already in memory)."
    )
    return "\n".join([header, *lines])
