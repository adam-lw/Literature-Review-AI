from fastapi import FastAPI

from literature_ai.core.agent.tools import register_all_tools
from literature_ai.core.api.routers.embedding_models import router as embedding_models_router
from literature_ai.core.api.routers.invoke_agent import router as invoke_agent_router
from literature_ai.core.api.routers.search import router as search_router

# Discover and register all @tool-decorated functions before any agent runs.
register_all_tools()

app = FastAPI(
    title="Literature AI API",
    version="0.1.0",
)

app.include_router(embedding_models_router)
app.include_router(invoke_agent_router)
app.include_router(search_router)
