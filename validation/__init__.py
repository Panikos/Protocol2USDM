"""
USDM Validation Package

Provides schema validation and CDISC conformance checking.

Architecture (v6.3+):
    1. usdm_validator - PRIMARY: Official CDISC usdm package (Pydantic models)
    2. cdisc_conformance - CDISC CORE conformance rules

The official usdm package (pip install usdm) provides authoritative validation
against the USDM 4.0 schema using Pydantic models.

Schema fixes are now handled UPSTREAM by:
    - core/usdm_types_generated.py:normalize_usdm_data() - type inference
    - Extraction prompts - proper entity structure from LLM

Archived (see archive/orphaned_cleanup/):
    - openapi_validator.py - Deprecated OpenAPI validator
    - schema_validator.py - Deprecated basic validator
    - USDM OpenAPI schema/ - OpenAPI spec files
"""

# PRIMARY: Official USDM package validator
from .usdm_validator import (
    USDMValidator,
    validate_usdm_file,
    validate_usdm_dict,
    ValidationResult,
    ValidationIssue,
    ValidationSeverity,
    get_usdm_schema,
    HAS_USDM,
    USDM_VERSION,
)

# CDISC conformance
from .cdisc_conformance import run_cdisc_conformance


def validate_usdm(data):
    """
    Validate USDM data against schema using official usdm package.
    
    Args:
        data: USDM JSON data (dict or file path)
        
    Returns:
        ValidationResult
    """
    if isinstance(data, str):
        return validate_usdm_file(data)
    else:
        return validate_usdm_dict(data)


__all__ = [
    # PRIMARY: Official USDM validator
    'USDMValidator',
    'validate_usdm',
    'validate_usdm_file',
    'validate_usdm_dict',
    'ValidationResult',
    'ValidationIssue',
    'ValidationSeverity',
    'get_usdm_schema',
    'HAS_USDM',
    'USDM_VERSION',
    # CDISC conformance
    'run_cdisc_conformance',
]
