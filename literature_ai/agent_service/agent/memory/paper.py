import difflib
from dataclasses import dataclass, field
from typing import Optional

from literature_ai.agent_service.agent.memory.core import MemoryObject

_MAX_SEARCH_RESULTS = 20


@dataclass
class PaperRecord:
    """
    A single paper's minimal factual identity.

    `title`/`abstract` are the only standard fields carried here - everything
    else a paper needs (year, venue, DOI, ...) belongs to the request/DB, not
    memory. This class is purely fact-based; prior LLM-produced review output
    about a paper (reviewed/included status, inclusion/exclusion reasoning)
    lives in `AgentPaperReviewMemory`, not here.
    """

    title: Optional[str] = None
    abstract: Optional[str] = None


@dataclass
class PaperMemoryObject(MemoryObject):
    """Memory object for a collection of papers, keyed by paper id."""

    papers: dict[str, PaperRecord] = field(default_factory=dict)

    def get_summary(self) -> str:
        return (
            f"{self.id}: factual metadata (title, abstract) for a collection "
            "of papers, keyed by paper id. Populated by `vector_search` as "
            "new papers are found. Call `retrieve_paper` with a paper id to "
            "view a specific paper's stored details, or `search_papers` "
            "with a title (or part of one) to find the paper id for a paper "
            f"the user names. Contains {len(self.papers)} papers."
        )

    def format_paper(self, paper_id: str) -> str:
        """Renders a single paper's title and abstract as text for an LLM to read."""
        paper = self.papers.get(paper_id)
        if paper is None:
            return f"No memory found for paper_id `{paper_id}`."

        lines = []
        if paper.title:
            lines.append(f"Title: {paper.title}")
        if paper.abstract:
            lines.append(f"Abstract: {paper.abstract}")

        return "\n".join(lines) if lines else "No details recorded for this paper."

    def search_papers(self, query: str = "") -> str:
        """
        Finds paper ids by title, so an LLM can resolve a paper the user
        names into the id every other paper/review tool expects.

        An empty query lists every stored paper. A non-empty query first
        tries a case-insensitive substring match against titles, falling
        back to fuzzy matching (`difflib`) so a slightly reworded title
        still resolves.
        """
        if not query:
            matches = list(self.papers.items())
        else:
            query_lower = query.lower()
            matches = [
                (paper_id, paper)
                for paper_id, paper in self.papers.items()
                if paper.title and query_lower in paper.title.lower()
            ]
            if not matches:
                titles = {
                    paper.title: paper_id
                    for paper_id, paper in self.papers.items()
                    if paper.title
                }
                close_titles = difflib.get_close_matches(
                    query, titles.keys(), n=_MAX_SEARCH_RESULTS, cutoff=0.6
                )
                matches = [(titles[title], self.papers[titles[title]]) for title in close_titles]

        if not matches:
            return f"No papers found matching `{query}`."

        lines = [
            f"{paper_id}: {paper.title or '(no title recorded)'}"
            for paper_id, paper in matches[:_MAX_SEARCH_RESULTS]
        ]
        return "\n".join(lines)

    def add_paper(
        self, paper_id: str, title: Optional[str] = None, abstract: Optional[str] = None
    ) -> bool:
        """
        Records a new paper's factual details, if not already known.

        This object only accumulates facts, it never revises or removes them
        - an existing `paper_id` is left untouched. Returns True if this
        added a new record, False if `paper_id` was already present. Not
        exposed as its own LLM tool; `vector_search` calls this directly to
        record what it finds.
        """
        if paper_id in self.papers:
            return False

        self.papers[paper_id] = PaperRecord(title=title, abstract=abstract)
        return True
