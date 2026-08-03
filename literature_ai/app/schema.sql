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

CREATE TABLE IF NOT EXISTS app.paper_inclusion_exclusion (
    "result_id" UUID PRIMARY KEY REFERENCES app.search_results("result_id") ON DELETE CASCADE,
    "included"  BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS app.paper_summarisations (
    "summarisation_id" UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "project_id"        UUID REFERENCES app.projects("project_id") ON DELETE CASCADE,
    "paper_id"          TEXT REFERENCES raw.raw_paper_searches("paperId"),
    "summary"           TEXT,
    "model"             TEXT,
    "created_at"        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS paper_summarisations_project_paper_uniq
    ON app.paper_summarisations ("project_id", "paper_id");

CREATE TABLE IF NOT EXISTS app.outputs (
    "output_id"  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "project_id" UUID REFERENCES app.projects("project_id") ON DELETE CASCADE,
    "kind"       TEXT,
    "content"    TEXT,
    "created_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    "updated_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
