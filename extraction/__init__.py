"""
Extraction module for Protocol2USDM pipeline.

This module contains the core extraction logic:
- soa_finder: Locate SoA pages in protocol PDFs
- header_analyzer: Vision-based structure extraction (epochs, encounters, timepoints)
- text_extractor: Text-based data extraction (activities, ticks)
- validator: Vision-based validation of text extraction
- pipeline: Orchestrates the complete extraction workflow
- metadata: Study identity & metadata extraction (Phase 2)
- eligibility: Inclusion/exclusion criteria extraction (Phase 1)

Design Principle:
- Vision extracts STRUCTURE (column headers, row groups)
- Text extracts DATA (activity details, tick matrix)
- Vision validates Text (confirms ticks, flags hallucinations)
"""

from .soa_finder import (
    find_soa_pages,
    find_soa_pages_heuristic,
    extract_soa_text,
    extract_soa_images,
)
from .header_analyzer import (
    analyze_soa_headers, 
    HeaderAnalysisResult,
    load_header_structure,
    save_header_structure,
)
from .text_extractor import (
    extract_soa_from_text,
    TextExtractionResult,
    build_usdm_output,
)
from .validator import (
    validate_extraction,
    ValidationResult,
    ValidationIssue,
    IssueType,
)
from .pipeline import (
    run_extraction_pipeline,
    run_from_files,
    PipelineConfig,
    PipelineResult,
)
from .metadata import (
    extract_study_metadata,
    MetadataExtractionResult,
    StudyMetadata,
    StudyTitle,
    StudyIdentifier,
    Organization,
    StudyRole,
    Indication,
)
from .eligibility import (
    extract_eligibility_criteria,
    EligibilityExtractionResult,
    EligibilityCriterion,
    EligibilityCriterionItem,
    StudyDesignPopulation,
    CriterionCategory,
)

__all__ = [
    # SoA Finder
    "find_soa_pages",
    "find_soa_pages_heuristic",
    "extract_soa_text",
    "extract_soa_images",
    # Header Analyzer
    "analyze_soa_headers",
    "HeaderAnalysisResult",
    "load_header_structure",
    "save_header_structure",
    # Text Extractor
    "extract_soa_from_text",
    "TextExtractionResult",
    "build_usdm_output",
    # Validator
    "validate_extraction",
    "ValidationResult",
    "ValidationIssue",
    "IssueType",
    # Pipeline
    "run_extraction_pipeline",
    "run_from_files",
    "PipelineConfig",
    "PipelineResult",
    # Metadata (Phase 2)
    "extract_study_metadata",
    "MetadataExtractionResult",
    "StudyMetadata",
    "StudyTitle",
    "StudyIdentifier",
    "Organization",
    "StudyRole",
    "Indication",
    # Eligibility (Phase 1)
    "extract_eligibility_criteria",
    "EligibilityExtractionResult",
    "EligibilityCriterion",
    "EligibilityCriterionItem",
    "StudyDesignPopulation",
    "CriterionCategory",
]
