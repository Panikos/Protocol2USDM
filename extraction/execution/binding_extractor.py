"""
Binding Extractor - Fix A and Fix B implementations

Fix A: Extracts operationalized titration schedules with day-bounded dose levels
Fix B: Creates instance bindings that link repetitions to ScheduledActivityInstances

This addresses the feedback:
- "Dose titration is described, but not operationalized"
- "You created repetition rules, but didn't bind them to scheduled instances"
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple

from .schema import (
    TitrationDoseLevel, DoseTitrationSchedule, InstanceBinding,
    Repetition, RepetitionType, ExecutionModelData, ExecutionModelResult
)

logger = logging.getLogger(__name__)


# =============================================================================
# FIX A: TITRATION SCHEDULE EXTRACTION
# =============================================================================

# Patterns for detecting titration schedules
TITRATION_PATTERNS = [
    # "15 mg/day for approximately 28 days then 30 mg/day"
    (r'(\d+)\s*mg(?:/day)?\s+(?:for\s+)?(?:approximately\s+)?(\d+)\s*days?\s*(?:,?\s*(?:then|followed\s+by).*?)(\d+)\s*mg', 'escalation'),
    # "15 mg/day ... followed by ... titration to 30 mg/day starting on Day 29"
    (r'(\d+)\s*mg(?:/day)?.*?(?:approximately|about)?\s*(\d+)\s*days?.*?(?:titration|titrate|followed\s+by).*?(\d+)\s*mg', 'escalation'),
    # "starting dose of 15 mg, escalate to 30 mg on Day 29"
    (r'starting\s+dose\s+(?:of\s+)?(\d+)\s*mg.*?(?:escalate|increase)\s+to\s+(\d+)\s*mg\s+(?:on\s+)?day\s+(\d+)', 'escalation'),
    # "Day 1-28: 15 mg, Day 29+: 30 mg"
    (r'day\s*(\d+)[-–](\d+)\s*:\s*(\d+)\s*mg.*?day\s*(\d+)\+?\s*:\s*(\d+)\s*mg', 'escalation'),
    # "titrate from 15 mg to 30 mg"
    (r'titrat(?:e|ion)\s+from\s+(\d+)\s*mg\s+to\s+(\d+)\s*mg', 'escalation'),
]

# Patterns for dose level day bounds
DOSE_DAY_PATTERNS = [
    (r'(\d+)\s*mg(?:/day)?\s+(?:from\s+)?day\s*(\d+)\s*(?:to|through|[-–])\s*(?:day\s*)?(\d+)', 'bounded'),
    (r'(\d+)\s*mg(?:/day)?\s+(?:starting\s+)?(?:on\s+)?day\s*(\d+)', 'start_only'),
    (r'day\s*(\d+)[-–](\d+)\s*[:\-]?\s*(\d+)\s*mg', 'day_range'),
]


def _extract_titration_from_text(text: str) -> List[DoseTitrationSchedule]:
    """Extract titration schedules from protocol text."""
    schedules = []
    text_lower = text.lower()
    
    # Look for titration indicators - expanded to catch more patterns
    titration_indicators = [
        'titrat', 'escalat', 'dose adjustment', 'dose increase',
        'then', 'followed by', 'switch to', 'increase to', 'from day'
    ]
    if not any(kw in text_lower for kw in titration_indicators):
        return schedules
    
    for pattern, ttype in TITRATION_PATTERNS:
        matches = re.finditer(pattern, text_lower, re.IGNORECASE)
        
        for match in matches:
            groups = match.groups()
            dose_levels = []
            
            if len(groups) >= 3:
                if ttype == 'escalation':
                    # Pattern: start_dose, duration, end_dose
                    try:
                        start_dose = int(groups[0])
                        duration = int(groups[1]) if groups[1].isdigit() else 28
                        end_dose = int(groups[2])
                        
                        dose_levels.append(TitrationDoseLevel(
                            dose_value=f"{start_dose} mg",
                            start_day=1,
                            end_day=duration,
                            source_text=match.group(),
                        ))
                        
                        dose_levels.append(TitrationDoseLevel(
                            dose_value=f"{end_dose} mg",
                            start_day=duration + 1,
                            requires_prior_dose=f"{start_dose} mg",
                            transition_rule=f"After {duration} days on {start_dose} mg",
                            source_text=match.group(),
                        ))
                    except (ValueError, IndexError):
                        continue
            
            if dose_levels:
                schedules.append(DoseTitrationSchedule(
                    id=f"titration_{len(schedules)+1}",
                    dose_levels=dose_levels,
                    titration_type=ttype,
                    source_text=match.group()[:200],
                ))
    
    return schedules


def extract_titration_from_arm(arm_data: Dict[str, Any]) -> Optional[DoseTitrationSchedule]:
    """
    Extract titration schedule from a StudyArm description.
    
    This is called during USDM enrichment to operationalize titration
    described in arm text.
    """
    description = arm_data.get('description', '')
    name = arm_data.get('name', '')
    
    # Check for titration indicators
    if not any(kw in description.lower() for kw in ['titrat', 'escalat', 'mg', 'dose']):
        return None
    
    schedules = _extract_titration_from_text(description)
    if schedules:
        schedule = schedules[0]
        schedule.intervention_name = name
        return schedule
    
    return None


# =============================================================================
# FIX B: INSTANCE BINDING CREATION
# =============================================================================

# Activity patterns that need binding
BINDABLE_ACTIVITIES = [
    ('urine', ['24-hour urine', '24h urine', 'urine collection', 'urinalysis']),
    ('feces', ['feces', 'stool', 'fecal']),
    ('meal', ['controlled meal', 'standardized meal', 'controlled diet']),
    ('pk_sample', ['pk sample', 'pharmacokinetic', 'blood sample for pk']),
    ('vital', ['vital signs', 'blood pressure', 'heart rate', 'temperature']),
    ('ecg', ['ecg', 'electrocardiogram', '12-lead']),
]


def create_instance_bindings(
    scheduled_instances: List[Dict[str, Any]],
    repetitions: List[Repetition],
    encounters: List[Dict[str, Any]],
) -> List[InstanceBinding]:
    """
    FIX B: Create bindings between ScheduledActivityInstances and repetition rules.
    
    This is the "highest ROI improvement" per feedback - it connects the
    repetition rules to actual scheduled instances so generators know
    exactly how to instantiate daily collections.
    
    Args:
        scheduled_instances: List of ScheduledActivityInstance from USDM
        repetitions: List of extracted Repetition rules
        encounters: List of Encounters from USDM
        
    Returns:
        List of InstanceBinding objects
    """
    bindings = []
    
    # Build encounter lookup for day ranges
    encounter_days = {}
    for enc in encounters:
        enc_id = enc.get('id', '')
        enc_name = enc.get('name', '').lower()
        
        # Parse day range from encounter name
        day_match = re.search(r'day\s*([-–]?\d+)(?:\s*(?:to|through|[-–])\s*([-–]?\d+))?', enc_name)
        if day_match:
            start = int(day_match.group(1).replace('–', '-'))
            end = int(day_match.group(2).replace('–', '-')) if day_match.group(2) else start
            encounter_days[enc_id] = (start, end)
    
    # Build repetition lookup by type and characteristics
    daily_repetitions = [r for r in repetitions if r.type == RepetitionType.DAILY]
    
    # Process each scheduled instance
    for instance in scheduled_instances:
        instance_id = instance.get('id', '')
        activity_ids = instance.get('activityIds', [])
        encounter_id = instance.get('encounterId', '')
        
        # Get activity name if available
        activity_name = ''
        if 'activity' in instance:
            activity_name = instance['activity'].get('name', '').lower()
        
        # Determine if this activity needs binding
        activity_type = None
        for atype, keywords in BINDABLE_ACTIVITIES:
            if any(kw in activity_name for kw in keywords):
                activity_type = atype
                break
        
        if not activity_type:
            continue
        
        # Get encounter day range
        day_range = encounter_days.get(encounter_id, (None, None))
        start_day, end_day = day_range
        
        # Find matching repetition rule
        matching_rep = None
        for rep in daily_repetitions:
            # Match by activity type in source text
            if activity_type in (rep.source_text or '').lower():
                matching_rep = rep
                break
        
        # Create binding
        expected_count = None
        if start_day is not None and end_day is not None:
            expected_count = abs(end_day - start_day) + 1
        
        binding = InstanceBinding(
            id=f"binding_{len(bindings)+1}",
            instance_id=instance_id,
            activity_id=activity_ids[0] if activity_ids else None,
            activity_name=activity_name,
            repetition_id=matching_rep.id if matching_rep else None,
            encounter_id=encounter_id,
            expected_count=expected_count,
            start_offset=f"P{start_day}D" if start_day and start_day >= 0 else f"-P{abs(start_day)}D" if start_day else None,
            end_offset=f"P{end_day}D" if end_day and end_day >= 0 else f"-P{abs(end_day)}D" if end_day else None,
        )
        
        # Set collection boundary for 24h collections
        if activity_type in ('urine', 'feces'):
            binding.collection_boundary = "morning-to-morning"
        
        bindings.append(binding)
    
    return bindings


def create_instance_bindings_from_usdm(
    usdm_data: Dict[str, Any],
    execution_data: ExecutionModelData,
) -> List[InstanceBinding]:
    """
    Create instance bindings by traversing USDM structure.
    
    This is called during pipeline integration to bind repetitions
    to the actual scheduled instances in the USDM output.
    """
    bindings = []
    
    # Navigate to study designs
    study_designs = []
    if 'studyDesigns' in usdm_data:
        study_designs = usdm_data['studyDesigns']
    elif 'study' in usdm_data and 'versions' in usdm_data['study']:
        for version in usdm_data['study']['versions']:
            study_designs.extend(version.get('studyDesigns', []))
    
    for design in study_designs:
        # Get encounters
        encounters = design.get('encounters', [])
        
        # Get scheduled instances from activities
        scheduled_instances = []
        for activity in design.get('activities', []):
            for instance in activity.get('scheduledActivityInstances', []):
                instance['activity'] = activity  # Attach parent for context
                scheduled_instances.append(instance)
        
        # Also check scheduledActivityInstances at design level
        scheduled_instances.extend(design.get('scheduledActivityInstances', []))
        
        # Create bindings
        design_bindings = create_instance_bindings(
            scheduled_instances=scheduled_instances,
            repetitions=execution_data.repetitions,
            encounters=encounters,
        )
        bindings.extend(design_bindings)
    
    return bindings


# =============================================================================
# FIX C: STRUCTURAL INTEGRITY - Dedupe epochs, fix visit windows
# =============================================================================

def deduplicate_epochs(epochs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    FIX C: Remove duplicate epochs by ID.
    
    Addresses feedback: "You have 'End of Study' duplicated with the same 
    epoch ID in the epoch list (this is a structural integrity bug)"
    """
    seen_ids = set()
    deduped = []
    
    for epoch in epochs:
        epoch_id = epoch.get('id', '')
        if epoch_id not in seen_ids:
            seen_ids.add(epoch_id)
            deduped.append(epoch)
        else:
            logger.warning(f"Removed duplicate epoch: {epoch_id}")
    
    return deduped


