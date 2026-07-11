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
    """Return SHA-256 hex digest of the given text (empty string for None)."""
    return hashlib.sha256((text or "").encode()).hexdigest()


def _has_formula(text: str) -> bool:
    """Return True if the text contains any LaTeX formula markers."""
    return bool(_FORMULA_RE.search(text))


def _clean_abstract(raw: str) -> str:
    """Strip HTML tags, unescape entities, remove LaTeX markup, and collapse whitespace.

    LaTeX math delimiters (``$...$``, ``\\[...\\]``, environments) are removed but
    their inner content is kept so no mathematical information is lost.
    """
    # HTML pass
    text = _HTML_TAG.sub(' ', raw)
    text = _html.unescape(text)
    # LaTeX pass — strip delimiters, keep content
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
    """Return the ISO 639-1 language code for text, or None if detection fails."""
    try:
        return detect(text)
    except LangDetectException:
        return None


def _load_candidates(max_processed_at) -> pd.DataFrame:
    """Load raw papers that have been updated since the last processing run."""
    if max_processed_at is None:
        return pd.read_sql(f'SELECT * FROM {INPUT_TABLE}', ENGINE)
    return pd.read_sql(
        text(f'SELECT * FROM {INPUT_TABLE} WHERE "last_updated" > :ts'),
        ENGINE,
        params={"ts": max_processed_at},
    )


def clean_abstracts(
    input_table: str = INPUT_TABLE,
    output_table: str = OUTPUT_TABLE,
) -> PaperProcessingMetrics:
    """Clean and enrich paper abstracts, writing results to the processed table.

    Reads raw abstracts from ``input_table``, strips HTML and LaTeX formatting
    while preserving semantic content, and derives enrichment fields. Results are
    upserted into ``output_table``. Rows whose content hash matches an existing
    processed row are skipped.

    Parameters
    ----------
    input_table : str
        Fully-qualified source table (schema.table). Defaults to
        ``raw.raw_paper_searches``.
    output_table : str
        Fully-qualified destination table (schema.table). Defaults to
        ``processed.processed_abstracts``.

    Returns
    -------
    PaperProcessingMetrics
        Counts of total candidates considered and rows inserted, updated, or
        skipped.
    """
    metrics = PaperProcessingMetrics()

    result = execute_query(f'SELECT MAX("processed_at") FROM {output_table}')
    max_processed_at = result.fetchone()[0]

    candidates = _load_candidates(max_processed_at)
    metrics.total = len(candidates)

    if candidates.empty:
        logger.info("clean_abstracts: no candidates to process")
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
        cleaned = _clean_abstract(raw_abstract)
        language = _detect_language(cleaned) if cleaned else None

        records.append({
            "paperId": paper_id,
            "abstract_clean": cleaned or None,
            "abstract_length": len(cleaned),
            "word_count": len(cleaned.split()) if cleaned else 0,
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
        f"clean_abstracts: total={metrics.total}, inserted={metrics.inserted}, "
        f"updated={metrics.updated}, skipped={metrics.skipped}"
    )
    return metrics
