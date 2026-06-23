- Vector database with PostgreSQL and pgvector


Evaluation
- Need to assess quality of embedding models & embedding sizes.
- Assess retrieval quality
	- AI as a judge to score paper relevance to some example queries, then rank various retrieval and indexing algorithms against the "ground truth"
- Assess index quality & tradeoffs 
	- Some indexes are slow and more accurate, some faster and less accurate.
	- Some consume more memory, some less
- Assess actual RAG performance for various approaches

Implementation
- Common `core` for main functionality of application
- Pipeline for building vector database, evaluation
- Notebooks for experimentation & evaluation
- Will be based on an embedding function which will be used in both the `pipeline` and `api` depending on the exact deployment - lives inside core
- 