def deduplicate_visit_windows(visit_windows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    FIX 5: Collapse duplicate visit windows (e.g., multiple EOS definitions).
    
    Keeps the window with the most specific/reasonable targetDay.
    """
    # Group by normalized name
    name_groups: Dict[str, List[Dict[str, Any]]] = {}
    
    for vw in visit_windows:
        vw_name = vw.get('visitName', vw.get('name', '')).lower()
        # Normalize common variations
        normalized = vw_name
        for pattern, canonical in [
            (r'end\s*of\s*study', 'eos'),
            (r'e\.?o\.?s\.?', 'eos'),
            (r'early\s*termination', 'et'),
            (r'e\.?t\.?', 'et'),
            (r'screen(?:ing)?', 'screening'),
            (r'base\s*line', 'baseline'),
        ]:
            if re.search(pattern, normalized):
                normalized = canonical
                break
        
        if normalized not in name_groups:
            name_groups[normalized] = []
        name_groups[normalized].append(vw)
    
    # Collapse duplicates - keep the one with most reasonable targetDay
    deduped = []
    for name, windows in name_groups.items():
        if len(windows) == 1:
            deduped.append(windows[0])
        else:
            # Multiple definitions - pick the best one
            # Prefer: highest targetDay for EOS, lowest for screening
            if name in ('eos', 'et'):
                # For EOS, higher day is more likely correct
                best = max(windows, key=lambda w: w.get('targetDay', 0) or 0)
            elif name in ('screening', 'baseline'):
                # For screening/baseline, lower (or negative) day is more likely
                best = min(windows, key=lambda w: w.get('targetDay', 999) or 999)
            else:
                # Default: keep first
                best = windows[0]
            
            logger.info(f"Collapsed {len(windows)} duplicate '{name}' visit windows -> targetDay={best.get('targetDay')}")
            deduped.append(best)
    
    return deduped


def fix_visit_window_targets(
    visit_windows: List[Dict[str, Any]], 
    encounters: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    FIX C: Correct visit window targets to match encounter definitions.
    
    Addresses feedback: "Visit window extraction looks wrong - EOS shows 
    a targetDay that doesn't look consistent with EOS Day 54+/-2"
    """
    # Build encounter lookup
    encounter_days = {}
    for enc in encounters:
        enc_name = enc.get('name', '').lower()
        
        # Extract day from encounter name
        day_match = re.search(r'day\s*(\d+)', enc_name)
        if day_match:
            target_day = int(day_match.group(1))
            
            # Extract window if present
            window_match = re.search(r'[±+-]\s*(\d+)', enc.get('name', ''))
            window = int(window_match.group(1)) if window_match else None
            
            # Use short name as key
            for key in ['eos', 'end of study', 'screening', 'baseline', 'follow-up']:
                if key in enc_name:
                    encounter_days[key] = (target_day, window)
                    break
    
    # Fix visit windows
    for vw in visit_windows:
        vw_name = vw.get('name', '').lower()
        
        for key, (target_day, window) in encounter_days.items():
            if key in vw_name:
                # Update target day if different
                current_target = vw.get('targetDay')
                if current_target != target_day:
                    logger.info(f"Fixed {vw.get('name')} targetDay: {current_target} -> {target_day}")
                    vw['targetDay'] = target_day
                
                if window is not None:
                    vw['windowBefore'] = window
                    vw['windowAfter'] = window
                break
    
    return visit_windows


# =============================================================================
# MAIN EXTRACTION FUNCTION
# =============================================================================

def extract_bindings_and_titration(
    pdf_path: str,
    model: str = "gemini-2.5-pro",
    usdm_data: Optional[Dict[str, Any]] = None,
    execution_data: Optional[ExecutionModelData] = None,
) -> ExecutionModelResult:
    """
    Extract titration schedules and create instance bindings.
    
    This should be called after initial extraction to add the
    operationalized titration and binding data.
    """
    from core.pdf_utils import extract_text_from_pages, get_page_count
    
    logger.info("Starting binding and titration extraction...")
    
    titration_schedules = []
    instance_bindings = []
    
    # Extract titration from PDF text
    try:
        # Get pages with dosing info
        pages = list(range(min(30, get_page_count(pdf_path))))
        text = extract_text_from_pages(pdf_path, pages)
        
        titration_schedules = _extract_titration_from_text(text)
        logger.info(f"  Extracted {len(titration_schedules)} titration schedules from PDF")
    except Exception as e:
        logger.warning(f"Titration extraction failed: {e}")
    
    # Create instance bindings from USDM
    if usdm_data and execution_data:
        instance_bindings = create_instance_bindings_from_usdm(usdm_data, execution_data)
        logger.info(f"  Created {len(instance_bindings)} instance bindings")
    
    data = ExecutionModelData(
        titration_schedules=titration_schedules,
        instance_bindings=instance_bindings,
    )
    
    return ExecutionModelResult(
        success=len(titration_schedules) > 0 or len(instance_bindings) > 0,
        data=data,
        pages_used=pages if 'pages' in dir() else [],
        model_used="heuristic",
    )
