from literature_ai.review_service.review.state import ReviewState


def deduplicate_papers(state: ReviewState) -> dict:
    """Stub - runs once all search terms have been collected and pruned. Will eventually
    collapse duplicate/near-duplicate papers (same paper surfaced by multiple search terms,
    conference/journal version pairs - see `duplicate_version_handling` in the scope
    specification) into a single entry; for now every collected paper passes through
    unchanged."""
    return {"deduplicated_papers": state["collected_papers"]}
