"""
USDM combiner — merges phase results into unified USDM v4.0 JSON.

This module contains the combine_to_full_usdm() function and its direct
helpers for assembling the final USDM document from extraction phase results.
"""

from typing import Dict, Optional, Any
from pathlib import Path
from datetime import datetime
import json
import os
import logging
import re
import uuid

from .phase_registry import phase_registry
from .base_phase import PhaseResult
from .integrations import (
    resolve_content_references,
    reconcile_estimand_population_refs,
)
from extraction.execution.pipeline_integration import resolve_execution_model_references, emit_placeholder_activities
from .post_processing import (
    run_reconciliation,
    run_structural_compliance,
    filter_enrichment_epochs,
    tag_unscheduled_encounters,
    promote_unscheduled_to_decisions,
    mark_activity_sources,
    link_procedures_to_activities,
    link_administrations_to_products,
    nest_ingredients_in_products,
    link_ingredient_strengths,
    link_cohorts_to_population,
    add_soa_footnotes,
    validate_anchor_consistency,
    resolve_name_as_id_references,
)
from .promotion import promote_extensions_to_usdm
from core.constants import SYSTEM_NAME, VERSION

logger = logging.getLogger(__name__)


def load_previous_extractions(output_dir: str) -> dict:
    """
    Load previously extracted data from JSON files.
    
    This allows the combine function to use data from prior runs
    even when those phases weren't re-run in the current session.
    
    Returns dict of phase_name -> loaded data (dict format, not objects)
    """
    loaded = {}
    
    # Define extraction files and their phase names
    extraction_files = {
        'metadata': ['2_study_metadata.json'],
        'eligibility': ['3_eligibility_criteria.json'],
        'objectives': ['4_objectives_endpoints.json'],
        'studydesign': ['5_study_design.json'],
        'interventions': ['6_interventions.json'],
        'narrative': ['7_narrative_structure.json'],
        'advanced': ['8_advanced_entities.json'],
        'procedures': ['9_procedures_devices.json'],
        'scheduling': ['10_scheduling_logic.json'],
        'docstructure': ['13_document_structure.json'],
        'amendmentdetails': ['14_amendment_details.json'],
        'execution': ['11_execution_model.json'],
        # Support current phase output + legacy extractor output for compatibility.
        'sap': ['14_sap_extraction.json', '11_sap_populations.json'],
        'sites': ['15_sites_extraction.json', '12_study_sites.json'],
    }

    for phase, candidate_filenames in extraction_files.items():
        for filename in candidate_filenames:
            filepath = os.path.join(output_dir, filename)
            if not os.path.exists(filepath):
                continue
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data.get('success', True):
                        loaded[phase] = data
                        logger.debug(f"Loaded previous extraction: {phase} from {filename}")
                        break
            except (json.JSONDecodeError, IOError) as e:
                logger.debug(f"Could not load {filename}: {e}")
    
    return loaded


