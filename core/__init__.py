"""
Core utilities for Protocol2USDM pipeline.

This module consolidates shared functionality to eliminate duplication:
- LLM client management
- JSON parsing and cleaning
- Provenance tracking
- Constants and configuration
"""

from .llm_client import (
    get_llm_client,
    LLMConfig,
    LLMResponse,
    get_default_model,
    call_llm,
    call_llm_with_image,
    acall_llm,
    agenerate_text,
)
from .json_utils import (
    parse_llm_json,
    extract_json_str,
    standardize_ids,
    clean_json_response,
    get_timeline,
    make_hashable,
)
from .provenance import ProvenanceTracker, ProvenanceSource
from .pdf_utils import (
    extract_text_from_pages,
    get_page_count,
    render_page_to_image,
    render_pages_to_images,
)
from .constants import (
    USDM_VERSION,
    SYSTEM_NAME,
    VERSION,
    SYSTEM_VERSION,
    DEFAULT_MODEL,
    REASONING_MODELS,
)

# Unified Reconciliation Framework
from .reconciliation import (
    # Base
    BaseReconciler,
    EntityContribution,
    ReconciledEntity,
    fuzzy_match_names,
    normalize_for_matching,
    # Epochs
    EpochReconciler,
    EpochContribution,
    ReconciledEpoch,
    reconcile_epochs_from_pipeline,
    # Activities
    ActivityReconciler,
    ActivityContribution,
    ReconciledActivity,
    reconcile_activities_from_pipeline,
    # Encounters
    EncounterReconciler,
    EncounterContribution,
    ReconciledEncounter,
    reconcile_encounters_from_pipeline,
)

__all__ = [
    # LLM Client
    "get_llm_client",
    "get_default_model",
    "call_llm",
    "call_llm_with_image",
    "acall_llm",
    "agenerate_text",
    "LLMConfig",
    "LLMResponse",
    # JSON Utilities
    "parse_llm_json",
    "extract_json_str",
    "standardize_ids",
    "clean_json_response",
    "get_timeline",
    "make_hashable",
    # Provenance
    "ProvenanceTracker",
    "ProvenanceSource",
    # PDF Utilities
    "extract_text_from_pages",
    "get_page_count",
    "render_page_to_image",
    "render_pages_to_images",
    # Constants
    "USDM_VERSION",
    "SYSTEM_NAME",
    "VERSION",
    "SYSTEM_VERSION",
    "DEFAULT_MODEL",
    "REASONING_MODELS",
    # Reconciliation Framework
    "BaseReconciler",
    "EntityContribution",
    "ReconciledEntity",
    "fuzzy_match_names",
    "normalize_for_matching",
    # Epochs
    "EpochReconciler",
    "EpochContribution",
    "ReconciledEpoch",
    "reconcile_epochs_from_pipeline",
    # Activities
    "ActivityReconciler",
    "ActivityContribution",
    "ReconciledActivity",
    "reconcile_activities_from_pipeline",
    # Encounters
    "EncounterReconciler",
    "EncounterContribution",
    "ReconciledEncounter",
    "reconcile_encounters_from_pipeline",
]
