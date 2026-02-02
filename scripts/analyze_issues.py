#!/usr/bin/env python3
"""Analyze processing issues across all generated protocols."""

import json
from pathlib import Path
from collections import defaultdict

def main():
    output_dir = Path("output")
    
    # Collectors
    llm_failures = []
    visit_failures = defaultdict(set)
    epoch_failures = defaultdict(set)
    dosing_issues = defaultdict(set)
    route_issues = defaultdict(set)
    
    # Scan all 20260120 outputs
    for d in sorted(output_dir.glob("*_20260120*")):
        proc_file = d / "processing_report.json"
        if not proc_file.exists():
            continue
            
        try:
            data = json.load(open(proc_file))
            trial = d.name.split("_Protocol")[0]
            
            for issue in data.get("processing_issues", []):
                msg = issue.get("message", "")
                details = issue.get("details", {})
                
                if "LLM" in msg and "failed" in msg:
                    error = details.get("error", msg)
                    llm_failures.append((trial, error[:100]))
                    
                if "Could not resolve visit" in msg:
                    visit = details.get("visit_name", "Unknown")
                    visit_failures[visit].add(trial)
                    
                if "Could not resolve epoch" in msg:
                    epoch = details.get("epoch_name", "Unknown")
                    epoch_failures[epoch].add(trial)
                    
                if "Dosing frequency not extracted" in msg:
                    treatment = details.get("treatment", "Unknown")
                    dosing_issues[treatment].add(trial)
                    
                if "Route of administration not extracted" in msg:
                    treatment = details.get("treatment", "Unknown")
                    route_issues[treatment].add(trial)
                    
        except Exception as e:
            print(f"Error processing {d.name}: {e}")
    
    print("=" * 60)
    print("PROTOCOL EXTRACTION ISSUE ANALYSIS")
    print("=" * 60)
    
    print("\n### LLM EXTRACTION FAILURES ###")
    for trial, error in llm_failures:
        print(f"  {trial}: {error}")
    
    print(f"\n### VISIT RESOLUTION FAILURES ({len(visit_failures)} unique visits) ###")
    for visit, trials in sorted(visit_failures.items(), key=lambda x: -len(x[1]))[:15]:
        print(f"  \"{visit}\": {len(trials)} trials")
    
    print(f"\n### EPOCH RESOLUTION FAILURES ({len(epoch_failures)} unique epochs) ###")
    for epoch, trials in sorted(epoch_failures.items(), key=lambda x: -len(x[1])):
        print(f"  \"{epoch}\": {len(trials)} trials - {list(trials)[:3]}")
    
    print(f"\n### MISSING DOSING FREQUENCY ({len(dosing_issues)} treatments) ###")
    for treatment, trials in sorted(dosing_issues.items(), key=lambda x: -len(x[1]))[:10]:
        print(f"  \"{treatment}\": {len(trials)} trials")
    
    print(f"\n### MISSING ROUTE OF ADMINISTRATION ({len(route_issues)} treatments) ###")
    for treatment, trials in sorted(route_issues.items(), key=lambda x: -len(x[1]))[:10]:
        print(f"  \"{treatment}\": {len(trials)} trials")

if __name__ == "__main__":
    main()
