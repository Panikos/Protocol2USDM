"""Check how sites are stored in the USDM JSON."""
import json

u = json.load(open("output/NCT04573309_Wilsons_v717/protocol_usdm.json"))
sv = u["study"]["versions"][0]
orgs = sv.get("organizations", [])
print(f"Total orgs: {len(orgs)}")

sites_total = 0
for i, o in enumerate(orgs[:5]):
    ms = o.get("managedSites", [])
    sites_total += len(ms)
    print(f"  org[{i}] name={o.get('name', '?')[:50]} managedSites={len(ms)} keys={sorted(o.keys())}")

# Check remaining orgs
for o in orgs[5:]:
    sites_total += len(o.get("managedSites", []))

print(f"\nTotal sites across all orgs: {sites_total}")

# Check if sites exist at design level (old path)
sd = sv.get("studyDesigns", [{}])[0]
old_sites = sd.get("studySites", [])
print(f"studyDesign.studySites (old path): {len(old_sites)}")
