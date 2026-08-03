from loguru import logger

from literature_ai.core.search.vector_search import vector_search

QUERY = "machine learning optical coherence tomography oct"
MODEL_NAME = "specter_v2"
MODEL_VERSION = None
N_DIM = None
N_RESULTS = 10

if __name__ == "__main__":
    logger.info(f"Searching: {QUERY!r} (model={MODEL_NAME}, n_results={N_RESULTS})")
    results = vector_search(
        query=QUERY,
        model_name=MODEL_NAME,
        model_version=MODEL_VERSION,
        n_dim=N_DIM,
        n_results=N_RESULTS,
    )
    logger.info(f"Found {len(results)} results")
    for i, r in enumerate(results, 1):
        print(f"\n{i}. {r['title']} ({r['year']})")
        print(f"   Venue    : {r['venue']}")
        print(f"   Citations: {r['citationCount']}")
        print(f"   Distance : {r['distance']:.4f}")