def combine_to_full_usdm(
    output_dir: str,
    soa_data: dict = None,
    expansion_results: dict = None,
    pdf_path: str = None,
) -> tuple:
    """
    Combine SoA and expansion results into unified USDM JSON.
    
    This function merges:
    1. Data from expansion_results (current run, PhaseResult format)
    2. Data from previously saved JSON files (prior runs, dict format)
    
    Returns tuple of (combined_data, output_path)
    """
    # Import phases to trigger registration
    from . import phases as _  # noqa
    
    # Load previously extracted data from JSON files
    previous_extractions = load_previous_extractions(output_dir)
    logger.info(f"Loaded {len(previous_extractions)} previous extractions from output directory")
    
    # USDM v4.0 compliant structure
    combined = {
        "usdmVersion": "4.0",
        "generatedAt": datetime.now().isoformat(),
        "generator": f"{SYSTEM_NAME} v{VERSION}",
        "_output_dir": output_dir,  # Temp: used by SAP phase for ARS generation, stripped before save
        "_pdf_path": pdf_path,  # Temp: used by enrollment finder, stripped before save
        "study": {
            "id": "study_1",
            "instanceType": "Study",
            "versions": []
        },
    }
    
    # Study version container
    study_version = {
        "id": "sv_1",
        "instanceType": "StudyVersion",
        "versionIdentifier": "1.0",
        "studyDesigns": [],
    }
    
    # Study design container — instanceType will be resolved after metadata combine
    study_design = {
        "id": "sd_1",
        "name": "Study Design",
        "rationale": "Protocol-defined study design for investigating efficacy and safety",
        "instanceType": "InterventionalStudyDesign",  # default, overridden below
    }
    
    # Run combine for each registered phase (always iterate, even without
    # current-run results, so previous_extractions can be used as fallback)
    for phase in phase_registry.get_all():
        phase_name = phase.config.name.lower()
        result = (expansion_results or {}).get(phase_name)
        
        phase.combine(
            result=result if result else PhaseResult(success=False),
            study_version=study_version,
            study_design=study_design,
            combined=combined,
            previous_extractions=previous_extractions,
        )
    
    # Apply defaults for required USDM fields
    _apply_defaults(study_version, study_design, combined, pdf_path)
    
    # Add SoA data
    _add_soa_data(study_design, soa_data)

    # Normalize legacy StudyElement keying before downstream reconciliation/integrity
    _normalize_study_elements(study_design)
    
    # Derive study design instanceType and studyType from metadata
    study_type = combined.pop("_temp_study_type", None)
    if study_type:
        normalized = study_type.strip().lower()
        if normalized in ("observational", "obs"):
            study_design["instanceType"] = "ObservationalStudyDesign"
            study_design["studyType"] = {
                "code": "C142615", "codeSystem": "http://www.cdisc.org",
                "codeSystemVersion": "2024-09-27", "decode": "Non-Interventional Study",
                "instanceType": "Code",
            }
            logger.info(f"  Study design type derived from metadata: ObservationalStudyDesign")
        else:
            study_design["instanceType"] = "InterventionalStudyDesign"
            study_design["studyType"] = {
                "code": "C98388", "codeSystem": "http://www.cdisc.org",
                "codeSystemVersion": "2024-09-27", "decode": "Interventional Study",
                "instanceType": "Code",
            }
            logger.info(f"  Study design type derived from metadata: InterventionalStudyDesign")
    else:
        # Default to Interventional
        study_design["studyType"] = {
            "code": "C98388", "codeSystem": "http://www.cdisc.org",
            "codeSystemVersion": "2024-09-27", "decode": "Interventional Study",
            "instanceType": "Code",
        }
        logger.info("  Study design type: defaulting to InterventionalStudyDesign (no metadata)")
    
    # Add indications to studyDesign (from metadata temp storage)
    if combined.get("_temp_indications"):
        study_design["indications"] = combined.pop("_temp_indications")
    
    # Deterministic fallback: infer therapeuticAreas from indications if LLM left it empty
    if not study_design.get("therapeuticAreas"):
        indication_names = [
            ind.get("name", "") for ind in study_design.get("indications", [])
            if isinstance(ind, dict) and ind.get("name")
        ]
        if indication_names:
            from extraction.studydesign.schema import (
                infer_therapeutic_areas_from_indications,
                _build_therapeutic_area_code,
            )
            inferred = infer_therapeutic_areas_from_indications(indication_names)
            if inferred:
                study_design["therapeuticAreas"] = [
                    _build_therapeutic_area_code(ta) for ta in inferred
                ]
                logger.info(f"  Therapeutic areas inferred from indications: {inferred}")
    
    # NOTE: SAP and Sites are registered phases (SAPPhase, SitesPhase)
    # and are handled exclusively via the phase.combine() loop above,
    # preventing duplicate extension creation from legacy side paths.
    
    # Reconcile estimand.analysisPopulationId → analysisPopulations references
    reconcile_estimand_population_refs(study_design)
    
    # Add studyDesign to study_version
    study_version["studyDesigns"] = [study_design]
    
    # Add computational execution metadata
    combined["computationalExecution"] = {
        "ready": True,
        "supportedSystems": ["EDC", "ePRO", "CTMS", "RTSM"],
        "validationStatus": "pending",
    }
    
    # Assemble final structure
    combined["study"]["versions"] = [study_version]
    
    # Handle execution model enrichment (special case - needs full structure)
    if expansion_results and expansion_results.get('execution'):
        exec_result = expansion_results['execution']
        if exec_result.success and exec_result.data:
            exec_phase = phase_registry.get('execution')
            if exec_phase and hasattr(exec_phase, 'enrich_usdm'):
                combined = exec_phase.enrich_usdm(combined, exec_result)
                logger.info(f"  ✓ Enriched USDM with execution model (Phase 14)")
                
                # Filter epochs added by enrichment
                combined = filter_enrichment_epochs(combined, soa_data)
    
    # Snapshot pre-reconciliation activity IDs for old→new mapping
    pre_recon_activities = {
        a.get('id'): a.get('name', '').lower().strip()
        for a in study_design.get('activities', [])
        if a.get('id') and a.get('name')
    }
    
    # Run reconciliation
    combined = run_reconciliation(combined, expansion_results, soa_data)
    
    # Build old→new activity ID mapping after reconciliation
    post_recon_name_to_id = {}
    for a in study_design.get('activities', []):
        name = a.get('name', '').lower().strip()
        if name:
            post_recon_name_to_id[name] = a.get('id')
            post_recon_name_to_id[re.sub(r'[^a-z0-9]', '', name)] = a.get('id')
    
    old_to_new_activity_ids = {}
    for old_id, old_name in pre_recon_activities.items():
        if old_name in post_recon_name_to_id:
            new_id = post_recon_name_to_id[old_name]
            if new_id != old_id:
                old_to_new_activity_ids[old_id] = new_id
        else:
            # Try normalized match
            norm = re.sub(r'[^a-z0-9]', '', old_name)
            if norm in post_recon_name_to_id:
                new_id = post_recon_name_to_id[norm]
                if new_id != old_id:
                    old_to_new_activity_ids[old_id] = new_id
    
    # Tag unscheduled encounters (safety net for UNS visits)
    combined = tag_unscheduled_encounters(combined)
    
    # Promote UNS encounters to ScheduledDecisionInstance (Phase 2)
    combined = promote_unscheduled_to_decisions(combined)
    
    # Resolve cross-references (targetId + pageNumber)
    resolve_content_references(combined)
    
    # Mark activity sources
    mark_activity_sources(study_design)
    
    # Link procedures to activities
    link_procedures_to_activities(study_design)
    
    # Add SoA footnotes from header
    add_soa_footnotes(study_design, output_dir)
    
    # Resolve execution model refs AFTER reconciliation + footnotes exist
    try:
        ref_stats = resolve_execution_model_references(
            study_design, old_to_new_ids=old_to_new_activity_ids
        )
    except Exception as e:
        logger.warning(f"Post-reconciliation extension ref resolution failed: {e}")
    
    # Link interventions entities (H8, H9, H10)
    combined = link_administrations_to_products(combined)
    combined = nest_ingredients_in_products(combined)
    combined = link_ingredient_strengths(combined)
    
    # Link cohorts to population (M3/M9)
    combined = link_cohorts_to_population(combined)
    
    # Validate anchor consistency against SoA encounters
    combined = validate_anchor_consistency(combined, expansion_results)
    
    # Resolve name-as-ID references (substanceId, fromElementId, toElementId)
    resolve_name_as_id_references(combined)
    
    # Structural CORE compliance (ordering chains, endpoint linkage, timing refs)
    combined = run_structural_compliance(combined)
    
    # Promote extension data back into core USDM entities
    promote_extensions_to_usdm(combined)
    
    # Strip internal temp keys before saving
    combined.pop("_output_dir", None)
    combined.pop("_pdf_path", None)
    combined.pop("_temp_planned_enrollment", None)
    # Amendment detail entities are now embedded inline (A3 fix)
    combined.pop("studyAmendmentReasons", None)
    combined.pop("studyAmendmentImpacts", None)
    combined.pop("studyChanges", None)
    
    # Save combined output
    output_path = os.path.join(output_dir, "protocol_usdm.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\n✓ Combined USDM saved to: {output_path}")
    
    # Run referential integrity checks
    try:
        from pipeline.integrity import check_integrity, save_integrity_report
        integrity_report = check_integrity(combined)
        save_integrity_report(integrity_report, output_dir)
        if integrity_report.error_count > 0:
            logger.warning(
                f"⚠ Integrity: {integrity_report.error_count} errors, "
                f"{integrity_report.warning_count} warnings"
            )
    except Exception as e:
        logger.warning(f"Integrity check failed: {e}")
    
    return combined, output_path


