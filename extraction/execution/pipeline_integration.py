"""
Pipeline Integration for Execution Model Extractors

Provides functions to integrate execution model extraction into the
existing Protocol2USDMv3 pipeline without breaking existing functionality.

The execution model extraction is additive - it enriches existing USDM
output with execution semantics via extensionAttributes.
"""

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Callable

from .schema import ExecutionModelData, ExecutionModelResult, ExecutionModelExtension
from core.reconciliation.activity_reconciler import _synonym_normalize, CLINICAL_SYNONYMS
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
from .execution_model_promoter import ExecutionModelPromoter, promote_execution_model

from .processing_warnings import get_processing_warnings, _add_processing_warning

logger = logging.getLogger(__name__)


_DEFAULT_MAX_WORKERS = 6


def _run_sub_extractor(
    name: str,
    fn: Callable[..., Any],
    kwargs: Dict[str, Any],
) -> Tuple[str, Any]:
    """Run a single sub-extractor, returning (name, result).

    Exceptions are caught so one failure doesn't kill the whole wave.
    """
    try:
        return name, fn(**kwargs)
    except Exception as exc:
        logger.error(f"Sub-extractor '{name}' raised: {exc}")
        return name, ExecutionModelResult(
            success=False,
            data=ExecutionModelData(),
            error=str(exc),
            pages_used=[],
            model_used=kwargs.get("model", ""),
        )


def extract_execution_model(
    pdf_path: str,
    model: str = "gemini-2.5-pro",
    activities: Optional[List[Dict[str, Any]]] = None,
    use_llm: bool = True,
    skip_llm: bool = False,
    sap_path: Optional[str] = None,
    soa_data: Optional[Dict[str, Any]] = None,
    output_dir: Optional[str] = None,
    parallel: bool = True,
    max_workers: Optional[int] = None,
    pipeline_context: Optional[Any] = None,
) -> ExecutionModelResult:
    """
    Extract complete execution model from a protocol PDF.
    
    This is the main entry point for execution model extraction.
    It runs all sub-extractors and merges results.

    When ``parallel=True`` (default), independent sub-extractors run
    concurrently in two waves:
      - **Wave 1** (12 extractors): all independent sub-extractors
      - **Wave 2** (1 extractor): state machine (depends on traversal + crossover)

    Set ``parallel=False`` to fall back to sequential execution (useful
    for debugging or when LLM providers have strict rate limits).
    
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
        parallel: Run independent sub-extractors concurrently (default True)
        max_workers: Max threads for parallel execution (default 6)
        
    Returns:
        ExecutionModelResult with combined ExecutionModelData
    """
    logger.info("=" * 60)
    logger.info("Starting Execution Model Extraction")
    logger.info("=" * 60)
    
    if sap_path:
        logger.info(f"SAP document provided: {sap_path}")
        if not Path(sap_path).exists():
            logger.warning(f"SAP file not found: {sap_path}")
            sap_path = None
    
    enable_llm = use_llm and not skip_llm
    
    # Extract SoA context once — shared by all sub-extractors
    soa_context = extract_soa_context(soa_data)
    if soa_context.has_epochs() or soa_context.has_encounters():
        logger.info(f"SoA context available: {soa_context.get_summary()}")
    
    soa_footnotes = soa_context.footnotes if soa_context.has_footnotes() else None

    # ── Define all sub-extractor tasks ────────────────────────────────
    # Each entry: (name, callable, kwargs_dict)
    wave1_tasks: List[Tuple[str, Callable, Dict[str, Any]]] = [
        ("time_anchors", extract_time_anchors, dict(
            pdf_path=pdf_path, model=model, use_llm=enable_llm,
            existing_encounters=soa_context.encounters if soa_context.has_encounters() else None,
            existing_epochs=soa_context.epochs if soa_context.has_epochs() else None,
            pipeline_context=pipeline_context,
        )),
        ("repetitions", extract_repetitions, dict(
            pdf_path=pdf_path, model=model, use_llm=enable_llm,
            existing_activities=soa_context.activities if soa_context.has_activities() else None,
            existing_encounters=soa_context.encounters if soa_context.has_encounters() else None,
        )),
        ("execution_types", classify_execution_types, dict(
            pdf_path=pdf_path,
            activities=activities or (soa_context.activities if soa_context.has_activities() else None),
            model=model, use_llm=enable_llm,
        )),
        ("crossover", extract_crossover_design, dict(
            pdf_path=pdf_path, model=model, use_llm=enable_llm,
            existing_epochs=soa_context.epochs if soa_context.has_epochs() else None,
        )),
        ("traversal", extract_traversal_constraints, dict(
            pdf_path=pdf_path, model=model, use_llm=enable_llm,
            existing_epochs=soa_context.epochs if soa_context.has_epochs() else None,
        )),
        ("footnotes", extract_footnote_conditions, dict(
            pdf_path=pdf_path, model=model, use_llm=enable_llm,
            footnotes=soa_footnotes,
            existing_activities=soa_context.activities if soa_context.has_activities() else None,
        )),
        ("endpoints", extract_endpoint_algorithms, dict(
            pdf_path=pdf_path, model=model, use_llm=enable_llm,
            sap_path=sap_path,
        )),
        ("derived_vars", extract_derived_variables, dict(
            pdf_path=pdf_path, model=model, use_llm=enable_llm,
            sap_path=sap_path,
        )),
        ("dosing", extract_dosing_regimens, dict(
            pdf_path=pdf_path, model=model, use_llm=enable_llm,
            existing_interventions=None,
            existing_arms=soa_context.arms if soa_context.arms else None,
        )),
        ("visit_windows", extract_visit_windows, dict(
            pdf_path=pdf_path, model=model, use_llm=enable_llm,
            soa_data=soa_data,
        )),
        ("stratification", extract_stratification, dict(
            pdf_path=pdf_path, model=model, use_llm=enable_llm,
        )),
        ("sampling", extract_sampling_density, dict(
            pdf_path=pdf_path, model=model, use_llm=enable_llm,
        )),
    ]

    # ── Execute Wave 1 ────────────────────────────────────────────────
    results: Dict[str, Any] = {}
    t0 = time.monotonic()

    workers = max_workers or int(os.environ.get("EXEC_MAX_WORKERS", _DEFAULT_MAX_WORKERS))

    if parallel and len(wave1_tasks) > 1:
        logger.info(f"Running {len(wave1_tasks)} sub-extractors in parallel (max_workers={workers})")
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_run_sub_extractor, name, fn, kwargs): name
                for name, fn, kwargs in wave1_tasks
            }
            for future in as_completed(futures):
                name, result = future.result()
                results[name] = result
    else:
        logger.info(f"Running {len(wave1_tasks)} sub-extractors sequentially")
        for name, fn, kwargs in wave1_tasks:
            _, result = _run_sub_extractor(name, fn, kwargs)
            results[name] = result

    wave1_elapsed = time.monotonic() - t0
    logger.info(f"Wave 1 complete: {len(wave1_tasks)} sub-extractors in {wave1_elapsed:.1f}s")

    # ── Log Wave 1 results ────────────────────────────────────────────
    _log_sub_result("time_anchors", results.get("time_anchors"))
    _log_sub_result("repetitions", results.get("repetitions"))
    _log_sub_result("execution_types", results.get("execution_types"))
    _log_sub_result("crossover", results.get("crossover"))
    _log_sub_result("traversal", results.get("traversal"))
    _log_sub_result("footnotes", results.get("footnotes"))
    _log_sub_result("endpoints", results.get("endpoints"))
    _log_sub_result("derived_vars", results.get("derived_vars"))
    _log_sub_result("dosing", results.get("dosing"))
    _log_sub_result("visit_windows", results.get("visit_windows"))
    _log_sub_result("stratification", results.get("stratification"))
    _log_sub_result("sampling", results.get("sampling"))

    # ── Execute Wave 2: state machine (depends on traversal + crossover) ──
    t1 = time.monotonic()
    traversal_result = results.get("traversal")
    crossover_result = results.get("crossover")

    traversal_for_sm = None
    if traversal_result and traversal_result.success and traversal_result.data.traversal_constraints:
        traversal_for_sm = traversal_result.data.traversal_constraints[0]

    crossover_for_sm = None
    if crossover_result and crossover_result.success and crossover_result.data.crossover_design:
        crossover_for_sm = crossover_result.data.crossover_design

    _, sm_result = _run_sub_extractor("state_machine", generate_state_machine, dict(
        pdf_path=pdf_path, model=model, use_llm=enable_llm,
        traversal=traversal_for_sm, crossover=crossover_for_sm,
        existing_epochs=soa_context.epochs if soa_context else None,
    ))
    results["state_machine"] = sm_result
    _log_sub_result("state_machine", sm_result)

    wave2_elapsed = time.monotonic() - t1
    total_elapsed = time.monotonic() - t0
    logger.info(f"Wave 2 complete: state machine in {wave2_elapsed:.1f}s (total: {total_elapsed:.1f}s)")

    # ── Merge all results ─────────────────────────────────────────────
    all_pages: List[int] = []
    errors: List[str] = []
    merged_data = ExecutionModelData()

    for name, res in results.items():
        if res is None:
            continue
        if hasattr(res, 'pages_used') and res.pages_used:
            all_pages.extend(res.pages_used)
        if hasattr(res, 'data') and res.data:
            merged_data = merged_data.merge(res.data)
        if hasattr(res, 'success') and not res.success and hasattr(res, 'error') and res.error:
            errors.append(f"{name}: {res.error}")

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
    logger.info(f"Execution Model Extraction Complete ({total_elapsed:.1f}s)")
    logger.info("=" * 60)
    
    return result


