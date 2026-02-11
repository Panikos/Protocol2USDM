"""
CDISC API Adapter — Stub for future CDISC Library API integration.

When the CDISC Library API becomes available for USDM Controlled Terminology,
this adapter will:
1. Fetch the latest CT package from the CDISC Library API
2. Parse it into the same format as ``usdm_ct.json``
3. Merge with local cache / xlsx data
4. Optionally update the local JSON files

For now this is a stub that documents the intended interface and raises
``NotImplementedError`` for all online methods.

CDISC Library API docs: https://www.cdisc.org/cdisc-library
API key required: https://www.cdisc.org/cdisc-library/api-key

Environment Variables:
    CDISC_API_KEY: API key for CDISC Library (not yet required)

See also:
    - Sister project patterns: USDM2Synthetic/src/sdtm_generator/terminology/cdisc_library.py
    - NCI EVS client: core/evs_client.py
"""
from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Future API endpoint
CDISC_LIBRARY_BASE = "https://library.cdisc.org/api"
CDISC_API_KEY_ENV = "CDISC_API_KEY"


class CDISCApiAdapter:
    """
    Adapter for the CDISC Library API.

    Currently a stub — all online methods raise ``NotImplementedError``.
    The local-only methods (``is_available``, ``get_api_key``) work now.

    Usage (future)::

        adapter = CDISCApiAdapter()
        if adapter.is_available():
            codelists = adapter.fetch_usdm_ct()
            adapter.update_local_json(codelists)
    """

    def __init__(self) -> None:
        self._api_key: Optional[str] = os.environ.get(CDISC_API_KEY_ENV)

    @property
    def is_available(self) -> bool:
        """Check if the CDISC API key is configured."""
        return bool(self._api_key)

    def get_api_key(self) -> Optional[str]:
        """Return the configured API key (or None)."""
        return self._api_key

    # ------------------------------------------------------------------
    # Future API methods (stubs)
    # ------------------------------------------------------------------

    def fetch_usdm_ct(self, version: str = "latest") -> Dict[str, Any]:
        """
        Fetch USDM Controlled Terminology from the CDISC Library API.

        Args:
            version: CT package version (default "latest")

        Returns:
            Dict in the same format as ``usdm_ct.json``

        Raises:
            NotImplementedError: API not yet available
        """
        raise NotImplementedError(
            "CDISC Library API integration is not yet available. "
            "Use core/reference_data/USDM_CT.xlsx as the source of truth. "
            "See https://www.cdisc.org/cdisc-library for API status."
        )

    def fetch_codelist(self, codelist_code: str) -> Dict[str, Any]:
        """
        Fetch a single codelist by its NCI C-code.

        Args:
            codelist_code: e.g. "C188725" (Objective.level)

        Returns:
            Codelist dict with terms

        Raises:
            NotImplementedError: API not yet available
        """
        raise NotImplementedError(
            "CDISC Library API integration is not yet available."
        )

    def fetch_ct_versions(self) -> List[str]:
        """
        List available CT package versions.

        Returns:
            List of version strings (e.g. ["2024-09-27", "2024-03-29"])

        Raises:
            NotImplementedError: API not yet available
        """
        raise NotImplementedError(
            "CDISC Library API integration is not yet available."
        )

    def update_local_json(
        self,
        codelists: Dict[str, Any],
        json_path: Optional[str] = None,
    ) -> None:
        """
        Update the local ``usdm_ct.json`` with fetched codelists.

        Args:
            codelists: Codelist data from ``fetch_usdm_ct()``
            json_path: Override path (default: core/reference_data/usdm_ct.json)

        Raises:
            NotImplementedError: API not yet available
        """
        raise NotImplementedError(
            "CDISC Library API integration is not yet available."
        )

    def check_for_updates(self) -> Dict[str, Any]:
        """
        Check if a newer CT package is available.

        Returns:
            Dict with ``available``, ``current_version``, ``latest_version``

        Raises:
            NotImplementedError: API not yet available
        """
        raise NotImplementedError(
            "CDISC Library API integration is not yet available."
        )
