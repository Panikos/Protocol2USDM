"""
Protocol2USDM Constants - Backward Compatibility Wrapper

This module provides backward compatibility for existing code.
New code should import from core.constants directly.
"""

# Re-export from core for backward compatibility
from core.constants import (
    USDM_VERSION,
    SYSTEM_NAME,
    SYSTEM_VERSION,
    DEFAULT_MODEL,
    OUTPUT_FILES,
    REASONING_MODELS,
    USDM_ENTITY_TYPES,
    TIMING_CODES,
)
