import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger

from literature_ai.db import upsert_table_async
from literature_ai.core.agent.logging.langfuse import lf_logger
from literature_ai.core.session import make_session
from literature_ai.core.utils import load_dict, get_project_root, PaperProcessingMetrics

CONFIG_PATH = get_project_root() / "config/core/data_collect/semantic_scholar.json"
RAW_PAPERS_TABLE = "raw.raw_paper_searches"

_CONFIG = load_dict(CONFIG_PATH)
_RETURN_FIELDS: list[str] = _CONFIG["default_return_fields"]
_PUBLICATION_TYPES: list[str] = _CONFIG["default_publication_types"]
_SESSION = make_session(
    cache_name="semantic_scholar",
    max_retries=_CONFIG["max_retries"],
    backoff_factor=_CONFIG["backoff_factor"],
)
_LAST_CALL: float = 0.0



async def _iter_papers(
    query: str,
    research_fields: list[str],
    *,
    sort_by: Optional[str] = None,
    ascending: Optional[bool] = None,
    years: Optional[tuple[int, int]] = None,
    open_access_only: bool = True,
    min_citation_count: int = 3,
    verbosity: int = 0,
):
    """Raw async generator yielding batches of paper records as list[dict]."""
    global _LAST_CALL

    if verbosity > 0:
        logger.info(f"Collecting papers for query `{query}`")

    if not all(field in _CONFIG.get("research_fields", []) for field in research_fields):
        raise ValueError(
            f"Unrecognised field(s) of study: {[f for f in research_fields if f not in _CONFIG['research_fields']]}"
        )

    if sort_by and sort_by not in _CONFIG["available_return_fields"]:
        raise ValueError(f"Unrecognised sort_by field {sort_by}")

    if sort_by is not None and ascending is not None:
        sort_by_str = sort_by + (":asc" if ascending else ":desc")
    elif sort_by is not None:
        sort_by_str = sort_by
    else:
        sort_by_str = None

    return_fields_set = set(_RETURN_FIELDS)
    years_str = "-".join(str(y) for y in years) if years is not None else None

    continuation_token: str = ""
    total_collected = 0
    limit = 0
    endpoint = "graph/v1/paper/search/bulk/"

    while True:
        # prepare params for request payload
        params = {
            "query": query,
            "token": continuation_token if continuation_token else None,
            "fields": ",".join(_RETURN_FIELDS),
            "sort": sort_by_str,
            "limit": 5000000,
            "publicationTypes": ",".join(_PUBLICATION_TYPES),
            "fieldsOfStudy": ",".join(research_fields),
            "year": years_str,
            "openAccessPdf": open_access_only,
            "minCitationCount": min_citation_count,
        }
        params = {k: v for k, v in params.items() if v is not None}

        elapsed = time.time() - _LAST_CALL
        if elapsed < _CONFIG["delay_per_request"]:
            await asyncio.sleep(_CONFIG["delay_per_request"] - elapsed)

        loop = asyncio.get_running_loop()
        start = time.time()
        response = await loop.run_in_executor(
            None, lambda: _SESSION.get(_CONFIG["url"] + endpoint, params=params)
        )
        duration = time.time() - start
        _LAST_CALL = time.time()

        data = response.json()
        try:
            lf_logger.log_api_call("semantic_scholar_api", endpoint, params, data, duration, error=None)
        except Exception:
            pass

        if data.get("error"):
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
            break

        continuation_token = data.get("token", "")
        raw = data.get("data") or []

        if not raw:
            logger.error(f"No data returned. Full response: {data}")
            break

        records = [{k: v for k, v in r.items() if k in return_fields_set} for r in raw]
        total_collected += len(records)
        yield records


def collect_papers(
    queries: list[dict[str, Any] | str],
    *,
    results_per_query: Optional[int] = None,
    research_fields: list[str] = [
        "Computer Science",
        "Mathematics",
    ],
    sort_by: Optional[str] = None,
    ascending: Optional[bool] = None,
    years: Optional[tuple[int, int]] = None,
    open_access_only: bool = True,
    min_citation_count: int = 3,
    verbosity: int = 0,
) -> PaperProcessingMetrics:
    """Collect papers from Semantic Scholar for a list of queries and upsert into the database.

    Each entry in `queries` is either a plain string or a dict with a required `"query"` key
    and optional per-query overrides for research_fields, sort_by, ascending, years,
    open_access_only, and min_citation_count. Return fields and publication types are
    determined by the module config and are not overridable per-query.

    Returns aggregate PaperProcessingMetrics across all queries.
    """
    
    query_list = queries if isinstance(queries, list) else [{"query": queries, "research_fields": research_fields}]

    metrics = PaperProcessingMetrics()

    async def _run():
        for query_settings in query_list:
            query = query_settings["query"]
            collected = 0
            async for batch in _iter_papers(
                query,
                query_settings.get("research_fields", research_fields),
                sort_by=query_settings.get("sort_by", sort_by),
                ascending=query_settings.get("ascending", ascending),
                years=query_settings.get("years", years),
                open_access_only=query_settings.get("open_access_only", open_access_only),
                min_citation_count=query_settings.get("min_citation_count", min_citation_count),
                verbosity=verbosity,
            ):
                print(f"batch[0]: {batch[0]}")
                now = datetime.now(timezone.utc)
                for record in batch:
                    # Handle subdictionaries for write
                    record["collected_at"] = now
                    record["last_updated"] = now

                    ext_ids = record.pop("externalIds")
                    if not isinstance(ext_ids, dict):
                        ext_ids = {}
                    ext_fields = ["ArXiV", "DBLP", "MAG", "DOI"]
                    record.update(**{field: ext_ids.get(field, None) for field in ext_fields})

                    pdf_info = record.pop("openAccessPdf")
                    if not isinstance(pdf_info, dict):
                        pdf_info = {}
                    pdf_fields = ["url", "status"]
                    record.update(**{field: pdf_info.get(field, None) for field in pdf_fields})

                    record["fieldsOfStudy"] = json.dumps(record.get("fieldsOfStudy") or [])
                    record["publicationTypes"] = json.dumps(record.get("publicationTypes") or [])
                    

                metrics.total += len(batch)
                try:
                    actual_inserted = await upsert_table_async(
                        batch, RAW_PAPERS_TABLE, conflict_cols=["paperId"], do_update=False
                    )
                    metrics.inserted += actual_inserted
                    metrics.skipped += len(batch) - actual_inserted
                except Exception as e:
                    logger.error(f"Upsert failed for query `{query}`: {e}")
                    metrics.errors += len(batch)
                collected += len(batch)
                logger.info(f"Processed {collected} papers for query `{query}`")
                if results_per_query and collected >= results_per_query:
                    break

    asyncio.run(_run())
    return metrics
