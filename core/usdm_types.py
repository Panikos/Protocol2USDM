"""
USDM Type Definitions - Official CDISC USDM v4.0 Entities

This module provides Python dataclasses for all USDM entities, generated from
the official CDISC dataStructure.yml schema.

Source of Truth: https://github.com/cdisc-org/DDF-RA/blob/main/Deliverables/UML/dataStructure.yml

All types include:
- Correct required fields per schema
- NCI codes where defined
- Auto-generated UUIDs for id fields
- Intelligent defaults for required Code fields (type, dataOriginType, etc.)

Usage:
    from core.usdm_types import Activity, Encounter, Code
    
    activity = Activity(name="Blood Draw")
    print(activity.to_dict())  # All required fields automatically included
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

# Import all official USDM types from schema-generated module
from core.usdm_types_generated import (
    # Core types
    Code,
    AliasCode,
    CommentAnnotation,
    Range,
    Quantity,
    Duration,
    
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
    Abbreviation,
    NarrativeContent,
    StudyAmendment,
    
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
    
    # Scheduling
    Condition,
    TransitionRule,
    
    # Helpers
    generate_uuid,
    create_wrapper_input,
    USDMEntity,
)


# =============================================================================
# Internal Extraction Types
# =============================================================================
# These types are used ONLY during the extraction pipeline and are NOT official
# USDM entities. They serve as intermediate containers before conversion.

@dataclass
class PlannedTimepoint:
    """
    Internal extraction type - represents a column in the SoA table.
    Maps to Encounter + Timing in USDM 4.0.
    """
    id: str = ""
    visit: str = ""
    epoch: str = ""
    epochId: str = ""
    day: str = ""
    window: Optional[str] = None
    encounterId: str = ""
    valueLabel: str = ""  # Alias for visit
    
    @property
    def name(self) -> str:
        """Alias for visit - for backward compatibility."""
        return self.visit or self.valueLabel
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id or generate_uuid(),
            "visit": self.visit,
            "epoch": self.epoch,
            "epochId": self.epochId,
            "day": self.day,
            "window": self.window,
            "encounterId": self.encounterId,
            "instanceType": "Timing",
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'PlannedTimepoint':
        if not data:
            return cls()
        return cls(
            id=data.get('id', ''),
            visit=data.get('visit', data.get('valueLabel', data.get('name', ''))),
            epoch=data.get('epoch', ''),
            epochId=data.get('epochId', ''),
            day=data.get('day', data.get('value', '')),
            window=data.get('window'),
            encounterId=data.get('encounterId', ''),
        )
    
    def to_timing(self) -> Timing:
        """Convert to official USDM Timing."""
        return Timing(id=self.id or generate_uuid(), value=self.day, valueLabel=self.visit)


@dataclass
class ActivityTimepoint:
    """
    Internal extraction type - represents a tick in the SoA matrix.
    Maps to ScheduledActivityInstance in USDM 4.0.
    
    Uses encounterId (enc_N) as the primary timepoint reference.
    plannedTimepointId (pt_N) is kept for backward compatibility only.
    
    footnoteRefs: List of footnote identifiers (e.g., ["a", "m"]) for ticks
    that have superscript references like "X^a" or "✓^m,n"
    """
    activity_id: str = ""
    timepoint_id: str = ""  # Deprecated - use encounterId
    is_performed: bool = True
    condition: Optional[str] = None
    activityId: str = ""  # Alternative field name
    encounterId: str = ""  # Primary: enc_N from header structure
    plannedTimepointId: str = ""  # Legacy: pt_N (backward compat)
    footnoteRefs: List[str] = field(default_factory=list)  # Footnote superscripts (e.g., ["a", "m"])
    
    def __post_init__(self):
        if not self.activity_id and self.activityId:
            self.activity_id = self.activityId
        # Prioritize encounterId over plannedTimepointId
        if not self.timepoint_id:
            self.timepoint_id = self.encounterId or self.plannedTimepointId
    
    def to_dict(self) -> Dict[str, Any]:
        # Use encounterId as the canonical ID
        enc_id = self.encounterId or self.timepoint_id or self.plannedTimepointId
        result = {
            "activityId": self.activity_id or self.activityId,
            "encounterId": enc_id,
            "instanceType": "ScheduledActivityInstance",
        }
        # Include footnoteRefs if present (for provenance/viewer, not USDM output)
        if self.footnoteRefs:
            result["footnoteRefs"] = self.footnoteRefs
        return result
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ActivityTimepoint':
        if not data:
            return cls()
        # Prioritize encounterId over plannedTimepointId
        enc_id = data.get('encounterId', data.get('plannedTimepointId', data.get('timepoint_id', '')))
        return cls(
            activity_id=data.get('activity_id', data.get('activityId', '')),
            encounterId=enc_id,
            timepoint_id=enc_id,
            is_performed=data.get('is_performed', data.get('isPerformed', True)),
            condition=data.get('condition'),
            footnoteRefs=data.get('footnoteRefs', data.get('footnote_refs', [])),
        )
    
    def to_scheduled_instance(self) -> ScheduledActivityInstance:
        """Convert to official USDM ScheduledActivityInstance."""
        act_id = self.activity_id or self.activityId
        enc_id = self.encounterId or self.timepoint_id or self.plannedTimepointId
        return ScheduledActivityInstance(
            id=generate_uuid(),
            activityIds=[act_id] if act_id else [],  # USDM 4.0 uses activityIds (plural)
            encounterId=enc_id,
        )


@dataclass
class ActivityGroup:
    """
    Internal extraction type - represents a row section header in SoA.
    Maps to Activity with childIds in USDM 4.0.
    """
    id: str = ""
    name: str = ""
    description: Optional[str] = None
    activity_ids: List[str] = field(default_factory=list)  # Activity IDs (populated during post-processing)
    activity_names: List[str] = field(default_factory=list)  # Activity names from header analyzer (for matching)
    is_bold: bool = False
    is_merged: bool = False
    row_index: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id or generate_uuid(),
            "name": self.name,
            "description": self.description,
            "childIds": self.activity_ids,
            "instanceType": "Activity",
        }
        # Include activity_names if present (for text extraction prompt)
        if self.activity_names:
            result["activityNames"] = self.activity_names
        return result
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ActivityGroup':
        if not data:
            return cls()
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            description=data.get('description'),
            activity_ids=data.get('activity_ids', data.get('childIds', [])),
            activity_names=data.get('activityNames', data.get('activity_names', [])),  # From header analyzer
            is_bold=data.get('is_bold', data.get('isBold', False)),
            is_merged=data.get('is_merged', data.get('isMerged', data.get('hasMergedCells', False))),
            row_index=data.get('row_index', data.get('rowIndex')),
        )
    
    def to_activity(self) -> Activity:
        """Convert to official USDM Activity with childIds."""
        return Activity(id=self.id or generate_uuid(), name=self.name, 
                       description=self.description, childIds=self.activity_ids)


@dataclass
class HeaderStructure:
    """
    Internal extraction type - container for SoA table structure from vision analysis.
    Used as an anchor for text extraction to ensure consistent IDs.
    """
    epochs: List[StudyEpoch] = field(default_factory=list)
    encounters: List[Encounter] = field(default_factory=list)
    plannedTimepoints: List[PlannedTimepoint] = field(default_factory=list)
    activityGroups: List[ActivityGroup] = field(default_factory=list)
    footnotes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'columnHierarchy': {
                'epochs': [e.to_dict() for e in self.epochs],
                'encounters': [e.to_dict() for e in self.encounters],
                'plannedTimepoints': [pt.to_dict() for pt in self.plannedTimepoints],
            },
            'rowGroups': [g.to_dict() for g in self.activityGroups],
            'footnotes': self.footnotes,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'HeaderStructure':
        if not data:
            return cls()
        col_h = data.get('columnHierarchy', {})
        
        # Parse epochs
        epochs = []
        for e in col_h.get('epochs', []):
            epochs.append(StudyEpoch(
                id=e.get('id', generate_uuid()),
                name=e.get('name', ''),
                description=e.get('description'),
            ))
        
        # Parse encounters
        encounters = []
        for e in col_h.get('encounters', []):
            encounters.append(Encounter(
                id=e.get('id', generate_uuid()),
                name=e.get('name', ''),
                epochId=e.get('epochId'),
            ))
        
        return cls(
            epochs=epochs,
            encounters=encounters,
            plannedTimepoints=[PlannedTimepoint.from_dict(pt) for pt in col_h.get('plannedTimepoints', [])],
            activityGroups=[ActivityGroup.from_dict(g) for g in data.get('rowGroups', [])],
            footnotes=data.get('footnotes', []),
        )
    
    def get_timepoint_ids(self) -> List[str]:
        return [pt.id for pt in self.plannedTimepoints]
    
    def get_encounter_ids(self) -> List[str]:
        return [enc.id for enc in self.encounters]
    
    def get_group_ids(self) -> List[str]:
        return [g.id for g in self.activityGroups]


@dataclass
class Timeline:
    """
    Internal extraction type - container for SoA data during extraction.
    Convert to StudyDesign via to_study_design() for USDM compliance.
    """
    activities: List[Activity] = field(default_factory=list)
    plannedTimepoints: List[PlannedTimepoint] = field(default_factory=list)
    encounters: List[Encounter] = field(default_factory=list)
    epochs: List[StudyEpoch] = field(default_factory=list)
    activityGroups: List[ActivityGroup] = field(default_factory=list)
    activityTimepoints: List[ActivityTimepoint] = field(default_factory=list)
    footnotes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'activities': [a.to_dict() for a in self.activities],
            'plannedTimepoints': [pt.to_dict() for pt in self.plannedTimepoints],
            'encounters': [e.to_dict() for e in self.encounters],
            'epochs': [e.to_dict() for e in self.epochs],
            'activityGroups': [g.to_dict() for g in self.activityGroups],
            'activityTimepoints': [at.to_dict() for at in self.activityTimepoints],
            'footnotes': self.footnotes,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Timeline':
        if not data:
            return cls()
        
        # Parse activities
        activities = []
        for a in data.get('activities', []):
            activities.append(Activity(
                id=a.get('id', generate_uuid()),
                name=a.get('name', ''),
                description=a.get('description'),
                label=a.get('label'),
            ))
        
        # Parse encounters
        encounters = []
        for e in data.get('encounters', []):
            encounters.append(Encounter(
                id=e.get('id', generate_uuid()),
                name=e.get('name', ''),
                epochId=e.get('epochId'),
            ))
        
        # Parse epochs
        epochs = []
        for e in data.get('epochs', []):
            epochs.append(StudyEpoch(
                id=e.get('id', generate_uuid()),
                name=e.get('name', ''),
                description=e.get('description'),
            ))
        
        return cls(
            activities=activities,
            plannedTimepoints=[PlannedTimepoint.from_dict(pt) for pt in data.get('plannedTimepoints', [])],
            encounters=encounters,
            epochs=epochs,
            activityGroups=[ActivityGroup.from_dict(g) for g in data.get('activityGroups', [])],
            activityTimepoints=[ActivityTimepoint.from_dict(at) for at in data.get('activityTimepoints', [])],
            footnotes=data.get('footnotes', []),
        )
    
    def to_study_design(self, design_id: str = "sd_1") -> StudyDesign:
        """Convert Timeline to proper USDM StudyDesign."""
        all_activities = []
        
        # Convert activity groups to parent Activities with childIds
        if self.activityGroups:
            for group in self.activityGroups:
                # 1. Check if ActivityGroup already has activity_ids (from post-processing)
                child_ids = getattr(group, 'activity_ids', []) or []
                
                # 2. Fallback: match by activityGroupId on activities
                if not child_ids:
                    for act in self.activities:
                        act_dict = act.to_dict() if hasattr(act, 'to_dict') else act
                        if act_dict.get('activityGroupId') == group.id:
                            child_ids.append(act.id)
                
                # 3. Fallback: match by activity_names from header analyzer (fuzzy name matching)
                if not child_ids:
                    activity_names = getattr(group, 'activity_names', []) or []
                    if activity_names:
                        activity_names_lower = [n.lower().strip() for n in activity_names]
                        for act in self.activities:
                            act_name = (act.name if hasattr(act, 'name') else act.get('name', '')).lower().strip()
                            if act_name in activity_names_lower:
                                child_ids.append(act.id if hasattr(act, 'id') else act.get('id'))
                
                # Only add parent activity if it has children
                if child_ids:
                    parent_activity = Activity(
                        id=group.id,
                        name=group.name,
                        description=group.description,
                        childIds=child_ids,
                    )
                    all_activities.append(parent_activity)
        
        all_activities.extend(self.activities)
        
        # Convert footnotes to CommentAnnotations
        soa_notes = [
            CommentAnnotation(id=f"soa_fn_{i+1}", text=fn)
            for i, fn in enumerate(self.footnotes)
        ]
        
        # Create ScheduledActivityInstances
        # Note: Extraction now uses enc_N directly, but we keep pt_N -> enc_N
        # mapping as backward compatibility for any legacy data
        import re
        pt_to_enc = {}
        for enc in self.encounters:
            enc_id = enc.id if hasattr(enc, 'id') else enc.get('id', '')
            match = re.match(r'^enc_(\d+)$', enc_id)
            if match:
                n = match.group(1)
                pt_to_enc[f"pt_{n}"] = enc_id
        
        instances = []
        for at in self.activityTimepoints:
            inst = at.to_scheduled_instance()
            # Backward compat: Map pt_* to enc_* if needed (legacy data)
            if inst.encounterId and inst.encounterId in pt_to_enc:
                inst.encounterId = pt_to_enc[inst.encounterId]
            instances.append(inst)
        
        return StudyDesign(
            id=design_id,
            activities=all_activities,
            encounters=self.encounters,
            epochs=self.epochs,
            scheduleTimelines=[
                ScheduleTimeline(
                    id="timeline_1",
                    name="Main Schedule Timeline",
                    mainTimeline=True,
                    instances=instances,
                )
            ],
            notes=soa_notes,
        )


# =============================================================================
# Enums and Constants
# =============================================================================

class EntityType(Enum):
    """USDM entity instance types."""
    ACTIVITY = "Activity"
    SCHEDULED_ACTIVITY_INSTANCE = "ScheduledActivityInstance"
    ENCOUNTER = "Encounter"
    STUDY_EPOCH = "StudyEpoch"
    SCHEDULE_TIMELINE = "ScheduleTimeline"
    TIMING = "Timing"
    # Deprecated names (backward compatibility)
    PLANNED_TIMEPOINT = "Timing"
    EPOCH = "StudyEpoch"
    ACTIVITY_GROUP = "Activity"
    ACTIVITY_TIMEPOINT = "ScheduledActivityInstance"


# Flag indicating we're using schema-generated types
USING_GENERATED_TYPES = True


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Core types
    'Code', 'AliasCode', 'CommentAnnotation', 'Range', 'Quantity', 'Duration',
    # Study structure
    'Study', 'StudyVersion', 'StudyDesign', 'StudyArm', 'StudyCell', 'StudyCohort',
    # Metadata
    'StudyTitle', 'StudyIdentifier', 'Organization', 'Indication',
    'Abbreviation', 'NarrativeContent', 'StudyAmendment',
    # SoA entities
    'Activity', 'Encounter', 'StudyEpoch', 'Epoch', 'ScheduleTimeline',
    'ScheduledActivityInstance', 'ScheduleTimelineExit', 'Timing',
    # Eligibility
    'EligibilityCriterion', 'EligibilityCriterionItem', 'StudyDesignPopulation',
    # Objectives
    'Objective', 'Endpoint', 'Estimand', 'IntercurrentEvent',
    # Interventions
    'StudyIntervention', 'AdministrableProduct', 'Administration', 'Procedure',
    # Scheduling
    'Condition', 'TransitionRule',
    # Internal extraction types (not official USDM)
    'PlannedTimepoint', 'ActivityTimepoint', 'ActivityGroup',
    'HeaderStructure', 'Timeline',
    # Helpers
    'generate_uuid', 'create_wrapper_input', 'USDMEntity',
    # Enums
    'EntityType',
    # Flags
    'USING_GENERATED_TYPES',
]
