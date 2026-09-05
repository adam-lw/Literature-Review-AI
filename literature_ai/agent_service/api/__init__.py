from fastapi import FastAPI

from literature_ai.agent_service.agent.tools import register_all_tools
from literature_ai.agent_service.api.routers.generate_title import (
    router as generate_title_router,
)
from literature_ai.agent_service.api.routers.invoke_agent import (
    router as invoke_agent_router,
)

# Discover and register all @tool-decorated functions before any agent runs.
register_all_tools()

app = FastAPI(
    title="Literature AI Agent API",
    version="0.1.0",
)

app.include_router(invoke_agent_router)
app.include_router(generate_title_router)
