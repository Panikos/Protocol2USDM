#!/usr/bin/env python
"""Compare two USDM extraction runs."""
import json
import sys

def count_all(data):
    """Count all entities in USDM output."""
    study = data.get('study', {})
    versions = study.get('versions', [{}])
    sv = versions[0] if versions else {}
    designs = sv.get('studyDesigns', [{}])
    sd = designs[0] if designs else {}
    
    counts = {
        # Study Version level
        'titles': len(sv.get('titles', [])),
        'organizations': len(sv.get('organizations', [])),
        'studyIdentifiers': len(sv.get('studyIdentifiers', [])),
        
        # Study Design level
        'epochs': len(sd.get('epochs', [])),
        'encounters': len(sd.get('encounters', [])),
        'activities': len(sd.get('activities', [])),
        'objectives': len(sd.get('objectives', [])),
        'estimands': len(sd.get('estimands', [])),
        'populations': len(sd.get('populations', [])),
        'arms': len(sd.get('arms', [])),
        'studyCells': len(sd.get('studyCells', [])),
        'timings': len(sd.get('timings', [])),
        'indications': len(sd.get('indications', [])),
        'studyInterventions': len(sd.get('studyInterventions', [])),
        'procedures': len(sd.get('procedures', [])),
        'studySites': len(sd.get('studySites', [])),
        'footnotes': len(sd.get('footnotes', [])),
        'biomedicalConcepts': len(sd.get('biomedicalConcepts', [])),
        'amendments': len(sd.get('amendments', [])),
    }
    
    # Population criteria
    pop = sd.get('population', {})
    if pop:
        counts['eligibilityCriteria'] = len(pop.get('criteria', []))
    else:
        counts['eligibilityCriteria'] = 0
    
    # Narrative content
    counts['narrativeContent'] = len(sv.get('narrativeContentItems', []))
    counts['abbreviations'] = len(sv.get('abbreviations', []))
    
    return counts

def main():
    old_path = 'output/NCT04573309_Wilsons_Protocol_20260123_090245/protocol_usdm.json'
    new_path = 'output/NCT04573309_Wilsons_Protocol_20260130_064146/protocol_usdm.json'
    
    with open(old_path, 'r') as f:
        old_data = json.load(f)
    with open(new_path, 'r') as f:
        new_data = json.load(f)
    
    old_counts = count_all(old_data)
    new_counts = count_all(new_data)
    
    print("=" * 70)
    print("COMPARISON: Previous Run (Jan 23) vs New Run (Jan 30, main_v3.py)")
    print("=" * 70)
    print(f"Previous: output/NCT04573309_Wilsons_Protocol_20260123_090245")
    print(f"New:      output/NCT04573309_Wilsons_Protocol_20260130_064146")
    print("=" * 70)
    print(f"{'Entity':<25} {'Previous':>10} {'New':>10} {'Diff':>10}")
    print("-" * 70)
    
    changes = []
    for key in sorted(old_counts.keys()):
        old_val = old_counts.get(key, 0)
        new_val = new_counts.get(key, 0)
        diff = new_val - old_val
        if diff > 0:
            diff_str = f"+{diff}"
            changes.append((key, old_val, new_val, diff))
        elif diff < 0:
            diff_str = str(diff)
            changes.append((key, old_val, new_val, diff))
        else:
            diff_str = "="
        print(f"{key:<25} {old_val:>10} {new_val:>10} {diff_str:>10}")
    
    print("=" * 70)
    if changes:
        print("\nSUMMARY OF CHANGES:")
        for key, old_val, new_val, diff in changes:
            direction = "increased" if diff > 0 else "decreased"
            print(f"  - {key}: {direction} from {old_val} to {new_val}")
    else:
        print("\nNo differences found - outputs are identical in entity counts.")

if __name__ == "__main__":
    main()
