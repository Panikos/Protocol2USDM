---
name: review-digital-protocol
description: Deep expertise in reviewing the quality of a digital clinical protocol (USDM JSON) against its source documents (Protocol PDF, SAP PDF) via the claude-mediator MCP server. Covers CDISC USDM v4.0 conformance, completeness, referential integrity, and adherence to source documentation.
---

# Review Digital Protocol Skill

This skill drives an **iterative quality improvement loop**: run the pipeline → review the output → categorize findings → implement fixes → re-run → re-review. It uses the `claude-mediator` MCP server as a second-opinion reviewer comparing extracted USDM JSON against source PDFs.

## When to Use

- **Initial review**: After running the extraction pipeline on a new protocol
- **Iteration review**: After implementing fixes from a previous review cycle
- **Regression check**: After pipeline code changes to verify no quality degradation
- **Cross-protocol validation**: Running the same review on multiple protocols to find systemic pipeline issues vs protocol-specific gaps
- When the user says "review quality", "check extraction", "compare to source", "iterate", or similar

## The Iterative Improvement Loop

```
┌─────────────────────────────────────────────────────────┐
│  1. RUN PIPELINE (/run-pipeline)                        │
│     python main_v3.py <pdf> --complete --parallel        │
│     Output: output/<trial_id>_<timestamp>/               │
├─────────────────────────────────────────────────────────┤
│  2. REVIEW (/review-protocol-quality)                    │
│     Session 1: JSON + Protocol PDF → full review         │
│     Session 2: JSON + SAP PDF → SAP review               │
│     Output: quality_review.md                            │
├─────────────────────────────────────────────────────────┤
│  3. TRIAGE FINDINGS                                      │
│     Classify: pipeline-generic vs protocol-specific      │
│     Classify: prompt issue vs code issue vs schema gap   │
│     Prioritize: CRITICAL → HIGH → MEDIUM → LOW           │
│     Check against known false positives (see below)      │
├─────────────────────────────────────────────────────────┤
│  4. IMPLEMENT FIXES                                      │
│     Modify: prompts.py / extractor.py / schema.py /      │
│             combiner.py / post_processing.py             │
│     Add regression tests for each fix                    │
│     Run: pytest tests/ to verify no breakage             │
├─────────────────────────────────────────────────────────┤
│  5. RE-RUN & DELTA REVIEW                                │
│     Re-run pipeline on same protocol                     │
│     Use delta review prompt to compare old vs new        │
│     Track: findings resolved, new findings, regressions  │
│     Update quality_review.md with iteration history      │
└────────────────────────── loop ─────────────────────────┘
```

## Prerequisites

1. **MCP mediator running** — `claude-cli-stream` backend available
2. **Pipeline output** directory containing `protocol_usdm.json`
3. **Source documents**: Protocol PDF and optionally SAP PDF in `input/trial/<trial_id>/`

## File Discovery

| File | Location Pattern |
|------|-----------------|
| USDM JSON | `output/<trial_id>_<timestamp>/protocol_usdm.json` |
| Protocol PDF | `input/trial/<trial_id>/<trial_id>_Protocol.pdf` |
| SAP PDF | `input/trial/<trial_id>/<trial_id>_SAP.pdf` |
| Previous review | `output/<trial_id>_<prev_timestamp>/quality_review.md` |

If the user doesn't specify which output, find the latest:
```
find_by_name in output/ for protocol_usdm.json, pick most recent by timestamp
```

## Cost Awareness

### Actual Cost Breakdown (Wilson Review, Session 1)

The first review used **claude-opus-4-6** via API fallback with 3-chunk map-reduce:

| Step | Input Tokens | Output Tokens | Est. Cost (Opus) |
|------|-------------|--------------|-----------------|
| JSON intake (chunk 1) | 26K | 8K | $1.00 |
| JSON intake (chunk 2) | 164K | 4K | $2.76 |
| JSON intake (chunk 3) | 43K | 4K | $0.95 |
| PDF intake | ~30K | 4K | $0.75 |
| Full review | ~180K | 16K | $3.90 |
| Continuation | ~180K | 16K | $3.90 |
| **Session 1 total** | **~623K** | **~52K** | **~$13.30** |

Session 2 (SAP) would add another ~$8-10. **Full review ≈ $20-25 on Opus.**

### Cost Reduction Strategies

