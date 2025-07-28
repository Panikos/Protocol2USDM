"""Utility for retrieving Code details from the NIH EVS REST API with a very small
on-disk JSON cache so the pipeline can work offline after the first run.

Only the subset of the API we need is implemented (lookup by NCI concept code).
If the API is unreachable or a code is not found, the client returns ``None``
so the caller can fall back to safe defaults.
"""
from __future__ import annotations

import json
import logging
import pathlib
import time
import uuid
from typing import Optional, Dict

try:
    import requests  # type: ignore
except ImportError:
    # The pipeline relies on ``requests``. Inform the developer clearly.
    raise SystemExit("[FATAL] The 'requests' package is required. Add it to requirements.txt and reinstall.")


CACHE_PATH = pathlib.Path("useful_material/evs_cache.json")
# Ensure cache directory exists
CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
CACHE_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days
# EVS v1 endpoint requires the terminology (NCIT) in the path
BASE_URL = "https://api-evsrest.nci.nih.gov/api/v1/concept/ncit/"

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

def _load_cache() -> Dict[str, dict]:
    if CACHE_PATH.exists():
        try:
            with CACHE_PATH.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            logger.warning("[EVS] Cache file corrupted – starting fresh.")
    return {}

def _save_cache(cache: Dict[str, dict]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CACHE_PATH.open("w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

def _is_fresh(entry: dict) -> bool:
    return time.time() - entry.get("_cached_at", 0) < CACHE_TTL_SECONDS


def fetch_code(c_code: str) -> Optional[dict]:
    """Return a dict with the six required Code fields or ``None`` if unavailable."""
    c_code = c_code.strip()
    if not c_code:
        return None

    cache = _load_cache()
    cached_entry = cache.get(c_code)
    if cached_entry and _is_fresh(cached_entry):
        return cached_entry["data"]

    url = f"{BASE_URL}{c_code}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 404 or resp.status_code == 400:
            # Fallback: use the search endpoint
            search_url = (
                "https://api-evsrest.nci.nih.gov/api/v1/concepts?terminology=NCIT&code="
                f"{c_code}&include=summary"
            )
            resp = requests.get(search_url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # /concepts returns a list
        if isinstance(data, list):
            data = data[0] if data else {}
    except Exception as exc:
        logger.debug("[EVS] %s not found (skipped) – %s", c_code, exc)
        return None

    # API schema varies; we extract what we need safely.
    term = data.get("preferredName") or data.get("name") or ""
    code_system = data.get("terminology") or "NCI Thesaurus"
    code_system_version = data.get("version") or "unknown"

    result = {
        "id": c_code,
        "code": c_code,
        "codeSystem": code_system,
        "codeSystemVersion": code_system_version,
        "decode": term,
        "instanceType": "Code",
    }

    cache[c_code] = {"_cached_at": time.time(), "data": result}
    _save_cache(cache)
    return result


def generate_placeholder(term: str | None = None) -> dict:
    """Return a syntactically valid Code object when EVS data is unavailable."""
    uid = str(uuid.uuid4())
    return {
        "id": uid,
        "code": term or "UNKNOWN",
        "codeSystem": "CDISC-CT",
        "codeSystemVersion": "unspecified",
        "decode": term or "UNKNOWN",
        "instanceType": "Code",
    }
