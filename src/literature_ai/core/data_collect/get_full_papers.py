import io
from datetime import datetime, timezone

import pypdf
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from loguru import logger

from literature_ai.db import execute_query, load_table, upsert_table
from literature_ai.core.utils import load_dict, get_project_root, PaperProcessingMetrics

_CONFIG_PATH = get_project_root() / "config/core/data_collect/semantic_scholar.json"
_config = load_dict(_CONFIG_PATH)

_pdf_session = requests.Session()
_pdf_session.mount(
    "https://",
    HTTPAdapter(
        max_retries=Retry(
            total=_config["max_retries"],
            backoff_factor=_config["backoff_factor"],
            status_forcelist=[429, 500, 502, 503, 504],
        )
    ),
)

RAW_PAPERS_TABLE = "raw.raw_paper_searches"
FULL_PAPERS_TABLE = "raw.full_papers"

_BATCH_SIZE = 50


def _resolve_pdf_url(row: dict) -> str | None:
    """Return the best available PDF URL for a paper, or None if none found.

    Prefers the S2 openAccessPdf URL; falls back to ArXiv if an ArXiv ID is present.
    """
    oa_pdf = row.get("openAccessPdf")
    if isinstance(oa_pdf, dict) and oa_pdf.get("url"):
        return oa_pdf["url"]

    external_ids = row.get("externalIds")
    if isinstance(external_ids, dict) and external_ids.get("ArXiv"):
        return f"https://arxiv.org/pdf/{external_ids['ArXiv']}"

    return None


def _download_and_extract(url: str) -> str | None:
    """Download a PDF from url and extract its full text. Returns None on failure."""
    try:
        response = _pdf_session.get(url, timeout=30, stream=True)
        response.raise_for_status()
        buf = io.BytesIO(response.content)
        reader = pypdf.PdfReader(buf)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as e:
        logger.warning(f"Failed to download/extract PDF from {url}: {e}")
        return None


def collect_full_papers(
    input_table: str = RAW_PAPERS_TABLE,
    output_table: str = FULL_PAPERS_TABLE,
) -> PaperProcessingMetrics:
    """Download and store full paper texts for all papers in input_table.

    Reads openAccessPdf and externalIds from input_table to resolve PDF URLs.
    Only processes papers not already present in output_table. Results are
    upserted into output_table in batches. output_table must already exist (see schema.sql).
    """
    metrics = PaperProcessingMetrics()

    input_df = load_table(input_table)
    metrics.total = len(input_df)

    url_map: dict[str, str] = {}
    for _, row in input_df.iterrows():
        url = _resolve_pdf_url(row.to_dict())
        if url:
            url_map[row["paperId"]] = url

    existing_result = execute_query(f'SELECT "paperId" FROM {output_table}')
    existing_ids: set[str] = {row[0] for row in existing_result.fetchall()}

    to_process = {pid: url for pid, url in url_map.items() if pid not in existing_ids}
    already_fetched = len(url_map) - len(to_process)
    metrics.skipped += already_fetched

    logger.info(
        f"collect_full_papers: {len(to_process)} to process, "
        f"{already_fetched} already in output table"
    )

    if not to_process:
        return metrics

    batch: list[dict] = []
    processed = 0

    for paper_id, pdf_url in to_process.items():
        text = _download_and_extract(pdf_url)
        if text is not None:
            batch.append({
                "paperId": paper_id,
                "full_text": text,
                "pdf_url": pdf_url,
                "collected_at": datetime.now(timezone.utc),
            })
            metrics.inserted += 1
        else:
            metrics.errors += 1

        processed += 1

        if len(batch) >= _BATCH_SIZE:
            upsert_table(batch, output_table, conflict_cols=["paperId"], do_update=False)
            logger.info(f"Upserted {len(batch)} papers ({processed}/{len(to_process)} processed)")
            batch = []

    if batch:
        upsert_table(batch, output_table, conflict_cols=["paperId"], do_update=False)
        logger.info(f"Upserted {len(batch)} papers ({processed}/{len(to_process)} processed)")

    logger.info(
        f"collect_full_papers complete — inserted: {metrics.inserted}, "
        f"skipped: {metrics.skipped}, errors: {metrics.errors}"
    )
    return metrics
