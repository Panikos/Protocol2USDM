#!/usr/bin/env python
"""Run full pipeline for all trials in input/trial directory."""

import subprocess
import sys
from pathlib import Path
import time

def find_trial_files(trial_dir: Path) -> tuple[Path | None, Path | None, Path | None]:
    """Find protocol PDF, SAP PDF, and sites CSV for a trial."""
    protocol = None
    sap = None
    sites = None
    
    for f in trial_dir.iterdir():
        name_lower = f.name.lower()
        if f.suffix.lower() == '.pdf':
            if 'sap' in name_lower:
                sap = f
            elif 'protocol' in name_lower or not sap:
                # Prefer files with 'protocol' in name, otherwise use first PDF
                if 'protocol' in name_lower or protocol is None:
                    if 'sap' not in name_lower:
                        protocol = f
        elif f.suffix.lower() == '.csv' and 'site' in name_lower:
            sites = f
    
    # If no protocol found but we have PDFs, use the non-SAP one
    if protocol is None:
        for f in trial_dir.iterdir():
            if f.suffix.lower() == '.pdf' and 'sap' not in f.name.lower():
                protocol = f
                break
    
    return protocol, sap, sites

def run_trial(trial_dir: Path, model: str = "gemini-3-flash-preview") -> dict:
    """Run the pipeline for a single trial."""
    protocol, sap, sites = find_trial_files(trial_dir)
    
    if not protocol:
        return {"trial": trial_dir.name, "status": "skipped", "reason": "No protocol PDF found"}
    
    cmd = [
        sys.executable, "main_v2.py",
        str(protocol),
        "--complete",
        "--model", model
    ]
    
    if sap:
        cmd.extend(["--sap", str(sap)])
    if sites:
        cmd.extend(["--sites", str(sites)])
    
    print(f"\n{'='*60}")
    print(f"TRIAL: {trial_dir.name}")
    print(f"{'='*60}")
    print(f"Protocol: {protocol.name}")
    print(f"SAP: {sap.name if sap else 'None'}")
    print(f"Sites: {sites.name if sites else 'None'}")
    print(f"Command: {' '.join(cmd)}")
    print()
    
    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            cwd=Path(__file__).parent.parent,
            capture_output=False,
            text=True
        )
        elapsed = time.time() - start_time
        
        return {
            "trial": trial_dir.name,
            "status": "success" if result.returncode == 0 else "failed",
            "exit_code": result.returncode,
            "elapsed_seconds": round(elapsed, 1)
        }
    except Exception as e:
        return {
            "trial": trial_dir.name,
            "status": "error",
            "error": str(e)
        }

def main():
    input_dir = Path(__file__).parent.parent / "input" / "trial"
    
    if not input_dir.exists():
        print(f"Error: {input_dir} does not exist")
        sys.exit(1)
    
    trials = sorted([d for d in input_dir.iterdir() if d.is_dir()])
    print(f"Found {len(trials)} trials to process")
    
    results = []
    for i, trial_dir in enumerate(trials, 1):
        print(f"\n[{i}/{len(trials)}] Processing {trial_dir.name}...")
        result = run_trial(trial_dir)
        results.append(result)
        
        # Print summary after each trial
        status_icon = "✓" if result["status"] == "success" else "✗" if result["status"] == "failed" else "○"
        elapsed = result.get("elapsed_seconds", 0)
        print(f"\n{status_icon} {trial_dir.name}: {result['status']} ({elapsed}s)")
    
    # Final summary
    print(f"\n{'='*60}")
    print("FINAL SUMMARY")
    print(f"{'='*60}")
    
    success = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    errors = sum(1 for r in results if r["status"] == "error")
    
    print(f"Success: {success}/{len(trials)}")
    print(f"Failed:  {failed}")
    print(f"Skipped: {skipped}")
    print(f"Errors:  {errors}")
    
    if failed > 0:
        print("\nFailed trials:")
        for r in results:
            if r["status"] == "failed":
                print(f"  - {r['trial']}")

if __name__ == "__main__":
    main()
