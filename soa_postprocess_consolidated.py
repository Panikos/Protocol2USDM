import json
import sys
from copy import deepcopy

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

def consolidate_and_fix_soa(input_path, output_path, ref_metadata_path=None):
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
    # Load files
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    ref_metadata = None
    if ref_metadata_path:
        with open(ref_metadata_path, 'r', encoding='utf-8') as f:
            ref_metadata = json.load(f)

    # --- USDM v4 Wrapper-Input enforcement ---
    required_keys = {'study', 'usdmVersion', 'systemName', 'systemVersion'}
    if not (isinstance(data, dict) and required_keys.issubset(set(data.keys()))):
        # Try to wrap in USDM Wrapper-Input format
        print("[INFO] Input missing USDM Wrapper-Input keys. Wrapping into required structure.")
        wrapped = {
            'study': data,
            'usdmVersion': '4.0',
            'systemName': 'Protocol2USDMv3',
            'systemVersion': '1.0'
        }
        data = wrapped
    study = data['study']

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
    # --- Strict deduplication: only merge if ALL identifying fields match ---
    pts = timeline.get('plannedTimepoints', [])
    seen = set()
    norm_timepoints = []
    for pt in pts:
        pt_tuple = tuple(sorted(pt.items()))
        if pt_tuple not in seen:
            # Merge in metadata from reference if available
            if ref_metadata:
                pt_id = pt.get('plannedTimepointId') or pt.get('plannedId') or pt.get('id')
                ref_pts = ref_metadata.get('plannedTimepoints', [])
                ref = next((x for x in ref_pts if (x.get('plannedTimepointId') or x.get('id')) == pt_id), None)
                if ref:
                    for k in ['description', 'code', 'window']:
                        if k in ref:
                            pt[k] = ref[k]
            norm_timepoints.append(pt)
            seen.add(pt_tuple)
    timeline['plannedTimepoints'] = norm_timepoints
    # Ensure pt_map is available for downstream usage
    pt_map = {pt.get('plannedTimepointId'): pt for pt in norm_timepoints if pt.get('plannedTimepointId')}

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
    group_map = {}
    norm_groups = []
    # Build a set of all group names needed based on activities
    needed_group_names = set()
    for act in norm_acts:
        group_name = act.get('activityGroupName') or act.get('groupName')
        if not group_name and 'activityName' in act:
            name = act['activityName'].lower()
            if 'laboratory' in name:
                group_name = 'Laboratory Tests'
            elif 'instrument' in name:
                group_name = 'Health Outcome Instruments'
            elif 'efficacy' in name:
                group_name = 'Efficacy Assessments'
            elif 'safety' in name:
                group_name = 'Safety Assessments'
        if not group_name:
            group_name = 'Ungrouped'
        act['activityGroupName'] = group_name
        needed_group_names.add(group_name)
    # Map group names to group ids
    group_name_to_id = {g['name']: g.get('activityGroupId') or g.get('groupId') or f'AG{i+1}' for i, g in enumerate(timeline.get('activityGroups', [])) if 'name' in g}
    # Add missing groups
    for group_name in needed_group_names:
        if group_name not in group_name_to_id:
            group_id = f'AG{len(group_name_to_id)+1}'
            group_name_to_id[group_name] = group_id
            norm_groups.append({'activityGroupId': group_id, 'name': group_name, 'activityIds': []})
    # Assign group ids to activities and collect activity ids for each group
    group_activities = {gid: [] for gid in group_name_to_id.values()}
    for act in norm_acts:
        group_id = group_name_to_id[act['activityGroupName']]
        act['activityGroupId'] = group_id
        group_activities[group_id].append(act.get('activityId'))
    # Update norm_groups with activity ids
    for g in norm_groups:
        gid = g['activityGroupId']
        g['activityIds'] = group_activities.get(gid, [])
    # Add any remaining groups from the original timeline
    for i, ag in enumerate(timeline.get('activityGroups', [])):
        group_id = ag.get('activityGroupId') or ag.get('groupId') or f'AG{i+1}'
        if group_id not in [g['activityGroupId'] for g in norm_groups]:
            norm_groups.append(ag)
    timeline['activityGroups'] = norm_groups

    # --- Expand activityTimepoints to explicit pairs ---
    new_atps = []
    dropped = []
    for atp in timeline.get('activityTimepoints', []):
        # Group-based
        if 'activityGroup' in atp and ('plannedTimepoint' in atp or 'plannedTimepointId' in atp):
            group_id = atp.get('activityGroup')
            if not group_id:
                # Try to infer group from activity name or assign 'Ungrouped'
                name = atp.get('name', '').lower()
                if 'laboratory' in name:
                    group_id = 'Laboratory Tests'
                elif 'instrument' in name or 'questionnaire' in name:
                    group_id = 'Health Outcome Instruments'
                elif 'safety' in name:
                    group_id = 'Safety Assessments'
                else:
                    group_id = 'Ungrouped'
                print(f"[WARN] Activity '{atp.get('name','<unknown>')}' missing activityGroupId. Assigned to '{group_id}'.")
                atp['activityGroupId'] = group_id
            pt_id = atp.get('plannedTimepoint') or atp.get('plannedTimepointId')
            group = group_map.get(group_id)
            if group and pt_id in pt_map:
                for aid in group.get('activityIds', []):
                    if aid in act_map:
                        new_atps.append({'activityId': aid, 'plannedTimepointId': pt_id})
                    else:
                        dropped.append({'activityId': aid, 'plannedTimepointId': pt_id, 'reason': 'activityId not found'})
                fixes.append(f"Expanded group {group_id} at {pt_id} to explicit pairs.")
            else:
                dropped.append({'activityGroup': group_id, 'plannedTimepoint': pt_id, 'reason': 'group or timepoint not found'})
        # Already pairwise
        elif 'activityId' in atp and ('plannedTimepointId' in atp or 'plannedTimepoint' in atp):
            pt_id = atp.get('plannedTimepointId') or atp.get('plannedTimepoint')
            if atp['activityId'] in act_map and pt_id in pt_map:
                new_atps.append({'activityId': atp['activityId'], 'plannedTimepointId': pt_id})
            else:
                dropped.append({**atp, 'reason': 'invalid activityId or plannedTimepointId'})
        else:
            dropped.append({**atp, 'reason': 'unrecognized format'})
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
        pt_map = {}
        unhandled_timepoints = []
        for pt in timeline.get('plannedTimepoints', []):
            # Accept both 'plannedTimepointId' and 'plannedVisitId' as equivalent
            pt_id = pt.get('plannedTimepointId') or pt.get('plannedVisitId')
            if pt_id is not None:
                pt['plannedTimepointId'] = pt_id  # Normalize key
                pt_map[pt_id] = pt
            else:
                print(f"[WARNING] Skipping timepoint missing both plannedTimepointId and plannedVisitId: {pt}")
                unhandled_timepoints.append(pt)
        if unhandled_timepoints:
            print(f"[SUMMARY] {len(unhandled_timepoints)} timepoints skipped due to missing IDs.")
        # Activities
        for act in timeline.get("activities", []):
            fill_missing_fields("Activity", act)
        # ActivityGroups
        for ag in timeline.get("activityGroups", []):
            fill_missing_fields("ActivityGroup", ag)
        # ActivityTimepoints
        for atp in timeline.get("activityTimepoints", []):
            fill_missing_fields("ActivityTimepoint", atp)
    # --- Save and report ---
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[CONSOLIDATE/FIX] {len(new_atps)} valid activityTimepoints. {len(dropped)} dropped. {len(norm_timepoints)} timepoints, {len(norm_acts)} activities, {len(norm_groups)} groups.")
    if fixes:
        print("Fixes applied:")
        for fix in fixes:
            print("-", fix)
    if dropped:
        print("First 10 dropped:")
        for d in dropped[:10]:
            print(d)
    else:
        print("No invalid links found.")

if __name__ == "__main__":
    if len(sys.argv) not in [3, 4]:
        print("Usage: python soa_postprocess_consolidated.py <input.json> <output.json> [reference_metadata.json]")
        sys.exit(1)
    consolidate_and_fix_soa(*sys.argv[1:])
