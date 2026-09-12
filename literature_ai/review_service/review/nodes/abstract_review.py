import json
import os

import requests

from literature_ai.agent_service.agent.prompt.prompt import get_prompt
from literature_ai.review_service.review.state import PaperReviewInput, ReviewedPaper

# Same convention as nodes/search_papers.py - base URL of the combined API (or the standalone
# agent_service app when run alone).
AGENT_SERVICE_URL = os.getenv("AGENT_SERVICE_URL", "http://localhost:8000")

MODEL = "gpt-5.6-luna"


def abstract_review(state: PaperReviewInput) -> dict:
    """Reviews one paper's title/abstract pair against the scope's inclusion/exclusion
    criteria via a single LLM call (see config/core/agent/prompts/utils/review_abstract.md) -
    a cautious pass that only excludes papers clearly out of scope. Runs as one parallel task
    per paper - see the fan-out in generate_review.py."""
    paper = state["paper"]
    specification = state["specification"]

    scope_context = json.dumps(
        {
            "research_questions": specification.get("research_questions"),
            "review_definition": specification.get("review_definition"),
            "inclusion_exclusion_criteria": specification.get("inclusion_exclusion_criteria"),
            "topical_relevance": specification.get("topical_relevance"),
        },
        indent=2,
    )

    prompt = get_prompt(
        "utils/review_abstract",
        scope_context=scope_context,
        title=paper["title"] or "",
        abstract=paper["abstract"] or "",
    )

    response = requests.post(
        f"{AGENT_SERVICE_URL}/call-llm",
        json={"model": MODEL, "text": prompt},
        timeout=60,
    )
    response.raise_for_status()
    output = response.json()["output"].strip()

    decision, _, reasoning = output.partition("\n")

    reviewed_paper: ReviewedPaper = {
        "paper_id": paper["paper_id"],
        "title": paper["title"],
        "abstract": paper["abstract"],
        "included": decision.strip().upper() == "INCLUDE",
        "reasoning": reasoning.strip() or None,
    }

    return {"reviewed_papers": [reviewed_paper]}
