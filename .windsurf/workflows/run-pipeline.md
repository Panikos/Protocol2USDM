---
description: Run the full extraction pipeline on a protocol PDF and verify output
auto_execution_mode: 3
---

## Steps

// turbo
1. Print the current project version and timestamp:
```
python -c "from core.constants import VERSION; from datetime import datetime; ts=datetime.now().strftime('%Y-%m-%d %H:%M:%S'); print(f'Protocol2USDM v{VERSION} -- {ts}')"
```

2. Confirm the input PDF path exists. Default location: `input/trial/NCT<id>/` or `input/`.

3. Run the pipeline (do NOT pass --model unless the user explicitly requests it). Use the version from step 1 in the output dir name (e.g. `v717`):
```
python main_v3.py <path_to_pdf> --complete --parallel --output-dir output/<protocol_id>_v<version>
```
   Add `--sap <sap_pdf>` and/or `--sites <sites_csv>` if available.

4. Check the output directory for:
   - `protocol_usdm.json` — the USDM v4.0 JSON
   - `m11_protocol.docx` — the M11-formatted DOCX
   - `m11_conformance_report.json` — conformance validation results
   - `run_manifest.json` — pipeline run metadata

5. Review conformance report:
```
python -c "import json,sys; r=json.load(open(sys.argv[1])); print('Score:',r.get('overall_score','N/A')); print('Errors:',len(r.get('errors',[]))); print('Warnings:',len(r.get('warnings',[])))" output/<protocol_id>/m11_conformance_report.json
```

6. If errors exist, check:
   - Missing extraction phases (check `run_manifest.json` for which phases ran)
   - LLM failures (check console output for warnings)
   - Schema validation issues (run `/validate-usdm` workflow)
