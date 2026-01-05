#!/usr/bin/env python3
"""
Protocol2USDM v2 - Simplified Pipeline

This is a cleaner, modular implementation of the SoA extraction pipeline.
It follows the original architectural intent:
- Vision extracts STRUCTURE (headers, groups)
- Text extracts DATA (activities, ticks) using structure as anchor
- Vision validates text extraction
- Output is schema-compliant USDM JSON

Usage:
    python main_v2.py protocol.pdf [--model gemini-2.5-pro] [--no-validate]
    
Compared to main.py, this version:
- Uses modular extraction components from extraction/
- Has cleaner separation of concerns
- Produces simpler, more debuggable output
- Follows the original design intent
"""

import argparse
import logging
import os
import sys
import json
import uuid
from pathlib import Path

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Import from new modular structure
from extraction import run_from_files, PipelineConfig, PipelineResult
from core.constants import DEFAULT_MODEL

# Import expansion modules
from extraction.metadata import extract_study_metadata
from extraction.metadata.extractor import save_metadata_result
from extraction.eligibility import extract_eligibility_criteria
from extraction.eligibility.extractor import save_eligibility_result
from extraction.objectives import extract_objectives_endpoints
from extraction.objectives.extractor import save_objectives_result
from extraction.studydesign import extract_study_design
from extraction.studydesign.extractor import save_study_design_result
from extraction.interventions import extract_interventions
from extraction.interventions.extractor import save_interventions_result
from extraction.narrative import extract_narrative_structure
from extraction.narrative.extractor import save_narrative_result
from extraction.advanced import extract_advanced_entities
from extraction.advanced.extractor import save_advanced_result
from extraction.execution import extract_execution_model
from core.reconciliation import (
    EpochReconciler, reconcile_epochs_from_pipeline,
    ActivityReconciler, reconcile_activities_from_pipeline,
    EncounterReconciler, reconcile_encounters_from_pipeline,
)
from extraction.pipeline_context import PipelineContext, create_pipeline_context
from extraction.confidence import (
    calculate_metadata_confidence,
    calculate_eligibility_confidence,
    calculate_objectives_confidence,
    calculate_studydesign_confidence,
    calculate_interventions_confidence,
    calculate_narrative_confidence,
    calculate_advanced_confidence,
)


def run_expansion_phases(
    pdf_path: str,
    output_dir: str,
    model: str,
    phases: dict,
    soa_data: dict = None,
    pipeline_context: PipelineContext = None,
) -> dict:
    """
    Run requested expansion phases.
    
    Args:
        pdf_path: Path to protocol PDF
        output_dir: Output directory
        model: LLM model name
        phases: Dict of phase_name -> bool indicating which to run
        soa_data: Optional SOA extraction data for enhanced context
        pipeline_context: Accumulated context from prior extractions
    
    Returns:
        Dict of phase_name -> extraction result
    """
    results = {}
    
    # Create or use existing pipeline context
    if pipeline_context is None:
        pipeline_context = create_pipeline_context(soa_data)
    
    logger.info(f"Pipeline context: {pipeline_context.get_summary()}")
    
    if phases.get('metadata'):
        logger.info("\n--- Expansion: Study Metadata (Phase 2) ---")
        result = extract_study_metadata(pdf_path, model_name=model)
        save_metadata_result(result, os.path.join(output_dir, "2_study_metadata.json"))
        results['metadata'] = result
        if result.success and result.metadata:
            # Update pipeline context with metadata
            pipeline_context.update_from_metadata(result.metadata)
            conf = calculate_metadata_confidence(result.metadata)
            logger.info(f"  ✓ Metadata extraction (📊 {conf.overall:.0%})")
        else:
            logger.info(f"  ✗ Metadata extraction failed")
    
    if phases.get('eligibility'):
        logger.info("\n--- Expansion: Eligibility Criteria (Phase 1) ---")
        result = extract_eligibility_criteria(
            pdf_path, 
            model_name=model,
            study_indication=pipeline_context.indication if pipeline_context.indication else None,
            study_phase=pipeline_context.phase if pipeline_context.phase else None,
        )
        save_eligibility_result(result, os.path.join(output_dir, "3_eligibility_criteria.json"))
        results['eligibility'] = result
        if result.success and result.data:
            pipeline_context.update_from_eligibility(result.data)
            conf = calculate_eligibility_confidence(result.data)
            logger.info(f"  ✓ Eligibility extraction (📊 {conf.overall:.0%})")
        else:
            logger.info(f"  ✗ Eligibility extraction failed")
    
    if phases.get('objectives'):
        logger.info("\n--- Expansion: Objectives & Endpoints (Phase 3) ---")
        result = extract_objectives_endpoints(
            pdf_path, 
            model_name=model,
            study_indication=pipeline_context.indication if pipeline_context.indication else None,
            study_phase=pipeline_context.phase if pipeline_context.phase else None,
        )
        save_objectives_result(result, os.path.join(output_dir, "4_objectives_endpoints.json"))
        results['objectives'] = result
        if result.success and result.data:
            pipeline_context.update_from_objectives(result.data)
            conf = calculate_objectives_confidence(result.data)
            logger.info(f"  ✓ Objectives extraction (📊 {conf.overall:.0%})")
        else:
            logger.info(f"  ✗ Objectives extraction failed")
    
    if phases.get('studydesign'):
        logger.info("\n--- Expansion: Study Design (Phase 4) ---")
        result = extract_study_design(
            pdf_path, 
            model_name=model,
            existing_epochs=pipeline_context.epochs if pipeline_context.has_epochs() else None,
            existing_arms=pipeline_context.arms if pipeline_context.has_arms() else None,
        )
        save_study_design_result(result, os.path.join(output_dir, "5_study_design.json"))
        results['studydesign'] = result
        if result.success and result.data:
            pipeline_context.update_from_studydesign(result.data)
            conf = calculate_studydesign_confidence(result.data)
            logger.info(f"  ✓ Study design extraction (📊 {conf.overall:.0%})")
        else:
            logger.info(f"  ✗ Study design extraction failed")
    
    if phases.get('interventions'):
        logger.info("\n--- Expansion: Interventions (Phase 5) ---")
        result = extract_interventions(
            pdf_path, 
            model_name=model,
            existing_arms=pipeline_context.arms if pipeline_context.has_arms() else None,
            study_indication=pipeline_context.indication if pipeline_context.indication else None,
        )
        save_interventions_result(result, os.path.join(output_dir, "6_interventions.json"))
        results['interventions'] = result
        if result.success and result.data:
            pipeline_context.update_from_interventions(result.data)
            conf = calculate_interventions_confidence(result.data)
            logger.info(f"  ✓ Interventions extraction (📊 {conf.overall:.0%})")
        else:
            logger.info(f"  ✗ Interventions extraction failed")
    
    if phases.get('narrative'):
        logger.info("\n--- Expansion: Narrative Structure (Phase 7) ---")
        result = extract_narrative_structure(pdf_path, model_name=model)
        save_narrative_result(result, os.path.join(output_dir, "7_narrative_structure.json"))
        results['narrative'] = result
        if result.success and result.data:
            conf = calculate_narrative_confidence(result.data)
            logger.info(f"  ✓ Narrative extraction (📊 {conf.overall:.0%})")
        else:
            logger.info(f"  ✗ Narrative extraction failed")
    
    if phases.get('advanced'):
        logger.info("\n--- Expansion: Advanced Entities (Phase 8) ---")
        result = extract_advanced_entities(pdf_path, model_name=model)
        save_advanced_result(result, os.path.join(output_dir, "8_advanced_entities.json"))
        results['advanced'] = result
        if result.success and result.data:
            conf = calculate_advanced_confidence(result.data)
            logger.info(f"  ✓ Advanced extraction (📊 {conf.overall:.0%})")
        else:
            logger.info(f"  ✗ Advanced extraction failed")
    
    if phases.get('procedures'):
        logger.info("\n--- Expansion: Procedures & Devices (Phase 10) ---")
        try:
            from extraction.procedures import extract_procedures_devices
            result = extract_procedures_devices(pdf_path, model=model, output_dir=output_dir)
            results['procedures'] = result
            if result.success and result.data:
                pipeline_context.update_from_procedures(result.data.to_dict())
                logger.info(f"  ✓ Procedures extraction ({result.data.to_dict()['summary']['procedureCount']} procedures)")
            else:
                logger.info(f"  ✗ Procedures extraction failed: {result.error}")
        except ImportError as e:
            logger.warning(f"  ✗ Procedures module not available: {e}")
    
    if phases.get('scheduling'):
        logger.info("\n--- Expansion: Scheduling Logic (Phase 11) ---")
        try:
            from extraction.scheduling import extract_scheduling
            result = extract_scheduling(pdf_path, model=model, output_dir=output_dir)
            results['scheduling'] = result
            if result.success and result.data:
                pipeline_context.update_from_scheduling(result.data.to_dict())
                logger.info(f"  ✓ Scheduling extraction ({result.data.to_dict()['summary']['timingCount']} timings)")
            else:
                logger.info(f"  ✗ Scheduling extraction failed: {result.error}")
        except ImportError as e:
            logger.warning(f"  ✗ Scheduling module not available: {e}")
    
    if phases.get('docstructure'):
        logger.info("\n--- Expansion: Document Structure (Phase 12) ---")
        try:
            from extraction.document_structure import extract_document_structure
            result = extract_document_structure(pdf_path, model=model, output_dir=output_dir)
            results['docstructure'] = result
            if result.success and result.data:
                summary = result.data.to_dict()['summary']
                logger.info(f"  ✓ Document structure ({summary['referenceCount']} refs, {summary['annotationCount']} annotations)")
            else:
                logger.info(f"  ✗ Document structure extraction failed: {result.error}")
        except ImportError as e:
            logger.warning(f"  ✗ Document structure module not available: {e}")
    
    if phases.get('amendmentdetails'):
        logger.info("\n--- Expansion: Amendment Details (Phase 13) ---")
        try:
            from extraction.amendments import extract_amendment_details
            result = extract_amendment_details(pdf_path, model=model, output_dir=output_dir)
            results['amendmentdetails'] = result
            if result.success and result.data:
                summary = result.data.to_dict()['summary']
                logger.info(f"  ✓ Amendment details ({summary['impactCount']} impacts, {summary['changeCount']} changes)")
            else:
                logger.info(f"  ✗ Amendment details extraction failed: {result.error}")
        except ImportError as e:
            logger.warning(f"  ✗ Amendment details module not available: {e}")
    
    if phases.get('execution'):
        logger.info("\n--- Expansion: Execution Model (Phase 14) ---")
        result = extract_execution_model(
            pdf_path, 
            model=model, 
            output_dir=output_dir,
            soa_data=soa_data,
        )
        results['execution'] = result
        if result.success and result.data:
            data = result.data
            anchors = len(data.time_anchors)
            reps = len(data.repetitions)
            exec_types = len(data.execution_types)
            traversals = len(data.traversal_constraints)
            footnotes = len(data.footnote_conditions)
            visits = len(data.visit_windows)
            dosing = len(data.dosing_regimens)
            crossover = "Yes" if data.crossover_design and data.crossover_design.is_crossover else "No"
            logger.info(f"  ✓ Execution model extracted")
            logger.info(f"    Anchors: {anchors}, Repetitions: {reps}, Exec Types: {exec_types}")
            logger.info(f"    Traversals: {traversals}, Footnotes: {footnotes}, Crossover: {crossover}")
            logger.info(f"    Visits: {visits}, Dosing: {dosing}")
        else:
            logger.info(f"  ✗ Execution model extraction failed: {result.error}")
    
    # Store pipeline context in results for downstream use
    results['_pipeline_context'] = pipeline_context
    
    return results


