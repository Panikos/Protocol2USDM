"""
Pipeline Context

Accumulates extraction results throughout the pipeline, enabling subsequent
extractors to reference relevant prior data. This ensures consistency and
avoids creating arbitrary labels that need downstream resolution.

Architecture:
    PDF → SoA Extraction → PipelineContext
                              ↓
    PDF → Metadata → adds to context
                              ↓
    PDF → Eligibility → references metadata, adds to context
                              ↓
    PDF → Objectives → references metadata, adds to context
                              ↓
    PDF → Study Design → references all above, adds to context
                              ↓
    ... subsequent extractors reference accumulated context ...
"""

import copy
import logging
import threading
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

# Phase → fields that phase is authoritative for during merge_from().
# This is the single source of truth for which phase owns which context fields.
# Tests in test_pipeline_context.py verify this mapping stays in sync.
PHASE_FIELD_OWNERSHIP: Dict[str, List[str]] = {
    'metadata': ['study_title', 'study_id', 'sponsor', 'indication', 'phase', 'study_type'],
    'eligibility': ['inclusion_criteria', 'exclusion_criteria'],
    'objectives': ['objectives', 'endpoints'],
    'studydesign': ['arms', 'cohorts'],
    'interventions': ['interventions', 'products'],
    'procedures': ['procedures', 'devices'],
    'scheduling': ['timings', 'scheduling_rules'],
    'narrative': ['narrative_contents'],
    'execution': ['time_anchors', 'repetitions', 'traversal_constraints', 'footnote_conditions'],
}


# ---------------------------------------------------------------------------
# Sub-context dataclasses (W-HIGH-2 decomposition)
# ---------------------------------------------------------------------------

@dataclass
class SoAContext:
    """Core Schedule of Activities entities from initial extraction."""
    epochs: List[Dict[str, Any]] = field(default_factory=list)
    encounters: List[Dict[str, Any]] = field(default_factory=list)
    activities: List[Dict[str, Any]] = field(default_factory=list)
    timepoints: List[Dict[str, Any]] = field(default_factory=list)
    study_cells: List[Dict[str, Any]] = field(default_factory=list)

    # Lookup maps (rebuilt on demand)
    _epoch_by_id: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    _epoch_by_name: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    _encounter_by_id: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    _activity_by_id: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    _activity_by_name: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def rebuild_maps(self):
        """Rebuild all SoA lookup maps from current data."""
        self._epoch_by_id.clear()
        self._epoch_by_name.clear()
        for epoch in self.epochs:
            eid = epoch.get('id', '')
            ename = epoch.get('name', '')
            if eid:
                self._epoch_by_id[eid] = epoch
            if ename:
                self._epoch_by_name[ename.lower()] = epoch

        self._encounter_by_id.clear()
        for enc in self.encounters:
            eid = enc.get('id', '')
            if eid:
                self._encounter_by_id[eid] = enc

        self._activity_by_id.clear()
        self._activity_by_name.clear()
        for act in self.activities:
            aid = act.get('id', '')
            aname = act.get('name', '')
            if aid:
                self._activity_by_id[aid] = act
            if aname:
                self._activity_by_name[aname.lower()] = act


@dataclass
class MetadataContext:
    """Study-level metadata from the metadata extraction phase."""
    study_title: str = ""
    study_id: str = ""
    sponsor: str = ""
    indication: str = ""
    phase: str = ""
    study_type: str = ""  # "Interventional" or "Observational"


@dataclass
class DesignContext:
    """Study design entities: arms, cohorts, objectives, endpoints, eligibility."""
    arms: List[Dict[str, Any]] = field(default_factory=list)
    cohorts: List[Dict[str, Any]] = field(default_factory=list)
    objectives: List[Dict[str, Any]] = field(default_factory=list)
    endpoints: List[Dict[str, Any]] = field(default_factory=list)
    inclusion_criteria: List[Dict[str, Any]] = field(default_factory=list)
    exclusion_criteria: List[Dict[str, Any]] = field(default_factory=list)

    # Lookup maps
    _arm_by_id: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def rebuild_maps(self):
        """Rebuild design lookup maps."""
        self._arm_by_id.clear()
        for arm in self.arms:
            aid = arm.get('id', '')
            if aid:
                self._arm_by_id[aid] = arm


