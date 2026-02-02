"""Check activity groups and linking from header_structure through to final output."""
import json

OUT = 'output/test_claude_opus'

# First check epochs
print("=== Epochs in Final Output ===")
with open(f'{OUT}/protocol_usdm.json') as f:
    final = json.load(f)
sd = final['study']['versions'][0]['studyDesigns'][0]
epochs = sd.get('epochs', [])
print(f"Total epochs: {len(epochs)}")
for i, e in enumerate(epochs):
    print(f"  {i}: {e.get('name')}")

# Check activities without ticks
print("\n=== Activities without Ticks ===")
timeline = sd.get('scheduleTimelines', [{}])[0] if sd.get('scheduleTimelines') else {}
instances = timeline.get('instances', [])
activity_ids_with_ticks = {inst.get('scheduledActivityId') or inst.get('activityId') for inst in instances}
activities = sd.get('activities', [])
print(f"Total activities: {len(activities)}")
print(f"Activities with ticks: {len(activity_ids_with_ticks)}")

# Find activities without ticks
no_ticks = [a for a in activities if a.get('id') not in activity_ids_with_ticks]
print(f"Activities WITHOUT ticks: {len(no_ticks)}")
for a in no_ticks[:10]:
    print(f"  - {a.get('name')}")

# Check which groups these belong to
all_child_ids = set()
groups = sd.get('activityGroups', [])
for g in groups:
    all_child_ids.update(g.get('childIds', []))
    
unlinked = [a for a in no_ticks if a.get('id') not in all_child_ids]
print(f"\nActivities WITHOUT ticks AND without group: {len(unlinked)}")
for a in unlinked[:10]:
    print(f"  - {a.get('name')}")

print()

# Check header structure - the AUTHORITATIVE source
print("=== Header Structure (4_header_structure.json) - AUTHORITATIVE ===")
with open(f'{OUT}/4_header_structure.json') as f:
    header = json.load(f)

# Header uses 'rowGroups' key
header_groups = header.get('rowGroups', [])
print(f"rowGroups: {len(header_groups)}")
for g in header_groups[:3]:
    names = g.get('activityNames', [])
    print(f"  - {g.get('name')}: activityNames={len(names)}")
    if names:
        print(f"    Sample: {names[:3]}")

# Check epochs from header
col_h = header.get('columnHierarchy', {})
header_epochs = col_h.get('epochs', [])
print(f"\nEpochs: {len(header_epochs)}")
for e in header_epochs:
    print(f"  - {e.get('id')}: {e.get('name')}")

# Check raw SoA output
print("\n=== Raw SoA (5_raw_text_soa.json) ===")
with open(f'{OUT}/5_raw_text_soa.json') as f:
    raw = json.load(f)
    
raw_sd = raw.get('study', {}).get('versions', [{}])[0].get('studyDesigns', [{}])[0]
raw_groups = raw_sd.get('activityGroups', [])
print(f"activityGroups: {len(raw_groups)}")

raw_acts = raw_sd.get('activities', [])
with_gid = [a for a in raw_acts if a.get('activityGroupId')]
print(f"Activities with activityGroupId: {len(with_gid)}/{len(raw_acts)}")
if with_gid:
    for a in with_gid[:3]:
        print(f"  - {a.get('name')}: {a.get('activityGroupId')}")

# Check SoA before reconciliation
print("\n=== SoA Output (9_final_soa.json) ===")
with open(f'{OUT}/9_final_soa.json') as f:
    soa = json.load(f)

soa_sd = soa['study']['versions'][0]['studyDesigns'][0]
soa_groups = soa_sd.get('activityGroups', [])
print(f"activityGroups: {len(soa_groups)}")
for g in soa_groups[:3]:
    print(f"  - {g.get('name')}: activityIds={len(g.get('activityIds', []))}")

soa_acts = soa_sd.get('activities', [])
with_gid2 = [a for a in soa_acts if a.get('activityGroupId')]
print(f"Activities with activityGroupId: {len(with_gid2)}/{len(soa_acts)}")

# Check final output
print("\n=== Final Output (protocol_usdm.json) ===")
with open(f'{OUT}/protocol_usdm.json') as f:
    data = json.load(f)

sd = data['study']['versions'][0]['studyDesigns'][0]
groups = sd.get('activityGroups', [])
activities = sd.get('activities', [])
epochs = sd.get('epochs', [])

print(f"Epochs: {len(epochs)}")
for e in epochs[:5]:
    print(f"  - {e.get('id')}: {e.get('name')}")

print(f"\nActivity Groups: {len(groups)}")
for g in groups[:3]:
    print(f"  - {g.get('name')}: activityIds={len(g.get('activityIds', []))}")

print(f"\nActivities: {len(activities)}")
with_group = [a for a in activities if a.get('activityGroupId')]
print(f"Activities with activityGroupId: {len(with_group)}")

# Debug: Check epochs - header vs final
print("\n=== DEBUG: Epoch Comparison ===")
header_epoch_names = [e.get('name') for e in header_epochs]
final_epoch_names = [e.get('name') for e in epochs]
print(f"Header epochs ({len(header_epochs)}): {header_epoch_names}")
print(f"Final epochs ({len(epochs)}): {final_epoch_names}")
extra = set(final_epoch_names) - set(header_epoch_names)
if extra:
    print(f"EXTRA epochs in final: {extra}")

# Debug: Check childIds on groups
print("\n=== DEBUG: Group childIds ===")
for g in groups[:3]:
    child_ids = g.get('childIds', [])
    print(f"  {g.get('name')}: childIds={len(child_ids)}")
