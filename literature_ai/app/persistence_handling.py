"""Persistence layer for the app-layer schema (app.projects, app.searches, app.search_results,
app.conversations, app.messages, app.scopes, app.reviews, app.written_papers).

Sync SQLAlchemy Core over the shared ENGINE, matching the style of
literature_ai.search_service.api.routers.embedding_models. This module is pure CRUD against the app
schema — it does not call literature_ai.search_service.search.vector_search itself; the projects API
router is responsible for running a search and passing the results to save_search_results. It is
also imported directly by literature_ai.agent_service (single FastAPI process, see main.py), so the
agent's conversation/scope/review state persists through the same tables and connection pool as
everything else here — there is no separate HTTP layer between the two.

Inclusion/exclusion state ("included") and per-paper review data live in app.reviews, keyed by
(conversation_id, paper_id) rather than by search result: a project has at most one 'review'-stage
conversation (see conversations_project_stage_uniq), so the same paper found via two different
search queries always carries exactly one verdict, and both manual checkbox toggles and agent tool
calls write into that same conversation's rows.
"""

import json
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
            p.project_id, p.project_title, p.inclusion_criteria,
            p.embedding_run_id, p.project_mode, p.created_at, p.updated_at,
            COUNT(DISTINCT s.search_id) AS search_count,
            COUNT(DISTINCT sr.paper_id) AS paper_count,
            COUNT(DISTINCT sr.paper_id) FILTER (
                WHERE COALESCE((r.content->>'included')::boolean, TRUE)
            ) AS included_count
        FROM app.projects p
        LEFT JOIN app.searches s ON s.project_id = p.project_id
        LEFT JOIN app.search_results sr ON sr.search_id = s.search_id
        LEFT JOIN app.conversations c ON c.project_id = p.project_id AND c.stage = 'review'
        LEFT JOIN app.reviews r ON r.conversation_id = c.conversation_id AND r.paper_id = sr.paper_id
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
    from literature_ai.search_service.search.vector_search import vector_search

    with ENGINE.connect() as conn:
        run_row = (
            conn.execute(
                text(
                    "SELECT run_id FROM processed.embedding_runs_metadata WHERE run_id = :run_id"
                ),
                {"run_id": embedding_run_id},
            )
            .mappings()
            .first()
        )
    if run_row is None:
        raise ValueError(
            f"No embedding run found for embedding_run_id={embedding_run_id}"
        )

    with ENGINE.begin() as conn:
        row = (
            conn.execute(
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
            )
            .mappings()
            .one()
        )
    project_id = str(row["project_id"])

    seen: set[str] = set()
    for raw_query in queries:
        query = raw_query.strip()
        if not query or query in seen:
            continue
        seen.add(query)
        search = create_search(project_id, query, n_results)
        results = vector_search(
            query=query, run_id=embedding_run_id, n_results=n_results
        )
        save_search_results(str(search["search_id"]), results)

    project = get_project(project_id)
    assert project is not None
    return project


def create_agent_project(
    inclusion_criteria: str | None = None,
    project_title: str | None = None,
) -> dict[str, Any]:
    """Creates an agent-mode project: no initial search queries or embedding_run_id (those get
    filled in once the scoping conversation produces a scope and the search_review stage starts
    running searches). The free-text research description isn't persisted here at all - it's
    sent straight through as the scoping conversation's opening instruction and lands in
    app.messages the first time that phase starts (see AgentProjectWorkspace.jsx).
    """
    with ENGINE.begin() as conn:
        row = (
            conn.execute(
                text("""
                INSERT INTO app.projects (project_title, inclusion_criteria, project_mode)
                VALUES (:title, :inclusion_criteria, 'agent')
                RETURNING project_id
            """),
                {
                    "title": project_title or placeholder_project_title(),
                    "inclusion_criteria": inclusion_criteria,
                },
            )
            .mappings()
            .one()
        )
    project = get_project(str(row["project_id"]))
    assert project is not None
    return project


