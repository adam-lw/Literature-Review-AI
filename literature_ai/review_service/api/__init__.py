from fastapi import FastAPI

from literature_ai.review_service.api.routers.generate_review import (
    router as generate_review_router,
)

app = FastAPI(
    title="Literature AI Review API",
    version="0.1.0",
)

app.include_router(generate_review_router)
