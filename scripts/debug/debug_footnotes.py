"""Debug UUID mismatch in provenance."""
import json

# Check ORIGINAL provenance (before UUID conversion)
print("=== ORIGINAL Provenance (9_final_soa_provenance.json) ===")
with open('output/test_linked/9_final_soa_provenance.json') as f:
    orig_prov = json.load(f)

orig_entities = orig_prov.get('entities', {})
print(f"Entity types: {list(orig_entities.keys())}")
for etype, edata in orig_entities.items():
    if isinstance(edata, dict):
        print(f"  {etype}: {len(edata)} items")
    else:
        print(f"  {etype}: {type(edata)}")

# Check CONVERTED provenance
print("\n=== CONVERTED Provenance (protocol_usdm_provenance.json) ===")
with open('output/test_linked/protocol_usdm_provenance.json') as f:
    prov = json.load(f)

print(f"Top-level keys: {list(prov.keys())}")
print(f"Cells type: {type(prov.get('cells'))}")

# Check cells structure - it's a dict with "actId|encId" keys
cells = prov.get('cells', {})
print(f"\nCells ({len(cells)}):")
sample_keys = list(cells.keys())[:5]
for key in sample_keys:
    parts = key.split('|')
    if len(parts) == 2:
        act_id, enc_id = parts
        print(f"  {key}")
        print(f"    activityId:  {act_id}")
        print(f"    encounterId: {enc_id}")

# Check USDM encounter IDs
with open('output/test_linked/protocol_usdm.json') as f:
    usdm = json.load(f)
sd = usdm['study']['versions'][0]['studyDesigns'][0]
encounters = sd.get('encounters', [])
enc_ids = {e.get('id') for e in encounters}
enc_names = {e.get('id'): e.get('name') for e in encounters}

print(f"\nUSDM encounter IDs ({len(enc_ids)}):")
for eid in list(enc_ids)[:5]:
    print(f"  {eid} = {enc_names.get(eid)}")

# Find mismatched IDs in provenance
print("\n=== Mismatched encounter IDs ===")
mismatched = set()
for key in cells.keys():
    parts = key.split('|')
    if len(parts) == 2:
        enc_id = parts[1]
        if enc_id not in enc_ids:
            mismatched.add(enc_id)

print(f"Total mismatched: {len(mismatched)}")
for enc_id in list(mismatched)[:5]:
    print(f"  {enc_id}")

# Check entities in provenance for the mismatched ID
print("\n=== Provenance entities ===")
entities = prov.get('entities', {})
print(f"Entity types: {list(entities.keys())}")

# Check if the mismatched ID is in provenance entities
enc_entities = entities.get('encounters', {})
print(f"\nProvenance encounters ({len(enc_entities)}):")
for eid, name in list(enc_entities.items())[:5]:
    print(f"  {eid} = {name}")

# Check if mismatched ID is there
for mid in mismatched:
    if mid in enc_entities:
        print(f"\n✓ Mismatched ID {mid} IS in provenance entities: {enc_entities[mid]}")
    else:
        print(f"\n✗ Mismatched ID {mid} NOT in provenance entities either!")

# Check what activity uses this mismatched encounter
print("\n=== Cells using mismatched encounter ===")
for key, val in cells.items():
    if '349a076a-80a0-4882-b47c-3ddff36598b2' in key:
        act_id = key.split('|')[0]
        act_name = entities.get('activities', {}).get(act_id, 'Unknown')
        print(f"  Activity: {act_name}")
        print(f"  Cell data: {val}")
