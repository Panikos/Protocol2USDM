import json
import sys
from typing import Set

def load_timepoints(path: str) -> Set[str]:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Drill to timepoints
        study = data.get('study') or data.get('Study')
        if not study:
            print(f"[WARN] No 'study' key in {path}")
            return set()
        versions = study.get('versions') or study.get('studyVersions') or []
        if isinstance(versions, dict):
            versions = [versions]
        timepoints = set()
        for v in versions:
            timeline = v.get('timeline') or v.get('studyDesign', {}).get('timeline') or {}
            for pt in timeline.get('plannedTimepoints', []):
                pt_id = pt.get('id') or pt.get('plannedTimepointId') or pt.get('plannedVisitId')
                pt_label = pt.get('name') or pt.get('label')
                if pt_id:
                    timepoints.add(f"{pt_id}::{pt_label}")
        return timepoints
    except Exception as e:
        print(f"[ERROR] Failed to load {path}: {e}")
        return set()

def compare_timepoints(paths):
    sets = [load_timepoints(p) for p in paths]
    names = [p for p in paths]
    all_union = set.union(*sets) if sets else set()
    print("\n=== Timepoint Audit Report ===")
    for i, s in enumerate(sets):
        missing = all_union - s
        extra = s - all_union
        print(f"\n[{names[i]}]")
        print(f"  Total: {len(s)}")
        if missing:
            print(f"  Missing ({len(missing)}): {sorted(list(missing))}")
        if extra:
            print(f"  Extra ({len(extra)}): {sorted(list(extra))}")
    # Pairwise comparison
    for i in range(len(sets)):
        for j in range(i+1, len(sets)):
            only_in_i = sets[i] - sets[j]
            only_in_j = sets[j] - sets[i]
            print(f"\n[{names[i]}] - [{names[j]}]: {sorted(list(only_in_i))}")
            print(f"[{names[j]}] - [{names[i]}]: {sorted(list(only_in_j))}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python audit_timepoints.py soa_text.json soa_vision.json [soa_final.json]")
        sys.exit(1)
    compare_timepoints(sys.argv[1:])
