import json, sys, argparse

def apply_header_repairs(soa_path: str, header_path: str, output: str):
    with open(soa_path, 'r', encoding='utf-8') as f:
        soa = json.load(f)
    with open(header_path, 'r', encoding='utf-8') as f:
        hdr = json.load(f)

    timeline = soa.get('study', {}).get('versions', [{}])[0].get('timeline', {})
    if not timeline:
        print('[WARN] No timeline found in SoA, nothing to validate.')
        json.dump(soa, open(output, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
        return

    fixes = []
    # ---- Validate activityGroupId ----
    hdr_groups = {g['id']: g for g in hdr.get('rowHierarchy', {}).get('activityGroups', []) if g.get('activities')}
    name_to_gid = {name.strip().lower(): gid for gid, grp in hdr_groups.items() for name in grp.get('activities', [])}
    for act in timeline.get('activities', []):
        if not act.get('activityGroupId'):
            gid = name_to_gid.get(act.get('name', '').strip().lower())
            if gid:
                act['activityGroupId'] = gid
                fixes.append(f"Added activityGroupId={gid} to activity {act.get('id')}")
    # ---- Validate plannedTimepoints ----
    hdr_tp_names = [enc['name'] for enc in hdr.get('columnHierarchy', {}).get('encounters', [])]
    # Not enforcing order strictly; can be extended.

    # ---- Inject Encounters & Epochs if missing ----
    col_h = hdr.get('columnHierarchy', {})
    hdr_encs = col_h.get('encounters', [])
    hdr_epochs = col_h.get('epochs', [])

    # Add missing encounters
    tl_encs = timeline.setdefault('encounters', [])
    existing_enc_ids = {e.get('id') for e in tl_encs}
    for enc in hdr_encs:
        if enc.get('id') not in existing_enc_ids:
            tl_encs.append({'id': enc['id'], 'name': enc.get('name', ''), 'description': enc.get('description', '')})
            fixes.append(f"Added encounter {enc['id']} from header structure")

    # Add epochs verbatim from header structure (no fabricated encounter mapping)
    tl_epochs = timeline.setdefault('epochs', [])
    if not tl_epochs and hdr_epochs:
        for ep in hdr_epochs:
            tl_epochs.append({
                'id': ep['id'],
                'name': ep.get('name', ''),
                'description': ep.get('description', '')
            })
        fixes.append(f"Injected {len(hdr_epochs)} epochs from header structure (encounters left unmapped)")
    # No further automatic encounter assignment; mapping to be handled by future vision/LLM step

    if fixes:
        soa.setdefault('p2uHeaderValidation', {})['fixes'] = fixes
        print(f'[INFO] Applied {len(fixes)} header-driven fixes.')
    else:
        print('[INFO] No header-driven fixes required.')

    with open(output, 'w', encoding='utf-8') as f:
        json.dump(soa, f, indent=2, ensure_ascii=False)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Validate & repair SoA against header structure.')
    ap.add_argument('--soa-file', required=True)
    ap.add_argument('--header-structure', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    apply_header_repairs(args.soa_file, args.header_structure, args.output)
