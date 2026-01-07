"""
Centralized constants for Protocol2USDM pipeline.

All pipeline-wide constants should be defined here to ensure consistency.
"""

# USDM Schema Version
USDM_VERSION: str = "4.0"

# System Metadata (appears in output JSON)
SYSTEM_NAME: str = "Protocol2USDM"
SYSTEM_VERSION: str = "0.1.0"

# Default Model Preference
DEFAULT_MODEL: str = "claude-opus-4-5"

# Pipeline Output File Names
OUTPUT_FILES = {
    "prompt": "1_llm_prompt.txt",
    "soa_pages": "2_soa_pages.json",
    "images_dir": "3_soa_images",
    "header_structure": "4_soa_header_structure.json",
    "raw_text": "5_raw_text_soa.json",
    "raw_vision": "6_raw_vision_soa.json",
    "postprocessed_text": "7_postprocessed_text_soa.json",
    "postprocessed_vision": "8_postprocessed_vision_soa.json",
    "final_soa": "9_reconciled_soa.json",
}

# Reasoning Models (special parameter handling)
REASONING_MODELS = [
    'o1', 'o1-mini',
    'o3', 'o3-mini', 'o3-mini-high',
    'gpt-5', 'gpt-5-mini',
    'gpt-5.1', 'gpt-5.1-mini'
]

# USDM Entity Types
USDM_ENTITY_TYPES = [
    'activities',
    'plannedTimepoints',
    'encounters',
    'epochs',
    'activityGroups',
    'activityTimepoints',
]

# USDM Timing Codes (for normalization)
TIMING_CODES = {
    "Fixed Reference": "C99073",
    "Start to Start": "C99074",
    "Visit": "C25426",
}
