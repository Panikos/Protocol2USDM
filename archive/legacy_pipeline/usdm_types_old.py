"""
USDM Type Definitions - Typed dataclasses for USDM v4.0 entities.

This module provides the primary interface for USDM types. It imports from:
1. usdm_types_generated.py - Types generated from official CDISC schema (preferred)
2. usdm_types_v4.py - Manually maintained types (fallback/legacy)

The schema-generated types are the source of truth, derived from:
https://github.com/cdisc-org/DDF-RA/blob/main/Deliverables/UML/dataStructure.yml

Migration Guide:
- Epoch → StudyEpoch
- ActivityTimepoint → ScheduledActivityInstance  
- PlannedTimepoint → Timing + Encounter
- ActivityGroup → Activity with childIds
- Timeline → StudyDesign with ScheduleTimeline

Usage:
    from core.usdm_types import Activity, Encounter, Code
    
    activity = Activity(name="Blood Draw")
    print(activity.to_dict())  # All required fields included
"""

# Try to import from schema-generated types first (source of truth)
try:
    from core.usdm_types_generated import (
        # Core types
        Code,
        AliasCode,
        CommentAnnotation,
        Range,
        Quantity,
        
        # Study structure
        Study,
        StudyVersion,
        StudyDesign,
        StudyArm,
        StudyCell,
        
        # Metadata
        StudyTitle,
        StudyIdentifier,
        Organization,
        
        # SoA entities
        Activity,
        Encounter,
        StudyEpoch,
        Epoch,  # Alias for StudyEpoch
        ScheduleTimeline,
        ScheduledActivityInstance,
        ScheduleTimelineExit,
        Timing,
        
        # Eligibility
        EligibilityCriterion,
        StudyDesignPopulation,
        
        # Objectives
        Objective,
        Endpoint,
        
        # Interventions
        StudyIntervention,
        Procedure,
        
        # Helpers
        generate_uuid,
        create_wrapper_input,
        USDMEntity,
    )
    
    USING_GENERATED_TYPES = True
    
except ImportError:
    # Fallback to manually maintained types
    USING_GENERATED_TYPES = False
    from core.usdm_types_v4 import (
        # Core types
        Code,
        Range,
        Duration,
        Quantity,
        
        # Study structure
        Study,
        StudyVersion,
        StudyDesign,
        StudyArm,
        StudyCell,
        StudyCohort,
        
        # Metadata
        StudyTitle,
        StudyIdentifier,
        Organization,
        Indication,
        
        # SoA entities
        Activity,
        Encounter,
        StudyEpoch,
        Epoch,  # Alias for StudyEpoch
        ScheduleTimeline,
        ScheduledActivityInstance,
        ScheduleTimelineExit,
        Timing,
        
        # Eligibility
        EligibilityCriterion,
        EligibilityCriterionItem,
        StudyDesignPopulation,
        
        # Objectives
        Objective,
        Endpoint,
        Estimand,
        IntercurrentEvent,
        
        # Interventions
        StudyIntervention,
        AdministrableProduct,
        Administration,
        Procedure,
        
        # Narrative
        NarrativeContent,
        Abbreviation,
        StudyAmendment,
        
        # Scheduling
        Condition,
        TransitionRule,
        
        # Backward compatibility (deprecated)
        ActivityTimepoint,
        PlannedTimepoint,
        ActivityGroup,
        
        # Containers
        HeaderStructure,
        Timeline,
        
        # Functions
        create_wrapper_input,
    )
    from core.usdm_types_v4 import generate_uuid, AliasCode, CommentAnnotation

from enum import Enum


class EntityType(Enum):
    """USDM entity instance types."""
    ACTIVITY = "Activity"
    SCHEDULED_ACTIVITY_INSTANCE = "ScheduledActivityInstance"
    ENCOUNTER = "Encounter"
    STUDY_EPOCH = "StudyEpoch"
    SCHEDULE_TIMELINE = "ScheduleTimeline"
    TIMING = "Timing"
    # Deprecated names (for backward compatibility)
    PLANNED_TIMEPOINT = "Timing"
    EPOCH = "StudyEpoch"
    ACTIVITY_GROUP = "Activity"
    ACTIVITY_TIMEPOINT = "ScheduledActivityInstance"


# All types are now imported from usdm_types_v4.py above.
# The old class definitions have been removed to avoid duplication.

__all__ = [
    # Core types
    'Code', 'Range', 'Duration', 'Quantity',
    # Study structure
    'Study', 'StudyVersion', 'StudyDesign', 'StudyArm', 'StudyCell', 'StudyCohort',
    # Metadata
    'StudyTitle', 'StudyIdentifier', 'Organization', 'Indication',
    # SoA entities
    'Activity', 'Encounter', 'StudyEpoch', 'Epoch', 'ScheduleTimeline',
    'ScheduledActivityInstance', 'ScheduleTimelineExit', 'Timing',
    # Eligibility
    'EligibilityCriterion', 'EligibilityCriterionItem', 'StudyDesignPopulation',
    # Objectives
    'Objective', 'Endpoint', 'Estimand', 'IntercurrentEvent',
    # Interventions
    'StudyIntervention', 'AdministrableProduct', 'Administration', 'Procedure',
    # Narrative
    'NarrativeContent', 'Abbreviation', 'StudyAmendment',
    # Scheduling
    'Condition', 'TransitionRule',
    # Backward compatibility
    'ActivityTimepoint', 'PlannedTimepoint', 'ActivityGroup',
    # Containers
    'HeaderStructure', 'Timeline',
    # Functions
    'create_wrapper_input',
    # Enums
    'EntityType',
]
