"""Compare old vs new protocol_usdm.json outputs."""
import json

OLD_PATH = 'output/Alexion_NCT04573309_Wilsons_20251130_223747/protocol_usdm.json'
NEW_PATH = 'output/test_childids_fix/protocol_usdm.json'

with open(OLD_PATH) as f:
    old = json.load(f)
with open(NEW_PATH) as f:
    new = json.load(f)

old_sd = old['study']['versions'][0]['studyDesigns'][0]
new_sd = new['study']['versions'][0]['studyDesigns'][0]

print("=" * 60)
print("COMPARISON: Pre-Reconciler vs With-Reconciler")
print("=" * 60)

print("\nOLD (Nov 30 - pre-reconciler):")
print(f"  Activities: {len(old_sd.get('activities', []))}")
print(f"  Epochs: {len(old_sd.get('epochs', []))}")
print(f"  Encounters: {len(old_sd.get('encounters', []))}")
print(f"  activityGroups: {len(old_sd.get('activityGroups', []))}")

old_groups = old_sd.get('activityGroups', [])
if old_groups:
    print("  Groups with childIds:")
    for g in old_groups[:3]:
        print(f"    - {g.get('name')}: {len(g.get('childIds', []))}")

print("\nNEW (test_usdm_final - with reconciler):")
print(f"  Activities: {len(new_sd.get('activities', []))}")
print(f"  Epochs: {len(new_sd.get('epochs', []))}")
print(f"  Encounters: {len(new_sd.get('encounters', []))}")
print(f"  activityGroups: {len(new_sd.get('activityGroups', []))}")

new_groups = new_sd.get('activityGroups', [])
if new_groups:
    print("  Groups with childIds:")
    for g in new_groups[:3]:
        print(f"    - {g.get('name')}: {len(g.get('childIds', []))}")

# Compare activity names
old_act_names = {a.get('name') for a in old_sd.get('activities', [])}
new_act_names = {a.get('name') for a in new_sd.get('activities', [])}

added = new_act_names - old_act_names
removed = old_act_names - new_act_names

print(f"\n=== Activity Differences ===")
print(f"Added by reconciler: {len(added)}")
if added:
    for name in sorted(list(added))[:10]:
        print(f"  + {name}")
print(f"\nRemoved: {len(removed)}")
if removed:
    for name in sorted(list(removed))[:5]:
        print(f"  - {name}")
