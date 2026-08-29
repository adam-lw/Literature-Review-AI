from dataclasses import dataclass, field

from literature_ai.agent_service.agent.memory.core import MemoryObject


@dataclass
class CriterionReview:
    """Pass/fail verdict and reasoning for one inclusion/exclusion criterion."""

    passed: bool = False
    reason: str = ""


@dataclass
class PaperReview:
    """
    A single paper's review verdict, keyed by paper id in
    `AgentPaperReviewMemory`.

    `inclusion_reasoning` is keyed by whatever criterion names the reviewing
    agent is working against (e.g. "methodological_focus",
    "in_domain_bounds") - these come from the scoping specification's own
    inclusion/exclusion criteria, which vary per review, so there is no fixed
    set of keys here.
    """

    reviewed: bool = False
    included: bool = False
    inclusion_reasoning: dict[str, CriterionReview] = field(default_factory=dict)


@dataclass
class AgentPaperReviewMemory(MemoryObject):
    """Memory object for per-paper review verdicts, keyed by paper id."""

    reviews: dict[str, PaperReview] = field(default_factory=dict)

    def get_summary(self) -> str:
        reviewed_count = sum(1 for r in self.reviews.values() if r.reviewed)
        return (
            f"{self.id}: per-paper review verdicts (reviewed/included status "
            "and pass/fail reasoning per inclusion/exclusion criterion) "
            "produced by the review agent, keyed by paper id. Call "
            "`retrieve_review` with a paper id to view a specific paper's "
            "review. Record verdicts with `record_criterion_review` (one "
            "inclusion/exclusion criterion at a time) and `finalize_review` "
            f"(overall include/exclude decision). Contains {len(self.reviews)} "
            f"paper reviews ({reviewed_count} reviewed so far)."
        )

    def format_review(self, paper_id: str) -> str:
        """Renders a single paper's review verdict as text for an LLM to read."""
        review = self.reviews.get(paper_id)
        if review is None:
            return f"No review recorded for paper_id `{paper_id}`."

        lines = [
            f"Reviewed: {review.reviewed}",
            f"Included: {review.included}",
        ]
        for criterion, verdict in review.inclusion_reasoning.items():
            status = "PASS" if verdict.passed else "FAIL"
            lines.append(
                f"{criterion.replace('_', ' ').title()}: {status} — {verdict.reason}"
            )

        return "\n".join(lines)

    def record_criterion_review(
        self, paper_id: str, criterion: str, passed: bool, reason: str
    ) -> str:
        """
        Records (or overwrites) the pass/fail verdict for one inclusion/
        exclusion criterion on a paper, creating the paper's review entry if
        it doesn't exist yet.
        """
        review = self.reviews.setdefault(paper_id, PaperReview())
        review.inclusion_reasoning[criterion] = CriterionReview(passed=passed, reason=reason)
        status = "PASS" if passed else "FAIL"
        return f"Recorded `{criterion}` as {status} for paper_id `{paper_id}`."

    def finalize_review(self, paper_id: str, included: bool) -> str:
        """Records the overall include/exclude decision for a paper's review."""
        review = self.reviews.setdefault(paper_id, PaperReview())
        review.reviewed = True
        review.included = included
        verdict = "included" if included else "excluded"
        return f"Finalized review for paper_id `{paper_id}`: {verdict}."

    def delete_review(self, paper_id: str) -> str:
        """Removes a paper's review entirely, so it can be reviewed from scratch."""
        if paper_id not in self.reviews:
            return f"No review recorded for paper_id `{paper_id}`; nothing to delete."

        del self.reviews[paper_id]
        return f"Deleted review for paper_id `{paper_id}`."
