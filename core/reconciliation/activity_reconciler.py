"""
Activity Reconciliation

Reconciles activity data from multiple extraction sources (SoA, Procedures, 
Execution Model) into canonical activities for protocol_usdm.json.
"""

import uuid
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from .base import (
    BaseReconciler,
    EntityContribution,
    ReconciledEntity,
    clean_entity_name,
    extract_footnote_refs,
    normalize_for_matching,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Activity Type Inference
# =============================================================================

ACTIVITY_TYPE_KEYWORDS = {
    # Procedures
    "blood": ("procedure", "Blood Collection"),
    "urine": ("procedure", "Urine Collection"),
    "sample": ("procedure", "Sample Collection"),
    "biopsy": ("procedure", "Biopsy"),
    "ecg": ("procedure", "ECG"),
    "ekg": ("procedure", "ECG"),
    "mri": ("procedure", "MRI"),
    "ct scan": ("procedure", "CT Scan"),
    "x-ray": ("procedure", "X-ray"),
    "xray": ("procedure", "X-ray"),
    "physical exam": ("procedure", "Physical Examination"),
    "vital": ("procedure", "Vital Signs"),
    
    # Assessments
    "questionnaire": ("assessment", "Questionnaire"),
    "survey": ("assessment", "Survey"),
    "scale": ("assessment", "Assessment Scale"),
    "score": ("assessment", "Assessment Score"),
    "diary": ("assessment", "Patient Diary"),
    "cognitive": ("assessment", "Cognitive Assessment"),
    
    # Lab tests
    "hematology": ("lab", "Hematology"),
    "chemistry": ("lab", "Chemistry"),
    "urinalysis": ("lab", "Urinalysis"),
    "serology": ("lab", "Serology"),
    "coagulation": ("lab", "Coagulation"),
    
    # Drug administration
    "dose": ("administration", "Drug Administration"),
    "infusion": ("administration", "Infusion"),
    "injection": ("administration", "Injection"),
    "administration": ("administration", "Drug Administration"),
    
    # Consent/Documentation
    "consent": ("documentation", "Informed Consent"),
    "randomization": ("documentation", "Randomization"),
    "enrollment": ("documentation", "Enrollment"),
}


def infer_activity_type(name: str) -> tuple:
    """Infer activity type from name."""
    name_lower = name.lower()
    
    for keyword, (category, label) in ACTIVITY_TYPE_KEYWORDS.items():
        if keyword in name_lower:
            return category, label
    
    return "other", "Study Activity"


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class ActivityContribution(EntityContribution):
    """Activity contribution from an extraction source."""
    activity_type: str = "other"        # procedure, assessment, lab, administration, other
    group_name: Optional[str] = None    # Activity group (e.g., "Lab Tests")
    epoch_ids: List[str] = field(default_factory=list)
    encounter_ids: List[str] = field(default_factory=list)
    is_conditional: bool = False
    condition_text: Optional[str] = None
    repetition_id: Optional[str] = None  # Link to execution model repetition
    timing_info: Dict[str, Any] = field(default_factory=dict)


@dataclass  
class ReconciledActivity(ReconciledEntity):
    """Reconciled activity for protocol_usdm.json."""
    activity_type: str = "other"
    group_name: Optional[str] = None
    epoch_ids: List[str] = field(default_factory=list)
    encounter_ids: List[str] = field(default_factory=list)
    is_conditional: bool = False
    condition_text: Optional[str] = None
    repetition_id: Optional[str] = None
    timing_info: Dict[str, Any] = field(default_factory=dict)
    instance_type: str = "Activity"
    
    def to_usdm_dict(self) -> Dict[str, Any]:
        """Convert to USDM-compliant dictionary."""
        result = self._base_usdm_dict()
        
        # Add definedProcedures if this is a procedure type
        if self.activity_type == "procedure":
            result["definedProcedures"] = []
        
        # Add biomedicalConcepts placeholder
        result["biomedicalConcepts"] = []
        
        # Build extension attributes
        extra_extensions = []
        
        # Activity type
        extra_extensions.append({
            "id": str(uuid.uuid4()),
            "url": "https://protocol2usdm.io/extensions/x-activityType",
            "instanceType": "ExtensionAttribute",
            "valueString": self.activity_type
        })
        
        # Group name
        if self.group_name:
            extra_extensions.append({
                "id": str(uuid.uuid4()),
                "url": "https://protocol2usdm.io/extensions/x-activityGroup",
                "instanceType": "ExtensionAttribute",
                "valueString": self.group_name
            })
        
        # Conditional flag
        if self.is_conditional:
            extra_extensions.append({
                "id": str(uuid.uuid4()),
                "url": "https://protocol2usdm.io/extensions/x-activityConditional",
                "instanceType": "ExtensionAttribute",
                "valueBoolean": True
            })
            if self.condition_text:
                extra_extensions.append({
                    "id": str(uuid.uuid4()),
                    "url": "https://protocol2usdm.io/extensions/x-activityConditionText",
                    "instanceType": "ExtensionAttribute",
                    "valueString": self.condition_text
                })
        
        # Repetition link
        if self.repetition_id:
            extra_extensions.append({
                "id": str(uuid.uuid4()),
                "url": "https://protocol2usdm.io/extensions/x-activityRepetitionId",
                "instanceType": "ExtensionAttribute",
                "valueString": self.repetition_id
            })
        
        # Timing info
        if self.timing_info:
            extra_extensions.append({
                "id": str(uuid.uuid4()),
                "url": "https://protocol2usdm.io/extensions/x-activityTiming",
                "instanceType": "ExtensionAttribute",
                "valueString": str(self.timing_info)
            })
        
        self._add_extension_attributes(result, extra_extensions=extra_extensions)
        
        return result


# =============================================================================
# Activity Reconciler
# =============================================================================

class ActivityReconciler(BaseReconciler[ActivityContribution, ReconciledActivity]):
    """
    Reconciler for activity data from multiple sources.
    
    Priority order (default):
    - SoA: 10 (base activities with tick marks)
    - Procedures: 20 (detailed procedure info)
    - Execution Model: 25 (repetition patterns, timing)
    - Footnotes: 30 (conditional logic)
    """
    
    def _create_contribution(
        self,
        source: str,
        entity: Dict[str, Any],
        index: int,
        priority: int,
        group_name: Optional[str] = None,
        **kwargs
    ) -> ActivityContribution:
        """Create activity contribution from raw dict."""
        raw_name = entity.get('name', entity.get('label', f'Activity {index+1}'))
        canonical = clean_entity_name(raw_name)
        footnotes = extract_footnote_refs(raw_name)
        
        # Infer activity type
        activity_type = entity.get('activityType')
        if not activity_type:
            activity_type, _ = infer_activity_type(canonical)
        
        # Extract group from entity or use provided
        entity_group = entity.get('group', entity.get('groupName'))
        final_group = group_name or entity_group
        
        return ActivityContribution(
            source=source,
            entity_id=entity.get('id', f'{source}_activity_{index+1}'),
            raw_name=raw_name,
            canonical_name=canonical,
            priority=priority,
            metadata={
                'footnoteRefs': footnotes,
                'originalIndex': index,
                **{k: v for k, v in entity.items() 
                   if k not in ['id', 'name', 'activityType', 'group']}
            },
            activity_type=activity_type,
            group_name=final_group,
            epoch_ids=entity.get('epochIds', []),
            encounter_ids=entity.get('encounterIds', []),
            is_conditional=entity.get('isConditional', False),
            condition_text=entity.get('conditionText'),
            repetition_id=entity.get('repetitionId'),
            timing_info=entity.get('timing', {}),
        )
    
    def _reconcile_entity(
        self,
        canonical_name: str,
        contributions: List[ActivityContribution]
    ) -> ReconciledActivity:
        """Reconcile multiple activity contributions."""
        # Sort by priority (highest first)
        contributions.sort(key=lambda c: -c.priority)
        primary = contributions[0]
        
        # Merge epoch and encounter IDs from all sources
        all_epoch_ids = set()
        all_encounter_ids = set()
        for c in contributions:
            all_epoch_ids.update(c.epoch_ids)
            all_encounter_ids.update(c.encounter_ids)
        
        # Use highest priority group name
        group_name = None
        for c in contributions:
            if c.group_name:
                group_name = c.group_name
                break
        
        # If any source says conditional, it's conditional
        is_conditional = any(c.is_conditional for c in contributions)
        condition_text = None
        for c in contributions:
            if c.condition_text:
                condition_text = c.condition_text
                break
        
        # Get repetition ID from execution model contribution
        repetition_id = None
        for c in contributions:
            if c.repetition_id:
                repetition_id = c.repetition_id
                break
        
        # Merge timing info
        timing_info = {}
        for c in contributions:
            timing_info.update(c.timing_info)
        
        return ReconciledActivity(
            id=self._get_best_id(contributions, "activity"),
            name=canonical_name,
            raw_name=primary.raw_name,
            sources=self._collect_sources(contributions),
            footnote_refs=self._collect_footnotes(contributions),
            activity_type=primary.activity_type,
            group_name=group_name,
            epoch_ids=list(all_epoch_ids),
            encounter_ids=list(all_encounter_ids),
            is_conditional=is_conditional,
            condition_text=condition_text,
            repetition_id=repetition_id,
            timing_info=timing_info,
        )
    
    def _post_reconcile(self, reconciled: List[ReconciledActivity]) -> List[ReconciledActivity]:
        """Sort activities by group and name."""
        # Sort by group (None last), then by name
        reconciled.sort(key=lambda a: (
            a.group_name or "zzz",  # None groups last
            a.name
        ))
        return reconciled
    
    def contribute_from_procedures(
        self,
        procedures: List[Dict[str, Any]],
        priority: int = 20
    ) -> None:
        """
        Add procedure contributions with automatic type mapping.
        
        Args:
            procedures: List of procedure dicts from procedures extractor
            priority: Priority for procedure contributions
        """
        for proc in procedures:
            proc['activityType'] = 'procedure'
        
        self.contribute("procedures", procedures, priority=priority)
    
    def contribute_from_execution_model(
        self,
        repetitions: List[Dict[str, Any]],
        activity_map: Dict[str, str],
        priority: int = 25
    ) -> None:
        """
        Add execution model repetition data to activities.
        
        Args:
            repetitions: Repetition patterns from execution model
            activity_map: Map of activity names to IDs
            priority: Priority for execution model contributions
        """
        activities_with_timing = []
        
        for rep in repetitions:
            activity_ref = rep.get('activityRef', '')
            
            # Try to match to existing activity
            matched_id = None
            for name, aid in activity_map.items():
                if normalize_for_matching(activity_ref) in normalize_for_matching(name):
                    matched_id = aid
                    break
            
            if matched_id or activity_ref:
                activities_with_timing.append({
                    'id': matched_id or f'exec_{activity_ref}',
                    'name': activity_ref,
                    'repetitionId': rep.get('id'),
                    'timing': {
                        'frequency': rep.get('frequency'),
                        'interval': rep.get('interval'),
                        'count': rep.get('count'),
                    }
                })
        
        if activities_with_timing:
            self.contribute("execution", activities_with_timing, priority=priority)


# =============================================================================
# Pipeline Integration
# =============================================================================

def reconcile_activities_from_pipeline(
    soa_activities: List[Dict[str, Any]],
    procedure_activities: Optional[List[Dict[str, Any]]] = None,
    execution_repetitions: Optional[List[Dict[str, Any]]] = None,
    footnote_conditions: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Convenience function for pipeline integration.
    
    Args:
        soa_activities: Activities from SoA extraction
        procedure_activities: Activities from procedures extractor
        execution_repetitions: Repetition patterns from execution model
        footnote_conditions: Conditional footnotes for activities
    
    Returns:
        List of reconciled activity dictionaries
    """
    # Use exact matching (1.0) to prevent incorrect merging of SoA activities
    # SoA activities are authoritative and should not be merged with procedure activities
    reconciler = ActivityReconciler(match_threshold=1.0)
    
    if soa_activities:
        reconciler.contribute("soa", soa_activities, priority=10)
    
    if procedure_activities:
        reconciler.contribute_from_procedures(procedure_activities, priority=20)
    
    # Map activity names to IDs for execution model matching
    activity_map = {}
    if soa_activities:
        for act in soa_activities:
            activity_map[act.get('name', '')] = act.get('id', '')
    
    if execution_repetitions and activity_map:
        reconciler.contribute_from_execution_model(
            execution_repetitions, 
            activity_map, 
            priority=25
        )
    
    # Apply footnote conditions
    if footnote_conditions:
        conditional_activities = []
        for fn in footnote_conditions:
            if fn.get('activityId') or fn.get('activityName'):
                conditional_activities.append({
                    'id': fn.get('activityId'),
                    'name': fn.get('activityName', ''),
                    'isConditional': True,
                    'conditionText': fn.get('condition', fn.get('text')),
                })
        
        if conditional_activities:
            reconciler.contribute("footnotes", conditional_activities, priority=30)
    
    reconciled = reconciler.reconcile()
    return [activity.to_usdm_dict() for activity in reconciled]
