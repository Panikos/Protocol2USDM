"""
Processing Warnings Module

Collects non-blocking processing issues that should be reported in the processing report.
Separated from pipeline_integration.py to avoid circular imports.
"""

from typing import Dict, Any, List

# Module-level list to collect processing warnings during execution
_processing_warnings: List[Dict[str, Any]] = []


def get_processing_warnings() -> List[Dict[str, Any]]:
    """Get collected processing warnings and clear the list."""
    global _processing_warnings
    warnings = _processing_warnings.copy()
    _processing_warnings = []
    return warnings


def _add_processing_warning(
    category: str,
    message: str,
    context: str = "",
    severity: str = "warning",
    details: dict = None
) -> None:
    """Add a processing warning to the collection.
    
    Args:
        category: Type of warning (e.g., 'extraction_failure', 'resolution_failure')
        message: Human-readable description of the issue
        context: Additional context (e.g., which extractor, what data)
        severity: 'warning', 'error', or 'info'
        details: Optional dict with additional structured data
    """
    global _processing_warnings
    warning = {
        "category": category,
        "message": message,
        "context": context,
        "severity": severity,
    }
    if details:
        warning["details"] = details
    _processing_warnings.append(warning)