def create_agent_project_from_scope(scope_id: str) -> dict[str, Any]:
    """Starts a brand-new agent project + scoping conversation from someone else's finalized
    scope, seeded to resume directly at the review phase (see AgentProjectWorkspace.jsx's
    resume-index logic in `load()`, which jumps straight to search_review once the scoping
    conversation is already `completed`). Never reuses the source scope's project_id/
    conversation_id/scope_id - those belong to whoever created it, not whoever's starting fresh
    from it - only its `content` (and, if present, its title/description) is copied across.
    """
    source = get_scope_by_id(scope_id)
    if source is None:
        raise ValueError(f"No scope found for scope_id={scope_id!r}")

    with ENGINE.begin() as conn:
        row = (
            conn.execute(
                text("""
                INSERT INTO app.projects (project_title, inclusion_criteria, project_mode)
                VALUES (:title, NULL, 'agent')
                RETURNING project_id
            """),
                {"title": source.get("scope_title") or placeholder_project_title()},
            )
            .mappings()
            .one()
        )
    new_project_id = str(row["project_id"])

    conversation = get_or_create_conversation(new_project_id, "scoping", "agent")
    new_conversation_id = str(conversation["conversation_id"])
    upsert_scope(new_conversation_id, source["content"])
    if source.get("scope_title") or source.get("scope_description"):
        set_scope_metadata(new_conversation_id, source.get("scope_title"), source.get("scope_description"))
    set_conversation_completed(new_conversation_id, True)

    project = get_project(new_project_id)
    assert project is not None
    return project


