---
description: Run schema, USDM, and CDISC CORE conformance validation on a USDM JSON output
---

## Steps

1. Identify the USDM JSON file to validate. Examples:
   - Pipeline output: `output/<protocol_id>/protocol_usdm.json`
   - Test data: `semantic/NCT04573309_Wilsons_Protocol_20260207_110101/history/protocol_usdm_2026-02-07T2152Z.json`

2. Run USDM schema validation:
// turbo
```
python -c "import json; from validation.usdm_validator import validate_usdm; r = validate_usdm(json.load(open(r'<path_to_usdm_json>'))); print(f'Valid: {r.get(\"valid\")}'); print(f'Errors: {len(r.get(\"errors\", []))}'); [print(f'  - {e}') for e in r.get('errors', [])[:10]]"
```

3. Run M11 conformance validation:
// turbo
```
python -c "import json; from validation.m11_conformance import validate_m11_conformance; usdm = json.load(open(r'<path_to_usdm_json>')); r = validate_m11_conformance(usdm); print(f'Score: {r.get(\"overall_score\", \"N/A\")}'); print(f'Errors: {len(r.get(\"errors\", []))}'); print(f'Warnings: {len(r.get(\"warnings\", []))}'); [print(f'  ERROR: {e}') for e in r.get('errors', [])[:10]]"
```

4. Run CDISC CORE conformance (requires rules engine):
```
python -c "from pathlib import Path; from validation.cdisc_conformance import run_cdisc_conformance; usdm = Path(r'<path_to_usdm_json>'); out_dir = usdm.parent; r = run_cdisc_conformance(str(usdm), str(out_dir)); print(f'Success: {r.get(\"success\")}'); print(f'Errors: {r.get(\"issues\", 0)}'); print(f'Warnings: {r.get(\"warnings\", 0)}'); [print(f'  - {i.get(\"rule\") or i.get(\"core_id\")}: {i.get(\"message\")}') for i in r.get('issues_list', [])[:10]]"
```

   Optional timeout override for large protocols:
```
set CDISC_CORE_TIMEOUT_SECONDS=300
```

5. Review results:
   - **Schema errors**: Fix entity structure in the relevant extraction combiner
   - **M11 conformance errors**: Check which M11 sections/fields are missing data
   - **CDISC CORE issues**: Check controlled terminology codes and entity relationships
   - If CORE reports timeout, retry with a higher `CDISC_CORE_TIMEOUT_SECONDS` value

6. Common fixes:
   - Missing `instanceType` → add in combiner
   - Missing required fields → check extractor prompts and parsing
   - Invalid code values → check CDISC CT codelist in `usdm-cdisc-codes.md`
