"""Debug difference between procedure activities and procedures."""
import json

with open('output/test_claude_fixed/protocol_usdm.json') as f:
    data = json.load(f)

sd = data['study']['versions'][0]['studyDesigns'][0]

# Activities with procedure_enrichment source
activities = sd.get('activities', [])
proc_activities = []
for a in activities:
    for ext in a.get('extensionAttributes', []):
        if ext.get('valueString') == 'procedure_enrichment':
            proc_activities.append(a)
            break

# Procedure entities
procedures = sd.get('procedures', [])

print(f"Activities with procedure_enrichment source: {len(proc_activities)}")
print(f"Procedure entities in studyDesign.procedures: {len(procedures)}")
print()
print("Sample procedure ACTIVITIES (from reconciler):")
for a in proc_activities[:5]:
    print(f"  - {a.get('name')}")
print()
print("Sample PROCEDURES (from procedures extractor):")
for p in procedures[:5]:
    print(f"  - {p.get('name')}")