def _log_sub_result(name: str, result: Any) -> None:
    """Log the outcome of a single sub-extractor."""
    if result is None:
        logger.warning(f"  ✗ {name}: no result")
        return
    if not hasattr(result, 'success'):
        return
    if not result.success:
        err = getattr(result, 'error', 'unknown')
        logger.warning(f"  ✗ {name}: {err}")
        return
    data = getattr(result, 'data', None)
    if data is None:
        logger.info(f"  ○ {name}: no data")
        return
    # Count entities for logging
    counts = []
    for attr in ('time_anchors', 'repetitions', 'execution_types',
                 'traversal_constraints', 'footnote_conditions',
                 'endpoint_algorithms', 'derived_variables',
                 'dosing_regimens', 'visit_windows', 'sampling_constraints'):
        val = getattr(data, attr, None)
        if val and len(val) > 0:
            counts.append(f"{len(val)} {attr}")
    if getattr(data, 'crossover_design', None):
        counts.append("crossover_design")
    if getattr(data, 'state_machine', None):
        sm = data.state_machine
        counts.append(f"state_machine({len(sm.states)}s/{len(sm.transitions)}t)")
    if getattr(data, 'randomization_scheme', None):
        counts.append("randomization_scheme")
    if counts:
        logger.info(f"  ✓ {name}: {', '.join(counts)}")
    else:
        logger.info(f"  ○ {name}: empty")


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
        
        # NEW: Promote execution model to core USDM (not just extensions)
        # This ensures downstream consumers can use core USDM without parsing extensions
        try:
            # Get study_version for Administration entities
            study_version = None
            if 'study' in enriched and 'versions' in enriched['study']:
                study_version = enriched['study']['versions'][0]
            
            if study_version:
                promoted_design, promoted_version, promotion_result = promote_execution_model(
                    design, study_version, execution_data
                )
                design.update(promoted_design)
                study_version.update(promoted_version)
                
                if promotion_result.anchors_created > 0 or promotion_result.instances_created > 0:
                    logger.info(f"  Promoted to core: {promotion_result.anchors_created} anchors, "
                               f"{promotion_result.instances_created} instances, "
                               f"{promotion_result.administrations_created} administrations")
                
                if promotion_result.references_fixed > 0:
                    logger.info(f"  Fixed {promotion_result.references_fixed} dangling timing references")
                
                # Store any promotion issues
                if promotion_result.issues:
                    design.setdefault('extensionAttributes', []).append(_create_extension_attribute(
                        "x-executionModel-promotionIssues", promotion_result.issues
                    ))
        except Exception as e:
            logger.warning(f"Execution model promotion failed: {e}")
        
        # Add all execution extensions (remaining data not promoted to core)
        _add_execution_extensions(design, execution_data)
        
        # NEW: Propagate timing windows to encounters for downstream access
        # This addresses feedback that generators must traverse timing graphs
        windows_propagated = propagate_windows_to_encounters(design)
        if windows_propagated > 0:
            logger.info(f"  Propagated timing windows to {windows_propagated} encounters")
        
        # FIX 5: Run integrity validation before finalizing
        integrity_issues = validate_execution_model_integrity(execution_data, design)
        if integrity_issues:
            # Store issues as extension for downstream visibility
            design['extensionAttributes'].append(_create_extension_attribute(
                "x-executionModel-integrityIssues", integrity_issues
            ))
        
        # NEW (P2): Add unified typed ExecutionModelExtension
        # This outputs the full execution model as a typed structure (not JSON string)
        # alongside the existing x-executionModel-* extensions for backward compatibility
        typed_extension = ExecutionModelExtension(
            extractionTimestamp=datetime.now(timezone.utc).isoformat(),
            data=execution_data,
            integrityIssues=[{"issue": i} for i in integrity_issues] if integrity_issues else [],
        )
        design.setdefault('extensionAttributes', []).append(typed_extension.to_usdm_extension())
        logger.info("  Added unified typed ExecutionModelExtension")
    
    # NOTE: Extension ref resolution (activityId, footnoteId) now runs
    # post-reconciliation in combiner.py with old→new ID mapping.
    
    return enriched


def _resolve_to_epoch_id(
    label: str,
    epoch_ids: set,
    epoch_names: Dict[str, str],
    llm_mappings: Dict[str, str],
    design: Dict[str, Any]
) -> Optional[str]:
    """
    Resolve any epoch label/name/placeholder to an actual epoch ID.
    Auto-creates terminal epochs if needed. Returns None if unresolvable.
    """
    label_upper = label.upper().replace(' ', '_').replace('-', '_')
    
    # Already a valid ID
    if label in epoch_ids:
        return label
    
    # Exact name match
    if label_upper in epoch_names:
        return epoch_names[label_upper]
    
    # LLM-resolved mapping
    if label_upper in llm_mappings:
        return llm_mappings[label_upper]
    
    # Terminal epochs - auto-create
    if label_upper in ['END_OF_STUDY', 'EOS', 'STUDY_COMPLETION', 'STUDY_END']:
        new_epoch = _create_terminal_epoch('epoch_end_of_study', 'End of Study')
        if 'epochs' not in design:
            design['epochs'] = []
        # Check if already exists
        existing = [e for e in design['epochs'] if 'end_of_study' in e.get('id', '').lower()]
        if existing:
            return existing[0]['id']
        design['epochs'].append(new_epoch)
        return new_epoch['id']
    
    if label_upper in ['EARLY_TERMINATION', 'ET', 'DISCONTINUED', 'WITHDRAWAL']:
        # Check if already exists in SoA epochs - don't create if not present
        # SoA header_structure is authoritative for epochs
        existing = [e for e in design.get('epochs', []) 
                   if 'early_termination' in e.get('id', '').lower() 
                   or 'early termination' in e.get('name', '').lower()]
        if existing:
            return existing[0]['id']
        # Don't create new terminal epochs - SoA is authoritative
        logger.debug(f"Skipping creation of 'Early Termination' epoch - not in SoA")
        return None
    
    # Fuzzy match existing epochs
    for epoch in design.get('epochs', []):
        epoch_name_lower = epoch.get('name', '').lower()
        if label.lower() in epoch_name_lower or epoch_name_lower in label.lower():
            return epoch['id']
    
    logger.warning(f"Could not resolve epoch label '{label}' to any ID")
    _add_processing_warning(
        category="epoch_resolution_failed",
        message=f"Could not resolve epoch label '{label}' to any ID",
        context="execution_model_promotion",
        details={'epoch_label': label}
    )
    return None


