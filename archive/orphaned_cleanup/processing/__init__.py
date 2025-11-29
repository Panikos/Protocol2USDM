"""
Processing module for USDM normalization and enrichment.

This module handles:
- Name vs timing normalization
- Required field defaulting
- Entity enrichment (codes, descriptions)
- USDM structure building
"""

from .normalizer import (
    normalize_names_vs_timing,
    normalize_timing_codes,
    clean_entity_names,
)

from .enricher import (
    ensure_required_fields,
    enrich_with_codes,
)

__all__ = [
    # Normalizer
    "normalize_names_vs_timing",
    "normalize_timing_codes",
    "clean_entity_names",
    # Enricher
    "ensure_required_fields",
    "enrich_with_codes",
]
