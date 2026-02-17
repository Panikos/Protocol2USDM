"""
Reconciliation/Promotion Layer for USDM Pipeline.

This layer bridges the gap between execution model findings and the core USDM graph.
It ensures that structural findings (crossover, traversal, dosing) don't just land
in extensions but actually shape the core USDM model.

Architecture:
    PDF → Core Extractors → Initial USDM Core
                                  ↓
    PDF → Execution Extractors → Execution Data
                                  ↓
             ← Reconciliation Layer →
                                  ↓
                         Enriched USDM Core

Key responsibilities:
1. Promote structural findings (crossover → epochs/cells/arms)
2. Bidirectional entity resolution (traversal ↔ epochs)
3. Consolidate/normalize extracted data (dosing, visits)
4. Validate consistency before final output
"""

import logging
import uuid
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class IssueSeverity(Enum):
    """Severity levels for integrity issues."""
    BLOCKING = "blocking"  # Prevents downstream use
    WARNING = "warning"    # Degraded but usable
    INFO = "info"          # Informational only


@dataclass
class IntegrityIssue:
    """A classified integrity issue with actionable context."""
    severity: IssueSeverity
    category: str  # e.g., "traversal_resolution", "dosing_fragmentation"
    message: str
    affected_path: str  # JSONPath to affected object
    affected_ids: List[str] = field(default_factory=list)
    suggestion: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity.value,
            "category": self.category,
            "message": self.message,
            "affectedPath": self.affected_path,
            "affectedIds": self.affected_ids,
            "suggestion": self.suggestion
        }


