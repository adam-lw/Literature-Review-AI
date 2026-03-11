"""
API wrapper for the Semantic Scholar API, including helper methods for bulk paper collection and embedding collection.


"""

from papery.core.api.core import api_call
import pandas as pd
import asyncio
from typing import Optional, Literal

from papery.core.utils import load_dict, get_project_root

from loguru import logger

CONFIG_PATH = get_project_root() / "config/api/semantic_scholar.json"


async def bulk_collect_papers(
    query: str,
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
    open_access_only: bool = True,
    min_citation_count: int = 3,
    verbosity: int = 0,
):
    """
    Helper method for calling the Semantic Scholar paper API for bulk paper collection.
    """
    if verbosity > 0:
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

    continuation_token: str = ""
    total_collected = 0
    limit = 0
    while True:
        params = {
            "query": query,
            "token": continuation_token if len(continuation_token) > 0 else None,
            "fields": return_fields_str,
            "sort": sort_by_str,
            "limit": 5000000,
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
            break

        if limit == 0:
            limit = data.get("total", 0)

        if limit == 0:
            logger.error(f"No matches returned for query: `{query}`.")
            break

        if total_collected >= limit:
            logger.info(f"Exhausted available papers for {query}")

        continuation_token = data.get("token", "")

        results = pd.DataFrame(data.get("data", None))

        if len(results) == 0:
            logger.error(f"No data returned. Full response: {data}")

        # The API will sometimes return fields we didn't ask for - drop them
        results = results.drop(
            columns=[c for c in results.columns if c not in return_fields]
        )

        yield results


async def collect_specter_embeddings(
    ids: list[str], embedding: Literal["specter_v1", "specter_v2"]
):
    """
    Generator method for collecting SPECTER paper embeddings in bulk, given a list of paper IDs.

    This is implemented seperately from the standard EmbeddingModel structure as this relies on
    retrieval of embeddings by ID, rather than embedding generation.
    """
    id_chunks = [ids[i : i + 500] for i in range(0, len(ids), 500)]

    tasks = [
        asyncio.create_task(
            api_call(
                header={"fields": f"paperId,embedding.{embedding}"},
                body={"ids": chunk},
                api_id="semantic_scholar_api",
                endpoint="graph/v1/paper/batch",
                task="POST",
                verbosity=1,
            )
        )
        for chunk in id_chunks
    ]

    for task in asyncio.as_completed(tasks):
        response = await task
        if response.get("code", None) != 200:
            logger.error("Error in API response.")
            logger.error(f"Full response: {response}")
            break

        resp_data = response.get("data", None)
        if resp_data is None:
            logger.error(f"No data field in response. Full response: {response}")
            break

        # Format data
        formatted_data = []
        for paper in resp_data:
            if paper is None:
                logger.warning("Null value encountered in response")
                continue
            elif paper.get("embedding", None) is None:
                print(f"No embedding for paperId {paper['paperId']}")
                continue
            formatted_data.append(
                {
                    "paperId": paper["paperId"],
                    embedding: paper.get("embedding", {}).get("vector", None),
                }
            )

        yield pd.DataFrame(formatted_data)

    return