def _resolve_to_encounter_id(
    visit_name: str,
    encounter_ids: set,
    encounters: List[Dict[str, Any]],
    epochs: Optional[List[Dict[str, Any]]] = None,
) -> Optional[str]:
    """
    Resolve a visit name to an encounter ID.

    Resolution strategy (in order):
      1. Direct ID match
      2. Exact name match
      3. Substring containment
      4. Name-based pattern matching (keyword aliases)
      5. Numeric extraction (Week N, Visit N, Day N)
      6. **Epoch-based semantic matching** — cross-reference the epoch
         each encounter belongs to and match conceptual visit keywords
         (screening, end-of-study, follow-up, withdrawal, etc.) against
         epoch names.  This avoids blind positional guessing.
      7. Positional fallback (first/last encounter) only when no epochs
         are available or epoch matching fails.
      8. Silently skip out-of-SoA visits (very high visit numbers,
         safety follow-up, unscheduled, etc.)

    Returns None if unresolvable.
    """
    import re

    visit_lower = visit_name.lower().strip()

    # ---- Phase 0: Direct ID ----
    if visit_name in encounter_ids:
        return visit_name

    # ---- Phase 1: Exact name match ----
    for enc in encounters:
        if enc.get('name', '').lower() == visit_lower:
            return enc['id']

    # ---- Phase 2: Substring containment ----
    for enc in encounters:
        enc_name = enc.get('name', '').lower()
        if visit_lower in enc_name or enc_name in visit_lower:
            return enc['id']

    # ---- Phase 3: Name-based keyword aliases ----
    for enc in encounters:
        enc_name = enc.get('name', '').lower()

        # End of Study / EOS / Final Visit
        if any(x in visit_lower for x in ['end of study', 'eos', 'final visit', 'study completion', 'termination']):
            if any(x in enc_name for x in ['end', 'eos', 'final', 'termination', 'completion', 'last']):
                return enc['id']

        # Screening
        if 'screening' in visit_lower or 'screen' in visit_lower:
            if 'screen' in enc_name or 'day -' in enc_name or 'day-' in enc_name:
                return enc['id']

        # Day 1 / Baseline / Randomization
        if any(x in visit_lower for x in ['day 1', 'day1', 'baseline', 'randomization', 'randomisation']):
            if any(x in enc_name for x in ['day 1', 'day1', 'baseline', 'random', 'week 0', 'visit 1']):
                return enc['id']

        # Generic treatment-visit bucket from traversal constraints.
        if any(x in visit_lower for x in [
            'scheduled treatment visit',
            'scheduled treatment visits',
            'treatment visit',
            'treatment visits',
            'double-blind treatment visit',
            'double-blind treatment visits',
            'double blind treatment visit',
            'double blind treatment visits',
        ]):
            if 'treatment' in enc_name and not any(x in enc_name for x in ['end', 'follow', 'safety']):
                return enc['id']

        # Follow-up / Safety follow-up
        if 'follow' in visit_lower or 'safety' in visit_lower:
            if 'follow' in enc_name or 'safety' in enc_name:
                return enc['id']

        # End of Treatment / EOT
        if any(x in visit_lower for x in ['end of treatment', 'eot', 'treatment end']):
            if any(x in enc_name for x in ['end of treatment', 'eot', 'treatment end', 'last dose']):
                return enc['id']

    # ---- Phase 4: Numeric extraction (Week N / Visit N / Day N) ----
    visit_week_match = re.search(r'week\s*[i-]?\s*(\d+)', visit_lower)
    visit_num_match = re.search(r'visit\s*(\d+)', visit_lower)
    visit_day_match = re.search(r'day\s*(\d+)', visit_lower)

    if visit_week_match:
        week_num = visit_week_match.group(1)
        for enc in encounters:
            enc_name = enc.get('name', '').lower()
            if re.search(rf'week\s*[i-]?\s*{week_num}\b', enc_name):
                return enc['id']
            if f'({week_num})' in enc_name or f'i-{week_num}' in enc_name or f'-{week_num}' in enc_name:
                return enc['id']

    if visit_num_match:
        visit_num = visit_num_match.group(1)
        for enc in encounters:
            enc_name = enc.get('name', '').lower()
            if re.search(rf'visit\s*{visit_num}\b', enc_name):
                return enc['id']

    if visit_day_match:
        day_num = visit_day_match.group(1)
        for enc in encounters:
            enc_name = enc.get('name', '').lower()
            if re.search(rf'day\s*{day_num}\b', enc_name):
                return enc['id']

    # ---- Phase 5: Epoch-based semantic matching ----
    # Cross-reference the epoch that each encounter belongs to.
    # Map conceptual visit keywords → epoch name patterns, then return
    # the first/last encounter in the matching epoch.
    #
    # Concept → epoch-name patterns (any substring match):
    _VISIT_EPOCH_MAP = [
        # (visit keywords, epoch patterns, pick)
        # pick: 'first' = first encounter in epoch, 'last' = last encounter
        (['screen', 'enrol'],
         ['screen', 'enrol', 'eligib'],
         'first'),
        (['baseline', 'randomiz', 'randomi', 'day 1', 'day1'],
         ['random', 'baseline', 'treatment', 'allocat'],
         'first'),
        (['scheduled treatment visit', 'scheduled treatment visits',
          'treatment visit', 'treatment visits',
          'double-blind treatment visit', 'double-blind treatment visits',
          'double blind treatment visit', 'double blind treatment visits'],
         ['treatment', 'double-blind', 'double blind', 'maintenance'],
         'first'),
        (['end of treatment', 'eot', 'treatment end', 'last dose'],
         ['treatment', 'dosing', 'intervention'],
         'last'),
        (['end of study', 'eos', 'study completion', 'closure', 'final'],
         ['end of study', 'eos', 'closure', 'study closure', 'completion', 'scv'],
         'last'),
        (['follow', 'safety'],
         ['follow', 'safety', 'observ', 'post'],
         'first'),
        (['withdraw', 'discontinu', 'early termin', 'premature'],
         ['discontinu', 'withdraw', 'terminat', 'ptdv', 'premature'],
         'first'),
    ]

    if epochs:
        # Build epoch-id → epoch-name lookup
        epoch_name_map = {ep['id']: ep.get('name', '').lower() for ep in epochs}
        # Build epoch-id → sorted encounters (preserve SoA order)
        epoch_encounters: Dict[str, List[Dict[str, Any]]] = {}
        for enc in encounters:
            eid = enc.get('epochId')
            if eid:
                epoch_encounters.setdefault(eid, []).append(enc)

        for visit_keywords, epoch_patterns, pick in _VISIT_EPOCH_MAP:
            # Does the visit name match this concept?
            if not any(kw in visit_lower for kw in visit_keywords):
                continue
            # Find epochs whose name matches any epoch pattern
            for ep_id, ep_name in epoch_name_map.items():
                if any(pat in ep_name for pat in epoch_patterns):
                    enc_list = epoch_encounters.get(ep_id, [])
                    if enc_list:
                        chosen = enc_list[0] if pick == 'first' else enc_list[-1]
                        return chosen['id']

    # ---- Phase 6: Positional fallback (only when epochs unavailable) ----
    if encounters and not epochs:
        # Screening → first encounter (most protocols begin with screening)
        if 'screening' in visit_lower or 'screen' in visit_lower:
            return encounters[0]['id']
        # End of Study / Final → last encounter
        if any(x in visit_lower for x in ['end of study', 'eos', 'final', 'completion', 'termination', 'closure']):
            return encounters[-1]['id']

    # ---- Phase 7: Silently skip out-of-SoA visits ----
    high_visit = re.search(r'visit\s*(\d+)', visit_lower)
    if high_visit and int(high_visit.group(1)) > 100:
        return None
    _SKIP_PATTERNS = ['safety follow', 'primary endpoint', 'unscheduled', 'ad hoc', 'rescue']
    if any(p in visit_lower for p in _SKIP_PATTERNS):
        return None

    logger.warning(f"Could not resolve visit '{visit_name}' to encounter ID")
    _add_processing_warning(
        category="visit_resolution_failed",
        message=f"Could not resolve visit '{visit_name}' to encounter ID",
        context="execution_model_promotion",
        details={'visit_name': visit_name, 'available_encounters': [e.get('name') for e in encounters[:5]]}
    )
    return None


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
            "code": "C71738",  # Clinical Trial Epoch (generic)
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


def _create_extension_attribute(
    name: str,
    value: Any,
) -> Dict[str, Any]:
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


def _set_canonical_extension(
    design: Dict[str, Any],
    name: str,
    value: Any,
) -> None:
    """
    Set a CANONICAL extension attribute, replacing any existing instance.
    
    This enforces exactly ONE instance per extension type, addressing the
    duplication issue where multiple copies of the same extension were created.
    
    Args:
        design: StudyDesign dict to modify
        name: Extension name (e.g., "x-executionModel-stateMachine")
        value: Value to set (will be serialized appropriately)
    """
    if 'extensionAttributes' not in design:
        design['extensionAttributes'] = []
    
    url = f"https://protocol2usdm.io/extensions/{name}"
    
    # Remove any existing extension with this URL
    design['extensionAttributes'] = [
        ext for ext in design['extensionAttributes']
        if ext.get('url') != url
    ]
    
    # Add the canonical instance
    design['extensionAttributes'].append(_create_extension_attribute(name, value))


