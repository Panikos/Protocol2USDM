"""
USDM Validation and ID Conversion Utilities

This module contains shared functions for:
- Converting simple IDs to UUIDs (USDM 4.0 requirement)
- Provenance ID synchronization
- Schema validation and auto-fixing

These functions are used by both main_v2.py and main_v3.py.
"""

import json
import logging
import os
import re
import uuid as uuid_module

logger = logging.getLogger(__name__)


def convert_ids_to_uuids(data: dict, id_map: dict = None) -> tuple:
    """
    Convert all simple IDs (like 'study_1', 'act_1') to proper UUIDs.
    
    USDM 4.0 requires all 'id' fields to be valid UUIDs.
    This function recursively converts IDs while maintaining internal references.
    
    Args:
        data: USDM JSON data
        id_map: Optional existing ID mapping (for consistency)
        
    Returns:
        Tuple of (data with UUIDs, ID mapping used)
    """
    if id_map is None:
        id_map = {}
    
    def is_simple_id(value):
        """Check if value looks like a simple ID that needs conversion."""
        if not isinstance(value, str):
            return False
        # Skip if already a UUID format
        try:
            uuid_module.UUID(value)
            return False  # Already a valid UUID
        except ValueError:
            pass
        # Check for common ID patterns
        id_patterns = ['_', '-']
        return any(p in value for p in id_patterns) and len(value) < 50
    
    def get_or_create_uuid(simple_id: str) -> str:
        """Get existing UUID for ID or create new one."""
        if simple_id not in id_map:
            id_map[simple_id] = str(uuid_module.uuid4())
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
                elif key == 'valueString' and isinstance(value, str):
                    # Handle JSON-encoded data in extension attribute valueString
                    # This contains footnote conditions, execution model data, etc.
                    try:
                        if value.startswith('[') or value.startswith('{'):
                            parsed = json.loads(value)
                            converted_parsed = convert_recursive(parsed)
                            result[key] = json.dumps(converted_parsed)
                        else:
                            result[key] = value
                    except (json.JSONDecodeError, TypeError):
                        result[key] = value
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