def _apply_defaults(study_version: dict, study_design: dict, combined: dict, pdf_path: str) -> None:
    """Apply default values for required USDM fields."""
    # Default titles
    if "titles" not in study_version:
        pdf_name = Path(pdf_path).stem if pdf_path else "Unknown Protocol"
        study_version["titles"] = [{
            "id": str(uuid.uuid4()),
            "instanceType": "StudyTitle",
            "text": pdf_name,
            "type": {"code": "C99905x1", "codeSystem": "http://www.cdisc.org", "decode": "Official Study Title"}
        }]
        logger.warning("  Using fallback default for titles (metadata extraction failed)")
    
    # Default study identifiers
    if "studyIdentifiers" not in study_version:
        sponsor_org_id = str(uuid.uuid4())
        if "organizations" not in study_version:
            study_version["organizations"] = []
        study_version["organizations"].append({
            "id": sponsor_org_id,
            "instanceType": "Organization",
            "name": "Sponsor",
            "identifier": "SPONSOR",
            "identifierScheme": "DUNS",
            "type": {"code": "C54149", "codeSystem": "http://www.cdisc.org", "codeSystemVersion": "2024-09-27", "decode": "Pharmaceutical Company", "instanceType": "Code"}
        })
        study_version["studyIdentifiers"] = [{
            "id": str(uuid.uuid4()),
            "instanceType": "StudyIdentifier",
            "text": "UNKNOWN",
            "scopeId": sponsor_org_id,
            "type": {"code": "C132351", "codeSystem": "http://www.cdisc.org", "decode": "Sponsor Protocol Identifier"}
        }]
        logger.warning("  Using fallback default for studyIdentifiers (metadata extraction failed)")
    
    # Default population
    if "population" not in study_design:
        study_design["population"] = {
            "id": "pop_1",
            "instanceType": "StudyDesignPopulation",
            "name": "Study Population",
            "description": "Target population for the study as defined by eligibility criteria",
            "includesHealthySubjects": False
        }
    elif "includesHealthySubjects" not in study_design["population"]:
        study_design["population"]["includesHealthySubjects"] = False
    
    # Link eligibility criteria to population (CORE-001018)
    criteria = study_design.get("eligibilityCriteria", [])
    population = study_design.get("population", {})
    if criteria and population and "criterionIds" not in population:
        population["criterionIds"] = [c["id"] for c in criteria if c.get("id")]
    
    # Default arms
    if "arms" not in study_design or not study_design["arms"]:
        study_design["arms"] = [{
            "id": "arm_1",
            "name": "Treatment Arm",
            "description": "Main treatment arm",
            "type": {
                "id": "code_arm_type_1",
                "code": "C174266",
                "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
                "codeSystemVersion": "25.01d",
                "decode": "Investigational Arm",
                "instanceType": "Code"
            },
            "dataOriginType": {
                "id": "code_data_origin_1",
                "code": "C188866",
                "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
                "codeSystemVersion": "25.01d",
                "decode": "Data Generated Within Study",
                "instanceType": "Code"
            },
            "dataOriginDescription": "Data collected during study conduct",
            "instanceType": "StudyArm"
        }]
    
    # Default epochs
    if "epochs" not in study_design or not study_design["epochs"]:
        study_design["epochs"] = [{
            "id": "epoch_1",
            "name": "Treatment Period",
            "description": "Main treatment period of the study",
            "instanceType": "StudyEpoch",
            "type": {
                "id": "code_epoch_type_1",
                "code": "C101526",
                "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
                "codeSystemVersion": "25.01d",
                "decode": "Treatment Epoch",
                "instanceType": "Code"
            }
        }]
    
    # Default study cells
    if "studyCells" not in study_design or not study_design["studyCells"]:
        arms = study_design.get("arms", [])
        epochs = study_design.get("epochs", [])
        cells = []
        for arm in arms:
            arm_id = arm.get("id", "arm_1")
            for epoch in epochs:
                epoch_id = epoch.get("id", "") if isinstance(epoch, dict) else getattr(epoch, 'id', '')
                if epoch_id:
                    cells.append({
                        "id": f"cell_{arm_id}_{epoch_id}",
                        "armId": arm_id,
                        "epochId": epoch_id,
                        "elementIds": [],
                        "instanceType": "StudyCell"
                    })
        if cells:
            study_design["studyCells"] = cells
        else:
            study_design["studyCells"] = [{
                "id": "cell_1",
                "armId": study_design["arms"][0]["id"] if study_design.get("arms") else "arm_1",
                "epochId": epochs[0].get("id", "epoch_1") if epochs else "epoch_1",
                "elementIds": [],
                "instanceType": "StudyCell"
            }]
    
    # B8: Fill in missing arm×epoch combinations when cells exist but are incomplete
    existing_cells = study_design.get("studyCells", [])
    if existing_cells:
        existing_combos = {
            (c.get("armId"), c.get("epochId")) for c in existing_cells
        }
        arms = study_design.get("arms", [])
        epochs = study_design.get("epochs", [])
        gap_count = 0
        for arm in arms:
            arm_id = arm.get("id", "")
            for epoch in epochs:
                epoch_id = epoch.get("id", "") if isinstance(epoch, dict) else getattr(epoch, 'id', '')
                if arm_id and epoch_id and (arm_id, epoch_id) not in existing_combos:
                    existing_cells.append({
                        "id": f"cell_{arm_id}_{epoch_id}",
                        "armId": arm_id,
                        "epochId": epoch_id,
                        "elementIds": [],
                        "instanceType": "StudyCell"
                    })
                    gap_count += 1
        if gap_count:
            logger.info(f"  ✓ Added {gap_count} missing StudyCell(s) for arm×epoch gaps")
    
    # Default model
    if "model" not in study_design:
        arms = study_design.get("arms", [])
        if len(arms) >= 2:
            study_design["model"] = {
                "id": "code_model_1",
                "code": "C82639",
                "codeSystem": "http://www.cdisc.org",
                "codeSystemVersion": "2024-09-27",
                "decode": "Parallel Study",
                "instanceType": "Code"
            }
        else:
            study_design["model"] = {
                "id": "code_model_1",
                "code": "C82640",
                "codeSystem": "http://www.cdisc.org",
                "codeSystemVersion": "2024-09-27",
                "decode": "Single Group Study",
                "instanceType": "Code"
            }


