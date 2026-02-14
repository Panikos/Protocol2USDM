---
description: Run the full extraction pipeline on a protocol PDF and verify output
auto_execution_mode: 3
---

## Steps

1. Confirm the input PDF path exists. Default location: `input/trial/NCT<id>/` or `input/`.

2. Run the pipeline (do NOT pass --model unless the user explicitly requests it):
```
python main_v3.py <path_to_pdf> --complete --parallel --output-dir output/<protocol_id>
```
   Add `--sap <sap_pdf>` and/or `--sites <sites_csv>` if available.

3. Check the output directory for:
   - `protocol_usdm.json` — the USDM v4.0 JSON
   - `m11_protocol.docx` — the M11-formatted DOCX
   - `m11_conformance_report.json` — conformance validation results
   - `run_manifest.json` — pipeline run metadata

4. Review conformance report:
```
python -c "import json; r = json.load(open('output/<protocol_id>/m11_conformance_report.json')); print(f'Score: {r.get(\"overall_score\", \"N/A\")}'); print(f'Errors: {len(r.get(\"errors\", []))}'); print(f'Warnings: {len(r.get(\"warnings\", []))}')"
```

5. If errors exist, check:
   - Missing extraction phases (check `run_manifest.json` for which phases ran)
   - LLM failures (check console output for warnings)
   - Schema validation issues (run `/validate-usdm` workflow)