def convert_provenance_to_uuids(
    provenance_data: dict, 
    id_map: dict,
    soa_data: dict = None,
    usdm_data: dict = None
) -> dict:
    """
    Convert provenance IDs to UUIDs using the same id_map from convert_ids_to_uuids.
    
    This creates a new provenance dict with all IDs converted to UUIDs,
    ensuring perfect alignment with protocol_usdm.json.
    
    Handles both:
    - New format: enc_N (encounterId directly from extraction)
    - Legacy format: pt_N (plannedTimepointId, backward compat)
    - Name-based fallback: If act_N not in id_map, match by activity name
    
    Args:
        provenance_data: Original provenance dict (entities, cells, cellFootnotes, metadata)
        id_map: ID mapping from convert_ids_to_uuids {simple_id: uuid}
        soa_data: Original 9_final_soa.json data (for activity name lookup)
        usdm_data: Final USDM data after ID conversion (for target UUID lookup)
        
    Returns:
        New provenance dict with all IDs converted to UUIDs
    """
    if not provenance_data or not id_map:
        return provenance_data
    
    # Build pt_N -> enc_N UUID mapping for backward compatibility
    # Legacy provenance used pt_1, pt_2... but id_map has enc_1, enc_2...
    pt_to_enc_uuid = {}
    for key, uuid_val in id_map.items():
        match = re.match(r'^enc_(\d+)$', key)
        if match:
            n = match.group(1)
            # Map pt_N directly to enc_N's UUID (backward compat)
            pt_to_enc_uuid[f"pt_{n}"] = uuid_val
    
    # Build name-based activity mapping for reconciliation cases
    # When SoA activities get replaced by procedure activities with different IDs
    act_name_to_uuid = {}
    soa_act_id_to_name = {}
    
    if soa_data and usdm_data:
        # Get SOA activity names by ID
        try:
            soa_sd = soa_data.get('study', {}).get('versions', [{}])[0].get('studyDesigns', [{}])[0]
            for act in soa_sd.get('activities', []):
                act_id = act.get('id')
                act_name = act.get('name', '').lower().strip()
                if act_id and act_name:
                    soa_act_id_to_name[act_id] = act_name
        except Exception:
            pass
        
        # Get USDM activity UUIDs by name
        try:
            usdm_sd = usdm_data.get('study', {}).get('versions', [{}])[0].get('studyDesigns', [{}])[0]
            for act in usdm_sd.get('activities', []):
                act_id = act.get('id')
                act_name = act.get('name', '').lower().strip()
                if act_id and act_name:
                    act_name_to_uuid[act_name] = act_id
        except Exception:
            pass
    
    # Build set of valid USDM activity UUIDs for validation
    usdm_activity_ids = set(act_name_to_uuid.values()) if act_name_to_uuid else set()
    
    def convert_id(old_id: str) -> str:
        """Convert ID using id_map, with name-based fallback for replaced activities."""
        # Direct lookup first
        if old_id in id_map:
            mapped_uuid = id_map[old_id]
            # Verify the mapped UUID exists in USDM (may not if activity was replaced)
            if not usdm_activity_ids or mapped_uuid in usdm_activity_ids:
                return mapped_uuid
            # UUID from id_map doesn't exist in USDM - fall through to name-based
        
        # Name-based fallback for act_N IDs that got replaced during reconciliation
        if old_id.startswith('act_') and soa_act_id_to_name and act_name_to_uuid:
            act_name = soa_act_id_to_name.get(old_id)
            if act_name and act_name in act_name_to_uuid:
                return act_name_to_uuid[act_name]
        
        # Return original or id_map result if nothing else works
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
        Tuple of (fixed_data, validation_result, fixer_result, usdm_result, id_map)
    """
    from validation import (
        validate_usdm_dict,  # Schema validation only
        validate_usdm_semantic,  # Schema + cross-reference checks
        HAS_USDM, USDM_VERSION,
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
        soa_path = os.path.join(output_dir, "9_final_soa.json")
        if os.path.exists(orig_provenance_path):
            with open(orig_provenance_path, 'r', encoding='utf-8') as f:
                orig_provenance = json.load(f)
            
            # Load SOA data for name-based activity mapping
            soa_data = None
            if os.path.exists(soa_path):
                with open(soa_path, 'r', encoding='utf-8') as f:
                    soa_data = json.load(f)
            
            # Convert provenance IDs using id_map + name-based fallback for replaced activities
            converted_provenance = convert_provenance_to_uuids(
                orig_provenance, id_map, soa_data=soa_data, usdm_data=data
            )
            
            # Populate encounter/activity name mappings from USDM data
            # This ensures UI can resolve UUIDs to display names
            try:
                sd = data.get('study', {}).get('versions', [{}])[0].get('studyDesigns', [{}])[0]
                if 'entities' not in converted_provenance:
                    converted_provenance['entities'] = {}
                
                # Add encounters with names
                converted_provenance['entities']['encounters'] = {
                    enc.get('id'): enc.get('name', 'Unknown')
                    for enc in sd.get('encounters', []) if enc.get('id')
                }
                # Add activities with names
                converted_provenance['entities']['activities'] = {
                    act.get('id'): act.get('name') or act.get('label', 'Unknown')
                    for act in sd.get('activities', []) if act.get('id')
                }
                # Add epochs with names
                converted_provenance['entities']['epochs'] = {
                    epoch.get('id'): epoch.get('name', 'Unknown')
                    for epoch in sd.get('epochs', []) if epoch.get('id')
                }
                
                # Note: We do NOT add provenance for enrichment-created instances.
                # The SoA provenance should only track original PDF ticks.
                # Enrichment instances are separate from SoA.
            except Exception:
                pass  # Keep original entities if extraction fails
            
            # Save as protocol_usdm_provenance.json (paired with protocol_usdm.json)
            prov_output_path = os.path.join(output_dir, "protocol_usdm_provenance.json")
            with open(prov_output_path, 'w', encoding='utf-8') as f:
                json.dump(converted_provenance, f, indent=2)
            logger.info(f"      ✓ Created protocol_usdm_provenance.json ({len(converted_provenance.get('cells', {}))} cells)")
    
    fixed_data = data
    fixer_result = None
    
    # Step 3: Validate with official usdm package (authoritative)
    logger.info("\n[3/3] Official USDM Package Validation...")
    schema_result = None  # Schema-only validation
    usdm_result = None    # Schema + semantic validation
    
    if HAS_USDM:
        logger.info(f"      Using usdm package (USDM {USDM_VERSION})")
        try:
            # 3a. Schema validation (structure/types only) → schema_validation.json
            logger.info("      [3a] Schema validation (structure/types)...")
            schema_result = validate_usdm_dict(fixed_data)
            
            if schema_result.valid:
                logger.info("          ✓ Schema validation PASSED")
            else:
                logger.warning(f"          ✗ Schema validation: {schema_result.error_count} errors")
            
            # 3b. Semantic validation (schema + cross-references) → usdm_validation.json
            logger.info("      [3b] Semantic validation (cross-references)...")
            usdm_result = validate_usdm_semantic(fixed_data)
            
            # Count semantic-only issues (warnings about references)
            xref_errors = len([i for i in usdm_result.issues if i.error_type in 
                             ('dangling_reference', 'orphaned_entity', 'missing_relationship')])
            
            if usdm_result.valid:
                logger.info("          ✓ Semantic validation PASSED")
            else:
                logger.warning(f"          ✗ Semantic validation: {usdm_result.error_count} errors, {usdm_result.warning_count} warnings")
                if xref_errors:
                    logger.info(f"          ({xref_errors} cross-reference issues)")
            
            # Group and summarize errors
            error_types = {}
            for issue in usdm_result.issues:
                error_types[issue.error_type] = error_types.get(issue.error_type, 0) + 1
            for etype, count in sorted(error_types.items(), key=lambda x: -x[1])[:5]:
                logger.warning(f"        - {etype}: {count}x")
            if len(error_types) > 5:
                logger.warning(f"        ... and {len(error_types) - 5} more error types")
            
            # Save semantic validation result (schema + cross-references)
            validation_output = os.path.join(output_dir, "usdm_validation.json")
            usdm_output = usdm_result.to_dict()
            usdm_output['validator_type'] = 'usdm_pydantic_semantic'  # Indicate semantic checks included
            usdm_output['includes_cross_references'] = True
            with open(validation_output, 'w', encoding='utf-8') as f:
                json.dump(usdm_output, f, indent=2)
            logger.info(f"      Results saved to: usdm_validation.json")
                
        except Exception as e:
            logger.error(f"      Validation error: {e}")
    else:
        logger.warning("      ⚠ usdm package not installed")
        logger.warning("      Install with: pip install usdm")
    
    logger.info("=" * 60)
    
    # Return schema_result for schema_validation.json, usdm_result for usdm_validation.json
    return fixed_data, schema_result, fixer_result, usdm_result, id_map if convert_to_uuids else {}
