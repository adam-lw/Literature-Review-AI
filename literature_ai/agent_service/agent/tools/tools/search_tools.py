import os

import requests

from literature_ai.agent_service.agent.tools.decorators import tool

# Base URL of the search service, including whatever prefix it's actually served under.
# - Standalone `literature_ai.search_service.api` app: no prefix, e.g. "http://localhost:8000".
# - Combined `main.py` app (mounts the search router under "/api"): "http://localhost:8000/api".
SEARCH_SERVICE_URL = os.getenv("SEARCH_SERVICE_URL", "http://localhost:8000")


@tool(
    name="vector_search",
    description="Perform a vector search using embeddings to find similar documents",
)
def vector_search(query: str, run_id: int, n_results: int = 5) -> list[dict]:
    """Perform a vector search over abstract embeddings by calling the search service's API.

    Parameters
    ----------
    query : str
        Natural-language search query.
    run_id : int
        Embedding run ID to search against.
    n_results : int
        Number of nearest neighbours to return. Default is ``5``.

    Returns
    -------
    list of dict
        Each dict contains ``paperId``, ``title``, ``abstract``, ``year``,
        ``venue``, ``citationCount``, ``url``, ``DOI``, and ``distance``
        (cosine distance to the query vector), ordered by ascending distance.

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
    return response.json()["results"]