The full USDM JSON must always be submitted as-is — the reviewer needs the actual data to give accurate feedback.

| Strategy | Savings | How |
|----------|---------|-----|
| **Use Sonnet** instead of Opus | **~90%** cost reduction | Set `model: "sonnet"` in mediator config or use `model` param |
| **Use `minify: "json"`** param | **~40-50%** on JSON whitespace | Pass `minify="json"` to `mcp0_query_with_session` — always use this |
| **Combine PDF intake + review** into 1 message | **~30%** fewer turns | Send PDF with review prompt attached (saves a full context re-read) |
| **Skip SAP session** for iterations | **~40%** total | SAP doesn't change between pipeline runs |
| **JSON-only regression** for quick checks | **~60%** total | No PDF needed for structural/conformance checks |
| **Zip for small protocols** | **Saves 1 turn** | Zip JSON + PDF if combined tokens < 200K (~50-page protocols) |

### Multi-File and Zip Considerations

- The mediator **supports zip files** — it unpacks them and sends each file to Claude.
- You can also **send multiple files in one message** via the `files` array parameter.
- **However**, Claude's context window is 200K tokens. A typical protocol PDF (~70+ pages) consumes ~180K tokens alone.
  Combined with the full JSON (~150K tokens via map-reduce), they cannot fit in a single message.
- **For small protocols** (<50 pages): zip the JSON + PDF and send in one message to save a turn.
- **For large protocols**: 2 messages minimum — JSON first (chunked via map-reduce), then PDF + review prompt.
- Always pass `minify="json"` when sending JSON files to strip whitespace.

### Review Tiers

Choose the tier that matches your goal. All tiers submit the **full USDM JSON**.

| Tier | When | Files Sent | Model | Messages | Est. Cost |
|------|------|-----------|-------|----------|-----------|
| **Tier 1: Quick Regression** | After code changes, structural check | Full JSON only | Sonnet | 1-2 | ~$0.50 |
| **Tier 2: Delta Review** | After fixes, with previous findings | Full JSON + PDF | Sonnet | 2-3 | ~$1-2 |
| **Tier 3: Full Review** | Initial review of new protocol | Full JSON + PDF | Sonnet | 2-3 | ~$2-3 |
| **Tier 4: Deep Review** | Production quality gate | Full JSON + PDF + SAP | Opus | 4-6 | ~$20-25 |

**Default to Tier 1 for iterations** (JSON-only, no PDF, checks conformance + integrity).
Use Tier 2 for delta review after significant fixes. Only Tier 4 for final quality gate.

## Review Process

### Phase 1: Ensure MCP Connectivity

1. Check backend status: `mcp0_get_service_status(backend="claude-cli-stream")`
2. If stopped: `mcp0_start_backend(backend="claude-cli-stream", clearSession=true)`
3. Verify with a ping: `mcp0_query(query="Hello, are you live?")`
4. If "Session not found": ask user to **Ctrl+Shift+P → Developer: Reload Window**

### Phase 2: Session 1 — Protocol Review

**Tier 1 (Quick Regression)** — JSON only, no PDF:
```
Step 1: mcp0_query_with_session(sessionId="<trial>-regcheck", query=JSON_INTAKE, files=[json], minify="json")
Step 2: mcp0_query_with_session(sessionId="<trial>-regcheck", query=QUICK_REGRESSION_PROMPT)
```

**Tier 2-3 (Delta / Full Review)** — JSON + PDF:
```
Step 1: mcp0_query_with_session(sessionId="<trial>-review-1", query=JSON_INTAKE, files=[json], minify="json")
Step 2: mcp0_query_with_session(sessionId="<trial>-review-1", query=PDF_INTAKE + REVIEW_PROMPT, files=[pdf])
Step 3: mcp0_query_with_session(sessionId="<trial>-review-1", query=CONTINUE)  ← only if truncated
```

**Note**: Always use `minify="json"` on JSON. Combine PDF intake + review prompt into 1 message to save a turn.

### Phase 3: Session 2 — SAP Review (Tier 4 only)

Same pattern with `sessionId="<trial>-review-2"` and SAP-specific prompts.
Only run for Tier 4 (deep review). SAP doesn't change between pipeline iterations.

### Phase 4: Triage & Categorize

For each finding from the reviewer, classify it:

