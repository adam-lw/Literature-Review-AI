"""Persistence layer for the app-layer schema (app.projects, app.searches, app.search_results,
app.paper_inclusion_exclusion, app.paper_summarisations, app.outputs).

Sync SQLAlchemy Core over the shared ENGINE, matching the style of
literature_ai.core.api.routers.embedding_models. This module is pure CRUD against the app
schema — it does not call literature_ai.core.search.vector_search itself; the projects API
router is responsible for running a search and passing the results to save_search_results.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import text

from literature_ai.db import ENGINE


def placeholder_project_title() -> str:
    # TODO: replace with a title generated from the submitted queries once that feature is
    # implemented (explicitly deferred for now).
    return f"Untitled project ({datetime.now():%Y-%m-%d %H:%M})"


def list_projects() -> list[dict[str, Any]]:
    sql = text("""
        SELECT
            p.project_id, p.project_title, p.description, p.inclusion_criteria,
            p.embedding_run_id, p.created_at, p.updated_at,
            COUNT(DISTINCT s.search_id) AS search_count,
            COUNT(DISTINCT sr.result_id) AS paper_count,
            COUNT(DISTINCT sr.result_id) FILTER (WHERE pie.included) AS included_count
        FROM app.projects p
        LEFT JOIN app.searches s ON s.project_id = p.project_id
        LEFT JOIN app.search_results sr ON sr.search_id = s.search_id
        LEFT JOIN app.paper_inclusion_exclusion pie ON pie.result_id = sr.result_id
        GROUP BY p.project_id
        ORDER BY p.created_at DESC
    """)
    with ENGINE.connect() as conn:
        rows = conn.execute(sql).mappings().all()
    return [dict(row) for row in rows]


def create_project(
    queries: list[str],
    embedding_run_id: int,
    inclusion_criteria: str | None = None,
    n_results: int = 10,
) -> dict[str, Any]:
    """Creates a project and runs every distinct, non-blank query in `queries` against it.

    Raises ValueError if `embedding_run_id` doesn't reference an existing embedding run.
    """
    from literature_ai.core.search.vector_search import vector_search

    with ENGINE.connect() as conn:
        run_row = conn.execute(
            text("SELECT run_id FROM processed.embedding_runs_metadata WHERE run_id = :run_id"),
            {"run_id": embedding_run_id},
        ).mappings().first()
    if run_row is None:
        raise ValueError(f"No embedding run found for embedding_run_id={embedding_run_id}")

    with ENGINE.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO app.projects (project_title, inclusion_criteria, embedding_run_id)
                VALUES (:title, :inclusion_criteria, :embedding_run_id)
                RETURNING project_id
            """),
            {
                "title": placeholder_project_title(),
                "inclusion_criteria": inclusion_criteria,
                "embedding_run_id": embedding_run_id,
            },
        ).mappings().one()
    project_id = str(row["project_id"])

    seen: set[str] = set()
    for raw_query in queries:
        query = raw_query.strip()
        if not query or query in seen:
            continue
        seen.add(query)
        search = create_search(project_id, query, n_results)
        results = vector_search(query=query, run_id=embedding_run_id, n_results=n_results)
        save_search_results(str(search["search_id"]), results)

    project = get_project(project_id)
    assert project is not None
    return project


def get_project(project_id: str) -> dict[str, Any] | None:
    with ENGINE.connect() as conn:
        project_row = conn.execute(
            text("""
                SELECT project_id, project_title, description, inclusion_criteria,
                       embedding_run_id, created_at, updated_at
                FROM app.projects WHERE project_id = :pid
            """),
            {"pid": project_id},
        ).mappings().first()
        if project_row is None:
            return None

        search_rows = conn.execute(
            text("""
                SELECT search_id, project_id, query, n_results, created_at
                FROM app.searches WHERE project_id = :pid
                ORDER BY created_at ASC
            """),
            {"pid": project_id},
        ).mappings().all()

        result_rows = conn.execute(
            text("""
                SELECT
                    sr.result_id, sr.search_id, sr.paper_id, sr.type, sr.search_rank,
                    sr.distance, sr.distance_type,
                    r.title, r.abstract, r.year, r.venue, r."citationCount" AS citation_count,
                    r.url, r."DOI" AS doi,
                    COALESCE(pie.included, TRUE) AS included
                FROM app.search_results sr
                JOIN app.searches s ON s.search_id = sr.search_id
                JOIN raw.raw_paper_searches r ON r."paperId" = sr.paper_id
                LEFT JOIN app.paper_inclusion_exclusion pie ON pie.result_id = sr.result_id
                WHERE s.project_id = :pid
                ORDER BY sr.search_id, sr.search_rank ASC
            """),
            {"pid": project_id},
        ).mappings().all()

    results_by_search: dict[str, list[dict[str, Any]]] = {}
    for row in result_rows:
        results_by_search.setdefault(str(row["search_id"]), []).append(dict(row))

    project = dict(project_row)
    project["searches"] = [
        {**dict(search), "results": results_by_search.get(str(search["search_id"]), [])}
        for search in search_rows
    ]
    return project


