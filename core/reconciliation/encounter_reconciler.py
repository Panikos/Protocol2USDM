"""
Encounter Reconciliation

Reconciles encounter/visit data from multiple extraction sources (SoA, Scheduling,
Execution Model visit windows) into canonical encounters for protocol_usdm.json.
"""

import uuid
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from .base import (
    BaseReconciler,
    EntityContribution,
    ReconciledEntity,
    clean_entity_name,
    extract_footnote_refs,
    fuzzy_match_names,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Encounter Type Inference
# =============================================================================

ENCOUNTER_TYPE_CODES = {
    "screening": ("C98779", "Screening Visit"),
    "baseline": ("C142615", "Baseline Visit"),
    "randomization": ("C71738", "Randomization Visit"),
    "treatment": ("C98780", "Treatment Visit"),
    "follow-up": ("C98777", "Follow-up Visit"),
    "followup": ("C98777", "Follow-up Visit"),
    "end of study": ("C98780", "End of Study Visit"),
    "eos": ("C98780", "End of Study Visit"),
    "early termination": ("C98780", "Early Termination Visit"),
    "et": ("C98780", "Early Termination Visit"),
    "unscheduled": ("C98780", "Unscheduled Visit"),
}


def infer_encounter_type(name: str) -> tuple:
    """Infer CDISC encounter type code from encounter name."""
    name_lower = name.lower()
    
    for keyword, (code, decode) in ENCOUNTER_TYPE_CODES.items():
        if keyword in name_lower:
            return code, decode
    
    # Check for day patterns
    if re.search(r'day\s*[-]?\d+', name_lower):
        return "C98780", "Study Visit"
    if re.search(r'week\s*\d+', name_lower):
        return "C98780", "Study Visit"
    if re.search(r'visit\s*\d+', name_lower):
        return "C98780", "Study Visit"
    
    return "C98780", "Study Visit"


def extract_timing_from_name(name: str) -> Dict[str, Any]:
    """Extract timing information from encounter name."""
    timing = {}
    name_lower = name.lower()
    
    # Day pattern: "Day 1", "Day -14", "D1"
    day_match = re.search(r'day\s*([-]?\d+)|d([-]?\d+)', name_lower)
    if day_match:
        day_num = day_match.group(1) or day_match.group(2)
        timing['studyDay'] = int(day_num)
    
    # Week pattern: "Week 4", "Wk4"
    week_match = re.search(r'week\s*(\d+)|wk\s*(\d+)', name_lower)
    if week_match:
        week_num = week_match.group(1) or week_match.group(2)
        timing['studyWeek'] = int(week_num)
    
    # Month pattern: "Month 3"
    month_match = re.search(r'month\s*(\d+)', name_lower)
    if month_match:
        timing['studyMonth'] = int(month_match.group(1))
    
    return timing


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class EncounterContribution(EntityContribution):
    """Encounter contribution from an extraction source."""
    encounter_type: str = "visit"       # visit, phone, remote
    epoch_id: Optional[str] = None      # Which epoch this belongs to
    study_day: Optional[int] = None     # Study day (e.g., Day 1, Day -14)
    study_week: Optional[int] = None
    window_lower: Optional[int] = None  # Visit window in days
    window_upper: Optional[int] = None
    is_required: bool = True
    timing_label: Optional[str] = None  # Original timing string


@dataclass
class ReconciledEncounter(ReconciledEntity):
    """Reconciled encounter for protocol_usdm.json."""
    encounter_type: str = "visit"
    epoch_id: Optional[str] = None
    study_day: Optional[int] = None
    study_week: Optional[int] = None
    window_lower: Optional[int] = None
    window_upper: Optional[int] = None
    is_required: bool = True
    timing_label: Optional[str] = None
    cdisc_code: Optional[str] = None
    cdisc_decode: Optional[str] = None
    instance_type: str = "Encounter"
    
    def to_usdm_dict(self) -> Dict[str, Any]:
        """Convert to USDM-compliant dictionary."""
        result = self._base_usdm_dict()
        
        # Add CDISC type
        if self.cdisc_code:
            result["type"] = {
                "id": str(uuid.uuid4()),
                "code": self.cdisc_code,
                "codeSystem": "http://www.cdisc.org",
                "codeSystemVersion": "2024-09-27",
                "decode": self.cdisc_decode or "Study Visit",
                "instanceType": "Code"
            }
        
        # Add epoch reference
        if self.epoch_id:
            result["epochId"] = self.epoch_id
        
        # Build extension attributes
        extra_extensions = []
        
        # Encounter type
        extra_extensions.append({
            "id": str(uuid.uuid4()),
            "url": "https://protocol2usdm.io/extensions/x-encounterType",
            "instanceType": "ExtensionAttribute",
            "valueString": self.encounter_type
        })
        
        # Study day
        if self.study_day is not None:
            extra_extensions.append({
                "id": str(uuid.uuid4()),
                "url": "https://protocol2usdm.io/extensions/x-encounterStudyDay",
                "instanceType": "ExtensionAttribute",
                "valueInteger": self.study_day
            })
        
        # Study week
        if self.study_week is not None:
            extra_extensions.append({
                "id": str(uuid.uuid4()),
                "url": "https://protocol2usdm.io/extensions/x-encounterStudyWeek",
                "instanceType": "ExtensionAttribute",
                "valueInteger": self.study_week
            })
        
        # Visit window
        if self.window_lower is not None or self.window_upper is not None:
            window_str = f"{self.window_lower or 0}/{self.window_upper or 0}"
            extra_extensions.append({
                "id": str(uuid.uuid4()),
                "url": "https://protocol2usdm.io/extensions/x-encounterWindow",
                "instanceType": "ExtensionAttribute",
                "valueString": window_str
            })
        
        # Required flag
        if not self.is_required:
            extra_extensions.append({
                "id": str(uuid.uuid4()),
                "url": "https://protocol2usdm.io/extensions/x-encounterOptional",
                "instanceType": "ExtensionAttribute",
                "valueBoolean": True
            })
        
        # Timing label
        if self.timing_label:
            extra_extensions.append({
                "id": str(uuid.uuid4()),
                "url": "https://protocol2usdm.io/extensions/x-encounterTimingLabel",
                "instanceType": "ExtensionAttribute",
                "valueString": self.timing_label
            })
        
        self._add_extension_attributes(result, extra_extensions=extra_extensions)
        
        return result


# =============================================================================
# Encounter Reconciler
# =============================================================================

class EncounterReconciler(BaseReconciler[EncounterContribution, ReconciledEncounter]):
    """
    Reconciler for encounter/visit data from multiple sources.
    
    Priority order (default):
    - SoA: 10 (base encounters/timepoints)
    - Scheduling: 20 (detailed timing info)
    - Execution Model: 25 (visit windows, constraints)
    """
    
    def _create_contribution(
        self,
        source: str,
        entity: Dict[str, Any],
        index: int,
        priority: int,
        epoch_id: Optional[str] = None,
        **kwargs
    ) -> EncounterContribution:
        """Create encounter contribution from raw dict."""
        raw_name = entity.get('name', entity.get('label', f'Visit {index+1}'))
        canonical = clean_entity_name(raw_name)
        footnotes = extract_footnote_refs(raw_name)
        
        # Extract timing from name
        timing = extract_timing_from_name(canonical)
        
        # Get encounter type
        enc_type = entity.get('encounterType', 'visit')
        if not enc_type or enc_type == 'visit':
            # Check for phone/remote indicators
            name_lower = canonical.lower()
            if 'phone' in name_lower or 'call' in name_lower:
                enc_type = 'phone'
            elif 'remote' in name_lower or 'telehealth' in name_lower:
                enc_type = 'remote'
        
        return EncounterContribution(
            source=source,
            entity_id=entity.get('id', f'{source}_encounter_{index+1}'),
            raw_name=raw_name,
            canonical_name=canonical,
            priority=priority,
            metadata={
                'footnoteRefs': footnotes,
                'originalIndex': index,
                **{k: v for k, v in entity.items() 
                   if k not in ['id', 'name', 'encounterType', 'epochId']}
            },
            encounter_type=enc_type,
            epoch_id=entity.get('epochId') or epoch_id,
            study_day=entity.get('studyDay') or timing.get('studyDay'),
            study_week=entity.get('studyWeek') or timing.get('studyWeek'),
            window_lower=entity.get('windowLower'),
            window_upper=entity.get('windowUpper'),
            is_required=entity.get('isRequired', True),
            timing_label=entity.get('timing', entity.get('timingLabel')),
        )
    
    def _reconcile_entity(
        self,
        canonical_name: str,
        contributions: List[EncounterContribution]
    ) -> ReconciledEncounter:
        """Reconcile multiple encounter contributions."""
        # Sort by priority (highest first)
        contributions.sort(key=lambda c: -c.priority)
        primary = contributions[0]
        
        # Get best epoch ID (prefer non-None)
        epoch_id = None
        for c in contributions:
            if c.epoch_id:
                epoch_id = c.epoch_id
                break
        
        # Get best study day (prefer specific values)
        study_day = None
        for c in contributions:
            if c.study_day is not None:
                study_day = c.study_day
                break
        
        study_week = None
        for c in contributions:
            if c.study_week is not None:
                study_week = c.study_week
                break
        
        # Get visit window (prefer specific values)
        window_lower = None
        window_upper = None
        for c in contributions:
            if c.window_lower is not None:
                window_lower = c.window_lower
                window_upper = c.window_upper
                break
        
        # Is required (if any source says optional, mark as not required)
        is_required = all(c.is_required for c in contributions)
        
        # Get timing label
        timing_label = None
        for c in contributions:
            if c.timing_label:
                timing_label = c.timing_label
                break
        
        # Infer CDISC type
        cdisc_code, cdisc_decode = infer_encounter_type(canonical_name)
        
        return ReconciledEncounter(
            id=self._get_best_id(contributions, "encounter"),
            name=canonical_name,
            raw_name=primary.raw_name,
            sources=self._collect_sources(contributions),
            footnote_refs=self._collect_footnotes(contributions),
            encounter_type=primary.encounter_type,
            epoch_id=epoch_id,
            study_day=study_day,
            study_week=study_week,
            window_lower=window_lower,
            window_upper=window_upper,
            is_required=is_required,
            timing_label=timing_label,
            cdisc_code=cdisc_code,
            cdisc_decode=cdisc_decode,
        )
    
    def _post_reconcile(self, reconciled: List[ReconciledEncounter]) -> List[ReconciledEncounter]:
        """Sort encounters by study day/week."""
        def sort_key(e):
            # Sort by study day if available, then by week, then by name
            day = e.study_day if e.study_day is not None else 9999
            week = e.study_week if e.study_week is not None else 9999
            return (day, week, e.name)
        
        reconciled.sort(key=sort_key)
        return reconciled
    
    def contribute_from_visit_windows(
        self,
        visit_windows: List[Dict[str, Any]],
        encounter_map: Dict[str, str],
        priority: int = 25
    ) -> None:
        """
        Add visit window data from execution model.
        
        Args:
            visit_windows: Visit windows from execution model
            encounter_map: Map of encounter names to IDs
            priority: Priority for execution model contributions
        """
        encounters_with_windows = []
        
        for vw in visit_windows:
            visit_ref = vw.get('visitRef', vw.get('encounterRef', ''))
            
            # Try to match to existing encounter
            matched_id = None
            for name, eid in encounter_map.items():
                if fuzzy_match_names(visit_ref, name, threshold=0.8):
                    matched_id = eid
                    break
            
            target_day = vw.get('targetDay', vw.get('studyDay'))
            
            encounters_with_windows.append({
                'id': matched_id or f'exec_{visit_ref}',
                'name': visit_ref or f"Day {target_day}" if target_day else 'Visit',
                'studyDay': target_day,
                'windowLower': vw.get('windowLower', vw.get('minusWindow')),
                'windowUpper': vw.get('windowUpper', vw.get('plusWindow')),
                'timing': vw.get('timing'),
            })
        
        if encounters_with_windows:
            self.contribute("execution", encounters_with_windows, priority=priority)


# =============================================================================
# Pipeline Integration
# =============================================================================

def reconcile_encounters_from_pipeline(
    soa_encounters: List[Dict[str, Any]],
    scheduling_encounters: Optional[List[Dict[str, Any]]] = None,
    visit_windows: Optional[List[Dict[str, Any]]] = None,
    epoch_map: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """
    Convenience function for pipeline integration.
    
    Args:
        soa_encounters: Encounters from SoA extraction
        scheduling_encounters: Encounters from scheduling extractor
        visit_windows: Visit windows from execution model
        epoch_map: Map of encounter IDs to epoch IDs
    
    Returns:
        List of reconciled encounter dictionaries
    """
    reconciler = EncounterReconciler()
    
    # Add epoch IDs to SoA encounters if map provided
    if soa_encounters:
        if epoch_map:
            for enc in soa_encounters:
                enc_id = enc.get('id')
                if enc_id and enc_id in epoch_map:
                    enc['epochId'] = epoch_map[enc_id]
        reconciler.contribute("soa", soa_encounters, priority=10)
    
    if scheduling_encounters:
        reconciler.contribute("scheduling", scheduling_encounters, priority=20)
    
    # Map encounter names to IDs for visit window matching
    encounter_map = {}
    if soa_encounters:
        for enc in soa_encounters:
            encounter_map[enc.get('name', '')] = enc.get('id', '')
    
    if visit_windows and encounter_map:
        reconciler.contribute_from_visit_windows(visit_windows, encounter_map, priority=25)
    
    reconciled = reconciler.reconcile()
    return [encounter.to_usdm_dict() for encounter in reconciled]
