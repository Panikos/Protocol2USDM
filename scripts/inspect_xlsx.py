"""Inspect USDM_CT.xlsx structure for CodeRegistry design."""
import openpyxl
import json

wb = openpyxl.load_workbook("core/reference_data/USDM_CT.xlsx")
ws = wb["DDF valid value sets"]

codelists = {}
for row in ws.iter_rows(min_row=7, values_only=True):
    entity, attr, cl_code, ext, code, decode, synonyms, definition = (
        row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8]
    )
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
        "synonyms": synonyms,
        "definition": str(definition)[:80] if definition else None,
    })

total_terms = sum(len(v["terms"]) for v in codelists.values())
print(f"Found {len(codelists)} codelists, {total_terms} total terms\n")
for k, v in sorted(codelists.items()):
    ext_str = "ext" if v["extensible"] else "fixed"
    print(f"  {k}: {v['codelistCode']} ({len(v['terms'])} terms, {ext_str})")

# Write JSON for the registry generator
with open("core/reference_data/usdm_ct.json", "w", encoding="utf-8") as f:
    json.dump(codelists, f, indent=2, ensure_ascii=False)
print(f"\nWrote core/reference_data/usdm_ct.json")
