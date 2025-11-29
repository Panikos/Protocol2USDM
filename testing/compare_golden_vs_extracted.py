#!/usr/bin/env python3
"""
COMPREHENSIVE side-by-side comparison of Golden File vs Extracted values vs Combined USDM.
Shows ALL values for ALL entities with semantic matching.
"""

import json
import sys
import re
from pathlib import Path
from datetime import datetime
from difflib import SequenceMatcher

# Paths
GOLDEN_FILE = "input/Alexion_NCT04573309_Wilsons_golden.json"
OUTPUT_DIR = "output/Alexion_NCT04573309_Wilsons"
COMBINED_FILE = "output/Alexion_NCT04573309_Wilsons/protocol_usdm.json"
SOA_FILE = "output/Alexion_NCT04573309_Wilsons/9_final_soa.json"
REPORT_FILE = "output/Alexion_NCT04573309_Wilsons/golden_comparison_report.txt"

# Collect output lines for saving to file
output_lines = []

def load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def out(text=""):
    """Print and collect output."""
    print(text)
    output_lines.append(text)

def section_header(title):
    """Print section header."""
    out()
    out("=" * 200)
    out(f"  {title}")
    out("=" * 200)

def normalize(val):
    """Normalize value for comparison - TBD, dash, empty are equivalent."""
    if val is None:
        return ""
    s = str(val).strip().lower()
    if s in ['tbd', '-', 'n/a', 'none', '']:
        return ""
    return s

def similarity(a, b):
    """Calculate string similarity ratio."""
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()

def semantic_match(golden_val, extracted_val):
    """Check if two values semantically match."""
    g = normalize(golden_val)
    e = normalize(extracted_val)
    # Both empty = match
    if not g and not e:
        return True
    # One empty, one not = no match
    if not g or not e:
        return False
    # Exact match
    if g == e:
        return True
    # High similarity (>80%)
    if similarity(g, e) > 0.8:
        return True
    # Substring match
    if g in e or e in g:
        return True
    return False

def find_best_match(target, candidates, key='text'):
    """Find best matching candidate for target using semantic similarity."""
    if not candidates:
        return None, 0
    
    target_val = target.get(key, target.get('name', str(target))) if isinstance(target, dict) else str(target)
    best_match = None
    best_score = 0
    
    for c in candidates:
        c_val = c.get(key, c.get('name', str(c))) if isinstance(c, dict) else str(c)
        score = similarity(target_val, c_val)
        if score > best_score:
            best_score = score
            best_match = c
    
    return best_match, best_score

def match_status(golden, extracted, combined=None):
    """Return match status emojis for extracted and combined vs golden."""
    e_match = "✅" if semantic_match(golden, extracted) else "❌"
    c_match = "✅" if combined is not None and semantic_match(golden, combined) else "❌"
    return e_match, c_match

def row3(idx, field, golden, extracted, combined):
    """Print a 3-column comparison row."""
    g = str(golden)[:55] if golden else "-"
    e = str(extracted)[:55] if extracted else "-"
    c = str(combined)[:55] if combined else "-"
    
    e_match, c_match = match_status(golden, extracted, combined)
    
    out(f"  {str(idx):<4} {field:<20} {g:<57} {e:<57} {e_match} {c:<45} {c_match}")