def _normalize_study_elements(study_design: dict) -> None:
    """Normalize legacy `studyElements` alias into canonical `elements` list."""
    legacy_elements = study_design.pop("studyElements", None)

    canonical_elements = study_design.get("elements", [])
    if not isinstance(canonical_elements, list):
        canonical_elements = [canonical_elements] if canonical_elements else []

    merged_elements = list(canonical_elements)
    seen_ids = {
        elem.get("id")
        for elem in merged_elements
        if isinstance(elem, dict) and elem.get("id")
    }

    added = 0
    if isinstance(legacy_elements, list):
        for elem in legacy_elements:
            if not isinstance(elem, dict):
                continue
            elem_id = elem.get("id")
            if elem_id and elem_id in seen_ids:
                continue
            merged_elements.append(elem)
            if elem_id:
                seen_ids.add(elem_id)
            added += 1

    if merged_elements or isinstance(legacy_elements, list):
        study_design["elements"] = merged_elements

    if added:
        logger.info(f"  ✓ Normalized {added} legacy studyElements into elements")


def _add_soa_data(study_design: dict, soa_data: Optional[dict]) -> None:
    """Add SoA data to study design."""
    if not soa_data:
        return
    
    soa_schedule = None
    
    # Try USDM v4.0 path
    if "study" in soa_data:
        try:
            sds = soa_data["study"]["versions"][0].get("studyDesigns", [])
            if sds and (sds[0].get("activities") or sds[0].get("scheduleTimelines") or 
                       sds[0].get("epochs") or sds[0].get("encounters")):
                soa_schedule = sds[0]
        except (KeyError, IndexError, TypeError):
            pass
        
        # Fallback: legacy timeline path
        if not soa_schedule:
            try:
                timeline = soa_data["study"]["versions"][0].get("timeline", {})
                if timeline and (timeline.get("activities") or timeline.get("activityTimepoints")):
                    soa_schedule = timeline
            except (KeyError, IndexError, TypeError):
                pass
    
    # Try top-level studyDesigns
    if not soa_schedule and "studyDesigns" in soa_data and soa_data["studyDesigns"]:
        soa_schedule = soa_data["studyDesigns"][0]
    
    if soa_schedule:
        soa_keys = ["scheduleTimelines", "encounters", "activities", "epochs",
                    "plannedTimepoints", "activityTimepoints", "activityGroups", "notes"]
        for key in soa_keys:
            if key in soa_schedule and soa_schedule[key]:
                study_design[key] = soa_schedule[key]
        
        # Ensure scheduleTimelines have required fields
        for timeline in study_design.get('scheduleTimelines', []):
            if 'mainTimeline' not in timeline:
                timeline['mainTimeline'] = True
            if 'entryCondition' not in timeline:
                timeline['entryCondition'] = "Subject meets all inclusion criteria and none of the exclusion criteria"
            if 'entryId' not in timeline:
                timeline['entryId'] = timeline.get('id', 'timeline_1')
