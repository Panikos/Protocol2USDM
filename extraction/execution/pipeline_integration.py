"""
Pipeline Integration for Execution Model Extractors

Provides functions to integrate execution model extraction into the
existing Protocol2USDMv3 pipeline without breaking existing functionality.

The execution model extraction is additive - it enriches existing USDM
output with execution semantics via extensionAttributes.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, Any, Optional, List

from .schema import ExecutionModelData, ExecutionModelResult
from .validation import validate_execution_model, ValidationResult
from .export import export_to_csv, save_report
from .time_anchor_extractor import extract_time_anchors
from .repetition_extractor import extract_repetitions
from .execution_type_classifier import classify_execution_types
from .crossover_extractor import extract_crossover_design
from .traversal_extractor import extract_traversal_constraints
from .footnote_condition_extractor import extract_footnote_conditions
from .endpoint_extractor import extract_endpoint_algorithms
from .derived_variable_extractor import extract_derived_variables
from .state_machine_generator import generate_state_machine
from .sampling_density_extractor import extract_sampling_density
from .dosing_regimen_extractor import extract_dosing_regimens
from .visit_window_extractor import extract_visit_windows
from .stratification_extractor import extract_stratification
from .entity_resolver import EntityResolver, EntityResolutionContext, create_resolution_context_from_design
from .reconciliation_layer import ReconciliationLayer, reconcile_usdm_with_execution_model
from .soa_context import SoAContext, extract_soa_context

logger = logging.getLogger(__name__)


def extract_execution_model(
    pdf_path: str,
    model: str = "gemini-2.5-pro",
    activities: Optional[List[Dict[str, Any]]] = None,
    use_llm: bool = True,  # LLM is now the default for better accuracy
    skip_llm: bool = False,  # Explicit flag to disable LLM (for testing/offline)
    sap_path: Optional[str] = None,  # Path to SAP PDF for enhanced extraction
    soa_data: Optional[Dict[str, Any]] = None,  # SOA extraction result for enhanced context
    output_dir: Optional[str] = None,
) -> ExecutionModelResult:
    """
    Extract complete execution model from a protocol PDF.
    
    This is the main entry point for execution model extraction.
    It runs all extractors and merges results.
    
    Args:
        pdf_path: Path to protocol PDF
        model: LLM model to use for extraction
        activities: Optional list of activities from prior extraction
                   (used for execution type classification)
        use_llm: Whether to use LLM (default True for best accuracy)
        skip_llm: If True, skip LLM even if use_llm=True (for offline/testing)
        sap_path: Optional path to SAP PDF for enhanced extraction
        soa_data: Optional SOA extraction result (contains encounters, timepoints)
        output_dir: Optional directory to save results
        
    Returns:
        ExecutionModelResult with combined ExecutionModelData
    """
    logger.info("=" * 60)
    logger.info("Starting Execution Model Extraction")
    logger.info("=" * 60)
    
    if sap_path:
        logger.info(f"SAP document provided: {sap_path}")
        # Validate SAP path
        if not Path(sap_path).exists():
            logger.warning(f"SAP file not found: {sap_path}")
            sap_path = None
    
    all_pages = []
    errors = []
    
    # Determine if LLM should be used
    enable_llm = use_llm and not skip_llm
    
    # Extract SoA context once - pass to all extractors for entity resolution
    soa_context = extract_soa_context(soa_data)
    if soa_context.has_epochs() or soa_context.has_encounters():
        logger.info(f"SoA context available: {soa_context.get_summary()}")
    
    # 1. Extract time anchors
    logger.info("Step 1/10: Extracting time anchors...")
    anchor_result = extract_time_anchors(
        pdf_path=pdf_path,
        model=model,
        use_llm=enable_llm,
    )
    
    if anchor_result.success:
        logger.info(f"  ✓ Found {len(anchor_result.data.time_anchors)} time anchors")
        all_pages.extend(anchor_result.pages_used)
    else:
        logger.warning(f"  ✗ Time anchor extraction failed: {anchor_result.error}")
        errors.append(f"TimeAnchor: {anchor_result.error}")
    
    # 2. Extract repetitions
    logger.info("Step 2/10: Extracting repetition patterns...")
    repetition_result = extract_repetitions(
        pdf_path=pdf_path,
        model=model,
        use_llm=enable_llm,
    )
    
    if repetition_result.success:
        logger.info(
            f"  ✓ Found {len(repetition_result.data.repetitions)} repetitions, "
            f"{len(repetition_result.data.sampling_constraints)} sampling constraints"
        )
        all_pages.extend(repetition_result.pages_used)
    else:
        logger.warning(f"  ✗ Repetition extraction failed: {repetition_result.error}")
        errors.append(f"Repetition: {repetition_result.error}")
    
    # 3. Classify execution types
    logger.info("Step 3/10: Classifying execution types...")
    classification_result = classify_execution_types(
        pdf_path=pdf_path,
        activities=activities,
        model=model,
        use_llm=enable_llm,
    )
    
    if classification_result.success:
        logger.info(f"  ✓ Classified {len(classification_result.data.execution_types)} activities")
        all_pages.extend(classification_result.pages_used)
    else:
        logger.warning(f"  ✗ Execution type classification failed: {classification_result.error}")
        errors.append(f"ExecutionType: {classification_result.error}")
    
    # 4. Extract crossover design (Phase 2)
    logger.info("Step 4/10: Detecting crossover design...")
    crossover_result = extract_crossover_design(
        pdf_path=pdf_path,
        model=model,
        use_llm=enable_llm,
    )
    
    if crossover_result.success and crossover_result.data.crossover_design:
        logger.info(
            f"  ✓ Detected crossover: {crossover_result.data.crossover_design.num_periods} periods, "
            f"washout={crossover_result.data.crossover_design.washout_duration}"
        )
        all_pages.extend(crossover_result.pages_used)
    else:
        logger.info("  ○ No crossover design detected (parallel or other)")
    
    # 5. Extract traversal constraints (Phase 2)
    logger.info("Step 5/10: Extracting traversal constraints...")
    
    # Use SoA epochs as reference (avoids abstract labels that need resolution)
    if soa_context.has_epochs():
        logger.info(f"  Using {len(soa_context.epochs)} SoA epochs as traversal reference")
    
    traversal_result = extract_traversal_constraints(
        pdf_path=pdf_path,
        model=model,
        use_llm=enable_llm,
        existing_epochs=soa_context.epochs if soa_context.has_epochs() else None,
    )
    
    if traversal_result.success:
        tc = traversal_result.data.traversal_constraints[0] if traversal_result.data.traversal_constraints else None
        if tc:
            logger.info(f"  ✓ Found {len(tc.required_sequence)} epochs, {len(tc.mandatory_visits)} mandatory visits")
        all_pages.extend(traversal_result.pages_used)
    else:
        logger.warning(f"  ✗ Traversal extraction failed: {traversal_result.error}")
        errors.append(f"Traversal: {traversal_result.error}")
    
    # 6. Extract footnote conditions (Phase 2)
    logger.info("Step 6/10: Extracting footnote conditions...")
    footnote_result = extract_footnote_conditions(
        pdf_path=pdf_path,
        model=model,
        use_llm=enable_llm,
        existing_activities=soa_context.activities if soa_context.has_activities() else None,
    )
    
    if footnote_result.success:
        logger.info(f"  ✓ Found {len(footnote_result.data.footnote_conditions)} footnote conditions")
        all_pages.extend(footnote_result.pages_used)
    else:
        logger.info("  ○ No footnote conditions extracted")
    
    # 7. Extract endpoint algorithms (Phase 3)
    logger.info("Step 7/10: Extracting endpoint algorithms...")
    endpoint_result = extract_endpoint_algorithms(
        pdf_path=pdf_path,
        model=model,
        use_llm=enable_llm,
        sap_path=sap_path,
    )
    
    if endpoint_result.success and endpoint_result.data.endpoint_algorithms:
        logger.info(f"  ✓ Found {len(endpoint_result.data.endpoint_algorithms)} endpoint algorithms")
        all_pages.extend(endpoint_result.pages_used)
    else:
        logger.info("  ○ No endpoint algorithms extracted")
    
    # 8. Extract derived variables (Phase 3)
    logger.info("Step 8/10: Extracting derived variables...")
    variable_result = extract_derived_variables(
        pdf_path=pdf_path,
        model=model,
        use_llm=enable_llm,
        sap_path=sap_path,
    )
    
    if variable_result.success and variable_result.data.derived_variables:
        logger.info(f"  ✓ Found {len(variable_result.data.derived_variables)} derived variables")
        all_pages.extend(variable_result.pages_used)
    else:
        logger.info("  ○ No derived variables extracted")
    
    # 9. Generate state machine (Phase 3)
    logger.info("Step 9/10: Generating subject state machine...")
    # Use traversal constraints if available
    traversal_for_sm = None
    if traversal_result.success and traversal_result.data.traversal_constraints:
        traversal_for_sm = traversal_result.data.traversal_constraints[0]
    
    crossover_for_sm = None
    if crossover_result.success and crossover_result.data.crossover_design:
        crossover_for_sm = crossover_result.data.crossover_design
    
    state_machine_result = generate_state_machine(
        pdf_path=pdf_path,
        model=model,
        traversal=traversal_for_sm,
        crossover=crossover_for_sm,
        use_llm=enable_llm,
    )
    
    if state_machine_result.success and state_machine_result.data.state_machine:
        sm = state_machine_result.data.state_machine
        logger.info(f"  ✓ Generated state machine: {len(sm.states)} states, {len(sm.transitions)} transitions")
        all_pages.extend(state_machine_result.pages_used)
    else:
        logger.info("  ○ No state machine generated")
    
    # 10. Extract dosing regimens (Phase 4)
    logger.info("Step 10/13: Extracting dosing regimens...")
    dosing_result = extract_dosing_regimens(
        pdf_path=pdf_path,
        model=model,
        use_llm=enable_llm,
    )
    
    if dosing_result.success and dosing_result.data.dosing_regimens:
        logger.info(f"  ✓ Found {len(dosing_result.data.dosing_regimens)} dosing regimens")
        all_pages.extend(dosing_result.pages_used)
    else:
        logger.info("  ○ No dosing regimens extracted")
    
    # 11. Extract visit windows (Phase 4)
    logger.info("Step 11/13: Extracting visit windows...")
    visit_result = extract_visit_windows(
        pdf_path=pdf_path,
        model=model,
        use_llm=enable_llm,
        soa_data=soa_data,
    )
    
    if visit_result.success and visit_result.data.visit_windows:
        logger.info(f"  ✓ Found {len(visit_result.data.visit_windows)} visit windows")
        all_pages.extend(visit_result.pages_used)
    else:
        logger.info("  ○ No visit windows extracted")
    
    # 12. Extract stratification/randomization (Phase 4)
    logger.info("Step 12/13: Extracting stratification scheme...")
    strat_result = extract_stratification(
        pdf_path=pdf_path,
        model=model,
        use_llm=enable_llm,
    )
    
    if strat_result.success and strat_result.data.randomization_scheme:
        scheme = strat_result.data.randomization_scheme
        logger.info(f"  ✓ Found randomization: {scheme.ratio}, {len(scheme.stratification_factors)} factors")
        all_pages.extend(strat_result.pages_used)
    else:
        logger.info("  ○ No randomization scheme extracted")
    
    # 13. Extract sampling density (Phase 5)
    logger.info("Step 13/13: Extracting sampling density...")
    sampling_result = extract_sampling_density(
        pdf_path=pdf_path,
        model=model,
        use_llm=enable_llm,
    )
    
    if sampling_result.success and sampling_result.data.sampling_constraints:
        logger.info(f"  ✓ Found {len(sampling_result.data.sampling_constraints)} sampling constraints")
        all_pages.extend(sampling_result.pages_used)
    else:
        logger.info("  ○ No additional sampling constraints found")
    
    # Merge all results
    merged_data = ExecutionModelData()
    
    if anchor_result.data:
        merged_data = merged_data.merge(anchor_result.data)
    if repetition_result.data:
        merged_data = merged_data.merge(repetition_result.data)
    if classification_result.data:
        merged_data = merged_data.merge(classification_result.data)
    if crossover_result.data:
        merged_data = merged_data.merge(crossover_result.data)
    if traversal_result.data:
        merged_data = merged_data.merge(traversal_result.data)
    if footnote_result.data:
        merged_data = merged_data.merge(footnote_result.data)
    # Phase 3 merges
    if endpoint_result.data:
        merged_data = merged_data.merge(endpoint_result.data)
    if variable_result.data:
        merged_data = merged_data.merge(variable_result.data)
    if state_machine_result.data:
        merged_data = merged_data.merge(state_machine_result.data)
    # Phase 4 merges
    if dosing_result.data:
        merged_data = merged_data.merge(dosing_result.data)
    if visit_result.data:
        merged_data = merged_data.merge(visit_result.data)
    if strat_result.data:
        merged_data = merged_data.merge(strat_result.data)
    # Phase 5 merge
    if sampling_result.data:
        merged_data = merged_data.merge(sampling_result.data)
    
    # Determine success
    has_data = (
        len(merged_data.time_anchors) > 0 or
        len(merged_data.repetitions) > 0 or
        len(merged_data.execution_types) > 0 or
        len(merged_data.traversal_constraints) > 0 or
        merged_data.crossover_design is not None or
        len(merged_data.footnote_conditions) > 0 or
        len(merged_data.endpoint_algorithms) > 0 or
        len(merged_data.derived_variables) > 0 or
        merged_data.state_machine is not None or
        len(merged_data.dosing_regimens) > 0 or
        len(merged_data.visit_windows) > 0 or
        merged_data.randomization_scheme is not None
    )
    
    result = ExecutionModelResult(
        success=has_data,
        data=merged_data,
        error="; ".join(errors) if errors and not has_data else None,
        pages_used=list(set(all_pages)),
        model_used=model,
    )
    
    # Save results if output_dir provided
    if output_dir and has_data:
        output_path = Path(output_dir) / "11_execution_model.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        logger.info(f"Saved execution model to {output_path}")
    
    logger.info("=" * 60)
    logger.info("Execution Model Extraction Complete")
    logger.info("=" * 60)
    
    return result


def enrich_usdm_with_execution_model(
    usdm_output: Dict[str, Any],
    execution_data: ExecutionModelData,
) -> Dict[str, Any]:
    """
    Enrich existing USDM output with execution model data.
    
    Adds execution semantics to USDM via extensionAttributes,
    maintaining full USDM compliance.
    
    Also applies structural integrity fixes:
    - FIX A: Extracts titration schedules from arm descriptions
    - FIX B: Creates instance bindings from USDM structure
    - FIX C: Deduplicates epochs, fixes visit window targets
    
    Args:
        usdm_output: Existing USDM JSON output
        execution_data: ExecutionModelData to add
        
    Returns:
        Enriched USDM output with execution model extensions
    """
    from .binding_extractor import (
        create_instance_bindings_from_usdm,
        extract_titration_from_arm,
        deduplicate_epochs,
        deduplicate_visit_windows,
        fix_visit_window_targets,
    )
    
    if not execution_data:
        return usdm_output
    
    enriched = dict(usdm_output)
    
    # Navigate to study designs
    study_designs = []
    if 'studyDesigns' in enriched:
        study_designs = enriched['studyDesigns']
    elif 'study' in enriched and 'versions' in enriched['study']:
        for version in enriched['study']['versions']:
            study_designs.extend(version.get('studyDesigns', []))
    
    for design in study_designs:
        # FIX C: Deduplicate epochs before adding extensions
        if 'epochs' in design:
            original_count = len(design['epochs'])
            design['epochs'] = deduplicate_epochs(design['epochs'])
            if len(design['epochs']) < original_count:
                logger.info(f"  Deduplicated epochs: {original_count} -> {len(design['epochs'])}")
        
        # FIX C + FIX 5: Deduplicate and fix visit windows
        if execution_data.visit_windows:
            vw_dicts = [vw.to_dict() for vw in execution_data.visit_windows]
            # First deduplicate (collapse duplicate EOS, etc.)
            vw_dicts = deduplicate_visit_windows(vw_dicts)
            # Then fix targets against encounters
            if design.get('encounters'):
                vw_dicts = fix_visit_window_targets(vw_dicts, design['encounters'])
            # Store fixed windows for later output
            execution_data._fixed_visit_windows = vw_dicts
        
        # FIX A: Extract titration from arm descriptions
        for arm in design.get('arms', []):
            titration = extract_titration_from_arm(arm)
            if titration:
                execution_data.titration_schedules.append(titration)
                logger.info(f"  Extracted titration schedule from arm: {arm.get('name')}")
        
        # FIX B: Create instance bindings dynamically
        if execution_data.repetitions and not execution_data.instance_bindings:
            bindings = create_instance_bindings_from_usdm(enriched, execution_data)
            execution_data.instance_bindings.extend(bindings)
            if bindings:
                logger.info(f"  Created {len(bindings)} instance bindings")
        
        # NEW: Run Reconciliation Layer to promote findings to core USDM
        # This promotes crossover→epochs/cells, resolves traversal→IDs, etc.
        try:
            reconciled_design, classified_issues, entity_maps = reconcile_usdm_with_execution_model(
                design, execution_data
            )
            # Update design in place with reconciled version
            design.update(reconciled_design)
            
            # Store entity maps for downstream use
            if entity_maps:
                design.setdefault('extensionAttributes', []).append(_create_extension_attribute(
                    "x-executionModel-entityMaps", entity_maps
                ))
            
            # Store classified issues (with severity levels)
            if classified_issues:
                design.setdefault('extensionAttributes', []).append(_create_extension_attribute(
                    "x-executionModel-classifiedIssues", classified_issues
                ))
                blocking = sum(1 for i in classified_issues if i.get('severity') == 'blocking')
                if blocking > 0:
                    logger.warning(f"  Reconciliation found {blocking} BLOCKING issues")
        except Exception as e:
            logger.warning(f"Reconciliation layer failed: {e}")
        
        # Add all execution extensions (remaining data not promoted to core)
        _add_execution_extensions(design, execution_data)
        
        # FIX 5: Run integrity validation before finalizing
        integrity_issues = validate_execution_model_integrity(execution_data, design)
        if integrity_issues:
            # Store issues as extension for downstream visibility
            design['extensionAttributes'].append(_create_extension_attribute(
                "x-executionModel-integrityIssues", integrity_issues
            ))
    
    return enriched


def _create_terminal_epoch(epoch_id: str, epoch_name: str) -> Dict[str, Any]:
    """
    FIX E: Create a terminal epoch (End of Study, Early Termination) when missing.
    
    These epochs are referenced by traversal constraints but may not exist in the 
    extracted schedule. This function creates them with proper USDM structure.
    """
    import uuid
    return {
        "id": epoch_id,
        "name": epoch_name,
        "description": f"{epoch_name} - terminal epoch for subject path completion",
        "sequenceNumber": 999,  # Terminal epochs are at the end
        "epochType": {
            "id": str(uuid.uuid4()),
            "code": "C99079" if "termination" in epoch_id else "C99078",
            "codeSystem": "http://www.cdisc.org",
            "decode": epoch_name,
            "instanceType": "Code"
        },
        "instanceType": "StudyEpoch"
    }


def _create_abstract_epoch(epoch_id: str, epoch_name: str) -> Dict[str, Any]:
    """
    FIX 2: Create an abstract epoch for traversal resolution.
    
    When traversal constraints reference abstract phases (RUN_IN, BASELINE, etc.)
    that don't match extracted SoA epochs, create placeholder epochs to maintain
    graph integrity.
    """
    import uuid
    
    # Map abstract names to CDISC epoch type codes
    epoch_codes = {
        'screening': 'C48262',      # Screening
        'run_in': 'C98779',         # Run-In
        'baseline': 'C25213',       # Baseline
        'treatment': 'C25532',      # Treatment
        'maintenance': 'C82517',    # Maintenance
        'follow_up': 'C48313',      # Follow-Up
        'washout': 'C48313',        # Washout (use Follow-Up code)
    }
    
    return {
        "id": epoch_id,
        "name": epoch_name,
        "description": f"{epoch_name} - auto-created from traversal constraint",
        "sequenceNumber": 50,  # Middle sequence for abstract epochs
        "epochType": {
            "id": str(uuid.uuid4()),
            "code": epoch_codes.get(epoch_id, "C25532"),
            "codeSystem": "http://www.cdisc.org",
            "decode": epoch_name,
            "instanceType": "Code"
        },
        "instanceType": "StudyEpoch"
    }


def _create_extension_attribute(name: str, value: Any) -> Dict[str, Any]:
    """
    Create a properly formatted USDM ExtensionAttribute per official schema.
    
    Per USDM dataStructure.yml, ExtensionAttribute supports:
    - valueString, valueBoolean, valueInteger for simple types
    - valueExtensionClass for complex nested structures
    
    For our execution model data (complex JSON), we serialize to valueString.
    """
    import uuid
    import json
    
    ext = {
        "id": str(uuid.uuid4()),
        "url": f"https://protocol2usdm.io/extensions/{name}",
        "instanceType": "ExtensionAttribute",
    }
    
    # Determine the appropriate value field based on type
    if isinstance(value, bool):
        ext["valueBoolean"] = value
    elif isinstance(value, int):
        ext["valueInteger"] = value
    elif isinstance(value, str):
        ext["valueString"] = value
    elif isinstance(value, (list, dict)):
        # Complex data - serialize as JSON string
        ext["valueString"] = json.dumps(value, ensure_ascii=False)
    else:
        # Fallback to string representation
        ext["valueString"] = str(value)
    
    return ext


def _add_execution_extensions(
    design: Dict[str, Any],
    execution_data: ExecutionModelData,
) -> None:
    """Add execution model extensions to a study design."""
    
    # FIX A: If crossover detected, update the BASE model (not just extension)
    # This ensures downstream consumers that only read base USDM behave correctly
    if execution_data.crossover_design and execution_data.crossover_design.is_crossover:
        design['model'] = {
            "id": "code_model_1",
            "code": "C49649",  # CDISC code for Crossover Study
            "codeSystem": "http://www.cdisc.org",
            "codeSystemVersion": "2024-09-27",
            "decode": "Crossover Study",
            "instanceType": "Code"
        }
        logger.info("Updated studyDesign.model to 'Crossover Study' based on crossover detection")
    
    # Initialize extensionAttributes if not present
    if 'extensionAttributes' not in design:
        design['extensionAttributes'] = []
    
    # Add time anchors
    if execution_data.time_anchors:
        design['extensionAttributes'].append(_create_extension_attribute(
            "x-executionModel-timeAnchors",
            [a.to_dict() for a in execution_data.time_anchors]
        ))
    
    # Add repetitions
    if execution_data.repetitions:
        design['extensionAttributes'].append(_create_extension_attribute(
            "x-executionModel-repetitions",
            [r.to_dict() for r in execution_data.repetitions]
        ))
    
    # Add sampling constraints
    if execution_data.sampling_constraints:
        design['extensionAttributes'].append(_create_extension_attribute(
            "x-executionModel-samplingConstraints",
            [s.to_dict() for s in execution_data.sampling_constraints]
        ))
    
    # Add execution type classifications to activities
    if execution_data.execution_types:
        exec_type_map = {
            et.activity_id: et.to_dict()
            for et in execution_data.execution_types
        }
        
        for activity in design.get('activities', []):
            activity_id = activity.get('id', '')
            activity_name = activity.get('name', '')
            
            # Match by ID or name
            exec_type = exec_type_map.get(activity_id) or exec_type_map.get(activity_name)
            
            if exec_type:
                if 'extensionAttributes' not in activity:
                    activity['extensionAttributes'] = []
                activity['extensionAttributes'].append(_create_extension_attribute(
                    "x-executionModel-executionType", exec_type
                ))
    
    # Phase 2: Add crossover design
    if execution_data.crossover_design:
        design['extensionAttributes'].append(_create_extension_attribute(
            "x-executionModel-crossoverDesign", execution_data.crossover_design.to_dict()
        ))
    
    # Phase 2: Add traversal constraints (using LLM-based entity resolution)
    if execution_data.traversal_constraints:
        # Get existing epoch and encounter IDs
        epoch_ids = {e.get('id') for e in design.get('epochs', [])}
        encounter_ids = {e.get('id') for e in design.get('encounters', [])}
        
        # Build basic epoch name mapping (exact matches only)
        epoch_names = {}
        for e in design.get('epochs', []):
            epoch_id = e.get('id')
            epoch_name = e.get('name', '')
            normalized = epoch_name.upper().replace(' ', '_').replace('-', '_')
            epoch_names[normalized] = epoch_id
            epoch_names[epoch_name.upper()] = epoch_id
        
        # Collect abstract concepts that need LLM resolution
        abstract_concepts = set()
        for tc in execution_data.traversal_constraints:
            for step in tc.required_sequence:
                step_upper = step.upper().replace(' ', '_')
                if step not in epoch_ids and step not in encounter_ids and step_upper not in epoch_names:
                    # Not a direct match - needs resolution
                    if step_upper not in ['END_OF_STUDY', 'EOS', 'STUDY_COMPLETION', 
                                          'EARLY_TERMINATION', 'ET', 'DISCONTINUED']:
                        abstract_concepts.add(step_upper)
        
        # Use LLM-based EntityResolver for abstract concepts
        llm_mappings = {}
        if abstract_concepts:
            try:
                resolver = EntityResolver()
                context = create_resolution_context_from_design(design)
                mappings = resolver.resolve_epoch_concepts(list(abstract_concepts), context)
                for concept, mapping in mappings.items():
                    if mapping:
                        llm_mappings[concept] = mapping.resolved_id
                        logger.info(f"LLM resolved '{concept}' → '{mapping.resolved_name}' (confidence: {mapping.confidence:.2f})")
                    else:
                        logger.warning(f"LLM could not resolve '{concept}' to any epoch")
                
                # Store mappings as extension attribute for transparency
                if resolver.get_all_mappings():
                    design['extensionAttributes'].append(_create_extension_attribute(
                        "x-executionModel-entityMappings", resolver.export_mappings()
                    ))
            except Exception as e:
                logger.warning(f"LLM entity resolution failed: {e}, falling back to skip")
        
        # Resolve traversal constraints to use real IDs
        resolved_constraints = []
        for tc in execution_data.traversal_constraints:
            resolved_sequence = []
            for step in tc.required_sequence:
                step_upper = step.upper().replace(' ', '_')
                
                # Check if already a valid ID
                if step in epoch_ids or step in encounter_ids:
                    resolved_sequence.append(step)
                # Try exact name match
                elif step_upper in epoch_names:
                    resolved_sequence.append(epoch_names[step_upper])
                # Try LLM-resolved mapping
                elif step_upper in llm_mappings:
                    resolved_sequence.append(llm_mappings[step_upper])
                # Handle terminal epochs
                elif step_upper in ['END_OF_STUDY', 'EOS', 'STUDY_COMPLETION']:
                    new_epoch = _create_terminal_epoch('end_of_study', 'End of Study')
                    if 'epochs' not in design:
                        design['epochs'] = []
                    design['epochs'].append(new_epoch)
                    epoch_ids.add(new_epoch['id'])
                    resolved_sequence.append(new_epoch['id'])
                elif step_upper in ['EARLY_TERMINATION', 'ET', 'DISCONTINUED']:
                    new_epoch = _create_terminal_epoch('early_termination', 'Early Termination')
                    if 'epochs' not in design:
                        design['epochs'] = []
                    design['epochs'].append(new_epoch)
                    epoch_ids.add(new_epoch['id'])
                    resolved_sequence.append(new_epoch['id'])
                else:
                    # Skip unresolvable - don't create orphans
                    logger.warning(f"Skipping unresolvable traversal step '{step}'")
            
            # Update the constraint with resolved sequence
            resolved_tc = tc.to_dict()
            resolved_tc['requiredSequence'] = resolved_sequence
            resolved_constraints.append(resolved_tc)
        
        design['extensionAttributes'].append(_create_extension_attribute(
            "x-executionModel-traversalConstraints", resolved_constraints
        ))
    
    # Phase 2: Add footnote conditions
    if execution_data.footnote_conditions:
        design['extensionAttributes'].append(_create_extension_attribute(
            "x-executionModel-footnoteConditions",
            [fc.to_dict() for fc in execution_data.footnote_conditions]
        ))
    
    # Phase 3: Add endpoint algorithms
    if execution_data.endpoint_algorithms:
        design['extensionAttributes'].append(_create_extension_attribute(
            "x-executionModel-endpointAlgorithms",
            [ep.to_dict() for ep in execution_data.endpoint_algorithms]
        ))
    
    # Phase 3: Add derived variables
    if execution_data.derived_variables:
        design['extensionAttributes'].append(_create_extension_attribute(
            "x-executionModel-derivedVariables",
            [dv.to_dict() for dv in execution_data.derived_variables]
        ))
    
    # Phase 3: Add state machine
    if execution_data.state_machine:
        design['extensionAttributes'].append(_create_extension_attribute(
            "x-executionModel-stateMachine", execution_data.state_machine.to_dict()
        ))
    
    # Phase 4: Add dosing regimens
    if execution_data.dosing_regimens:
        design['extensionAttributes'].append(_create_extension_attribute(
            "x-executionModel-dosingRegimens",
            [dr.to_dict() for dr in execution_data.dosing_regimens]
        ))
    
    # Phase 4: Add visit windows (use fixed/deduped if available)
    if execution_data.visit_windows:
        vw_output = getattr(execution_data, '_fixed_visit_windows', None)
        if vw_output is None:
            vw_output = [vw.to_dict() for vw in execution_data.visit_windows]
        design['extensionAttributes'].append(_create_extension_attribute(
            "x-executionModel-visitWindows", vw_output
        ))
    
    # Phase 4: Add randomization scheme
    if execution_data.randomization_scheme:
        design['extensionAttributes'].append(_create_extension_attribute(
            "x-executionModel-randomizationScheme", execution_data.randomization_scheme.to_dict()
        ))
    
    # FIX 1: Ensure all bound repetitions exist before processing bindings
    # Build map of existing repetitions
    rep_id_map = {r.id: r for r in execution_data.repetitions}
    
    # Check bindings and auto-create missing repetitions
    if execution_data.activity_bindings:
        for ab in execution_data.activity_bindings:
            if ab.repetition_id and ab.repetition_id not in rep_id_map:
                # Create a placeholder repetition from binding metadata
                from .schema import Repetition, RepetitionType
                placeholder_rep = Repetition(
                    id=ab.repetition_id,
                    type=RepetitionType.DAILY,
                    interval="P1D",
                    count=ab.expected_occurrences if ab.expected_occurrences else 1,
                    source_text=f"Auto-generated from binding: {ab.source_text}",
                )
                execution_data.repetitions.append(placeholder_rep)
                rep_id_map[ab.repetition_id] = placeholder_rep
                logger.info(f"Auto-created missing repetition: {ab.repetition_id}")
    
    # FIX C: Add activity bindings for tight coupling (with ID resolution)
    if execution_data.activity_bindings:
        # Build name->UUID mapping from actual USDM activities
        activity_uuid_map = {}
        for activity in design.get('activities', []):
            act_id = activity.get('id', '')
            act_name = activity.get('name', '').lower()
            activity_uuid_map[act_name] = act_id
            # Also map normalized versions
            normalized = re.sub(r'[^a-z0-9]', '', act_name)
            activity_uuid_map[normalized] = act_id
        
        # Build repetition ID set for validation (now includes auto-created ones)
        rep_id_set = {r.id for r in execution_data.repetitions}
        
        # Resolve binding IDs
        resolved_bindings = []
        for ab in execution_data.activity_bindings:
            ab_dict = ab.to_dict()
            
            # Resolve activity ID to UUID
            activity_key = ab.activity_name.lower() if ab.activity_name else ab.activity_id.lower()
            normalized_key = re.sub(r'[^a-z0-9]', '', activity_key)
            
            resolved_uuid = activity_uuid_map.get(activity_key) or activity_uuid_map.get(normalized_key)
            if resolved_uuid:
                ab_dict['activityId'] = resolved_uuid
            
            # All repetitions should now exist (we auto-created missing ones above)
            resolved_bindings.append(ab_dict)
        
        if resolved_bindings:
            design['extensionAttributes'].append(_create_extension_attribute(
                "x-executionModel-activityBindings", resolved_bindings
            ))
    
    # FIX C: Also add bindings directly to activities for easy lookup
    if execution_data.activity_bindings:
        binding_map = {
            ab.activity_id: ab.to_dict()
            for ab in execution_data.activity_bindings
        }
        # Also map by activity name for flexible matching
        for ab in execution_data.activity_bindings:
            if ab.activity_name:
                binding_map[ab.activity_name] = ab.to_dict()
        
        for activity in design.get('activities', []):
            activity_id = activity.get('id', '')
            activity_name = activity.get('name', '')
            
            binding = binding_map.get(activity_id) or binding_map.get(activity_name)
            if binding:
                if 'extensionAttributes' not in activity:
                    activity['extensionAttributes'] = []
                activity['extensionAttributes'].append(_create_extension_attribute(
                    "x-executionModel-binding", binding
                ))
    
    # FIX A: Add titration schedules (operationalized dose transitions)
    if execution_data.titration_schedules:
        design['extensionAttributes'].append(_create_extension_attribute(
            "x-executionModel-titrationSchedules",
            [ts.to_dict() for ts in execution_data.titration_schedules]
        ))
    
    # FIX B: Add instance bindings (repetition → ScheduledActivityInstance)
    if execution_data.instance_bindings:
        design['extensionAttributes'].append(_create_extension_attribute(
            "x-executionModel-instanceBindings",
            [ib.to_dict() for ib in execution_data.instance_bindings]
        ))
    
    # FIX 3: Add analysis windows
    if execution_data.analysis_windows:
        design['extensionAttributes'].append(_create_extension_attribute(
            "x-executionModel-analysisWindows",
            [aw.to_dict() for aw in execution_data.analysis_windows]
        ))


def validate_execution_model_integrity(
    execution_data: ExecutionModelData,
    design: Dict[str, Any],
) -> List[str]:
    """
    FIX 5: Post-combine integrity validator.
    
    Checks for internal consistency issues before writing USDM:
    1. All binding.repetitionId references exist in repetitions list
    2. All traversal.requiredSequence items are valid epoch UUIDs
    3. Titration schedules have explicit day bounds
    4. Day offsets have correct sign semantics
    5. No duplicate epoch/visit window definitions
    
    Returns list of issues found (empty = valid).
    """
    issues = []
    
    # 1. Binding → Repetition integrity
    rep_ids = {r.id for r in execution_data.repetitions}
    for ab in execution_data.activity_bindings:
        if ab.repetition_id and ab.repetition_id not in rep_ids:
            issues.append(f"INTEGRITY: Binding '{ab.id}' references missing repetition '{ab.repetition_id}'")
    
    # 2. Traversal → Epoch integrity (check resolved constraints in design)
    epoch_ids = {e.get('id') for e in design.get('epochs', [])}
    # Check the resolved traversal constraints from extension attributes
    for ext in design.get('extensionAttributes', []):
        url = ext.get('url', '')
        if 'traversalConstraints' in url:
            import json
            resolved_constraints = json.loads(ext.get('valueString', '[]'))
            for tc in resolved_constraints:
                for step in tc.get('requiredSequence', []):
                    # Check if step is a valid epoch ID (should be after resolution)
                    is_in_epochs = step in epoch_ids
                    if not is_in_epochs and not step.startswith('end_of_study') and not step.startswith('early_termination'):
                        issues.append(f"INTEGRITY: Traversal step '{step}' is not a valid epoch ID")
    
    # 3. Titration schedule bounds check
    for ts in execution_data.titration_schedules:
        for dl in ts.dose_levels:
            if dl.start_day is None:
                issues.append(f"INTEGRITY: Titration dose '{dl.dose_value}' missing start_day")
    
    # 4. Day offset sign validation
    for rep in execution_data.repetitions:
        if rep.start_offset and rep.source_text:
            # Check if source mentions negative days but offset is positive
            if 'day -' in rep.source_text.lower() or 'day−' in rep.source_text.lower():
                if rep.start_offset and not rep.start_offset.startswith('-'):
                    issues.append(f"INTEGRITY: Repetition '{rep.id}' has positive offset but source mentions negative day")
    
    # 5. Duplicate epoch check
    epoch_names_seen = set()
    for e in design.get('epochs', []):
        name = e.get('name', '').lower()
        if name in epoch_names_seen:
            issues.append(f"INTEGRITY: Duplicate epoch name '{name}'")
        epoch_names_seen.add(name)
    
    # Log summary
    if issues:
        logger.warning(f"Execution model integrity check found {len(issues)} issues")
        for issue in issues[:5]:  # Log first 5
            logger.warning(f"  {issue}")
    else:
        logger.info("Execution model integrity check passed")
    
    return issues


def create_execution_model_summary(
    execution_data: ExecutionModelData,
) -> str:
    """
    Create a human-readable summary of execution model extractions.
    
    Useful for logging and debugging.
    """
    lines = ["Execution Model Summary", "=" * 40]
    
    # Time anchors
    lines.append(f"\nTime Anchors ({len(execution_data.time_anchors)}):")
    for anchor in execution_data.time_anchors:
        lines.append(f"  • {anchor.anchor_type.value}: {anchor.definition}")
        if anchor.source_text:
            lines.append(f"    Source: \"{anchor.source_text[:60]}...\"")
    
    # Repetitions
    lines.append(f"\nRepetitions ({len(execution_data.repetitions)}):")
    for rep in execution_data.repetitions:
        interval_str = f", interval={rep.interval}" if rep.interval else ""
        lines.append(f"  • {rep.type.value}{interval_str}")
        if rep.source_text:
            lines.append(f"    Source: \"{rep.source_text[:60]}...\"")
    
    # Sampling constraints
    lines.append(f"\nSampling Constraints ({len(execution_data.sampling_constraints)}):")
    for sc in execution_data.sampling_constraints:
        lines.append(f"  • {sc.activity_id}: min {sc.min_per_window} per window")
        if sc.timepoints:
            lines.append(f"    Timepoints: {', '.join(sc.timepoints[:8])}...")
    
    # Execution types
    lines.append(f"\nExecution Types ({len(execution_data.execution_types)}):")
    type_groups = {}
    for et in execution_data.execution_types:
        type_name = et.execution_type.value
        if type_name not in type_groups:
            type_groups[type_name] = []
        type_groups[type_name].append(et.activity_id)
    
    for type_name, activities in type_groups.items():
        lines.append(f"  {type_name}: {', '.join(activities[:5])}")
        if len(activities) > 5:
            lines.append(f"    ... and {len(activities) - 5} more")
    
    # Crossover design
    if execution_data.crossover_design:
        cd = execution_data.crossover_design
        lines.append(f"\nCrossover Design:")
        lines.append(f"  • Periods: {cd.num_periods}")
        lines.append(f"  • Sequences: {', '.join(cd.sequences) if cd.sequences else 'N/A'}")
        if cd.washout_duration:
            lines.append(f"  • Washout: {cd.washout_duration}")
    
    # Traversal constraints
    lines.append(f"\nTraversal Constraints ({len(execution_data.traversal_constraints)}):")
    for tc in execution_data.traversal_constraints:
        lines.append(f"  • Sequence: {' → '.join(tc.required_sequence[:6])}")
        if len(tc.required_sequence) > 6:
            lines.append(f"    ... and {len(tc.required_sequence) - 6} more epochs")
        if tc.mandatory_visits:
            lines.append(f"  • Mandatory: {', '.join(tc.mandatory_visits[:5])}")
    
    # Footnote conditions
    lines.append(f"\nFootnote Conditions ({len(execution_data.footnote_conditions)}):")
    for fc in execution_data.footnote_conditions[:5]:
        lines.append(f"  • [{fc.condition_type}] {fc.text[:50]}...")
    if len(execution_data.footnote_conditions) > 5:
        lines.append(f"    ... and {len(execution_data.footnote_conditions) - 5} more")
    
    # Phase 3: Endpoint algorithms
    lines.append(f"\nEndpoint Algorithms ({len(execution_data.endpoint_algorithms)}):")
    for ep in execution_data.endpoint_algorithms[:5]:
        lines.append(f"  • [{ep.endpoint_type.value}] {ep.name[:60]}")
        if ep.algorithm:
            lines.append(f"    Algorithm: {ep.algorithm[:50]}...")
    if len(execution_data.endpoint_algorithms) > 5:
        lines.append(f"    ... and {len(execution_data.endpoint_algorithms) - 5} more")
    
    # Phase 3: Derived variables
    lines.append(f"\nDerived Variables ({len(execution_data.derived_variables)}):")
    for dv in execution_data.derived_variables[:5]:
        lines.append(f"  • [{dv.variable_type.value}] {dv.name[:60]}")
        if dv.derivation_rule:
            lines.append(f"    Rule: {dv.derivation_rule[:50]}")
    if len(execution_data.derived_variables) > 5:
        lines.append(f"    ... and {len(execution_data.derived_variables) - 5} more")
    
    # Phase 3: State machine
    if execution_data.state_machine:
        sm = execution_data.state_machine
        lines.append(f"\nSubject State Machine:")
        lines.append(f"  • States: {len(sm.states)} ({', '.join(s.value for s in sm.states[:5])}...)")
        lines.append(f"  • Transitions: {len(sm.transitions)}")
        lines.append(f"  • Initial: {sm.initial_state.value}")
        lines.append(f"  • Terminal: {', '.join(s.value for s in sm.terminal_states[:4])}")
    
    # Phase 4: Dosing regimens
    lines.append(f"\nDosing Regimens ({len(execution_data.dosing_regimens)}):")
    for dr in execution_data.dosing_regimens[:5]:
        doses = ", ".join(f"{d.amount}{d.unit}" for d in dr.dose_levels[:3])
        lines.append(f"  • {dr.treatment_name}: {doses} {dr.frequency.value} ({dr.route.value})")
    if len(execution_data.dosing_regimens) > 5:
        lines.append(f"    ... and {len(execution_data.dosing_regimens) - 5} more")
    
    # Phase 4: Visit windows
    lines.append(f"\nVisit Windows ({len(execution_data.visit_windows)}):")
    for vw in execution_data.visit_windows[:8]:
        window_str = f"±{vw.window_before}/{vw.window_after}d" if vw.window_before or vw.window_after else ""
        lines.append(f"  • {vw.visit_name}: Day {vw.target_day} {window_str}")
    if len(execution_data.visit_windows) > 8:
        lines.append(f"    ... and {len(execution_data.visit_windows) - 8} more")
    
    # Phase 4: Randomization scheme
    if execution_data.randomization_scheme:
        rs = execution_data.randomization_scheme
        lines.append(f"\nRandomization Scheme:")
        lines.append(f"  • Ratio: {rs.ratio}")
        lines.append(f"  • Method: {rs.method}")
        if rs.stratification_factors:
            factors = ", ".join(f.name for f in rs.stratification_factors[:4])
            lines.append(f"  • Stratification: {factors}")
    
    return "\n".join(lines)
