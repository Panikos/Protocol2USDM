"""
Amendment Details Extraction Module - Phase 13

Extracts USDM entities:
- StudyAmendmentImpact
- StudyAmendmentReason
- StudyChange
"""

from .schema import (
    StudyAmendmentImpact,
    StudyAmendmentReason,
    StudyChange,
    AmendmentDetailsData,
    AmendmentDetailsResult,
    ImpactLevel,
    ChangeType,
    ReasonCategory,
)
from .extractor import extract_amendment_details

__all__ = [
    'StudyAmendmentImpact',
    'StudyAmendmentReason',
    'StudyChange',
    'AmendmentDetailsData',
    'AmendmentDetailsResult',
    'ImpactLevel',
    'ChangeType',
    'ReasonCategory',
    'extract_amendment_details',
]
