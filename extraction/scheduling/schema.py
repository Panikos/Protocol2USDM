"""
Scheduling Extraction Schema - Internal types for extraction pipeline.

These types are used during extraction and convert to official USDM types
(from core.usdm_types) when generating final output.

For official USDM types, see: core/usdm_types.py
Schema source: https://github.com/cdisc-org/DDF-RA/blob/main/Deliverables/UML/dataStructure.yml
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

from core.usdm_types import generate_uuid, Code


class TimingType(Enum):
    """Types of timing constraints."""
    BEFORE = "Before"
    AFTER = "After"
    WITHIN = "Within"
    AT = "At"
    BETWEEN = "Between"


class TimingRelativeToFrom(Enum):
    """What timing is relative to."""
    STUDY_START = "Study Start"
    RANDOMIZATION = "Randomization"
    FIRST_DOSE = "First Dose"
    LAST_DOSE = "Last Dose"
    PREVIOUS_VISIT = "Previous Visit"
    SCREENING = "Screening"
    BASELINE = "Baseline"
    END_OF_TREATMENT = "End of Treatment"


class ConditionOperator(Enum):
    """Operators for condition evaluation."""
    EQUALS = "Equals"
    NOT_EQUALS = "Not Equals"
    GREATER_THAN = "Greater Than"
    LESS_THAN = "Less Than"
    CONTAINS = "Contains"
    IN = "In"
    AND = "And"
    OR = "Or"


class TransitionType(Enum):
    """Types of study transitions."""
    EPOCH_TRANSITION = "Epoch Transition"
    ARM_TRANSITION = "Arm Transition"
    DISCONTINUATION = "Discontinuation"
    EARLY_TERMINATION = "Early Termination"
    RESCUE_THERAPY = "Rescue Therapy"
    DOSE_MODIFICATION = "Dose Modification"


@dataclass
class Timing:
    """
    USDM Timing entity.
    Represents timing constraints for visits/activities.
    """
    id: str
    name: str
    timing_type: TimingType
    value: Optional[float] = None
    value_min: Optional[float] = None
    value_max: Optional[float] = None
    unit: str = "days"
    relative_to: Optional[TimingRelativeToFrom] = None
    relative_to_timepoint_id: Optional[str] = None
    window_lower: Optional[float] = None  # e.g., -3 days
    window_upper: Optional[float] = None  # e.g., +3 days
    instance_type: str = "Timing"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "type": self.timing_type.value,
            "unit": self.unit,
            "instanceType": self.instance_type,
        }
        if self.value is not None:
            result["value"] = self.value
        if self.value_min is not None:
            result["valueMin"] = self.value_min
        if self.value_max is not None:
            result["valueMax"] = self.value_max
        if self.relative_to:
            result["relativeTo"] = self.relative_to.value
        if self.relative_to_timepoint_id:
            result["relativeToTimepointId"] = self.relative_to_timepoint_id
        if self.window_lower is not None:
            result["windowLower"] = self.window_lower
        if self.window_upper is not None:
            result["windowUpper"] = self.window_upper
        return result


@dataclass
class Condition:
    """
    USDM Condition entity.
    Represents conditional logic for branching protocols.
    """
    id: str
    name: str
    description: Optional[str] = None
    text: Optional[str] = None  # Human-readable condition
    context_ids: List[str] = field(default_factory=list)
    applies_to_ids: List[str] = field(default_factory=list)
    instance_type: str = "Condition"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "instanceType": self.instance_type,
        }
        if self.description:
            result["description"] = self.description
        if self.text:
            result["text"] = self.text
        if self.context_ids:
            result["contextIds"] = self.context_ids
        if self.applies_to_ids:
            result["appliesToIds"] = self.applies_to_ids
        return result


@dataclass
class ConditionAssignment:
    """
    USDM ConditionAssignment entity.
    Links conditions to study arms or elements.
    """
    id: str
    condition_id: str
    assigned_to_id: str  # Arm, Cell, or Element ID
    instance_type: str = "ConditionAssignment"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "conditionId": self.condition_id,
            "assignedToId": self.assigned_to_id,
            "instanceType": self.instance_type,
        }


@dataclass
class TransitionRule:
    """
    USDM TransitionRule entity.
    Defines rules for transitioning between study states.
    """
    id: str
    name: str
    description: Optional[str] = None
    transition_type: Optional[TransitionType] = None
    from_element_id: Optional[str] = None
    to_element_id: Optional[str] = None
    condition_id: Optional[str] = None
    text: Optional[str] = None  # Human-readable rule
    instance_type: str = "TransitionRule"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "instanceType": self.instance_type,
        }
        if self.description:
            result["description"] = self.description
        if self.transition_type:
            result["transitionType"] = self.transition_type.value
        if self.from_element_id:
            result["fromElementId"] = self.from_element_id
        if self.to_element_id:
            result["toElementId"] = self.to_element_id
        if self.condition_id:
            result["conditionId"] = self.condition_id
        if self.text:
            result["text"] = self.text
        return result


@dataclass
class ScheduleTimelineExit:
    """
    USDM ScheduleTimelineExit entity.
    Defines criteria for exiting the study timeline.
    """
    id: str
    name: str
    description: Optional[str] = None
    exit_type: str = "Early Termination"  # Early Termination, Completion, etc.
    condition_id: Optional[str] = None
    instance_type: str = "ScheduleTimelineExit"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "exitType": self.exit_type,
            "instanceType": self.instance_type,
        }
        if self.description:
            result["description"] = self.description
        if self.condition_id:
            result["conditionId"] = self.condition_id
        return result


@dataclass
class ScheduledDecisionInstance:
    """
    USDM ScheduledDecisionInstance entity.
    Represents a decision point in the schedule timeline.
    """
    id: str
    name: str
    timepoint_id: str
    description: Optional[str] = None
    condition_ids: List[str] = field(default_factory=list)
    default_transition_id: Optional[str] = None
    instance_type: str = "ScheduledDecisionInstance"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "timepointId": self.timepoint_id,
            "instanceType": self.instance_type,
        }
        if self.description:
            result["description"] = self.description
        if self.condition_ids:
            result["conditionIds"] = self.condition_ids
        if self.default_transition_id:
            result["defaultTransitionId"] = self.default_transition_id
        return result


@dataclass
class SchedulingData:
    """Container for scheduling logic extraction results."""
    timings: List[Timing] = field(default_factory=list)
    conditions: List[Condition] = field(default_factory=list)
    condition_assignments: List[ConditionAssignment] = field(default_factory=list)
    transition_rules: List[TransitionRule] = field(default_factory=list)
    schedule_exits: List[ScheduleTimelineExit] = field(default_factory=list)
    decision_instances: List[ScheduledDecisionInstance] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timings": [t.to_dict() for t in self.timings],
            "conditions": [c.to_dict() for c in self.conditions],
            "conditionAssignments": [c.to_dict() for c in self.condition_assignments],
            "transitionRules": [t.to_dict() for t in self.transition_rules],
            "scheduleTimelineExits": [e.to_dict() for e in self.schedule_exits],
            "scheduledDecisionInstances": [d.to_dict() for d in self.decision_instances],
            "summary": {
                "timingCount": len(self.timings),
                "conditionCount": len(self.conditions),
                "transitionRuleCount": len(self.transition_rules),
                "exitCount": len(self.schedule_exits),
            }
        }


@dataclass
class SchedulingResult:
    """Result container for scheduling logic extraction."""
    success: bool
    data: Optional[SchedulingData] = None
    error: Optional[str] = None
    pages_used: List[int] = field(default_factory=list)
    model_used: Optional[str] = None
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "success": self.success,
            "pagesUsed": self.pages_used,
            "modelUsed": self.model_used,
            "confidence": self.confidence,
        }
        if self.data:
            result["scheduling"] = self.data.to_dict()
        if self.error:
            result["error"] = self.error
        return result
