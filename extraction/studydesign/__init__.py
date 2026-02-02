"""
Study Design Structure Extraction Module - Phase 4 of USDM Expansion

Extracts study design structure from protocol:
- InterventionalStudyDesign / ObservationalStudyDesign
- StudyArm
- StudyCell (Arm × Epoch matrix)
- StudyCohort
"""

from .extractor import (
    extract_study_design,
    StudyDesignExtractionResult,
)
from .schema import (
    StudyDesignData,
    InterventionalStudyDesign,
    StudyArm,
    StudyCell,
    StudyCohort,
    StudyElement,
    ArmType,
    BlindingSchema,
    AllocationRatio,
)

__all__ = [
    # Main extraction function
    "extract_study_design",
    "StudyDesignExtractionResult",
    # Schema classes
    "StudyDesignData",
    "InterventionalStudyDesign",
    "StudyArm",
    "StudyCell",
    "StudyCohort",
    "StudyElement",
    "ArmType",
    "BlindingSchema",
    "AllocationRatio",
]
