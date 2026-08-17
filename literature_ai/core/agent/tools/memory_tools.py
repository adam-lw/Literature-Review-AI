from literature_ai.core.agent.memory import PaperMemoryObject
from literature_ai.core.agent.tools.core import tool


@tool(
    name="retrieve_findings",
    description=(
        "Retrieves stored findings for a specific paper by its paper id: its "
        "title, abstract, and any prior notes recorded about it (e.g. "
        "summarisation, inclusion/exclusion reasoning, thoughts, user comments)."
    ),
    accepts_memory=True,
    memory_type=PaperMemoryObject,
)
def retrieve_findings(paper_id: str, memory: PaperMemoryObject) -> str:
    """
    Parameters
    ----------
    paper_id : str
        The id of the paper whose findings should be retrieved.
    """
    return memory.format_findings(paper_id)
