from kneed import KneeLocator

from literature_ai.review_service.review.state import ReviewState

# Fewer points than this and a knee isn't meaningful to fit - keep the whole result set.
MIN_POINTS_FOR_KNEE = 3


def compute_elbow(state: ReviewState) -> dict:
    """Finds the elbow/knee in the current term's rank-vs-similarity curve with the Kneedle
    algorithm: similarity falls sharply for the first, most-relevant results, then levels off
    into a long tail - the knee marks where that tail begins. Results are already ranked best
    (rank 1) to worst, so the curve is convex and decreasing."""
    results = state["current_term_results"]

    if len(results) < MIN_POINTS_FOR_KNEE:
        return {"current_term_elbow_rank": results[-1]["rank"] if results else 0}

    ranks = [r["rank"] for r in results]
    similarities = [r["similarity"] for r in results]

    knee_locator = KneeLocator(ranks, similarities, curve="convex", direction="decreasing")

    # No knee found (e.g. similarity doesn't meaningfully taper off) - keep everything rather
    # than silently dropping results.
    elbow_rank = knee_locator.knee if knee_locator.knee is not None else ranks[-1]

    return {"current_term_elbow_rank": elbow_rank}
