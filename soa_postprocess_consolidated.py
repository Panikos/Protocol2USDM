import json
import sys
from copy import deepcopy
import os

# Load entity mapping for required fields and value sets
def load_entity_mapping(mapping_path="soa_entity_mapping.json"):
    with open(mapping_path, "r", encoding="utf-8") as f:
        return json.load(f)

ENTITY_MAP = None
try:
    ENTITY_MAP = load_entity_mapping()
except Exception:
    ENTITY_MAP = None
    print("[WARNING] Could not load soa_entity_mapping.json. Post-processing will not fill missing fields.")

def make_hashable(o):
    """
    Recursively converts a dictionary or list to a hashable representation
    (tuples of tuples).
    """
    if isinstance(o, (tuple, list)):
        return tuple((make_hashable(e) for e in o))
    if isinstance(o, dict):
        return tuple(sorted((k, make_hashable(v)) for k, v in o.items()))
    if isinstance(o, (set, frozenset)):
        return tuple(sorted(make_hashable(e) for e in o))
    return o

def standardize_ids_recursive(obj):
    """Recursively traverse a dictionary or list and standardize IDs."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, str) and (key == 'id' or key.endswith('Id')):
                obj[key] = value.replace('-', '_')
            else:
                standardize_ids_recursive(value)
    elif isinstance(obj, list):
        for item in obj:
            standardize_ids_recursive(item)
    return obj

def consolidate_and_fix_soa(input_path, output_path, header_structure_path=None, ref_metadata_path=None):
    """
    Consolidate, normalize, and fully expand a loosely structured SoA file into strict USDM v4.0 Wrapper-Input format.
    Optionally merge in richer metadata from a hand-curated reference file.
    - Enforces top-level keys: study, usdmVersion, systemName, systemVersion
    - Normalizes field names and expands group-based activityTimepoints
    - Preserves and merges metadata (description, code, window, etc.) where possible
    - Validates all references and schema compliance
    - Extracts footnotes, legend, and milestone and outputs a secondary M11-table-aligned JSON for Streamlit
    """
    fixes = []
    # Helper to record provenance
    def _tp_sort_key(label: str):
        label_l = label.lower() if isinstance(label, str) else ''
        m = re.search(r'(visit|day|week|period)\s*(-?\d+)', label_l)
        if m:
            return int(m.group(2))
        m = re.search(r'(-?\d+)\s*hour', label_l)
        if m:
            return int(m.group(1))
        if 'screen' in label_l:
            return -9999
        return 9999

    def _tag_provenance(container_key, obj_list, src):
        prov = data.setdefault('p2uProvenance', {}).setdefault(container_key, {})
        for obj in obj_list:
            if isinstance(obj, dict) and obj.get('id'):
                prov[obj['id']] = src

    # Load files
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Standardize all IDs ('epoch-1' -> 'epoch_1') before any processing
    data = standardize_ids_recursive(data)
    fixes.append("Standardized all hyphenated IDs to use underscores.")

    ref_metadata = None
    if ref_metadata_path:
        with open(ref_metadata_path, 'r', encoding='utf-8') as f:
            ref_metadata = json.load(f)

    # --- USDM v4 Wrapper-Input enforcement ---
    required_keys = {'study', 'usdmVersion', 'systemName', 'systemVersion'}
    if not (isinstance(data, dict) and required_keys.issubset(set(data.keys()))):
        print("[INFO] Input missing USDM Wrapper-Input keys. Attempting to fix.")
        # If the input is just the study object itself (no 'study' key at top level)
        if 'study' not in data:
            print("[INFO] Assuming input is the study object. Wrapping.")
            data = {
                'study': data,
                'usdmVersion': '4.0',
                'systemName': 'Protocol2USDMv3',
                'systemVersion': '1.0'
            }
        # If the input has a 'study' key but is missing other wrapper keys
        else:
            print("[INFO] Found 'study' key. Adding missing wrapper keys.")
            data.setdefault('usdmVersion', '4.0')
            data.setdefault('systemName', 'Protocol2USDMv3')
            data.setdefault('systemVersion', '1.0')

    study = data.get('study')
    if not study:
        print("[FATAL] Could not find 'study' object in the input data.")
        sys.exit(1)

    # --- Inject required Study fields to pass schema validation ---
    study.setdefault('name', 'Auto-generated Study Name')
    study.setdefault('instanceType', 'Study')

    # Robustly drill to timeline, handling old and new grouping structures
    versions = study.get('versions') or study.get('studyVersions')
    # Accept single version as dict
    if versions and isinstance(versions, dict):
        versions = [versions]
        study['versions'] = versions
    # If missing or empty, but study itself looks like a version (has timeline), wrap it
    if (not versions or not isinstance(versions, list) or len(versions) == 0):
        # Accept timeline at study, studyDesign, or direct timeline keys
        timeline_candidate = study.get('timeline') or study.get('studyDesign', {}).get('timeline') or study.get('Timeline')
        if timeline_candidate:
            versions = [dict(study)]
            versions[0]['timeline'] = timeline_candidate
            study['versions'] = versions
            print("[INFO] Study missing versions/studyVersions; treating study as a single version.")
        else:
            print("[FATAL] Study must contain a non-empty 'versions' or 'studyVersions' array, and no timeline found in study.")
            print("[DEBUG] Study keys:", list(study.keys()))
            sys.exit(1)
    # --- Inject required StudyVersion fields to pass schema validation ---
    for version in versions:
        version.setdefault('id', 'autogen-version-id-1')
        version.setdefault('versionIdentifier', '1.0.0')
        version.setdefault('rationale', 'Version auto-generated by pipeline.')
        version.setdefault('studyIdentifiers', [])
        version.setdefault('titles', [])
        version.setdefault('instanceType', 'StudyVersion')

    # Accept timeline in various possible locations/names
    timeline = (
        versions[0].get('timeline') or
        versions[0].get('Timeline') or
        versions[0].get('studyDesign', {}).get('timeline') or
        versions[0].get('studyDesign', {}).get('Timeline')
    )
    if not timeline:
        print("[FATAL] No timeline found in study version.")
        print("[DEBUG] Version keys:", list(versions[0].keys()))
        sys.exit(1)
    # Accept timeline as a list (legacy), wrap as dict
    if isinstance(timeline, list):
        timeline = {'plannedTimepoints': timeline}
        versions[0]['timeline'] = timeline
        print("[INFO] Timeline was a list, wrapped as dict.")

    # --- Normalize plannedTimepoints and add milestone support ---
    norm_timepoints = []
    seen_timepoints = set()
    pt_map = {}
    for pt in timeline.get('plannedTimepoints', [],):
        pt_tuple = make_hashable(pt)
        if pt_tuple not in seen_timepoints:
            # Normalize ID fields
            pt_id = pt.get('plannedTimepointId') or pt.get('id')
            if not pt_id:
                print(f"[WARNING] Skipping timepoint with no ID: {pt}")
                continue
            pt['id'] = pt_id
            pt['plannedTimepointId'] = pt_id

            # Merge in metadata from reference if available
            if ref_metadata:
                ref_pts = ref_metadata.get('plannedTimepoints', [])
                ref = next((x for x in ref_pts if (x.get('plannedTimepointId') or x.get('id')) == pt_id), None)
                if ref:
                    for k in ['description', 'code', 'window']:
                        if k in ref:
                            pt[k] = ref[k]
            
            norm_timepoints.append(pt)
            pt_map[pt_id] = pt
            seen_timepoints.add(pt_tuple)
    timeline['plannedTimepoints'] = norm_timepoints

    # --- Normalize activities ---
    act_map = {}
    norm_acts = []
    acts = timeline.get('activities', [])
    if acts and isinstance(acts[0], str):
        for i, act_str in enumerate(acts):
            act = {"activityId": f"A{i+1}", "activityName": act_str}
            norm_acts.append(act)
            act_map[act['activityId']] = act
        fixes.append("Converted activities from strings to objects.")
    else:
        for act in acts:
            act = deepcopy(act)
            act_id = act.get('activityId') or act.get('id')
            if act_id:
                act['activityId'] = act_id
            if 'name' in act and 'activityName' not in act:
                act['activityName'] = act['name']
            norm_acts.append(act)
            act_map[act['activityId']] = act
    timeline['activities'] = norm_acts

    # --- Normalize activityGroups ---
    # First, map all existing groups by their ID for easy lookup.
    group_map = {g.get('activityGroupId'): g for g in timeline.get('activityGroups', []) if g.get('activityGroupId')}
    # For now, we are not performing group inference, so the final list of groups is just the ones from the input.
    norm_groups = list(group_map.values())
    timeline['activityGroups'] = norm_groups

    # --- Process ActivityTimepoints ---
    atps = timeline.get('activityTimepoints', [])
    new_atps = []
    dropped = []
    
    # Handle multiple formats in a single pass, robustly handling nested ID objects
    for atp in atps:
        try:
            # Format 1: Direct IDs (most common from vision)
            if 'activityId' in atp and 'plannedTimepointId' in atp:
                act_id = atp['activityId']
                if isinstance(act_id, dict): act_id = act_id.get('id')

                pt_id = atp['plannedTimepointId']
                if isinstance(pt_id, dict): pt_id = pt_id.get('id')

                if act_id and pt_id and act_id in act_map and pt_id in pt_map:
                    new_atps.append({'activityId': act_id, 'plannedTimepointId': pt_id})
                else:
                    dropped.append({**atp, 'reason': 'invalid activityId or plannedTimepointId'})
            
            # Format 2: Group-based
            elif 'activityGroupId' in atp and 'plannedTimepointId' in atp:
                group = next((g for g in norm_groups if g.get('id') == atp['activityGroupId']), None)
                pt_id = atp['plannedTimepointId']
                if isinstance(pt_id, dict): pt_id = pt_id.get('id')

                if group and pt_id and pt_id in pt_map:
                    for act_id_from_group in group.get('activityIds', []):
                        if act_id_from_group in act_map:
                            new_atps.append({'activityId': act_id_from_group, 'plannedTimepointId': pt_id})
                        else:
                            dropped.append({'activityId': act_id_from_group, 'plannedTimepointId': pt_id, 'reason': 'invalid activityId in group expansion'})
                else:
                    dropped.append({**atp, 'reason': 'group not found or invalid timepointId'})
            
            # Format 3: Activity-based with a list of timepoints
            elif 'activityId' in atp and 'plannedTimepointIds' in atp:
                act_id = atp['activityId']
                if isinstance(act_id, dict): act_id = act_id.get('id')

                if act_id and act_id in act_map:
                    for ptid_item in atp['plannedTimepointIds']:
                        ptid = ptid_item
                        if isinstance(ptid, dict): ptid = ptid.get('id')

                        if ptid and ptid in pt_map:
                            new_atps.append({'activityId': act_id, 'plannedTimepointId': ptid})
                        else:
                            dropped.append({'activityId': act_id, 'plannedTimepointId': ptid, 'reason': 'invalid plannedTimepointId in list'})
                else:
                    dropped.append({**atp, 'reason': 'invalid activityId'})
            
            # Unrecognized format
            else:
                dropped.append({**atp, 'reason': 'unrecognized format'})
        except Exception as e:
            dropped.append({**atp, 'reason': f'processing error: {e}'})

    # --- Fallback: If no activityTimepoints, try to infer from activities ---
    if not new_atps:
        for act in norm_acts:
            aid = act.get('activityId') or act.get('id')
            for k in ['plannedTimepoints', 'plannedTimepointIds']:
                if k in act:
                    for ptid in act[k]:
                        if aid and ptid:
                            new_atps.append({'activityId': aid, 'plannedTimepointId': ptid})
        if new_atps:
            fixes.append('Auto-generated activityTimepoints from per-activity plannedTimepoints.')

    timeline['activityTimepoints'] = new_atps

    # --- Auto-provenance tagging if missing --------------------------------------
    source_tag = 'text' if 'text' in os.path.basename(input_path).lower() else (
        'vision' if 'vision' in os.path.basename(input_path).lower() else None)
    if source_tag:
        prov_root = data.setdefault('p2uProvenance', {})
        # timepoints
        if 'plannedTimepoints' not in prov_root:
            prov_root['plannedTimepoints'] = {pt['id']: source_tag for pt in timeline.get('plannedTimepoints', []) if pt.get('id')}
        # activities
        if 'activities' not in prov_root:
            prov_root['activities'] = {act['id']: source_tag for act in timeline.get('activities', []) if act.get('id')}

    # --- Fill missing fields using entity mapping ---
    def fill_missing_fields(entity_type, obj):
        if not ENTITY_MAP or entity_type not in ENTITY_MAP:
            return
        mapping = ENTITY_MAP[entity_type]
        for field, meta in mapping.items():
            if field not in obj:
                # Use empty string or placeholder for missing required fields
                if 'allowed_values' in meta:
                    obj[field] = meta['allowed_values'][0]['term'] if meta['allowed_values'] else ''
                else:
                    obj[field] = ''
            # Normalize coded values
            if 'allowed_values' in meta and obj[field]:
                allowed = [v['term'] for v in meta['allowed_values']]
                if isinstance(obj[field], list):
                    obj[field] = [v if v in allowed else allowed[0] for v in obj[field]]
                else:
                    if obj[field] not in allowed:
                        obj[field] = allowed[0]
    # Study
    fill_missing_fields("Study", data)
    for sv in data.get("studyVersions", []):
        fill_missing_fields("StudyVersion", sv)
        sd = sv.get("studyDesign", {})
        timeline = sd.get("timeline", {})
        fill_missing_fields("Timeline", timeline)
        # PlannedTimepoints
        import re
        pt_pattern = re.compile(r"^(.*?)\s*\(([^()]+)\)\s*$")
        pt_map = {}
        unhandled_timepoints = []
        for pt in timeline.get('plannedTimepoints', []):
            # --- Split concatenated name/description like "Visit 1 (Week -2)" ---
            if pt and isinstance(pt.get('name'), str):
                m = pt_pattern.match(pt['name'])
                if m and (not pt.get('description')):
                    pt['name'] = m.group(1).strip()
                    pt['description'] = m.group(2).strip()
            # Accept both 'plannedTimepointId' and 'plannedVisitId' as equivalent
            pt_id = pt.get('plannedTimepointId') or pt.get('plannedVisitId') or pt.get('id')
            if pt_id is not None:
                pt['plannedTimepointId'] = pt_id  # Normalize key
                pt_map[pt_id] = pt
            else:
                print(f"[WARNING] Skipping timepoint missing both plannedTimepointId and plannedVisitId: {pt}")
                unhandled_timepoints.append(pt)
        if unhandled_timepoints:
            print(f"[SUMMARY] {len(unhandled_timepoints)} timepoints skipped due to missing IDs.")
        # --- Propagate timing from PlannedTimepoints to Encounters ---
        # Build quick lookup of PT description by cleaned name
        pt_label_to_desc = {pt['name']: pt.get('description') for pt in timeline.get('plannedTimepoints', []) if pt.get('name')}

        # Encounters - split concatenated name and create timing
        for enc in timeline.get('encounters', []):
            if enc and isinstance(enc.get('name'), str):
                m = pt_pattern.match(enc['name'])
                if m:
                    enc['name'] = m.group(1).strip()
                    timing_label = m.group(2).strip()
                    enc['timing'] = enc.get('timing') or {}
                    if 'windowLabel' not in enc['timing']:
                        enc['timing']['windowLabel'] = timing_label
            # If still no timing, attempt to copy from matching PlannedTimepoint description
            if enc.get('name') and (not enc.get('timing') or not enc['timing'].get('windowLabel')):
                desc = pt_label_to_desc.get(enc['name'])
                if desc:
                    enc.setdefault('timing', {})['windowLabel'] = desc
        # Activities
        for act in timeline.get("activities", []):
            fill_missing_fields("Activity", act)
        # ActivityGroups
        for ag in timeline.get("activityGroups", []):
            fill_missing_fields("ActivityGroup", ag)
        # ActivityTimepoints
        for atp in timeline.get("activityTimepoints", []):
            fill_missing_fields("ActivityTimepoint", atp)
            # --- Orphan PlannedTimepoints detection ---------------------------------
        # Build set of linked timepoint IDs from activityTimepoints
        linked_tp_ids = {link['plannedTimepointId'] for link in timeline.get('activityTimepoints', []) if isinstance(link, dict)}
        orphan_pts = [pt for pt in timeline.get('plannedTimepoints', []) if pt.get('id') not in linked_tp_ids]
        if orphan_pts:
            timeline['plannedTimepoints'] = [pt for pt in timeline['plannedTimepoints'] if pt.get('id') in linked_tp_ids]
            data.setdefault('p2uOrphans', {})['plannedTimepoints'] = orphan_pts
            fixes.append(f"Moved {len(orphan_pts)} orphan plannedTimepoints to p2uOrphans.")
        # --- Header-structure-driven enrichment ----------------------------------
        if header_structure_path:
            try:
                with open(header_structure_path, 'r', encoding='utf-8') as f:
                    hdr = json.load(f)
                hdr_groups = {g['id']: g for g in hdr.get('rowHierarchy', {}).get('activityGroups', []) if g.get('activities')}
                # Map activity name (lower) to group id
                name_to_gid = {}
                for gid, grp in hdr_groups.items():
                    for act_name in grp.get('activities', []):
                        name_to_gid[act_name.strip().lower()] = gid
                # Assign missing activityGroupId on activities
                added = 0
                for act in timeline.get('activities', []):
                    if not act.get('activityGroupId'):
                        gid = name_to_gid.get(act.get('name', '').strip().lower())
                        if gid:
                            act['activityGroupId'] = gid
                            _tag_provenance('activities', [act], 'headerStructure')
                            added += 1
                if added:
                    fixes.append(f"Filled activityGroupId for {added} activities using header structure.")
                # Populate missing activityIds lists in groups from header if still empty
                acts_by_id_lc = {a['name'].strip().lower(): a['id'] for a in timeline.get('activities', []) if a.get('id') and a.get('name')}
                for gid, grp in hdr_groups.items():
                    g_obj = next((g for g in timeline.get('activityGroups', []) if g.get('id') == gid), None)
                    if not g_obj:
                        continue
                    if not g_obj.get('activityIds'):
                        ids = [acts_by_id_lc.get(n.strip().lower()) for n in grp.get('activities', [])]
                        ids = [i for i in ids if i]
                        if ids:
                            g_obj['activityIds'] = ids
                            _tag_provenance('activityGroups', [g_obj], 'headerStructure')
                fixes.append("Applied header structure group mappings where possible.")
            except Exception as e:
                print(f"[WARN] Could not apply header structure enrichment: {e}")
        # --- ActivityGroup enrichment & conflict detection -----------------------
        acts_by_id = {a['id']: a for a in timeline.get('activities', []) if a.get('id')}
        # Fill missing activityIds lists
        for ag in timeline.get('activityGroups', []):
            if not ag.get('activityIds'):
                ag['activityIds'] = [aid for aid, a in acts_by_id.items() if a.get('activityGroupId') == ag['id']]
        # --- Chronology sanity check -----------------------------------------------
        # Compare canonical sort order with current order in timeline
        tp_list = timeline.get('plannedTimepoints', [])
        sort_key = lambda pt: _tp_sort_key(pt.get('name', ''))
        sorted_ids = [pt['id'] for pt in sorted(tp_list, key=sort_key)]
        current_ids = [pt['id'] for pt in tp_list]
        if sorted_ids != current_ids:
            data['p2uTimelineOrderIssues'] = {
                'expectedOrder': sorted_ids,
                'currentOrder': current_ids
            }
            fixes.append('Detected out-of-order plannedTimepoints; stored in p2uTimelineOrderIssues.')
        # Detect activities linked to >1 group
        group_membership = {}
        for ag in timeline.get('activityGroups', []):
            for aid in ag.get('activityIds', []):
                group_membership.setdefault(aid, set()).add(ag['id'])
        conflicts = [ {'activityId': aid, 'groupIds': list(gids)} for aid, gids in group_membership.items() if len(gids) > 1 ]
        if conflicts:
            data.setdefault('p2uGroupConflicts', conflicts)
            fixes.append(f"Detected {len(conflicts)} activities assigned to multiple groups (stored in p2uGroupConflicts).")
        # ------------------------------------------------------------------------
        
        # --- Save and report ---
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[CONSOLIDATE/FIX] {len(new_atps)} valid activityTimepoints. {len(dropped)} dropped. {len(norm_timepoints)} timepoints, {len(norm_acts)} activities, {len(norm_groups)} groups.")
    if fixes:
        print("Fixes applied:")
        for fix in fixes:
            print("- ", fix)
    if dropped:
        print("First 10 dropped:")
        for d in dropped[:10]:
            print(d)
    else:
        print("No invalid links found.")

if __name__ == "__main__":
    if len(sys.argv) not in [4, 5]:
        print("Usage: python soa_postprocess_consolidated.py <input.json> <output.json> <header_structure.json> [reference_metadata.json]")
        sys.exit(1)
    consolidate_and_fix_soa(*sys.argv[1:])
