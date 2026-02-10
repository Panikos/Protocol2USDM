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
    'execution': ['time_anchors', 'repetitions', 'traversal_constraints', 'footnote_conditions'],
}


@dataclass
class PipelineContext:
    """
    Accumulates all extraction results for reference by subsequent extractors.
    
    Each extraction phase adds its results and can reference prior phases.
    This ensures:
    - Consistent ID references across extractions
    - No arbitrary labels that need resolution
    - Rich context for better extraction accuracy
    """
    
    # Core SoA entities (from initial extraction)
    epochs: List[Dict[str, Any]] = field(default_factory=list)
    encounters: List[Dict[str, Any]] = field(default_factory=list)
    activities: List[Dict[str, Any]] = field(default_factory=list)
    timepoints: List[Dict[str, Any]] = field(default_factory=list)
    
    # Study metadata
    study_title: str = ""
    study_id: str = ""
    sponsor: str = ""
    indication: str = ""
    phase: str = ""
    study_type: str = ""  # "Interventional" or "Observational"
    
    # Arms and design
    arms: List[Dict[str, Any]] = field(default_factory=list)
    cohorts: List[Dict[str, Any]] = field(default_factory=list)
    study_cells: List[Dict[str, Any]] = field(default_factory=list)
    
    # Eligibility
    inclusion_criteria: List[Dict[str, Any]] = field(default_factory=list)
    exclusion_criteria: List[Dict[str, Any]] = field(default_factory=list)
    
    # Objectives & Endpoints
    objectives: List[Dict[str, Any]] = field(default_factory=list)
    endpoints: List[Dict[str, Any]] = field(default_factory=list)
    
    # Interventions
    interventions: List[Dict[str, Any]] = field(default_factory=list)
    products: List[Dict[str, Any]] = field(default_factory=list)
    
    # Procedures & Devices
    procedures: List[Dict[str, Any]] = field(default_factory=list)
    devices: List[Dict[str, Any]] = field(default_factory=list)
    
    # Scheduling
    timings: List[Dict[str, Any]] = field(default_factory=list)
    scheduling_rules: List[Dict[str, Any]] = field(default_factory=list)
    
    # Execution model (added later in pipeline)
    time_anchors: List[Dict[str, Any]] = field(default_factory=list)
    repetitions: List[Dict[str, Any]] = field(default_factory=list)
    traversal_constraints: List[Dict[str, Any]] = field(default_factory=list)
    footnote_conditions: List[Dict[str, Any]] = field(default_factory=list)
    
    # Lookup maps (built lazily)
    _epoch_by_id: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    _epoch_by_name: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    _encounter_by_id: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    _activity_by_id: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    _activity_by_name: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    _arm_by_id: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    _intervention_by_id: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Thread lock for safe concurrent merges
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    
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
                epochs=copy.deepcopy(self.epochs),
                encounters=copy.deepcopy(self.encounters),
                activities=copy.deepcopy(self.activities),
                timepoints=copy.deepcopy(self.timepoints),
                study_title=self.study_title,
                study_id=self.study_id,
                sponsor=self.sponsor,
                indication=self.indication,
                phase=self.phase,
                study_type=self.study_type,
                arms=copy.deepcopy(self.arms),
                cohorts=copy.deepcopy(self.cohorts),
                study_cells=copy.deepcopy(self.study_cells),
                inclusion_criteria=copy.deepcopy(self.inclusion_criteria),
                exclusion_criteria=copy.deepcopy(self.exclusion_criteria),
                objectives=copy.deepcopy(self.objectives),
                endpoints=copy.deepcopy(self.endpoints),
                interventions=copy.deepcopy(self.interventions),
                products=copy.deepcopy(self.products),
                procedures=copy.deepcopy(self.procedures),
                devices=copy.deepcopy(self.devices),
                timings=copy.deepcopy(self.timings),
                scheduling_rules=copy.deepcopy(self.scheduling_rules),
                time_anchors=copy.deepcopy(self.time_anchors),
                repetitions=copy.deepcopy(self.repetitions),
                traversal_constraints=copy.deepcopy(self.traversal_constraints),
                footnote_conditions=copy.deepcopy(self.footnote_conditions),
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
        self._epoch_by_id.clear()
        self._epoch_by_name.clear()
        for epoch in self.epochs:
            epoch_id = epoch.get('id', '')
            epoch_name = epoch.get('name', '')
            if epoch_id:
                self._epoch_by_id[epoch_id] = epoch
            if epoch_name:
                self._epoch_by_name[epoch_name.lower()] = epoch
        
        self._encounter_by_id.clear()
        for enc in self.encounters:
            enc_id = enc.get('id', '')
            if enc_id:
                self._encounter_by_id[enc_id] = enc
        
        self._activity_by_id.clear()
        self._activity_by_name.clear()
        for act in self.activities:
            act_id = act.get('id', '')
            act_name = act.get('name', '')
            if act_id:
                self._activity_by_id[act_id] = act
            if act_name:
                self._activity_by_name[act_name.lower()] = act
        
        self._arm_by_id.clear()
        for arm in self.arms:
            arm_id = arm.get('id', '')
            if arm_id:
                self._arm_by_id[arm_id] = arm
        
        self._intervention_by_id.clear()
        for intv in self.interventions:
            intv_id = intv.get('id', '')
            if intv_id:
                self._intervention_by_id[intv_id] = intv
    
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
