"""
Generate code registry artifacts from USDM_CT.xlsx.

Outputs:
  1. core/reference_data/usdm_ct.json        — full codelist data for Python registry
  2. web-ui/lib/codelist.generated.json       — UI-ready dropdown data (alias-keyed)

Optionally verifies supplementary codelists against EVS_VERIFIED_CODES
(no network required — uses the curated mapping in code_verification.py).

Usage:
    python scripts/generate_code_registry.py              # generate + verify
    python scripts/generate_code_registry.py --skip-verify  # generate only
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

XLSX_PATH = PROJECT_ROOT / "core" / "reference_data" / "USDM_CT.xlsx"
JSON_PATH = PROJECT_ROOT / "core" / "reference_data" / "usdm_ct.json"
UI_JSON_PATH = PROJECT_ROOT / "web-ui" / "lib" / "codelist.generated.json"


def parse_xlsx() -> dict:
    """Parse USDM_CT.xlsx → codelist dict."""
    try:
        import openpyxl
    except ImportError:
        sys.exit("openpyxl is required: pip install openpyxl")

    wb = openpyxl.load_workbook(str(XLSX_PATH), read_only=True)
    ws = wb["DDF valid value sets"]

    codelists: dict = {}
    for row in ws.iter_rows(min_row=7, values_only=True):
        entity = row[1]
        attr = row[2]
        cl_code = row[3]
        ext = row[4]
        code = row[5]
        decode = row[6]
        synonyms = row[7] if len(row) > 7 else None
        definition = row[8] if len(row) > 8 else None

        if not entity or not code:
            continue

        key = f"{entity}.{attr}"
        if key not in codelists:
            codelists[key] = {
                "codelistCode": cl_code,
                "entity": entity,
                "attribute": attr,
                "extensible": str(ext).strip().lower() == "yes",
                "terms": [],
            }
        codelists[key]["terms"].append({
            "code": code,
            "decode": decode,
            "synonyms": synonyms if synonyms else None,
            "definition": str(definition) if definition else None,
        })

    wb.close()
    return codelists


def generate_ui_json() -> None:
    """Generate the UI-ready JSON by loading the full registry."""
    from core.code_registry import CodeRegistry

    reg = CodeRegistry()
    ui_data = reg.export_for_ui()

    UI_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(UI_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(ui_data, f, indent=2, ensure_ascii=False)
    print(f"  → {UI_JSON_PATH.relative_to(PROJECT_ROOT)} ({len(ui_data)} keys)")


def main() -> None:
    print("=== Code Registry Generator ===\n")

    # Step 1: xlsx → JSON
    if not XLSX_PATH.exists():
        sys.exit(f"USDM_CT.xlsx not found at {XLSX_PATH}")

    codelists = parse_xlsx()
    total_terms = sum(len(v["terms"]) for v in codelists.values())
    print(f"Parsed {len(codelists)} codelists, {total_terms} terms from USDM_CT.xlsx")

    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(codelists, f, indent=2, ensure_ascii=False)
    print(f"  → {JSON_PATH.relative_to(PROJECT_ROOT)}")

    # Step 2: Generate UI JSON (includes supplementary codelists)
    generate_ui_json()

    # Step 3: Verify supplementary codelists against EVS_VERIFIED_CODES
    if "--skip-verify" not in sys.argv:
        verify_supplementary()
    else:
        print("\n  (verification skipped)")

    print("\nDone.")


def verify_supplementary() -> None:
    """Verify supplementary codelist codes against EVS_VERIFIED_CODES."""
    from core.code_verification import CodeVerificationService, EVS_VERIFIED_CODES

    print("\n--- Supplementary Code Verification ---")

    svc = CodeVerificationService()
    failed = 0

    for key in EVS_VERIFIED_CODES:
        report = svc.verify_codelist(key)
        if report.passed:
            print(f"  [PASS] {key} ({report.ok_count} codes)")
        else:
            print(f"  [FAIL] {key}")
            for r in report.results:
                if r.status != "OK":
                    print(f"         [{r.status}] {r.code}: {r.detail}")
            failed += report.mismatch_count + report.not_found_count

    if failed:
        print(f"\n  ⚠ {failed} code(s) failed verification — review core/code_verification.py")
    else:
        print("\n  All supplementary codes verified ✓")


if __name__ == "__main__":
    main()
