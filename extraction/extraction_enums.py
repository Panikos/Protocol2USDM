"""
Centralized Enum Configuration for Extraction Pipeline

This module provides a single source of truth for all enum types used during
protocol extraction. It re-exports enums from their domain-specific schema files
and documents which values indicate "not extracted from source".

IMPORTANT: The UNKNOWN value (empty string "") indicates data was NOT extracted
from the source protocol. This should be displayed in UI as "Not extracted" or
similar, and should trigger validation warnings in processing_report.json.

Usage:
    from extraction.extraction_enums import (
        ArmType, BlindingSchema, RandomizationType,
        ObjectiveLevel, EndpointLevel,
        InterventionRole,
        DosingFrequency, RouteOfAdministration,
        AnchorType, RepetitionType,
        TitleType, OrganizationType, StudyRoleCode,
        ProcedureType, DeviceType,
        ImpactLevel, ChangeType, ReasonCategory,
        TimingType, TimingRelativeToFrom,
    )
"""

# =============================================================================
# Study Design Enums
# =============================================================================
from extraction.studydesign.schema import (
    ArmType,           # UNKNOWN, EXPERIMENTAL, ACTIVE_COMPARATOR, PLACEBO_COMPARATOR, etc.
    BlindingSchema,    # UNKNOWN, OPEN_LABEL, SINGLE_BLIND, DOUBLE_BLIND, etc.
    RandomizationType, # UNKNOWN, RANDOMIZED, NON_RANDOMIZED
    ControlType,       # PLACEBO, ACTIVE, DOSE_COMPARISON, NO_TREATMENT, HISTORICAL
)

# =============================================================================
# Objectives Enums
# =============================================================================
from extraction.objectives.schema import (
    ObjectiveLevel,    # UNKNOWN, PRIMARY, SECONDARY, EXPLORATORY
    EndpointLevel,     # UNKNOWN, PRIMARY, SECONDARY, EXPLORATORY
    IntercurrentEventStrategy,  # TREATMENT_POLICY, COMPOSITE, HYPOTHETICAL, etc.
)

# =============================================================================
# Interventions Enums
# =============================================================================
from extraction.interventions.schema import (
    InterventionRole,         # UNKNOWN, INVESTIGATIONAL, COMPARATOR, PLACEBO, etc.
    RouteOfAdministration as InterventionRoute,  # ORAL, INTRAVENOUS, etc. (alias)
    DoseForm,                 # TABLET, CAPSULE, SOLUTION, etc.
)

# =============================================================================
# Metadata Enums
# =============================================================================
from extraction.metadata.schema import (
    TitleType,         # UNKNOWN, BRIEF, OFFICIAL, PUBLIC, SCIENTIFIC, ACRONYM
    OrganizationType,  # UNKNOWN, REGULATORY_AGENCY, PHARMACEUTICAL_COMPANY, CRO, etc.
    StudyRoleCode,     # UNKNOWN, SPONSOR, CO_SPONSOR, INVESTIGATOR, PI, etc.
    IdentifierType,    # NCT, SPONSOR_PROTOCOL, EUDRACT, etc. (no UNKNOWN - always has type)
)

# =============================================================================
# Procedures Enums
# =============================================================================
from extraction.procedures.schema import (
    ProcedureType,     # UNKNOWN, DIAGNOSTIC, THERAPEUTIC, SURGICAL, SAMPLING, etc.
    DeviceType,        # UNKNOWN, DRUG_DELIVERY, DIAGNOSTIC, MONITORING, etc.
)

# =============================================================================
# Amendments Enums
# =============================================================================
from extraction.amendments.schema import (
    ImpactLevel,       # UNKNOWN, MAJOR, MINOR, ADMINISTRATIVE
    ChangeType,        # UNKNOWN, ADDITION, DELETION, MODIFICATION, CLARIFICATION
    ReasonCategory,    # UNKNOWN, SAFETY, EFFICACY, REGULATORY, OPERATIONAL, etc.
)

# =============================================================================
# Scheduling Enums
# =============================================================================
from extraction.scheduling.schema import (
    TimingType,        # UNKNOWN, BEFORE, AFTER, WITHIN, AT, BETWEEN
    TimingRelativeToFrom,  # UNKNOWN, STUDY_START, RANDOMIZATION, FIRST_DOSE, etc.
)

# =============================================================================
# Eligibility Enums
# =============================================================================
from extraction.eligibility.schema import (
    CriterionCategory,  # INCLUSION, EXCLUSION (no UNKNOWN - binary choice)
)

