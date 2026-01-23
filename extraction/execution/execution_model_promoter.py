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
        
        # Sort anchors by intra-day order for consistent processing
        sorted_anchors = sorted(
            time_anchors,
            key=lambda a: (getattr(a, 'day_value', 1), getattr(a, 'intra_day_order', 100))
        )
        
        for anchor in sorted_anchors:
            # Get anchor attributes
            anchor_name = getattr(anchor, 'name', '')
            if not anchor_name:
                anchor_type = getattr(anchor, 'anchor_type', 'Anchor')
                anchor_name = anchor_type.value if hasattr(anchor_type, 'value') else str(anchor_type)
            anchor_id = getattr(anchor, 'id', str(uuid.uuid4()))
            classification = getattr(anchor, 'classification', None)
            classification_val = classification.value if hasattr(classification, 'value') else str(classification)
            
            # Skip if similar anchor already exists
            if anchor_name.lower() in existing_anchor_names:
                for inst in instances:
                    if anchor_name.lower() in inst.get('name', '').lower():
                        self._anchor_instance_map[anchor_id] = inst['id']
                        break
                continue
            
            # =========================================================================
            # ENFORCE ANCHOR CLASSIFICATION (per feedback)
            # - VISIT anchors: Create ScheduledActivityInstance with encounter
            # - EVENT anchors: Link to activity, create instance only if activity exists
            # - CONCEPTUAL anchors: Timing reference only, no instance created
            # =========================================================================
            
            if classification_val == 'Conceptual':
                # CONCEPTUAL anchors are pure timing references - no instance needed
                # Store in map as a pseudo-reference for timing resolution
                self._anchor_instance_map[anchor_id] = f"timing_ref_{anchor_id}"
                logger.debug(f"  Conceptual anchor (no instance): {anchor_name}")
                continue
            
            instance_id = f"anchor_inst_{anchor_id}"
            day_value = getattr(anchor, 'day_value', None)
            intra_day_order = getattr(anchor, 'intra_day_order', 100)
            
            if classification_val == 'Event':
                # EVENT anchors link to activities, not visits
                # Only create instance if we can resolve to an activity
                activity_id = getattr(anchor, 'activity_id', None)
                if not activity_id:
                    activity_id = self._find_activity_by_anchor_type(design, anchor_name)
                
                anchor_instance = {
                    "id": instance_id,
                    "name": anchor_name,
                    "description": f"Event anchor: {anchor_name}",
                    "activityIds": [activity_id] if activity_id else [],
                    "instanceType": "ScheduledActivityInstance",
                    "extensionAttributes": [{
                        "id": f"ext_anchor_{instance_id[:8]}",
                        "url": "http://example.org/usdm/anchorClassification",
                        "instanceType": "ExtensionAttribute",
                        "valueString": "Event"
                    }]
                }
                # EVENT anchors get epoch but no encounter (they're not visits)
                anchor_instance["epochId"] = self._find_first_treatment_epoch_id(design)
                
            else:  # VISIT classification
                # VISIT anchors represent real encounters
                anchor_instance = {
                    "id": instance_id,
                    "name": anchor_name,
                    "description": f"Visit anchor: {anchor_name}",
                    "encounterId": anchor_encounter_id,
                    "epochId": self._find_first_treatment_epoch_id(design),
                    "activityIds": [],
                    "instanceType": "ScheduledActivityInstance",
                    "extensionAttributes": [{
                        "id": f"ext_anchor_{instance_id[:8]}",
                        "url": "http://example.org/usdm/anchorClassification",
                        "instanceType": "ExtensionAttribute",
                        "valueString": "Visit"
                    }]
                }
            
            # Add scheduling metadata
            if day_value is not None:
                anchor_instance["scheduledDay"] = day_value
            anchor_instance["extensionAttributes"].append({
                "id": f"ext_order_{instance_id[:8]}",
                "url": "http://example.org/usdm/intraDayOrder",
                "instanceType": "ExtensionAttribute",
                "valueInteger": intra_day_order
            })
            
            instances.append(anchor_instance)
            self._anchor_instance_map[anchor_id] = instance_id
            existing_anchor_names.add(anchor_name.lower())
            self.result.anchors_created += 1
            
            logger.info(f"  Created {classification_val} anchor: {anchor_name} → {instance_id}")
        
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
                        # Mark as enrichment-created so UI can distinguish from SoA instances
                        "extensionAttributes": [{
                            "id": f"ext_source_{instance_id[:8]}",
                            "url": "http://example.org/usdm/instanceSource",
                            "instanceType": "ExtensionAttribute",
                            "valueString": "execution_model"
                        }]
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
                    # Determine if this is a VISIT anchor that should create an instance
                    # or a CONCEPTUAL anchor that should remain a pure timing reference
                    anchor_classification = self._classify_timing_anchor(timing_name, ref_id)
                    
                    if anchor_classification == "Visit":
                        # VISIT anchors: Create ScheduledActivityInstance with encounter
                        encounter_id = self._find_or_create_anchor_encounter(design)
                        anchor_instance = {
                            "id": ref_id,
                            "name": f"Anchor: {timing_name}" if timing_name else f"Anchor: {ref_id}",
                            "activityIds": [],
                            "encounterId": encounter_id,
                            "instanceType": "ScheduledActivityInstance",
                            "extensionAttributes": [{
                                "id": f"ext_source_{ref_id[:8]}",
                                "url": "http://example.org/usdm/instanceSource",
                                "instanceType": "ExtensionAttribute",
                                "valueString": "execution_model"
                            }, {
                                "id": f"ext_class_{ref_id[:8]}",
                                "url": "http://example.org/usdm/anchorClassification",
                                "instanceType": "ExtensionAttribute",
                                "valueString": "Visit"
                            }]
                        }
                        instances.append(anchor_instance)
                        existing_instance_ids.add(ref_id)
                        self.result.anchors_created += 1
                        self.result.issues.append({
                            "severity": "info",
                            "category": "visit_anchor_created",
                            "message": f"Created VISIT anchor instance: {ref_id} (encounter: {encounter_id})",
                            "affectedPath": f"$.scheduleTimelines[0].instances[-1]"
                        })
                    elif anchor_classification == "Event":
                        # EVENT anchors: Try to attach to existing activity
                        activity_instance = self._find_activity_for_event_anchor(timing_name, instances)
                        if activity_instance:
                            # Use existing activity instance as the anchor
                            timing['relativeFromScheduledInstanceId'] = activity_instance
                            self.result.references_fixed += 1
                            self.result.issues.append({
                                "severity": "info",
                                "category": "event_anchor_linked",
                                "message": f"EVENT anchor '{timing_name}' linked to existing activity: {activity_instance}",
                                "affectedPath": f"$.timings[?(@.id=='{timing.get('id')}')]"
                            })
                        else:
                            # No activity found - store as conceptual reference
                            self._store_conceptual_anchor(design, ref_id, timing_name, "Event")
                            self.result.issues.append({
                                "severity": "warning",
                                "category": "event_anchor_unresolved",
                                "message": f"EVENT anchor '{timing_name}' has no matching activity - stored as conceptual",
                                "affectedPath": f"$.timings[?(@.id=='{timing.get('id')}')]"
                            })
                    else:
                        # CONCEPTUAL anchors: Store as pure timing reference (no instance)
                        self._store_conceptual_anchor(design, ref_id, timing_name, "Conceptual")
                        self.result.issues.append({
                            "severity": "info",
                            "category": "conceptual_anchor_stored",
                            "message": f"CONCEPTUAL anchor '{timing_name}' stored as timing reference (no visit)",
                            "affectedPath": f"$.extensionAttributes[?(@.url contains 'conceptualAnchors')]"
                        })
        
        return design
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _create_main_timeline(self) -> Dict[str, Any]:
        """Create main schedule timeline if missing."""
        timeline_id = f"timeline_{uuid.uuid4()}"
        return {
            "id": timeline_id,
            "name": "Main Study Timeline",
            "instances": [],
            "timings": [],
            "instanceType": "ScheduleTimeline",
            "mainTimeline": True,
            "entryCondition": "Subject meets all inclusion criteria and none of the exclusion criteria",
            "entryId": timeline_id  # Self-reference for main timeline entry point
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
    
    def _find_activity_by_anchor_type(self, design: Dict[str, Any], anchor_name: str) -> Optional[str]:
        """
        Find activity ID that matches an anchor type (for EVENT anchors).
        
        Maps anchor types to typical activity names:
        - FirstDose/TreatmentStart → drug administration activities
        - Randomization → randomization activities
        - InformedConsent → consent activities
        """
        if not anchor_name:
            return None
        
        anchor_lower = anchor_name.lower()
        
        # Map anchor types to activity keywords
        anchor_to_keywords = {
            'firstdose': ['dose', 'administration', 'infusion', 'injection', 'drug'],
            'treatmentstart': ['dose', 'administration', 'treatment', 'drug'],
            'randomization': ['randomization', 'randomize', 'allocation'],
            'informedconsent': ['consent', 'informed consent', 'icf'],
            'enrollment': ['enrollment', 'enroll', 'registration'],
        }
        
        # Normalize anchor name
        anchor_key = anchor_lower.replace(' ', '').replace('_', '')
        keywords = anchor_to_keywords.get(anchor_key, [anchor_lower])
        
        for activity in design.get('activities', []):
            act_name = activity.get('name', '').lower()
            for kw in keywords:
                if kw in act_name:
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
    
    def _classify_timing_anchor(self, timing_name: str, ref_id: str) -> str:
        """
        Classify a timing anchor to determine how it should be promoted.
        
        Returns:
            "Visit" - Should create ScheduledActivityInstance with encounter
            "Event" - Should attach to existing activity instance
            "Conceptual" - Should remain as pure timing reference (no instance)
        """
        if not timing_name:
            # Default unknown references to conceptual
            return "Conceptual"
        
        name_lower = timing_name.lower()
        
        # VISIT anchors - represent physical visits/encounters
        visit_keywords = [
            'day 1', 'day1', 'baseline', 'screening', 'visit',
            'check-in', 'checkin', 'admission', 'discharge',
            'end of study', 'eos', 'follow-up', 'followup',
        ]
        if any(kw in name_lower for kw in visit_keywords):
            return "Visit"
        
        # EVENT anchors - represent activity occurrences
        event_keywords = [
            'first dose', 'dose', 'randomization', 'randomisation',
            'informed consent', 'enrollment', 'enrolment',
            'treatment start', 'drug admin',
        ]
        if any(kw in name_lower for kw in event_keywords):
            return "Event"
        
        # CONCEPTUAL anchors - abstract timing references
        conceptual_keywords = [
            'cycle', 'period', 'phase', 'collection', 'study start',
            'study day', 'anchor',
        ]
        if any(kw in name_lower for kw in conceptual_keywords):
            return "Conceptual"
        
        # Default to conceptual for unrecognized patterns
        return "Conceptual"
    
    def _find_activity_for_event_anchor(
        self, 
        timing_name: str, 
        instances: List[Dict]
    ) -> Optional[str]:
        """
        Find an existing activity instance that matches an EVENT anchor.
        
        EVENT anchors (e.g., "First Dose", "Randomization") should attach to
        existing activities rather than creating new instances.
        """
        if not timing_name or not instances:
            return None
        
        name_lower = timing_name.lower()
        
        # Map event keywords to activity patterns
        event_activity_map = {
            'first dose': ['dose', 'drug', 'treatment', 'administration', 'alxn'],
            'dose': ['dose', 'drug', 'treatment', 'administration'],
            'randomization': ['random'],
            'randomisation': ['random'],
            'informed consent': ['consent', 'icf'],
            'enrollment': ['enroll', 'registration'],
            'enrolment': ['enroll', 'registration'],
        }
        
        # Find matching patterns
        patterns = []
        for event_kw, activity_patterns in event_activity_map.items():
            if event_kw in name_lower:
                patterns.extend(activity_patterns)
        
        if not patterns:
            return None
        
        # Search instances for matching activity
        for inst in instances:
            inst_name = inst.get('name', '').lower()
            for pattern in patterns:
                if pattern in inst_name:
                    return inst['id']
        
        return None
    
    def _store_conceptual_anchor(
        self, 
        design: Dict[str, Any], 
        ref_id: str, 
        timing_name: str,
        classification: str
    ) -> None:
        """
        Store a conceptual anchor as a pure timing reference.
        
        CONCEPTUAL anchors don't create ScheduledActivityInstances.
        They are stored in an extension for reference by downstream tools.
        """
        # Get or create conceptual anchors extension
        ext_url = "https://protocol2usdm.io/extensions/x-executionModel-conceptualAnchors"
        
        if 'extensionAttributes' not in design:
            design['extensionAttributes'] = []
        
        # Find existing conceptual anchors extension
        conceptual_ext = None
        for ext in design['extensionAttributes']:
            if ext.get('url') == ext_url:
                conceptual_ext = ext
                break
        
        if conceptual_ext is None:
            conceptual_ext = {
                "id": f"ext_conceptual_{uuid.uuid4()}",
                "url": ext_url,
                "instanceType": "ExtensionAttribute",
                "valueString": "[]"
            }
            design['extensionAttributes'].append(conceptual_ext)
        
        # Parse existing anchors
        import json
        try:
            anchors = json.loads(conceptual_ext.get('valueString', '[]'))
        except json.JSONDecodeError:
            anchors = []
        
        # Add new anchor
        anchors.append({
            "id": ref_id,
            "name": timing_name,
            "classification": classification,
            "note": "Pure timing reference - no visit or activity instance"
        })
        
        conceptual_ext['valueString'] = json.dumps(anchors)


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