def _validate_dosing_regimen(regimen: Dict[str, Any]) -> bool:
    """
    Validate a dosing regimen to filter out sentence fragments and invalid entries.
    
    This acts as a GATEKEEPER to prevent garbage like "for the", "day and",
    "mg and" from being treated as dosing regimens.
    
    Returns True if the regimen is valid, False if it should be discarded.
    """
    # Must have a treatment name
    treatment_name = regimen.get('treatmentName', '') or regimen.get('treatment_name', '')
    if not treatment_name:
        return False
    
    # Treatment name must be substantial (not a fragment)
    if len(treatment_name.strip()) < 3:
        return False
    
    # Reject common sentence fragments
    STOPWORD_PATTERNS = [
        r'^(for|the|and|or|to|of|in|on|at|by|with|from|as|is|are|was|were)\s',
        r'^\s*(for|the|and|or|to|of)$',
        r'^\d+\s*(mg|ml|mcg|g|kg)\s*(and|or)?$',
        r'^(day|week|month)\s*(and|or)?',
        r'^\s*$',
    ]
    
    import re
    name_lower = treatment_name.lower().strip()
    for pattern in STOPWORD_PATTERNS:
        if re.match(pattern, name_lower, re.IGNORECASE):
            logger.debug(f"Filtering invalid dosing regimen: '{treatment_name}'")
            return False
    
    # Must have at least one of: dose, frequency, or route
    has_dose = bool(regimen.get('dose') or regimen.get('doseLevels') or regimen.get('dose_levels'))
    has_frequency = bool(regimen.get('frequency'))
    has_route = bool(regimen.get('route'))
    
    if not (has_dose or has_frequency or has_route):
        logger.debug(f"Filtering incomplete dosing regimen: '{treatment_name}'")
        return False
    
    return True


