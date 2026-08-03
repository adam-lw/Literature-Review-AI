from fastapi import APIRouter
from sqlalchemy import text

from literature_ai.core.api.models import EmbeddingModelsResponse, EmbeddingRun
from literature_ai.db import ENGINE

router = APIRouter(prefix="/embedding-models", tags=["embedding-models"])


@router.get("", response_model=EmbeddingModelsResponse)
def get_embedding_models() -> EmbeddingModelsResponse:
    sql = text("""
        SELECT run_id, ran_at, embedding_model, embedding_version, n_dim, user_tags, source
        FROM processed.embedding_runs_metadata
        ORDER BY ran_at DESC
    """)
    with ENGINE.connect() as conn:
        rows = conn.execute(sql).fetchall()
    runs = [
        EmbeddingRun(
            run_id=row[0],
            ran_at=row[1],
            embedding_model=row[2],
            embedding_version=row[3],
            n_dim=row[4],
            user_tags=row[5] if row[5] is not None else {},
            source=row[6],
        )
        for row in rows
    ]
    return EmbeddingModelsResponse(runs=runs)
