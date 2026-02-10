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
import uuid

from .phase_registry import phase_registry
from .base_phase import PhaseResult
from .integrations import (
    integrate_sites,
    integrate_sap,
    resolve_content_references,
    reconcile_estimand_population_refs,
)
from .post_processing import (
    run_reconciliation,
    filter_enrichment_epochs,
    mark_activity_sources,
    link_procedures_to_activities,
    add_soa_footnotes,
)
from .promotion import promote_extensions_to_usdm
from core.constants import SYSTEM_NAME, SYSTEM_VERSION

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
        'metadata': '2_study_metadata.json',
        'eligibility': '3_eligibility_criteria.json',
        'objectives': '4_objectives_endpoints.json',
        'studydesign': '5_study_design.json',
        'interventions': '6_interventions.json',
        'narrative': '7_narrative_structure.json',
        'advanced': '8_advanced_entities.json',
        'procedures': '9_procedures_devices.json',
        'scheduling': '10_scheduling_logic.json',
        'docstructure': '13_document_structure.json',
        'amendmentdetails': '14_amendment_details.json',
        'execution': '11_execution_model.json',
        'sap': '11_sap_populations.json',
    }
    
    for phase, filename in extraction_files.items():
        filepath = os.path.join(output_dir, filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data.get('success', True):
                        loaded[phase] = data
                        logger.debug(f"Loaded previous extraction: {phase}")
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
        "generator": f"{SYSTEM_NAME} v{SYSTEM_VERSION}",
        "_output_dir": output_dir,  # Temp: used by SAP phase for ARS generation, stripped before save
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
    
    # Derive study design instanceType from metadata (instead of hardcoding)
    study_type = combined.pop("_temp_study_type", None)
    if study_type:
        normalized = study_type.strip().lower()
        if normalized in ("observational", "obs"):
            study_design["instanceType"] = "ObservationalStudyDesign"
            logger.info(f"  Study design type derived from metadata: ObservationalStudyDesign")
        else:
            study_design["instanceType"] = "InterventionalStudyDesign"
            logger.info(f"  Study design type derived from metadata: InterventionalStudyDesign")
    else:
        logger.info("  Study design type: defaulting to InterventionalStudyDesign (no metadata)")
    
    # Add indications to studyDesign (from metadata temp storage)
    if combined.get("_temp_indications"):
        study_design["indications"] = combined.pop("_temp_indications")
    
    # NOTE: SAP and Sites are now registered phases (SAPPhase, SitesPhase)
    # and handled by the phase.combine() loop above. The integrate_sap()
    # and integrate_sites() helpers are retained for backward compatibility
    # with callers that pass SAP/sites results directly in expansion_results
    # without going through the phase registry.
    if expansion_results and (expansion_results.get('sap') or expansion_results.get('sites')):
        integrate_sites(study_version, study_design, expansion_results)
        integrate_sap(study_version, study_design, expansion_results, output_dir)
    
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
    
    # Run reconciliation
    combined = run_reconciliation(combined, expansion_results, soa_data)
    
    # Resolve cross-references (targetId + pageNumber)
    resolve_content_references(combined)
    
    # Mark activity sources
    mark_activity_sources(study_design)
    
    # Link procedures to activities
    link_procedures_to_activities(study_design)
    
    # Add SoA footnotes from header
    add_soa_footnotes(study_design, output_dir)
    
    # Promote extension data back into core USDM entities
    promote_extensions_to_usdm(combined)
    
    # Strip internal temp keys before saving
    combined.pop("_output_dir", None)
    
    # Save combined output
    output_path = os.path.join(output_dir, "protocol_usdm.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\n✓ Combined USDM saved to: {output_path}")
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
            "type": {"code": "C70793", "codeSystem": "http://www.cdisc.org", "decode": "Clinical Study Sponsor"}
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
                "decode": "Experimental Arm",
                "instanceType": "Code"
            },
            "dataOriginType": {
                "id": "code_data_origin_1",
                "code": "C142493",
                "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
                "codeSystemVersion": "25.01d",
                "decode": "Collected",
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
                "code": "C82638",
                "codeSystem": "http://www.cdisc.org",
                "codeSystemVersion": "2024-09-27",
                "decode": "Single Group Study",
                "instanceType": "Code"
            }


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