def _consolidate_dosing_regimens(regimens: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Consolidate dosing regimens: validate, deduplicate, and merge fragments.
    
    This ensures exactly ONE canonical regimen per intervention per arm.
    """
    if not regimens:
        return []
    
    # First pass: filter out invalid regimens
    valid_regimens = [r for r in regimens if _validate_dosing_regimen(r)]
    
    if len(valid_regimens) < len(regimens):
        logger.info(f"Filtered {len(regimens) - len(valid_regimens)} invalid dosing regimens")
    
    # Second pass: deduplicate by treatment name
    seen = {}
    for regimen in valid_regimens:
        treatment_name = (regimen.get('treatmentName') or regimen.get('treatment_name', '')).strip().lower()
        
        if treatment_name not in seen:
            seen[treatment_name] = regimen
        else:
            # Merge: keep the one with more complete information
            existing = seen[treatment_name]
            existing_score = sum([
                bool(existing.get('dose') or existing.get('doseLevels')),
                bool(existing.get('frequency')),
                bool(existing.get('route')),
                bool(existing.get('armId') or existing.get('arm_id')),
            ])
            new_score = sum([
                bool(regimen.get('dose') or regimen.get('doseLevels')),
                bool(regimen.get('frequency')),
                bool(regimen.get('route')),
                bool(regimen.get('armId') or regimen.get('arm_id')),
            ])
            if new_score > existing_score:
                seen[treatment_name] = regimen
    
    consolidated = list(seen.values())
    if len(consolidated) < len(valid_regimens):
        logger.info(f"Consolidated {len(valid_regimens)} -> {len(consolidated)} dosing regimens")
    
    return consolidated


def _add_execution_extensions(
    design: Dict[str, Any],
    execution_data: ExecutionModelData,
) -> None:
    """Add execution model extensions to a study design."""
    # ... (rest of the code remains the same)
    
    # FIX A: If crossover detected, update the BASE model (not just extension)
    # This ensures downstream consumers that only read base USDM behave correctly
    if execution_data.crossover_design and execution_data.crossover_design.is_crossover:
        design['model'] = {
            "id": "code_model_1",
            "code": "C82637",  # Crossover Study (EVS-verified)
            "codeSystem": "http://www.cdisc.org",
            "codeSystemVersion": "2024-09-27",
            "decode": "Crossover Study",
            "instanceType": "Code"
        }
        logger.info("Updated studyDesign.model to 'Crossover Study' based on crossover detection")
    
    # Initialize extensionAttributes if not present
    if 'extensionAttributes' not in design:
        design['extensionAttributes'] = []
    
    # Add time anchors (use canonical setter to prevent duplicates)
    if execution_data.time_anchors:
        _set_canonical_extension(design, "x-executionModel-timeAnchors",
            [a.to_dict() for a in execution_data.time_anchors])
    
    # Add repetitions (use canonical setter to prevent duplicates)
    if execution_data.repetitions:
        _set_canonical_extension(design, "x-executionModel-repetitions",
            [r.to_dict() for r in execution_data.repetitions])
    
    # Add sampling constraints (use canonical setter to prevent duplicates)
    if execution_data.sampling_constraints:
        _set_canonical_extension(design, "x-executionModel-samplingConstraints",
            [s.to_dict() for s in execution_data.sampling_constraints])
    
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
    
    # Phase 2: Add crossover design AND promote periods to first-class epochs
    if execution_data.crossover_design:
        cd = execution_data.crossover_design
        
        # Promote crossover periods to actual USDM epochs (not just extension)
        if cd.is_crossover and cd.num_periods and cd.num_periods > 0:
            if 'epochs' not in design:
                design['epochs'] = []
            
            existing_epoch_names = {e.get('name', '').lower() for e in design.get('epochs', [])}
            
            for i in range(cd.num_periods):
                period_name = f"Period {i + 1}"
                if period_name.lower() not in existing_epoch_names:
                    import uuid
                    period_epoch = {
                        "id": f"epoch_period_{i + 1}",
                        "name": period_name,
                        "description": f"Crossover study period {i + 1}",
                        "sequenceNumber": 100 + i,  # After screening/baseline epochs
                        "epochType": {
                            "id": str(uuid.uuid4()),
                            "code": "C101526",  # Treatment Epoch
                            "codeSystem": "http://www.cdisc.org",
                            "decode": "Treatment Epoch",
                            "instanceType": "Code"
                        },
                        "instanceType": "StudyEpoch"
                    }
                    design['epochs'].append(period_epoch)
                    logger.info(f"Promoted crossover {period_name} to first-class USDM epoch")
            
            # Add washout epochs between periods if washout duration exists
            if cd.washout_duration and cd.num_periods > 1:
                for i in range(cd.num_periods - 1):
                    washout_name = f"Washout {i + 1}"
                    if washout_name.lower() not in existing_epoch_names:
                        import uuid
                        washout_epoch = {
                            "id": f"epoch_washout_{i + 1}",
                            "name": washout_name,
                            "description": f"Washout period between Period {i + 1} and Period {i + 2}",
                            "sequenceNumber": 100 + i + 0.5,
                            "epochType": {
                                "id": str(uuid.uuid4()),
                                "code": "C71738",  # Clinical Trial Epoch (no specific washout code in NCI)
                                "codeSystem": "http://www.cdisc.org",
                                "decode": "Washout",
                                "instanceType": "Code"
                            },
                            "instanceType": "StudyEpoch"
                        }
                        design['epochs'].append(washout_epoch)
                        logger.info(f"Promoted crossover {washout_name} to first-class USDM epoch")
        
        # Still store extension for full crossover details (sequences, etc.)
        _set_canonical_extension(design, "x-executionModel-crossoverDesign", cd.to_dict())
    
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
        
        # Resolve traversal constraints - ALL fields must use real IDs
        resolved_constraints = []
        for tc in execution_data.traversal_constraints:
            resolved_tc = tc.to_dict()
            
            # 1. Resolve requiredSequence
            resolved_sequence = []
            for step in tc.required_sequence:
                resolved_id = _resolve_to_epoch_id(
                    step, epoch_ids, epoch_names, llm_mappings, design
                )
                if resolved_id:
                    resolved_sequence.append(resolved_id)
                    epoch_ids.add(resolved_id)  # Track newly created
            resolved_tc['requiredSequence'] = resolved_sequence
            
            # 2. Resolve exitEpochIds - MUST be real epoch IDs
            resolved_exits = []
            for exit_id in tc.exit_epoch_ids or []:
                resolved_id = _resolve_to_epoch_id(
                    exit_id, epoch_ids, epoch_names, llm_mappings, design
                )
                if resolved_id:
                    resolved_exits.append(resolved_id)
                    epoch_ids.add(resolved_id)
            resolved_tc['exitEpochIds'] = resolved_exits
            
            # 3. Resolve mandatoryVisits - convert names to encounter IDs
            resolved_visits = []
            for visit in tc.mandatory_visits or []:
                resolved_id = _resolve_to_encounter_id(
                    visit, encounter_ids, design.get('encounters', []),
                    epochs=design.get('epochs', design.get('studyEpochs', [])),
                )
                if resolved_id:
                    resolved_visits.append(resolved_id)
            resolved_tc['mandatoryVisits'] = resolved_visits
            
            resolved_constraints.append(resolved_tc)
        
        # Validate: no unresolved references allowed
        for tc in resolved_constraints:
            for step in tc.get('requiredSequence', []):
                if step not in epoch_ids and not step.startswith('epoch_'):
                    logger.error(f"UNRESOLVED traversal step after resolution: {step}")
        
        _set_canonical_extension(design, "x-executionModel-traversalConstraints", resolved_constraints)
    
    # Phase 2: Add footnote conditions with resolved activity/encounter IDs
    # Also promote to native USDM by attaching as activity notes
    # Per USDM IG: activity-specific footnotes -> Activity.notes[]
    #              protocol-wide footnotes -> StudyDesign.notes[]
    if execution_data.footnote_conditions:
        resolved_footnotes = []
        activity_names = {a.get('name', '').lower(): a.get('id') for a in design.get('activities', [])}
        activity_ids_set = {a.get('id') for a in design.get('activities', [])}
        
        # Track conditions per activity for native USDM promotion
        activity_conditions = {}  # activity_id -> list of condition texts
        # Track protocol-wide footnotes (no activity match) for StudyDesign.notes[]
        protocol_wide_footnotes = []
        
        # Build keyword-to-activity mapping for footnote text matching
        activity_keywords = {}
        for a in design.get('activities', []):
            a_name = a.get('name', '').lower()
            a_id = a.get('id')
            # Add full name
            activity_keywords[a_name] = a_id
            # Add individual words (except common ones)
            for word in a_name.split():
                if len(word) > 3 and word not in {'the', 'and', 'for', 'with', 'other'}:
                    if word not in activity_keywords:
                        activity_keywords[word] = a_id
        
        for fc in execution_data.footnote_conditions:
            fc_dict = fc.to_dict()
            
            # First: try to resolve any existing activity refs from LLM
            resolved_activity_ids = set()  # Use set to avoid duplicates
            if fc.applies_to_activity_ids:
                for act in fc.applies_to_activity_ids:
                    if act in activity_ids_set:
                        resolved_activity_ids.add(act)
                    elif act.lower() in activity_names:
                        resolved_activity_ids.add(activity_names[act.lower()])
                    else:
                        # Fuzzy match
                        for a_name, a_id in activity_names.items():
                            if act.lower() in a_name or a_name in act.lower():
                                resolved_activity_ids.add(a_id)
                                break
            resolved_activity_ids = list(resolved_activity_ids)  # Convert back to list
            
            # Second: if no activity refs yet, extract from footnote text
            if not resolved_activity_ids and fc.text:
                fn_text_lower = fc.text.lower()
                matched_ids = set()
                for keyword, a_id in activity_keywords.items():
                    if keyword in fn_text_lower:
                        matched_ids.add(a_id)
                resolved_activity_ids = list(matched_ids)
            
            if resolved_activity_ids:
                fc_dict['appliesToActivityIds'] = resolved_activity_ids
                # Track for native USDM promotion to Activity.notes[]
                for act_id in resolved_activity_ids:
                    if act_id not in activity_conditions:
                        activity_conditions[act_id] = []
                    activity_conditions[act_id].append({
                        'type': fc.condition_type,
                        'text': fc.text,
                        'structured': fc.structured_condition,
                    })
            else:
                # No activity match - this is a protocol-wide footnote
                # Per USDM IG, goes to StudyDesign.notes[]
                protocol_wide_footnotes.append({
                    'type': fc.condition_type,
                    'text': fc.text,
                    'structured': fc.structured_condition,
                    'source': fc.source_text,
                })
            
            # Resolve appliesToTimepointIds to encounter IDs
            if fc.applies_to_timepoint_ids:
                resolved_encounter_ids = []
                for tp in fc.applies_to_timepoint_ids:
                    resolved_id = _resolve_to_encounter_id(
                        tp, encounter_ids, design.get('encounters', []),
                        epochs=design.get('epochs', design.get('studyEpochs', [])),
                    )
                    if resolved_id:
                        resolved_encounter_ids.append(resolved_id)
                if resolved_encounter_ids:
                    fc_dict['appliesToEncounterIds'] = resolved_encounter_ids
            
            resolved_footnotes.append(fc_dict)
        
        # Store structured footnote conditions with resolved activity/encounter IDs
        # These are parsed from authoritative SoA footnotes (vision-extracted)
        if resolved_footnotes:
            _set_canonical_extension(design, "x-footnoteConditions", resolved_footnotes)
        
        # Promote to native USDM: Attach conditions as notes to activities
        conditions_promoted = 0
        for activity in design.get('activities', []):
            act_id = activity.get('id')
            if act_id in activity_conditions:
                conditions = activity_conditions[act_id]
                # Add as notes array if not present
                if 'notes' not in activity:
                    activity['notes'] = []
                for cond in conditions:
                    note = {
                        "id": f"note_cond_{act_id}_{len(activity['notes'])+1}",
                        "text": cond['text'][:500],
                        "instanceType": "Note"
                    }
                    activity['notes'].append(note)
                    conditions_promoted += 1
        
        if conditions_promoted > 0:
            logger.info(f"Promoted {conditions_promoted} footnote conditions to native USDM activity notes")
        
        # Promote protocol-wide footnotes to StudyDesign.notes[] per USDM IG
        if protocol_wide_footnotes:
            if 'notes' not in design:
                design['notes'] = []
            for i, fn in enumerate(protocol_wide_footnotes):
                note = {
                    "id": f"note_protocol_{i+1}",
                    "text": fn['text'][:500] if fn.get('text') else "Protocol-level condition",
                    "instanceType": "Note"
                }
                design['notes'].append(note)
            logger.info(f"Promoted {len(protocol_wide_footnotes)} protocol-wide footnotes to StudyDesign.notes[]")
    
    # Phase 3: Add endpoint algorithms (canonical - one per design)
    if execution_data.endpoint_algorithms:
        _set_canonical_extension(design, "x-executionModel-endpointAlgorithms",
            [ep.to_dict() for ep in execution_data.endpoint_algorithms])
    
    # Phase 3: Add derived variables (canonical - one per design)
    if execution_data.derived_variables:
        _set_canonical_extension(design, "x-executionModel-derivedVariables",
            [dv.to_dict() for dv in execution_data.derived_variables])
    
    # Phase 3: Add state machine (canonical - exactly one per design)
    if execution_data.state_machine:
        _set_canonical_extension(design, "x-executionModel-stateMachine",
            execution_data.state_machine.to_dict())
    
    # Phase 4: Promote dosing regimens to native USDM Administration entities
    if execution_data.dosing_regimens:
        # CONSOLIDATION: Validate and deduplicate dosing regimens before storing
        raw_regimens = [dr.to_dict() for dr in execution_data.dosing_regimens]
        consolidated_regimens = _consolidate_dosing_regimens(raw_regimens)
        
        # Store canonical consolidated regimens (one extension, no duplicates)
        _set_canonical_extension(design, "x-executionModel-dosingRegimens", consolidated_regimens)
        
        # Promote to native USDM: Create Administration entities and link to interventions
        promoted_administrations = []
        for dr in execution_data.dosing_regimens:
            # Build dose string from dose levels
            dose_str = None
            if dr.dose_levels:
                doses = [f"{dl.amount} {dl.unit}" for dl in dr.dose_levels]
                dose_str = " / ".join(doses)
            
            # Build frequency string
            freq_str = dr.frequency.value if dr.frequency else None
            
            # Build route
            route_code = None
            if dr.route:
                route_code = {
                    "code": dr.route.value,
                    "codeSystem": "http://www.cdisc.org",
                    "decode": dr.route.value,
                    "instanceType": "Code"
                }
            
            admin = {
                "id": f"admin_exec_{dr.id}",
                "name": f"{dr.treatment_name} Administration",
                "instanceType": "Administration",
            }
            if dose_str:
                admin["dose"] = dose_str
            if freq_str:
                admin["doseFrequency"] = freq_str
            if route_code:
                admin["route"] = route_code
            if dr.duration_description:
                admin["duration"] = dr.duration_description
            if dr.source_text:
                admin["description"] = dr.source_text[:200]
            
            promoted_administrations.append(admin)
            
            # Try to link to matching intervention
            treatment_lower = dr.treatment_name.lower()
            for intervention in design.get('studyInterventions', []):
                int_name = intervention.get('name', '').lower()
                if treatment_lower in int_name or int_name in treatment_lower:
                    if 'administrationIds' not in intervention:
                        intervention['administrationIds'] = []
                    if admin['id'] not in intervention['administrationIds']:
                        intervention['administrationIds'].append(admin['id'])
                    break
        
        # Add promoted administrations to a dedicated array (if not already present)
        if 'administrations' not in design:
            design['administrations'] = []
        design['administrations'].extend(promoted_administrations)
        logger.info(f"Promoted {len(promoted_administrations)} dosing regimens to native USDM Administration entities")
    
    # Phase 4: Add visit windows (use fixed/deduped if available)
    if execution_data.visit_windows:
        vw_output = getattr(execution_data, '_fixed_visit_windows', None)
        if vw_output is None:
            vw_output = [vw.to_dict() for vw in execution_data.visit_windows]
        _set_canonical_extension(design, "x-executionModel-visitWindows", vw_output)
    
    # Phase 4: Add randomization scheme (canonical - one per design)
    if execution_data.randomization_scheme:
        _set_canonical_extension(design, "x-executionModel-randomizationScheme",
            execution_data.randomization_scheme.to_dict())
    
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
            
            # Resolve activity ID to UUID — try exact, normalized, then fuzzy
            activity_key = ab.activity_name.lower() if ab.activity_name else ab.activity_id.lower()
            normalized_key = re.sub(r'[^a-z0-9]', '', activity_key)
            
            resolved_uuid = activity_uuid_map.get(activity_key) or activity_uuid_map.get(normalized_key)
            
            # Fuzzy: substring containment (same pattern as footnote resolution)
            if not resolved_uuid:
                for a_name, a_id in activity_uuid_map.items():
                    if activity_key in a_name or a_name in activity_key:
                        resolved_uuid = a_id
                        break
            
            if resolved_uuid:
                ab_dict['activityId'] = resolved_uuid
            
            # All repetitions should now exist (we auto-created missing ones above)
            resolved_bindings.append(ab_dict)
        
        if resolved_bindings:
            _set_canonical_extension(design, "x-executionModel-activityBindings", resolved_bindings)
    
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
        _set_canonical_extension(design, "x-executionModel-titrationSchedules",
            [ts.to_dict() for ts in execution_data.titration_schedules])
    
    # FIX B: Add instance bindings (repetition → ScheduledActivityInstance)
    if execution_data.instance_bindings:
        _set_canonical_extension(design, "x-executionModel-instanceBindings",
            [ib.to_dict() for ib in execution_data.instance_bindings])
    
    # FIX 3: Add analysis windows (regex-detected + epoch-derived fallback)
    all_analysis_windows = list(execution_data.analysis_windows) if execution_data.analysis_windows else []
    
    # Derive additional windows from epoch structure if treatment/follow-up are missing
    detected_types = {aw.window_type for aw in all_analysis_windows}
    if 'treatment' not in detected_types or 'follow_up' not in detected_types:
        epoch_windows = _derive_analysis_windows_from_epochs(design)
        for ew in epoch_windows:
            if ew.window_type not in detected_types:
                all_analysis_windows.append(ew)
                detected_types.add(ew.window_type)
    
    if all_analysis_windows:
        _set_canonical_extension(design, "x-executionModel-analysisWindows",
            [aw.to_dict() for aw in all_analysis_windows])


def _derive_analysis_windows_from_epochs(design: Dict[str, Any]) -> List:
    """
    Derive analysis windows from the epoch structure in the USDM design.
    
    Generic approach: classify epochs by name patterns into window types,
    then compute day ranges from encounter timings within each epoch.
    Works for any protocol structure.
    """
    from .schema import AnalysisWindow
    from core.usdm_types_generated import generate_uuid
    
    epochs = design.get('epochs', [])
    encounters = design.get('encounters', [])
    if not epochs:
        return []
    
    # Build epoch-to-encounters mapping via cells/elements
    # Each encounter has an epochId (set during pipeline) or we infer from name
    epoch_encounters: Dict[str, List[Dict[str, Any]]] = {ep.get('id', ''): [] for ep in epochs}
    for enc in encounters:
        eid = enc.get('epochId', '')
        if eid and eid in epoch_encounters:
            epoch_encounters[eid].append(enc)
    
    # Classify epochs by name → window_type
    TREATMENT_KEYWORDS = ['treatment', 'dosing', 'active', 'intervention', 'study drug', 'run-in']
    FOLLOWUP_KEYWORDS = ['follow-up', 'follow up', 'followup', 'post-treatment', 'observation']
    WASHOUT_KEYWORDS = ['washout', 'wash-out', 'wash out']
    SCREENING_KEYWORDS = ['screening', 'screen']
    
    windows = []
    
    for epoch in epochs:
        epoch_name = (epoch.get('name') or '').lower()
        epoch_id = epoch.get('id', '')
        
        # Determine window type from epoch name
        window_type = None
        if any(kw in epoch_name for kw in TREATMENT_KEYWORDS):
            window_type = 'treatment'
        elif any(kw in epoch_name for kw in FOLLOWUP_KEYWORDS):
            window_type = 'follow_up'
        elif any(kw in epoch_name for kw in WASHOUT_KEYWORDS):
            window_type = 'washout'
        elif any(kw in epoch_name for kw in SCREENING_KEYWORDS):
            window_type = 'screening'
        else:
            continue  # Skip epochs we can't classify
        
        # Compute day range from encounters in this epoch
        enc_list = epoch_encounters.get(epoch_id, [])
        if not enc_list:
            continue
        
        # Extract day numbers from encounter names
        all_days = []
        for enc in enc_list:
            enc_name = enc.get('name', '')
            # Match "Day X" patterns, including negative
            for m in re.finditer(r'[Dd]ay[s]?\s*(-?\d+)', enc_name):
                all_days.append(int(m.group(1)))
            # Also check parenthesized numbers like "Screening (-21)"
            for m in re.finditer(r'\((-?\d+)\)', enc_name):
                all_days.append(int(m.group(1)))
        
        if not all_days:
            continue
        
        start_day = min(all_days)
        end_day = max(all_days)
        
        display_name = epoch.get('name', window_type.replace('_', ' ').title())
        # Avoid double "Period" (e.g., "Treatment Period Period")
        label = display_name if re.search(r'period|phase|window', display_name, re.IGNORECASE) else f"{display_name} Period"
        windows.append(AnalysisWindow(
            id=generate_uuid(),
            window_type=window_type,
            name=label,
            start_day=start_day,
            end_day=end_day,
            description=f"{display_name} from Day {start_day} to Day {end_day}",
            source_text=f"Derived from epoch '{epoch.get('name', '?')}' with {len(enc_list)} encounters",
        ))
        logger.info(f"Derived analysis window: {window_type} from epoch '{epoch.get('name')}' (Day {start_day}–{end_day})")
    
    return windows


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


def propagate_windows_to_encounters(design: Dict[str, Any]) -> int:
    """
    Denormalize timing windows to encounters for easy downstream access.
    
    This addresses the architectural feedback that visit windows only live in 
    Timing objects, forcing generators to traverse timing graphs. After this,
    each encounter exposes its effective window directly.
    
    Adds to each encounter:
      - effectiveWindowLower: int (days before nominal, typically negative)
      - effectiveWindowUpper: int (days after nominal, typically positive)
      - scheduledDay: int (nominal study day, derived from timing)
    
    Args:
        design: StudyDesign dict to modify in-place
        
    Returns:
        Number of encounters updated with window information
    """
    import json
    
    # Build timing map from all sources
    timing_map: Dict[str, Dict[str, Any]] = {}
    
    # 1. Collect timings from schedule timelines
    for timeline in design.get('scheduleTimelines', []):
        for timing in timeline.get('timings', []):
            timing_map[timing.get('id', '')] = timing
    
    # 2. Collect from root-level timings
    for timing in design.get('timings', []):
        timing_map[timing.get('id', '')] = timing
    
    # 3. Collect from visit windows extension
    visit_windows_ext = None
    for ext in design.get('extensionAttributes', []):
        if 'visitWindows' in ext.get('url', ''):
            try:
                visit_windows = json.loads(ext.get('valueString', '[]'))
                # Build name-based lookup for visit windows
                for vw in visit_windows:
                    visit_name = vw.get('visitName', '').lower()
                    if visit_name:
                        timing_map[f"vw_{visit_name}"] = {
                            'value': vw.get('targetDay'),
                            'windowLower': -abs(vw.get('windowBefore', 0)) if vw.get('windowBefore') else None,
                            'windowUpper': vw.get('windowAfter'),
                        }
            except json.JSONDecodeError:
                pass
    
    updated_count = 0
    
    for encounter in design.get('encounters', []):
        enc_id = encounter.get('id', '')
        enc_name = encounter.get('name', '')
        enc_name_lower = enc_name.lower()
        
        # Try to find timing by scheduledAtId
        timing_id = encounter.get('scheduledAtId')
        timing = timing_map.get(timing_id) if timing_id else None
        
        # If no direct link, try name-based matching with visit windows
        if not timing:
            timing = timing_map.get(f"vw_{enc_name_lower}")
        
        # Try fuzzy name matching
        if not timing:
            for key, t in timing_map.items():
                t_name = t.get('name', '').lower() if isinstance(t, dict) else ''
                if enc_name_lower and (enc_name_lower in t_name or t_name in enc_name_lower):
                    timing = t
                    break
        
        if timing:
            # Propagate window bounds
            if timing.get('windowLower') is not None:
                encounter['effectiveWindowLower'] = timing['windowLower']
            if timing.get('windowUpper') is not None:
                encounter['effectiveWindowUpper'] = timing['windowUpper']
            
            # Propagate scheduled day
            if timing.get('value') is not None:
                encounter['scheduledDay'] = timing['value']
            
            updated_count += 1
        
        # Also try to extract day from encounter name if not found
        if 'scheduledDay' not in encounter:
            import re
            day_match = re.search(r'day\s*[-]?\s*(\d+)', enc_name_lower)
            if day_match:
                encounter['scheduledDay'] = int(day_match.group(1))
    
    if updated_count > 0:
        logger.info(f"Propagated timing windows to {updated_count} encounters")
    
    return updated_count


# =============================================================================
# A1+A2: Comprehensive Extension Reference Resolution
# =============================================================================

def _build_activity_lookup(design: Dict[str, Any]) -> Dict[str, str]:
    """
    Build a comprehensive activity name→UUID lookup from reconciled activities.
    
    Returns a dict mapping various name forms to the canonical UUID:
    - Exact lowercase name
    - Normalized (alphanumeric only)
    - Synonym-expanded (clinical abbreviation/qualifier stripping)
    - Word set key for overlap matching
    """
    lookup: Dict[str, str] = {}
    for act in design.get('activities', []):
        act_id = act.get('id', '')
        act_name = act.get('name', '')
        if not act_id or not act_name:
            continue
        # Exact lowercase
        lookup[act_name.lower()] = act_id
        # Normalized (alphanumeric only)
        normalized = re.sub(r'[^a-z0-9]', '', act_name.lower())
        lookup[normalized] = act_id
        # Synonym-expanded form
        syn = _synonym_normalize(act_name)
        if syn:
            lookup[syn] = act_id
            lookup[re.sub(r'[^a-z0-9]', '', syn)] = act_id
        # Also store the UUID itself so we can detect already-resolved refs
        lookup[act_id] = act_id
    return lookup


def _word_overlap_score(a: str, b: str) -> float:
    """Jaccard similarity on word sets, ignoring short/stop words."""
    stop = {'the', 'a', 'an', 'of', 'for', 'and', 'or', 'in', 'to', 'at', 'by', 'on'}
    wa = {w for w in re.findall(r'[a-z0-9]+', a.lower()) if len(w) > 1 and w not in stop}
    wb = {w for w in re.findall(r'[a-z0-9]+', b.lower()) if len(w) > 1 and w not in stop}
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def _resolve_activity_ref(
    ref: str,
    lookup: Dict[str, str],
    activity_names: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """Resolve a single activity reference (name or orphaned UUID) to a reconciled UUID.
    
    Args:
        ref: The reference value (name, UUID, or orphaned UUID)
        lookup: name/normalized/synonym → reconciled UUID mapping
        activity_names: Optional id → name mapping for word-overlap scoring
    """
    if not ref or not isinstance(ref, str):
        return None
    # Already in lookup (exact UUID match)
    if ref in lookup:
        return lookup[ref]
    # Lowercase name match
    low = ref.lower().strip()
    if low in lookup:
        return lookup[low]
    # Normalized match
    normalized = re.sub(r'[^a-z0-9]', '', low)
    if normalized in lookup:
        return lookup[normalized]
    # Synonym-expanded match
    syn = _synonym_normalize(ref)
    if syn and syn in lookup:
        return lookup[syn]
    syn_norm = re.sub(r'[^a-z0-9]', '', syn) if syn else ''
    if syn_norm and syn_norm in lookup:
        return lookup[syn_norm]
    # Substring containment (both directions)
    for key, uid in lookup.items():
        if len(key) > 3 and (low in key or key in low):
            return uid
    # Word-overlap scoring (for semantically similar but textually different names)
    if activity_names and not re.match(r'^[0-9a-f]{8}-', ref):
        best_score = 0.0
        best_id = None
        ref_syn = _synonym_normalize(ref)
        for act_id, act_name in activity_names.items():
            score = _word_overlap_score(ref, act_name)
            # Also try synonym-expanded forms
            act_syn = _synonym_normalize(act_name)
            syn_score = _word_overlap_score(ref_syn, act_syn)
            final_score = max(score, syn_score)
            if final_score > best_score:
                best_score = final_score
                best_id = act_id
        if best_score >= 0.4 and best_id:
            return best_id
    return None


def _resolve_refs_in_obj(
    obj: Any,
    activity_lookup: Dict[str, str],
    footnote_id_map: Dict[str, str],
    stats: Dict[str, int],
    activity_names: Optional[Dict[str, str]] = None,
) -> Any:
    """Recursively walk an object and resolve activityId/appliesToActivityIds/footnoteId."""
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if k == 'activityId' and isinstance(v, str):
                resolved = _resolve_activity_ref(v, activity_lookup, activity_names)
                # Fallback: use sibling 'activityName' as resolution hint
                if (not resolved or resolved == v) and 'activityName' in obj:
                    hint = obj['activityName']
                    if isinstance(hint, str) and hint:
                        resolved = _resolve_activity_ref(hint, activity_lookup, activity_names)
                if resolved and resolved != v:
                    stats['activityId'] = stats.get('activityId', 0) + 1
                    result[k] = resolved
                else:
                    result[k] = v
            elif k == 'appliesToActivityIds' and isinstance(v, list):
                new_list = []
                for item in v:
                    if isinstance(item, str):
                        resolved = _resolve_activity_ref(item, activity_lookup, activity_names)
                        if resolved and resolved != item:
                            stats['appliesToActivityIds'] = stats.get('appliesToActivityIds', 0) + 1
                            new_list.append(resolved)
                        else:
                            new_list.append(item)
                    else:
                        new_list.append(item)
                result[k] = new_list
            elif k == 'footnoteId' and isinstance(v, str) and v in footnote_id_map:
                stats['footnoteId'] = stats.get('footnoteId', 0) + 1
                result[k] = footnote_id_map[v]
            elif k == 'valueString' and isinstance(v, str):
                # Parse JSON in valueString and resolve refs within
                try:
                    if v.startswith('[') or v.startswith('{'):
                        parsed = json.loads(v)
                        resolved_parsed = _resolve_refs_in_obj(
                            parsed, activity_lookup, footnote_id_map, stats, activity_names
                        )
                        result[k] = json.dumps(resolved_parsed, ensure_ascii=False)
                    else:
                        result[k] = v
                except (json.JSONDecodeError, TypeError):
                    result[k] = v
            elif isinstance(v, (dict, list)):
                result[k] = _resolve_refs_in_obj(v, activity_lookup, footnote_id_map, stats, activity_names)
            else:
                result[k] = v
        return result
    elif isinstance(obj, list):
        return [_resolve_refs_in_obj(item, activity_lookup, footnote_id_map, stats, activity_names) for item in obj]
    else:
        return obj


def _nullify_orphan_refs(
    design: Dict[str, Any],
    valid_activity_ids: set,
) -> Dict[str, int]:
    """
    Walk extension attributes and nullify any activityId / appliesToActivityIds
    values that are not in the valid activity ID set.
    
    This is the safety-net fallback after resolution: any remaining orphan
    refs (phantom UUIDs, unresolvable name-strings) get set to None / removed
    so they don't appear as broken references in the final USDM output.
    
    Returns stats dict with counts of nullified refs.
    """
    stats: Dict[str, int] = {}
    
    def _walk_and_nullify(obj: Any) -> Any:
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                if k == 'activityId' and isinstance(v, str) and v not in valid_activity_ids:
                    stats['activityId_nullified'] = stats.get('activityId_nullified', 0) + 1
                    logger.debug(f"  Nullifying orphan activityId: {v[:50]}")
                    result[k] = None
                elif k == 'appliesToActivityIds' and isinstance(v, list):
                    cleaned = [item for item in v if not isinstance(item, str) or item in valid_activity_ids]
                    removed = len(v) - len(cleaned)
                    if removed > 0:
                        stats['appliesToActivityIds_nullified'] = stats.get('appliesToActivityIds_nullified', 0) + removed
                        logger.debug(f"  Removed {removed} orphan appliesToActivityIds entries")
                    result[k] = cleaned if cleaned else None
                elif k == 'valueString' and isinstance(v, str):
                    try:
                        if v.startswith('[') or v.startswith('{'):
                            parsed = json.loads(v)
                            nullified = _walk_and_nullify(parsed)
                            result[k] = json.dumps(nullified, ensure_ascii=False)
                        else:
                            result[k] = v
                    except (json.JSONDecodeError, TypeError):
                        result[k] = v
                elif isinstance(v, (dict, list)):
                    result[k] = _walk_and_nullify(v)
                else:
                    result[k] = v
            return result
        elif isinstance(obj, list):
            return [_walk_and_nullify(item) for item in obj]
        else:
            return obj
    
    # Walk study design extensions
    if 'extensionAttributes' in design:
        design['extensionAttributes'] = _walk_and_nullify(design['extensionAttributes'])
    
    # Walk individual activity extensions
    for activity in design.get('activities', []):
        if 'extensionAttributes' in activity:
            activity['extensionAttributes'] = _walk_and_nullify(activity['extensionAttributes'])
    
    return stats


def resolve_execution_model_references(
    design: Dict[str, Any],
    old_to_new_ids: Optional[Dict[str, str]] = None,
) -> Dict[str, int]:
    """
    Post-integration pass: resolve all activityId, appliesToActivityIds, and
    footnoteId references in execution model extensions to reconciled entity UUIDs.
    
    This fixes:
    - A1: Orphaned UUID activityIds (execution-phase UUIDs → reconciled UUIDs)
    - A2: Name-as-ID activityIds and appliesToActivityIds
    - A1: Orphaned footnoteIds (match to SoA footnote object IDs)
    
    Args:
        design: The studyDesign dict (post-reconciliation)
        old_to_new_ids: Optional mapping of pre-reconciliation activity IDs
            to post-reconciliation IDs. Used to resolve orphaned UUIDs that
            were valid before reconciliation but got replaced.
    
    Returns:
        Dict of resolution stats (field_name → count of resolved refs)
    """
    activity_lookup = _build_activity_lookup(design)
    
    # Merge old→new ID mapping so orphaned pre-reconciliation UUIDs resolve
    if old_to_new_ids:
        for old_id, new_id in old_to_new_ids.items():
            if old_id not in activity_lookup:
                activity_lookup[old_id] = new_id
    
    # Build footnote ID map: old footnote_id → new object ID
    # The x-soaFootnotes extension may store footnotes as objects with IDs
    footnote_id_map: Dict[str, str] = {}
    for ext in design.get('extensionAttributes', []):
        if ext.get('url', '').endswith('soaFootnotes'):
            vs = ext.get('valueString', '')
            if vs:
                try:
                    footnotes = json.loads(vs)
                    if isinstance(footnotes, list):
                        for fn in footnotes:
                            if isinstance(fn, dict) and 'id' in fn:
                                # Map common patterns: fn_1, fn_2, markers a, b, etc.
                                fn_id = fn['id']
                                footnote_id_map[fn_id] = fn_id
                except (json.JSONDecodeError, TypeError):
                    pass
    
    # Build activity id→name mapping for word-overlap scoring
    activity_names: Dict[str, str] = {
        a.get('id', ''): a.get('name', '')
        for a in design.get('activities', [])
        if a.get('id') and a.get('name')
    }
    
    stats: Dict[str, int] = {}
    
    # Walk all extension attributes on the study design
    if 'extensionAttributes' in design:
        design['extensionAttributes'] = _resolve_refs_in_obj(
            design['extensionAttributes'], activity_lookup, footnote_id_map, stats, activity_names
        )
    
    # Walk extension attributes on individual activities
    for activity in design.get('activities', []):
        if 'extensionAttributes' in activity:
            activity['extensionAttributes'] = _resolve_refs_in_obj(
                activity['extensionAttributes'], activity_lookup, footnote_id_map, stats, activity_names
            )
    
    total = sum(stats.values())
    if total > 0:
        logger.info(f"  ✓ Resolved {total} execution model references: {stats}")
    
    # --- Nullification pass: clean up remaining orphan refs ---
    # After resolution, any activityId / appliesToActivityIds values that are
    # still not valid activity UUIDs are orphans. Nullify them to prevent
    # broken references in the final USDM output.
    valid_activity_ids = {a.get('id') for a in design.get('activities', []) if a.get('id')}
    nullify_stats = _nullify_orphan_refs(design, valid_activity_ids)
    if sum(nullify_stats.values()) > 0:
        logger.info(f"  ✓ Nullified {sum(nullify_stats.values())} unresolvable orphan refs: {nullify_stats}")
    stats.update(nullify_stats)
    
    return stats


def emit_placeholder_activities(design: Dict[str, Any]) -> int:
    """
    Create placeholder Activity entities for any remaining unresolved
    activityId / appliesToActivityIds references in execution model extensions.
    
    Handles:
    - Orphaned UUIDs with sibling activityName: creates activity with the name
    - Name-string refs: creates activity with that name
    
    Returns the number of placeholder activities created.
    """
    import uuid as uuid_mod
    
    act_ids = {a.get('id') for a in design.get('activities', []) if a.get('id')}
    UUID_PAT = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    
    # Collect unresolved refs: ref_value → best name hint
    unresolved: Dict[str, Optional[str]] = {}
    
    def _scan(obj: Any) -> None:
        if isinstance(obj, dict):
            aid = obj.get('activityId')
            if isinstance(aid, str) and aid not in act_ids:
                hint = obj.get('activityName', '')
                hint = hint.replace('\n', ' ').strip() if isinstance(hint, str) else ''
                if UUID_PAT.match(aid):
                    if aid not in unresolved and hint:
                        unresolved[aid] = hint
                else:
                    unresolved[aid] = aid
            applies = obj.get('appliesToActivityIds')
            if isinstance(applies, list):
                for item in applies:
                    if isinstance(item, str) and item not in act_ids:
                        if UUID_PAT.match(item):
                            unresolved.setdefault(item, None)
                        else:
                            unresolved[item] = item
            for k, v in obj.items():
                if k == 'valueString' and isinstance(v, str):
                    try:
                        if v.startswith('[') or v.startswith('{'):
                            _scan(json.loads(v))
                    except Exception:
                        pass
                elif isinstance(v, (dict, list)):
                    _scan(v)
        elif isinstance(obj, list):
            for item in obj:
                _scan(item)
    
    _scan(design.get('extensionAttributes', []))
    
    if not unresolved:
        return 0
    
    # Group by canonical name to avoid duplicate placeholders
    name_to_new_id: Dict[str, str] = {}
    old_to_placeholder: Dict[str, str] = {}
    placeholders: List[Dict[str, Any]] = []
    
    for ref_val, name_hint in unresolved.items():
        if not name_hint:
            continue
        canon = name_hint.strip()
        canon_key = canon.lower()
        if canon_key in name_to_new_id:
            new_id = name_to_new_id[canon_key]
        else:
            new_id = str(uuid_mod.uuid4())
            name_to_new_id[canon_key] = new_id
            placeholders.append({
                'id': new_id,
                'name': canon,
                'label': canon,
                'description': f'Execution model activity category: {canon}',
                'instanceType': 'Activity',
            })
        old_to_placeholder[ref_val] = new_id
    
    if not placeholders:
        return 0
    
    design.setdefault('activities', []).extend(placeholders)
    
    # Remap references in extensions
    remap_count = [0]
    
    def _remap(obj: Any) -> Any:
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                if k == 'activityId' and isinstance(v, str) and v in old_to_placeholder:
                    result[k] = old_to_placeholder[v]
                    remap_count[0] += 1
                elif k == 'appliesToActivityIds' and isinstance(v, list):
                    result[k] = [
                        old_to_placeholder.get(i, i) if isinstance(i, str) else i
                        for i in v
                    ]
                    remap_count[0] += sum(1 for i in v if isinstance(i, str) and i in old_to_placeholder)
                elif k == 'valueString' and isinstance(v, str):
                    try:
                        if v.startswith('[') or v.startswith('{'):
                            parsed = json.loads(v)
                            remapped = _remap(parsed)
                            result[k] = json.dumps(remapped, ensure_ascii=False)
                        else:
                            result[k] = v
                    except Exception:
                        result[k] = v
                elif isinstance(v, (dict, list)):
                    result[k] = _remap(v)
                else:
                    result[k] = v
            return result
        elif isinstance(obj, list):
            return [_remap(item) for item in obj]
        return obj
    
    if 'extensionAttributes' in design:
        design['extensionAttributes'] = _remap(design['extensionAttributes'])
    
    logger.info(
        f"  ✓ Emitted {len(placeholders)} placeholder activities, "
        f"remapped {remap_count[0]} refs"
    )
    return len(placeholders)
