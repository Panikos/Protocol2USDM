"""Verify CORE compliance fixes against existing USDM output."""
import json
import copy
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.post_processing import (
    _deduplicate_ids,
    _fix_activity_child_ordering,
    _fix_endpoint_level_decodes,
    _fix_timing_relative_refs,
    _normalize_country_decodes,
    _fix_window_durations,
    _normalize_code_system_versions,
    _fix_amendment_other_reason,
    _remove_non_usdm_properties,
    _ensure_leaf_activity_procedures,
    _fix_timing_values,
    _fix_amendment_reason_codesystem,
    _fix_empty_amendment_changes,
    _fix_unit_codes,
)

USDM = "output/NCT04573309_Wilsons_v717/protocol_usdm.json"
usdm = json.load(open(USDM))
combined = copy.deepcopy(usdm)

sd = combined["study"]["versions"][0]["studyDesigns"][0]

print("Simulating CORE compliance fixes on existing output...\n")

dedup = _deduplicate_ids(combined)
print(f"  CORE-001015  Deduplicated IDs:          {dedup:4d}  (was 76 issues)")

act_order = _fix_activity_child_ordering(sd)
print(f"  CORE-001066  Activity child ordering:   {act_order:4d}  (was 43 issues)")

ep_decode = _fix_endpoint_level_decodes(sd)
print(f"  CORE-000940  Endpoint level decodes:    {ep_decode:4d}  (was 22 issues)")

timing_rel = _fix_timing_relative_refs(sd)
print(f"  CORE-000423  Timing relFrom/To:         {timing_rel:4d}  (was 15 issues)")

country = _normalize_country_decodes(combined)
print(f"  CORE-000427  Country decodes:           {country:4d}  (was 14 issues)")

window = _fix_window_durations(sd)
print(f"  CORE-000825  Window durations:          {window:4d}  (was 11 issues)")

csv = _normalize_code_system_versions(combined)
print(f"  CORE-000808  codeSystemVersion:         {csv:4d}  (was 6 issues)")

amend = _fix_amendment_other_reason(combined)
print(f"  CORE-000413  Amendment otherReason:     {amend:4d}  (was 4 issues)")

non_usdm = _remove_non_usdm_properties(combined)
print(f"  CORE-000937  Non-USDM properties:      {non_usdm:4d}  (was 28 issues)")

leaf_procs = _ensure_leaf_activity_procedures(sd)
print(f"  CORE-001076  Leaf activity procedures:  {leaf_procs:4d}  (was 33 issues)")

timing_vals = _fix_timing_values(sd)
print(f"  CORE-000820  Timing value durations:    {timing_vals:4d}  (was 3 issues)")

amend_cs = _fix_amendment_reason_codesystem(combined)
print(f"  CORE-000930  Amend reason codeSystem:   {amend_cs:4d}  (was 4 issues)")

amend_ch = _fix_empty_amendment_changes(combined)
print(f"  CORE-000938  Empty amendment changes:   {amend_ch:4d}  (was 4 issues)")

unit_codes = _fix_unit_codes(combined)
print(f"  CORE-001060  Unit codes:               {unit_codes:4d}  (was 6 issues)")

total = dedup + act_order + ep_decode + timing_rel + country + window + csv + amend + non_usdm + leaf_procs + timing_vals + amend_cs + amend_ch + unit_codes
print(f"\n  Total fixes applied:                    {total:4d}  (was 347 total issues)")
print(f"  Estimated remaining issues:             {347 - total}  (mostly CORE-001013 dup names, CORE-001076 no procedures, CORE-000937 missing attrs)")

# Spot-check: verify endpoint decodes are fixed
print("\n=== Spot checks ===")
for obj in sd.get("objectives", [])[:2]:
    for ep in obj.get("endpoints", [])[:2]:
        lvl = ep.get("level", {})
        print(f"  Endpoint '{ep.get('name','')[:40]}' decode='{lvl.get('decode','')}'")

# Spot-check: timings
for tl in sd.get("scheduleTimelines", []):
    for t in tl.get("timings", [])[:3]:
        rf = t.get("relativeFromScheduledInstanceId", "NONE")[:20]
        rt = t.get("relativeToScheduledInstanceId", "NONE")[:20]
        print(f"  Timing '{t.get('label','')[:30]}' relFrom={rf} relTo={rt} same={rf==rt}")
    break

# Spot-check: amendments
ver = combined["study"]["versions"][0]
for am in ver.get("amendments", [])[:2]:
    pr = am.get("primaryReason", {})
    if isinstance(pr, dict):
        print(f"  Amendment reason: code={pr.get('code',{}).get('code','?')} otherReason={pr.get('otherReason','REMOVED')}")
