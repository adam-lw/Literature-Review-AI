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

    paper_fulltext {
        TEXT paperId PK, FK
        TEXT status
        TEXT pdf_url
        TEXT full_text
        TEXT tei_xml
        TEXT grobid_version
        TIMESTAMPTZ parsed_at
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
        TEXT target
    }

    abstract_embeddings {
        TEXT paperId PK, FK
        BIGINT run_id PK, FK
        TIMESTAMPTZ processed_at
        TEXT content_hash
    }

    paper_chunks {
        TEXT paperId PK, FK
        INTEGER chunk_index PK
        INTEGER section_index
        TEXT section_header
        INTEGER start_index
        INTEGER end_index
        INTEGER char_count
        VECTOR embedding
        TIMESTAMPTZ chunked_at
    }

    raw_paper_searches ||--o| paper_fulltext : "paperId (optional GROBID-parsed full text)"
    raw_paper_searches ||--o| processed_abstracts : "paperId (1:1 cleaned abstract)"
    raw_paper_searches ||--o{ abstract_embeddings : "paperId (many embeddings per paper)"
    raw_paper_searches ||--o{ paper_chunks : "paperId (many chunks per paper)"
    embedding_runs_metadata ||--o{ abstract_embeddings : "run_id, target='abstract'"
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
| `paper_fulltext` | `raw` | Full paper text parsed from open-access PDFs via GROBID, fetched and cached on demand. Optional 1:1 with `raw_paper_searches`; `status` is `success` or `no_pdf_available` (transient fetch/parse failures are never persisted). |
| `processed_abstracts` | `processed` | Cleaned and enriched abstracts. Strict 1:1 with `raw_paper_searches`. |
| `embedding_runs_metadata` | `processed` | One row per distinct embedding run (model + version + dims + tags + target). Shared between abstract and chunk embedding runs; `target` (`abstract` or `chunk`) disambiguates which physical embeddings table a run's vectors live in. Has a unique index to deduplicate runs. |
| `abstract_embeddings` | `processed` | Abstract embedding vectors. One row per (paperId, run_id). Embedding vector columns (e.g. `embedding_768 VECTOR(768)`) are added dynamically via `ALTER TABLE` when a new model dimension is first seen. |
| `paper_chunks` | `processed` | Full-paper text chunked from GROBID-parsed body text. One row per (paperId, chunk_index). Stores no text of its own - `start_index`/`end_index` are character offsets into the parent `paper_fulltext.full_text` row, substringed out on read. `embedding` is a single fixed-model vector (`text-embedding-3-small`, 1536 dims), computed once by `process_papers_by_id` - no per-run/multi-model tracking like `abstract_embeddings`. Immutable once written; a manual delete forces re-chunking. |
