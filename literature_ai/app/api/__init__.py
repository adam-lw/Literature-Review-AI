from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from literature_ai.app.api.routers.health import router as health_router
from literature_ai.app.api.routers.projects import results_router, router as projects_router
from literature_ai.db import apply_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    apply_schema(Path(__file__).resolve().parents[2] / "core" / "service_schema.sql")
    apply_schema(Path(__file__).resolve().parents[1] / "schema.sql")
    yield


app = FastAPI(
    title="Literature AI API - App Layer",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(projects_router)
app.include_router(results_router)
