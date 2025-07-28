import warnings
warnings.warn("mapping_pre_scan.py is deprecated and will be removed in a future release.", DeprecationWarning)

"""Pre-scan the soa_entity_mapping.json file to identify all NCI c_codes we
might need in the SoA pipeline and pre-populate the EVS cache. This speeds up
pipeline runs and surfaces missing codes early in CI.

Run this script manually (or in CI) when the mapping file changes.
"""
from __future__ import annotations

import json
import logging
import pathlib
import sys
from typing import Set

import evs_client

MAPPING_PATH = pathlib.Path("soa_entity_mapping.json")

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def collect_codes(mapping: dict) -> Set[str]:
    codes: Set[str] = set()
    for entity, sections in mapping.items():
        for section_name, section in sections.items():
            for field, meta in section.items():
                # We only fetch codes from explicit value lists (controlled terminology)
                for val in meta.get("allowed_values", []):
                    cc = val.get("concept_c_code")
                    if cc:
                        codes.add(cc)
    return codes


def main() -> None:
    if not MAPPING_PATH.exists():
        logger.error("Mapping file %s not found", MAPPING_PATH)
        sys.exit(1)

    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    codes = collect_codes(mapping)
    logger.info("Found %d unique c_codes", len(codes))

    cached = 0
    skipped = 0
    for code in sorted(codes):
        details = evs_client.fetch_code(code)
        if details is None:
            logger.debug("[EVS] %s not found (skipped)", code)
            skipped += 1
        else:
            cached += 1
    logger.info("Cache warmed: %d cached, %d skipped (likely list roots/retired).", cached, skipped)
    # Always exit 0 so CI and local runs continue even if some codes are unavailable.


if __name__ == "__main__":
    main()
