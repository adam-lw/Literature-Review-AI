# Bulk Search API

https://api.semanticscholar.org/api-docs/?utm_source=chatgpt.com#tag/Paper-Data/operation/get_graph_paper_bulk_search

Endpoint: https://api.semanticscholar.org/graph/v1/paper/search/bulk
## Keys

- query: (required) Keyword-based search across title & abstract for papers
- token: continuation token
- fields: fields to return
- sort
- publicationTypes
- openAccessPdf
- minCitationCount
- publicationDateOrYear
- year
- venue
- fieldsOfStudy

## Available Fields

**Identifiers & Links**

- `paperId` — Unique Semantic Scholar paper identifier (always included). 
    
- `url` — URL of the paper’s Semantic Scholar page. 
    

**Basic Metadata**

- `title` — Paper title. 
    
- `abstract` — Abstract text. 
    
- `year` — Publication year. 
    
- `publicationDate` — Full publication date (may be null). 
    
- `venue` — Where it was published (conference/journal). 
    
- `publicationTypes` — Types like _JournalArticle_, _ConferencePaper_, etc. 
    

**Citation Metrics**

- `citationCount` — Total number of times cited. 
    
- `influentialCitationCount` — Count of influential citations (when available). 
    
- _(Note: Citation fields may be available depending on the endpoint/context.)_
    

**Open Access / PDF Info**

- `openAccessPdf` — Metadata about public PDF availability (includes subfields like `url` and `status`). 
    

**Authors** _(requestable as nested subfields)_  
You can request nested author data via syntax like `authors.authorId` or `authors.name`, etc. 

- `authors` array
    
    - `authorId` — Unique author ID
        
    - `name` — Author name
        
    - `url` — Link to author’s Semantic Scholar page
        
    - Additional author subfields if requested
        

**Fields of Study**

- `s2FieldsOfStudy` — Paper’s subject area classifications (e.g., _Computer Science_, _Medicine_, etc.). 
    

**Other Nested / Optional Subfields**  
Semantic Scholar supports deeply nested properties; you can request them using dot notation, for example:

- `references.paperId`, `references.title` — Metadata of referenced papers
    
- `citations.paperId`, `citations.authors` — Metadata for citing papers
    
- `authors.affiliations` or other author-specific attributes
    
- Any combination of nested fields as supported by the general API (e.g., `citations.citationCount`, `references.publicationDate`)

- **`embedding.specter_v1`** – the original SPECTER embedding vector
    
- **`embedding.specter_v2`** – an updated SPECTER2 embedding model (newer and typically better)

## Available Publication Types

- Review
- JournalArticle
- CaseReport
- ClinicalTrial
- Conference
- Dataset
- Editorial
- LettersAndComments
- MetaAnalysis
- News
- Study
- Book
- BookSection

## Available Research Fields

- Computer Science
- Medicine
- Chemistry
- Biology
- Materials Science
- Physics
- Geology
- Psychology
- Art
- History
- Geography
- Sociology
- Business
- Political Science
- Economics
- Philosophy
- Mathematics
- Engineering
- Environmental Science
- Agricultural and Food Sciences
- Education
- Law
- Linguistics

## Bulk Search Query Syntax

fish ladder matches papers that contain "fish" and "ladder"
fish -ladder matches papers that contain "fish" but not "ladder"
fish | ladder matches papers that contain "fish" or "ladder"
"fish ladder" matches papers that contain the phrase "fish ladder"
(fish ladder) | outflow matches papers that contain "fish" and "ladder" OR "outflow"
fish~ matches papers that contain "fish", "fist", "fihs", etc.
"fish ladder"~3 mathces papers that contain the phrase "fish ladder" or "fish is on a ladder"