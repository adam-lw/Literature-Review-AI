from dataclasses import dataclass, field
from typing import Any, Optional

from literature_ai.agent_service.agent.memory.core import MemoryObject


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
