-- literature-ai application layer schema.
-- Requires the core service schema (service_schema.sql) to be applied first,
-- as app.search_results references raw.raw_paper_searches.

CREATE SCHEMA IF NOT EXISTS app;

CREATE TABLE IF NOT EXISTS app.projects (
    "project_id"    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "created_at"    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    "project_title" TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app.searches (
    "search_id"  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "project_id" UUID NOT NULL REFERENCES app.projects("project_id") ON DELETE CASCADE,
    "query"      TEXT NOT NULL,
    "created_at" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS app.search_results (
    "result_id"     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "search_id"     UUID NOT NULL REFERENCES app.searches("search_id") ON DELETE CASCADE,
    "type"          TEXT NOT NULL CHECK ("type" IN ('embedding', 'keyword', 'ranking')),
    "search_rank"   INTEGER NOT NULL,
    "distance"      FLOAT,
    "distance_type" TEXT DEFAULT 'cosine',
    -- paper_id returned by the core microservice API
    "paper_id"      TEXT NOT NULL REFERENCES raw.raw_paper_searches("paperId")
);

CREATE TABLE IF NOT EXISTS app.paper_inclusion_exclusion (
    "result_id" UUID PRIMARY KEY REFERENCES app.search_results("result_id") ON DELETE CASCADE,
    "included"  BOOLEAN NOT NULL
);

-- Placeholder tables for future features
CREATE TABLE IF NOT EXISTS app.paper_summarisations (
    "summarisation_id" UUID PRIMARY KEY DEFAULT gen_random_uuid()
);

CREATE TABLE IF NOT EXISTS app.outputs (
    "output_id" UUID PRIMARY KEY DEFAULT gen_random_uuid()
);
