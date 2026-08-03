from fastapi import APIRouter, HTTPException

from literature_ai.app import persistence_handling as db
from literature_ai.app.api import models
from literature_ai.core.search.vector_search import vector_search

router = APIRouter(prefix="/projects", tags=["projects"])
results_router = APIRouter(prefix="/results", tags=["projects"])


def _try_get_project(project_id: str) -> dict:
    project = db.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"No project found for project_id={project_id!r}")
    return project


@router.get("", response_model=models.ProjectListResponse)
def list_projects() -> models.ProjectListResponse:
    projects = [models.ProjectSummaryOut(**p) for p in db.list_projects()]
    return models.ProjectListResponse(projects=projects)


@router.post("", response_model=models.ProjectOut)
def create_project(request: models.ProjectCreateRequest) -> models.ProjectOut:
    try:
        project = db.create_project(
            queries=request.queries,
            embedding_run_id=request.embedding_run_id,
            inclusion_criteria=request.inclusion_criteria,
            n_results=request.n_results,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return models.ProjectOut(**project)


@router.get("/{project_id}", response_model=models.ProjectOut)
def get_project(project_id: str) -> models.ProjectOut:
    return models.ProjectOut(**_try_get_project(project_id))


@router.patch("/{project_id}", response_model=models.ProjectOut)
def update_project(project_id: str, request: models.ProjectUpdateRequest) -> models.ProjectOut:
    _try_get_project(project_id)
    project = db.update_project(project_id, **request.model_dump(exclude_unset=True))
    assert project is not None
    return models.ProjectOut(**project)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str) -> None:
    db.delete_project(project_id)


@router.post("/{project_id}/searches", response_model=models.SearchOut)
def add_search(project_id: str, request: models.SearchCreateRequest) -> models.SearchOut:
    project = _try_get_project(project_id)
    if project["embedding_run_id"] is None:
        raise HTTPException(status_code=422, detail=f"Project {project_id!r} has no embedding_run_id set")

    query = request.query.strip()
    search = db.create_search(project_id, query, request.n_results)
    try:
        results = vector_search(
            query=query,
            run_id=project["embedding_run_id"],
            n_results=request.n_results,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.save_search_results(str(search["search_id"]), results)

    group = db.get_search(str(search["search_id"]))
    assert group is not None
    return models.SearchOut(**group)


@router.delete("/{project_id}/searches/{search_id}", status_code=204)
def delete_search(project_id: str, search_id: str) -> None:
    db.delete_search(project_id, search_id)


@router.patch("/{project_id}/inclusion")
def set_inclusion_bulk(project_id: str, request: models.InclusionBulkRequest) -> dict:
    _try_get_project(project_id)
    count = db.set_inclusion_bulk([item.model_dump() for item in request.items])
    return {"updated": count}


@results_router.patch("/{result_id}/inclusion")
def set_inclusion(result_id: str, request: models.InclusionUpdateRequest) -> dict:
    db.set_inclusion(result_id, request.included)
    return {"result_id": result_id, "included": request.included}
