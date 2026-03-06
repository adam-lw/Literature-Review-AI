"""
Pipelines for building a vector database


"""

from papery.core.api.core import api_call
import pandas as pd
import asyncio
from typing import Optional, Any, Literal

from papery.core.utils import load_dict, get_project_root
from papery.core.db import load_table, save_table_async, get_inspector

from loguru import logger

CONFIG_PATH = get_project_root() / "config/api/semantic_scholar.json"


async def bulk_collect_papers(
    query: str,
    table_save_path: str,
    research_fields: list[str],
    *,
    sort_by: Optional[str] = None,
    ascending: Optional[bool] = None,
    return_fields: list[str] = [
        "paperId",
        "title",
        "abstract",
        "year",
        "fieldsOfStudy",
    ],
    publication_types: list[str] = [
        "JournalArticle",
        "Review",
        "Conference",
        "MetaAnalysis",
    ],
    years: Optional[tuple[int, int]] = None,
    n_results: int = 1000,
    open_access_only: bool = True,
    min_citation_count: int = 3,
) -> dict[str, Any]:
    """
    Helper method for calling the Semantic Scholar paper API for bulk paper collection.
    """
    logger.info(f"Collecting papers for query `{query}`")
    config = load_dict(CONFIG_PATH)

    # Validate data
    if not all(
        [field in config.get("research_fields", []) for field in research_fields]
    ):
        raise ValueError(
            f"Unrecognised field(s) of study: {[f for f in research_fields if f not in config['research_fields']]}"
        )

    if not all(
        [
            pubtype in config.get("publication_types", [])
            for pubtype in publication_types
        ]
    ):
        raise ValueError(
            f"Unrecognised publication type(s): {[p for p in publication_types if p not in config['publication_types']]}"
        )

    if sort_by and sort_by not in config["return_fields"]:
        raise ValueError(f"Unrecognised sort_by field {sort_by}")

    inspector = get_inspector()
    if not inspector.has_schema(str(table_save_path).split(".")[0]):
        raise ValueError(
            f"Schema {table_save_path.split('.')[0]} does not exist. Please create the schema before running the pipeline."
        )

    # Prepare data
    if sort_by is not None and ascending is not None:
        sort_by_str = sort_by + (":asc" if ascending else ":desc")
    elif sort_by is not None:
        sort_by_str = sort_by
    else:
        sort_by_str = None

    return_fields_str = ",".join(return_fields)
    logger.info(return_fields_str)
    publication_types_str = ",".join(publication_types)
    fields_of_study_str = ",".join(research_fields)
    years_str = "-".join([str(y) for y in years]) if years is not None else None

    metadata = {"query": query}
    continuation_token: str = ""
    remaining_papers = n_results
    while remaining_papers > 0:
        print(f"Remaining papers: {remaining_papers}")
        n_papers_to_collect = remaining_papers if remaining_papers < 1000 else 1000
        remaining_papers -= n_papers_to_collect

        params = {
            "query": query,
            "token": continuation_token if len(continuation_token) > 0 else None,
            "fields": return_fields_str,
            "sort": sort_by_str,
            "limit": n_results,
            "publicationTypes": publication_types_str,
            "fieldsOfStudy": fields_of_study_str,
            "year": years_str,
            "openAccessPdf": open_access_only,
            "minCitationCount": min_citation_count,
        }

        # custom `api_call` method handles queuing, retrying, etc. for potentially many calls across many applications
        # loop required due to continuation tokens in this instance
        data = await api_call(
            api_id="semantic_scholar_api",
            header=params,
            endpoint="graph/v1/paper/search/bulk/",
        )
        print(f"Response length: {len(data.get('data', []))}")

        print(data.get("total", "No total field"))

        # Process errors
        if data.get("error", None):
            logger.error(f"Error in API response: {data['error']}")
            logger.error(f"Full response: {data}")
            metadata["error"] = data["error"]
            break

        continuation_token = data.get("token", "")

        if "n_found" not in metadata.keys():
            metadata["n_found"] = data.get("total", 0)

        results = pd.DataFrame(data.get("data", None))

        if len(results) == 0:
            logger.error(f"No data returned. Full response: {data}")

        if data.get("total", 0) == 0:
            logger.error(
                f"No matches returned. {query} Remaining results {remaining_papers} Full response: {data}"
            )

        # The API will sometimes return fields we didn't ask for - drop them
        results = results.drop(
            columns=[c for c in results.columns if c not in return_fields]
        )

        await save_table_async(results, table_path=table_save_path, if_exists="append")

        if n_results > data.get("total", 0):
            logger.warning(
                "Warning: total matches is lower than desired matches. Stopping"
            )
            break

    return metadata


async def collect_embeddings(
    table_uri: str, id_col: str, embedding: Literal["specter_v1", "specter_v2"]
):
    data = load_table(table_uri)

    ids = data[id_col].tolist()

    id_chunks = [ids[i : i + 500] for i in range(0, len(ids), 500)]

    response = await asyncio.gather(
        *[
            api_call(
                header={"fields": f"paperId,embedding.{embedding}"},
                body={"ids": chunk},
                api_id="semantic_scholar_api",
                endpoint="graph/v1/paper/batch",
                task="POST",
            )
            for chunk in id_chunks
        ][0:2]
    )

    print(response[0].keys())


# if __name__ == "__main__":

#     load_dotenv()

#     papers = asyncio.run(bulk_collect_papers(
#         query="machine learning",
#         table_save_path="test.test_papers",
#         research_fields=["Medicine", "Computer Science"],
#         publication_types=["JournalArticle", "Conference"],
#         n_results=2500)
#     )

if __name__ == "__main__":
    asyncio.run(
        collect_embeddings(
            table_uri="test.test_papers", id_col="paperId", embedding="specter_v2"
        )
    )
