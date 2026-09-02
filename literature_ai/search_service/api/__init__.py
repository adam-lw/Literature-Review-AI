from fastapi import FastAPI

from literature_ai.search_service.api.routers.embedding_models import (
    router as embedding_models_router,
)
from literature_ai.search_service.api.routers.full_paper import (
    router as full_paper_router,
)
from literature_ai.search_service.api.routers.rag_paper_chunks import (
    router as rag_paper_chunks_router,
)
from literature_ai.search_service.api.routers.search import router as search_router

app = FastAPI(
    title="Literature AI Search API",
    version="0.1.0",
)

app.include_router(embedding_models_router)
app.include_router(full_paper_router)
app.include_router(rag_paper_chunks_router)
app.include_router(search_router)
