from literature_ai.agent_service.agent.memory import (
    AgentPaperReviewMemory,
    PaperMemoryObject,
    ScopingMemoryObject,
)
from literature_ai.agent_service.agent.tools.decorators import tool


@tool(
    name="retrieve_paper",
    description=(
        "Retrieves stored factual details for a specific paper by its paper "
        "id: its title and abstract."
    ),
    accepts_memory=True,
    memory_type=PaperMemoryObject,
)
def retrieve_paper(paper_id: str, memory: PaperMemoryObject) -> str:
    """
    Parameters
    ----------
    paper_id : str
        The id of the paper whose details should be retrieved.
    """
    return memory.format_paper(paper_id)


@tool(
    name="search_papers",
    description=(
        "Finds paper ids by title. Use this to resolve a paper the user "
        "names (or part of its title) into the paper id that every other "
        "paper/review tool requires. Call with an empty query to list every "
        "paper currently in memory."
    ),
    accepts_memory=True,
    memory_type=PaperMemoryObject,
)
def search_papers(memory: PaperMemoryObject, query: str = "") -> str:
    """
    Parameters
    ----------
    query : str
        A title, or part of one, to search for. Leave empty to list every
        stored paper.
    """
    return memory.search_papers(query)


@tool(
    name="retrieve_scope",
    description=(
        "Retrieves the current scoping specification for this literature "
        "review: research questions, review definition, inclusion/exclusion "
        "criteria, topical relevance, search terms, open items, and scope "
        "risk note."
    ),
    accepts_memory=True,
    memory_type=ScopingMemoryObject,
)
def retrieve_scope(memory: ScopingMemoryObject) -> str:
    return memory.format_specification()


@tool(
    name="update_scope",
    description=(
        "Replaces the scoping specification with a new, complete "
        "specification. This is a wholesale replacement, not a partial "
        "patch - always pass the full specification JSON, including fields "
        "that are unchanged."
    ),
    accepts_memory=True,
    memory_type=ScopingMemoryObject,
)
def update_scope(specification: str, memory: ScopingMemoryObject) -> str:
    """
    Parameters
    ----------
    specification : str
        The complete, updated scoping specification, as a JSON string.
    """
    return memory.update_scope(specification)


@tool(
    name="retrieve_review",
    description=(
        "Retrieves the recorded review verdict for a specific paper by its "
        "paper id: overall reviewed/included status and pass/fail reasoning "
        "per inclusion/exclusion criterion."
    ),
    accepts_memory=True,
    memory_type=AgentPaperReviewMemory,
)
def retrieve_review(paper_id: str, memory: AgentPaperReviewMemory) -> str:
    """
    Parameters
    ----------
    paper_id : str
        The id of the paper whose review should be retrieved.
    """
    return memory.format_review(paper_id)


@tool(
    name="record_criterion_review",
    description=(
        "Records the pass/fail verdict and reasoning for one inclusion/"
        "exclusion criterion on a paper's review. Call once per criterion; "
        "calling it again for the same criterion overwrites the prior "
        "verdict."
    ),
    accepts_memory=True,
    memory_type=AgentPaperReviewMemory,
)
def record_criterion_review(
    paper_id: str, criterion: str, passed: bool, reason: str, memory: AgentPaperReviewMemory
) -> str:
    """
    Parameters
    ----------
    paper_id : str
        The id of the paper being reviewed.
    criterion : str
        The name of the inclusion/exclusion criterion being evaluated.
    passed : bool
        Whether the paper satisfies this criterion.
    reason : str
        The reasoning behind the verdict.
    """
    return memory.record_criterion_review(paper_id, criterion, passed, reason)


@tool(
    name="finalize_review",
    description=(
        "Records the overall include/exclude decision for a paper, after "
        "its inclusion/exclusion criteria have been evaluated."
    ),
    accepts_memory=True,
    memory_type=AgentPaperReviewMemory,
)
def finalize_review(paper_id: str, included: bool, memory: AgentPaperReviewMemory) -> str:
    """
    Parameters
    ----------
    paper_id : str
        The id of the paper being reviewed.
    included : bool
        Whether the paper should be included in the review overall.
    """
    return memory.finalize_review(paper_id, included)


@tool(
    name="delete_review",
    description="Removes a paper's recorded review entirely, so it can be reviewed from scratch.",
    accepts_memory=True,
    memory_type=AgentPaperReviewMemory,
)
def delete_review(paper_id: str, memory: AgentPaperReviewMemory) -> str:
    """
    Parameters
    ----------
    paper_id : str
        The id of the paper whose review should be deleted.
    """
    return memory.delete_review(paper_id)
