"""
Local quality review script for USDM JSON output.
Performs comprehensive checks across all review dimensions without MCP.
Usage: python scripts/local_quality_review.py <output_dir>
"""
import json
import sys
import os
import re
from collections import Counter, defaultdict

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def review(output_dir):
    usdm = load_json(os.path.join(output_dir, 'protocol_usdm.json'))
    sv = usdm['study']['versions'][0]
    sd = sv['studyDesigns'][0]
    
    findings = []
    
    def finding(severity, category, message, detail=""):
        findings.append({"severity": severity, "category": category, "message": message, "detail": detail})
    
    # ========== 1. METADATA ==========
    print("=" * 60)
    print("1. STUDY METADATA")
    print("=" * 60)
    
    titles = sv.get('titles', [])
    for t in titles:
        ttype = t.get('type', {}).get('decode', '?')
        print(f"  {ttype}: {str(t.get('text', '?'))[:100]}")
    
    # Phase
    isd = sd.get('studyDesign', sd)  # InterventionalStudyDesign may be nested
    phase_code = sd.get('trialPhaseCode', {})
    phase_sc = phase_code.get('standardCode', {})
    phase_decode = phase_sc.get('decode', '') or phase_code.get('decode', '')
    phase_ccode = phase_sc.get('code', '') or phase_code.get('code', '')
    print(f"  Phase: {phase_decode} (C-code: {phase_ccode})")
    if not phase_ccode:
        finding("HIGH", "C-codes", "Trial phase C-code missing")
    
    # Study type
    type_code = sd.get('trialTypeCode', {})
    type_sc = type_code.get('standardCode', {})
    type_decode = type_sc.get('decode', '') or type_code.get('decode', '')
    print(f"  Type: {type_decode}")
    
    # Blinding
    masking = sd.get('masking', {})
    blind_decode = ''
    if masking:
        blind_code = masking.get('blindingSchemaCode', {})
        blind_sc = blind_code.get('standardCode', {})
        blind_decode = blind_sc.get('decode', '') or blind_code.get('decode', '')
    print(f"  Blinding: {blind_decode or 'Not specified'}")
    
    # Identifiers
    ids = sv.get('studyIdentifiers', []) or usdm['study'].get('studyIdentifiers', [])
    print(f"  Identifiers: {len(ids)}")
    for si in ids[:5]:
        org = si.get('scopeOrganization', {}).get('name', '?')
        print(f"    {si.get('text', '?')} ({org})")
    
    # ========== 2. ARMS & EPOCHS ==========
    print("\n" + "=" * 60)
    print("2. STUDY DESIGN (Arms, Epochs, Cells)")
    print("=" * 60)
    
    arms = sd.get('arms', [])
    epochs = sd.get('epochs', [])
    cells = sd.get('studyCells', [])
    
    print(f"  Arms: {len(arms)}, Epochs: {len(epochs)}, Cells: {len(cells)}")
    expected_cells = len(arms) * len(epochs)
    if len(cells) != expected_cells and len(cells) > 0:
        finding("MEDIUM", "design", f"StudyCell count ({len(cells)}) != arms*epochs ({expected_cells})")
    
    arm_map = {a['id']: a for a in arms}
    epoch_map = {e['id']: e for e in epochs}
    
    for arm in arms:
        atype = arm.get('type', {})
        atype_sc = atype.get('standardCode', {})
        atype_decode = atype_sc.get('decode', '') or atype.get('decode', '')
        atype_code = atype_sc.get('code', '') or atype.get('code', '')
        print(f"  Arm: {arm.get('name', '?')} | type={atype_decode} ({atype_code})")
        if not atype_code:
            finding("HIGH", "C-codes", f"Arm '{arm.get('name')}' missing arm type C-code")
    
    for ep in epochs:
        etype = ep.get('epochType', {})
        etype_sc = etype.get('standardCode', {})
        etype_decode = etype_sc.get('decode', '') or etype.get('decode', '')
        print(f"  Epoch: {ep.get('name', '?')} | type={etype_decode}")
    
    # Check cell references
    cell_arm_ids = {c.get('armId') for c in cells}
    cell_epoch_ids = {c.get('epochId') for c in cells}
    for arm in arms:
        if arm['id'] not in cell_arm_ids:
            finding("MEDIUM", "integrity", f"Arm '{arm.get('name')}' not referenced by any StudyCell")
    for ep in epochs:
        if ep['id'] not in cell_epoch_ids:
            finding("MEDIUM", "integrity", f"Epoch '{ep.get('name')}' not referenced by any StudyCell")
    
    # ========== 3. OBJECTIVES & ENDPOINTS ==========
    print("\n" + "=" * 60)
    print("3. OBJECTIVES & ENDPOINTS")
    print("=" * 60)
    
    objectives = sd.get('objectives', [])
    print(f"  Objectives: {len(objectives)}")
    
    obj_levels = Counter()
    ep_levels = Counter()
    
    for obj in objectives:
        level = obj.get('level', {})
        level_sc = level.get('standardCode', {})
        level_decode = level_sc.get('decode', '') or level.get('decode', '')
        level_code = level_sc.get('code', '') or level.get('code', '')
        obj_levels[level_decode] += 1
        text = str(obj.get('text', '?'))[:100]
        print(f"  [{level_decode}] {text}")
        
        if not level_code:
            finding("HIGH", "C-codes", f"Objective missing level C-code: {text[:50]}")
        
        endpoints = obj.get('endpoints', [])
        for ep in endpoints:
            ep_level = ep.get('level', {})
            ep_level_sc = ep_level.get('standardCode', {})
            ep_level_decode = ep_level_sc.get('decode', '') or ep_level.get('decode', '')
            ep_levels[ep_level_decode] += 1
            ep_text = str(ep.get('text', '?'))[:80]
            print(f"    EP [{ep_level_decode}]: {ep_text}")
    
    print(f"\n  Objective levels: {dict(obj_levels)}")
    print(f"  Endpoint levels: {dict(ep_levels)}")
    
    # CheckMate 227 should have primary + secondary objectives minimum
    if obj_levels.get('Primary Objective', 0) == 0:
        finding("CRITICAL", "completeness", "No Primary Objective found")
    
    # Estimands
    estimands = sd.get('estimands', [])
    print(f"  Estimands: {len(estimands)}")
    if len(estimands) == 0:
        finding("MEDIUM", "completeness", "No Estimands extracted (expected for Phase III)")
    
    # ========== 4. ELIGIBILITY ==========
    print("\n" + "=" * 60)
    print("4. ELIGIBILITY CRITERIA")
    print("=" * 60)
    
    ecis = sv.get('eligibilityCriterionItems', [])
    print(f"  EligibilityCriterionItems: {len(ecis)}")
    
    inc_count = 0
    exc_count = 0
    for eci in ecis:
        criterion = eci.get('criterion', {})
        cat = criterion.get('category', {})
        cat_sc = cat.get('standardCode', {})
        cat_decode = cat_sc.get('decode', '') or cat.get('decode', '')
        if 'inclusion' in cat_decode.lower():
            inc_count += 1
        elif 'exclusion' in cat_decode.lower():
            exc_count += 1
    
    print(f"  Inclusion: {inc_count}, Exclusion: {exc_count}")
    
    if inc_count == 0:
        finding("CRITICAL", "completeness", "No inclusion criteria extracted")
    if exc_count == 0:
        finding("CRITICAL", "completeness", "No exclusion criteria extracted")
    
    # Population
    pop = sd.get('population', {})
    print(f"  Population: {bool(pop)}")
    if pop:
        planned_age = pop.get('plannedAge', {})
        planned_enroll = pop.get('plannedEnrollmentNumber', {})
        planned_sex = pop.get('plannedSex', [])
        print(f"    plannedAge: {planned_age}")
        print(f"    plannedEnrollment: {planned_enroll}")
        print(f"    plannedSex: {len(planned_sex)} entries")
    
    # ========== 5. INTERVENTIONS ==========
    print("\n" + "=" * 60)
    print("5. INTERVENTIONS")
    print("=" * 60)
    
    interventions = sv.get('studyInterventions', [])
    products = sv.get('administrableProducts', [])
    print(f"  StudyInterventions: {len(interventions)}")
    print(f"  AdministrableProducts: {len(products)}")
    
    for si in interventions:
        print(f"  Intervention: {si.get('name', '?')} | type={si.get('type', '?')}")
    
    admins = []
    for prod in products:
        for admin in prod.get('administrations', []):
            admins.append(admin)
    print(f"  Administrations: {len(admins)}")
    
    for admin in admins[:5]:
        route = admin.get('route', {})
        route_decode = route.get('standardCode', {}).get('decode', '') or route.get('decode', '')
        freq = admin.get('frequency', {})
        freq_decode = freq.get('standardCode', {}).get('decode', '') or freq.get('decode', '') if freq else ''
        print(f"    {admin.get('name', '?')}: route={route_decode}, freq={freq_decode}")
    
    # ========== 6. SoA (Schedule of Activities) ==========
    print("\n" + "=" * 60)
    print("6. SCHEDULE OF ACTIVITIES")
    print("=" * 60)
    
    activities = sd.get('activities', [])
    encounters = sd.get('encounters', [])
    timelines = sd.get('scheduleTimelines', [])
    
    print(f"  Activities: {len(activities)}")
    print(f"  Encounters: {len(encounters)}")
    print(f"  ScheduleTimelines: {len(timelines)}")
    
    total_instances = 0
    for tl in timelines:
        instances = tl.get('instances', [])
        total_instances += len(instances)
        timings = tl.get('timings', [])
        print(f"  Timeline '{tl.get('name', '?')}': {len(instances)} instances, {len(timings)} timings")
    
    print(f"  Total ScheduledInstances: {total_instances}")
    
    # Check orphaned activities
    scheduled_act_ids = set()
    for tl in timelines:
        for inst in tl.get('instances', []):
            for aid in inst.get('activityIds', []):
                scheduled_act_ids.add(aid)
    
    orphaned = [a for a in activities if a['id'] not in scheduled_act_ids]
    print(f"  Orphaned activities: {len(orphaned)}")
    for o in orphaned[:5]:
        print(f"    {o.get('name', '?')}")
    if len(orphaned) > 5:
        print(f"    ... and {len(orphaned)-5} more")
    
    if len(encounters) < 3:
        finding("HIGH", "completeness", f"Only {len(encounters)} encounters - protocol likely has more visits")
    
    # ========== 7. NARRATIVE ==========
    print("\n" + "=" * 60)
    print("7. NARRATIVE CONTENT")
    print("=" * 60)
    
    ncis = sv.get('narrativeContentItems', [])
    print(f"  NarrativeContentItems: {len(ncis)}")
    
    section_numbers = set()
    for nci in ncis:
        for nc in nci.get('contentItems', []) or [nci]:
            sn = nc.get('sectionNumber', '')
            if sn:
                section_numbers.add(sn.split('.')[0] if '.' in str(sn) else str(sn))
    
    m11_sections = set(str(i) for i in range(1, 15))
    covered = section_numbers & m11_sections
    missing = m11_sections - covered
    print(f"  M11 sections covered: {sorted(covered)}")
    if missing:
        print(f"  M11 sections missing: {sorted(missing)}")
        finding("MEDIUM", "m11", f"Missing M11 sections: {sorted(missing)}")
    
    # Abbreviations
    abbrevs = sv.get('abbreviations', [])
    print(f"  Abbreviations: {len(abbrevs)}")
    
    # ========== 8. AMENDMENTS ==========
    print("\n" + "=" * 60)
    print("8. AMENDMENTS")
    print("=" * 60)
    
    amendments = sv.get('amendments', [])
    print(f"  StudyAmendments: {len(amendments)}")
    for a in amendments[:3]:
        print(f"    {a.get('number', '?')}: {str(a.get('summary', '?'))[:60]}")
    
    # ========== 9. C-CODE AUDIT ==========
    print("\n" + "=" * 60)
    print("9. C-CODE AUDIT")
    print("=" * 60)
    
    # Check key C-code fields
    checks = [
        ("trialPhaseCode", sd.get('trialPhaseCode', {})),
        ("trialTypeCode", sd.get('trialTypeCode', {})),
    ]
    
    for name, code_obj in checks:
        sc = code_obj.get('standardCode', {})
        code = sc.get('code', '') or code_obj.get('code', '')
        decode = sc.get('decode', '') or code_obj.get('decode', '')
        status = 'OK' if code else 'MISSING'
        print(f"  {name}: {decode} ({code}) [{status}]")
    
    # Check arm type codes
    valid_arm_codes = {'C174266', 'C174267', 'C174268', 'C174451'}
    for arm in arms:
        atype = arm.get('type', {})
        code = atype.get('standardCode', {}).get('code', '') or atype.get('code', '')
        if code and code not in valid_arm_codes:
            finding("HIGH", "C-codes", f"Arm '{arm.get('name')}' has unexpected arm type code: {code}")
    
    # Check objective level codes
    valid_obj_codes = {'C85826', 'C85827', 'C163559'}
    for obj in objectives:
        level = obj.get('level', {})
        code = level.get('standardCode', {}).get('code', '') or level.get('code', '')
        if code and code not in valid_obj_codes:
            finding("HIGH", "C-codes", f"Objective has unexpected level code: {code}")
    
    # Check eligibility category codes
    valid_elig_codes = {'C25532', 'C25370'}
    for eci in ecis:
        crit = eci.get('criterion', {})
        cat = crit.get('category', {})
        code = cat.get('standardCode', {}).get('code', '') or cat.get('code', '')
        if code and code not in valid_elig_codes:
            finding("MEDIUM", "C-codes", f"Eligibility criterion has unexpected category code: {code}")
    
    # ========== 10. UUID INTEGRITY ==========
    print("\n" + "=" * 60)
    print("10. UUID INTEGRITY")
    print("=" * 60)
    
    # Collect all entity IDs
    all_ids = set()
    id_types = defaultdict(list)
    
    def collect_ids(obj, path="root"):
        if isinstance(obj, dict):
            oid = obj.get('id')
            itype = obj.get('instanceType', '')
            if oid and itype:
                if oid in all_ids:
                    id_types[oid].append(itype)
                else:
                    all_ids.add(oid)
                    id_types[oid] = [itype]
            for k, v in obj.items():
                collect_ids(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                collect_ids(item, f"{path}[{i}]")
    
    collect_ids(usdm)
    
    # Check for UUID collisions
    collisions = {k: v for k, v in id_types.items() if len(v) > 1 and len(set(v)) > 1}
    print(f"  Total unique IDs: {len(all_ids)}")
    print(f"  UUID collisions (different types): {len(collisions)}")
    for cid, types in list(collisions.items())[:5]:
        finding("CRITICAL", "integrity", f"UUID collision: {cid[:12]}... used by {set(types)}")
    
    # ========== 11. EXTENSION ATTRIBUTES ==========
    print("\n" + "=" * 60)
    print("11. EXTENSION ATTRIBUTES")
    print("=" * 60)
    
    ext_names = Counter()
    def count_extensions(obj):
        if isinstance(obj, dict):
            for ea in obj.get('extensionAttributes', []):
                ext_names[ea.get('name', '?')] += 1
            for v in obj.values():
                count_extensions(v)
        elif isinstance(obj, list):
            for item in obj:
                count_extensions(item)
    
    count_extensions(usdm)
    print(f"  Total extension attributes: {sum(ext_names.values())}")
    for name, count in ext_names.most_common(10):
        print(f"    {name}: {count}")
    
    # Check for _temp_ leaked data
    temp_count = sum(1 for name in ext_names if '_temp_' in name.lower())
    if temp_count > 0:
        finding("MEDIUM", "cleanup", f"{temp_count} _temp_ extension attributes leaked into final output")
    
    # ========== 12. ANALYSIS POPULATIONS ==========
    print("\n" + "=" * 60)
    print("12. ANALYSIS POPULATIONS & SAP DATA")
    print("=" * 60)
    
    analysis_pops = sd.get('analysisPopulations', [])
    print(f"  AnalysisPopulations: {len(analysis_pops)}")
    for ap in analysis_pops:
        print(f"    {ap.get('name', '?')}: {str(ap.get('description', '?'))[:60]}")
    
    # ========== SUMMARY ==========
    print("\n" + "=" * 60)
    print("FINDINGS SUMMARY")
    print("=" * 60)
    
    severity_counts = Counter(f['severity'] for f in findings)
    print(f"  CRITICAL: {severity_counts.get('CRITICAL', 0)}")
    print(f"  HIGH: {severity_counts.get('HIGH', 0)}")
    print(f"  MEDIUM: {severity_counts.get('MEDIUM', 0)}")
    print(f"  LOW: {severity_counts.get('LOW', 0)}")
    print(f"  TOTAL: {len(findings)}")
    
    print("\nAll findings:")
    for f in sorted(findings, key=lambda x: ['CRITICAL','HIGH','MEDIUM','LOW'].index(x['severity'])):
        print(f"  [{f['severity']}] {f['category']}: {f['message']}")
    
    return findings

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python scripts/local_quality_review.py <output_dir>")
        sys.exit(1)
    review(sys.argv[1])
