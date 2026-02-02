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
- objectives: Objectives & endpoints extraction (Phase 3)
- studydesign: Study design structure extraction (Phase 4)
- interventions: Interventions & products extraction (Phase 5)
- narrative: Document structure & abbreviations extraction (Phase 7)
- advanced: Amendments, geographic scope, sites extraction (Phase 8)
- execution: Execution model extraction for synthetic data (Phase 9)
  - Time anchors, repetitions, cycles, execution types
  - Enables deterministic synthetic data generation

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
from .objectives import (
    extract_objectives_endpoints,
    ObjectivesExtractionResult,
    Objective,
    Endpoint,
    Estimand,
    IntercurrentEvent,
    ObjectivesData,
    ObjectiveLevel,
    EndpointLevel,
)
from .studydesign import (
    extract_study_design,
    StudyDesignExtractionResult,
    StudyDesignData,
    InterventionalStudyDesign,
    StudyArm,
    StudyCell,
    StudyCohort,
    ArmType,
    BlindingSchema,
)
from .interventions import (
    extract_interventions,
    InterventionsExtractionResult,
    InterventionsData,
    StudyIntervention,
    AdministrableProduct,
    Administration,
    MedicalDevice,
    Substance,
)
from .narrative import (
    extract_narrative_structure,
    NarrativeExtractionResult,
    NarrativeData,
    NarrativeContent,
    Abbreviation,
    StudyDefinitionDocument,
)
from .advanced import (
    extract_advanced_entities,
    AdvancedExtractionResult,
    AdvancedData,
    StudyAmendment,
    GeographicScope,
    Country,
)
from .execution import (
    extract_execution_model,
    enrich_usdm_with_execution_model,
    create_execution_model_summary,
    extract_time_anchors,
    extract_repetitions,
    classify_execution_types,
    ExecutionModelResult,
    ExecutionModelData,
    TimeAnchor,
    AnchorType,
    Repetition,
    RepetitionType,
    ExecutionType,
    SamplingConstraint,
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
    # Objectives (Phase 3)
    "extract_objectives_endpoints",
    "ObjectivesExtractionResult",
    "Objective",
    "Endpoint",
    "Estimand",
    "IntercurrentEvent",
    "ObjectivesData",
    "ObjectiveLevel",
    "EndpointLevel",
    # Study Design (Phase 4)
    "extract_study_design",
    "StudyDesignExtractionResult",
    "StudyDesignData",
    "InterventionalStudyDesign",
    "StudyArm",
    "StudyCell",
    "StudyCohort",
    "ArmType",
    "BlindingSchema",
    # Interventions (Phase 5)
    "extract_interventions",
    "InterventionsExtractionResult",
    "InterventionsData",
    "StudyIntervention",
    "AdministrableProduct",
    "Administration",
    "MedicalDevice",
    "Substance",
    # Narrative (Phase 7)
    "extract_narrative_structure",
    "NarrativeExtractionResult",
    "NarrativeData",
    "NarrativeContent",
    "Abbreviation",
    "StudyDefinitionDocument",
    # Advanced (Phase 8)
    "extract_advanced_entities",
    "AdvancedExtractionResult",
    "AdvancedData",
    "StudyAmendment",
    "GeographicScope",
    "Country",
    # Execution Model (Phase 9)
    "extract_execution_model",
    "enrich_usdm_with_execution_model",
    "create_execution_model_summary",
    "extract_time_anchors",
    "extract_repetitions",
    "classify_execution_types",
    "ExecutionModelResult",
    "ExecutionModelData",
    "TimeAnchor",
    "AnchorType",
    "Repetition",
    "RepetitionType",
    "ExecutionType",
    "SamplingConstraint",
]
