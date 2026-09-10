-- literature-ai application layer schema.
-- Requires the core service schema (service_schema.sql) to be applied first,
-- as app.search_results references raw.raw_paper_searches.

CREATE SCHEMA IF NOT EXISTS app;

CREATE TABLE IF NOT EXISTS app.projects (
    "project_id"         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "project_title"      TEXT NOT NULL,
    "description"        TEXT,
    "inclusion_criteria" TEXT,
    "embedding_run_id"   INTEGER REFERENCES processed.embedding_runs_metadata("run_id"),
    "created_at"         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    "updated_at"         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Distinguishes an "agent-created" project (no manual search/review UI, routes to
-- AgentProjectWorkspace) from a "human-created" one (has manual search/review UI plus an
-- optional agent-flow toggle, routes to ProjectWorkspace) - purely for frontend routing, set
-- once at creation. NOT to be confused with app.conversations.mode below, which is
-- per-conversation and can differ from this within the same project (e.g. a human-mode
-- project's review conversation can still be touched by the agent flow via the mode toggle).
ALTER TABLE app.projects
    ADD COLUMN IF NOT EXISTS "project_mode" TEXT NOT NULL DEFAULT 'human'
    CHECK ("project_mode" IN ('human', 'agent'));

CREATE TABLE IF NOT EXISTS app.searches (
    "search_id"  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "project_id" UUID NOT NULL REFERENCES app.projects("project_id") ON DELETE CASCADE,
    "query"      TEXT NOT NULL,
    "n_results"  INTEGER NOT NULL DEFAULT 10,
    "created_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS searches_project_query_uniq
    ON app.searches ("project_id", "query");
CREATE INDEX IF NOT EXISTS searches_project_id_idx ON app.searches ("project_id");

CREATE TABLE IF NOT EXISTS app.search_results (
    "result_id"     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "search_id"     UUID NOT NULL REFERENCES app.searches("search_id") ON DELETE CASCADE,
    "paper_id"      TEXT NOT NULL REFERENCES raw.raw_paper_searches("paperId"),
    "type"          TEXT NOT NULL CHECK ("type" IN ('embedding', 'keyword', 'hybrid')),
    "search_rank"   INTEGER NOT NULL,
    "distance"      FLOAT,
    "distance_type" TEXT DEFAULT 'cosine'
);

CREATE UNIQUE INDEX IF NOT EXISTS search_results_uniq
    ON app.search_results ("search_id", "type", "paper_id");
CREATE INDEX IF NOT EXISTS search_results_search_id_idx ON app.search_results ("search_id");

-- Retired by the conversations/reviews persistence migration - superseded by
-- app.conversations / app.scopes / app.reviews / app.written_papers below. No production data
-- existed under the old schema (paper_inclusion_exclusion was keyed per search-result rather
-- than per paper, so the same paper found via two queries could carry two different flags,
-- and paper_summarisations and outputs never had a write path at all) - this is a clean-slate
-- rebuild, not a data-preserving ALTER migration. Left in permanently since apply_schema() is
-- this project's entire migration mechanism (no Alembic) - these DROPs simply no-op once run.
DROP TABLE IF EXISTS app.paper_inclusion_exclusion CASCADE;
DROP TABLE IF EXISTS app.paper_summarisations CASCADE;
DROP TABLE IF EXISTS app.outputs CASCADE;

-- One conversation per (project, stage). "stage" collapses the API-layer <phase>/<phase>_chat
-- distinction - both e.g. a "search_review" and a "review_chat" call for a project log into
-- the single stage='review' row here. "mode" is recorded only when the conversation is first
-- created (which surface started it), and is not revised by later cross-mode activity - see
-- app.reviews below for why a single conversation is deliberately shared across modes.
CREATE TABLE IF NOT EXISTS app.conversations (
    "conversation_id" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "project_id"       UUID NOT NULL REFERENCES app.projects("project_id") ON DELETE CASCADE,
    "stage"            TEXT NOT NULL CHECK ("stage" IN ('scoping', 'review', 'writing')),
    "mode"             TEXT NOT NULL CHECK ("mode" IN ('agent', 'human')),
    "completed"        BOOLEAN NOT NULL DEFAULT FALSE,
    "author"           TEXT,
    "created_at"       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    "updated_at"       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS conversations_project_stage_uniq
    ON app.conversations ("project_id", "stage");

-- Every tool call any agent has ever made, stored structurally rather than flattened into the
-- text of the turn that made it - which is what used to leak a raw "Called tool `ask_user`
-- with arguments {...}" string into the UI when a conversation was reloaded. Deliberately not
-- scoped to a conversation: app.messages.tool_call_id is what ties a call to its turn.
CREATE TABLE IF NOT EXISTS app.tool_calls (
    "tool_call_id" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "tool_name"    TEXT NOT NULL,
    "arguments"    JSONB NOT NULL DEFAULT '{}'::jsonb,
    "created_at"   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Every turn of every conversation - both the phase-driving agent and its "_chat" companion,
-- for scoping/review/writing, human and agent mode alike. The system prompt is never stored
-- here (see agent_service/agent/agent/spawn_agent.py) - it's rebuilt fresh from (stage,
-- memory) on every call rather than persisted/resent, so "role" excludes 'system' on purpose.
CREATE TABLE IF NOT EXISTS app.messages (
    "message_id"      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "conversation_id" UUID NOT NULL REFERENCES app.conversations("conversation_id") ON DELETE CASCADE,
    "seq"             BIGSERIAL,
    "role"            TEXT NOT NULL CHECK ("role" IN ('user', 'assistant', 'tool')),
    "content"         TEXT NOT NULL,
    "created_at"      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS messages_conversation_seq_idx ON app.messages ("conversation_id", "seq");

-- Set when a turn was the model reaching for a tool rather than speaking to the user: "content"
-- then holds only the thinking that led to the call (empty string when it thought silently),
-- and the call itself lives in app.tool_calls. This is what lets a conversation be replayed and
-- re-rendered mid-tool-call - most visibly an `ask_user` question, which the frontend rebuilds
-- into a question card from the call's arguments instead of printing the turn as chat text.
ALTER TABLE app.messages
    ADD COLUMN IF NOT EXISTS "tool_call_id" UUID REFERENCES app.tool_calls("tool_call_id");

-- The scoping conversation's finalized (or since-revised) specification. One row per
-- conversation, upserted wholesale - matches ScopingMemoryObject.update_scope's "always a
-- full replacement" semantics, so there's no revision history here, just the current value.
CREATE TABLE IF NOT EXISTS app.scopes (
    "scope_id"        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "conversation_id" UUID NOT NULL REFERENCES app.conversations("conversation_id") ON DELETE CASCADE,
    "content"         JSONB NOT NULL,
    "created_at"      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    "updated_at"      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS scopes_conversation_id_uniq ON app.scopes ("conversation_id");

-- One shared verdict per (project, paper): since app.conversations enforces at most one
-- 'review'-stage conversation per project, both human checkbox toggles and agent tool calls
-- upsert into the SAME conversation's rows here, fixing the old per-result_id duplicate-flag
-- bug (the same paper found via two search queries now has exactly one verdict). "content"
-- mirrors AgentPaperReviewMemory's PaperReview shape (agent_service/agent/memory/paper_review.py):
-- {"reviewed": bool, "included": bool, "inclusion_reasoning": {criterion: {"passed": bool, "reason": str}}}
CREATE TABLE IF NOT EXISTS app.reviews (
    "review_id"       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "conversation_id" UUID NOT NULL REFERENCES app.conversations("conversation_id") ON DELETE CASCADE,
    "paper_id"        TEXT NOT NULL REFERENCES raw.raw_paper_searches("paperId"),
    "content"         JSONB NOT NULL DEFAULT '{}'::jsonb,
    "created_at"      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    "updated_at"      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS reviews_conversation_paper_uniq ON app.reviews ("conversation_id", "paper_id");
CREATE INDEX IF NOT EXISTS reviews_paper_id_idx ON app.reviews ("paper_id");

-- The final generated literature-review document. A project-level durable artifact (unlike
-- the 'writing' conversation, which is ephemeral working state) - not unique per project, so
-- every draft/regeneration is kept - read the latest by created_at. Replaces app.outputs.
CREATE TABLE IF NOT EXISTS app.written_papers (
    "written_paper_id" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "project_id"        UUID NOT NULL REFERENCES app.projects("project_id") ON DELETE CASCADE,
    "agent_version"      TEXT,
    "content"            TEXT,
    "created_at"         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    "updated_at"         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS written_papers_project_id_idx ON app.written_papers ("project_id");