# =============================================================================
# Execution Model Enums
# =============================================================================
from extraction.execution.schema import (
    DosingFrequency,          # UNKNOWN, ONCE_DAILY (QD), TWICE_DAILY (BID), etc.
    RouteOfAdministration,    # UNKNOWN, ORAL, IV, SC, IM, etc.
    AnchorType,               # CUSTOM, FIRST_DOSE, DAY_1, RANDOMIZATION, etc.
    RepetitionType,           # UNKNOWN, DAILY, INTERVAL, CYCLE, CONTINUOUS, etc.
    ExecutionType,            # WINDOW, EPISODE, SINGLE, RECURRING
    EndpointType,             # PRIMARY, SECONDARY, EXPLORATORY, SAFETY
    VariableType,             # BASELINE, CHANGE_FROM_BASELINE, etc.
    StateType,                # SCREENING, ENROLLED, RANDOMIZED, etc.
)


# =============================================================================
# Enum Configuration: Which values represent "not extracted"
# =============================================================================

# Maps enum classes to their "not extracted" value
UNKNOWN_VALUES = {
    # Study Design
    ArmType: ArmType.UNKNOWN,
    BlindingSchema: BlindingSchema.UNKNOWN,
    RandomizationType: RandomizationType.UNKNOWN,
    
    # Objectives
    ObjectiveLevel: ObjectiveLevel.UNKNOWN,
    EndpointLevel: EndpointLevel.UNKNOWN,
    
    # Interventions
    InterventionRole: InterventionRole.UNKNOWN,
    
    # Metadata
    TitleType: TitleType.UNKNOWN,
    OrganizationType: OrganizationType.UNKNOWN,
    StudyRoleCode: StudyRoleCode.UNKNOWN,
    
    # Procedures
    ProcedureType: ProcedureType.UNKNOWN,
    DeviceType: DeviceType.UNKNOWN,
    
    # Amendments
    ImpactLevel: ImpactLevel.UNKNOWN,
    ChangeType: ChangeType.UNKNOWN,
    ReasonCategory: ReasonCategory.UNKNOWN,
    
    # Scheduling
    TimingType: TimingType.UNKNOWN,
    TimingRelativeToFrom: TimingRelativeToFrom.UNKNOWN,
    
    # Execution Model
    DosingFrequency: DosingFrequency.UNKNOWN,
    RouteOfAdministration: RouteOfAdministration.UNKNOWN,
    AnchorType: AnchorType.CUSTOM,  # CUSTOM serves as "not specifically identified"
    RepetitionType: RepetitionType.UNKNOWN,
}


def is_unknown(value) -> bool:
    """Check if an enum value represents 'not extracted from source'."""
    if value is None:
        return True
    enum_class = type(value)
    unknown_val = UNKNOWN_VALUES.get(enum_class)
    return value == unknown_val if unknown_val else False


def get_display_value(value) -> str:
    """Get display-friendly string for an enum value.
    
    Returns "Not extracted" for UNKNOWN values, otherwise the enum's value.
    """
    if value is None or is_unknown(value):
        return "Not extracted"
    return value.value if hasattr(value, 'value') else str(value)


# =============================================================================
# Enums WITHOUT UNKNOWN (intentionally - they have fixed/binary choices)
# =============================================================================
# - ControlType: Specific control type or None
# - IntercurrentEventStrategy: ICH E9(R1) defined strategies
# - IdentifierType: Always has a specific type (NCT, EUDRACT, etc.)
# - CriterionCategory: Binary choice (INCLUSION or EXCLUSION)
# - ExecutionType: Specific execution semantics
# - EndpointType: Specific endpoint classification
# - VariableType: Specific variable type
# - StateType: Specific subject state
# - DoseForm: Specific form or None


# =============================================================================
# Values NOT suitable for enum configuration (free-form strings)
# =============================================================================
# The following values were identified but are NOT suitable for enum configuration
# because they are free-form text fields that vary widely across protocols:
#
# 1. Dose Unit ('mg', 'mcg', 'mL', 'IU', 'units', etc.)
#    - Too many possible values to enumerate
#    - Should remain empty string "" when not extracted
#
# 2. Endpoint Purpose ('Efficacy', 'Safety', 'PK', 'PD', 'Biomarker', etc.)
#    - Free-form text describing the endpoint's intent
#    - Should remain empty string "" or None when not extracted
#
# 3. Trial Type ('Interventional', 'Observational', etc.)
#    - While limited options exist, protocols often use custom descriptions
#    - Should remain empty string "" when not extracted
#
# 4. Ingredient Role ('Active', 'Inactive', 'Excipient', etc.)
#    - Simple string field with few common values
#    - Should remain empty string "" when not extracted
#
# 5. Allocation Ratio ('1:1', '2:1', '1:1:1', etc.)
#    - Numeric ratios as strings, highly variable
#    - Should remain empty string "" when not extracted
#
# 6. Randomization Method ('Simple randomization', 'Block randomization', etc.)
#    - Free-form description of randomization approach
#    - Should remain empty string "" when not extracted
# =============================================================================