def convert_ids_to_uuids(data: dict, id_map: dict = None) -> dict:
    """
    Convert all simple IDs (like 'study_1', 'act_1') to proper UUIDs.
    
    USDM 4.0 requires all 'id' fields to be valid UUIDs.
    This function recursively converts IDs while maintaining internal references.
    
    Args:
        data: USDM JSON data
        id_map: Optional existing ID mapping (for consistency)
        
    Returns:
        Data with UUIDs and the ID mapping used
    """
    if id_map is None:
        id_map = {}
    
    def is_simple_id(value):
        """Check if value looks like a simple ID that needs conversion."""
        if not isinstance(value, str):
            return False
        # Skip if already a UUID format
        try:
            uuid.UUID(value)
            return False  # Already a valid UUID
        except ValueError:
            pass
        # Check for common ID patterns
        id_patterns = ['_', '-']
        return any(p in value for p in id_patterns) and len(value) < 50
    
    def get_or_create_uuid(simple_id: str) -> str:
        """Get existing UUID for ID or create new one."""
        if simple_id not in id_map:
            id_map[simple_id] = str(uuid.uuid4())
        return id_map[simple_id]
    
    def convert_recursive(obj):
        """Recursively convert IDs in nested structure."""
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                if key == 'id' and is_simple_id(value):
                    result[key] = get_or_create_uuid(value)
                elif key.endswith('Id') and is_simple_id(value):
                    # Handle reference fields like activityId, encounterId, epochId
                    result[key] = get_or_create_uuid(value)
                elif key.endswith('Ids') and isinstance(value, list):
                    # Handle ID arrays like activityIds, childIds
                    result[key] = [get_or_create_uuid(v) if is_simple_id(v) else v for v in value]
                elif isinstance(value, (dict, list)):
                    result[key] = convert_recursive(value)
                else:
                    result[key] = value
            return result
        elif isinstance(obj, list):
            return [convert_recursive(item) for item in obj]
        else:
            return obj
    
    converted = convert_recursive(data)
    return converted, id_map


def link_timing_ids_to_instances(study_design: dict) -> int:
    """
    Link timingId on ScheduledActivityInstances based on encounter matching.
    
    Per USDM 4.0, ScheduledActivityInstance can have a timingId reference.
    This function matches instances to timings using multiple strategies:
    1. Exact name match
    2. Day number extraction and matching
    3. Partial/fuzzy name matching
    
    Args:
        study_design: StudyDesign dict with scheduleTimelines containing instances and timings
        
    Returns:
        Number of instances that were linked to timings
    """
    import re
    
    if not study_design.get('scheduleTimelines'):
        return 0
    
    main_timeline = study_design['scheduleTimelines'][0]
    instances = main_timeline.get('instances', [])
    timings = main_timeline.get('timings', [])
    
    if not instances or not timings:
        return 0
    
    def extract_day_numbers(text: str) -> set:
        """Extract day numbers from text like 'Day 1', 'Day -1', '(Day 54)'."""
        if not text:
            return set()
        # Match patterns: "Day 1", "Day -1", "day 54", "(Day 1)", etc.
        matches = re.findall(r'day\s*(-?\d+)', text.lower())
        return set(int(m) for m in matches)
    
    def extract_visit_number(text: str) -> int:
        """Extract visit number from text like 'Visit 1', 'V1'."""
        if not text:
            return None
        match = re.search(r'(?:visit|v)\s*(\d+)', text.lower())
        return int(match.group(1)) if match else None
    
    # Build encounter ID -> info lookup
    enc_id_to_info = {}
    for enc in study_design.get('encounters', []):
        enc_id = enc.get('id', '')
        enc_name = enc.get('name', '')
        if enc_id:
            enc_id_to_info[enc_id] = {
                'name': enc_name.lower().strip(),
                'days': extract_day_numbers(enc_name),
                'visit': extract_visit_number(enc_name),
            }
    
    # Build timing lookup with multiple keys
    timing_by_name = {}  # exact name match
    timing_by_day = {}   # day number match
    timing_by_visit = {} # visit number match
    
    for timing in timings:
        timing_id = timing.get('id', '')
        if not timing_id:
            continue
        
        name = timing.get('name', '').lower().strip()
        value_label = timing.get('valueLabel', '').lower().strip()
        
        # Add exact name matches
        if name:
            timing_by_name[name] = timing_id
        if value_label:
            timing_by_name[value_label] = timing_id
        
        # Extract and add day numbers
        for text in [name, value_label]:
            for day in extract_day_numbers(text):
                timing_by_day[day] = timing_id
        
        # Add by ISO duration value
        value = timing.get('value')
        if isinstance(value, str) and value.startswith('P') and 'D' in value:
            match = re.search(r'P(-?\d+)D', value)
            if match:
                timing_by_day[int(match.group(1))] = timing_id
        
        # Add visit number
        for text in [name, value_label]:
            visit = extract_visit_number(text)
            if visit:
                timing_by_visit[visit] = timing_id
    
    # Link instances to timings
    linked_count = 0
    for instance in instances:
        if instance.get('timingId'):
            continue  # Already has timing
        
        enc_id = instance.get('encounterId', '')
        enc_info = enc_id_to_info.get(enc_id, {})
        
        if not enc_info:
            continue
        
        timing_id = None
        
        # Strategy 1: Exact name match
        if enc_info['name'] in timing_by_name:
            timing_id = timing_by_name[enc_info['name']]
        
        # Strategy 2: Day number match
        if not timing_id and enc_info['days']:
            for day in enc_info['days']:
                if day in timing_by_day:
                    timing_id = timing_by_day[day]
                    break
        
        # Strategy 3: Visit number match
        if not timing_id and enc_info['visit']:
            if enc_info['visit'] in timing_by_visit:
                timing_id = timing_by_visit[enc_info['visit']]
        
        if timing_id:
            instance['timingId'] = timing_id
            linked_count += 1
    
    return linked_count


def build_name_to_id_map(data: dict) -> dict:
    """
    Build a mapping of entity names to their IDs from USDM data.
    
    This allows matching entities between provenance and data by name
    when IDs don't match (e.g., after UUID conversion).
    """
    name_map = {
        'activities': {},
        'encounters': {},
        'epochs': {},
        'plannedTimepoints': {},
    }
    
    # Navigate to studyDesigns
    try:
        study_designs = data.get('study', {}).get('versions', [{}])[0].get('studyDesigns', [])
        if not study_designs:
            return name_map
        sd = study_designs[0]
    except (KeyError, IndexError, TypeError):
        return name_map
    
    # Build maps by name
    for act in sd.get('activities', []):
        if act.get('name') and act.get('id'):
            name_map['activities'][act['name']] = act['id']
    
    for enc in sd.get('encounters', []):
        if enc.get('name') and enc.get('id'):
            name_map['encounters'][enc['name']] = enc['id']
    
    for epoch in sd.get('epochs', []):
        if epoch.get('name') and epoch.get('id'):
            name_map['epochs'][epoch['name']] = epoch['id']
    
    # PlannedTimepoints might be in scheduleTimelines or directly
    for pt in sd.get('plannedTimepoints', []):
        if pt.get('name') and pt.get('id'):
            name_map['plannedTimepoints'][pt['name']] = pt['id']
    
    return name_map


def convert_provenance_to_uuids(provenance_data: dict, id_map: dict) -> dict:
    """
    Convert provenance IDs to UUIDs using the same id_map from convert_ids_to_uuids.
    
    This creates a new provenance dict with all IDs converted to UUIDs,
    ensuring perfect alignment with protocol_usdm.json.
    
    Handles both:
    - New format: enc_N (encounterId directly from extraction)
    - Legacy format: pt_N (plannedTimepointId, backward compat)
    
    Args:
        provenance_data: Original provenance dict (entities, cells, cellFootnotes, metadata)
        id_map: ID mapping from convert_ids_to_uuids {simple_id: uuid}
        
    Returns:
        New provenance dict with all IDs converted to UUIDs
    """
    if not provenance_data or not id_map:
        return provenance_data
    
    # Build pt_N -> enc_N UUID mapping for backward compatibility
    # Legacy provenance used pt_1, pt_2... but id_map has enc_1, enc_2...
    import re
    pt_to_enc_uuid = {}
    for key, uuid_val in id_map.items():
        match = re.match(r'^enc_(\d+)$', key)
        if match:
            n = match.group(1)
            # Map pt_N directly to enc_N's UUID (backward compat)
            pt_to_enc_uuid[f"pt_{n}"] = uuid_val
    
    def convert_id(old_id: str) -> str:
        """Convert ID using id_map, return original if not found."""
        return id_map.get(old_id, old_id)
    
    def convert_timepoint_id(old_id: str) -> str:
        """Convert timepoint ID to UUID. Handles both enc_N (new) and pt_N (legacy)."""
        # Direct lookup in id_map (handles enc_N directly)
        if old_id in id_map:
            return id_map[old_id]
        # Legacy: pt_N -> enc_N UUID lookup
        if old_id in pt_to_enc_uuid:
            return pt_to_enc_uuid[old_id]
        # Return as-is if not found
        return old_id
    
    result = {}
    
    # Convert entity IDs
    if 'entities' in provenance_data:
        result['entities'] = {}
        for entity_type, entities in provenance_data['entities'].items():
            if isinstance(entities, dict):
                result['entities'][entity_type] = {
                    convert_id(eid): source for eid, source in entities.items()
                }
            else:
                result['entities'][entity_type] = entities
    
    # Convert cell keys (format: "act_id|pt_id" -> "uuid|enc_uuid")
    if 'cells' in provenance_data:
        result['cells'] = {}
        for key, source in provenance_data['cells'].items():
            if '|' in key:
                act_id, pt_id = key.split('|', 1)
                # Use convert_timepoint_id to map pt_N -> enc_N UUID
                new_key = f"{convert_id(act_id)}|{convert_timepoint_id(pt_id)}"
                result['cells'][new_key] = source
            else:
                result['cells'][key] = source
    
    # Convert cellFootnotes keys (format: "act_id|pt_id" -> "uuid|enc_uuid")
    if 'cellFootnotes' in provenance_data:
        result['cellFootnotes'] = {}
        for key, refs in provenance_data['cellFootnotes'].items():
            if '|' in key:
                act_id, pt_id = key.split('|', 1)
                new_key = f"{convert_id(act_id)}|{convert_timepoint_id(pt_id)}"
                result['cellFootnotes'][new_key] = refs
            else:
                result['cellFootnotes'][key] = refs
    
    # Copy metadata unchanged
    if 'metadata' in provenance_data:
        result['metadata'] = provenance_data['metadata'].copy()
    
    return result


