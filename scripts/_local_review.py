"""Local quality review of ADAURA USDM output."""
import json, sys

OUTPUT_DIR = "output/NCT03036124_ADAURA_v811_g31pro"
usdm = json.load(open(f"{OUTPUT_DIR}/protocol_usdm.json"))

# --- Validation ---
try:
    from validation.usdm_validator import validate_usdm_dict
    r = validate_usdm_dict(usdm)
    print(f"Schema Valid: {r.valid}")
    print(f"Schema Errors: {len(r.errors) if hasattr(r, 'errors') else 'N/A'}")
    if hasattr(r, 'errors') and r.errors:
        for e in r.errors[:5]:
            print(f"  - {e}")
except Exception as e:
    print(f"Validation: {e}")

# --- Structure ---
sv = usdm["study"]["versions"][0]
sd = sv["studyDesigns"][0]

print("\n=== STUDY METADATA ===")
for t in sv.get("titles", []):
    print(f"  Title: {t.get('text', '')[:80]}  type={t.get('type',{}).get('decode','?')}")
print(f"  Phase: {sv.get('studyPhase', {}).get('standardCode', {}).get('decode', 'MISSING')}")
print(f"  StudyType: {sd.get('studyDesignType', {}).get('decode', 'MISSING')}")

# Arms
print(f"\n=== ARMS ({len(sd.get('arms', []))}) ===")
for arm in sd.get("arms", []):
    print(f"  {arm.get('name')} | code={arm.get('type',{}).get('code','?')} decode={arm.get('type',{}).get('decode','?')}")

# Blinding
bs = sd.get("blindingSchema", {})
print(f"\n=== BLINDING ===")
print(f"  blindingSchema: {bs.get('standardCode',{}).get('decode','MISSING')} ({bs.get('standardCode',{}).get('code','?')})")

# Population
pop = sd.get("population", {})
print(f"\n=== POPULATION ===")
print(f"  plannedNumberOfSubjects: {pop.get('plannedNumberOfSubjects', 'MISSING')}")
print(f"  plannedSex: {[s.get('decode','?') for s in pop.get('plannedSex', [])]}")
print(f"  plannedMinAge: {pop.get('plannedMinimumAgeOfSubjects', {}).get('value', 'MISSING')}")
print(f"  plannedMaxAge: {pop.get('plannedMaximumAgeOfSubjects', {}).get('value', 'MISSING')}")

# Eligibility
ecis = sv.get("eligibilityCriterionItems", [])
criteria = sd.get("eligibilityCriteria", [])
nested_count = sum(1 for i in ecis if i.get("criterion"))
print(f"\n=== ELIGIBILITY ===")
print(f"  criterionItems: {len(ecis)}")
print(f"  criteria: {len(criteria)}")
print(f"  nested (criterion in item): {nested_count}/{len(ecis)}")
if ecis:
    sample = ecis[0]
    crit = sample.get("criterion", {})
    print(f"  Sample item: {sample.get('text', '')[:60]}...")
    print(f"    criterion.category: {crit.get('category', {}).get('decode', 'MISSING')}")

# Objectives
objs = sd.get("objectives", [])
print(f"\n=== OBJECTIVES ({len(objs)}) ===")
for o in objs:
    level = o.get("level", {}).get("decode", "?")
    eps = o.get("endpoints", [])
    print(f"  [{level}] {o.get('text', '')[:70]}... ({len(eps)} endpoints)")

# Interventions
sis = sv.get("studyInterventions", [])
print(f"\n=== INTERVENTIONS ({len(sis)}) ===")
for si in sis:
    admins = si.get("administrations", [])
    print(f"  {si.get('name')} | role={si.get('role',{}).get('decode','')} | admins={len(admins)}")
    for a in admins:
        pid = a.get("administrableProductId", "NONE")
        print(f"    Admin: {a.get('name','')} | prodId={pid[:20] if pid else 'NONE'}")

# Products
prods = sv.get("administrableProducts", [])
print(f"\n=== PRODUCTS ({len(prods)}) ===")
for p in prods:
    ings = p.get("ingredients", [])
    print(f"  {p.get('name')} | ingredients={len(ings)}")

# SoA
timelines = sd.get("scheduleTimelines", [])
print(f"\n=== SCHEDULE OF ACTIVITIES ===")
for tl in timelines:
    instances = tl.get("instances", [])
    timings = tl.get("timings", [])
    print(f"  Timeline: {tl.get('name','')} | instances={len(instances)} | timings={len(timings)}")

# Epochs, encounters, activities
epochs = sd.get("epochs", [])
encounters = sd.get("encounters", [])
activities = sd.get("activities", [])
print(f"  Epochs: {len(epochs)}")
for ep in epochs:
    print(f"    {ep.get('name')} | type={ep.get('type',{}).get('decode','?')}")
print(f"  Encounters: {len(encounters)}")
print(f"  Activities: {len(activities)}")

# Narrative
ncis = sv.get("narrativeContentItems", [])
print(f"\n=== NARRATIVE ===")
print(f"  narrativeContentItems: {len(ncis)}")

# Amendments
amendments = sv.get("amendments", [])
print(f"\n=== AMENDMENTS ({len(amendments)}) ===")

# StudyCells
cells = sd.get("studyCells", [])
print(f"\n=== STUDY CELLS ({len(cells)}) ===")

# Conditions
conditions = sv.get("conditions", [])
print(f"  Conditions: {len(conditions)}")

# Extension attributes check
exts = sd.get("extensionAttributes", []) or []
print(f"\n=== EXTENSIONS ===")
print(f"  studyDesign extensions: {len(exts)}")
for ext in exts[:5]:
    print(f"    {ext.get('name','?')}: {str(ext.get('valueString',''))[:50]}")

# M11 conformance
try:
    conf = json.load(open(f"{OUTPUT_DIR}/m11_conformance_report.json"))
    print(f"\n=== M11 CONFORMANCE ===")
    print(f"  Required: {conf.get('required_met',0)}/{conf.get('required_total',0)}")
    print(f"  Issues: {len(conf.get('issues', []))}")
    for iss in conf.get("issues", [])[:10]:
        print(f"    [{iss.get('severity','')}] {iss.get('section','')} - {iss.get('message','')[:80]}")
except:
    pass

# Entity stats
try:
    stats = json.load(open(f"{OUTPUT_DIR}/entity_stats.json"))
    print(f"\n=== ENTITY STATS ===")
    for k, v in sorted(stats.items()):
        if isinstance(v, (int, float)) and v > 0:
            print(f"  {k}: {v}")
except:
    pass
