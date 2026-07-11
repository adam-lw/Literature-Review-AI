import os

import requests_cache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_CACHE_DIR = "data/http_cache"
_DEFAULT_TTL = 60 * 60 * 24 * 7  # 7 days
_DEBUG = os.getenv("SCRAPE_DEBUG", "").lower() in ("1", "true", "yes")


def _debug_log(response, *args, **kwargs):
    if _DEBUG:
        status = "HIT " if response.from_cache else "MISS"
        print(f"[cache {status}] {response.request.url}")


def _strip_vary(response, *args, **kwargs):
    # Prevents per-request Vary header values (e.g. WMF-Uniq cookies) from causing
    # every cached response to miss by keying separate cache entries per header combo.
    response.headers.pop("Vary", None)
    return response


def make_session(
    cache_name: str,
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    cache_ttl: int = _DEFAULT_TTL,
    cache_enabled: bool = False,
) -> requests_cache.CachedSession:
    session = requests_cache.CachedSession(
        f"{_CACHE_DIR}/{cache_name}",
        expire_after=cache_ttl,
    )
    if not cache_enabled:
        session.settings.disabled = True
    session.hooks["response"].append(_strip_vary)
    session.hooks["response"].append(_debug_log)
    retry = Retry(
        total=max_retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session
