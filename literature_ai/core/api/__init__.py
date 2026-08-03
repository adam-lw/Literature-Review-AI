from fastapi import FastAPI

from literature_ai.core.api.routers.embedding_models import router as embedding_models_router
from literature_ai.core.api.routers.search import router as search_router

app = FastAPI(
    title="Literature AI API",
    version="0.1.0",
)

app.include_router(embedding_models_router)
app.include_router(search_router)
