from dataclasses import dataclass


@dataclass
class MemoryObject:
    """
    Base class for objects held in an Agent's `memory` store.

    Subclasses represent a specific kind of context (e.g. a collection of
    papers) that the agent can look up on demand via a memory-aware tool (see
    `accepts_memory` on the `tool` decorator), rather than having it dumped
    into the prompt up front.
    """

    id: str


def get_formatted_memory(memory: dict[str, MemoryObject]) -> str:
    """Returns a string summarizing available memory objects for use by an LLM."""
    if not memory:
        return ""

    # Imported lazily to avoid a circular import (paper.py imports MemoryObject from here).
    from literature_ai.agent_service.agent.memory.paper import PaperMemoryObject

    lines: list[str] = []
    for obj in memory.values():
        if isinstance(obj, PaperMemoryObject):
            lines.extend(
                f"- {paper_id}: {paper.title or 'Untitled paper'}"
                for paper_id, paper in obj.papers.items()
            )
        else:
            lines.append(f"- {obj.id}")

    if not lines:
        return ""

    return (
        "\n\nThe following items are available in memory. Call a memory-aware "
        "tool (e.g. `retrieve_findings`) with an id below to view its full "
        "stored contents.\n" + "\n".join(lines)
    )
