"""Trace exact fields causing the top USDM validation errors."""
import json, glob, os
from collections import Counter

for d in sorted(glob.glob("output/*_v800"))[:1]:  # Just first trial for tracing
    trial = os.path.basename(d)
    uv = json.load(open(os.path.join(d, "usdm_validation.json")))
    print(f"=== {trial}: {uv['error_count']} errors, {uv['warning_count']} warnings ===\n")
    
    # Group by message prefix
    by_msg = {}
    for iss in uv["issues"]:
        key = iss["message"][:60]
        by_msg.setdefault(key, []).append(iss)
    
    for msg, items in sorted(by_msg.items(), key=lambda x: -len(x[1])):
        print(f"\n[{len(items)}x] {msg}")
        # Show unique paths (leaf portion)
        paths = Counter()
        for it in items:
            p = it.get("path", "")
            # Get last 3 segments of path
            parts = p.split(" -> ")
            leaf = " -> ".join(parts[-4:]) if len(parts) > 4 else p
            paths[leaf] += 1
        for path, cnt in paths.most_common(5):
            print(f"  [{cnt}x] ...{path}")
        
        # Show first example with full detail
        ex = items[0]
        if ex.get("context"):
            print(f"  context: {str(ex['context'])[:200]}")
        if ex.get("expected"):
            print(f"  expected: {ex['expected']}")
        if ex.get("actual_value") is not None:
            print(f"  actual: {str(ex['actual_value'])[:200]}")

# Also check what protocol_usdm.json actually has at the error paths
print("\n\n=== SAMPLING ACTUAL VALUES ===")
usdm = json.load(open("output/NCT01776840_SHINE_v800/protocol_usdm.json"))
sd = usdm["study"]["versions"][0]["studyDesigns"][0]

# Check Procedure fields
print("\nFirst activity's definedProcedures:")
acts = sd.get("activities", [])
if acts:
    for proc in acts[0].get("definedProcedures", [])[:2]:
        print(f"  procedureType: {type(proc.get('procedureType')).__name__} = {str(proc.get('procedureType'))[:100]}")
        print(f"  code: {type(proc.get('code')).__name__} = {str(proc.get('code'))[:100]}")
        print(f"  label: {type(proc.get('label')).__name__} = {str(proc.get('label'))[:60]}")
        print(f"  description: {type(proc.get('description')).__name__} = {str(proc.get('description'))[:60]}")
        print()

# Check Amendment changes
print("First amendment's changes:")
amends = usdm["study"]["versions"][0].get("amendments", [])
if amends:
    for ch in amends[0].get("changes", [])[:2]:
        print(f"  keys: {list(ch.keys())}")
        print(f"  summary: {ch.get('summary', 'MISSING')}")
        print()

# Check Administration duration
print("First intervention's administration duration:")
intervs = usdm["study"]["versions"][0].get("studyInterventions", [])
if intervs:
    for adm in intervs[0].get("administrations", [])[:2]:
        d = adm.get("duration")
        print(f"  duration: {type(d).__name__} = {str(d)[:100]}")
        print()
