import os

import requests

from literature_ai.agent_service.agent.tools.decorators import tool

# See search_tools.py's SEARCH_SERVICE_URL for the two ways this base URL is used
# (standalone search-service app with no prefix, vs. the combined app's "/api" prefix).
SEARCH_SERVICE_URL = os.getenv("SEARCH_SERVICE_URL", "http://localhost:8000")


@tool(
    name="rag_paper_chunks",
    description=(
        "Performs a RAG search over the full text of specific papers (not just their "
        "abstracts), restricted to the paper_ids you provide. Use this when a query "
        "needs details that live in a paper's body - methodology details, specific "
        "numbers, quotes - rather than what's summarized in the abstract. Only "
        "searches papers that have already been fetched and chunked (e.g. via a prior "
        "list_paper_sections or get_paper_section call for that paper_id) - a paper "
        "not yet processed simply contributes no results, so fetch it first."
    ),
)
def rag_paper_chunks(paper_ids: list[str], query: str, n_results: int = 5) -> str:
    """Search the full text of specific papers by calling the search service's API.

    Parameters
    ----------
    paper_ids : list of str
        Paper ids to restrict the search to (e.g. from vector_search results).
    query : str
        Natural-language search query to run against each paper's full text.
    n_results : int
        Number of chunk results to return across all papers. Default is 5.

    Raises
    ------
    requests.HTTPError
        If the search service request fails.
    """
    response = requests.post(
        f"{SEARCH_SERVICE_URL}/rag-paper-chunks",
        json={
            "paper_ids": paper_ids,
            "query": query,
            "n_results": n_results,
        },
        timeout=200,
    )
    response.raise_for_status()
    results = response.json()["results"]

    if not results:
        return f"No matching chunks found for query `{query}` in {paper_ids}."

    lines = [f"Found {len(results)} matching chunks."]
    for result in results:
        header = result.get("section_header") or "(untitled section)"
        lines.append(f"\n[{result['paperId']} / {header}] (distance={result['distance']:.4f})")
        lines.append(result["chunk_text"])
    return "\n".join(lines)


@tool(
    name="list_paper_sections",
    description=(
        "Lists a paper's actual section headers (e.g. what it calls its methodology "
        "or results section), in document order, along with the index each has. Call "
        "this BEFORE get_paper_section to find the index of the section you want, "
        "since papers do not share a standard set of section headers."
    ),
)
def list_paper_sections(paper_id: str) -> str:
    """List a paper's section headers by calling the search service's API.

    Parameters
    ----------
    paper_id : str
        Paper id to list sections for.

    Raises
    ------
    requests.HTTPError
        If the search service request fails (e.g. unknown paper_id, or no full text
        available for this paper).
    """
    response = requests.get(f"{SEARCH_SERVICE_URL}/full-paper/{paper_id}/sections", timeout=200)
    response.raise_for_status()
    sections = response.json()["sections"]

    if not sections:
        return f"No section headers found for paper_id `{paper_id}`."

    return "\n".join(f"{s['index']}: {s['header']}" for s in sections)


@tool(
    name="get_paper_section",
    description=(
        "Retrieves one section's full text from a paper's parsed full text, by the "
        "`index` returned from list_paper_sections. Section headers are free-text as "
        "written in each paper's own PDF, with no fixed taxonomy, so sections are "
        "addressed by index rather than by guessing a name - call list_paper_sections "
        "first to find the index you want."
    ),
)
def get_paper_section(paper_id: str, index: int) -> str:
    """Retrieve a section by index by calling the search service's API.

    Parameters
    ----------
    paper_id : str
        Paper id to retrieve a section from.
    index : int
        Section index, as returned by list_paper_sections.

    Raises
    ------
    requests.HTTPError
        If the search service request fails (e.g. unknown paper_id, or no section at
        that index).
    """
    response = requests.get(
        f"{SEARCH_SERVICE_URL}/full-paper/{paper_id}/sections/{index}",
        timeout=200,
    )
    response.raise_for_status()
    body = response.json()

    header = body["header"] or "(untitled section)"
    return f"[{header}]\n\n{body['section_text']}"
