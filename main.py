from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from literature_ai.app.api.routers.health import router as health_router
from literature_ai.app.api.routers.projects import results_router, router as projects_router
from literature_ai.core.api.routers.embedding_models import router as embedding_models_router
from literature_ai.core.api.routers.search import router as search_router
from literature_ai.db import apply_schema

_REPO_ROOT = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    apply_schema(_REPO_ROOT / "literature_ai" / "core" / "service_schema.sql")
    apply_schema(_REPO_ROOT / "literature_ai" / "app" / "schema.sql")
    yield


app = FastAPI(title="Literature AI", lifespan=lifespan)

app.include_router(embedding_models_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(health_router, prefix="/api")
app.include_router(projects_router, prefix="/api")
app.include_router(results_router, prefix="/api")

_dist = _REPO_ROOT / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