def get_project(project_id: str) -> dict[str, Any] | None:
    with ENGINE.connect() as conn:
        project_row = (
            conn.execute(
                text("""
                SELECT project_id, project_title, inclusion_criteria,
                       embedding_run_id, project_mode, created_at, updated_at
                FROM app.projects WHERE project_id = :pid
            """),
                {"pid": project_id},
            )
            .mappings()
            .first()
        )
        if project_row is None:
            return None

        search_rows = (
            conn.execute(
                text("""
                SELECT search_id, project_id, query, n_results, created_at
                FROM app.searches WHERE project_id = :pid
                ORDER BY created_at ASC
            """),
                {"pid": project_id},
            )
            .mappings()
            .all()
        )

        result_rows = (
            conn.execute(
                text("""
                SELECT
                    sr.result_id, sr.search_id, sr.paper_id, sr.type, sr.search_rank,
                    sr.distance, sr.distance_type,
                    r.title, r.abstract, r.year, r.venue, r."citationCount" AS citation_count,
                    r.url, r."DOI" AS doi,
                    COALESCE((rv.content->>'included')::boolean, TRUE) AS included
                FROM app.search_results sr
                JOIN app.searches s ON s.search_id = sr.search_id
                JOIN raw.raw_paper_searches r ON r."paperId" = sr.paper_id
                LEFT JOIN app.conversations c ON c.project_id = s.project_id AND c.stage = 'review'
                LEFT JOIN app.reviews rv ON rv.conversation_id = c.conversation_id AND rv.paper_id = sr.paper_id
                WHERE s.project_id = :pid
                ORDER BY sr.search_id, sr.search_rank ASC
            """),
                {"pid": project_id},
            )
            .mappings()
            .all()
        )

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
    # Only filters on `k in allowed` - the router already limits `fields` to what the client
    # actually sent via `request.model_dump(exclude_unset=True)`, so an explicit `None` here
    # means the client asked to clear that field, not that it was omitted. Filtering out `None`
    # values on top of that (as this used to) silently ignored every clear-a-field request.
    allowed = {"project_title", "inclusion_criteria", "embedding_run_id"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_project(project_id)
    set_clause = ", ".join(f'"{k}" = :{k}' for k in updates)
    with ENGINE.begin() as conn:
        conn.execute(
            text(
                f'UPDATE app.projects SET {set_clause}, "updated_at" = NOW() WHERE project_id = :pid'
            ),
            {**updates, "pid": project_id},
        )
    return get_project(project_id)


def delete_project(project_id: str) -> None:
    with ENGINE.begin() as conn:
        conn.execute(
            text("DELETE FROM app.projects WHERE project_id = :pid"),
            {"pid": project_id},
        )


def create_search(project_id: str, query: str, n_results: int = 10) -> dict[str, Any]:
    """Creates (or, on conflict, refreshes n_results on) the app.searches row for this term."""
    with ENGINE.begin() as conn:
        row = (
            conn.execute(
                text("""
                INSERT INTO app.searches (project_id, query, n_results)
                VALUES (:project_id, :query, :n_results)
                ON CONFLICT (project_id, query) DO UPDATE SET n_results = EXCLUDED.n_results
                RETURNING search_id, project_id, query, n_results, created_at
            """),
                {"project_id": project_id, "query": query, "n_results": n_results},
            )
            .mappings()
            .one()
        )
    return dict(row)


def get_search(search_id: str) -> dict[str, Any] | None:
    with ENGINE.connect() as conn:
        search_row = (
            conn.execute(
                text("""
                SELECT search_id, project_id, query, n_results, created_at
                FROM app.searches WHERE search_id = :sid
            """),
                {"sid": search_id},
            )
            .mappings()
            .first()
        )
        if search_row is None:
            return None

        result_rows = (
            conn.execute(
                text("""
                SELECT
                    sr.result_id, sr.search_id, sr.paper_id, sr.type, sr.search_rank,
                    sr.distance, sr.distance_type,
                    r.title, r.abstract, r.year, r.venue, r."citationCount" AS citation_count,
                    r.url, r."DOI" AS doi,
                    COALESCE((rv.content->>'included')::boolean, TRUE) AS included
                FROM app.search_results sr
                JOIN app.searches s ON s.search_id = sr.search_id
                JOIN raw.raw_paper_searches r ON r."paperId" = sr.paper_id
                LEFT JOIN app.conversations c ON c.project_id = s.project_id AND c.stage = 'review'
                LEFT JOIN app.reviews rv ON rv.conversation_id = c.conversation_id AND rv.paper_id = sr.paper_id
                WHERE sr.search_id = :sid
                ORDER BY sr.search_rank ASC
            """),
                {"sid": search_id},
            )
            .mappings()
            .all()
        )

    return {**dict(search_row), "results": [dict(row) for row in result_rows]}


def delete_search(project_id: str, search_id: str) -> None:
    with ENGINE.begin() as conn:
        conn.execute(
            text(
                "DELETE FROM app.searches WHERE search_id = :sid AND project_id = :pid"
            ),
            {"sid": search_id, "pid": project_id},
        )


def save_search_results(
    search_id: str, rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Upserts vector_search() result rows for a search, ranked by their list order.

    Re-running a search updates rank/distance for papers still present rather than resetting
    them. Inclusion defaults to True at read time (see get_project/get_search's
    `COALESCE(..., TRUE)`) rather than being eagerly written here - a paper only gets an
    app.reviews row once someone actually reviews it.
    """
    inserted: list[dict[str, Any]] = []
    with ENGINE.begin() as conn:
        for rank, row in enumerate(rows, start=1):
            result = (
                conn.execute(
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
                )
                .mappings()
                .one()
            )
            inserted.append({"result_id": str(result["result_id"]), **row})
    return inserted


# --- Conversations / messages -----------------------------------------------------------

_VALID_STAGES = {"scoping", "review", "writing"}
_VALID_MODES = {"agent", "human"}


def get_conversation(project_id: str, stage: str) -> dict[str, Any] | None:
    with ENGINE.connect() as conn:
        row = (
            conn.execute(
                text("""
                SELECT conversation_id, project_id, stage, mode, completed, author,
                       created_at, updated_at
                FROM app.conversations WHERE project_id = :pid AND stage = :stage
            """),
                {"pid": project_id, "stage": stage},
            )
            .mappings()
            .first()
        )
    return dict(row) if row is not None else None


def get_or_create_conversation(project_id: str, stage: str, mode: str) -> dict[str, Any]:
    """Looked up by (project_id, stage) - a project has at most one conversation per stage (see
    conversations_project_stage_uniq), created lazily on first use. `mode` is only recorded on
    first creation (reflects how this stage's conversation started); it is not revised by later
    activity from the other mode, even though both modes may go on to write into the same
    conversation's messages/scope/reviews (see module docstring).
    """
    assert stage in _VALID_STAGES, f"Unknown stage {stage!r}"
    assert mode in _VALID_MODES, f"Unknown mode {mode!r}"
    with ENGINE.begin() as conn:
        row = (
            conn.execute(
                text("""
                INSERT INTO app.conversations (project_id, stage, mode)
                VALUES (:pid, :stage, :mode)
                ON CONFLICT (project_id, stage) DO UPDATE SET updated_at = app.conversations.updated_at
                RETURNING conversation_id, project_id, stage, mode, completed, author,
                          created_at, updated_at
            """),
                {"pid": project_id, "stage": stage, "mode": mode},
            )
            .mappings()
            .one()
        )
    return dict(row)


def set_conversation_completed(conversation_id: str, completed: bool = True) -> None:
    with ENGINE.begin() as conn:
        conn.execute(
            text("""
                UPDATE app.conversations SET completed = :completed, updated_at = NOW()
                WHERE conversation_id = :cid
            """),
            {"cid": conversation_id, "completed": completed},
        )


def list_messages(conversation_id: str) -> list[dict[str, Any]]:
    """Every turn in order. A turn that made a tool call carries that call's name and arguments
    joined in as "tool_name"/"tool_arguments" (both None for ordinary turns) - see app.tool_calls.
    """
    with ENGINE.connect() as conn:
        rows = (
            conn.execute(
                text("""
                SELECT m.message_id, m.conversation_id, m.role, m.content, m.created_at,
                       m.tool_call_id, t.tool_name, t.arguments AS tool_arguments
                FROM app.messages m
                LEFT JOIN app.tool_calls t ON t.tool_call_id = m.tool_call_id
                WHERE m.conversation_id = :cid ORDER BY m.seq ASC
            """),
                {"cid": conversation_id},
            )
            .mappings()
            .all()
        )
    return [dict(row) for row in rows]


def _insert_tool_call(conn: Any, tool_name: str, arguments: dict[str, Any]) -> str:
    """Logs one tool call, returning its id for the message that made it to point at."""
    return str(
        conn.execute(
            text("""
                INSERT INTO app.tool_calls (tool_name, arguments)
                VALUES (:name, :arguments)
                RETURNING tool_call_id
            """),
            {"name": tool_name, "arguments": json.dumps(arguments)},
        ).scalar_one()
    )


def add_message(
    conversation_id: str,
    role: str,
    content: str,
    tool_name: str | None = None,
    tool_arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with ENGINE.begin() as conn:
        tool_call_id = (
            _insert_tool_call(conn, tool_name, tool_arguments or {}) if tool_name else None
        )
        row = (
            conn.execute(
                text("""
                INSERT INTO app.messages (conversation_id, role, content, tool_call_id)
                VALUES (:cid, :role, :content, :tool_call_id)
                RETURNING message_id, conversation_id, role, content, tool_call_id, created_at
            """),
                {
                    "cid": conversation_id,
                    "role": role,
                    "content": content,
                    "tool_call_id": tool_call_id,
                },
            )
            .mappings()
            .one()
        )
    return dict(row)


def add_messages(conversation_id: str, messages: list[dict[str, Any]]) -> None:
    """Inserts turns in one transaction, preserving order via `seq`. Each entry is a
    {"role", "content"} dict, optionally carrying "tool_name"/"tool_arguments" for a turn that
    made a tool call - those are logged to app.tool_calls first, and the message points at the
    resulting row.
    """
    if not messages:
        return
    with ENGINE.begin() as conn:
        for message in messages:
            tool_name = message.get("tool_name")
            tool_call_id = (
                _insert_tool_call(conn, tool_name, message.get("tool_arguments") or {})
                if tool_name
                else None
            )
            conn.execute(
                text("""
                    INSERT INTO app.messages (conversation_id, role, content, tool_call_id)
                    VALUES (:cid, :role, :content, :tool_call_id)
                """),
                {
                    "cid": conversation_id,
                    "role": message["role"],
                    "content": message["content"],
                    "tool_call_id": tool_call_id,
                },
            )


# --- Scopes -------------------------------------------------------------------------------


def get_scope(conversation_id: str) -> dict[str, Any] | None:
    with ENGINE.connect() as conn:
        row = (
            conn.execute(
                text("""
                SELECT scope_id, conversation_id, content, scope_title, scope_description,
                       created_at, updated_at
                FROM app.scopes WHERE conversation_id = :cid
            """),
                {"cid": conversation_id},
            )
            .mappings()
            .first()
        )
    return dict(row) if row is not None else None


def get_scope_by_id(scope_id: str) -> dict[str, Any] | None:
    with ENGINE.connect() as conn:
        row = (
            conn.execute(
                text("""
                SELECT scope_id, conversation_id, content, scope_title, scope_description,
                       created_at, updated_at
                FROM app.scopes WHERE scope_id = :sid
            """),
                {"sid": scope_id},
            )
            .mappings()
            .first()
        )
    return dict(row) if row is not None else None


def list_recent_scopes(search: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
    """Recently-finalized scopes from any completed scoping conversation, newest-updated first -
    for the agent landing page's "start review from an existing scope" list. Only completed
    scoping conversations are eligible - an in-progress scope isn't a finished artifact yet.
    `content` is included so the frontend can expand a row without a second round-trip.
    """
    where = ["c.\"stage\" = 'scoping'", 'c."completed" = TRUE']
    params: dict[str, Any] = {"limit": limit}
    if search:
        where.append(
            '(sc."scope_title" ILIKE :pattern OR sc."scope_description" ILIKE :pattern '
            'OR p."project_title" ILIKE :pattern)'
        )
        params["pattern"] = f"%{search}%"
    sql = text(f"""
        SELECT sc.scope_id, sc.scope_title, sc.scope_description, sc.content,
               p.project_title AS source_project_title, sc.created_at, sc.updated_at
        FROM app.scopes sc
        JOIN app.conversations c ON c.conversation_id = sc.conversation_id
        JOIN app.projects p ON p.project_id = c.project_id
        WHERE {' AND '.join(where)}
        ORDER BY sc.updated_at DESC
        LIMIT :limit
    """)
    with ENGINE.connect() as conn:
        rows = conn.execute(sql, params).mappings().all()
    return [dict(row) for row in rows]


def set_scope_metadata(
    conversation_id: str, scope_title: str | None, scope_description: str | None
) -> dict[str, Any] | None:
    with ENGINE.begin() as conn:
        row = (
            conn.execute(
                text("""
                UPDATE app.scopes SET scope_title = :title, scope_description = :description,
                       updated_at = NOW()
                WHERE conversation_id = :cid
                RETURNING scope_id, conversation_id, content, scope_title, scope_description,
                          created_at, updated_at
            """),
                {"cid": conversation_id, "title": scope_title, "description": scope_description},
            )
            .mappings()
            .first()
        )
    return dict(row) if row is not None else None


def upsert_scope(conversation_id: str, content: dict[str, Any]) -> dict[str, Any]:
    """Replaces the conversation's scope wholesale, matching
    ScopingMemoryObject.update_scope's "always a full replacement" semantics."""
    with ENGINE.begin() as conn:
        row = (
            conn.execute(
                text("""
                INSERT INTO app.scopes (conversation_id, content)
                VALUES (:cid, CAST(:content AS jsonb))
                ON CONFLICT (conversation_id)
                DO UPDATE SET content = EXCLUDED.content, updated_at = NOW()
                RETURNING scope_id, conversation_id, content, created_at, updated_at
            """),
                {"cid": conversation_id, "content": json.dumps(content)},
            )
            .mappings()
            .one()
        )
    return dict(row)


# --- Reviews --------------------------------------------------------------------------------


def get_review(conversation_id: str, paper_id: str) -> dict[str, Any] | None:
    with ENGINE.connect() as conn:
        row = (
            conn.execute(
                text("""
                SELECT review_id, conversation_id, paper_id, content, created_at, updated_at
                FROM app.reviews WHERE conversation_id = :cid AND paper_id = :pid
            """),
                {"cid": conversation_id, "pid": paper_id},
            )
            .mappings()
            .first()
        )
    return dict(row) if row is not None else None


def list_reviews(conversation_id: str) -> list[dict[str, Any]]:
    with ENGINE.connect() as conn:
        rows = (
            conn.execute(
                text("""
                SELECT review_id, conversation_id, paper_id, content, created_at, updated_at
                FROM app.reviews WHERE conversation_id = :cid
            """),
                {"cid": conversation_id},
            )
            .mappings()
            .all()
        )
    return [dict(row) for row in rows]


def upsert_review(conversation_id: str, paper_id: str, content: dict[str, Any]) -> dict[str, Any]:
    """Merges `content` into the paper's existing review (JSONB `||`, not a clobber) so e.g. a
    checkbox flip ({"reviewed": true, "included": false}) never wipes out inclusion_reasoning
    an agent already recorded, and vice versa."""
    with ENGINE.begin() as conn:
        row = (
            conn.execute(
                text("""
                INSERT INTO app.reviews (conversation_id, paper_id, content)
                VALUES (:cid, :pid, CAST(:content AS jsonb))
                ON CONFLICT (conversation_id, paper_id)
                DO UPDATE SET content = app.reviews.content || EXCLUDED.content, updated_at = NOW()
                RETURNING review_id, conversation_id, paper_id, content, created_at, updated_at
            """),
                {"cid": conversation_id, "pid": paper_id, "content": json.dumps(content)},
            )
            .mappings()
            .one()
        )
    return dict(row)


def delete_review(conversation_id: str, paper_id: str) -> None:
    with ENGINE.begin() as conn:
        conn.execute(
            text("DELETE FROM app.reviews WHERE conversation_id = :cid AND paper_id = :pid"),
            {"cid": conversation_id, "pid": paper_id},
        )


def set_inclusion(result_id: str, included: bool) -> None:
    """Resolves result_id to (project_id, paper_id) and upserts the shared review verdict for
    that paper - keyed by paper, not by search result, so the same paper found via two
    different queries always carries exactly one verdict (see module docstring)."""
    with ENGINE.connect() as conn:
        row = (
            conn.execute(
                text("""
                SELECT s.project_id, sr.paper_id FROM app.search_results sr
                JOIN app.searches s ON s.search_id = sr.search_id
                WHERE sr.result_id = :rid
            """),
                {"rid": result_id},
            )
            .mappings()
            .first()
        )
    if row is None:
        raise ValueError(f"No search result found for result_id={result_id!r}")
    conversation = get_or_create_conversation(str(row["project_id"]), "review", "human")
    upsert_review(str(conversation["conversation_id"]), row["paper_id"], {"reviewed": True, "included": included})


def set_inclusion_bulk(project_id: str, items: list[dict[str, Any]]) -> int:
    if not items:
        return 0
    conversation = get_or_create_conversation(project_id, "review", "human")
    with ENGINE.connect() as conn:
        result_ids = [item["result_id"] for item in items]
        rows = (
            conn.execute(
                text("""
                SELECT sr.result_id, sr.paper_id FROM app.search_results sr
                WHERE sr.result_id = ANY(:rids)
            """),
                {"rids": result_ids},
            )
            .mappings()
            .all()
        )
    paper_id_by_result = {str(r["result_id"]): r["paper_id"] for r in rows}
    for item in items:
        paper_id = paper_id_by_result.get(str(item["result_id"]))
        if paper_id is None:
            raise ValueError(f"No search result found for result_id={item['result_id']!r}")
        upsert_review(
            str(conversation["conversation_id"]), paper_id, {"reviewed": True, "included": item["included"]}
        )
    return len(items)


# --- Written papers ---------------------------------------------------------------------


def list_written_papers(project_id: str) -> list[dict[str, Any]]:
    with ENGINE.connect() as conn:
        rows = (
            conn.execute(
                text("""
                SELECT written_paper_id, project_id, agent_version, content, created_at, updated_at
                FROM app.written_papers WHERE project_id = :pid ORDER BY created_at DESC
            """),
                {"pid": project_id},
            )
            .mappings()
            .all()
        )
    return [dict(row) for row in rows]


def get_latest_written_paper(project_id: str) -> dict[str, Any] | None:
    papers = list_written_papers(project_id)
    return papers[0] if papers else None


def create_written_paper(
    project_id: str, content: str, agent_version: str | None = None
) -> dict[str, Any]:
    with ENGINE.begin() as conn:
        row = (
            conn.execute(
                text("""
                INSERT INTO app.written_papers (project_id, agent_version, content)
                VALUES (:pid, :agent_version, :content)
                RETURNING written_paper_id, project_id, agent_version, content, created_at, updated_at
            """),
                {"pid": project_id, "agent_version": agent_version, "content": content},
            )
            .mappings()
            .one()
        )
    return dict(row)
