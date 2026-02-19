#!/usr/bin/env python
"""Run full pipeline for all trials in input/trial directory."""

import argparse
import json
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

def run_trial(trial_dir: Path, version: str = "v800") -> dict:
    """Run the pipeline for a single trial."""
    protocol, sap, sites = find_trial_files(trial_dir)
    
    if not protocol:
        return {"trial": trial_dir.name, "status": "skipped", "reason": "No protocol PDF found"}
    
    output_dir = f"output/{trial_dir.name}_{version}"
    
    cmd = [
        sys.executable, "main_v3.py",
        str(protocol),
        "--complete",
        "--parallel",
        "--output-dir", output_dir
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
    print(f"Output:   {output_dir}")
    print(f"Command: {' '.join(cmd)}")
    print()
    
    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True
        )
        elapsed = time.time() - start_time
        
        # Print last portion of stdout
        if result.stdout:
            print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
        
        # Check for actual output as success indicator (exit code 1 is common
        # even on successful runs due to SoA success flag)
        usdm_path = Path(result.cwd if hasattr(result, 'cwd') else Path(__file__).parent.parent) / output_dir / "protocol_usdm.json"
        output_exists = usdm_path.exists()
        
        if result.returncode != 0 and not output_exists and result.stderr:
            print(f"\nSTDERR (last 2000 chars):\n{result.stderr[-2000:]}")
        
        status = "success" if output_exists else "failed"
        
        return {
            "trial": trial_dir.name,
            "status": status,
            "exit_code": result.returncode,
            "elapsed_seconds": round(elapsed, 1),
            "output_dir": output_dir,
            "error_tail": result.stderr[-500:] if not output_exists and result.stderr else None
        }
    except Exception as e:
        return {
            "trial": trial_dir.name,
            "status": "error",
            "error": str(e)
        }

def main():
    parser = argparse.ArgumentParser(description="Run pipeline for all trials")
    parser.add_argument("--version", default="v800", help="Version tag for output dirs (default: v800)")
    parser.add_argument("--resume", action="store_true", help="Skip trials that already have protocol_usdm.json")
    args = parser.parse_args()
    
    base_dir = Path(__file__).parent.parent
    input_dir = base_dir / "input" / "trial"
    
    if not input_dir.exists():
        print(f"Error: {input_dir} does not exist")
        sys.exit(1)
    
    trials = sorted([d for d in input_dir.iterdir() if d.is_dir()])
    print(f"Found {len(trials)} trials to process")
    if args.resume:
        print(f"Resume mode: will skip trials with existing output")
    
    results = []
    for i, trial_dir in enumerate(trials, 1):
        # Check if already completed (resume mode)
        if args.resume:
            out_path = base_dir / "output" / f"{trial_dir.name}_{args.version}" / "protocol_usdm.json"
            if out_path.exists():
                print(f"\n[{i}/{len(trials)}] SKIP {trial_dir.name} (already completed)")
                results.append({"trial": trial_dir.name, "status": "success", "elapsed_seconds": 0, "output_dir": str(out_path.parent.relative_to(base_dir)), "resumed": True})
                continue
        
        print(f"\n[{i}/{len(trials)}] Processing {trial_dir.name}...")
        result = run_trial(trial_dir, version=args.version)
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
                print(f"  - {r['trial']} (exit {r.get('exit_code','?')})")
                if r.get('error_tail'):
                    print(f"    {r['error_tail'][:200]}")
    
    # Save results JSON for tracking
    results_path = Path(__file__).parent.parent / "output" / "run_all_results.json"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(results, indent=2))
    print(f"\nResults saved to: {results_path}")

if __name__ == "__main__":
    main()
