"""
JSON Utilities - Backward Compatibility Wrapper

This module provides backward compatibility for existing code.
New code should import from core.json_utils directly.

Usage (legacy):
    from json_utils import extract_json_str, clean_llm_json
    
Usage (preferred):
    from core.json_utils import parse_llm_json, extract_json_str
"""

# Re-export from core for backward compatibility
from core.json_utils import (
    extract_json_str,
    parse_llm_json,
    standardize_ids,
    clean_json_response,
    make_hashable,
    get_timeline,
)

# Legacy function kept for backward compatibility
def clean_llm_json(raw):
    """
    Simple cleaner: strip code fences and trailing text after the last closing brace.
    
    DEPRECATED: Use core.json_utils.clean_json_response() instead.
    """
    if not raw:
        return raw
    raw = raw.strip()
    # Remove code block markers
    if raw.startswith('```json'):
        raw = raw[7:]
    if raw.startswith('```'):
        raw = raw[3:]
    if raw.endswith('```'):
        raw = raw[:-3]
    # Remove anything after the last closing brace
    last_brace = raw.rfind('}')
    if last_brace != -1:
        raw = raw[:last_brace + 1]
    return raw