def sync_provenance_with_data(provenance_path: str, data: dict, id_map: dict = None) -> None:
    """
    Synchronize provenance IDs with the final USDM data.
    
    Uses multiple strategies to match entities:
    1. Direct ID mapping (if id_map provided)
    2. Name-based matching (entities with same name get same ID)
    
    Args:
        provenance_path: Path to provenance JSON file
        data: Final USDM data (after any ID conversions)
        id_map: Optional direct ID mapping from convert_ids_to_uuids
    """
    if not os.path.exists(provenance_path):
        return
    
    with open(provenance_path, 'r', encoding='utf-8') as f:
        prov = json.load(f)
    
    # Build name-to-ID map from final data
    name_map = build_name_to_id_map(data)
    
    # Also need provenance entity names to do the mapping
    # Load the original SoA file to get names for provenance IDs
    soa_path = provenance_path.replace('_provenance.json', '.json')
    prov_id_to_name = {'activities': {}, 'encounters': {}, 'epochs': {}, 'plannedTimepoints': {}}
    
    if os.path.exists(soa_path):
        with open(soa_path, 'r', encoding='utf-8') as f:
            soa_data = json.load(f)
        
        # Extract from SoA structure
        try:
            sd = soa_data.get('study', {}).get('versions', [{}])[0].get('studyDesigns', [{}])[0]
            for act in sd.get('activities', []):
                if act.get('id') and act.get('name'):
                    prov_id_to_name['activities'][act['id']] = act['name']
            for enc in sd.get('encounters', []):
                if enc.get('id') and enc.get('name'):
                    prov_id_to_name['encounters'][enc['id']] = enc['name']
            for epoch in sd.get('epochs', []):
                if epoch.get('id') and epoch.get('name'):
                    prov_id_to_name['epochs'][epoch['id']] = epoch['name']
            for pt in sd.get('plannedTimepoints', []):
                if pt.get('id') and pt.get('name'):
                    prov_id_to_name['plannedTimepoints'][pt['id']] = pt['name']
        except (KeyError, IndexError, TypeError):
            pass
    
    def convert_id(old_id: str, entity_type: str) -> str:
        """Convert old ID to new ID using id_map or name matching."""
        # Try direct mapping first
        if id_map and old_id in id_map:
            return id_map[old_id]
        
        # Try name-based matching
        if entity_type in prov_id_to_name and entity_type in name_map:
            name = prov_id_to_name[entity_type].get(old_id)
            if name and name in name_map[entity_type]:
                return name_map[entity_type][name]
        
        # Return original if no mapping found
        return old_id
    
    # Convert entity IDs in provenance
    if 'entities' in prov:
        for entity_type, entities in prov['entities'].items():
            if isinstance(entities, dict):
                prov['entities'][entity_type] = {
                    convert_id(eid, entity_type): source 
                    for eid, source in entities.items()
                }
    
    # Convert cell IDs (format: "act_id|pt_id")
    if 'cells' in prov:
        new_cells = {}
        for key, source in prov['cells'].items():
            if '|' in key:
                act_id, pt_id = key.split('|', 1)
                # Activities and plannedTimepoints/encounters
                new_act_id = convert_id(act_id, 'activities')
                new_pt_id = convert_id(pt_id, 'plannedTimepoints')
                if new_pt_id == pt_id:  # Try encounters if plannedTimepoints didn't match
                    new_pt_id = convert_id(pt_id, 'encounters')
                new_key = f"{new_act_id}|{new_pt_id}"
                new_cells[new_key] = source
            else:
                new_cells[key] = source
        prov['cells'] = new_cells
    
    # Save updated provenance
    with open(provenance_path, 'w', encoding='utf-8') as f:
        json.dump(prov, f, indent=2)


def convert_provenance_ids(provenance_path: str, id_map: dict) -> None:
    """
    DEPRECATED: Use sync_provenance_with_data instead.
    
    Convert simple IDs to UUIDs in provenance file.
    """
    if not os.path.exists(provenance_path) or not id_map:
        return
    
    with open(provenance_path, 'r', encoding='utf-8') as f:
        prov = json.load(f)
    
    def convert_id(simple_id: str) -> str:
        return id_map.get(simple_id, simple_id)
    
    # Convert entity IDs
    if 'entities' in prov:
        for entity_type, entities in prov['entities'].items():
            if isinstance(entities, dict):
                prov['entities'][entity_type] = {
                    convert_id(eid): source 
                    for eid, source in entities.items()
                }
    
    # Convert cell IDs (format: "act_id|pt_id")
    if 'cells' in prov:
        new_cells = {}
        for key, source in prov['cells'].items():
            if '|' in key:
                act_id, pt_id = key.split('|', 1)
                new_key = f"{convert_id(act_id)}|{convert_id(pt_id)}"
                new_cells[new_key] = source
            else:
                new_cells[key] = source
        prov['cells'] = new_cells
    
    # Save updated provenance
    with open(provenance_path, 'w', encoding='utf-8') as f:
        json.dump(prov, f, indent=2)


def validate_and_fix_schema(
    data: dict,
    output_dir: str,
    model: str = "gemini-2.5-pro",
    use_llm: bool = True,
    convert_to_uuids: bool = True,
) -> tuple:
    """
    Validate USDM data against schema and auto-fix issues.
    
    Validation Pipeline:
    1. Convert simple IDs to UUIDs (required by USDM 4.0)
    2. Run programmatic fixes via OpenAPI validator + LLM fixer
    3. Validate with official usdm Pydantic package (authoritative)
    
    Args:
        data: USDM JSON data
        output_dir: Directory for output files
        model: LLM model for auto-fixes
        use_llm: Whether to use LLM for complex fixes
        convert_to_uuids: Whether to convert simple IDs to UUIDs
        
    Returns:
        Tuple of (fixed_data, validation_result, fixer_result)
    """
    from validation import (
        validate_usdm_dict, HAS_USDM, USDM_VERSION,  # Official validation
    )
    from core.usdm_types_generated import normalize_usdm_data
    
    logger.info("=" * 60)
    logger.info("USDM v4.0 Schema Validation Pipeline")
    logger.info("=" * 60)
    
    # Step 1: Normalize data using dataclass auto-population
    # This leverages type inference in Encounter, StudyArm, Epoch, Code objects
    logger.info("\n[1/3] Normalizing entities (type inference)...")
    data = normalize_usdm_data(data)
    logger.info("      ✓ Applied type inference to Encounters, Epochs, Arms, Codes")
    
    # Step 2: Convert IDs to UUIDs (USDM 4.0 requirement)
    id_map = {}
    if convert_to_uuids:
        logger.info("\n[2/3] Converting IDs to UUIDs...")
        data, id_map = convert_ids_to_uuids(data)
        logger.info(f"      Converted {len(id_map)} IDs to UUIDs")
        
        # Save ID mapping for reference
        id_map_path = os.path.join(output_dir, "id_mapping.json")
        with open(id_map_path, 'w', encoding='utf-8') as f:
            json.dump(id_map, f, indent=2)
        
        # Generate protocol_usdm_provenance.json with converted IDs
        # This ensures provenance keys match protocol_usdm.json exactly
        orig_provenance_path = os.path.join(output_dir, "9_final_soa_provenance.json")
        if os.path.exists(orig_provenance_path):
            with open(orig_provenance_path, 'r', encoding='utf-8') as f:
                orig_provenance = json.load(f)
            
            # Convert provenance IDs using the same id_map
            converted_provenance = convert_provenance_to_uuids(orig_provenance, id_map)
            
            # Save as protocol_usdm_provenance.json (paired with protocol_usdm.json)
            prov_output_path = os.path.join(output_dir, "protocol_usdm_provenance.json")
            with open(prov_output_path, 'w', encoding='utf-8') as f:
                json.dump(converted_provenance, f, indent=2)
            logger.info(f"      ✓ Created protocol_usdm_provenance.json ({len(converted_provenance.get('cells', {}))} cells)")
    
    fixed_data = data
    fixer_result = None
    
    # Step 3: Validate with official usdm package (authoritative)
    logger.info("\n[3/3] Official USDM Package Validation...")
    usdm_result = None
    
    if HAS_USDM:
        logger.info(f"      Using usdm package (USDM {USDM_VERSION})")
        try:
            usdm_result = validate_usdm_dict(fixed_data)
            
            if usdm_result.valid:
                logger.info("      ✓ VALIDATION PASSED")
            else:
                logger.warning(f"      ✗ VALIDATION FAILED: {usdm_result.error_count} errors")
                # Group and summarize errors
                error_types = {}
                for issue in usdm_result.issues:
                    error_types[issue.error_type] = error_types.get(issue.error_type, 0) + 1
                for etype, count in sorted(error_types.items(), key=lambda x: -x[1])[:5]:
                    logger.warning(f"        - {etype}: {count}x")
                if len(error_types) > 5:
                    logger.warning(f"        ... and {len(error_types) - 5} more error types")
            
            # Save detailed validation result
            validation_output = os.path.join(output_dir, "usdm_validation.json")
            with open(validation_output, 'w', encoding='utf-8') as f:
                json.dump(usdm_result.to_dict(), f, indent=2)
            logger.info(f"      Results saved to: usdm_validation.json")
                
        except Exception as e:
            logger.error(f"      Validation error: {e}")
    else:
        logger.warning("      ⚠ usdm package not installed")
        logger.warning("      Install with: pip install usdm")
    
    logger.info("=" * 60)
    
    return fixed_data, usdm_result, fixer_result, usdm_result, id_map if convert_to_uuids else {}


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
                    if data.get('success', True):  # Default to True if not present
                        loaded[phase] = data
                        logger.debug(f"Loaded previous extraction: {phase}")
            except (json.JSONDecodeError, IOError) as e:
                logger.debug(f"Could not load {filename}: {e}")
    
    return loaded