@dataclass
class InterventionContext:
    """Interventions, products, procedures, and devices."""
    interventions: List[Dict[str, Any]] = field(default_factory=list)
    products: List[Dict[str, Any]] = field(default_factory=list)
    procedures: List[Dict[str, Any]] = field(default_factory=list)
    devices: List[Dict[str, Any]] = field(default_factory=list)

    # Lookup maps
    _intervention_by_id: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def rebuild_maps(self):
        """Rebuild intervention lookup maps."""
        self._intervention_by_id.clear()
        for intv in self.interventions:
            iid = intv.get('id', '')
            if iid:
                self._intervention_by_id[iid] = intv


@dataclass
class SchedulingContext:
    """Scheduling, execution model, and narrative data."""
    timings: List[Dict[str, Any]] = field(default_factory=list)
    scheduling_rules: List[Dict[str, Any]] = field(default_factory=list)
    narrative_contents: List[Dict[str, Any]] = field(default_factory=list)
    time_anchors: List[Dict[str, Any]] = field(default_factory=list)
    repetitions: List[Dict[str, Any]] = field(default_factory=list)
    traversal_constraints: List[Dict[str, Any]] = field(default_factory=list)
    footnote_conditions: List[Dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# PipelineContext — composed from sub-contexts with backward-compatible API
# ---------------------------------------------------------------------------

@dataclass
class PipelineContext:
    """
    Accumulates all extraction results for reference by subsequent extractors.
    
    Each extraction phase adds its results and can reference prior phases.
    This ensures:
    - Consistent ID references across extractions
    - No arbitrary labels that need resolution
    - Rich context for better extraction accuracy
    
    Internally composed of focused sub-contexts (SoAContext, MetadataContext,
    DesignContext, InterventionContext, SchedulingContext). All fields are
    accessible directly on PipelineContext for backward compatibility.
    """
    
    # --- Sub-contexts (W-HIGH-2 decomposition) ---
    soa: SoAContext = field(default_factory=SoAContext)
    metadata: MetadataContext = field(default_factory=MetadataContext)
    design: DesignContext = field(default_factory=DesignContext)
    intervention: InterventionContext = field(default_factory=InterventionContext)
    scheduling: SchedulingContext = field(default_factory=SchedulingContext)
    
    # Thread lock for safe concurrent merges
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    
    # --- Backward-compatible property delegates ---
    # SoAContext
    @property
    def epochs(self): return self.soa.epochs
    @epochs.setter
    def epochs(self, v): self.soa.epochs = v
    @property
    def encounters(self): return self.soa.encounters
    @encounters.setter
    def encounters(self, v): self.soa.encounters = v
    @property
    def activities(self): return self.soa.activities
    @activities.setter
    def activities(self, v): self.soa.activities = v
    @property
    def timepoints(self): return self.soa.timepoints
    @timepoints.setter
    def timepoints(self, v): self.soa.timepoints = v
    @property
    def study_cells(self): return self.soa.study_cells
    @study_cells.setter
    def study_cells(self, v): self.soa.study_cells = v

    # MetadataContext
    @property
    def study_title(self): return self.metadata.study_title
    @study_title.setter
    def study_title(self, v): self.metadata.study_title = v
    @property
    def study_id(self): return self.metadata.study_id
    @study_id.setter
    def study_id(self, v): self.metadata.study_id = v
    @property
    def sponsor(self): return self.metadata.sponsor
    @sponsor.setter
    def sponsor(self, v): self.metadata.sponsor = v
    @property
    def indication(self): return self.metadata.indication
    @indication.setter
    def indication(self, v): self.metadata.indication = v
    @property
    def phase(self): return self.metadata.phase
    @phase.setter
    def phase(self, v): self.metadata.phase = v
    @property
    def study_type(self): return self.metadata.study_type
    @study_type.setter
    def study_type(self, v): self.metadata.study_type = v

    # DesignContext
    @property
    def arms(self): return self.design.arms
    @arms.setter
    def arms(self, v): self.design.arms = v
    @property
    def cohorts(self): return self.design.cohorts
    @cohorts.setter
    def cohorts(self, v): self.design.cohorts = v
    @property
    def objectives(self): return self.design.objectives
    @objectives.setter
    def objectives(self, v): self.design.objectives = v
    @property
    def endpoints(self): return self.design.endpoints
    @endpoints.setter
    def endpoints(self, v): self.design.endpoints = v
    @property
    def inclusion_criteria(self): return self.design.inclusion_criteria
    @inclusion_criteria.setter
    def inclusion_criteria(self, v): self.design.inclusion_criteria = v
    @property
    def exclusion_criteria(self): return self.design.exclusion_criteria
    @exclusion_criteria.setter
    def exclusion_criteria(self, v): self.design.exclusion_criteria = v

    # InterventionContext
    @property
    def interventions(self): return self.intervention.interventions
    @interventions.setter
    def interventions(self, v): self.intervention.interventions = v
    @property
    def products(self): return self.intervention.products
    @products.setter
    def products(self, v): self.intervention.products = v
    @property
    def procedures(self): return self.intervention.procedures
    @procedures.setter
    def procedures(self, v): self.intervention.procedures = v
    @property
    def devices(self): return self.intervention.devices
    @devices.setter
    def devices(self, v): self.intervention.devices = v

    # SchedulingContext
    @property
    def timings(self): return self.scheduling.timings
    @timings.setter
    def timings(self, v): self.scheduling.timings = v
    @property
    def scheduling_rules(self): return self.scheduling.scheduling_rules
    @scheduling_rules.setter
    def scheduling_rules(self, v): self.scheduling.scheduling_rules = v
    @property
    def narrative_contents(self): return self.scheduling.narrative_contents
    @narrative_contents.setter
    def narrative_contents(self, v): self.scheduling.narrative_contents = v
    @property
    def time_anchors(self): return self.scheduling.time_anchors
    @time_anchors.setter
    def time_anchors(self, v): self.scheduling.time_anchors = v
    @property
    def repetitions(self): return self.scheduling.repetitions
    @repetitions.setter
    def repetitions(self, v): self.scheduling.repetitions = v
    @property
    def traversal_constraints(self): return self.scheduling.traversal_constraints
    @traversal_constraints.setter
    def traversal_constraints(self, v): self.scheduling.traversal_constraints = v
    @property
    def footnote_conditions(self): return self.scheduling.footnote_conditions
    @footnote_conditions.setter
    def footnote_conditions(self, v): self.scheduling.footnote_conditions = v

    # Lookup map delegates (read-only)
    @property
    def _epoch_by_id(self): return self.soa._epoch_by_id
    @property
    def _epoch_by_name(self): return self.soa._epoch_by_name
    @property
    def _encounter_by_id(self): return self.soa._encounter_by_id
    @property
    def _activity_by_id(self): return self.soa._activity_by_id
    @property
    def _activity_by_name(self): return self.soa._activity_by_name
    @property
    def _arm_by_id(self): return self.design._arm_by_id
    @property
    def _intervention_by_id(self): return self.intervention._intervention_by_id
    
    def __post_init__(self):
        """Build lookup maps after initialization."""
        self._rebuild_lookup_maps()
    
    def snapshot(self) -> 'PipelineContext':
        """
        Create a deep-copy snapshot of this context for safe use in a parallel phase.
        
        The snapshot is independent — mutations by a phase won't affect the original.
        After the phase completes, call merge_from() on the original to incorporate results.
        """
        with self._lock:
            ctx = PipelineContext(
                soa=SoAContext(
                    epochs=copy.deepcopy(self.soa.epochs),
                    encounters=copy.deepcopy(self.soa.encounters),
                    activities=copy.deepcopy(self.soa.activities),
                    timepoints=copy.deepcopy(self.soa.timepoints),
                    study_cells=copy.deepcopy(self.soa.study_cells),
                ),
                metadata=MetadataContext(
                    study_title=self.metadata.study_title,
                    study_id=self.metadata.study_id,
                    sponsor=self.metadata.sponsor,
                    indication=self.metadata.indication,
                    phase=self.metadata.phase,
                    study_type=self.metadata.study_type,
                ),
                design=DesignContext(
                    arms=copy.deepcopy(self.design.arms),
                    cohorts=copy.deepcopy(self.design.cohorts),
                    objectives=copy.deepcopy(self.design.objectives),
                    endpoints=copy.deepcopy(self.design.endpoints),
                    inclusion_criteria=copy.deepcopy(self.design.inclusion_criteria),
                    exclusion_criteria=copy.deepcopy(self.design.exclusion_criteria),
                ),
                intervention=InterventionContext(
                    interventions=copy.deepcopy(self.intervention.interventions),
                    products=copy.deepcopy(self.intervention.products),
                    procedures=copy.deepcopy(self.intervention.procedures),
                    devices=copy.deepcopy(self.intervention.devices),
                ),
                scheduling=SchedulingContext(
                    timings=copy.deepcopy(self.scheduling.timings),
                    scheduling_rules=copy.deepcopy(self.scheduling.scheduling_rules),
                    narrative_contents=copy.deepcopy(self.scheduling.narrative_contents),
                    time_anchors=copy.deepcopy(self.scheduling.time_anchors),
                    repetitions=copy.deepcopy(self.scheduling.repetitions),
                    traversal_constraints=copy.deepcopy(self.scheduling.traversal_constraints),
                    footnote_conditions=copy.deepcopy(self.scheduling.footnote_conditions),
                ),
            )
        return ctx
    
    def merge_from(self, phase_name: str, phase_snapshot: 'PipelineContext') -> None:
        """
        Merge results from a phase's snapshot back into this (authoritative) context.
        
        Only fields that the given phase is known to populate are merged,
        preventing one phase from clobbering another's data.
        
        Args:
            phase_name: Name of the phase that produced the snapshot
            phase_snapshot: The snapshot context after the phase ran
        """
        fields_to_merge = PHASE_FIELD_OWNERSHIP.get(phase_name)
        if not fields_to_merge:
            logger.debug(f"No merge mapping for phase '{phase_name}', skipping context merge")
            return
        
        with self._lock:
            for field_name in fields_to_merge:
                new_value = getattr(phase_snapshot, field_name, None)
                if new_value:  # Only overwrite if the phase actually produced data
                    setattr(self, field_name, new_value)
            self._rebuild_lookup_maps()
        
        logger.debug(f"Merged context from phase '{phase_name}': {fields_to_merge}")
    
    def _rebuild_lookup_maps(self):
        """Rebuild all lookup maps from current data."""
        self.soa.rebuild_maps()
        self.design.rebuild_maps()
        self.intervention.rebuild_maps()
    
    # === Update methods (used in sequential mode) ===
    
    def update_from_soa(self, soa_data: Dict[str, Any]):
        """Update context from SoA extraction result."""
        if not soa_data:
            return
        
        # Try direct keys first
        self.epochs = soa_data.get('epochs', self.epochs)
        self.encounters = soa_data.get('encounters', self.encounters)
        self.activities = soa_data.get('activities', self.activities)
        self.timepoints = soa_data.get('timepoints', self.timepoints)
        self.arms = soa_data.get('arms', self.arms)
        self.study_cells = soa_data.get('studyCells', self.study_cells)
        
        # Try nested USDM structure
        study = soa_data.get('study', {})
        versions = study.get('versions', [])
        if versions:
            for version in versions:
                designs = version.get('studyDesigns', [])
                if designs:
                    design = designs[0]
                    self.epochs = self.epochs or design.get('epochs', [])
                    self.encounters = self.encounters or design.get('encounters', [])
                    self.activities = self.activities or design.get('activities', [])
                    self.arms = self.arms or design.get('arms', [])
                    self.study_cells = self.study_cells or design.get('studyCells', [])
                    break
        
        self._rebuild_lookup_maps()
        logger.info(f"Updated context from SoA: {len(self.epochs)} epochs, {len(self.encounters)} encounters, {len(self.activities)} activities")
    
    def update_from_metadata(self, metadata):
        """Update context from metadata extraction."""
        if not metadata:
            return
        # Handle both dict and object types
        if hasattr(metadata, 'to_dict'):
            metadata = metadata.to_dict()
        elif hasattr(metadata, '__dict__') and not isinstance(metadata, dict):
            metadata = vars(metadata)
        if isinstance(metadata, dict):
            self.study_title = metadata.get('studyTitle', metadata.get('study_title', self.study_title))
            self.study_id = metadata.get('studyId', metadata.get('study_id', self.study_id))
            self.sponsor = metadata.get('sponsor', self.sponsor)
            self.indication = metadata.get('indication', self.indication)
            self.phase = metadata.get('phase', self.phase)
            self.study_type = metadata.get('studyType', metadata.get('study_type', self.study_type))
        logger.debug(f"Updated context from metadata: {self.study_title}")
    
    def _to_dict(self, obj):
        """Convert object to dict if needed."""
        if obj is None:
            return {}
        if isinstance(obj, dict):
            return obj
        if hasattr(obj, 'to_dict'):
            return obj.to_dict()
        if hasattr(obj, '__dict__'):
            return vars(obj)
        return {}
    
    def update_from_eligibility(self, eligibility):
        """Update context from eligibility extraction."""
        if not eligibility:
            return
        data = self._to_dict(eligibility)
        self.inclusion_criteria = data.get('inclusionCriteria', data.get('inclusion_criteria', self.inclusion_criteria))
        self.exclusion_criteria = data.get('exclusionCriteria', data.get('exclusion_criteria', self.exclusion_criteria))
        logger.debug(f"Updated context from eligibility: {len(self.inclusion_criteria)} inclusion, {len(self.exclusion_criteria)} exclusion")
    
    def update_from_objectives(self, objectives):
        """Update context from objectives extraction."""
        if not objectives:
            return
        data = self._to_dict(objectives)
        self.objectives = data.get('objectives', self.objectives)
        self.endpoints = data.get('endpoints', self.endpoints)
        logger.debug(f"Updated context from objectives: {len(self.objectives)} objectives, {len(self.endpoints)} endpoints")
    
    def update_from_studydesign(self, design):
        """Update context from study design extraction."""
        if not design:
            return
        data = self._to_dict(design)
        self.arms = data.get('arms', self.arms)
        self.cohorts = data.get('cohorts', self.cohorts)
        self._rebuild_lookup_maps()
        logger.debug(f"Updated context from study design: {len(self.arms)} arms, {len(self.cohorts)} cohorts")
    
    def update_from_interventions(self, interventions):
        """Update context from interventions extraction."""
        if not interventions:
            return
        data = self._to_dict(interventions)
        self.interventions = data.get('interventions', self.interventions)
        self.products = data.get('products', self.products)
        self._rebuild_lookup_maps()
        logger.debug(f"Updated context from interventions: {len(self.interventions)} interventions")
    
    def update_from_procedures(self, procedures):
        """Update context from procedures extraction."""
        if not procedures:
            return
        data = self._to_dict(procedures)
        self.procedures = data.get('procedures', self.procedures)
        self.devices = data.get('devices', self.devices)
        logger.debug(f"Updated context from procedures: {len(self.procedures)} procedures")
    
    def update_from_scheduling(self, scheduling):
        """Update context from scheduling extraction."""
        if not scheduling:
            return
        data = self._to_dict(scheduling)
        self.timings = data.get('timings', self.timings)
        self.scheduling_rules = data.get('rules', self.scheduling_rules)
        logger.debug(f"Updated context from scheduling: {len(self.timings)} timings")
    
    def update_from_execution_model(self, execution: Dict[str, Any]):
        """Update context from execution model extraction."""
        if not execution:
            return
        self.time_anchors = execution.get('timeAnchors', self.time_anchors)
        self.repetitions = execution.get('repetitions', self.repetitions)
        self.traversal_constraints = execution.get('traversalConstraints', self.traversal_constraints)
        self.footnote_conditions = execution.get('footnoteConditions', self.footnote_conditions)
        logger.debug(f"Updated context from execution: {len(self.repetitions)} repetitions")
    
    # === Query methods ===
    
    def has_epochs(self) -> bool:
        return len(self.epochs) > 0
    
    def has_encounters(self) -> bool:
        return len(self.encounters) > 0
    
    def has_activities(self) -> bool:
        return len(self.activities) > 0
    
    def has_arms(self) -> bool:
        return len(self.arms) > 0
    
    def has_interventions(self) -> bool:
        return len(self.interventions) > 0
    
    def has_objectives(self) -> bool:
        return len(self.objectives) > 0
    
    def get_epoch_ids(self) -> List[str]:
        return [e.get('id', '') for e in self.epochs if e.get('id')]
    
    def get_epoch_names(self) -> List[str]:
        return [e.get('name', '') for e in self.epochs if e.get('name')]
    
    def get_activity_names(self) -> List[str]:
        return [a.get('name', '') for a in self.activities if a.get('name')]
    
    def get_intervention_names(self) -> List[str]:
        return [i.get('name', '') for i in self.interventions if i.get('name')]
    
    def find_epoch_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        return self._epoch_by_name.get(name.lower())
    
    def find_epoch_by_id(self, epoch_id: str) -> Optional[Dict[str, Any]]:
        return self._epoch_by_id.get(epoch_id)
    
    def find_activity_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        return self._activity_by_name.get(name.lower())
    
    def find_intervention_by_id(self, intv_id: str) -> Optional[Dict[str, Any]]:
        return self._intervention_by_id.get(intv_id)
    
    def get_summary(self) -> str:
        """Get a summary of available context."""
        parts = []
        if self.epochs:
            parts.append(f"{len(self.epochs)} epochs")
        if self.encounters:
            parts.append(f"{len(self.encounters)} encounters")
        if self.activities:
            parts.append(f"{len(self.activities)} activities")
        if self.arms:
            parts.append(f"{len(self.arms)} arms")
        if self.interventions:
            parts.append(f"{len(self.interventions)} interventions")
        if self.objectives:
            parts.append(f"{len(self.objectives)} objectives")
        if self.inclusion_criteria:
            parts.append(f"{len(self.inclusion_criteria)} inclusion")
        return ", ".join(parts) if parts else "empty"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for serialization."""
        return {
            'epochs': self.epochs,
            'encounters': self.encounters,
            'activities': self.activities,
            'timepoints': self.timepoints,
            'arms': self.arms,
            'cohorts': self.cohorts,
            'study_cells': self.study_cells,
            'study_title': self.study_title,
            'study_id': self.study_id,
            'sponsor': self.sponsor,
            'indication': self.indication,
            'phase': self.phase,
            'study_type': self.study_type,
            'inclusion_criteria': self.inclusion_criteria,
            'exclusion_criteria': self.exclusion_criteria,
            'objectives': self.objectives,
            'endpoints': self.endpoints,
            'interventions': self.interventions,
            'products': self.products,
            'procedures': self.procedures,
            'devices': self.devices,
            'timings': self.timings,
            'scheduling_rules': self.scheduling_rules,
        }


def create_pipeline_context(soa_data: Optional[Dict[str, Any]] = None) -> PipelineContext:
    """
    Create a new pipeline context, optionally initialized from SoA data.
    
    Args:
        soa_data: Optional SoA extraction result to initialize from
        
    Returns:
        PipelineContext ready to accumulate extraction results
    """
    context = PipelineContext()
    if soa_data:
        context.update_from_soa(soa_data)
    return context
