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

-- Postgres full-text search vectors derived from processed.processed_abstracts
-- (title+abstract), built incrementally by processing/build_keyword_vectors.py.
-- Separate 1:1 table rather than a column on processed_abstracts itself, mirroring
-- abstract_embeddings' relationship to processed_abstracts. Title weighted 'A'
-- (higher), abstract 'B'. GIN index created via processing/create_index.py's
-- create_keyword_search_index(), same workflow as the HNSW indices below.
CREATE TABLE IF NOT EXISTS processed.abstract_keyword_vectors (
    "paperId"       TEXT PRIMARY KEY REFERENCES processed.processed_abstracts("paperId"),
    "search_vector" tsvector NOT NULL,
    "content_hash"  TEXT,
    "processed_at"  TIMESTAMP WITH TIME ZONE NOT NULL
);

-- Metadata for each distinct embedding run (unique combination of model + version +
-- dims + tags + target). "target" distinguishes abstract-embedding runs from
-- full-paper-chunk-embedding runs sharing this table.
CREATE TABLE IF NOT EXISTS processed.embedding_runs_metadata (
    "run_id"            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    "ran_at"            TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    "embedding_model"   TEXT NOT NULL,
    "embedding_version" TEXT,
    "n_dim"             INTEGER NOT NULL,
    "user_tags"         JSONB NOT NULL DEFAULT '{}',
    "source"            TEXT NOT NULL CHECK ("source" IN ('collect', 'generate')),
    "target"            TEXT NOT NULL DEFAULT 'abstract' CHECK ("target" IN ('abstract', 'chunk'))
);

-- Handles NULL embedding_version correctly via COALESCE.
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

-- One row per chunk. Chunks don't store their own text - "start_index"/"end_index" are
-- character offsets into the parent raw.paper_fulltext.full_text row, substringed out on
-- read. "embedding" is a single fixed-model vector (text-embedding-3-small, 1536 dims) -
-- unlike abstract_embeddings, there's no per-run/multi-model tracking here.
CREATE TABLE IF NOT EXISTS processed.paper_chunks (
    "paperId"        TEXT NOT NULL REFERENCES raw.raw_paper_searches("paperId"),
    "chunk_index"    INTEGER NOT NULL,
    "section_index"  INTEGER,
    "section_header" TEXT,
    "start_index"    INTEGER NOT NULL,
    "end_index"      INTEGER NOT NULL,
    "char_count"     INTEGER NOT NULL,
    "embedding"      VECTOR(1536),
    "chunked_at"     TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY ("paperId", "chunk_index")
);