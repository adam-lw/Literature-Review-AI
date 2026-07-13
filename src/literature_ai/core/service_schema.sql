-- literature-ai core service data model. Run once against a fresh database.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS processed;

-- Papers retrieved from the Semantic Scholar bulk-search API.
CREATE TABLE IF NOT EXISTS raw.raw_paper_searches (
    "paperId"                  TEXT PRIMARY KEY,
    "title"                    TEXT,
    "abstract"                 TEXT,
    "venue"                    TEXT,
    "year"                     INTEGER,
    "citationCount"            INTEGER,
    "influentialCitationCount" INTEGER,
    "fieldsOfStudy"            JSONB,
    "isOpenAccess"             BOOLEAN,
    "publicationTypes"         JSONB,
    -- openAccessPdf expanded
    "url"                      TEXT,
    "status"                   TEXT,
    -- externalIds expanded
    "ArXiV"                    TEXT,
    "DBLP"                     TEXT,
    "MAG"                      TEXT,
    "DOI"                      TEXT,
    "collected_at"             TIMESTAMP WITH TIME ZONE NOT NULL,
    -- set on insert, updated only when row content actually changes
    "last_updated"             TIMESTAMP WITH TIME ZONE
);

-- Full paper texts downloaded from open-access PDF sources.
CREATE TABLE IF NOT EXISTS raw.full_papers (
    "paperId"       TEXT PRIMARY KEY,
    "full_text"     TEXT,
    "pdf_url"       TEXT,
    "collected_at"  TIMESTAMP WITH TIME ZONE NOT NULL
);

-- Cleaned and enriched abstracts. 1:1 with raw.raw_paper_searches.
CREATE TABLE IF NOT EXISTS processed.processed_abstracts (
    "paperId"           TEXT PRIMARY KEY REFERENCES raw.raw_paper_searches("paperId"),
    "title"             TEXT,
    "abstract"          TEXT,
    "abstract_length"   INTEGER,
    "word_count"        INTEGER,
    "has_formula"       BOOLEAN,
    "language"          TEXT,
    "content_hash"      TEXT,
    "processed_at"      TIMESTAMP WITH TIME ZONE
);

-- Metadata for each distinct embedding run (unique combination of model + version + dims + tags).
CREATE TABLE IF NOT EXISTS processed.embedding_runs_metadata (
    "run_id"            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    "ran_at"            TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    "embedding_model"   TEXT NOT NULL,
    "embedding_version" TEXT,
    "n_dim"             INTEGER NOT NULL,
    "user_tags"         JSONB NOT NULL DEFAULT '{}',
    "source"            TEXT NOT NULL CHECK ("source" IN ('collect', 'generate'))
);

-- Handles NULL embedding_version correctly via COALESCE.
CREATE UNIQUE INDEX IF NOT EXISTS embedding_runs_metadata_unique
    ON processed.embedding_runs_metadata (
        "embedding_model",
        COALESCE("embedding_version", ''),
        "n_dim",
        "user_tags",
        "source"
    );

-- Abstract embeddings. One row per (paperId, run_id). Embedding columns (e.g. embedding_768
-- VECTOR(768)) are added dynamically via ALTER TABLE when a new model dimension is first seen.
CREATE TABLE IF NOT EXISTS processed.abstract_embeddings (
    "paperId"       TEXT NOT NULL REFERENCES raw.raw_paper_searches("paperId"),
    "run_id"        BIGINT NOT NULL REFERENCES processed.embedding_runs_metadata("run_id"),
    "processed_at"  TIMESTAMP WITH TIME ZONE,
    "content_hash"  TEXT,
    PRIMARY KEY ("paperId", "run_id")
);