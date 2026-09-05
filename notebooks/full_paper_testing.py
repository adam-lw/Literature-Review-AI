import pandas as pd
from sqlalchemy import text

from literature_ai.db import ENGINE
from literature_ai.search_service.search.vector_search import vector_search
from literature_ai.search_service.search.keyword_search import keyword_search
from literature_ai.search_service.search.chunk_search import rag_paper_chunks, CHUNKS_TABLE
from literature_ai.search_service.data_collect.collect_full_papers import process_papers_by_id, FULLTEXT_TABLE

QUERY = "ML"

vector_results = vector_search(QUERY, run_id=1, n_results=20)
print(pd.DataFrame(vector_results))

keyword_results = keyword_search(QUERY, n_results=20)
print(pd.DataFrame(keyword_results))

paper_ids = [r["paperId"] for r in keyword_results]
metrics = process_papers_by_id(paper_ids)

print(metrics.inserted)

with ENGINE.connect() as conn:
    rows = conn.execute(
        text('SELECT "paperId" FROM {} WHERE "paperId" = ANY(:ids) AND "status" = \'success\''.format(FULLTEXT_TABLE)),
        {"ids": paper_ids},
    ).fetchall()
successful_ids = [r[0] for r in rows]

for paper_id in successful_ids:
    with ENGINE.connect() as conn:
        rows = conn.execute(
            text('SELECT section_header FROM {} WHERE "paperId" = :id ORDER BY section_index'.format(CHUNKS_TABLE)),
            {"id": paper_id},
        ).fetchall()
    headers = list(dict.fromkeys(r[0] for r in rows))
    print(paper_id, headers)

rag_results = rag_paper_chunks(successful_ids, QUERY, n_results=10)
print(pd.DataFrame(rag_results["results"]))
