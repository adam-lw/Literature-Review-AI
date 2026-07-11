import hashlib
import html as _html
import re
from datetime import datetime, timezone

from langdetect import detect, LangDetectException
from loguru import logger
from sqlalchemy import text
import pandas as pd

from literature_ai.db import ENGINE, execute_query, upsert_table
from literature_ai.core.utils import PaperProcessingMetrics

INPUT_TABLE = "raw.raw_paper_searches"
OUTPUT_TABLE = "processed.processed_abstracts"

_FORMULA_RE = re.compile(r'\$|\\\(|\\\[|\\begin\{')

_DISPLAY_MATH_DOLLAR = re.compile(r'\$\$(.+?)\$\$', re.DOTALL)
_DISPLAY_MATH_BRACKET = re.compile(r'\\\[(.+?)\\\]', re.DOTALL)
_INLINE_MATH_PAREN = re.compile(r'\\\((.+?)\\\)', re.DOTALL)
_INLINE_MATH_DOLLAR = re.compile(r'\$(.+?)\$')
_MATH_ENV = re.compile(r'\\begin\{[^}]+\}(.*?)\\end\{[^}]+\}', re.DOTALL)
_FORMATTING_CMD = re.compile(r'\\(?:textbf|textit|emph|underline|texttt|text|mathrm|mathbf|mathit)\{(.+?)\}')
_DISCARD_CMD = re.compile(r'\\(?:cite|ref|label|footnote)\{[^}]*\}')
_LONE_CMD = re.compile(r'\\[a-zA-Z]+\s?')
_WHITESPACE = re.compile(r'\s+')
_HTML_TAG = re.compile(r'<[^>]+>')


def _hash(text: str | None) -> str:
    return hashlib.sha256((text or "").encode()).hexdigest()


def _has_formula(text: str) -> bool:
    return bool(_FORMULA_RE.search(text))


def _clean_text(raw: str) -> str:
    """Strip HTML tags, unescape entities, remove LaTeX markup, and collapse whitespace."""
    text = _HTML_TAG.sub(' ', raw)
    text = _html.unescape(text)
    text = _DISPLAY_MATH_DOLLAR.sub(r'\1', text)
    text = _DISPLAY_MATH_BRACKET.sub(r'\1', text)
    text = _INLINE_MATH_PAREN.sub(r'\1', text)
    text = _INLINE_MATH_DOLLAR.sub(r'\1', text)
    text = _MATH_ENV.sub(r'\1', text)
    text = _FORMATTING_CMD.sub(r'\1', text)
    text = _DISCARD_CMD.sub('', text)
    text = _LONE_CMD.sub(' ', text)
    return _WHITESPACE.sub(' ', text).strip()


def _detect_language(text: str) -> str | None:
    try:
        return detect(text)
    except LangDetectException:
        return None


def _load_candidates(max_processed_at) -> pd.DataFrame:
    if max_processed_at is None:
        return pd.read_sql(f'SELECT * FROM {INPUT_TABLE}', ENGINE)
    return pd.read_sql(
        text(f'SELECT * FROM {INPUT_TABLE} WHERE "last_updated" > :ts'),
        ENGINE,
        params={"ts": max_processed_at},
    )


def clean_paper(
    input_table: str = INPUT_TABLE,
    output_table: str = OUTPUT_TABLE,
) -> PaperProcessingMetrics:
    """Clean paper titles and abstracts, writing results to the processed table.

    Reads raw papers from ``input_table``, strips HTML and LaTeX formatting from
    both title and abstract, and derives enrichment fields. Results are upserted
    into ``output_table``. Rows whose content hash matches an existing processed
    row are skipped.
    """
    metrics = PaperProcessingMetrics()

    result = execute_query(f'SELECT MAX("processed_at") FROM {output_table}')
    max_processed_at = result.fetchone()[0]

    candidates = _load_candidates(max_processed_at)
    metrics.total = len(candidates)

    if candidates.empty:
        logger.info("clean_paper: no candidates to process")
        return metrics

    existing = execute_query(f'SELECT "paperId", content_hash FROM {output_table}')
    existing_hashes: dict[str, str] = {row[0]: row[1] for row in existing.fetchall()}

    records: list[dict] = []
    now = datetime.now(timezone.utc)

    for _, row in candidates.iterrows():
        paper_id: str = row["paperId"]
        raw_abstract: str = row.get("abstract") or ""
        content_hash = _hash(raw_abstract)

        if existing_hashes.get(paper_id) == content_hash:
            metrics.skipped += 1
            continue

        is_update = paper_id in existing_hashes
        has_formula = _has_formula(raw_abstract)
        abstract_clean = _clean_text(raw_abstract)
        title_clean = _clean_text(row.get("title") or "") or None
        language = _detect_language(abstract_clean) if abstract_clean else None

        records.append({
            "paperId": paper_id,
            "title": title_clean,
            "abstract": abstract_clean or None,
            "abstract_length": len(abstract_clean),
            "word_count": len(abstract_clean.split()) if abstract_clean else 0,
            "has_formula": has_formula,
            "language": language,
            "content_hash": content_hash,
            "processed_at": now,
        })

        if is_update:
            metrics.updated += 1
        else:
            metrics.inserted += 1

    if records:
        upsert_table(records, output_table, conflict_cols=["paperId"], do_update=True)

    logger.info(
        f"clean_paper: total={metrics.total}, inserted={metrics.inserted}, "
        f"updated={metrics.updated}, skipped={metrics.skipped}"
    )
    return metrics
