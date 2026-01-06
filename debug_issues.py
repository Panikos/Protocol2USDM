"""Debug remaining SoA issues."""
import json

OUT = 'output/test_procedure_display'

with open(f'{OUT}/protocol_usdm.json') as f:
    data = json.load(f)

sd = data['study']['versions'][0]['studyDesigns'][0]

# Check encounters with missing/invalid epochId
epochs = sd.get('epochs', [])
epoch_ids = {e.get('id') for e in epochs}
encounters = sd.get('encounters', [])

print("=== Encounters with missing/invalid epochId ===")
bad_encs = [e for e in encounters if e.get('epochId') not in epoch_ids]
print(f"Total: {len(bad_encs)}")
for e in bad_encs[:5]:
    print(f"  {e.get('name')}: epochId={e.get('epochId')}")

# Check activity group linking
print("\n=== Activity Group Linking Debug ===")
groups = sd.get('activityGroups', [])
activities = sd.get('activities', [])

# Check Eligibility group
elig_group = next((g for g in groups if 'eligibility' in g.get('name', '').lower()), None)
if elig_group:
    print(f"Eligibility group childIds: {len(elig_group.get('childIds', []))}")
    print(f"  activityNames from header: {elig_group.get('activityNames', [])[:5]}")

# Find inclusion/exclusion activity
inc_act = next((a for a in activities if 'inclusion' in a.get('name', '').lower()), None)
if inc_act:
    print(f"\nInclusion activity: {inc_act.get('name')}")
    print(f"  ID: {inc_act.get('id')}")
    
    # Check if in any group's childIds
    for g in groups:
        if inc_act.get('id') in g.get('childIds', []):
            print(f"  Linked to group: {g.get('name')}")
            break
    else:
        print("  NOT linked to any group")
        
# Check header structure for actual group names
print("\n=== Header Structure Activity Names ===")
with open(f'{OUT}/4_header_structure.json') as f:
    header = json.load(f)
    
for g in header.get('rowGroups', [])[:3]:
    names = g.get('activityNames', [])
    print(f"{g.get('name')}: {names}")
