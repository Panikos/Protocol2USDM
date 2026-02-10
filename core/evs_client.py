"""
NCI EVS (Enterprise Vocabulary Services) Client

Retrieves controlled terminology codes from the NCI Thesaurus via EVS REST APIs.
Maintains a local cache for offline operation and performance.

API References:
- EVS CT API (CDISC CT): https://evs.nci.nih.gov/swagger-ui.html#/ct
- EVS REST API (NCIt): https://api-evsrest.nci.nih.gov/

Based on the approach from https://github.com/Panikos/AIBC
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional, Dict, List, Any

from core.terminology_codes import USDM_CODES_REGISTRY

try:
    import requests
except ImportError:
    raise SystemExit("[FATAL] The 'requests' package is required. pip install requests")

logger = logging.getLogger(__name__)

# Cache configuration
CACHE_DIR = Path(__file__).parent / "evs_cache"
CACHE_FILE = CACHE_DIR / "nci_codes.json"
CACHE_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days

# API endpoints
EVS_CT_BASE = os.getenv("EVS_API_BASE", "https://evs.nci.nih.gov/ctapi/v1")
EVS_REST_BASE = "https://api-evsrest.nci.nih.gov/api/v1"


class EVSClient:
    """Client for NCI EVS APIs with local caching."""
    
    def __init__(self, cache_file: Path = CACHE_FILE):
        self.cache_file = cache_file
        self.cache: Dict[str, dict] = {}
        self._load_cache()
    
    def _load_cache(self) -> None:
        """Load cache from disk."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
                logger.debug(f"Loaded {len(self.cache)} codes from EVS cache")
            except Exception as e:
                logger.warning(f"EVS cache corrupted, starting fresh: {e}")
                self.cache = {}
        else:
            self.cache = {}
    
    def _save_cache(self) -> None:
        """Save cache to disk."""
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, indent=2)
    
    def _is_fresh(self, entry: dict) -> bool:
        """Check if cache entry is still valid."""
        return time.time() - entry.get("_cached_at", 0) < CACHE_TTL_SECONDS
    
    def _http_get(self, url: str, params: dict = None, timeout: int = 10) -> Optional[dict]:
        """Generic HTTP GET with error handling."""
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.debug(f"EVS API request failed: {e}")
            return None
    
    def find_ct_entry(
        self, 
        term: str, 
        synonyms: Optional[List[str]] = None,
        code: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Find a CDISC Controlled Terminology entry by term, synonyms, or code.
        
        Uses the EVS CT API endpoint which is optimized for CDISC CT lookups.
        
        Args:
            term: Primary term to search
            synonyms: Optional list of synonyms to try
            code: Optional NCI code (e.g., "C16735")
            
        Returns:
            Dict with NCIt entry or None if not found
        """
        # Build ordered list of candidate query strings
        candidates: List[str] = []
        if term:
            candidates.append(term)
        if synonyms:
            candidates.extend([s for s in synonyms if s])
        if code:
            candidates.append(code)
        
        # Deduplicate while preserving order
        seen: set = set()
        ordered_candidates: List[str] = []
        for c in candidates:
            lc = c.lower()
            if lc not in seen:
                ordered_candidates.append(c)
                seen.add(lc)
        
        # Check cache first
        for cand in ordered_candidates:
            cache_key = f"ct:{cand.lower()}"
            cached = self.cache.get(cache_key)
            if cached and self._is_fresh(cached):
                return cached.get("data")
        
        # Query EVS CT API
        for cand in ordered_candidates:
            data = self._http_get(f"{EVS_CT_BASE}/ct/term", {"term": cand})
            if not data:
                continue
            
            term_lower = cand.lower()
            for entry in data:
                if (
                    entry.get("code", "").lower() == term_lower
                    or entry.get("preferredName", "").lower() == term_lower
                ):
                    # Cache and return exact match
                    cache_key = f"ct:{term_lower}"
                    self.cache[cache_key] = {"_cached_at": time.time(), "data": entry}
                    self._save_cache()
                    return entry
            
            # Return first result if no exact match
            if data:
                entry = data[0]
                cache_key = f"ct:{term_lower}"
                self.cache[cache_key] = {"_cached_at": time.time(), "data": entry}
                self._save_cache()
                return entry
        
        return None
    
    def fetch_ncit_code(self, code: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a specific NCIt concept by code (e.g., 'C15600' for Phase I Trial).
        
        Uses the EVS REST API for direct code lookup.
        
        Returns a USDM-compliant Code object or None if not found.
        """
        code = code.strip().upper()
        if not code:
            return None
        
        # Check cache first
        cache_key = f"ncit:{code}"
        cached = self.cache.get(cache_key)
        if cached and self._is_fresh(cached):
            return cached.get("data")
        
        # Fetch from EVS REST API
        data = self._http_get(f"{EVS_REST_BASE}/concept/ncit/{code}")
        
        if not data:
            # Try search endpoint as fallback
            search_data = self._http_get(
                f"{EVS_REST_BASE}/concept/ncit/search",
                {"term": code, "type": "contains"}
            )
            if search_data and search_data.get("concepts"):
                data = search_data["concepts"][0]
        
        if not data:
            logger.debug(f"NCIt code {code} not found")
            return None
        
        # Build USDM Code object
        result = {
            "id": code,
            "code": code,
            "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
            "codeSystemVersion": data.get("version", "unknown"),
            "decode": data.get("name") or data.get("preferredName", code),
            "instanceType": "Code",
        }
        
        # Cache the result with additional metadata
        self.cache[cache_key] = {
            "_cached_at": time.time(),
            "data": result,
            "_raw": {
                "name": data.get("name"),
                "preferredName": data.get("preferredName"),
                "definitions": data.get("definitions", []),
                "synonyms": data.get("synonyms", []),
            }
        }
        self._save_cache()
        
        return result
    
    def search_term(self, term: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search NCI Thesaurus for a term.
        
        Returns list of matching concepts.
        """
        data = self._http_get(
            f"{EVS_REST_BASE}/concept/ncit/search",
            {"term": term, "type": "contains", "pageSize": str(limit)}
        )
        
        if not data:
            return []
        
        concepts = data.get("concepts", [])
        return [
            {
                "code": c.get("code"),
                "name": c.get("name"),
                "preferredName": c.get("preferredName"),
            }
            for c in concepts
        ]
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = len(self.cache)
        fresh = sum(1 for v in self.cache.values() if self._is_fresh(v))
        
        return {
            "total_entries": total,
            "fresh_entries": fresh,
            "stale_entries": total - fresh,
            "cache_file": str(self.cache_file),
        }
    
    def clear_cache(self) -> None:
        """Clear the cache."""
        self.cache = {}
        if self.cache_file.exists():
            self.cache_file.unlink()
        logger.info("EVS cache cleared")
    
    def update_cache(self, codes: List[str]) -> Dict[str, int]:
        """
        Update cache with specific codes (fetch fresh from API).
        
        Returns dict with success/failure counts.
        """
        success = 0
        failed = 0
        
        for code in codes:
            # Remove from cache to force refresh
            cache_key = f"ncit:{code}"
            if cache_key in self.cache:
                del self.cache[cache_key]
            
            result = self.fetch_ncit_code(code)
            if result:
                success += 1
            else:
                failed += 1
        
        return {"success": success, "failed": failed}


# Backward-compatible alias — now derived from the single source of truth
# in core.terminology_codes.USDM_CODES_REGISTRY.
USDM_CODES = USDM_CODES_REGISTRY


def ensure_usdm_codes_cached(client: EVSClient = None) -> Dict[str, int]:
    """
    Ensure all USDM-relevant NCI codes are in the cache.
    
    Call this on first run or to refresh the cache.
    """
    if client is None:
        client = EVSClient()
    
    codes_to_fetch = []
    for code in USDM_CODES.keys():
        cache_key = f"ncit:{code}"
        cached = client.cache.get(cache_key)
        if not cached or not client._is_fresh(cached):
            codes_to_fetch.append(code)
    
    if not codes_to_fetch:
        logger.info(f"All {len(USDM_CODES)} USDM codes already cached")
        return {"success": len(USDM_CODES), "failed": 0, "skipped": 0}
    
    logger.info(f"Fetching {len(codes_to_fetch)} NCI codes...")
    result = client.update_cache(codes_to_fetch)
    result["skipped"] = len(USDM_CODES) - len(codes_to_fetch)
    
    return result


# Singleton instance for convenience
_client: Optional[EVSClient] = None


def get_client() -> EVSClient:
    """Get the singleton EVS client instance."""
    global _client
    if _client is None:
        _client = EVSClient()
    return _client


def fetch_code(code: str) -> Optional[Dict[str, Any]]:
    """Convenience function to fetch a code using the singleton client."""
    return get_client().fetch_ncit_code(code)


def find_ct_entry(term: str, synonyms: List[str] = None) -> Optional[Dict[str, Any]]:
    """Convenience function to find CT entry using the singleton client."""
    return get_client().find_ct_entry(term, synonyms)


def search_term(term: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Convenience function to search using the singleton client."""
    return get_client().search_term(term, limit)