def compare_all():
    # Load golden file
    golden = load_json(GOLDEN_FILE)
    gv = golden['study']['versions'][0]
    gd = gv.get('studyDesigns', [{}])[0]
    
    # Load combined USDM and flatten structure
    combined_raw = load_json(COMBINED_FILE) if Path(COMBINED_FILE).exists() else {}
    comb_study = combined_raw.get('study', {})
    comb_design = combined_raw.get('studyDesigns', [{}])[0] if combined_raw.get('studyDesigns') else {}
    
    # Flatten combined for easy access - note different key names in combined file
    combined = {
        'studyIdentifiers': comb_study.get('studyIdentifiers', []),
        'titles': comb_study.get('studyTitles', []),  # studyTitles not titles
        'indications': comb_study.get('indications', []),
        # From studyDesigns[0]:
        'eligibilityCriteria': comb_design.get('eligibilityCriteria', []),
        'objectives': comb_design.get('objectives', []),
        'endpoints': comb_design.get('endpoints', []),
        'studyArms': comb_design.get('studyArms', []),
        'epochs': comb_design.get('epochs', []),
        'studyInterventions': comb_design.get('studyInterventions', []),
        'activities': comb_design.get('activities', []),
        'encounters': comb_design.get('encounters', []),
        # Top-level entities:
        'administrableProducts': combined_raw.get('administrableProducts', []),
        'abbreviations': combined_raw.get('abbreviations', []),
        'studyAmendments': combined_raw.get('studyAmendments', []),
        'procedures': combined_raw.get('procedures', []),
        'analysisPopulations': combined_raw.get('analysisPopulations', []),  # Top-level in combined
    }
    
    out("=" * 200)
    out("  COMPREHENSIVE GOLDEN vs EXTRACTED vs COMBINED USDM COMPARISON")
    out(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    out("=" * 200)
    out()
    out("  Legend: E = Extracted matches Golden | C = Combined USDM matches Golden")
    out("  Matching: Semantic matching (TBD/dash = empty, >80% similarity = match)")
    out()
    
    def header3(title):
        out(f"  {'#':<4} {title:<20} {'GOLDEN':<57} {'EXTRACTED':<57} {'E'} {'COMBINED':<45} {'C'}")
        out("  " + "-" * 195)
    
    # Load all extracted files
    meta = load_json(Path(OUTPUT_DIR) / "2_study_metadata.json").get('metadata', {})
    elig = load_json(Path(OUTPUT_DIR) / "3_eligibility_criteria.json").get('eligibility', {})
    obj_data = load_json(Path(OUTPUT_DIR) / "4_objectives_endpoints.json").get('objectivesEndpoints', {})
    design = load_json(Path(OUTPUT_DIR) / "5_study_design.json").get('studyDesignStructure', {})
    int_data = load_json(Path(OUTPUT_DIR) / "6_interventions.json").get('interventions', {})
    narr = load_json(Path(OUTPUT_DIR) / "7_narrative_structure.json").get('narrative', {})
    adv = load_json(Path(OUTPUT_DIR) / "8_advanced_entities.json").get('advanced', {})
    proc = load_json(Path(OUTPUT_DIR) / "9_procedures_devices.json").get('proceduresDevices', {})
    sap = load_json(Path(OUTPUT_DIR) / "11_sap_populations.json").get('sapData', {})
    soa = load_json(Path(OUTPUT_DIR) / "9_final_soa.json")
    
    # Parse SoA
    try:
        timeline = soa.get('study', {}).get('versions', [{}])[0].get('timeline', {})
        e_activities = timeline.get('activities', [])
        e_encounters = timeline.get('encounters', [])
    except:
        e_activities = []
        e_encounters = []
    
    # =========================================================================
    # 1. STUDY IDENTIFIERS - Semantic matching
    # =========================================================================
    section_header("1. STUDY IDENTIFIERS - SEMANTIC MATCHING")
    header3("Identifier")
    
    g_ids = gv.get('studyIdentifiers', [])
    e_ids = meta.get('identifiers', [])
    c_ids = combined.get('studyIdentifiers', [])
    
    # Match by finding best match for each golden identifier
    used_e = set()
    used_c = set()
    for i, g_id in enumerate(g_ids):
        g_text = g_id.get('text', '-')
        # Find best extracted match
        best_e, score_e = None, 0
        for j, e_id in enumerate(e_ids):
            if j not in used_e:
                e_text = e_id.get('text', '')
                if g_text.lower() == e_text.lower() or g_text in e_text or e_text in g_text:
                    best_e = e_id
                    used_e.add(j)
                    break
        # Find best combined match
        best_c, score_c = None, 0
        for j, c_id in enumerate(c_ids):
            if j not in used_c:
                c_text = c_id.get('text', '')
                if g_text.lower() == c_text.lower() or g_text in c_text or c_text in g_text:
                    best_c = c_id
                    used_c.add(j)
                    break
        e_text = best_e.get('text', '-') if best_e else '-'
        c_text = best_c.get('text', '-') if best_c else '-'
        row3(i+1, "Identifier", g_text, e_text, c_text)
    
    # =========================================================================
    # 2. STUDY TITLES - Match by type, TBD = dash
    # =========================================================================
    section_header("2. STUDY TITLES - SEMANTIC MATCHING (TBD = dash)")
    header3("Title Type")
    
    g_titles = gv.get('titles', [])
    e_titles = meta.get('titles', [])
    c_titles = combined.get('titles', [])
    
    for i, g_t in enumerate(g_titles):
        g_type = g_t.get('type', {}).get('decode', 'Unknown')
        g_text = g_t.get('text', '-')
        # Find by type
        e_match = next((t for t in e_titles if t.get('type', {}).get('decode', '') == g_type), {})
        c_match = next((t for t in c_titles if t.get('type', {}).get('decode', '') == g_type), {})
        e_text = e_match.get('text', '-')
        c_text = c_match.get('text', '-')
        row3(i+1, g_type, g_text, e_text, c_text)
    
    # =========================================================================
    # 3. INDICATIONS
    # =========================================================================
    section_header("3. INDICATIONS")
    header3("Field")
    
    g_inds = gd.get('indications', [])
    e_inds = meta.get('indications', [])
    c_inds = combined.get('indications', [])
    
    max_inds = max(len(g_inds), len(e_inds), len(c_inds), 1)
    for i in range(max_inds):
        g_name = g_inds[i].get('name', '-') if i < len(g_inds) else '-'
        e_name = e_inds[i].get('name', '-') if i < len(e_inds) else '-'
        c_name = c_inds[i].get('name', '-') if i < len(c_inds) else '-'
        row3(i+1, "Indication", g_name, e_name, c_name)
    
    # =========================================================================
    # 4. ELIGIBILITY CRITERIA - Side by side with golden
    # =========================================================================
    section_header("4. ELIGIBILITY CRITERIA")
    
    g_criteria = gd.get('eligibilityCriteria', gd.get('population', {}).get('criteria', []))
    e_criteria = elig.get('eligibilityCriteria', [])
    c_criteria = combined.get('eligibilityCriteria', [])
    
    out(f"  {'#':<4} {'Category':<12} {'GOLDEN':<55} {'EXTRACTED':<55} {'E'} {'COMBINED':<40} {'C'}")
    out("  " + "-" * 195)
    
    # Group by category (golden uses 'Inclusion Criteria', extracted uses 'Inclusion')
    for cat_label, cat_variants in [('Inclusion', ['Inclusion', 'Inclusion Criteria']), 
                                     ('Exclusion', ['Exclusion', 'Exclusion Criteria'])]:
        g_cat = [c for c in g_criteria if c.get('category', {}).get('decode', '') in cat_variants]
        e_cat = [c for c in e_criteria if c.get('category', {}).get('decode', '') in cat_variants]
        c_cat = [c for c in c_criteria if c.get('category', {}).get('decode', '') in cat_variants]
        cat = cat_label
        
        max_cat = max(len(g_cat), len(e_cat), len(c_cat))
        for i in range(max_cat):
            g_name = g_cat[i].get('name', g_cat[i].get('text', '-'))[:52] if i < len(g_cat) else '-'
            e_name = e_cat[i].get('name', e_cat[i].get('text', '-'))[:52] if i < len(e_cat) else '-'
            c_name = c_cat[i].get('name', c_cat[i].get('text', '-'))[:37] if i < len(c_cat) else '-'
            e_m, c_m = match_status(g_name, e_name, c_name)
            out(f"  {i+1:<4} {cat:<12} {g_name:<55} {e_name:<55} {e_m} {c_name:<40} {c_m}")
    
    out()
    out(f"  SUMMARY: Golden={len(g_criteria)}, Extracted={len(e_criteria)}, Combined={len(c_criteria)}")
    
    # =========================================================================
    # 5. OBJECTIVES - Semantic matching
    # =========================================================================
    section_header("5. OBJECTIVES - SEMANTIC MATCHING")
    
    g_objectives = gd.get('objectives', [])
    e_objectives = obj_data.get('objectives', [])
    c_objectives = combined.get('objectives', [])
    
    out(f"  {'#':<4} {'Level':<20} {'GOLDEN':<55} {'EXTRACTED':<55} {'E'} {'COMBINED':<40} {'C'}")
    out("  " + "-" * 195)
    
    used_e = set()
    for i, g_obj in enumerate(g_objectives):
        g_level = g_obj.get('level', {}).get('decode', 'Unknown')
        g_text = g_obj.get('text', '-')
        # Find best extracted match by similarity
        best_e_idx, best_e_score = -1, 0
        for j, e_obj in enumerate(e_objectives):
            if j not in used_e:
                score = similarity(g_text, e_obj.get('text', ''))
                if score > best_e_score:
                    best_e_score = score
                    best_e_idx = j
        if best_e_idx >= 0 and best_e_score > 0.5:
            used_e.add(best_e_idx)
            e_text = e_objectives[best_e_idx].get('text', '-')
        else:
            e_text = '-'
        # Find best combined match
        best_c, _ = find_best_match(g_obj, c_objectives, 'text')
        c_text = best_c.get('text', '-') if best_c else '-'
        
        e_m, c_m = match_status(g_text, e_text, c_text)
        out(f"  {i+1:<4} {g_level:<20} {str(g_text)[:55]:<55} {str(e_text)[:55]:<55} {e_m} {str(c_text)[:40]:<40} {c_m}")
    
    # Show unmatched extracted
    out()
    out("  EXTRACTED NOT MATCHED TO GOLDEN:")
    for j, e_obj in enumerate(e_objectives):
        if j not in used_e:
            e_level = e_obj.get('level', {}).get('decode', 'Unknown')
            e_text = e_obj.get('text', '-')
            out(f"  +    {e_level:<20} {str(e_text)[:130]}")
    
    # =========================================================================
    # 6. ENDPOINTS
    # =========================================================================
    section_header("6. ENDPOINTS")
    
    g_endpoints = gd.get('endpoints', [])
    e_endpoints = obj_data.get('endpoints', [])
    c_endpoints = combined.get('endpoints', [])
    
    out(f"  {'#':<4} {'Level':<15} {'GOLDEN':<50} {'EXTRACTED':<50} {'E'} {'COMBINED':<35} {'C'}")
    out("  " + "-" * 195)
    
    max_ep = max(len(g_endpoints), len(e_endpoints), len(c_endpoints))
    for i in range(max_ep):
        g_level = g_endpoints[i].get('level', {}).get('decode', '-') if i < len(g_endpoints) else '-'
        g_text = g_endpoints[i].get('text', '-') if i < len(g_endpoints) else '-'
        e_level = e_endpoints[i].get('level', {}).get('decode', '-') if i < len(e_endpoints) else '-'
        e_text = e_endpoints[i].get('text', '-') if i < len(e_endpoints) else '-'
        c_text = c_endpoints[i].get('text', '-') if i < len(c_endpoints) else '-'
        e_m, c_m = match_status(g_text, e_text, c_text)
        out(f"  {i+1:<4} {g_level:<15} {str(g_text)[:50]:<50} {str(e_text)[:50]:<50} {e_m} {str(c_text)[:35]:<35} {c_m}")
    
    # =========================================================================
    # 7. STUDY ARMS
    # =========================================================================
    section_header("7. STUDY ARMS")
    header3("Field")
    
    g_arms = gd.get('arms', gd.get('studyArms', []))
    e_arms = design.get('studyArms', [])
    c_arms = combined.get('studyArms', [])
    
    max_arms = max(len(g_arms), len(e_arms), len(c_arms))
    for i in range(max_arms):
        g_name = g_arms[i].get('name', '-') if i < len(g_arms) else '-'
        e_name = e_arms[i].get('name', '-') if i < len(e_arms) else '-'
        c_name = c_arms[i].get('name', '-') if i < len(c_arms) else '-'
        row3(i+1, f"Arm {i+1} Name", g_name, e_name, c_name)
        g_desc = g_arms[i].get('description', '-') if i < len(g_arms) else '-'
        e_desc = e_arms[i].get('description', '-') if i < len(e_arms) else '-'
        c_desc = c_arms[i].get('description', '-') if i < len(c_arms) else '-'
        row3('', f"Arm {i+1} Desc", g_desc, e_desc, c_desc)
    
    # =========================================================================
    # 8. EPOCHS
    # =========================================================================
    section_header("8. EPOCHS")
    header3("Field")
    
    g_epochs = gd.get('epochs', [])
    e_epochs = design.get('studyEpochs', design.get('epochs', []))
    c_epochs = combined.get('epochs', [])
    
    # Also check SoA for epochs
    if not e_epochs and e_encounters:
        # Try to extract epoch info from encounters
        epoch_names = set()
        for enc in e_encounters:
            epoch_ref = enc.get('epochId', enc.get('epoch', ''))
            if epoch_ref:
                epoch_names.add(epoch_ref)
        e_epochs = [{'name': n} for n in sorted(epoch_names)]
    
    max_epochs = max(len(g_epochs), len(e_epochs), len(c_epochs))
    for i in range(max_epochs):
        g_name = g_epochs[i].get('name', '-') if i < len(g_epochs) else '-'
        e_name = e_epochs[i].get('name', '-') if i < len(e_epochs) else '-'
        c_name = c_epochs[i].get('name', '-') if i < len(c_epochs) else '-'
        row3(i+1, f"Epoch {i+1}", g_name, e_name, c_name)
    
    # =========================================================================
    # 9. INTERVENTIONS
    # =========================================================================
    section_header("9. INTERVENTIONS")
    
    g_interventions = gd.get('studyInterventions', [])
    e_interventions = int_data.get('studyInterventions', [])
    c_interventions = combined.get('studyInterventions', [])
    e_products = int_data.get('administrableProducts', [])
    c_products = combined.get('administrableProducts', [])
    
    out(f"  {'#':<4} {'Field':<20} {'GOLDEN':<55} {'EXTRACTED':<55} {'E'} {'COMBINED':<40} {'C'}")
    out("  " + "-" * 195)
    
    max_intv = max(len(g_interventions), len(e_interventions), len(c_interventions))
    for i in range(max_intv):
        g_name = g_interventions[i].get('name', '-') if i < len(g_interventions) else '-'
        e_name = e_interventions[i].get('name', '-') if i < len(e_interventions) else '-'
        c_name = c_interventions[i].get('name', '-') if i < len(c_interventions) else '-'
        row3(i+1, f"Intervention", g_name, e_name, c_name)
    
    out()
    out("  ADMINISTRABLE PRODUCTS:")
    max_prod = max(len(e_products), len(c_products))
    for i in range(max_prod):
        e_prod = e_products[i] if i < len(e_products) else {}
        c_prod = c_products[i] if i < len(c_products) else {}
        e_form = e_prod.get('doseForm', {}).get('decode', '-') if isinstance(e_prod.get('doseForm'), dict) else e_prod.get('doseForm', '-')
        c_form = c_prod.get('doseForm', {}).get('decode', '-') if isinstance(c_prod.get('doseForm'), dict) else c_prod.get('doseForm', '-')
        out(f"  {i+1:<4} {'Name':<20} {'-':<55} {e_prod.get('name', '-'):<55}    {c_prod.get('name', '-'):<40}")
        out(f"       {'Dose Form':<20} {'-':<55} {e_form:<55}    {c_form:<40}")
        out(f"       {'Strength':<20} {'-':<55} {e_prod.get('strength', '-'):<55}    {c_prod.get('strength', '-'):<40}")
    
    # =========================================================================
    # 10. ABBREVIATIONS
    # =========================================================================
    section_header("10. ABBREVIATIONS")
    
    g_abbrs = gv.get('abbreviations', [])
    e_abbrs = narr.get('abbreviations', [])
    c_abbrs = combined.get('abbreviations', [])
    
    out(f"  {'#':<4} {'Abbr':<15} {'GOLDEN Expanded':<45} {'EXTRACTED Expanded':<45} {'E'} {'COMBINED Expanded':<35} {'C'}")
    out("  " + "-" * 195)
    
    # Combine all abbreviations by matching abbreviatedText
    all_abbrs = {}
    for a in g_abbrs:
        key = a.get('abbreviatedText', '')
        if key:
            all_abbrs[key] = {'g': a.get('expandedText', '-'), 'e': '-', 'c': '-'}
    for a in e_abbrs:
        key = a.get('abbreviatedText', '')
        if key:
            if key not in all_abbrs:
                all_abbrs[key] = {'g': '-', 'e': '-', 'c': '-'}
            all_abbrs[key]['e'] = a.get('expandedText', '-')
    for a in c_abbrs:
        key = a.get('abbreviatedText', '')
        if key:
            if key not in all_abbrs:
                all_abbrs[key] = {'g': '-', 'e': '-', 'c': '-'}
            all_abbrs[key]['c'] = a.get('expandedText', '-')
    
    for i, (abbr, vals) in enumerate(sorted(all_abbrs.items())):
        e_m, c_m = match_status(vals['g'], vals['e'], vals['c'])
        out(f"  {i+1:<4} {abbr:<15} {str(vals['g'])[:45]:<45} {str(vals['e'])[:45]:<45} {e_m} {str(vals['c'])[:35]:<35} {c_m}")
    
    # =========================================================================
    # 11. AMENDMENTS - Match by amendment number
    # =========================================================================
    section_header("11. AMENDMENTS - MATCHED BY NUMBER")
    
    g_amendments = gv.get('amendments', [])
    e_amendments = adv.get('studyAmendments', [])
    c_amendments = combined.get('studyAmendments', [])
    
    out(f"  {'#':<4} {'Amend#':<12} {'GOLDEN Summary':<50} {'EXTRACTED Summary':<50} {'E'} {'COMBINED Summary':<35} {'C'}")
    out("  " + "-" * 195)
    
    # Match by amendment number
    all_numbers = set()
    for a in g_amendments:
        all_numbers.add(str(a.get('number', '')))
    for a in e_amendments:
        all_numbers.add(str(a.get('number', '')))
    for a in c_amendments:
        all_numbers.add(str(a.get('number', '')))
    
    # Sort numerically where possible
    def sort_key(n):
        try:
            # Extract leading number for sorting
            import re
            match = re.match(r'(\d+)', n)
            return (int(match.group(1)), n) if match else (999, n)
        except:
            return (999, n)
    
    for i, num in enumerate(sorted(all_numbers, key=sort_key)):
        if not num:
            continue
        # Find matching amendments
        g_match = next((a for a in g_amendments if str(a.get('number', '')) == num), None)
        e_match = next((a for a in e_amendments if str(a.get('number', '')) == num), None)
        c_match = next((a for a in c_amendments if str(a.get('number', '')) == num), None)
        
        g_sum = g_match.get('summary', '-')[:47] if g_match else '-'
        e_sum = (e_match.get('summary', e_match.get('description', '-')) or '-')[:47] if e_match else '-'
        c_sum = (c_match.get('summary', c_match.get('description', '-')) or '-')[:32] if c_match else '-'
        
        e_m, c_m = match_status(g_sum if g_match else None, e_sum if e_match else None, c_sum if c_match else None)
        out(f"  {i+1:<4} {num:<12} {g_sum:<50} {e_sum:<50} {e_m} {c_sum:<35} {c_m}")
    
    # =========================================================================
    # 12. PROCEDURES
    # =========================================================================
    section_header("12. PROCEDURES")
    
    g_procedures = gd.get('procedures', [])
    e_procedures = proc.get('procedures', [])
    c_procedures = combined.get('procedures', [])
    
    out(f"  {'#':<4} {'GOLDEN Procedure':<45} {'EXTRACTED Procedure':<45} {'E'} {'COMBINED Procedure':<35} {'C'}")
    out("  " + "-" * 195)
    
    max_proc = max(len(g_procedures), len(e_procedures), len(c_procedures))
    for i in range(max_proc):
        g_name = g_procedures[i].get('name', '-') if i < len(g_procedures) else '-'
        e_name = e_procedures[i].get('name', '-') if i < len(e_procedures) else '-'
        c_name = c_procedures[i].get('name', '-') if i < len(c_procedures) else '-'
        e_m, c_m = match_status(g_name, e_name, c_name)
        out(f"  {i+1:<4} {str(g_name)[:45]:<45} {str(e_name)[:45]:<45} {e_m} {str(c_name)[:35]:<35} {c_m}")
    
    # =========================================================================
    # 13. ANALYSIS POPULATIONS
    # =========================================================================
    section_header("13. ANALYSIS POPULATIONS")
    
    g_populations = gd.get('analysisPopulations', [])
    e_populations = sap.get('analysisPopulations', [])
    c_populations = combined.get('analysisPopulations', [])
    
    out(f"  {'#':<4} {'GOLDEN Population':<40} {'EXTRACTED Population':<40} {'E'} {'COMBINED Population':<30} {'C'}")
    out("  " + "-" * 195)
    
    max_pop = max(len(g_populations), len(e_populations), len(c_populations))
    for i in range(max_pop):
        g_name = g_populations[i].get('name', '-') if i < len(g_populations) else '-'
        e_name = e_populations[i].get('name', '-') if i < len(e_populations) else '-'
        c_name = c_populations[i].get('name', '-') if i < len(c_populations) else '-'
        e_m, c_m = match_status(g_name, e_name, c_name)
        out(f"  {i+1:<4} {str(g_name)[:40]:<40} {str(e_name)[:40]:<40} {e_m} {str(c_name)[:30]:<30} {c_m}")
    
    # =========================================================================
    # 14. SOA ACTIVITIES - Semantic matching
    # =========================================================================
    section_header("14. SOA ACTIVITIES - SEMANTIC MATCHING")
    
    g_activities = gd.get('activities', [])
    c_activities = combined.get('activities', [])
    
    out(f"  {'#':<4} {'GOLDEN Activity':<50} {'EXTRACTED Activity (Best Match)':<50} {'Match%':<7} {'COMBINED':<35}")
    out("  " + "-" * 195)
    
    used_e = set()
    for i, g_act in enumerate(g_activities):
        g_name = g_act.get('name', '-')
        # Find best match in extracted
        best_e_idx, best_e_score = -1, 0
        for j, e_act in enumerate(e_activities):
            if j not in used_e:
                score = similarity(g_name, e_act.get('name', ''))
                if score > best_e_score:
                    best_e_score = score
                    best_e_idx = j
        if best_e_idx >= 0 and best_e_score > 0.3:
            used_e.add(best_e_idx)
            e_name = e_activities[best_e_idx].get('name', '-')
        else:
            e_name = '-'
        # Find best combined match
        best_c, c_score = find_best_match(g_act, c_activities, 'name')
        c_name = best_c.get('name', '-') if best_c else '-'
        
        match_pct = f"{int(best_e_score*100)}%"
        out(f"  {i+1:<4} {str(g_name)[:50]:<50} {str(e_name)[:50]:<50} {match_pct:<7} {str(c_name)[:35]:<35}")
    
    out()
    out("  EXTRACTED ACTIVITIES NOT MATCHED TO GOLDEN:")
    for j, e_act in enumerate(e_activities):
        if j not in used_e:
            e_name = e_act.get('name', '-')
            out(f"  +{j+1:<3} {e_name}")
    
    # =========================================================================
    # 15. SOA ENCOUNTERS - Semantic matching
    # =========================================================================
    section_header("15. SOA ENCOUNTERS - SEMANTIC MATCHING")
    
    g_encounters = gd.get('encounters', [])
    c_encounters = combined.get('encounters', [])
    
    out(f"  {'#':<4} {'GOLDEN Encounter':<45} {'EXTRACTED Encounter (Best Match)':<45} {'Match%':<7} {'COMBINED':<35}")
    out("  " + "-" * 195)
    
    used_e = set()
    for i, g_enc in enumerate(g_encounters):
        g_name = g_enc.get('name', '-')
        # Find best match in extracted
        best_e_idx, best_e_score = -1, 0
        for j, e_enc in enumerate(e_encounters):
            if j not in used_e:
                score = similarity(g_name, e_enc.get('name', ''))
                if score > best_e_score:
                    best_e_score = score
                    best_e_idx = j
        if best_e_idx >= 0 and best_e_score > 0.3:
            used_e.add(best_e_idx)
            e_name = e_encounters[best_e_idx].get('name', '-')
        else:
            e_name = '-'
        # Find best combined match
        best_c, _ = find_best_match(g_enc, c_encounters, 'name')
        c_name = best_c.get('name', '-') if best_c else '-'
        
        match_pct = f"{int(best_e_score*100)}%"
        out(f"  {i+1:<4} {str(g_name)[:45]:<45} {str(e_name)[:45]:<45} {match_pct:<7} {str(c_name)[:35]:<35}")
    
    out()
    out("  EXTRACTED ENCOUNTERS NOT MATCHED TO GOLDEN:")
    for j, e_enc in enumerate(e_encounters):
        if j not in used_e:
            e_name = e_enc.get('name', '-')
            out(f"  +{j+1:<3} {e_name}")
    
    # =========================================================================
    # SUMMARY
    # =========================================================================
    section_header("SUMMARY")
    out()
    out(f"  {'Entity':<30} {'Golden':<10} {'Extracted':<12} {'Combined':<12} {'E Match':<10} {'C Match'}")
    out("  " + "-" * 100)
    
    g_ids = gv.get('studyIdentifiers', [])
    e_ids = meta.get('identifiers', [])
    c_ids = combined.get('studyIdentifiers', [])
    out(f"  {'Study Identifiers':<30} {len(g_ids):<10} {len(e_ids):<12} {len(c_ids):<12} {'✅' if len(e_ids) >= len(g_ids) else '❌':<10} {'✅' if len(c_ids) >= len(g_ids) else '❌'}")
    
    out(f"  {'Study Titles':<30} {len(g_titles):<10} {len(e_titles):<12} {len(c_titles):<12} {'✅' if len(e_titles) >= 2 else '❌':<10} {'✅' if len(c_titles) >= 2 else '❌'}")
    out(f"  {'Eligibility Criteria':<30} {len(g_criteria):<10} {len(e_criteria):<12} {len(c_criteria):<12} {'✅' if len(e_criteria) >= 25 else '❌':<10} {'✅' if len(c_criteria) >= 25 else '❌'}")
    out(f"  {'Objectives':<30} {len(g_objectives):<10} {len(e_objectives):<12} {len(c_objectives):<12} {'✅' if len(e_objectives) >= 8 else '❌':<10} {'✅' if len(c_objectives) >= 8 else '❌'}")
    out(f"  {'Endpoints':<30} {len(g_endpoints):<10} {len(e_endpoints):<12} {len(c_endpoints):<12} {'✅' if len(e_endpoints) >= 5 else '❌':<10} {'✅' if len(c_endpoints) >= 5 else '❌'}")
    out(f"  {'Study Arms':<30} {len(g_arms):<10} {len(e_arms):<12} {len(c_arms):<12} {'✅' if len(e_arms) >= 1 else '❌':<10} {'✅' if len(c_arms) >= 1 else '❌'}")
    out(f"  {'Epochs':<30} {len(g_epochs):<10} {len(e_epochs):<12} {len(c_epochs):<12} {'✅' if len(e_epochs) >= 2 else '❌':<10} {'✅' if len(c_epochs) >= 2 else '❌'}")
    out(f"  {'Amendments':<30} {len(g_amendments):<10} {len(e_amendments):<12} {len(c_amendments):<12} {'✅' if len(e_amendments) >= 3 else '❌':<10} {'✅' if len(c_amendments) >= 3 else '❌'}")
    out(f"  {'Procedures':<30} {len(g_procedures):<10} {len(e_procedures):<12} {len(c_procedures):<12} {'✅' if len(e_procedures) >= 5 else '❌':<10} {'✅' if len(c_procedures) >= 5 else '❌'}")
    out(f"  {'Analysis Populations':<30} {len(g_populations):<10} {len(e_populations):<12} {len(c_populations):<12} {'✅' if len(e_populations) >= 3 else '❌':<10} {'✅' if len(c_populations) >= 3 else '❌'}")
    out(f"  {'Abbreviations':<30} {len(g_abbrs):<10} {len(e_abbrs):<12} {len(c_abbrs):<12} {'✅' if len(e_abbrs) >= 5 else '❌':<10} {'✅' if len(c_abbrs) >= 5 else '❌'}")
    out(f"  {'Activities (SOA)':<30} {len(g_activities):<10} {len(e_activities):<12} {len(c_activities):<12} {'✅' if len(e_activities) >= 10 else '❌':<10} {'✅' if len(c_activities) >= 10 else '❌'}")
    out(f"  {'Encounters (SOA)':<30} {len(g_encounters):<10} {len(e_encounters):<12} {len(c_encounters):<12} {'✅' if len(e_encounters) >= 5 else '❌':<10} {'✅' if len(c_encounters) >= 5 else '❌'}")
    out()
    
    # Save report
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))
    out(f"📄 Report saved to: {REPORT_FILE}")


if __name__ == "__main__":
    compare_all()
