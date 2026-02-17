---
description: Review digital protocol quality by sending USDM JSON + source PDFs to claude-mediator for CDISC conformance, completeness, referential integrity, and source adherence review
---

## Steps

1. Invoke the `review-digital-protocol` skill for detailed knowledge.

2. Identify the files to review. If the user doesn't specify, find the latest output:
   - USDM JSON: `output/<latest_dir>/protocol_usdm.json`
   - Protocol PDF: `input/trial/<trial_id>/<trial_id>_Protocol.pdf`
   - SAP PDF (optional): `input/trial/<trial_id>/<trial_id>_SAP.pdf`
   - Previous review (if iterating): `output/<prev_dir>/quality_review.md`

3. Determine review tier (see skill doc for cost breakdown). Full USDM JSON is always submitted as-is.
   - **Tier 1 — Quick Regression** (~$0.50): After code changes. Full JSON only, no PDF. Sonnet. 1-2 messages.
   - **Tier 2 — Delta Review** (~$1-2): After fixes. Full JSON + PDF. Sonnet. 2-3 messages.
   - **Tier 3 — Full Review** (~$2-3): Initial review of new protocol. Full JSON + PDF. Sonnet. 2-3 messages.
   - **Tier 4 — Deep Review** (~$20-25): Production quality gate. Full JSON + PDF + SAP. Opus. 4-6 messages.
   Default to **Tier 1** for iterations. Use Tier 3 for first review. Only Tier 4 for final gate.

4. Verify MCP mediator connectivity:
// turbo
```
mcp0_get_service_status(backend="claude-cli-stream")
```
   If stopped, start it with `mcp0_start_backend(backend="claude-cli-stream", clearSession=true)`.
   If "Session not found", ask user to reload Windsurf (Ctrl+Shift+P → Developer: Reload Window).

5. **Session 1 — Protocol Review** (varies by tier):
   - **Tier 1**: 1-2 messages — send full JSON with `minify="json"`, then quick regression prompt.
   - **Tier 2-3**: 2-3 messages — send full JSON with `minify="json"`, then PDF + review prompt combined.
   - **Tier 4**: Same as Tier 3 but use Opus model.
   Always use `minify="json"` on JSON files.
   If response is truncated, send the Continuation Prompt in the same session.

6. Save Session 1 findings (read full output from temp file if truncated).

7. **Session 2 — SAP Review** (Tier 4 only, skip for iterations):
   Send USDM JSON first with `minify="json"`, then SAP PDF + SAP review prompt combined.
   Use `mcp0_query_with_session` with `sessionId="<trial_id>-review-2"`.

8. Save Session 2 findings.

9. Consolidate all findings into `output/<latest_dir>/quality_review.md` with:
   - Summary table (CRITICAL/HIGH/MEDIUM/LOW counts)
   - Quality scores by dimension (Conformance, Completeness, Integrity, Fidelity, M11, Overall)
   - Detailed findings grouped by review category
   - Hallucination check results
   - Extraction gap check results
   - Action items mapped to pipeline phases and files (use `review-criteria.md §7`)
   - Iteration History table (if delta review)
   - Known false positives noted (see skill doc)

10. Triage findings per the skill's Phase 4 (pipeline-generic vs protocol-specific, prompt vs code vs schema).

11. Optionally run local validation to cross-check:
// turbo
```
python -c "import json; from validation.usdm_validator import validate_usdm; r = validate_usdm(json.load(open(r'<path_to_usdm_json>'))); print(f'Valid: {r.get(\"valid\")}'); print(f'Errors: {len(r.get(\"errors\", []))}'); [print(f'  - {e}') for e in r.get('errors', [])[:10]]"
```

12. Present findings to user and ask: **implement fixes now** (start the improvement loop) or **save for later**?
    - If implementing: follow the skill's Phase 5 fix patterns from `review-criteria.md §8`
    - After fixes: re-run pipeline (`/run-pipeline`) and repeat from step 1 as delta review
