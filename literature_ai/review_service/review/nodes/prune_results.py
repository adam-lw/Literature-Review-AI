from literature_ai.review_service.review.state import ReviewState


def prune_results(state: ReviewState) -> dict:
    """Drops every result ranked after the current term's elbow point, then folds the
    survivors into the running `collected_papers` set and advances to the next search term."""
    elbow_rank = state["current_term_elbow_rank"]
    assert elbow_rank is not None, "prune_results must run after compute_elbow"
    kept = [r for r in state["current_term_results"] if r["rank"] <= elbow_rank]

    return {
        "collected_papers": [*state["collected_papers"], *kept],
        "term_index": state["term_index"] + 1,
    }