def combine_to_full_usdm(
    output_dir: str,
    soa_data: dict = None,
    expansion_results: dict = None,
) -> dict:
    """
    Combine SoA and expansion results into unified USDM JSON.
    
    This function merges:
    1. Data from expansion_results (current run, object format)
    2. Data from previously saved JSON files (prior runs, dict format)
    
    Previously extracted data is used as fallback when expansion_results
    doesn't contain data for a phase.
    """
    from datetime import datetime
    
    # Load previously extracted data from JSON files
    previous_extractions = load_previous_extractions(output_dir)
    logger.info(f"Loaded {len(previous_extractions)} previous extractions from output directory")
    
    # USDM v4.0 compliant structure:
    # study.versions[0].studyDesigns[] contains the actual data
    combined = {
        "usdmVersion": "4.0",
        "generatedAt": datetime.now().isoformat(),
        "generator": "Protocol2USDM v6.5.0",
        "study": {
            "id": "study_1",
            "instanceType": "Study",
            "versions": []  # Will be populated with study version containing studyDesigns
        },
    }
    
    # Temporary container for study version data
    study_version = {
        "id": "sv_1",
        "instanceType": "StudyVersion",
        "versionIdentifier": "1.0",
        "studyDesigns": [],
    }
    
    # Add Study Metadata to study_version (USDM v4.0 compliant)
    metadata_added = False
    if expansion_results and expansion_results.get('metadata'):
        r = expansion_results['metadata']
        if r.success and r.metadata:
            md = r.metadata
            study_version["titles"] = [t.to_dict() for t in md.titles]
            study_version["studyIdentifiers"] = [i.to_dict() for i in md.identifiers]
            # USDM-compliant: organizations go to studyVersion (per dataStructure.yml)
            study_version["organizations"] = [o.to_dict() for o in md.organizations]
            if md.study_phase:
                study_version["studyPhase"] = md.study_phase.to_dict()
            # Store indications temporarily - will be added to studyDesign later
            if md.indications:
                combined["_temp_indications"] = [i.to_dict() for i in md.indications]
            metadata_added = True
    
    # Fallback to previously extracted metadata
    if not metadata_added and previous_extractions.get('metadata'):
        prev = previous_extractions['metadata']
        if prev.get('metadata'):
            md = prev['metadata']
            if md.get('titles'):
                study_version["titles"] = md['titles']
            if md.get('identifiers'):
                study_version["studyIdentifiers"] = md['identifiers']
            if md.get('organizations'):
                study_version["organizations"] = md['organizations']
            if md.get('studyPhase'):
                study_version["studyPhase"] = md['studyPhase']
            if md.get('indications'):
                combined["_temp_indications"] = md['indications']
            logger.info("  Using previously extracted metadata")
    
    # Build StudyDesign container with all required fields
    study_design = {
        "id": "sd_1", 
        "name": "Study Design",
        "rationale": "Protocol-defined study design for investigating efficacy and safety",
        "instanceType": "InterventionalStudyDesign",
        # Model will be added based on arms count
    }
    
    # Add Study Design Structure
    studydesign_added = False
    if expansion_results and expansion_results.get('studydesign'):
        r = expansion_results['studydesign']
        if r.success and r.data:
            sd = r.data
            if sd.study_design:
                if sd.study_design.blinding_schema:
                    study_design["blindingSchema"] = {"code": sd.study_design.blinding_schema.value}
                if sd.study_design.randomization_type:
                    study_design["randomizationType"] = {"code": sd.study_design.randomization_type.value}
            study_design["arms"] = [a.to_dict() for a in sd.arms]
            study_design["studyCohorts"] = [c.to_dict() for c in sd.cohorts]
            study_design["studyCells"] = [c.to_dict() for c in sd.cells]
            studydesign_added = True
    
    # Fallback to previously extracted study design
    if not studydesign_added and previous_extractions.get('studydesign'):
        prev = previous_extractions['studydesign']
        if prev.get('studyDesign'):
            sd = prev['studyDesign']
            if sd.get('blindingSchema'):
                study_design["blindingSchema"] = sd['blindingSchema']
            if sd.get('randomizationType'):
                study_design["randomizationType"] = sd['randomizationType']
            if sd.get('arms'):
                study_design["arms"] = sd['arms']
            if sd.get('cohorts'):
                study_design["studyCohorts"] = sd['cohorts']
            if sd.get('cells'):
                study_design["studyCells"] = sd['cells']
            logger.info("  Using previously extracted study design")
    
    # Add Eligibility Criteria
    eligibility_added = False
    if expansion_results and expansion_results.get('eligibility'):
        r = expansion_results['eligibility']
        if r.success and r.data:
            # USDM-compliant: EligibilityCriterionItems go to studyVersion (per dataStructure.yml)
            if r.data.criterion_items:
                study_version["eligibilityCriterionItems"] = [item.to_dict() for item in r.data.criterion_items]
            # EligibilityCriteria stay in studyDesign (per dataStructure.yml)
            study_design["eligibilityCriteria"] = [c.to_dict() for c in r.data.criteria]
            if r.data.population:
                study_design["population"] = r.data.population.to_dict()
            eligibility_added = True
    
    # Fallback to previously extracted eligibility
    if not eligibility_added and previous_extractions.get('eligibility'):
        prev = previous_extractions['eligibility']
        if prev.get('eligibility'):
            elig = prev['eligibility']
            if elig.get('criterionItems'):
                study_version["eligibilityCriterionItems"] = elig['criterionItems']
            if elig.get('criteria'):
                study_design["eligibilityCriteria"] = elig['criteria']
            if elig.get('population'):
                study_design["population"] = elig['population']
            logger.info("  Using previously extracted eligibility")
    
    # Ensure population is always present (required by USDM schema)
    if "population" not in study_design:
        study_design["population"] = {
            "id": "pop_1",
            "instanceType": "StudyDesignPopulation",
            "name": "Study Population",
            "description": "Target population for the study as defined by eligibility criteria",
            "includesHealthySubjects": False  # Required field per USDM schema
        }
    elif "includesHealthySubjects" not in study_design["population"]:
        study_design["population"]["includesHealthySubjects"] = False
    
    # Add Objectives & Endpoints
    objectives_added = False
    if expansion_results and expansion_results.get('objectives'):
        r = expansion_results['objectives']
        if r.success and r.data:
            study_design["objectives"] = [o.to_dict() for o in r.data.objectives]
            study_design["endpoints"] = [e.to_dict() for e in r.data.endpoints]
            if r.data.estimands:
                study_design["estimands"] = [e.to_dict() for e in r.data.estimands]
            objectives_added = True
    
    # Fallback to previously extracted objectives
    if not objectives_added and previous_extractions.get('objectives'):
        prev = previous_extractions['objectives']
        if prev.get('objectives'):
            obj = prev['objectives']
            if obj.get('objectives'):
                study_design["objectives"] = obj['objectives']
            if obj.get('endpoints'):
                study_design["endpoints"] = obj['endpoints']
            if obj.get('estimands'):
                study_design["estimands"] = obj['estimands']
            logger.info("  Using previously extracted objectives")
    
    # Add Interventions
    interventions_added = False
    if expansion_results and expansion_results.get('interventions'):
        r = expansion_results['interventions']
        if r.success and r.data:
            # USDM-compliant: studyInterventions go to studyVersion (per dataStructure.yml)
            study_version["studyInterventions"] = [i.to_dict() for i in r.data.interventions]
            # USDM-compliant: administrableProducts go to studyVersion (per dataStructure.yml)
            study_version["administrableProducts"] = [p.to_dict() for p in r.data.products]
            # Administrations and substances - keep at root for now (product details)
            combined["administrations"] = [a.to_dict() for a in r.data.administrations]
            combined["substances"] = [s.to_dict() for s in r.data.substances]
            interventions_added = True
    
    # Fallback to previously extracted interventions
    if not interventions_added and previous_extractions.get('interventions'):
        prev = previous_extractions['interventions']
        if prev.get('interventions'):
            intv = prev['interventions']
            if intv.get('studyInterventions'):
                study_version["studyInterventions"] = intv['studyInterventions']
            if intv.get('administrableProducts'):
                # Ensure administrableDoseForm has required standardCode (USDM 4.0)
                products = []
                for p in intv['administrableProducts']:
                    if isinstance(p, dict):
                        dose_form = p.get('administrableDoseForm', {})
                        if dose_form and 'code' in dose_form and 'standardCode' not in dose_form:
                            p = dict(p)  # Copy to avoid mutating original
                            p['administrableDoseForm'] = {
                                **dose_form,
                                'standardCode': {
                                    'id': str(uuid.uuid4()),
                                    'code': dose_form.get('code', ''),
                                    'codeSystem': dose_form.get('codeSystem', 'http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl'),
                                    'codeSystemVersion': dose_form.get('codeSystemVersion', '25.01d'),
                                    'decode': dose_form.get('decode', ''),
                                    'instanceType': 'Code',
                                }
                            }
                    products.append(p)
                study_version["administrableProducts"] = products
            if intv.get('administrations'):
                combined["administrations"] = intv['administrations']
            if intv.get('substances'):
                combined["substances"] = intv['substances']
            if intv.get('medicalDevices'):
                study_version["medicalDevices"] = intv['medicalDevices']
            logger.info("  Using previously extracted interventions")
    
    # Add SoA data - check multiple possible locations
    if soa_data:
        soa_schedule = None
        
        # Try 1: USDM v4.0 path - study.versions[0].studyDesigns[0]
        if "study" in soa_data:
            try:
                sds = soa_data["study"]["versions"][0].get("studyDesigns", [])
                if sds and (sds[0].get("activities") or sds[0].get("scheduleTimelines")):
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
        
        # Try 2: Top-level studyDesigns
        if not soa_schedule and "studyDesigns" in soa_data and soa_data["studyDesigns"]:
            soa_schedule = soa_data["studyDesigns"][0]
        
        if soa_schedule:
            # Copy all SoA-related keys (including notes for SoA footnotes)
            soa_keys = ["scheduleTimelines", "encounters", "activities", "epochs", 
                        "plannedTimepoints", "activityTimepoints", "activityGroups", "notes"]
            for key in soa_keys:
                if key in soa_schedule and soa_schedule[key]:
                    study_design[key] = soa_schedule[key]
    
    # Ensure arms is always present (required by USDM schema for InterventionalStudyDesign)
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
    
    # Ensure studyCells is always present (required by USDM schema)
    if "studyCells" not in study_design or not study_design["studyCells"]:
        # Create cells linking arms to epochs
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
            # Fallback: create at least one cell
            study_design["studyCells"] = [{
                "id": "cell_1",
                "armId": study_design["arms"][0]["id"] if study_design.get("arms") else "arm_1",
                "epochId": epochs[0].get("id", "epoch_1") if epochs else "epoch_1",
                "elementIds": [],
                "instanceType": "StudyCell"
            }]
    
    # Add model field (required) - infer from arms count
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
    
    # Add indications to studyDesign (USDM-compliant: studyDesign.indications, not study.indications)
    if combined.get("_temp_indications"):
        study_design["indications"] = combined.pop("_temp_indications")
    
    # Add studyDesign to study_version (not to root)
    study_version["studyDesigns"] = [study_design]
    
    # Add Narrative Content
    # USDM-compliant: abbreviations go in studyVersion.abbreviations
    narrative_added = False
    if expansion_results and expansion_results.get('narrative'):
        r = expansion_results['narrative']
        if r.success and r.data:
            # USDM-compliant: narrativeContentItems go to studyVersion (per dataStructure.yml)
            study_version["narrativeContentItems"] = [s.to_dict() for s in r.data.sections]
            study_version["abbreviations"] = [a.to_dict() for a in r.data.abbreviations]
            if r.data.document:
                combined["studyDefinitionDocument"] = r.data.document.to_dict()
            narrative_added = True
    
    # Fallback to previously extracted narrative
    if not narrative_added and previous_extractions.get('narrative'):
        prev = previous_extractions['narrative']
        if prev.get('narrative'):
            narr = prev['narrative']
            if narr.get('narrativeContentItems'):
                study_version["narrativeContentItems"] = narr['narrativeContentItems']
            elif narr.get('narrativeContents'):
                study_version["narrativeContentItems"] = narr['narrativeContents']
            if narr.get('abbreviations'):
                study_version["abbreviations"] = narr['abbreviations']
            if narr.get('studyDefinitionDocument'):
                combined["studyDefinitionDocument"] = narr['studyDefinitionDocument']
            logger.info("  Using previously extracted narrative")
    
    # Add Advanced Entities
    # USDM-compliant: amendments go to studyVersion.amendments (per dataStructure.yml)
    advanced_added = False
    if expansion_results and expansion_results.get('advanced'):
        r = expansion_results['advanced']
        if r.success and r.data:
            if r.data.amendments:
                study_version["amendments"] = [a.to_dict() for a in r.data.amendments]
            if r.data.geographic_scope:
                combined["geographicScope"] = r.data.geographic_scope.to_dict()
            if r.data.countries:
                combined["countries"] = [c.to_dict() for c in r.data.countries]
            advanced_added = True
    
    # Fallback to previously extracted advanced entities
    if not advanced_added and previous_extractions.get('advanced'):
        prev = previous_extractions['advanced']
        if prev.get('advanced'):
            adv = prev['advanced']
            if adv.get('studyAmendments'):
                study_version["amendments"] = adv['studyAmendments']
            elif adv.get('amendments'):
                study_version["amendments"] = adv['amendments']
            if adv.get('geographicScope'):
                combined["geographicScope"] = adv['geographicScope']
            if adv.get('countries'):
                combined["countries"] = adv['countries']
            logger.info("  Using previously extracted advanced entities")
    
    # Add Procedures & Devices (Phase 10)
    # USDM-compliant: procedures go in activity.definedProcedures, not at root
    if expansion_results and expansion_results.get('procedures'):
        r = expansion_results['procedures']
        if r.success and r.data:
            data_dict = r.data.to_dict()
            procedures_list = data_dict.get('procedures', [])
            
            # Link procedures to activities via definedProcedures
            if procedures_list and study_design.get('activities'):
                # Build name-to-procedure mapping for matching
                proc_by_name = {}
                for proc in procedures_list:
                    proc_name = proc.get('name', '').lower()
                    if proc_name:
                        proc_by_name[proc_name] = proc
                        # Also add without common suffixes for fuzzy matching
                        for suffix in [' sampling', ' collection', ' test', ' assessment']:
                            if proc_name.endswith(suffix):
                                proc_by_name[proc_name[:-len(suffix)]] = proc
                
                # Match procedures to activities
                procedures_linked = 0
                for activity in study_design['activities']:
                    act_name = activity.get('name', '').lower()
                    matched_procs = []
                    
                    # Direct match
                    if act_name in proc_by_name:
                        matched_procs.append(proc_by_name[act_name])
                    
                    # Partial match - procedure name in activity name or vice versa
                    for proc_name, proc in proc_by_name.items():
                        if proc not in matched_procs:
                            if proc_name in act_name or act_name in proc_name:
                                matched_procs.append(proc)
                    
                    if matched_procs:
                        activity['definedProcedures'] = matched_procs
                        procedures_linked += len(matched_procs)
                
                # Any unmatched procedures go to a general "Other" activity or studyDesign.procedures
                unmatched = [p for p in procedures_list if not any(
                    p in act.get('definedProcedures', []) for act in study_design['activities']
                )]
                if unmatched:
                    # Add unmatched to studyDesign.procedures as fallback
                    study_design['procedures'] = unmatched
            
            # USDM-compliant: medicalDevices go to studyVersion (per dataStructure.yml)
            if data_dict.get('medicalDevices'):
                study_version["medicalDevices"] = data_dict['medicalDevices']
            # Ingredients and strengths are product-related, keep at root for now
            if data_dict.get('ingredients'):
                combined["ingredients"] = data_dict['ingredients']
            if data_dict.get('strengths'):
                combined["strengths"] = data_dict['strengths']
    
    # Add Scheduling Logic (Phase 11)
    # USDM-compliant: timings/exits go in scheduleTimeline, conditions in studyVersion
    scheduling_added = False
    if expansion_results and expansion_results.get('scheduling'):
        r = expansion_results['scheduling']
        if r.success and r.data:
            data_dict = r.data.to_dict()
            
            # Timings and exits go into scheduleTimeline (per USDM spec)
            if study_design.get('scheduleTimelines'):
                main_timeline = study_design['scheduleTimelines'][0]
                if data_dict.get('timings'):
                    if 'timings' not in main_timeline:
                        main_timeline['timings'] = []
                    main_timeline['timings'].extend(data_dict['timings'])
                    
                    # USDM Enhancement: Link timingId on ScheduledActivityInstances
                    linked = link_timing_ids_to_instances(study_design)
                    if linked > 0:
                        logger.info(f"  Linked {linked} instances to timings")
                
                if data_dict.get('scheduleTimelineExits'):
                    if 'exits' not in main_timeline:
                        main_timeline['exits'] = []
                    main_timeline['exits'].extend(data_dict['scheduleTimelineExits'])
            
            # Conditions go to studyVersion (per USDM spec)
            if data_dict.get('conditions'):
                study_version["conditions"] = data_dict['conditions']
            
            # TransitionRules stay at root for now (need element linkage)
            if data_dict.get('transitionRules'):
                combined["transitionRules"] = data_dict['transitionRules']
            scheduling_added = True
    
    # Fallback to previously extracted scheduling
    if not scheduling_added and previous_extractions.get('scheduling'):
        prev = previous_extractions['scheduling']
        if prev.get('scheduling'):
            sched = prev['scheduling']
            if study_design.get('scheduleTimelines') and sched.get('timings'):
                main_timeline = study_design['scheduleTimelines'][0]
                if 'timings' not in main_timeline:
                    main_timeline['timings'] = []
                main_timeline['timings'].extend(sched['timings'])
                
                # USDM Enhancement: Link timingId on ScheduledActivityInstances
                linked = link_timing_ids_to_instances(study_design)
                if linked > 0:
                    logger.info(f"  Linked {linked} instances to timings")
            
            if sched.get('conditions'):
                study_version["conditions"] = sched['conditions']
            if sched.get('transitionRules'):
                combined["transitionRules"] = sched['transitionRules']
            logger.info("  Using previously extracted scheduling")
    
    # Add SAP data (from --sap extraction)
    # USDM-compliant: analysisPopulations go in studyDesign.analysisPopulations
    sap_added = False
    if expansion_results and expansion_results.get('sap'):
        r = expansion_results['sap']
        if r.success and r.data:
            data_dict = r.data.to_dict()
            if data_dict.get('analysisPopulations'):
                study_design["analysisPopulations"] = data_dict['analysisPopulations']
            if data_dict.get('characteristics'):
                study_design["characteristics"] = data_dict['characteristics']
            sap_added = True
    
    # Fallback to previously extracted SAP
    if not sap_added and previous_extractions.get('sap'):
        prev = previous_extractions['sap']
        if prev.get('sap'):
            sap = prev['sap']
            if sap.get('analysisPopulations'):
                study_design["analysisPopulations"] = sap['analysisPopulations']
            if sap.get('characteristics'):
                study_design["characteristics"] = sap['characteristics']
            logger.info("  Using previously extracted SAP populations")
    
    # Add Sites data (conditional)
    if expansion_results and expansion_results.get('sites'):
        r = expansion_results['sites']
        if r.success and r.data:
            data_dict = r.data.to_dict()
            if data_dict.get('studySites'):
                combined["studySites"] = data_dict['studySites']
            if data_dict.get('studyRoles'):
                combined["studyRoles"] = data_dict['studyRoles']
            if data_dict.get('assignedPersons'):
                combined["assignedPersons"] = data_dict['assignedPersons']
    
    # Add Document Structure (Phase 12)
    if expansion_results and expansion_results.get('docstructure'):
        r = expansion_results['docstructure']
        if r.success and r.data:
            data_dict = r.data.to_dict()
            if data_dict.get('documentContentReferences'):
                combined["documentContentReferences"] = data_dict['documentContentReferences']
            if data_dict.get('commentAnnotations'):
                combined["commentAnnotations"] = data_dict['commentAnnotations']
            if data_dict.get('studyDefinitionDocumentVersions'):
                combined["studyDefinitionDocumentVersions"] = data_dict['studyDefinitionDocumentVersions']
    
    # Add Amendment Details (Phase 13)
    if expansion_results and expansion_results.get('amendmentdetails'):
        r = expansion_results['amendmentdetails']
        if r.success and r.data:
            data_dict = r.data.to_dict()
            if data_dict.get('studyAmendmentImpacts'):
                combined["studyAmendmentImpacts"] = data_dict['studyAmendmentImpacts']
            if data_dict.get('studyAmendmentReasons'):
                combined["studyAmendmentReasons"] = data_dict['studyAmendmentReasons']
            if data_dict.get('studyChanges'):
                combined["studyChanges"] = data_dict['studyChanges']
    
    # Add computational execution metadata
    combined["computationalExecution"] = {
        "ready": True,
        "supportedSystems": ["EDC", "ePRO", "CTMS", "RTSM"],
        "validationStatus": "pending",
    }
    
    # Assemble final USDM v4.0 structure: study.versions[0] contains all data
    combined["study"]["versions"] = [study_version]
    
    # Add Execution Model (Phase 14) - enrich studyDesigns with execution semantics
    # Must be done AFTER study.versions is assembled so enrich can find studyDesigns
    execution_data = None
    if expansion_results and expansion_results.get('execution'):
        r = expansion_results['execution']
        if r.success and r.data:
            from extraction.execution import enrich_usdm_with_execution_model
            combined = enrich_usdm_with_execution_model(combined, r.data)
            execution_data = r.data
            logger.info(f"  ✓ Enriched USDM with execution model (Phase 14)")
    
    # Reconcile Epochs (Phase 15) - merge epoch sources, identify main flow
    # This runs after execution model so we have traversal constraints
    try:
        study_design = combined.get("study", {}).get("versions", [{}])[0].get("studyDesigns", [{}])[0]
        soa_epochs = study_design.get("epochs", [])
        
        # Extract traversal sequence from execution model if available
        traversal_sequence = None
        if execution_data and hasattr(execution_data, 'traversal_constraints'):
            constraints = execution_data.traversal_constraints or []
            if constraints and hasattr(constraints[0], 'required_sequence'):
                traversal_sequence = constraints[0].required_sequence
        
        # Also check extension attributes for traversal constraints
        if not traversal_sequence:
            extensions = study_design.get("extensionAttributes", [])
            for ext in extensions:
                if ext.get("url", "").endswith("traversalConstraints") and ext.get("valueString"):
                    try:
                        import json as json_mod
                        constraints = json_mod.loads(ext["valueString"])
                        if constraints and isinstance(constraints, list) and constraints[0].get("requiredSequence"):
                            traversal_sequence = constraints[0]["requiredSequence"]
                            break
                    except (json.JSONDecodeError, KeyError, IndexError):
                        pass
        
        # Epoch reconciliation - now preserves original IDs
        if soa_epochs:
            reconciled_epochs = reconcile_epochs_from_pipeline(
                soa_epochs=soa_epochs,
                traversal_sequence=traversal_sequence,
            )
            if reconciled_epochs:
                study_design["epochs"] = reconciled_epochs
                main_epochs = [e for e in reconciled_epochs if any(
                    ext.get("valueString") == "main" 
                    for ext in e.get("extensionAttributes", [])
                    if ext.get("url", "").endswith("epochCategory")
                )]
                logger.info(f"  ✓ Reconciled {len(reconciled_epochs)} epochs ({len(main_epochs)} main, {len(reconciled_epochs) - len(main_epochs)} sub)")
        
        # NOTE: Encounter/Activity reconciliation is DISABLED because it generates new IDs
        # that break references in scheduleTimelines (which causes missing ticks in UI).
        # TODO: Either preserve original IDs or update scheduleTimeline references after reconciliation.
        # 
        # # Reconcile encounters
        # soa_encounters = study_design.get("encounters", [])
        # if soa_encounters:
        #     visit_windows = None
        #     if execution_data and hasattr(execution_data, 'visit_windows'):
        #         visit_windows = [vw.__dict__ if hasattr(vw, '__dict__') else vw 
        #                         for vw in (execution_data.visit_windows or [])]
        #     reconciled_encounters = reconcile_encounters_from_pipeline(
        #         soa_encounters=soa_encounters,
        #         visit_windows=visit_windows,
        #     )
        #     if reconciled_encounters:
        #         study_design["encounters"] = reconciled_encounters
        #         logger.info(f"  ✓ Reconciled {len(reconciled_encounters)} encounters")
        
        # Activity reconciliation also DISABLED - same ID reference issue as encounters
        # # Reconcile activities
        # soa_activities = study_design.get("activities", [])
        # if soa_activities:
        #     procedure_activities = None
        #     if expansion_results and expansion_results.get('procedures'):
        #         proc_result = expansion_results['procedures']
        #         if proc_result.success and proc_result.data:
        #             if hasattr(proc_result.data, 'procedures'):
        #                 procedure_activities = [
        #                     p.__dict__ if hasattr(p, '__dict__') else p 
        #                     for p in (proc_result.data.procedures or [])
        #                 ]
        #             elif isinstance(proc_result.data, dict):
        #                 procedure_activities = proc_result.data.get('procedures', [])
        #     execution_repetitions = None
        #     if execution_data and hasattr(execution_data, 'repetitions'):
        #         execution_repetitions = [r.__dict__ if hasattr(r, '__dict__') else r 
        #                                 for r in (execution_data.repetitions or [])]
        #     footnote_conditions = None
        #     if execution_data and hasattr(execution_data, 'footnote_conditions'):
        #         footnote_conditions = [f.__dict__ if hasattr(f, '__dict__') else f 
        #                               for f in (execution_data.footnote_conditions or [])]
        #     reconciled_activities = reconcile_activities_from_pipeline(
        #         soa_activities=soa_activities,
        #         procedure_activities=procedure_activities,
        #         execution_repetitions=execution_repetitions,
        #         footnote_conditions=footnote_conditions,
        #     )
        #     if reconciled_activities:
        #         study_design["activities"] = reconciled_activities
        #         logger.info(f"  ✓ Reconciled {len(reconciled_activities)} activities")
                
    except Exception as e:
        logger.warning(f"  ⚠ Entity reconciliation skipped: {e}")
    
    # Save combined output as protocol_usdm.json (golden standard)
    output_path = os.path.join(output_dir, "protocol_usdm.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\n✓ Combined USDM saved to: {output_path}")
    return combined, output_path


