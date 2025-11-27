"""
Eligibility Criteria Extraction Module - Phase 1 of USDM Expansion

Extracts inclusion and exclusion criteria from protocol Section 4-5:
- EligibilityCriterion
- EligibilityCriterionItem
- StudyDesignPopulation
"""

from .extractor import (
    extract_eligibility_criteria,
    EligibilityExtractionResult,
)
from .schema import (
    EligibilityCriterion,
    EligibilityCriterionItem,
    StudyDesignPopulation,
    CriterionCategory,
)

__all__ = [
    # Main extraction function
    "extract_eligibility_criteria",
    "EligibilityExtractionResult",
    # Schema classes
    "EligibilityCriterion",
    "EligibilityCriterionItem",
    "StudyDesignPopulation",
    "CriterionCategory",
]
