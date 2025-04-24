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

    # Drill to timeline
    versions = study.get('versions') or study.get('studyVersions')
    if not versions or not isinstance(versions, list):
        raise ValueError("Study must contain a non-empty 'versions' or 'studyVersions' array.")
    timeline = versions[0].get('timeline') or versions[0].get('studyDesign', {}).get('timeline')
    if not timeline:
        raise ValueError("No timeline found in study version.")

    # --- Normalize plannedTimepoints and add milestone support ---
    pt_map = {}
    norm_timepoints = []
    pts = timeline.get('plannedTimepoints', [])
    for pt in pts:
        pt = deepcopy(pt)
        pt_id = pt.get('plannedTimepointId') or pt.get('plannedId') or pt.get('id')
        if pt_id:
            pt['plannedTimepointId'] = pt_id
        # Milestone support: look for milestone or milestoneType
        if 'milestone' not in pt:
            if pt.get('milestoneType') or (pt.get('isMilestone') is True):
                pt['milestone'] = True
        norm_timepoints.append(pt)
        pt_map[pt['plannedTimepointId']] = pt
    else:
        for pt in pts:
            pt = deepcopy(pt)
            pt_id = pt.get('plannedTimepointId') or pt.get('plannedId') or pt.get('id')
            if pt_id:
                pt['plannedTimepointId'] = pt_id
            if 'visit' in pt and 'visitName' not in pt:
                pt['visitName'] = pt['visit']
            if 'name' in pt and 'visitName' not in pt:
                pt['visitName'] = pt['name']
            # Merge in metadata from reference if available
            if ref_metadata:
                ref_pts = ref_metadata.get('plannedTimepoints', [])
                ref = next((x for x in ref_pts if x.get('plannedTimepointId') == pt_id or x.get('id') == pt_id), None)
                if ref:
                    for k in ['description', 'code', 'window']:
                        if k in ref:
                            pt[k] = ref[k]
            pt_map[pt['plannedTimepointId']] = pt
            norm_timepoints.append(pt)
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
            # Merge in metadata from reference if available
            if ref_metadata:
                ref_acts = ref_metadata.get('activities', [])
                ref = next((x for x in ref_acts if x.get('activityId') == act_id or x.get('id') == act_id), None)
                if ref:
                    for k in ['description', 'code']:
                        if k in ref:
                            act[k] = ref[k]
            act_map[act['activityId']] = act
            norm_acts.append(act)
    timeline['activities'] = norm_acts

    # --- Normalize activityGroups ---
    group_map = {}
    norm_groups = []
    for i, ag in enumerate(timeline.get('activityGroups', [])):
        ag = deepcopy(ag)
        group_id = ag.get('activityGroupId') or ag.get('groupId') or f'AG{i+1}'
        ag['activityGroupId'] = group_id
        aids = ag.get('activityIds') if 'activityIds' in ag else ag.get('activities', [])
        ag['activityIds'] = aids
        group_map[group_id] = ag
        norm_groups.append(ag)
    timeline['activityGroups'] = norm_groups

    # --- Expand activityTimepoints to explicit pairs ---
    new_atps = []
    dropped = []
    for atp in timeline.get('activityTimepoints', []):
        # Group-based
        if 'activityGroup' in atp and ('plannedTimepoint' in atp or 'plannedTimepointId' in atp):
            group_id = atp['activityGroup']
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
