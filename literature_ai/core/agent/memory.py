from dataclasses import dataclass, field
from typing import Any, Optional


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


@dataclass
class PaperRecord:
    """
    A single paper's minimal identity plus freeform findings.

    `title`/`abstract` are the only standard fields carried here - everything
    else a paper needs (year, venue, DOI, ...) belongs to the request/DB, not
    memory. `findings` holds prior LLM output about the paper, keyed by kind
    (e.g. "summarisation", "inclusion_reasoning", "thoughts",
    "user_comments"), with values of whatever shape that kind needs.
    """

    title: Optional[str] = None
    abstract: Optional[str] = None
    findings: dict[str, Any] = field(default_factory=dict)


@dataclass
class PaperMemoryObject(MemoryObject):
    """Memory object for a collection of papers, keyed by paper id."""

    papers: dict[str, PaperRecord] = field(default_factory=dict)

    def format_findings(self, paper_id: str) -> str:
        """Renders a single paper's title, abstract, and findings as text for an LLM to read."""
        paper = self.papers.get(paper_id)
        if paper is None:
            return f"No memory found for paper_id `{paper_id}`."

        lines = []
        if paper.title:
            lines.append(f"Title: {paper.title}")
        if paper.abstract:
            lines.append(f"Abstract: {paper.abstract}")
        for kind, value in paper.findings.items():
            lines.append(f"{kind.replace('_', ' ').title()}: {value}")

        return "\n".join(lines) if lines else "No findings recorded for this paper."


def get_formatted_memory(memory: dict[str, MemoryObject]) -> str:
    """Returns a string summarizing available memory objects for use by an LLM."""
    if not memory:
        return ""

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
