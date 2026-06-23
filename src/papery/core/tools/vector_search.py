from typing import Any
from papery.core.embeddings import get_embedding_model
from papery.core.tools import tool
from papery.core.db import execute_query

@tool(
    name="vector_search",
    description="Perform a vector search using embeddings to find similar documents",
)
async def vector_search(
    query: str,
    model_name: str,
    table_path: str,
    n_results: int = 5
) -> list[dict]:
    """
    Perform a vector search using a given string query.
    
    Args:
        query: The search query string
        model_name: Name of the embedding model to use
        table_path: PostgreSQL table path for searching
        n_results: Number of nearest neighbors to return
        connection: Database connection object
    
    Returns:
        List of N nearest neighbor results from the table
    """
    # Get the embedding model using factory
    model = get_embedding_model(model_name)
    
    # Generate embedding vector for the query
    query_embedding = await model.call(query)
    
    # Search for nearest neighbors in the PostgreSQL table
    results = execute_query(
        f"""
        SELECT * FROM {table_path}
        ORDER BY embedding <-> '{query_embedding}'
        LIMIT {n_results}
        """
    )
    return results