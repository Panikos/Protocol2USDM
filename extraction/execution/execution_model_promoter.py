"""
Execution Model Promoter - Materializes execution findings into core USDM.

This module addresses the gap where execution model data (anchors, repetitions,
dosing regimens) is extracted but stored only in extensions. Downstream consumers
(synthetic generators) need this data in core USDM structures.

Architecture:
    Execution Model Data (extensions)
              ↓
    ExecutionModelPromoter
              ↓
    Core USDM Entities:
      - ScheduledActivityInstance (for anchors)
      - ScheduledActivityInstance (for repetitions)  
      - Administration (for dosing regimens)
      - Timing (with valid relativeFromScheduledInstanceId)

Key Contract:
    Extensions are OPTIONAL/DEBUG. Core USDM must be self-sufficient.
"""

import logging
import uuid
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class PromotionResult:
    """Result of execution model promotion."""
    anchors_created: int = 0
    instances_created: int = 0
    administrations_created: int = 0
    references_fixed: int = 0
    issues: List[Dict[str, Any]] = field(default_factory=list)


class ExecutionModelPromoter:
    """
    Promotes execution model findings from extensions into core USDM entities.
    
    Ensures that downstream consumers can use core USDM without parsing extensions.
    """
    
    def __init__(self):
        self._anchor_instance_map: Dict[str, str] = {}  # anchor_id → instance_id
        self._repetition_instance_map: Dict[str, List[str]] = {}  # rep_id → [instance_ids]
        self._administration_map: Dict[str, str] = {}  # regimen_id → administration_id
        self.result = PromotionResult()
    
    def promote(
        self,
        usdm_design: Dict[str, Any],
        study_version: Dict[str, Any],
        execution_data: Any,  # ExecutionModelData
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Main promotion entry point.
        
        Args:
            usdm_design: The study design to enrich
            study_version: The study version (for administrableProducts, etc.)
            execution_data: Extracted execution model data
            
        Returns:
            Tuple of (enriched_design, enriched_version)
        """
        logger.info("Starting execution model promotion to core USDM...")
        
        # Step 1: Promote time anchors → ScheduledActivityInstances
        if execution_data.time_anchors:
            usdm_design = self._promote_time_anchors(
                usdm_design, execution_data.time_anchors
            )
        
        # Step 2: Expand repetitions → ScheduledActivityInstances
        if execution_data.repetitions:
            usdm_design = self._promote_repetitions(
                usdm_design, execution_data.repetitions
            )
        
        # Step 3: Promote dosing regimens → Administration entities
        if execution_data.dosing_regimens:
            study_version = self._promote_dosing_regimens(
                usdm_design, study_version, execution_data.dosing_regimens
            )
        
        # Step 4: Fix dangling references in timings
        usdm_design = self._fix_timing_references(usdm_design)
        
        # Step 5: Promote footnote conditions to activity notes (already done elsewhere, verify)
        
        logger.info(
            f"Promotion complete: {self.result.anchors_created} anchors, "
            f"{self.result.instances_created} instances, "
            f"{self.result.administrations_created} administrations, "
            f"{self.result.references_fixed} refs fixed"
        )
        
        return usdm_design, study_version
    
    def _promote_time_anchors(
        self,
        design: Dict[str, Any],
        time_anchors: List[Any]
    ) -> Dict[str, Any]:
        """
        Promote time anchors to concrete ScheduledActivityInstances.
        
        Time anchors (First Dose, Randomization, etc.) need to exist as
        actual instances so that Timing.relativeFromScheduledInstanceId
        can reference them.
        """
        # Get or create the main schedule timeline
        timelines = design.setdefault('scheduleTimelines', [])
        if not timelines:
            main_timeline = self._create_main_timeline()
            timelines.append(main_timeline)
        else:
            main_timeline = timelines[0]
        
        instances = main_timeline.setdefault('instances', [])
        existing_instance_ids = {inst.get('id') for inst in instances}
        
        # Track anchor names to avoid duplicates
        existing_anchor_names = set()
        for inst in instances:
            name = inst.get('name', '').lower()
            if 'anchor' in inst.get('instanceType', '').lower() or \
               any(kw in name for kw in ['first dose', 'randomization', 'baseline', 'screening']):
                existing_anchor_names.add(name)
        
        # Find or create anchor encounter
        anchor_encounter_id = self._find_or_create_anchor_encounter(design)
        
        for anchor in time_anchors:
            # Get anchor name, handling AnchorType enum
            anchor_name = getattr(anchor, 'name', '')
            if not anchor_name:
                anchor_type = getattr(anchor, 'anchor_type', 'Anchor')
                # Handle enum types by getting their value
                anchor_name = anchor_type.value if hasattr(anchor_type, 'value') else str(anchor_type)
            anchor_id = getattr(anchor, 'id', str(uuid.uuid4()))
            
            # Skip if similar anchor already exists
            if anchor_name.lower() in existing_anchor_names:
                # Map to existing
                for inst in instances:
                    if anchor_name.lower() in inst.get('name', '').lower():
                        self._anchor_instance_map[anchor_id] = inst['id']
                        break
                continue
            
            # Create anchor instance
            instance_id = f"anchor_inst_{anchor_id}"
            anchor_instance = {
                "id": instance_id,
                "name": f"Anchor: {anchor_name}",
                "description": f"Time anchor for scheduling: {anchor_name}",
                "encounterId": anchor_encounter_id,
                "epochId": self._find_first_treatment_epoch_id(design),
                "activityIds": [],  # Anchors may not have activities
                "instanceType": "ScheduledActivityInstance",
            }
            
            # Add day value if available
            day_value = getattr(anchor, 'day_value', None)
            if day_value is not None:
                anchor_instance["scheduledDay"] = day_value
            
            instances.append(anchor_instance)
            self._anchor_instance_map[anchor_id] = instance_id
            existing_anchor_names.add(anchor_name.lower())
            self.result.anchors_created += 1
            
            logger.info(f"  Created anchor instance: {anchor_name} → {instance_id}")
        
        return design
    
    def _promote_repetitions(
        self,
        design: Dict[str, Any],
        repetitions: List[Any]
    ) -> Dict[str, Any]:
        """
        Expand repetitions into scheduled activity instances.
        
        For each repetition (e.g., "Daily dosing Days 1-14"), create
        concrete ScheduledActivityInstance entries for each occurrence.
        
        This enables synthetic generators to see the actual schedule.
        """
        timelines = design.get('scheduleTimelines', [])
        if not timelines:
            return design
        
        main_timeline = timelines[0]
        instances = main_timeline.setdefault('instances', [])
        
        # Get activity map for binding
        activities = {a.get('id'): a for a in design.get('activities', [])}
        encounters = design.get('encounters', [])
        encounter_by_day = self._build_encounter_by_day_map(encounters)
        
        for rep in repetitions:
            rep_id = getattr(rep, 'id', str(uuid.uuid4()))
            rep_type = getattr(rep, 'repetition_type', 'Unknown')
            activity_name = getattr(rep, 'activity_name', '')
            start_offset = getattr(rep, 'start_day_offset', 1)
            end_offset = getattr(rep, 'end_day_offset', start_offset)
            interval = getattr(rep, 'interval_days', 1)
            
            # Find matching activity
            activity_id = self._find_activity_by_name(design, activity_name)
            if not activity_id:
                continue  # Can't bind without activity
            
            # Calculate occurrence days
            if rep_type == 'Daily':
                interval = 1
            elif rep_type == 'Weekly':
                interval = 7
            elif rep_type == 'Continuous':
                # For continuous, just mark start and end
                interval = max(1, end_offset - start_offset)
            
            # Generate instances for each day
            created_instances = []
            day = start_offset
            while day <= end_offset:
                # Find or create encounter for this day
                encounter_id = encounter_by_day.get(day)
                if not encounter_id:
                    # Skip days without encounters (might be windows)
                    day += interval
                    continue
                
                instance_id = f"rep_{rep_id}_day_{day}"
                
                # Check if similar instance already exists
                exists = any(
                    inst.get('activityIds') and activity_id in inst.get('activityIds', []) and
                    inst.get('encounterId') == encounter_id
                    for inst in instances
                )
                
                if not exists:
                    instance = {
                        "id": instance_id,
                        "name": f"{activity_name} @ Day {day}",
                        "activityIds": [activity_id],
                        "encounterId": encounter_id,
                        "scheduledDay": day,
                        "instanceType": "ScheduledActivityInstance",
                    }
                    instances.append(instance)
                    created_instances.append(instance_id)
                    self.result.instances_created += 1
                
                day += interval
            
            if created_instances:
                self._repetition_instance_map[rep_id] = created_instances
                logger.info(f"  Expanded repetition '{activity_name}': {len(created_instances)} instances")
        
        return design
    
    def _promote_dosing_regimens(
        self,
        design: Dict[str, Any],
        version: Dict[str, Any],
        dosing_regimens: List[Any]
    ) -> Dict[str, Any]:
        """
        Promote dosing regimens to Administration entities.
        
        Creates proper USDM Administration objects and links them
        to StudyInterventions.
        """
        interventions = version.get('studyInterventions', [])
        intervention_by_name = {
            i.get('name', '').lower(): i for i in interventions
        }
        
        administrations = version.setdefault('administrations', [])
        existing_admin_ids = {a.get('id') for a in administrations}
        
        for regimen in dosing_regimens:
            regimen_id = getattr(regimen, 'id', str(uuid.uuid4()))
            treatment_name = getattr(regimen, 'treatment_name', '')
            dose = getattr(regimen, 'dose', '')
            route = getattr(regimen, 'route', '')
            frequency = getattr(regimen, 'frequency', '')
            
            # Skip prose fragments
            if self._is_prose_fragment(treatment_name):
                continue
            
            # Find matching intervention
            intervention = self._find_matching_intervention(
                treatment_name, intervention_by_name
            )
            
            # Create Administration entity
            admin_id = f"admin_{regimen_id}"
            if admin_id in existing_admin_ids:
                continue
            
            administration = {
                "id": admin_id,
                "name": f"Administration of {treatment_name}" if treatment_name else "Study Drug Administration",
                "description": f"{dose} {route} {frequency}".strip(),
                "instanceType": "Administration",
            }
            
            # Add dose if parseable
            if dose:
                dose_match = re.match(r'(\d+(?:\.\d+)?)\s*(\w+)?', dose)
                if dose_match:
                    administration["doseValue"] = float(dose_match.group(1))
                    if dose_match.group(2):
                        administration["doseUnit"] = {
                            "id": str(uuid.uuid4()),
                            "code": dose_match.group(2),
                            "decode": dose_match.group(2),
                            "instanceType": "Code"
                        }
            
            # Add route if available
            if route:
                route_code = self._get_route_code(route)
                administration["route"] = route_code
            
            administrations.append(administration)
            self._administration_map[regimen_id] = admin_id
            self.result.administrations_created += 1
            
            # Link to intervention
            if intervention:
                intervention.setdefault('administrationIds', []).append(admin_id)
                logger.info(f"  Created administration: {treatment_name} → {intervention.get('name')}")
            else:
                logger.info(f"  Created unlinked administration: {treatment_name}")
        
        return version
    
    def _fix_timing_references(self, design: Dict[str, Any]) -> Dict[str, Any]:
        """
        Post-pass to fix dangling relativeFromScheduledInstanceId references.
        
        For each Timing with a relativeFromScheduledInstanceId, verify that
        the referenced instance exists. If not, either:
        1. Create the missing anchor instance, or
        2. Remap to the closest existing instance
        """
        timelines = design.get('scheduleTimelines', [])
        if not timelines:
            return design
        
        main_timeline = timelines[0]
        instances = main_timeline.get('instances', [])
        existing_instance_ids = {inst.get('id') for inst in instances}
        
        timings = main_timeline.get('timings', [])
        
        # Also check root-level timings
        if design.get('timings'):
            timings = timings + design.get('timings', [])
        
        for timing in timings:
            ref_id = timing.get('relativeFromScheduledInstanceId')
            if not ref_id:
                continue
            
            if ref_id not in existing_instance_ids:
                # Check if we have a mapping from anchor promotion
                if ref_id in self._anchor_instance_map:
                    new_ref = self._anchor_instance_map[ref_id]
                    timing['relativeFromScheduledInstanceId'] = new_ref
                    self.result.references_fixed += 1
                    continue
                
                # Try to find closest match by name
                timing_name = timing.get('name', '')
                best_match = self._find_best_matching_instance(
                    timing_name, instances
                )
                
                if best_match:
                    timing['relativeFromScheduledInstanceId'] = best_match
                    self.result.references_fixed += 1
                    self.result.issues.append({
                        "severity": "warning",
                        "category": "timing_reference_remapped",
                        "message": f"Timing '{timing_name}' reference remapped: {ref_id} → {best_match}",
                        "affectedPath": f"$.timings[?(@.id=='{timing.get('id')}')]"
                    })
                else:
                    # Create missing anchor instance
                    anchor_instance = {
                        "id": ref_id,
                        "name": f"Auto-anchor for {timing_name}",
                        "activityIds": [],
                        "instanceType": "ScheduledActivityInstance",
                    }
                    instances.append(anchor_instance)
                    existing_instance_ids.add(ref_id)
                    self.result.anchors_created += 1
                    self.result.issues.append({
                        "severity": "info",
                        "category": "anchor_auto_created",
                        "message": f"Created anchor instance for missing reference: {ref_id}",
                        "affectedPath": f"$.scheduleTimelines[0].instances[-1]"
                    })
        
        return design
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _create_main_timeline(self) -> Dict[str, Any]:
        """Create main schedule timeline if missing."""
        return {
            "id": f"timeline_{uuid.uuid4()}",
            "name": "Main Study Timeline",
            "instances": [],
            "timings": [],
            "instanceType": "ScheduleTimeline"
        }
    
    def _find_or_create_anchor_encounter(self, design: Dict[str, Any]) -> str:
        """Find or create an encounter for anchor instances."""
        encounters = design.get('encounters', [])
        
        # Look for Day 1 or Baseline encounter
        for enc in encounters:
            name = enc.get('name', '').lower()
            if 'day 1' in name or 'baseline' in name or 'first' in name:
                return enc['id']
        
        # Use first treatment encounter
        for enc in encounters:
            name = enc.get('name', '').lower()
            if 'screen' not in name:
                return enc['id']
        
        # Fallback to first encounter
        if encounters:
            return encounters[0]['id']
        
        # Create placeholder
        anchor_enc = {
            "id": f"enc_anchor_{uuid.uuid4()}",
            "name": "Anchor Reference Point",
            "instanceType": "Encounter"
        }
        design.setdefault('encounters', []).append(anchor_enc)
        return anchor_enc['id']
    
    def _find_first_treatment_epoch_id(self, design: Dict[str, Any]) -> Optional[str]:
        """Find the first treatment epoch ID."""
        for epoch in design.get('epochs', []):
            name = epoch.get('name', '').lower()
            if any(kw in name for kw in ['treatment', 'period 1', 'day 1', 'inpatient']):
                return epoch['id']
        
        # Skip screening, use first non-screening
        for epoch in design.get('epochs', []):
            if 'screen' not in epoch.get('name', '').lower():
                return epoch['id']
        
        if design.get('epochs'):
            return design['epochs'][0]['id']
        
        return None
    
    def _build_encounter_by_day_map(self, encounters: List[Dict]) -> Dict[int, str]:
        """Build a map of day number → encounter ID."""
        day_map = {}
        
        for enc in encounters:
            name = enc.get('name', '')
            enc_id = enc.get('id')
            
            # Try to extract day number from name
            day_match = re.search(r'day\s*[-]?\s*(\d+)', name.lower())
            if day_match:
                day = int(day_match.group(1))
                if day not in day_map:
                    day_map[day] = enc_id
        
        return day_map
    
    def _find_activity_by_name(self, design: Dict[str, Any], name: str) -> Optional[str]:
        """Find activity ID by name."""
        if not name:
            return None
        
        name_lower = name.lower()
        
        for activity in design.get('activities', []):
            act_name = activity.get('name', '').lower()
            act_label = activity.get('label', '').lower()
            
            if name_lower == act_name or name_lower == act_label:
                return activity['id']
            
            if name_lower in act_name or act_name in name_lower:
                return activity['id']
        
        return None
    
    def _is_prose_fragment(self, text: str) -> bool:
        """
        Check if text is a prose fragment rather than a valid treatment name.
        
        Filters out garbage like "for the", "day and", "mg and", "to ALXN1840"
        that sometimes get extracted as treatment names.
        """
        if not text:
            return True
        
        text_clean = text.strip()
        
        # Too short to be a real treatment name
        if len(text_clean) < 3:
            return True
        
        # Starts with common stopwords
        text_lower = text_clean.lower()
        stopword_prefixes = [
            'the ', 'is ', 'with ', 'of ', 'for ', 'to ', 'and ', 'or ',
            'in ', 'on ', 'at ', 'by ', 'from ', 'as ',
        ]
        if any(text_lower.startswith(prefix) for prefix in stopword_prefixes):
            return True
        
        # Is ONLY a stopword
        pure_stopwords = {'the', 'is', 'with', 'of', 'for', 'to', 'and', 'or', 'in', 'on', 'at', 'by'}
        if text_lower in pure_stopwords:
            return True
        
        # Just a dose/unit fragment (e.g., "mg and", "15 mg", "day and")
        if re.match(r'^\d+\s*(mg|ml|mcg|g|kg|iu)?\s*(and|or)?$', text_lower):
            return True
        if re.match(r'^(day|week|month)\s*(and|or|$)', text_lower):
            return True
        
        # Contains prose indicators
        prose_indicators = [
            'reconstituted', 'lyophilized', 'concentration',
            'administered', 'provided', 'according to'
        ]
        if any(ind in text_lower for ind in prose_indicators):
            return True
        
        return False
    
    def _find_matching_intervention(
        self, 
        name: str, 
        interventions: Dict[str, Any]
    ) -> Optional[Dict]:
        """Find matching intervention by name."""
        if not name:
            return None
        
        name_lower = name.lower()
        
        # Exact match
        if name_lower in interventions:
            return interventions[name_lower]
        
        # Fuzzy match
        for int_name, intervention in interventions.items():
            if name_lower in int_name or int_name in name_lower:
                return intervention
        
        return None
    
    def _get_route_code(self, route: str) -> Dict[str, Any]:
        """Get CDISC code for route of administration."""
        route_codes = {
            'oral': ('C38288', 'Oral'),
            'intravenous': ('C38276', 'Intravenous'),
            'iv': ('C38276', 'Intravenous'),
            'subcutaneous': ('C38299', 'Subcutaneous'),
            'intramuscular': ('C38273', 'Intramuscular'),
            'topical': ('C38304', 'Topical'),
        }
        
        # Handle enum objects (extract .value if it's an enum)
        route_str = route.value if hasattr(route, 'value') else str(route)
        route_lower = route_str.lower()
        code, decode = route_codes.get(route_lower, ('C38288', route_str))
        
        return {
            "id": str(uuid.uuid4()),
            "code": code,
            "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
            "decode": decode,
            "instanceType": "Code"
        }
    
    def _find_best_matching_instance(
        self, 
        timing_name: str, 
        instances: List[Dict]
    ) -> Optional[str]:
        """Find best matching instance for a timing reference."""
        if not timing_name or not instances:
            return None
        
        timing_lower = timing_name.lower()
        
        # Look for keywords in timing name
        keywords = ['first dose', 'baseline', 'day 1', 'randomization', 'screening']
        
        for kw in keywords:
            if kw in timing_lower:
                for inst in instances:
                    inst_name = inst.get('name', '').lower()
                    if kw in inst_name:
                        return inst['id']
        
        # Try day matching
        day_match = re.search(r'day\s*(\d+)', timing_lower)
        if day_match:
            target_day = int(day_match.group(1))
            for inst in instances:
                inst_day = inst.get('scheduledDay')
                if inst_day == target_day:
                    return inst['id']
        
        return None


def promote_execution_model(
    usdm_design: Dict[str, Any],
    study_version: Dict[str, Any],
    execution_data: Any,  # ExecutionModelData
) -> Tuple[Dict[str, Any], Dict[str, Any], PromotionResult]:
    """
    Convenience function to run execution model promotion.
    
    Args:
        usdm_design: The study design
        study_version: The study version  
        execution_data: Execution model data to promote
        
    Returns:
        Tuple of (enriched_design, enriched_version, result)
    """
    promoter = ExecutionModelPromoter()
    design, version = promoter.promote(usdm_design, study_version, execution_data)
    return design, version, promoter.result
