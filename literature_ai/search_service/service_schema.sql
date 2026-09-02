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

-- Full paper text parsed from open-access PDFs via GROBID. Optional 1:1 with
-- raw_paper_searches. status distinguishes a successful parse from a paper with no
-- resolvable PDF (both are stable, cacheable outcomes). Transient fetch/parse failures are
-- never written here so they retry on next request.
CREATE TABLE IF NOT EXISTS raw.paper_fulltext (
    "paperId"        TEXT PRIMARY KEY REFERENCES raw.raw_paper_searches("paperId"),
    "status"         TEXT NOT NULL CHECK ("status" IN ('success', 'no_pdf_available')),
    "pdf_url"        TEXT,
    "full_text"      TEXT,
    "tei_xml"        TEXT,
    "grobid_version" TEXT,
    "parsed_at"      TIMESTAMP WITH TIME ZONE NOT NULL
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

-- Discriminates abstract-embedding runs from full-paper-chunk-embedding runs sharing
-- this same run-bookkeeping table. Existing rows default to 'abstract' since every run
-- created before this column existed was an abstract run.
ALTER TABLE processed.embedding_runs_metadata
    ADD COLUMN IF NOT EXISTS "target" TEXT NOT NULL DEFAULT 'abstract'
        CHECK ("target" IN ('abstract', 'chunk'));

-- Handles NULL embedding_version correctly via COALESCE. Rebuilt (rather than just
-- ALTERed) to include target: without it, an abstract run and a chunk run sharing the
-- same model/version/n_dim/tags/source would wrongly collide as duplicates. This table
-- is tiny (one row per experiment run), so dropping and recreating the index on every
-- apply_schema() call (i.e. every app startup) is cheap.
DROP INDEX IF EXISTS processed.embedding_runs_metadata_unique;
CREATE UNIQUE INDEX IF NOT EXISTS embedding_runs_metadata_unique
    ON processed.embedding_runs_metadata (
        "target",
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

-- Chunked full-paper text, split from GROBID-parsed body text (raw.paper_fulltext).
-- One row per (paperId, chunk_index), computed on demand the first time a paper is
-- requested for chunk-scoped RAG search. There is no content-hash-based incremental
-- update here (unlike abstract_embeddings): raw.paper_fulltext.full_text never changes
-- after first parse, so "any rows exist for paperId" is a sufficient cache check.
-- Re-chunking (e.g. after a chunking-algorithm change) is a manual delete of a
-- paper's rows here (there is no automatic invalidation, matching
-- raw.paper_fulltext's own lack of one).
CREATE TABLE IF NOT EXISTS processed.paper_chunks (
    "paperId"        TEXT NOT NULL REFERENCES raw.raw_paper_searches("paperId"),
    "chunk_index"    INTEGER NOT NULL,
    "section_index"  INTEGER,
    "section_header" TEXT,
    "chunk_text"     TEXT NOT NULL,
    "char_count"     INTEGER NOT NULL,
    "content_hash"   TEXT NOT NULL,
    "chunked_at"     TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY ("paperId", "chunk_index")
);

-- Chunk embeddings. Cannot reuse abstract_embeddings - its primary key is one row per
-- paper, but chunks need many rows per paper - so this has its own composite key.
-- What IS shared with abstract_embeddings is embedding_runs_metadata (via
-- target='chunk') and the dynamically-added embedding_{n_dim} column pattern.
-- ON DELETE CASCADE cleans up embeddings automatically if paper_chunks rows are
-- manually deleted to force re-chunking.
CREATE TABLE IF NOT EXISTS processed.chunk_embeddings (
    "paperId"       TEXT NOT NULL,
    "chunk_index"   INTEGER NOT NULL,
    "run_id"        BIGINT NOT NULL REFERENCES processed.embedding_runs_metadata("run_id"),
    "processed_at"  TIMESTAMP WITH TIME ZONE,
    "content_hash"  TEXT,
    PRIMARY KEY ("paperId", "chunk_index", "run_id"),
    FOREIGN KEY ("paperId", "chunk_index")
        REFERENCES processed.paper_chunks ("paperId", "chunk_index") ON DELETE CASCADE
);