def main():
    parser = argparse.ArgumentParser(
        description="Extract Schedule of Activities from clinical protocol PDF (v2 - Simplified)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main_v2.py protocol.pdf                    # SoA extraction only
    python main_v2.py protocol.pdf --soa              # SoA + validation + conformance
    python main_v2.py protocol.pdf --full-protocol    # Everything (SoA + all expansions + validation)
    python main_v2.py protocol.pdf --expansion-only --full-protocol  # Expansions only, no SoA
    python main_v2.py protocol.pdf --eligibility --objectives  # SoA + selected phases
        """
    )
    
    parser.add_argument(
        "pdf_path",
        nargs="?",  # Optional when using --update-cache
        help="Path to the clinical protocol PDF"
    )
    
    parser.add_argument(
        "--model", "-m",
        default=DEFAULT_MODEL,
        help=f"LLM model to use (default: {DEFAULT_MODEL})"
    )
    
    parser.add_argument(
        "--output-dir", "-o",
        help="Output directory (default: output/<protocol_name>_<timestamp>)"
    )
    
    parser.add_argument(
        "--pages", "-p",
        help="Comma-separated SoA page numbers (1-indexed, matching PDF viewer). If not provided, will auto-detect."
    )
    
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip vision validation step"
    )
    
    parser.add_argument(
        "--remove-hallucinations",
        action="store_true",
        help="Remove cells not confirmed by vision (default: keep all text-extracted cells)"
    )
    
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.7,
        help="Confidence threshold for removing hallucinations (default: 0.7)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--view",
        action="store_true",
        help="Launch Streamlit viewer after extraction"
    )
    
    parser.add_argument(
        "--no-view",
        action="store_true",
        help="Don't launch Streamlit viewer (default behavior)"
    )
    
    parser.add_argument(
        "--enrich",
        action="store_true",
        help="Enrich entities with NCI terminology codes (Step 7)"
    )
    
    parser.add_argument(
        "--update-evs-cache",
        action="store_true",
        help="Update the EVS terminology cache before enrichment"
    )
    
    parser.add_argument(
        "--validate-schema",
        action="store_true",
        help="Validate output against USDM schema (Step 8)"
    )
    
    parser.add_argument(
        "--conformance",
        action="store_true",
        help="Run CDISC CORE conformance rules (Step 9)"
    )
    
    parser.add_argument(
        "--update-cache",
        action="store_true",
        help="Update CDISC CORE rules cache (requires CDISC_API_KEY in .env)"
    )
    
    parser.add_argument(
        "--soa",
        action="store_true",
        help="Run full SoA pipeline including enrichment, validation, and conformance (Steps 7-9)"
    )
    
    # USDM Expansion flags (v6.0)
    expansion_group = parser.add_argument_group('USDM Expansion (v6.0)')
    expansion_group.add_argument(
        "--metadata",
        action="store_true",
        help="Extract study metadata (Phase 2)"
    )
    expansion_group.add_argument(
        "--eligibility",
        action="store_true",
        help="Extract eligibility criteria (Phase 1)"
    )
    expansion_group.add_argument(
        "--objectives",
        action="store_true",
        help="Extract objectives & endpoints (Phase 3)"
    )
    expansion_group.add_argument(
        "--studydesign",
        action="store_true",
        help="Extract study design structure (Phase 4)"
    )
    expansion_group.add_argument(
        "--interventions",
        action="store_true",
        help="Extract interventions & products (Phase 5)"
    )
    expansion_group.add_argument(
        "--narrative",
        action="store_true",
        help="Extract narrative structure & abbreviations (Phase 7)"
    )
    expansion_group.add_argument(
        "--advanced",
        action="store_true",
        help="Extract amendments & geographic scope (Phase 8)"
    )
    expansion_group.add_argument(
        "--full-protocol",
        action="store_true",
        help="Extract EVERYTHING: SoA + all expansion phases"
    )
    expansion_group.add_argument(
        "--expansion-only",
        action="store_true",
        help="Run expansion phases only, skip SoA extraction"
    )
    expansion_group.add_argument(
        "--procedures",
        action="store_true",
        help="Extract procedures & medical devices (Phase 10)"
    )
    expansion_group.add_argument(
        "--scheduling",
        action="store_true",
        help="Extract scheduling logic & timing (Phase 11)"
    )
    expansion_group.add_argument(
        "--docstructure",
        action="store_true",
        help="Extract document structure & references (Phase 12)"
    )
    expansion_group.add_argument(
        "--amendmentdetails",
        action="store_true",
        help="Extract amendment details & changes (Phase 13)"
    )
    expansion_group.add_argument(
        "--execution",
        action="store_true",
        help="Extract execution model semantics (Phase 14 - time anchors, repetitions, crossover)"
    )
    expansion_group.add_argument(
        "--complete",
        action="store_true",
        help="Run COMPLETE extraction: full protocol + SAP (if provided) + all post-processing"
    )
    
    # Conditional source arguments
    conditional_group = parser.add_argument_group('Conditional Sources (additional documents)')
    conditional_group.add_argument(
        "--sap",
        type=str,
        metavar="PATH",
        help="Path to SAP PDF for analysis population extraction"
    )
    conditional_group.add_argument(
        "--sites",
        type=str,
        metavar="PATH",
        help="Path to site list (CSV/Excel) for site extraction"
    )
    
    
    args = parser.parse_args()
    
    # Handle --update-cache flag first (can be standalone operation)
    if args.update_cache:
        logger.info("Updating CDISC CORE rules cache...")
        from validation.cdisc_conformance import CORE_ENGINE_PATH
        core_dir = CORE_ENGINE_PATH.parent
        
        # Get API key
        api_key = os.environ.get('CDISC_LIBRARY_API_KEY') or os.environ.get('CDISC_API_KEY')
        if not api_key:
            logger.error("CDISC_API_KEY not found in .env file")
            logger.error("Get your API key from: https://www.cdisc.org/cdisc-library")
            sys.exit(1)
        
        import subprocess
        try:
            result = subprocess.run(
                [str(CORE_ENGINE_PATH), "update-cache", "--apikey", api_key],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(core_dir),
            )
            if result.returncode == 0:
                logger.info("✓ CDISC CORE cache updated successfully")
            else:
                logger.error(f"Cache update failed: {result.stderr}")
                sys.exit(1)
        except Exception as e:
            logger.error(f"Cache update error: {e}")
            sys.exit(1)
        
        # If no PDF path provided, exit after cache update
        if not args.pdf_path:
            logger.info("Cache update complete. Provide a PDF path to run the pipeline.")
            sys.exit(0)
    
    # Validate PDF path (required for pipeline operations)
    if not args.pdf_path:
        logger.error("PDF path is required. Use --help for usage.")
        sys.exit(1)
    if not os.path.exists(args.pdf_path):
        logger.error(f"PDF file not found: {args.pdf_path}")
        sys.exit(1)
    
    # Set up output directory
    protocol_name = Path(args.pdf_path).stem
    if args.output_dir:
        # Use user-specified output directory directly
        output_dir = args.output_dir
    else:
        # Default: Create timestamped folder for each run
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join("output", f"{protocol_name}_{timestamp}")
    
    # Parse page numbers if provided (user gives 1-indexed, convert to 0-indexed)
    soa_pages = None
    if args.pages:
        try:
            # User provides 1-indexed pages (matching PDF viewer), convert to 0-indexed
            soa_pages = [int(p.strip()) - 1 for p in args.pages.split(",")]
            logger.info(f"Using specified SoA pages: {[p+1 for p in soa_pages]} (PDF viewer numbering)")
        except ValueError:
            logger.error(f"Invalid page numbers: {args.pages}")
            sys.exit(1)
    
    # Configure pipeline
    config = PipelineConfig(
        model_name=args.model,
        validate_with_vision=not args.no_validate,
        remove_hallucinations=args.remove_hallucinations,  # Default False (keep all cells)
        hallucination_confidence_threshold=args.confidence_threshold,
        save_intermediate=True,
    )
    
    # Handle --complete flag (enables everything)
    if args.complete:
        args.full_protocol = True
        args.soa = True  # Full SoA pipeline with post-processing
        args.enrich = True
        args.validate_schema = True
        args.conformance = True
        logger.info("Complete mode: enabling full protocol extraction with all post-processing")
    
    # Determine which expansion phases to run
    run_any_expansion = (args.full_protocol or args.expansion_only or 
                         args.metadata or args.eligibility or args.objectives or
                         args.studydesign or args.interventions or args.narrative or 
                         args.advanced or args.procedures or args.scheduling or
                         args.docstructure or args.amendmentdetails or args.execution)
    
    expansion_phases = {
        'metadata': args.full_protocol or args.metadata,
        'eligibility': args.full_protocol or args.eligibility,
        'objectives': args.full_protocol or args.objectives,
        'studydesign': args.full_protocol or args.studydesign,
        'interventions': args.full_protocol or args.interventions,
        'narrative': args.full_protocol or args.narrative,
        'advanced': args.full_protocol or args.advanced,
        'procedures': args.full_protocol or args.procedures,
        'scheduling': args.full_protocol or args.scheduling,
        'docstructure': args.full_protocol or args.docstructure,
        'amendmentdetails': args.full_protocol or args.amendmentdetails,
        'execution': args.full_protocol or args.execution,
    }
    
    # Conditional source phases (only run if source file provided)
    conditional_sources = {
        'sap': args.sap,  # Path to SAP PDF
        'sites': args.sites,  # Path to sites file
    }
    
    run_soa = not args.expansion_only
    
    # Print configuration
    logger.info("="*60)
    logger.info("Protocol2USDM v6.5.0 - Full Protocol Extraction")
    logger.info("="*60)
    logger.info(f"Input PDF: {args.pdf_path}")
    logger.info(f"Output Directory: {output_dir}")
    logger.info(f"Model: {config.model_name}")
    logger.info(f"SoA Extraction: {'Enabled' if run_soa else 'Disabled'}")
    if run_any_expansion:
        enabled = [k for k, v in expansion_phases.items() if v]
        logger.info(f"Expansion Phases: {', '.join(enabled)}")
    logger.info("="*60)
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Run pipeline
    try:
        result = None
        soa_data = None
        
        # Run SoA extraction if not skipped
        if run_soa:
            logger.info("\n" + "="*60)
            logger.info("SCHEDULE OF ACTIVITIES EXTRACTION")
            logger.info("="*60)
            result = run_from_files(
                pdf_path=args.pdf_path,
                output_dir=output_dir,
                soa_pages=soa_pages,
                config=config,
            )
            
            # Load SoA data for combining
            if result.success and result.output_path:
                with open(result.output_path, 'r', encoding='utf-8') as f:
                    soa_data = json.load(f)
        else:
            # Check for existing SoA
            existing_soa = os.path.join(output_dir, "9_final_soa.json")
            if os.path.exists(existing_soa):
                logger.info(f"Loading existing SoA from {existing_soa}")
                with open(existing_soa, 'r', encoding='utf-8') as f:
                    soa_data = json.load(f)
        
        # Print SoA results
        if result:
            print()
            logger.info("="*60)
            if result.success:
                logger.info("SOA EXTRACTION COMPLETED SUCCESSFULLY")
            else:
                logger.error("SOA EXTRACTION COMPLETED WITH ERRORS")
            logger.info("="*60)
            
            logger.info(f"Activities extracted: {result.activities_count}")
            logger.info(f"Timepoints: {result.timepoints_count}")
            logger.info(f"Ticks: {result.ticks_count}")
            
            if result.validated:
                logger.info(f"Hallucinations removed: {result.hallucinations_removed}")
                logger.info(f"Possibly missed ticks: {result.missed_ticks_found}")
            
            if result.output_path:
                logger.info(f"Output: {result.output_path}")
            if result.provenance_path:
                logger.info(f"Provenance: {result.provenance_path}")
            
            if result.errors:
                logger.warning("Errors encountered:")
                for err in result.errors:
                    logger.warning(f"  - {err}")
            
            logger.info("="*60)
        
        # Run expansion phases if requested
        expansion_results = {}
        if run_any_expansion:
            logger.info("\n" + "="*60)
            logger.info("USDM EXPANSION PHASES")
            logger.info("="*60)
            
            expansion_results = run_expansion_phases(
                pdf_path=args.pdf_path,
                output_dir=output_dir,
                model=config.model_name,
                phases=expansion_phases,
                soa_data=soa_data,
            )
            
            # Print expansion summary (exclude _pipeline_context from count)
            success_count = sum(1 for k, r in expansion_results.items() if k != '_pipeline_context' and hasattr(r, 'success') and r.success)
            total_count = sum(1 for k in expansion_results if k != '_pipeline_context')
            logger.info(f"\n✓ Expansion phases: {success_count}/{total_count} successful")
        
        # Run conditional source extraction if files provided
        if conditional_sources.get('sap'):
            logger.info("\n--- Conditional: SAP Analysis Populations ---")
            try:
                from extraction.conditional import extract_from_sap
                sap_result = extract_from_sap(conditional_sources['sap'], model=config.model_name, output_dir=output_dir)
                if sap_result.success:
                    expansion_results['sap'] = sap_result
                    logger.info(f"  ✓ SAP extraction ({sap_result.data.to_dict()['summary']['populationCount']} populations)")
                else:
                    logger.warning(f"  ✗ SAP extraction failed: {sap_result.error}")
            except Exception as e:
                logger.warning(f"  ✗ SAP extraction error: {e}")
        
        if conditional_sources.get('sites'):
            logger.info("\n--- Conditional: Study Sites ---")
            try:
                from extraction.conditional import extract_from_sites
                sites_result = extract_from_sites(conditional_sources['sites'], output_dir=output_dir)
                if sites_result.success:
                    expansion_results['sites'] = sites_result
                    logger.info(f"  ✓ Sites extraction ({sites_result.data.to_dict()['summary']['siteCount']} sites)")
                else:
                    logger.warning(f"  ✗ Sites extraction failed: {sites_result.error}")
            except Exception as e:
                logger.warning(f"  ✗ Sites extraction error: {e}")
        
        # Combine outputs - always run if we have any data (soa_data or expansion)
        # This ensures protocol_usdm.json is created for viewer even for SoA-only runs
        combined_usdm_path = None
        schema_validation_result = None
        schema_fixer_result = None
        
        if args.full_protocol or run_any_expansion or soa_data:
            logger.info("\n" + "="*60)
            logger.info("COMBINING OUTPUTS")
            logger.info("="*60)
            combined_data, combined_usdm_path = combine_to_full_usdm(output_dir, soa_data, expansion_results)
            
            # ═══════════════════════════════════════════════════════════════
            # SCHEMA VALIDATION & AUTO-FIX (integrated into combine phase)
            # ═══════════════════════════════════════════════════════════════
            logger.info("\n" + "="*60)
            logger.info("SCHEMA VALIDATION & AUTO-FIX")
            logger.info("="*60)
            
            # Validate and fix schema issues
            use_llm_for_fixes = not args.no_validate  # Use LLM unless explicitly disabled
            fixed_data, schema_validation_result, schema_fixer_result, usdm_result, id_map = validate_and_fix_schema(
                combined_data,
                output_dir,
                model=config.model_name,
                use_llm=use_llm_for_fixes,
            )
            
            # Save the fixed data back to protocol_usdm.json
            # (Always save since UUID conversion happens)
            with open(combined_usdm_path, 'w', encoding='utf-8') as f:
                json.dump(fixed_data, f, indent=2, ensure_ascii=False)
            logger.info(f"  ✓ USDM output saved to: {combined_usdm_path}")
            
            # Note: protocol_usdm_provenance.json is created during validate_and_fix_schema
            # with UUID-converted IDs that match protocol_usdm.json exactly
            prov_path = os.path.join(output_dir, "protocol_usdm_provenance.json")
            if os.path.exists(prov_path):
                logger.info(f"  ✓ Provenance file: protocol_usdm_provenance.json")
            
            combined_data = fixed_data
            
            # Save schema validation results (including unfixable issues)
            schema_output_path = os.path.join(output_dir, "schema_validation.json")
            schema_output = {
                "valid": usdm_result.valid if usdm_result else (schema_validation_result.valid if schema_validation_result else False),
                "schemaVersion": "4.0",
                "validator": "usdm_pydantic" if usdm_result else "openapi_custom",
                "summary": {
                    "errorsCount": usdm_result.error_count if usdm_result else 0,
                    "warningsCount": usdm_result.warning_count if usdm_result else 0,
                },
                "issues": [i.to_dict() for i in (usdm_result.issues if usdm_result else (schema_validation_result.issues if schema_validation_result else []))],
            }
            if schema_fixer_result:
                schema_output["fixerSummary"] = {
                    "originalIssues": schema_fixer_result.original_issues,
                    "fixedIssues": schema_fixer_result.fixed_issues,
                    "remainingIssues": schema_fixer_result.remaining_issues,
                    "iterations": schema_fixer_result.iterations,
                }
                schema_output["fixesApplied"] = [f.to_dict() for f in schema_fixer_result.fixes_applied]
                schema_output["unfixableIssues"] = [i.to_dict() for i in schema_fixer_result.unfixable_issues]
            
            with open(schema_output_path, 'w', encoding='utf-8') as f:
                json.dump(schema_output, f, indent=2, ensure_ascii=False)
            logger.info(f"  Schema validation report: {schema_output_path}")
        
        # Determine which output to validate with legacy/conformance
        # For full-protocol: validate combined output
        # For SoA-only: validate SoA output
        validation_target = combined_usdm_path if combined_usdm_path else (result.output_path if result else None)
        
        # Run post-processing steps if requested
        if validation_target:
            run_enrich = args.enrich or args.soa or args.full_protocol
            run_validate = args.validate_schema or args.soa or args.full_protocol
            run_conform = args.conformance or args.soa or args.full_protocol
            
            if run_enrich:
                logger.info("\n--- Step 7: Terminology Enrichment ---")
                from enrichment.terminology import enrich_terminology as enrich_fn, update_evs_cache
                
                # Update EVS cache if requested
                if args.update_evs_cache:
                    logger.info("  Updating EVS terminology cache...")
                    cache_result = update_evs_cache()
                    logger.info(f"  Cache updated: {cache_result.get('success', 0)} codes fetched")
                
                enrich_result = enrich_fn(validation_target, output_dir=output_dir)
                enriched = enrich_result.get('enriched', 0)
                total = enrich_result.get('total_entities', 0)
                if enriched > 0:
                    logger.info(f"  ✓ Enriched {enriched}/{total} entities with NCI codes")
                    by_type = enrich_result.get('by_type', {})
                    for etype, count in by_type.items():
                        logger.info(f"    - {etype}: {count}")
                else:
                    logger.info(f"  No entities required enrichment")
            
            if run_validate:
                # Skip legacy validation if OpenAPI validation was already done
                if schema_validation_result is not None:
                    logger.info("\n--- Step 8: Schema Validation (already completed) ---")
                    if usdm_result and usdm_result.valid:
                        logger.info(f"  ✓ Schema validation PASSED")
                    elif usdm_result:
                        logger.warning(f"  Schema validation: {usdm_result.error_count} errors, "
                                      f"{usdm_result.warning_count} warnings")
                    else:
                        logger.info(f"  Schema validation completed")
                else:
                    # Run validation for SoA-only outputs
                    logger.info("\n--- Step 8: Schema Validation ---")
                    with open(validation_target, 'r', encoding='utf-8') as f:
                        target_data = json.load(f)
                    
                    fixed_data, schema_validation_result, schema_fixer_result, usdm_result, id_map = validate_and_fix_schema(
                        target_data,
                        output_dir,
                        model=config.model_name,
                        use_llm=not args.no_validate,
                    )
                    
                    # Save fixed data (UUID conversion always happens)
                    with open(validation_target, 'w', encoding='utf-8') as f:
                        json.dump(fixed_data, f, indent=2, ensure_ascii=False)
                    logger.info(f"  ✓ Fixed data saved")
                    
                    # Note: protocol_usdm_provenance.json is created during validate_and_fix_schema
                    prov_path = os.path.join(output_dir, "protocol_usdm_provenance.json")
                    if os.path.exists(prov_path):
                        logger.info(f"  ✓ Provenance file: protocol_usdm_provenance.json")
                    
                    # Save schema validation report
                    schema_output_path = os.path.join(output_dir, "schema_validation.json")
                    schema_output = {
                        "valid": usdm_result.valid if usdm_result else False,
                        "schemaVersion": "4.0",
                        "validator": "usdm_pydantic" if usdm_result else "none",
                        "summary": {
                            "errorsCount": usdm_result.error_count if usdm_result else 0,
                            "warningsCount": usdm_result.warning_count if usdm_result else 0,
                        },
                        "issues": [i.to_dict() for i in (usdm_result.issues if usdm_result else [])],
                    }
                    if schema_fixer_result:
                        schema_output["fixerSummary"] = {
                            "originalIssues": schema_fixer_result.original_issues,
                            "fixedIssues": schema_fixer_result.fixed_issues,
                            "remainingIssues": schema_fixer_result.remaining_issues,
                        }
                        schema_output["fixesApplied"] = [f.to_dict() for f in schema_fixer_result.fixes_applied]
                    
                    with open(schema_output_path, 'w', encoding='utf-8') as f:
                        json.dump(schema_output, f, indent=2, ensure_ascii=False)
                    
                    final_valid = usdm_result.valid if usdm_result else (schema_validation_result.valid if schema_validation_result else False)
                    if final_valid:
                        logger.info(f"  ✓ Schema validation PASSED")
                    else:
                        logger.warning(f"  Schema validation found issues (see schema_validation.json)")
            
            if run_conform:
                logger.info("\n--- Step 9: CDISC Conformance ---")
                from validation.cdisc_conformance import run_cdisc_conformance as conform_fn
                conform_result = conform_fn(validation_target, output_dir)
                if conform_result.get('success'):
                    issues = conform_result.get('issues', 0)
                    warnings = conform_result.get('warnings', 0)
                    if issues == 0 and warnings == 0:
                        logger.info(f"  ✓ Conformance passed - no issues found")
                    else:
                        logger.info(f"  Conformance: {issues} errors, {warnings} warnings")
                    logger.info(f"  ✓ Conformance report: {output_dir}/conformance_report.json")
                else:
                    error_msg = conform_result.get('error', 'Unknown error')
                    error_summary = conform_result.get('error_summary', '')
                    logger.warning(f"  ✗ CDISC CORE failed: {error_msg}")
                    if error_summary:
                        logger.warning(f"    Details: {error_summary}")
                    logger.info(f"  Error saved to: {output_dir}/conformance_report.json")
            
            # Update computational execution status if full protocol
            if combined_usdm_path and run_validate and schema_validation_result is not None:
                with open(combined_usdm_path, 'r', encoding='utf-8') as f:
                    final_data = json.load(f)
                if "computationalExecution" not in final_data:
                    final_data["computationalExecution"] = {}
                final_data["computationalExecution"]["validationStatus"] = "complete" if schema_validation_result.valid else "issues_found"
                with open(combined_usdm_path, 'w', encoding='utf-8') as f:
                    json.dump(final_data, f, indent=2, ensure_ascii=False)
        
        # Launch Streamlit viewer if requested
        if args.view:
            if combined_usdm_path and os.path.exists(combined_usdm_path):
                launch_viewer(combined_usdm_path)
            elif result and result.success and result.output_path:
                launch_viewer(result.output_path)
        
        # Determine overall success
        soa_success = result.success if result else True  # If no SoA, consider it OK
        expansion_success = all(r.success for k, r in expansion_results.items() if k != '_pipeline_context' and hasattr(r, 'success')) if expansion_results else True
        overall_success = soa_success and expansion_success
        
        # Final summary
        logger.info("\n" + "="*60)
        logger.info("EXTRACTION COMPLETE")
        logger.info("="*60)
        if run_soa:
            logger.info(f"SoA: {'✓ Success' if (result and result.success) else '✗ Failed'}")
        if run_any_expansion:
            exp_success = sum(1 for k, r in expansion_results.items() if k != '_pipeline_context' and hasattr(r, 'success') and r.success)
            exp_total = sum(1 for k in expansion_results if k != '_pipeline_context')
            logger.info(f"Expansion: {exp_success}/{exp_total} phases successful")
        
        # Schema validation summary
        if schema_validation_result is not None:
            if schema_validation_result.valid:
                logger.info(f"Schema: ✓ Valid (USDM {schema_validation_result.usdm_version_expected})")
            else:
                logger.info(f"Schema: ⚠ {schema_validation_result.error_count} errors, "
                           f"{schema_validation_result.warning_count} warnings")
            if schema_fixer_result and schema_fixer_result.fixed_issues > 0:
                logger.info(f"  Auto-fixed: {schema_fixer_result.fixed_issues} issues")
        
        if combined_usdm_path:
            logger.info(f"Golden Standard Output: {combined_usdm_path}")
        logger.info("="*60)
        
        sys.exit(0 if overall_success else 1)
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def launch_viewer(soa_path: str):
    """Launch the Streamlit SoA viewer."""
    import subprocess
    
    viewer_script = os.path.join(os.path.dirname(__file__), "soa_streamlit_viewer.py")
    
    if not os.path.exists(viewer_script):
        logger.warning(f"Viewer not found: {viewer_script}")
        return
    
    logger.info(f"Launching SoA viewer...")
    
    try:
        subprocess.Popen(
            ["streamlit", "run", viewer_script, "--", soa_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        logger.warning(f"Could not launch viewer: {e}")
        logger.info(f"Run manually: streamlit run soa_viewer.py -- {soa_path}")


if __name__ == "__main__":
    main()
