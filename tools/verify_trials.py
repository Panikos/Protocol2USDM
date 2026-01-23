#!/usr/bin/env python3
"""
Verify which trials have complete documentation (Protocol + SAP + Sites).
"""
import os
from pathlib import Path

trial_dir = Path(r"C:\Users\panik\Documents\GitHub\Protcol2USDMv3\input\trial")

complete = []
incomplete = []

for folder in sorted(trial_dir.iterdir()):
    if folder.is_dir():
        files = list(folder.iterdir())
        file_names = [f.name.lower() for f in files]

        has_protocol = any("protocol" in f for f in file_names)
        has_sap = any("sap" in f for f in file_names)
        has_sites = any("sites" in f for f in file_names)

        # Protocol_SAP combined file counts as both
        has_protocol_sap = any("protocol_sap" in f for f in file_names)
        if has_protocol_sap:
            has_protocol = has_sap = True

        status = {
            "folder": folder.name,
            "protocol": has_protocol,
            "sap": has_sap,
            "sites": has_sites,
            "files": [f.name for f in files]
        }

        if has_protocol and has_sap:
            complete.append(status)
        else:
            incomplete.append(status)

print("=" * 80)
print(f"COMPLETE TRIALS ({len(complete)} with Protocol + SAP):")
print("=" * 80)
for t in complete:
    print(f"  {t['folder']}")
    for f in t['files']:
        print(f"    - {f}")
    print()

print("\n" + "=" * 80)
print(f"INCOMPLETE TRIALS ({len(incomplete)} - missing Protocol or SAP):")
print("=" * 80)
for t in incomplete:
    missing = []
    if not t['protocol']:
        missing.append("Protocol")
    if not t['sap']:
        missing.append("SAP")
    print(f"  {t['folder']} - Missing: {', '.join(missing)}")

print(f"\n\nSUMMARY: {len(complete)} complete, {len(incomplete)} incomplete")