def update_project(project_id: str, **fields: Any) -> dict[str, Any] | None:
    allowed = {"project_title", "description", "inclusion_criteria", "embedding_run_id"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return get_project(project_id)
    set_clause = ", ".join(f'"{k}" = :{k}' for k in updates)
    with ENGINE.begin() as conn:
        conn.execute(
            text(f'UPDATE app.projects SET {set_clause}, "updated_at" = NOW() WHERE project_id = :pid'),
            {**updates, "pid": project_id},
        )
    return get_project(project_id)


def delete_project(project_id: str) -> None:
    with ENGINE.begin() as conn:
        conn.execute(text("DELETE FROM app.projects WHERE project_id = :pid"), {"pid": project_id})


def create_search(project_id: str, query: str, n_results: int = 10) -> dict[str, Any]:
    """Creates (or, on conflict, refreshes n_results on) the app.searches row for this term."""
    with ENGINE.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO app.searches (project_id, query, n_results)
                VALUES (:project_id, :query, :n_results)
                ON CONFLICT (project_id, query) DO UPDATE SET n_results = EXCLUDED.n_results
                RETURNING search_id, project_id, query, n_results, created_at
            """),
            {"project_id": project_id, "query": query, "n_results": n_results},
        ).mappings().one()
    return dict(row)


def get_search(search_id: str) -> dict[str, Any] | None:
    with ENGINE.connect() as conn:
        search_row = conn.execute(
            text("""
                SELECT search_id, project_id, query, n_results, created_at
                FROM app.searches WHERE search_id = :sid
            """),
            {"sid": search_id},
        ).mappings().first()
        if search_row is None:
            return None

        result_rows = conn.execute(
            text("""
                SELECT
                    sr.result_id, sr.search_id, sr.paper_id, sr.type, sr.search_rank,
                    sr.distance, sr.distance_type,
                    r.title, r.abstract, r.year, r.venue, r."citationCount" AS citation_count,
                    r.url, r."DOI" AS doi,
                    COALESCE(pie.included, TRUE) AS included
                FROM app.search_results sr
                JOIN raw.raw_paper_searches r ON r."paperId" = sr.paper_id
                LEFT JOIN app.paper_inclusion_exclusion pie ON pie.result_id = sr.result_id
                WHERE sr.search_id = :sid
                ORDER BY sr.search_rank ASC
            """),
            {"sid": search_id},
        ).mappings().all()

    return {**dict(search_row), "results": [dict(row) for row in result_rows]}


def delete_search(project_id: str, search_id: str) -> None:
    with ENGINE.begin() as conn:
        conn.execute(
            text("DELETE FROM app.searches WHERE search_id = :sid AND project_id = :pid"),
            {"sid": search_id, "pid": project_id},
        )


def save_search_results(search_id: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Upserts vector_search() result rows for a search, ranked by their list order.

    Re-running a search updates rank/distance for papers still present rather than resetting
    them, and never overwrites an existing inclusion flag — only a first-seen result gets the
    default included=True.
    """
    inserted: list[dict[str, Any]] = []
    with ENGINE.begin() as conn:
        for rank, row in enumerate(rows, start=1):
            result = conn.execute(
                text("""
                    INSERT INTO app.search_results
                        (search_id, paper_id, type, search_rank, distance, distance_type)
                    VALUES (:search_id, :paper_id, 'embedding', :rank, :distance, :distance_type)
                    ON CONFLICT (search_id, type, paper_id)
                    DO UPDATE SET search_rank = EXCLUDED.search_rank,
                                  distance = EXCLUDED.distance,
                                  distance_type = EXCLUDED.distance_type
                    RETURNING result_id
                """),
                {
                    "search_id": search_id,
                    "paper_id": row["paperId"],
                    "rank": rank,
                    "distance": row.get("distance"),
                    "distance_type": row.get("distance_type") or "cosine",
                },
            ).mappings().one()
            result_id = result["result_id"]
            conn.execute(
                text("""
                    INSERT INTO app.paper_inclusion_exclusion (result_id, included)
                    VALUES (:result_id, TRUE)
                    ON CONFLICT (result_id) DO NOTHING
                """),
                {"result_id": result_id},
            )
            inserted.append({"result_id": str(result_id), **row})
    return inserted


def set_inclusion(result_id: str, included: bool) -> None:
    with ENGINE.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO app.paper_inclusion_exclusion (result_id, included)
                VALUES (:result_id, :included)
                ON CONFLICT (result_id) DO UPDATE SET included = EXCLUDED.included
            """),
            {"result_id": result_id, "included": included},
        )


def set_inclusion_bulk(items: list[dict[str, Any]]) -> int:
    if not items:
        return 0
    with ENGINE.begin() as conn:
        for item in items:
            conn.execute(
                text("""
                    INSERT INTO app.paper_inclusion_exclusion (result_id, included)
                    VALUES (:result_id, :included)
                    ON CONFLICT (result_id) DO UPDATE SET included = EXCLUDED.included
                """),
                {"result_id": item["result_id"], "included": item["included"]},
            )
    return len(items)


def list_summarisations(project_id: str) -> list[dict[str, Any]]:
    with ENGINE.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT summarisation_id, project_id, paper_id, summary, model, created_at
                FROM app.paper_summarisations
                WHERE project_id = :pid
                ORDER BY created_at DESC
            """),
            {"pid": project_id},
        ).mappings().all()
    return [dict(row) for row in rows]