| Classification | Meaning | Action |
|---------------|---------|--------|
| **Pipeline-generic** | Would affect any protocol (e.g., epoch type over-application) | Fix in pipeline code; add regression test |
| **Protocol-specific** | Only affects this protocol (e.g., specific objective missed) | May indicate prompt needs broadening |
| **Prompt issue** | LLM didn't extract the data despite it being in the PDF | Improve extraction prompt with examples |
| **Parser/mapper issue** | LLM extracted data but parser dropped or miscoded it | Fix extractor.py or schema.py |
| **Combiner/post-processing issue** | Data extracted but lost during assembly | Fix combiner.py, post_processing.py, promotion.py |
| **Schema gap** | USDM v4.0 has no native entity for this data | Use extension attributes or accept as limitation |
| **Known false positive** | Reviewer flagged something incorrectly (see below) | Ignore; note in known-false-positives.md |

### Phase 5: Implement Fixes

For each actionable finding:
1. **Read the relevant file** (see `review-criteria.md` § 7 for phase→file mapping)
2. **Determine fix type**: prompt change, parser logic, schema field, combiner wiring
3. **Implement the minimal fix** — prefer upstream fixes over downstream workarounds
4. **Add a regression test** in `tests/` that would catch the issue if it recurred
5. **Run `pytest tests/`** to verify no breakage

### Phase 6: Delta Review (Re-run Cycle)

After fixes, re-run the pipeline and use the **delta review prompt** (see `review-prompts.md`):
1. Re-run pipeline: `python main_v3.py <pdf> --complete --parallel`
2. Send new JSON + PDF to a fresh session
3. Include the previous review's top findings in the prompt
4. Ask reviewer to confirm which findings are resolved, which persist, any new regressions
5. Update `quality_review.md` with iteration history section

### Phase 7: Cross-Protocol Validation

After fixing pipeline-generic issues, validate on multiple protocols:
1. Run pipeline on 2-3 different protocols (different phases, designs, therapeutic areas)
2. Review each output — systemic issues should be resolved across all
3. Protocol-specific gaps are expected and acceptable

## Known False Positives

The reviewer may flag these — they are expected behaviors, not bugs:

| Finding | Why It's Expected | Pipeline Phase |
|---------|------------------|----------------|
| **Study sites appear hallucinated** | Sites come from the `sites` conditional phase which extracts from a separate sites CSV/file, not the protocol PDF | sites |
| **Age upper limit 99** | Convention for "no upper limit" — standard in CDISC submissions | eligibility |
| **Extension attributes not prefixed ext_** | Our extensions use USDM ExtensionAttribute entities with `name` field; the `ext_` prefix applies to inline JSON keys | combiner |
| **Narrative text duplication** | Narrative phase maps protocol sections to M11 sections; some protocol sections span multiple M11 sections, causing intentional content sharing | narrative |
| **Adaptive/sequential design characteristics** | Extracted from protocol text; may be "borderline" but defensible | studydesign |
| **_temp_ prefixed entities** | Pipeline staging data that should be cleaned up in post-processing; flag as MEDIUM, not CRITICAL | post_processing |

## Tracking Progress Across Iterations

Each `quality_review.md` should have an **Iteration History** section:

```markdown
## Iteration History

| Iteration | Date | Pipeline Run | Score | CRIT | HIGH | MED | LOW | Key Changes |
|-----------|------|-------------|-------|------|------|-----|-----|-------------|
| 1 | 2026-02-16 | 20260213_233110 | 7.3/10 | 5 | 19 | 19 | 10 | Baseline |
| 2 | 2026-02-17 | 20260217_... | ?/10 | ? | ? | ? | ? | Fixed: UUID collision, safety codes, missing objectives |
```

## Multi-Protocol Comparison

When reviewing multiple protocols, track common findings:

```markdown
## Cross-Protocol Findings

| Finding | Wilson | SURPASS-4 | ADAURA | Generic? | Fix Priority |
|---------|--------|----------|--------|----------|-------------|
| Epoch type over-application | ✅ | ? | ? | Likely | HIGH |
| Safety obj miscoded | ✅ | ? | ? | Likely | HIGH |
| Missing exploratory objectives | ✅ | ? | ? | Maybe | MEDIUM |
```

See `review-criteria.md` for the full checklist and `review-prompts.md` for exact MCP prompts.
