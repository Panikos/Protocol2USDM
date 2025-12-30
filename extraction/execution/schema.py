"""
Execution Model Schema Definitions

Defines dataclasses for execution-level semantics that complement
core USDM types. These are used via extensionAttributes to maintain
USDM compliance while adding execution capabilities.

Per USDM v4.0, extensionAttributes is available on all entities
for custom metadata that doesn't fit core schema.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


class AnchorType(Enum):
    """Types of time anchors."""
    FIRST_DOSE = "FirstDose"
    TREATMENT_START = "TreatmentStart"
    RANDOMIZATION = "Randomization"
    SCREENING = "Screening"
    DAY_1 = "Day1"
    BASELINE = "Baseline"
    ENROLLMENT = "Enrollment"
    INFORMED_CONSENT = "InformedConsent"
    CYCLE_START = "CycleStart"
    COLLECTION_DAY = "CollectionDay"  # FIX 4: 24-hour collection boundary anchor
    CUSTOM = "Custom"


class RepetitionType(Enum):
    """Types of repetition patterns."""
    DAILY = "Daily"
    INTERVAL = "Interval"
    CYCLE = "Cycle"
    CONTINUOUS = "Continuous"
    ON_DEMAND = "OnDemand"


class ExecutionType(Enum):
    """Execution semantics for activities."""
    WINDOW = "Window"      # Continuous collection over time period
    EPISODE = "Episode"    # Ordered conditional workflow
    SINGLE = "Single"      # One-time event
    RECURRING = "Recurring"  # Scheduled repeats


class EndpointType(Enum):
    """Types of study endpoints."""
    PRIMARY = "Primary"
    SECONDARY = "Secondary"
    EXPLORATORY = "Exploratory"
    SAFETY = "Safety"


class VariableType(Enum):
    """Types of derived variables."""
    BASELINE = "Baseline"
    CHANGE_FROM_BASELINE = "ChangeFromBaseline"
    PERCENT_CHANGE = "PercentChange"
    TIME_TO_EVENT = "TimeToEvent"
    CATEGORICAL = "Categorical"
    COMPOSITE = "Composite"
    CUSTOM = "Custom"


class StateType(Enum):
    """Types of subject states in state machine."""
    SCREENING = "Screening"
    ENROLLED = "Enrolled"
    RANDOMIZED = "Randomized"
    ON_TREATMENT = "OnTreatment"
    COMPLETED = "Completed"
    DISCONTINUED = "Discontinued"
    FOLLOW_UP = "FollowUp"
    LOST_TO_FOLLOW_UP = "LostToFollowUp"
    WITHDRAWN = "Withdrawn"
    DEATH = "Death"


@dataclass
class TimeAnchor:
    """
    Canonical time anchor for a timeline.
    
    Every main timeline requires an anchor point from which
    all other timing is measured (per USDM workshop manual).
    
    Attributes:
        id: Unique identifier
        definition: Human-readable definition (e.g., "First administration of study drug")
        anchor_type: Categorized anchor type
        timeline_id: Timeline this anchor applies to (None = study-wide)
        day_value: Numeric day value (e.g., 1 for Day 1)
        source_text: Original text from protocol
    """
    id: str
    definition: str
    anchor_type: AnchorType = AnchorType.DAY_1
    timeline_id: Optional[str] = None
    day_value: int = 1
    source_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "definition": self.definition,
            "anchorType": self.anchor_type.value,
            "timelineId": self.timeline_id,
            "dayValue": self.day_value,
            "sourceText": self.source_text,
        }
    
    def to_extension(self) -> Dict[str, Any]:
        """Convert to USDM extensionAttributes format."""
        return {
            "x-executionModel": {
                "timeAnchor": self.to_dict()
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TimeAnchor':
        return cls(
            id=data.get('id', ''),
            definition=data.get('definition', ''),
            anchor_type=AnchorType(data.get('anchorType', 'Day1')),
            timeline_id=data.get('timelineId'),
            day_value=data.get('dayValue', 1),
            source_text=data.get('sourceText'),
        )


@dataclass
class Repetition:
    """
    Repetition pattern for an activity or collection.
    
    Captures cycles, daily collections, interval sampling, etc.
    
    Attributes:
        id: Unique identifier
        type: Type of repetition (DAILY, INTERVAL, CYCLE, etc.)
        activity_id: Activity this applies to
        start_offset: ISO 8601 duration from anchor to start
        end_offset: ISO 8601 duration from anchor to end
        interval: ISO 8601 duration between repeats (e.g., "PT5M" for 5 minutes)
        count: Number of repetitions (None = until end_offset)
        min_observations: Minimum required observations in window
        cycle_length: For CYCLE type, duration of one cycle
        exit_condition: Condition text for exiting cycle
    """
    id: str
    type: RepetitionType
    activity_id: Optional[str] = None
    start_offset: Optional[str] = None
    end_offset: Optional[str] = None
    interval: Optional[str] = None
    count: Optional[int] = None
    min_observations: Optional[int] = None
    cycle_length: Optional[str] = None
    exit_condition: Optional[str] = None
    source_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "type": self.type.value,
        }
        if self.activity_id:
            result["activityId"] = self.activity_id
        if self.start_offset:
            result["startOffset"] = self.start_offset
        if self.end_offset:
            result["endOffset"] = self.end_offset
        if self.interval:
            result["interval"] = self.interval
        if self.count is not None:
            result["count"] = self.count
        if self.min_observations is not None:
            result["minObservations"] = self.min_observations
        if self.cycle_length:
            result["cycleLength"] = self.cycle_length
        if self.exit_condition:
            result["exitCondition"] = self.exit_condition
        if self.source_text:
            result["sourceText"] = self.source_text
        return result
    
    def to_extension(self) -> Dict[str, Any]:
        """Convert to USDM extensionAttributes format."""
        return {
            "x-executionModel": {
                "repetition": self.to_dict()
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Repetition':
        return cls(
            id=data.get('id', ''),
            type=RepetitionType(data.get('type', 'Daily')),
            activity_id=data.get('activityId'),
            start_offset=data.get('startOffset'),
            end_offset=data.get('endOffset'),
            interval=data.get('interval'),
            count=data.get('count'),
            min_observations=data.get('minObservations'),
            cycle_length=data.get('cycleLength'),
            exit_condition=data.get('exitCondition'),
            source_text=data.get('sourceText'),
        )


@dataclass
class SamplingConstraint:
    """
    Minimum sampling density requirement for an activity.
    
    Ensures synthetic data generators produce sufficient observations.
    
    Attributes:
        id: Unique identifier
        activity_id: Activity this applies to
        min_per_window: Minimum observations required per window
        window_duration: ISO 8601 duration of the window
        timepoints: Specific timepoints if prescribed (e.g., ["0", "5", "10", "15", "30"])
        domain: Data domain (e.g., "PK", "PD", "LB")
        anchor_id: Reference to time anchor for this constraint
        window_start: ISO 8601 offset from anchor for window start
        window_end: ISO 8601 offset from anchor for window end
        rationale: Why this constraint exists (e.g., linked to endpoint)
    """
    id: str
    activity_id: str
    min_per_window: int
    window_duration: Optional[str] = None
    timepoints: List[str] = field(default_factory=list)
    domain: Optional[str] = None
    anchor_id: Optional[str] = None
    window_start: Optional[str] = None
    window_end: Optional[str] = None
    rationale: Optional[str] = None
    source_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "activityId": self.activity_id,
            "minPerWindow": self.min_per_window,
        }
        if self.window_duration:
            result["windowDuration"] = self.window_duration
        if self.timepoints:
            result["timepoints"] = self.timepoints
        if self.domain:
            result["domain"] = self.domain
        if self.anchor_id:
            result["anchorId"] = self.anchor_id
        if self.window_start:
            result["windowStart"] = self.window_start
        if self.window_end:
            result["windowEnd"] = self.window_end
        if self.rationale:
            result["rationale"] = self.rationale
        if self.source_text:
            result["sourceText"] = self.source_text
        return result


@dataclass
class AnalysisWindow:
    """
    Defines a computable analysis window for endpoint derivation.
    
    FIX 3: Addresses the need for explicit baseline/accumulation/steady-state phases
    that can be referenced by endpoints for deterministic derivation.
    
    Attributes:
        id: Unique identifier
        window_type: Type of window (baseline, accumulation, steady_state, treatment)
        name: Human-readable name
        start_day: Start day relative to anchor (can be negative for baseline)
        end_day: End day relative to anchor
        anchor_id: Reference to time anchor
        linked_endpoint_ids: Endpoints that use this window
        description: Additional context
    """
    id: str
    window_type: str  # baseline, accumulation, steady_state, treatment, follow_up
    name: str
    start_day: int
    end_day: int
    anchor_id: Optional[str] = None
    linked_endpoint_ids: List[str] = field(default_factory=list)
    description: Optional[str] = None
    source_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "windowType": self.window_type,
            "name": self.name,
            "startDay": self.start_day,
            "endDay": self.end_day,
        }
        if self.anchor_id:
            result["anchorId"] = self.anchor_id
        if self.linked_endpoint_ids:
            result["linkedEndpointIds"] = self.linked_endpoint_ids
        if self.description:
            result["description"] = self.description
        if self.source_text:
            result["sourceText"] = self.source_text
        return result


# =============================================================================
# FIX A: DOSE TITRATION SCHEDULE - Day-bounded dose levels with transition rules
# =============================================================================

@dataclass
class TitrationDoseLevel:
    """
    A single dose level within a titration schedule.
    
    Attributes:
        dose_value: Dose amount (e.g., "15 mg")
        start_day: First day this dose applies
        end_day: Last day this dose applies (None = ongoing)
        requires_prior_dose: Previous dose level required before this one
        transition_rule: Rule for transitioning to this dose
    """
    dose_value: str
    start_day: int
    end_day: Optional[int] = None
    requires_prior_dose: Optional[str] = None
    transition_rule: Optional[str] = None
    source_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "doseValue": self.dose_value,
            "startDay": self.start_day,
        }
        if self.end_day is not None:
            result["endDay"] = self.end_day
        if self.requires_prior_dose:
            result["requiresPriorDose"] = self.requires_prior_dose
        if self.transition_rule:
            result["transitionRule"] = self.transition_rule
        if self.source_text:
            result["sourceText"] = self.source_text
        return result


@dataclass
class DoseTitrationSchedule:
    """
    FIX A: Operationalized titration schedule with explicit day bounds.
    
    Addresses feedback: "Dose titration is described, but not operationalized"
    by providing machine-enforceable dose transitions.
    
    Attributes:
        id: Unique identifier
        intervention_id: Reference to the intervention being titrated
        dose_levels: Ordered list of dose levels with day bounds
        titration_type: Type of titration (escalation, de-escalation, adaptive)
        anchor_id: Reference to time anchor (e.g., first dose)
    """
    id: str
    intervention_id: Optional[str] = None
    intervention_name: Optional[str] = None
    dose_levels: List[TitrationDoseLevel] = field(default_factory=list)
    titration_type: str = "escalation"  # escalation, de-escalation, adaptive
    anchor_id: Optional[str] = None
    source_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "titrationType": self.titration_type,
            "doseLevels": [d.to_dict() for d in self.dose_levels],
        }
        if self.intervention_id:
            result["interventionId"] = self.intervention_id
        if self.intervention_name:
            result["interventionName"] = self.intervention_name
        if self.anchor_id:
            result["anchorId"] = self.anchor_id
        if self.source_text:
            result["sourceText"] = self.source_text
        return result


# =============================================================================
# FIX B: INSTANCE BINDING - Bind repetitions/anchors to ScheduledActivityInstance
# =============================================================================

@dataclass
class InstanceBinding:
    """
    FIX B: Binds execution rules to specific ScheduledActivityInstance.
    
    Addresses feedback: "You created repetition rules, but didn't bind them to
    scheduled instances" - this is the highest ROI fix for realism.
    
    Attributes:
        id: Unique identifier
        instance_id: Reference to ScheduledActivityInstance.id
        activity_id: Reference to the activity
        repetition_id: Which repetition rule applies
        time_anchor_id: Which time anchor this instance uses
        start_offset: ISO 8601 offset from anchor to start
        end_offset: ISO 8601 offset from anchor to end
        expected_count: Expected number of occurrences in this binding
        collection_boundary: For 24h collections, defines the boundary type
    """
    id: str
    instance_id: str
    activity_id: Optional[str] = None
    activity_name: Optional[str] = None
    repetition_id: Optional[str] = None
    time_anchor_id: Optional[str] = None
    start_offset: Optional[str] = None  # ISO 8601 duration
    end_offset: Optional[str] = None    # ISO 8601 duration
    expected_count: Optional[int] = None
    collection_boundary: Optional[str] = None  # "morning-to-morning", "midnight-to-midnight"
    encounter_id: Optional[str] = None
    source_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "instanceId": self.instance_id,
        }
        if self.activity_id:
            result["activityId"] = self.activity_id
        if self.activity_name:
            result["activityName"] = self.activity_name
        if self.repetition_id:
            result["repetitionId"] = self.repetition_id
        if self.time_anchor_id:
            result["timeAnchorId"] = self.time_anchor_id
        if self.start_offset:
            result["startOffset"] = self.start_offset
        if self.end_offset:
            result["endOffset"] = self.end_offset
        if self.expected_count is not None:
            result["expectedCount"] = self.expected_count
        if self.collection_boundary:
            result["collectionBoundary"] = self.collection_boundary
        if self.encounter_id:
            result["encounterId"] = self.encounter_id
        if self.source_text:
            result["sourceText"] = self.source_text
        return result


@dataclass
class ActivityBinding:
    """
    Binds an activity to its execution timing rules.
    
    FIX C: This solves the "loose coupling" problem by explicitly linking
    activities to their time anchors, repetition patterns, and sampling constraints.
    
    Attributes:
        id: Unique identifier
        activity_id: The activity being bound
        activity_name: Human-readable activity name
        time_anchor_id: Reference to the time anchor for this activity
        repetition_id: Reference to the repetition pattern
        sampling_constraint_id: Reference to sampling constraint
        nominal_timepoints: Explicit list of timepoints (e.g., ["PT0M", "PT5M", "PT10M"])
        offset_from_anchor: ISO 8601 offset from anchor to first occurrence
    """
    id: str
    activity_id: str
    activity_name: Optional[str] = None
    time_anchor_id: Optional[str] = None
    repetition_id: Optional[str] = None
    sampling_constraint_id: Optional[str] = None
    nominal_timepoints: List[str] = field(default_factory=list)
    offset_from_anchor: Optional[str] = None
    expected_occurrences: Optional[int] = None  # FIX 2: Expected daily counts
    source_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "activityId": self.activity_id,
        }
        if self.activity_name:
            result["activityName"] = self.activity_name
        if self.time_anchor_id:
            result["timeAnchorId"] = self.time_anchor_id
        if self.repetition_id:
            result["repetitionId"] = self.repetition_id
        if self.sampling_constraint_id:
            result["samplingConstraintId"] = self.sampling_constraint_id
        if self.nominal_timepoints:
            result["nominalTimepoints"] = self.nominal_timepoints
        if self.offset_from_anchor:
            result["offsetFromAnchor"] = self.offset_from_anchor
        if self.expected_occurrences is not None:
            result["expectedOccurrences"] = self.expected_occurrences
        if self.source_text:
            result["sourceText"] = self.source_text
        return result


@dataclass
class TraversalConstraint:
    """
    Required subject path through study design.
    
    Ensures subjects complete required epochs/periods in order.
    
    Attributes:
        id: Unique identifier
        required_sequence: Ordered list of epoch/element IDs that must be traversed
        allow_early_exit: Whether early termination is permitted
        exit_epoch_ids: Epoch IDs where early exit is allowed
        mandatory_visits: Visit names that cannot be skipped
    """
    id: str
    required_sequence: List[str] = field(default_factory=list)
    allow_early_exit: bool = True
    exit_epoch_ids: List[str] = field(default_factory=list)
    mandatory_visits: List[str] = field(default_factory=list)
    source_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "requiredSequence": self.required_sequence,
            "allowEarlyExit": self.allow_early_exit,
            "exitEpochIds": self.exit_epoch_ids,
        }
        if self.mandatory_visits:
            result["mandatoryVisits"] = self.mandatory_visits
        if self.source_text:
            result["sourceText"] = self.source_text
        return result


@dataclass
class CrossoverDesign:
    """
    Crossover study design structure.
    
    Captures period sequencing, washout requirements, and treatment sequences.
    
    Attributes:
        id: Unique identifier
        is_crossover: Whether study uses crossover design
        num_periods: Number of treatment periods
        num_sequences: Number of treatment sequences
        periods: Ordered list of period names
        sequences: List of sequence definitions (e.g., ["AB", "BA"])
        washout_duration: ISO 8601 duration for washout period
        washout_required: Whether washout is mandatory between periods
        carryover_prevention: Description of carryover prevention measures
    """
    id: str
    is_crossover: bool = False
    num_periods: int = 1
    num_sequences: int = 1
    periods: List[str] = field(default_factory=list)
    sequences: List[str] = field(default_factory=list)
    washout_duration: Optional[str] = None
    washout_required: bool = False
    carryover_prevention: Optional[str] = None
    source_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "isCrossover": self.is_crossover,
            "numPeriods": self.num_periods,
            "numSequences": self.num_sequences,
        }
        if self.periods:
            result["periods"] = self.periods
        if self.sequences:
            result["sequences"] = self.sequences
        if self.washout_duration:
            result["washoutDuration"] = self.washout_duration
        result["washoutRequired"] = self.washout_required
        if self.carryover_prevention:
            result["carryoverPrevention"] = self.carryover_prevention
        if self.source_text:
            result["sourceText"] = self.source_text
        return result


@dataclass
class FootnoteCondition:
    """
    Structured condition extracted from SoA footnotes.
    
    Converts narrative footnote text into machine-readable conditions.
    
    Attributes:
        id: Unique identifier
        footnote_id: Reference to original footnote
        condition_type: Type of condition (timing, eligibility, procedure_variant, etc.)
        text: Original footnote text
        structured_condition: Machine-readable condition expression
        applies_to_activity_ids: Activities this condition applies to
        applies_to_timepoint_ids: Timepoints this condition applies to
        timing_constraint: Optional timing constraint (e.g., "30 minutes before labs")
    """
    id: str
    footnote_id: Optional[str] = None
    condition_type: str = "general"  # timing, eligibility, procedure_variant, frequency, sequence
    text: str = ""
    structured_condition: Optional[str] = None
    applies_to_activity_ids: List[str] = field(default_factory=list)
    applies_to_timepoint_ids: List[str] = field(default_factory=list)
    timing_constraint: Optional[str] = None
    source_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "conditionType": self.condition_type,
            "text": self.text,
        }
        if self.footnote_id:
            result["footnoteId"] = self.footnote_id
        if self.structured_condition:
            result["structuredCondition"] = self.structured_condition
        if self.applies_to_activity_ids:
            result["appliesToActivityIds"] = self.applies_to_activity_ids
        if self.applies_to_timepoint_ids:
            result["appliesToTimepointIds"] = self.applies_to_timepoint_ids
        if self.timing_constraint:
            result["timingConstraint"] = self.timing_constraint
        if self.source_text:
            result["sourceText"] = self.source_text
        return result


@dataclass
class EndpointAlgorithm:
    """
    Computational logic for an endpoint evaluation.
    
    Captures the algorithm needed to compute endpoint results,
    enabling deterministic evaluation from collected data.
    
    Attributes:
        id: Unique identifier
        name: Endpoint name (e.g., "Primary: Hypoglycemia Recovery")
        endpoint_type: PRIMARY, SECONDARY, EXPLORATORY, SAFETY
        inputs: Required input variables
        time_window: When measurement is taken
        algorithm: Computation logic expression
        success_criteria: Success/response definition
        source_text: Original protocol text
    """
    id: str
    name: str
    endpoint_type: EndpointType = EndpointType.PRIMARY
    inputs: List[str] = field(default_factory=list)
    time_window_reference: Optional[str] = None  # e.g., "glucagon administration"
    time_window_duration: Optional[str] = None   # ISO 8601 (e.g., "PT30M")
    algorithm: Optional[str] = None              # e.g., "PG >= 70 OR (PG - nadir) >= 20"
    success_criteria: Optional[str] = None       # e.g., "PG >= 70 mg/dL within 30 minutes"
    unit: Optional[str] = None                   # e.g., "mg/dL"
    comparator: Optional[str] = None             # e.g., "placebo", "baseline"
    source_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "endpointType": self.endpoint_type.value,
        }
        if self.inputs:
            result["inputs"] = self.inputs
        if self.time_window_reference:
            result["timeWindow"] = {
                "reference": self.time_window_reference,
                "duration": self.time_window_duration,
            }
        if self.algorithm:
            result["algorithm"] = self.algorithm
        if self.success_criteria:
            result["successCriteria"] = self.success_criteria
        if self.unit:
            result["unit"] = self.unit
        if self.comparator:
            result["comparator"] = self.comparator
        if self.source_text:
            result["sourceText"] = self.source_text[:200]
        return result


@dataclass
class DerivedVariable:
    """
    Definition of a derived/computed variable.
    
    Captures how to compute analysis variables from raw collected data.
    
    Attributes:
        id: Unique identifier
        name: Variable name (e.g., "Change from Baseline in HbA1c")
        variable_type: Type of derivation
        source_variables: Input variables required
        derivation_rule: How to compute the variable
        baseline_definition: When/how baseline is defined
        analysis_window: Time window for analysis
    """
    id: str
    name: str
    variable_type: VariableType = VariableType.CUSTOM
    source_variables: List[str] = field(default_factory=list)
    derivation_rule: Optional[str] = None        # e.g., "week12_value - baseline_value"
    baseline_definition: Optional[str] = None    # e.g., "Last non-missing value before Day 1"
    baseline_visit: Optional[str] = None         # e.g., "Day -1" or "Screening"
    analysis_window: Optional[str] = None        # e.g., "Week 12 ± 3 days"
    imputation_rule: Optional[str] = None        # e.g., "LOCF" or "MMRM"
    unit: Optional[str] = None
    source_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "variableType": self.variable_type.value,
        }
        if self.source_variables:
            result["sourceVariables"] = self.source_variables
        if self.derivation_rule:
            result["derivationRule"] = self.derivation_rule
        if self.baseline_definition:
            result["baselineDefinition"] = self.baseline_definition
        if self.baseline_visit:
            result["baselineVisit"] = self.baseline_visit
        if self.analysis_window:
            result["analysisWindow"] = self.analysis_window
        if self.imputation_rule:
            result["imputationRule"] = self.imputation_rule
        if self.unit:
            result["unit"] = self.unit
        if self.source_text:
            result["sourceText"] = self.source_text[:200]
        return result


@dataclass
class StateTransition:
    """
    A transition in the subject state machine.
    
    Defines how subjects move between states based on conditions/events.
    """
    from_state: StateType
    to_state: StateType
    trigger: str                              # Event/condition that triggers transition
    guard_condition: Optional[str] = None     # Additional condition required
    actions: List[str] = field(default_factory=list)  # Actions to perform
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "fromState": self.from_state.value,
            "toState": self.to_state.value,
            "trigger": self.trigger,
        }
        if self.guard_condition:
            result["guardCondition"] = self.guard_condition
        if self.actions:
            result["actions"] = self.actions
        return result


@dataclass
class SubjectStateMachine:
    """
    State machine describing valid subject paths through a study.
    
    Enables validation of subject journeys and generation of
    realistic disposition patterns.
    
    Attributes:
        id: Unique identifier
        initial_state: Starting state (usually SCREENING)
        terminal_states: Final states (COMPLETED, DISCONTINUED, etc.)
        states: All possible states
        transitions: Valid state transitions
    """
    id: str
    initial_state: StateType = StateType.SCREENING
    terminal_states: List[StateType] = field(default_factory=lambda: [
        StateType.COMPLETED, StateType.DISCONTINUED, 
        StateType.WITHDRAWN, StateType.DEATH
    ])
    states: List[StateType] = field(default_factory=list)
    transitions: List[StateTransition] = field(default_factory=list)
    source_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "initialState": self.initial_state.value,
            "terminalStates": [s.value for s in self.terminal_states],
            "states": [s.value for s in self.states],
            "transitions": [t.to_dict() for t in self.transitions],
        }
    
    def get_valid_transitions(self, current_state: StateType) -> List[StateTransition]:
        """Get all valid transitions from a given state."""
        return [t for t in self.transitions if t.from_state == current_state]
    
    def is_terminal(self, state: StateType) -> bool:
        """Check if a state is terminal."""
        return state in self.terminal_states


@dataclass
class ExecutionTypeAssignment:
    """
    Execution type classification for an activity.
    
    Attributes:
        activity_id: Activity being classified
        execution_type: WINDOW, EPISODE, SINGLE, or RECURRING
        rationale: Why this classification was made
    """
    activity_id: str
    execution_type: ExecutionType
    rationale: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "activityId": self.activity_id,
            "executionType": self.execution_type.value,
        }
        if self.rationale:
            result["rationale"] = self.rationale
        return result


# ============================================================================
# Phase 4 Components: Dosing, Visit Windows, Stratification
# ============================================================================

class DosingFrequency(Enum):
    """Dosing frequency patterns."""
    ONCE_DAILY = "QD"
    TWICE_DAILY = "BID"
    THREE_TIMES_DAILY = "TID"
    FOUR_TIMES_DAILY = "QID"
    EVERY_OTHER_DAY = "QOD"
    WEEKLY = "QW"
    EVERY_TWO_WEEKS = "Q2W"
    EVERY_THREE_WEEKS = "Q3W"
    EVERY_FOUR_WEEKS = "Q4W"
    MONTHLY = "QM"
    AS_NEEDED = "PRN"
    SINGLE_DOSE = "Single"
    CONTINUOUS = "Continuous"
    CUSTOM = "Custom"


class RouteOfAdministration(Enum):
    """Routes of drug administration."""
    ORAL = "Oral"
    INTRAVENOUS = "IV"
    SUBCUTANEOUS = "SC"
    INTRAMUSCULAR = "IM"
    TOPICAL = "Topical"
    INHALATION = "Inhalation"
    INTRANASAL = "Intranasal"
    TRANSDERMAL = "Transdermal"
    SUBLINGUAL = "Sublingual"
    RECTAL = "Rectal"
    OPHTHALMIC = "Ophthalmic"
    OTHER = "Other"


@dataclass
class DoseLevel:
    """A specific dose level in a regimen."""
    amount: float
    unit: str  # mg, mcg, mL, etc.
    description: Optional[str] = None  # e.g., "low dose", "high dose"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "amount": self.amount,
            "unit": self.unit,
        }
        if self.description:
            result["description"] = self.description
        return result


@dataclass
class DosingRegimen:
    """
    Dosing schedule and rules for a treatment arm.
    
    Captures dosing frequency, amounts, titration rules, and modifications
    needed to generate realistic treatment data.
    
    Attributes:
        id: Unique identifier
        treatment_name: Name of drug/intervention
        dose_levels: Available dose amounts
        frequency: Dosing frequency (QD, BID, etc.)
        route: Route of administration
        start_day: Day dosing begins (relative to Day 1)
        end_day: Day dosing ends (None = until end of study)
        titration_schedule: Dose escalation/reduction rules
        dose_modifications: Rules for dose adjustments
        max_dose: Maximum allowed dose
        min_dose: Minimum allowed dose
    """
    id: str
    treatment_name: str
    dose_levels: List[DoseLevel] = field(default_factory=list)
    frequency: DosingFrequency = DosingFrequency.ONCE_DAILY
    route: RouteOfAdministration = RouteOfAdministration.ORAL
    start_day: int = 1
    end_day: Optional[int] = None
    duration_description: Optional[str] = None  # e.g., "24 weeks"
    titration_schedule: Optional[str] = None  # e.g., "Increase by 10mg weekly"
    dose_modifications: List[str] = field(default_factory=list)
    max_dose: Optional[float] = None
    min_dose: Optional[float] = None
    source_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "treatmentName": self.treatment_name,
            "frequency": self.frequency.value,
            "route": self.route.value,
            "startDay": self.start_day,
        }
        if self.dose_levels:
            result["doseLevels"] = [d.to_dict() for d in self.dose_levels]
        if self.end_day:
            result["endDay"] = self.end_day
        if self.duration_description:
            result["durationDescription"] = self.duration_description
        if self.titration_schedule:
            result["titrationSchedule"] = self.titration_schedule
        if self.dose_modifications:
            result["doseModifications"] = self.dose_modifications
        if self.max_dose:
            result["maxDose"] = self.max_dose
        if self.min_dose:
            result["minDose"] = self.min_dose
        if self.source_text:
            result["sourceText"] = self.source_text[:200]
        return result


@dataclass
class VisitWindow:
    """
    Scheduled visit with allowed timing window.
    
    Defines when a visit should occur and acceptable deviations,
    critical for generating realistic visit timing data.
    
    Attributes:
        id: Unique identifier
        visit_name: Name of visit (e.g., "Week 4", "Day 15")
        visit_number: Sequential visit number
        target_day: Target study day for visit
        window_before: Days allowed before target (negative deviation)
        window_after: Days allowed after target (positive deviation)
        is_required: Whether visit is mandatory
        epoch: Study epoch this visit belongs to
        activities: Activities to perform at this visit
    """
    id: str
    visit_name: str
    visit_number: Optional[int] = None
    target_day: int = 1
    window_before: int = 0  # Days before target allowed
    window_after: int = 0   # Days after target allowed
    target_week: Optional[int] = None  # Alternative: week number
    is_required: bool = True
    epoch: Optional[str] = None
    activities: List[str] = field(default_factory=list)
    source_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "visitName": self.visit_name,
            "targetDay": self.target_day,
            "windowBefore": self.window_before,
            "windowAfter": self.window_after,
            "isRequired": self.is_required,
        }
        if self.visit_number is not None:
            result["visitNumber"] = self.visit_number
        if self.target_week is not None:
            result["targetWeek"] = self.target_week
        if self.epoch:
            result["epoch"] = self.epoch
        if self.activities:
            result["activities"] = self.activities
        if self.source_text:
            result["sourceText"] = self.source_text[:200]
        return result


@dataclass
class StratificationFactor:
    """
    A factor used for randomization stratification.
    
    Attributes:
        id: Unique identifier
        name: Factor name (e.g., "Age Group", "Disease Severity")
        categories: Possible values/levels
        is_blocking: Whether used for block randomization
    """
    id: str
    name: str
    categories: List[str] = field(default_factory=list)
    is_blocking: bool = False
    source_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "categories": self.categories,
            "isBlocking": self.is_blocking,
        }
        if self.source_text:
            result["sourceText"] = self.source_text[:200]
        return result


@dataclass
class RandomizationScheme:
    """
    Randomization design including stratification.
    
    Captures how subjects are allocated to treatment arms,
    including ratios and stratification factors.
    
    Attributes:
        id: Unique identifier
        ratio: Allocation ratio (e.g., "1:1", "2:1", "1:1:1")
        method: Randomization method (e.g., "Blocked", "Stratified")
        block_size: Block size if blocked randomization
        stratification_factors: Factors used for stratification
        central_randomization: Whether using IWRS/IXRS
    """
    id: str
    ratio: str = "1:1"
    method: str = "Stratified block randomization"
    block_size: Optional[int] = None
    stratification_factors: List[StratificationFactor] = field(default_factory=list)
    central_randomization: bool = True
    source_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "ratio": self.ratio,
            "method": self.method,
            "centralRandomization": self.central_randomization,
        }
        if self.block_size:
            result["blockSize"] = self.block_size
        if self.stratification_factors:
            result["stratificationFactors"] = [s.to_dict() for s in self.stratification_factors]
        if self.source_text:
            result["sourceText"] = self.source_text[:200]
        return result


@dataclass
class ExecutionModelData:
    """
    Container for all execution model extractions.
    
    Aggregates all execution-level semantics extracted from a protocol.
    """
    # Phase 1 components
    time_anchors: List[TimeAnchor] = field(default_factory=list)
    repetitions: List[Repetition] = field(default_factory=list)
    sampling_constraints: List[SamplingConstraint] = field(default_factory=list)
    execution_types: List[ExecutionTypeAssignment] = field(default_factory=list)
    # Phase 2 components
    traversal_constraints: List[TraversalConstraint] = field(default_factory=list)
    crossover_design: Optional[CrossoverDesign] = None
    footnote_conditions: List[FootnoteCondition] = field(default_factory=list)
    # Phase 3 components
    endpoint_algorithms: List[EndpointAlgorithm] = field(default_factory=list)
    derived_variables: List[DerivedVariable] = field(default_factory=list)
    state_machine: Optional[SubjectStateMachine] = None
    # Phase 4 components
    dosing_regimens: List[DosingRegimen] = field(default_factory=list)
    visit_windows: List[VisitWindow] = field(default_factory=list)
    randomization_scheme: Optional[RandomizationScheme] = None
    # FIX C: Activity bindings for tight coupling
    activity_bindings: List[ActivityBinding] = field(default_factory=list)
    # FIX 3: Analysis windows for endpoint derivation
    analysis_windows: List[AnalysisWindow] = field(default_factory=list)
    # FIX A: Operationalized titration schedules
    titration_schedules: List['DoseTitrationSchedule'] = field(default_factory=list)
    # FIX B: Instance bindings (repetition → ScheduledActivityInstance)
    instance_bindings: List['InstanceBinding'] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "timeAnchors": [a.to_dict() for a in self.time_anchors],
            "repetitions": [r.to_dict() for r in self.repetitions],
            "samplingConstraints": [s.to_dict() for s in self.sampling_constraints],
            "traversalConstraints": [t.to_dict() for t in self.traversal_constraints],
            "executionTypes": [e.to_dict() for e in self.execution_types],
        }
        if self.crossover_design:
            result["crossoverDesign"] = self.crossover_design.to_dict()
        if self.footnote_conditions:
            result["footnoteConditions"] = [f.to_dict() for f in self.footnote_conditions]
        # Phase 3 components
        if self.endpoint_algorithms:
            result["endpointAlgorithms"] = [e.to_dict() for e in self.endpoint_algorithms]
        if self.derived_variables:
            result["derivedVariables"] = [d.to_dict() for d in self.derived_variables]
        if self.state_machine:
            result["stateMachine"] = self.state_machine.to_dict()
        # Phase 4 components
        if self.dosing_regimens:
            result["dosingRegimens"] = [d.to_dict() for d in self.dosing_regimens]
        if self.visit_windows:
            result["visitWindows"] = [v.to_dict() for v in self.visit_windows]
        if self.randomization_scheme:
            result["randomizationScheme"] = self.randomization_scheme.to_dict()
        # FIX C: Activity bindings
        if self.activity_bindings:
            result["activityBindings"] = [b.to_dict() for b in self.activity_bindings]
        # FIX 3: Analysis windows
        if self.analysis_windows:
            result["analysisWindows"] = [w.to_dict() for w in self.analysis_windows]
        # FIX A: Titration schedules
        if self.titration_schedules:
            result["titrationSchedules"] = [t.to_dict() for t in self.titration_schedules]
        # FIX B: Instance bindings
        if self.instance_bindings:
            result["instanceBindings"] = [i.to_dict() for i in self.instance_bindings]
        return result
    
    def to_extension(self) -> Dict[str, Any]:
        """Convert to USDM extensionAttributes format."""
        return {
            "x-executionModel": self.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionModelData':
        return cls(
            time_anchors=[TimeAnchor.from_dict(a) for a in data.get('timeAnchors', [])],
            repetitions=[Repetition.from_dict(r) for r in data.get('repetitions', [])],
            sampling_constraints=[],  # TODO: implement from_dict
            traversal_constraints=[],  # TODO: implement from_dict
            execution_types=[],  # TODO: implement from_dict
        )
    
    def merge(self, other: 'ExecutionModelData') -> 'ExecutionModelData':
        """Merge another ExecutionModelData into this one."""
        # For singleton objects, prefer non-None value
        merged_crossover = self.crossover_design or other.crossover_design
        merged_state_machine = self.state_machine or other.state_machine
        merged_randomization = self.randomization_scheme or other.randomization_scheme
        
        return ExecutionModelData(
            # Phase 1
            time_anchors=self.time_anchors + other.time_anchors,
            repetitions=self.repetitions + other.repetitions,
            sampling_constraints=self.sampling_constraints + other.sampling_constraints,
            execution_types=self.execution_types + other.execution_types,
            # Phase 2
            traversal_constraints=self.traversal_constraints + other.traversal_constraints,
            crossover_design=merged_crossover,
            footnote_conditions=self.footnote_conditions + other.footnote_conditions,
            # Phase 3
            endpoint_algorithms=self.endpoint_algorithms + other.endpoint_algorithms,
            derived_variables=self.derived_variables + other.derived_variables,
            state_machine=merged_state_machine,
            # Phase 4
            dosing_regimens=self.dosing_regimens + other.dosing_regimens,
            visit_windows=self.visit_windows + other.visit_windows,
            randomization_scheme=merged_randomization,
            # Fix 2, 3: Activity bindings and analysis windows
            activity_bindings=self.activity_bindings + other.activity_bindings,
            analysis_windows=self.analysis_windows + other.analysis_windows,
            # Fix A, B: Titration schedules and instance bindings
            titration_schedules=self.titration_schedules + other.titration_schedules,
            instance_bindings=self.instance_bindings + other.instance_bindings,
        )


@dataclass
class ExecutionModelResult:
    """
    Result of execution model extraction.
    
    Wraps ExecutionModelData with metadata about the extraction process.
    """
    success: bool
    data: Optional[ExecutionModelData] = None
    error: Optional[str] = None
    pages_used: List[int] = field(default_factory=list)
    model_used: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "success": self.success,
            "pagesUsed": self.pages_used,
            "modelUsed": self.model_used,
        }
        if self.data:
            result["data"] = self.data.to_dict()
        if self.error:
            result["error"] = self.error
        return result
