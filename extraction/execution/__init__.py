"""
Execution Model Extractors

This module provides extractors for execution-level semantics that enable
deterministic synthetic data generation from USDM output.

Extractors:
- TimeAnchorExtractor: Identifies canonical time anchors for timelines
- RepetitionExtractor: Detects cycles, intervals, and repeated collections
- ExecutionTypeClassifier: Classifies activities as WINDOW vs EPISODE
- TraversalExtractor: Extracts required subject paths through study
- FootnoteConditionExtractor: Converts footnotes to structured Conditions

All extractors produce USDM-compliant output using extensionAttributes
for execution-specific metadata.
"""

from .schema import (
    # Phase 1
    TimeAnchor,
    AnchorType,
    Repetition,
    RepetitionType,
    ExecutionTypeAssignment,
    ExecutionType,
    SamplingConstraint,
    ActivityBinding,
    # Phase 2
    TraversalConstraint,
    CrossoverDesign,
    FootnoteCondition,
    # Phase 3
    EndpointAlgorithm,
    EndpointType,
    DerivedVariable,
    VariableType,
    SubjectStateMachine,
    StateTransition,
    StateType,
    # Phase 4
    DosingRegimen,
    DoseLevel,
    DosingFrequency,
    RouteOfAdministration,
    VisitWindow,
    StratificationFactor,
    RandomizationScheme,
    # Container
    ExecutionModelData,
    ExecutionModelResult,
)

from .time_anchor_extractor import extract_time_anchors, find_anchor_pages
from .repetition_extractor import extract_repetitions
from .execution_type_classifier import classify_execution_types
from .crossover_extractor import extract_crossover_design
from .traversal_extractor import extract_traversal_constraints
from .footnote_condition_extractor import extract_footnote_conditions
from .endpoint_extractor import extract_endpoint_algorithms
from .derived_variable_extractor import extract_derived_variables
from .state_machine_generator import generate_state_machine
from .sampling_density_extractor import extract_sampling_density
from .dosing_regimen_extractor import extract_dosing_regimens
from .visit_window_extractor import extract_visit_windows
from .stratification_extractor import extract_stratification
from .validation import (
    validate_execution_model,
    ValidationResult,
    ValidationIssue,
    ValidationSeverity,
    create_validation_summary,
)
from .export import (
    export_to_csv,
    generate_markdown_report,
    save_report,
)
from .config import (
    ExtractionConfig,
    load_config,
    save_config,
    create_default_config,
)
from .cache import (
    ExecutionCache,
    get_cache,
    set_cache,
    cached,
)
from .pipeline_integration import (
    extract_execution_model,
    enrich_usdm_with_execution_model,
    create_execution_model_summary,
)

__all__ = [
    # Phase 1 Schema
    "TimeAnchor",
    "AnchorType", 
    "Repetition",
    "RepetitionType",
    "ExecutionType",
    "SamplingConstraint",
    "ActivityBinding",
    # Phase 2 Schema
    "TraversalConstraint",
    "CrossoverDesign",
    "FootnoteCondition",
    # Phase 3 Schema
    "EndpointAlgorithm",
    "EndpointType",
    "DerivedVariable",
    "VariableType",
    "SubjectStateMachine",
    "StateTransition",
    "StateType",
    # Phase 4 Schema
    "DosingRegimen",
    "DoseLevel",
    "DosingFrequency",
    "RouteOfAdministration",
    "VisitWindow",
    "StratificationFactor",
    "RandomizationScheme",
    # Container
    "ExecutionModelData",
    "ExecutionModelResult",
    # Phase 1 Extractors
    "extract_time_anchors",
    "find_anchor_pages",
    "extract_repetitions",
    "classify_execution_types",
    # Phase 2 Extractors
    "extract_crossover_design",
    "extract_traversal_constraints",
    "extract_footnote_conditions",
    # Phase 3 Extractors
    "extract_endpoint_algorithms",
    "extract_derived_variables",
    "generate_state_machine",
    # Phase 4 Extractors
    "extract_dosing_regimens",
    "extract_visit_windows",
    "extract_stratification",
    # Phase 5 Extractor
    "extract_sampling_density",
    # Pipeline integration
    "extract_execution_model",
    "enrich_usdm_with_execution_model",
    "create_execution_model_summary",
    # Validation
    "validate_execution_model",
    "ValidationResult",
    "ValidationIssue",
    "ValidationSeverity",
    "create_validation_summary",
    # Export
    "export_to_csv",
    "generate_markdown_report",
    "save_report",
    # Configuration
    "ExtractionConfig",
    "load_config",
    "save_config",
    "create_default_config",
    # Caching
    "ExecutionCache",
    "get_cache",
    "set_cache",
    "cached",
]
