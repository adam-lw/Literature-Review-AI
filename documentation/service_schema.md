# Service Schema — Entity Relationship Diagram

```mermaid
erDiagram
    raw_paper_searches {
        TEXT paperId PK
        TEXT title
        TEXT abstract
        TEXT venue
        INTEGER year
        INTEGER citationCount
        INTEGER influentialCitationCount
        JSONB fieldsOfStudy
        BOOLEAN isOpenAccess
        JSONB publicationTypes
        TEXT url
        TEXT status
        TEXT ArXiV
        TEXT DBLP
        TEXT MAG
        TEXT DOI
        TIMESTAMPTZ collected_at
        TIMESTAMPTZ last_updated
    }

    full_papers {
        TEXT paperId PK
        TEXT full_text
        TEXT pdf_url
        TIMESTAMPTZ collected_at
    }

    processed_abstracts {
        TEXT paperId PK, FK
        TEXT title
        TEXT abstract
        INTEGER abstract_length
        INTEGER word_count
        BOOLEAN has_formula
        TEXT language
        TEXT content_hash
        TIMESTAMPTZ processed_at
    }

    embedding_runs_metadata {
        BIGINT run_id PK
        TIMESTAMPTZ ran_at
        TEXT embedding_model
        TEXT embedding_version
        INTEGER n_dim
        JSONB user_tags
        TEXT source
    }

    abstract_embeddings {
        TEXT paperId PK, FK
        BIGINT run_id PK, FK
        TIMESTAMPTZ processed_at
        TEXT content_hash
    }

    raw_paper_searches ||--o| full_papers : "paperId (optional full text)"
    raw_paper_searches ||--o| processed_abstracts : "paperId (1:1 cleaned abstract)"
    raw_paper_searches ||--o{ abstract_embeddings : "paperId (many embeddings per paper)"
    embedding_runs_metadata ||--o{ abstract_embeddings : "run_id (many papers per run)"
```

## Schema overview

Two PostgreSQL schemas organise the tables:

| Schema | Purpose |
|---|---|
| `raw` | Data as received from upstream sources (Semantic Scholar API, open-access PDFs) |
| `processed` | Cleaned, enriched, and derived data produced by internal pipelines |

### Tables

| Table | Schema | Description |
|---|---|---|
| `raw_paper_searches` | `raw` | Papers retrieved from the Semantic Scholar bulk-search API. Central entity; all processed tables FK back here. |
| `full_papers` | `raw` | Full paper text downloaded from open-access PDF sources. Optional 1:1 with `raw_paper_searches`. |
| `processed_abstracts` | `processed` | Cleaned and enriched abstracts. Strict 1:1 with `raw_paper_searches`. |
| `embedding_runs_metadata` | `processed` | One row per distinct embedding run (model + version + dims + tags). Has a unique index to deduplicate runs. |
| `abstract_embeddings` | `processed` | Abstract embedding vectors. One row per (paperId, run_id). Embedding vector columns (e.g. `embedding_768 VECTOR(768)`) are added dynamically via `ALTER TABLE` when a new model dimension is first seen. |