class ReconciliationLayer:
    """
    Bridges execution model findings with the core USDM graph.
    
    This layer ensures that extracted execution logic actually shapes
    the core USDM model, not just extensions.
    """
    
    def __init__(self):
        self.issues: List[IntegrityIssue] = []
        self._epoch_alias_map: Dict[str, str] = {}  # alias → epoch_id
        self._visit_alias_map: Dict[str, str] = {}  # alias → encounter_id
    
    def reconcile(
        self,
        usdm_design: Dict[str, Any],
        execution_data: Any,  # ExecutionModelData
    ) -> Dict[str, Any]:
        """
        Main reconciliation entry point.
        
        Args:
            usdm_design: The core USDM study design
            execution_data: Extracted execution model data
            
        Returns:
            Enriched USDM design with promoted findings
        """
        logger.info("Starting reconciliation layer...")
        
        # Step 0: Design reconciliation gate - validate crossover vs study design consistency
        if execution_data.crossover_design and execution_data.crossover_design.is_crossover:
            # Check if crossover detection is consistent with study design
            num_arms = len(usdm_design.get('arms', []))
            crossover_valid = self._validate_crossover_consistency(
                usdm_design, execution_data.crossover_design
            )
            if not crossover_valid:
                logger.warning("Crossover detection inconsistent with study design - dropping crossover extension")
                execution_data.crossover_design = None
        
        # Step 1: Promote crossover findings to core epochs/cells (if still valid)
        if execution_data.crossover_design:
            usdm_design = self._promote_crossover_design(
                usdm_design, execution_data.crossover_design
            )
        
        # Step 2: Build bidirectional entity resolution maps
        self._build_entity_maps(usdm_design, execution_data)
        
        # Step 3: Resolve traversal constraints to actual epoch IDs
        if execution_data.traversal_constraints:
            execution_data = self._resolve_traversal_references(
                usdm_design, execution_data
            )
        
        # Step 4: Consolidate dosing regimens
        if execution_data.dosing_regimens:
            usdm_design = self._consolidate_dosing_regimens(
                usdm_design, execution_data.dosing_regimens
            )
        
        # Step 5: Normalize visit windows
        if execution_data.visit_windows:
            usdm_design = self._normalize_visit_windows(
                usdm_design, execution_data.visit_windows
            )
        
        # Step 6: Classify and attach integrity issues
        self._classify_issues()
        
        logger.info(f"Reconciliation complete: {len(self.issues)} issues found")
        return usdm_design
    
    def _validate_crossover_consistency(
        self,
        design: Dict[str, Any],
        crossover: Any,  # CrossoverDesign
    ) -> bool:
        """
        Validate that crossover detection is consistent with the actual study design.
        
        Design reconciliation gate: If the study is single-arm or the crossover
        detection doesn't match the study structure, return False to drop it.
        
        TRUE CROSSOVER characteristics:
        - Same subjects receive both treatments (AB/BA sequences)
        - Typically 2 sequence arms with balanced randomization (1:1)
        - Washout periods between same-subject treatments
        
        FALSE POSITIVES to detect:
        - Parallel-group RCT with extension/switch (e.g., MTX→Upadacitinib)
        - Multi-arm parallel designs (>2 arms with unequal ratios)
        - One-way switch patterns without reciprocal sequences
        
        Returns:
            True if crossover is consistent with design, False otherwise
        """
        arms = design.get('arms', [])
        num_arms = len(arms)
        num_epochs = len(design.get('epochs', []))
        
        # Single-arm studies shouldn't have crossover (unless it's a within-subject crossover)
        if num_arms <= 1 and crossover.num_sequences > 1:
            self.issues.append(IntegrityIssue(
                severity=IssueSeverity.WARNING,
                category="crossover_design_mismatch",
                message=f"Crossover detected ({crossover.num_sequences} sequences) but study has {num_arms} arm(s)",
                affected_path="$.studyDesigns[0].crossoverDesign",
                suggestion="Review if this is actually a crossover study or if detection was a false positive"
            ))
            return False
        
        # =======================================================================
        # CHECK 1: Multi-arm parallel design (>2 arms = likely NOT crossover)
        # True crossover typically has 2 arms representing AB and BA sequences
        # =======================================================================
        if num_arms > 2:
            # Check if arms look like parallel treatment groups (not sequences)
            arm_names = [a.get('name', '') for a in arms]
            arm_descriptions = [a.get('description', '') for a in arms]
            
            # Look for sequence naming (AB, BA, Sequence 1, etc.)
            sequence_indicators = ['sequence ab', 'sequence ba', 'ab sequence', 'ba sequence',
                                   'sequence 1', 'sequence 2', 'treatment sequence']
            has_sequence_naming = any(
                any(ind in name.lower() or ind in desc.lower() 
                    for ind in sequence_indicators)
                for name, desc in zip(arm_names, arm_descriptions)
            )
            
            if not has_sequence_naming:
                self.issues.append(IntegrityIssue(
                    severity=IssueSeverity.WARNING,
                    category="crossover_parallel_mismatch",
                    message=f"Crossover detected but study has {num_arms} arms without sequence naming - likely parallel-group design",
                    affected_path="$.studyDesigns[0].crossoverDesign",
                    affected_ids=[a.get('id', '') for a in arms],
                    suggestion="Multi-arm parallel studies should use 'Parallel Study' model, not 'Crossover Study'"
                ))
                return False
        
        # =======================================================================
        # CHECK 2: One-way switch pattern (NOT true crossover)
        # True crossover: subjects get A→B AND B→A (bidirectional)
        # Extension/switch: some subjects get A→B only (unidirectional)
        # =======================================================================
        arm_descriptions = ' '.join(a.get('description', '') for a in arms)
        arm_names_combined = ' '.join(a.get('name', '') for a in arms)
        all_arm_text = (arm_descriptions + ' ' + arm_names_combined).lower()
        
        # Detect one-way switch patterns (MTX to X, placebo to X, etc.)
        switch_patterns = [
            (r'(\w+)\s+to\s+(\w+)', 'to'),      # "MTX to Upadacitinib"
            (r'(\w+)\s*[→➔]\s*(\w+)', '→'),    # "MTX → Upadacitinib"
            (r'(\w+)\s+then\s+(\w+)', 'then'),  # "MTX then Upadacitinib"
        ]
        
        switch_pairs = []
        for pattern, _ in switch_patterns:
            matches = re.findall(pattern, all_arm_text)
            for match in matches:
                if len(match) >= 2:
                    switch_pairs.append((match[0], match[1]))
        
        if switch_pairs:
            # Check for bidirectional switches (true crossover signature)
            has_bidirectional = False
            for a, b in switch_pairs:
                # Look for reverse switch (B to A)
                if any(pair[0] == b and pair[1] == a for pair in switch_pairs):
                    has_bidirectional = True
                    break
            
            if not has_bidirectional and len(switch_pairs) > 0:
                # Unidirectional switch = extension/switch design, NOT crossover
                self.issues.append(IntegrityIssue(
                    severity=IssueSeverity.WARNING,
                    category="crossover_switch_pattern",
                    message=f"Detected one-way treatment switch pattern without reciprocal sequence - this is extension/switch design, not crossover",
                    affected_path="$.studyDesigns[0].crossoverDesign",
                    affected_ids=[f"{a}→{b}" for a, b in switch_pairs[:3]],
                    suggestion="Use 'Parallel Study' with treatment switch epochs instead of 'Crossover Study'"
                ))
                return False
        
        # =======================================================================
        # CHECK 3: Unequal randomization ratio (typical crossover is 1:1)
        # =======================================================================
        allocation_ratio = design.get('allocationRatio', {})
        ratio_str = allocation_ratio.get('ratio', '') if isinstance(allocation_ratio, dict) else ''
        
        if ratio_str and ':' in ratio_str:
            ratios = [int(r) for r in ratio_str.split(':') if r.isdigit()]
            if len(ratios) > 2:
                # More than 2 ratio components = not typical crossover
                self.issues.append(IntegrityIssue(
                    severity=IssueSeverity.WARNING,
                    category="crossover_ratio_mismatch",
                    message=f"Allocation ratio '{ratio_str}' has {len(ratios)} components - true crossover typically has 2 sequences (1:1)",
                    affected_path="$.studyDesigns[0].allocationRatio",
                    suggestion="Multi-way randomization suggests parallel-group design"
                ))
                return False
            elif len(ratios) == 2 and ratios[0] != ratios[1]:
                # Unequal ratio for 2 arms - could still be crossover but flag it
                self.issues.append(IntegrityIssue(
                    severity=IssueSeverity.INFO,
                    category="crossover_unequal_ratio",
                    message=f"Allocation ratio '{ratio_str}' is unequal - true crossover typically uses 1:1",
                    affected_path="$.studyDesigns[0].allocationRatio",
                    suggestion="Verify this is truly a crossover design"
                ))
                # Don't fail, just flag
        
        # Check if periods make sense given epochs
        if crossover.num_periods > num_epochs:
            self.issues.append(IntegrityIssue(
                severity=IssueSeverity.WARNING,
                category="crossover_period_mismatch",
                message=f"Crossover has {crossover.num_periods} periods but only {num_epochs} epochs exist",
                affected_path="$.studyDesigns[0].crossoverDesign",
                suggestion="Period epochs may need to be created or crossover detection may be inaccurate"
            ))
            # Don't fail - we can create the epochs
        
        # Check for titration indicators that conflict with crossover
        titration_indicators = ['titration', 'titrate', 'dose escalation', 'dose adjustment']
        if any(ind in all_arm_text for ind in titration_indicators):
            self.issues.append(IntegrityIssue(
                severity=IssueSeverity.WARNING,
                category="crossover_titration_conflict",
                message="Study appears to have titration schedule which conflicts with crossover detection",
                affected_path="$.studyDesigns[0].crossoverDesign",
                suggestion="Titration studies are typically not crossover - dropping crossover extension"
            ))
            return False
        
        return True
    
    def _promote_crossover_design(
        self,
        design: Dict[str, Any],
        crossover: Any,  # CrossoverDesign
    ) -> Dict[str, Any]:
        """
        Promote crossover findings into core USDM epochs/cells/arms.
        
        If isCrossover=true, we need to:
        - Create epochs for each period (+ washout if present)
        - Create study cells per arm×epoch
        - Ensure encounters align to epochs
        """
        if not crossover.is_crossover:
            return design
        
        logger.info(f"Promoting crossover design: {crossover.num_periods} periods, {crossover.num_sequences} sequences")
        
        existing_epochs = {e.get('name', '').lower(): e for e in design.get('epochs', [])}
        existing_epoch_ids = {e.get('id') for e in design.get('epochs', [])}
        
        # Create period epochs if they don't exist
        period_epochs = []
        for i in range(1, crossover.num_periods + 1):
            period_name = f"Period {i}"
            if period_name.lower() not in existing_epochs:
                epoch = self._create_epoch(
                    f"period_{i}",
                    period_name,
                    sequence_number=i + 10,  # After screening/baseline
                    epoch_type_code="C101526"  # Treatment epoch
                )
                design.setdefault('epochs', []).append(epoch)
                period_epochs.append(epoch)
                self._epoch_alias_map[f'PERIOD_{i}'] = epoch['id']
                logger.info(f"Created period epoch: {period_name}")
            else:
                period_epochs.append(existing_epochs[period_name.lower()])
                self._epoch_alias_map[f'PERIOD_{i}'] = existing_epochs[period_name.lower()]['id']
        
        # Create washout epoch if mentioned
        if crossover.washout_duration:
            washout_name = "Washout"
            if washout_name.lower() not in existing_epochs:
                washout_epoch = self._create_epoch(
                    "washout",
                    washout_name,
                    sequence_number=15,
                    epoch_type_code="C48313"  # Follow-up/washout
                )
                design.setdefault('epochs', []).append(washout_epoch)
                self._epoch_alias_map['WASHOUT'] = washout_epoch['id']
                logger.info(f"Created washout epoch: {crossover.washout_duration}")
        
        # Create study cells for each sequence × period
        if crossover.sequences:
            existing_cells = design.get('studyCells', [])
            existing_arms = {a.get('name', ''): a for a in design.get('arms', [])}
            
            for seq in crossover.sequences:
                # Create arm for sequence if needed
                arm_name = f"Sequence {seq.sequence_name}"
                if arm_name not in existing_arms:
                    arm = self._create_arm(seq.sequence_name, arm_name)
                    design.setdefault('arms', []).append(arm)
                    existing_arms[arm_name] = arm
                    logger.info(f"Created arm for sequence: {arm_name}")
                
                # Create cells linking arm to period epochs
                for i, treatment in enumerate(seq.treatment_order):
                    if i < len(period_epochs):
                        cell = self._create_study_cell(
                            arm_id=existing_arms[arm_name]['id'],
                            epoch_id=period_epochs[i]['id'],
                            treatment=treatment
                        )
                        design.setdefault('studyCells', []).append(cell)
        
        # Update study design type
        design['studyDesignType'] = self._create_code(
            "C98388",  # Crossover
            "http://www.cdisc.org",
            "Crossover Study"
        )
        
        return design
    
    def _build_entity_maps(
        self,
        design: Dict[str, Any],
        execution_data: Any
    ):
        """Build bidirectional maps between semantic labels and USDM entity IDs."""
        
        # Map epochs by name variants
        for epoch in design.get('epochs', []):
            epoch_id = epoch.get('id', '')
            epoch_name = epoch.get('name', '')
            
            # Direct name mapping
            self._epoch_alias_map[epoch_name.upper()] = epoch_id
            self._epoch_alias_map[epoch_name.upper().replace(' ', '_')] = epoch_id
            
            # Semantic aliases based on name content
            name_lower = epoch_name.lower()
            if 'screen' in name_lower:
                self._epoch_alias_map['SCREENING'] = epoch_id
            if 'baseline' in name_lower or name_lower == 'day 1':
                self._epoch_alias_map['BASELINE'] = epoch_id
            if 'treatment' in name_lower:
                self._epoch_alias_map['TREATMENT'] = epoch_id
            if 'run' in name_lower and 'in' in name_lower:
                self._epoch_alias_map['RUN_IN'] = epoch_id
            if 'follow' in name_lower:
                self._epoch_alias_map['FOLLOW_UP'] = epoch_id
            if 'maintenance' in name_lower:
                self._epoch_alias_map['MAINTENANCE'] = epoch_id
            if 'end' in name_lower and 'study' in name_lower:
                self._epoch_alias_map['END_OF_STUDY'] = epoch_id
            
            # Period number extraction
            period_match = re.search(r'period\s*(\d+)', name_lower)
            if period_match:
                self._epoch_alias_map[f'PERIOD_{period_match.group(1)}'] = epoch_id
        
        # Map encounters/visits
        for enc in design.get('encounters', []):
            enc_id = enc.get('id', '')
            enc_name = enc.get('name', '')
            self._visit_alias_map[enc_name.upper()] = enc_id
            self._visit_alias_map[enc_name.upper().replace(' ', '_')] = enc_id
        
        logger.info(f"Built entity maps: {len(self._epoch_alias_map)} epoch aliases, {len(self._visit_alias_map)} visit aliases")
    
    def _resolve_traversal_references(
        self,
        design: Dict[str, Any],
        execution_data: Any
    ) -> Any:
        """Resolve traversal constraint labels to actual USDM epoch IDs using LLM."""
        from .entity_resolver import EntityResolver, create_resolution_context_from_design
        
        epoch_ids = {e.get('id') for e in design.get('epochs', [])}
        
        # Collect all unresolved concepts
        unresolved_concepts = set()
        for tc in execution_data.traversal_constraints:
            for step in tc.required_sequence:
                step_upper = step.upper().replace(' ', '_')
                if step not in epoch_ids and step_upper not in self._epoch_alias_map:
                    unresolved_concepts.add(step_upper)
        
        # Use LLM-based EntityResolver for semantic mapping
        llm_mappings = {}
        if unresolved_concepts:
            try:
                resolver = EntityResolver()
                context = create_resolution_context_from_design(design)
                mappings = resolver.resolve_epoch_concepts(list(unresolved_concepts), context)
                
                for concept, mapping in mappings.items():
                    if mapping:
                        llm_mappings[concept] = mapping.resolved_id
                        self._epoch_alias_map[concept] = mapping.resolved_id
                        logger.info(f"LLM resolved '{concept}' → '{mapping.resolved_name}' (confidence: {mapping.confidence:.2f})")
                    else:
                        logger.warning(f"LLM could not resolve '{concept}'")
            except Exception as e:
                logger.warning(f"LLM entity resolution failed: {e}")
        
        # Now resolve all traversal steps
        unresolved = set()
        for tc in execution_data.traversal_constraints:
            resolved_sequence = []
            for step in tc.required_sequence:
                step_upper = step.upper().replace(' ', '_')
                
                # Already a valid ID?
                if step in epoch_ids:
                    resolved_sequence.append(step)
                # Can we resolve via alias map (includes LLM mappings)?
                elif step_upper in self._epoch_alias_map:
                    resolved_sequence.append(self._epoch_alias_map[step_upper])
                elif step in self._epoch_alias_map:
                    resolved_sequence.append(self._epoch_alias_map[step])
                else:
                    # Record as unresolved
                    unresolved.add(step)
                    self.issues.append(IntegrityIssue(
                        severity=IssueSeverity.WARNING,
                        category="traversal_resolution",
                        message=f"Traversal step '{step}' could not be resolved to an epoch ID",
                        affected_path=f"$.traversalConstraints[].requiredSequence",
                        affected_ids=[tc.id if hasattr(tc, 'id') else ''],
                        suggestion=f"Create epoch for '{step}' or map to existing epoch"
                    ))
            
            # Update the constraint with resolved sequence
            tc.required_sequence = resolved_sequence
        
        if unresolved:
            logger.warning(f"Unresolved traversal steps: {unresolved}")
        else:
            logger.info("All traversal steps resolved to epoch IDs")
        
        return execution_data
    
    def _consolidate_dosing_regimens(
        self,
        design: Dict[str, Any],
        dosing_regimens: List[Any]
    ) -> Dict[str, Any]:
        """
        Consolidate fragmented dosing regimens into coherent structures.
        
        Problems to fix:
        - treatmentName contains prose fragments
        - Multiple regimens for same intervention
        - Missing linkage to actual interventions
        """
        
        # Get actual intervention names from design
        interventions = {
            i.get('name', '').lower(): i 
            for i in design.get('studyInterventions', [])
        }
        intervention_names = set(interventions.keys())
        
        # Group regimens by likely intervention
        consolidated = {}
        fragments = []
        
        for regimen in dosing_regimens:
            treatment_name = getattr(regimen, 'treatment_name', '') or ''
            
            # Check if this is a valid intervention name
            is_valid = any(
                inv_name in treatment_name.lower() or treatment_name.lower() in inv_name
                for inv_name in intervention_names
            )
            
            # Detect prose fragments
            prose_indicators = [
                'the ', 'is ', 'with ', 'of ', 'for ', 'to ', 
                'reconstituted', 'lyophilized', 'concentration'
            ]
            is_fragment = any(ind in treatment_name.lower() for ind in prose_indicators)
            
            if is_fragment:
                fragments.append(regimen)
                self.issues.append(IntegrityIssue(
                    severity=IssueSeverity.WARNING,
                    category="dosing_fragmentation",
                    message=f"Dosing regimen has prose fragment as treatment name: '{treatment_name[:50]}...'",
                    affected_path="$.dosingRegimens[]",
                    affected_ids=[getattr(regimen, 'id', '')],
                    suggestion="Consolidate with parent intervention regimen"
                ))
            elif is_valid:
                # Group by normalized intervention name
                key = self._find_matching_intervention(treatment_name, intervention_names)
                if key:
                    consolidated.setdefault(key, []).append(regimen)
            else:
                # Unknown treatment - keep but flag
                consolidated.setdefault(treatment_name, []).append(regimen)
        
        # Merge regimens for same intervention
        for intervention_name, regimens in consolidated.items():
            if len(regimens) > 1:
                logger.info(f"Consolidating {len(regimens)} regimens for '{intervention_name}'")
                # Keep the most complete regimen, merge details from others
                # (Implementation would merge dose, route, frequency, etc.)
        
        logger.info(f"Dosing consolidation: {len(consolidated)} interventions, {len(fragments)} fragments")
        return design
    
    def _normalize_visit_windows(
        self,
        design: Dict[str, Any],
        visit_windows: List[Any]
    ) -> Dict[str, Any]:
        """
        Normalize visit windows and surface them on encounters.
        
        Per feedback: "encounter windows are not surfaced directly" - this fix
        duplicates window info onto encounters as derived read-only attributes
        so consumers don't have to reconstruct windows from timing logic.
        
        Problems to fix:
        - Multiple visits with same targetDay
        - Incorrect targetDay derivation
        - Missing/inconsistent visit identifiers
        - Windows not surfaced on encounters (NEW)
        """
        
        # Build encounter lookup by name/day for matching
        encounters = design.get('encounters', [])
        encounter_by_name = {}
        encounter_by_day = {}
        for enc in encounters:
            enc_name = enc.get('name', '').lower()
            encounter_by_name[enc_name] = enc
            # Try to extract day from name
            day_match = re.search(r'day\s*[-]?\s*(\d+)', enc_name)
            if day_match:
                encounter_by_day[int(day_match.group(1))] = enc
        
        # Group by targetDay to find conflicts
        by_target_day: Dict[int, List[Any]] = {}
        for vw in visit_windows:
            target_day = getattr(vw, 'target_day', None)
            if target_day is not None:
                by_target_day.setdefault(target_day, []).append(vw)
        
        # Flag conflicts
        for target_day, windows in by_target_day.items():
            if len(windows) > 1:
                visit_names = [getattr(w, 'visit_name', 'unknown') for w in windows]
                
                # Day 1 conflict is particularly problematic
                if target_day == 1:
                    self.issues.append(IntegrityIssue(
                        severity=IssueSeverity.BLOCKING,
                        category="visit_window_conflict",
                        message=f"Multiple visits mapped to Day 1: {visit_names}",
                        affected_path="$.visitWindows[]",
                        affected_ids=[getattr(w, 'id', '') for w in windows],
                        suggestion="Re-derive targetDay from visit context or SoA position"
                    ))
                else:
                    self.issues.append(IntegrityIssue(
                        severity=IssueSeverity.WARNING,
                        category="visit_window_conflict",
                        message=f"Multiple visits mapped to Day {target_day}: {visit_names}",
                        affected_path="$.visitWindows[]",
                        affected_ids=[getattr(w, 'id', '') for w in windows],
                        suggestion="Verify visit scheduling logic"
                    ))
        
        # =========================================================================
        # SURFACE WINDOWS ON ENCOUNTERS (per feedback)
        # This makes window info directly accessible without reconstructing from timing
        # =========================================================================
        windows_surfaced = 0
        for vw in visit_windows:
            visit_name = getattr(vw, 'visit_name', '')
            visit_id = getattr(vw, 'id', '')
            target_day = getattr(vw, 'target_day', None)
            window_before = getattr(vw, 'window_before', 0)
            window_after = getattr(vw, 'window_after', 0)
            
            # Try to match to an encounter
            matched_encounter = None
            visit_name_lower = visit_name.lower() if visit_name else ''
            
            # Match by name first
            if visit_name_lower in encounter_by_name:
                matched_encounter = encounter_by_name[visit_name_lower]
            else:
                # Try partial match
                for enc_name, enc in encounter_by_name.items():
                    if visit_name_lower and (visit_name_lower in enc_name or enc_name in visit_name_lower):
                        matched_encounter = enc
                        break
            
            # Fall back to day match
            if not matched_encounter and target_day is not None:
                matched_encounter = encounter_by_day.get(target_day)
            
            if matched_encounter:
                # Surface window info on encounter as extension attributes
                ext_attrs = matched_encounter.setdefault('extensionAttributes', [])
                
                # Add window info
                ext_attrs.append({
                    "id": f"ext_window_{matched_encounter['id'][:8]}",
                    "url": "http://example.org/usdm/visitWindow",
                    "instanceType": "ExtensionAttribute",
                    "valueJson": {
                        "targetDay": target_day,
                        "windowBefore": window_before,
                        "windowAfter": window_after,
                        "windowDescription": f"Day {target_day} (±{max(window_before, window_after)} days)" if window_before == window_after else f"Day {target_day} (-{window_before}/+{window_after} days)"
                    }
                })
                
                # Also add scheduledAtId if available
                timing_id = getattr(vw, 'timing_id', None)
                if timing_id:
                    ext_attrs.append({
                        "id": f"ext_timing_{matched_encounter['id'][:8]}",
                        "url": "http://example.org/usdm/scheduledAtId",
                        "instanceType": "ExtensionAttribute",
                        "valueString": timing_id
                    })
                
                windows_surfaced += 1
                self._visit_alias_map[visit_name] = matched_encounter['id']
            else:
                if not visit_id or visit_id.startswith('visit_window_'):
                    self.issues.append(IntegrityIssue(
                        severity=IssueSeverity.INFO,
                        category="visit_window_identity",
                        message=f"Visit '{visit_name}' has placeholder ID and could not be linked to encounter",
                        affected_path="$.visitWindows[]",
                        affected_ids=[visit_id],
                        suggestion="Link to corresponding USDM encounter"
                    ))
        
        logger.info(f"Visit normalization: {len(by_target_day)} unique target days, {windows_surfaced} windows surfaced on encounters")
        return design
    
    def _classify_issues(self):
        """Final classification pass on all collected issues."""
        blocking = sum(1 for i in self.issues if i.severity == IssueSeverity.BLOCKING)
        warnings = sum(1 for i in self.issues if i.severity == IssueSeverity.WARNING)
        info = sum(1 for i in self.issues if i.severity == IssueSeverity.INFO)
        
        logger.info(f"Issue classification: {blocking} blocking, {warnings} warning, {info} info")
    
    def get_issues(self) -> List[IntegrityIssue]:
        """Get all classified integrity issues."""
        return self.issues
    
    def get_issues_dict(self) -> List[Dict[str, Any]]:
        """Get issues as serializable dicts."""
        return [i.to_dict() for i in self.issues]
    
    def get_entity_maps(self) -> Dict[str, Dict[str, str]]:
        """Get the entity resolution maps for downstream use."""
        return {
            "epochAliases": self._epoch_alias_map.copy(),
            "visitAliases": self._visit_alias_map.copy()
        }
    
    # Helper methods
    
    def _create_epoch(
        self,
        epoch_id: str,
        name: str,
        sequence_number: int,
        epoch_type_code: str
    ) -> Dict[str, Any]:
        """Create a properly structured USDM epoch."""
        return {
            "id": epoch_id,
            "name": name,
            "description": f"{name} - auto-generated from crossover detection",
            "sequenceNumber": sequence_number,
            "epochType": self._create_code(epoch_type_code, "http://www.cdisc.org", name),
            "instanceType": "StudyEpoch"
        }
    
    def _create_arm(self, arm_id: str, name: str) -> Dict[str, Any]:
        """Create a properly structured USDM arm."""
        return {
            "id": arm_id,
            "name": name,
            "description": f"{name} - auto-generated from crossover sequence",
            "armType": self._create_code("C98388", "http://www.cdisc.org", "Crossover Arm"),
            "instanceType": "StudyArm"
        }
    
    def _create_study_cell(
        self,
        arm_id: str,
        epoch_id: str,
        treatment: str
    ) -> Dict[str, Any]:
        """Create a study cell linking arm to epoch."""
        return {
            "id": f"cell_{arm_id}_{epoch_id}",
            "armId": arm_id,
            "epochId": epoch_id,
            "description": f"Treatment: {treatment}",
            "instanceType": "StudyCell"
        }
    
    def _create_code(
        self,
        code: str,
        code_system: str,
        decode: str
    ) -> Dict[str, Any]:
        """Create a USDM Code object."""
        return {
            "id": str(uuid.uuid4()),
            "code": code,
            "codeSystem": code_system,
            "decode": decode,
            "instanceType": "Code"
        }
    
    def _find_matching_intervention(
        self,
        treatment_name: str,
        intervention_names: Set[str]
    ) -> Optional[str]:
        """Find the best matching intervention for a treatment name."""
        treatment_lower = treatment_name.lower()
        
        # Exact match
        if treatment_lower in intervention_names:
            return treatment_lower
        
        # Substring match
        for inv_name in intervention_names:
            if inv_name in treatment_lower or treatment_lower in inv_name:
                return inv_name
        
        return None


def reconcile_usdm_with_execution_model(
    usdm_design: Dict[str, Any],
    execution_data: Any
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Dict[str, str]]]:
    """
    Main entry point for reconciliation.
    
    Args:
        usdm_design: The core USDM study design
        execution_data: Extracted execution model data
        
    Returns:
        Tuple of (enriched_design, classified_issues, entity_maps)
    """
    reconciler = ReconciliationLayer()
    enriched_design = reconciler.reconcile(usdm_design, execution_data)
    
    return (
        enriched_design,
        reconciler.get_issues_dict(),
        reconciler.get_entity_maps()
    )
