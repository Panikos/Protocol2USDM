# Hallucination Risk Audit

**Date**: 2026-02-21  
**Scope**: Full pipeline audit for LLM/code-level data fabrication  
**Context**: Discovered that the estimands extractor was fabricating ICH E9(R1) estimands and intercurrent events for exploratory studies that had no estimand framework.

---

## Summary

| # | Location | What's fabricated | Risk | Status |
|---|----------|------------------|------|--------|
| **1** | `pipeline/integrations.py` — `_create_populations_from_estimands()` | Boilerplate population definitions | HIGH | **FIXED** |
| **2** | `extraction/conditional/ars_generator.py` — default operations | P-value operation for unknown methods | MEDIUM | **FIXED** |
| **3** | `pipeline/promotion.py` — `_infer_sex_from_criteria()` / `_infer_age_from_criteria()` | Inferred from criteria regex | Low | Acceptable — logged, sourced from real text |
| **4** | `pipeline/post_processing.py` — `_fix_empty_amendment_changes()` | Placeholder StudyChange | Low | Acceptable — USDM schema compliance |
| **5** | `extraction/objectives/prompts.py` — `ESTIMANDS_PROMPT` | Fabricated estimands + ICEs | HIGH | **FIXED** (session 2026-02-21) |

---

## 1. Boilerplate Analysis Population Definitions

**File**: `pipeline/integrations.py:98` — `_create_populations_from_estimands()`

**Problem**: When the SAP phase doesn't run (no separate SAP PDF), this function manufactures `AnalysisPopulation` entities using hardcoded boilerplate text. For example, it generates:

> "All randomized participants who received at least one dose of study intervention, analyzed according to randomized treatment assignment."

...even for single-arm studies that don't use randomization.

**Compounding factor**: If a model still fabricates estimands (e.g., using an older prompt), this function cascades the hallucination by creating populations from those fabricated estimand references.

**Impact**: A biostatistician sees population definitions that look authoritative but don't match the actual protocol. The Wilson's study (single-arm, open-label, ~10 participants) would get a boilerplate ITT definition mentioning "randomized treatment assignment."

**Fix** (two layers):
1. **Analysis approach gating**: `reconcile_estimand_population_refs()` now reads the `x-analysisApproach` extension attribute (set by the objectives extractor during Phase 2 classification). If the study is classified as `"descriptive"`, the entire population fallback is skipped — no populations are inferred from estimand references for studies that shouldn't have estimands in the first place. This leverages the analysis approach classification built in Fix #5.
2. **No boilerplate text**: When the fallback does fire (confirmatory studies without a SAP), populations use the estimand's own `analysisPopulation` text (extracted from actual protocol language by the LLM), not hardcoded boilerplate. The auto-addition of a Safety population was also removed.

---

## 2. ARS Default P-value Operations

**File**: `extraction/conditional/ars_generator.py:498-502` — `_get_operations_for_method()`

**Problem**: When a statistical method doesn't match any known STATO pattern, the ARS generator creates default operations including a "P-value" operation. This is incorrect for descriptive studies — descriptive statistics (mean, median, SD) don't produce p-values.

**Impact**: A statistician reviewing the ARS output sees a p-value operation attached to what should be a descriptive summary. This undermines trust in the tool's scientific accuracy.

**Fix**: Default operations now produce only a generic "Result" operation. P-value is no longer assumed as a default — it's only included when the method is explicitly matched to an inferential statistical test (ANCOVA, t-test, chi-square, etc.).

---

## 3. Sex/Age Inference from Criteria (Acceptable)

**File**: `pipeline/promotion.py:155,187`

**Problem**: `_infer_sex_from_criteria()` and `_infer_age_from_criteria()` scan eligibility criteria text with regex to populate `plannedSex` / `plannedAge` on the population entity.

**Why acceptable**: 
- Sources from actual protocol text (eligibility criteria), not boilerplate
- Uses conservative regex patterns
- Already logged as "Inferred" in output
- Fills USDM required fields that would otherwise be empty

**No action needed.**

---

## 4. Amendment Placeholder Changes (Acceptable)

**File**: `pipeline/post_processing.py:2774`

**Problem**: CORE-000938 compliance fix creates a placeholder `StudyChange` when an amendment has an empty `changes[]` list. Uses `sectionNumber: "N/A"` and sources text from the amendment's own summary.

**Why acceptable**:
- USDM schema requires ≥1 change per amendment (mandatory cardinality)
- Placeholder text comes from the amendment's own extracted summary
- This is structural compliance, not clinical data fabrication

**No action needed.**

---

## 5. Estimand Fabrication (FIXED)

**File**: `extraction/objectives/prompts.py` — `ESTIMANDS_PROMPT`

**Problem**: The prompt instructed the LLM to:
- "Extract at least one estimand for each primary endpoint" (Rule 6)
- "Include common intercurrent events (discontinuation, rescue medication) even if not explicit" (Rule 7)

Additionally, `_parse_estimands()` manufactured a default "Treatment discontinuation" ICE when none were found, and `Estimand.to_dict()` did the same in the output.

**Fix applied**:
- Rewrote prompt to classify analysis approach (confirmatory vs descriptive) first
- Only extract estimands explicitly defined in the protocol
- Removed all default ICE fabrication from parser and schema
- Added `AnalysisApproach` enum and approach-aware validation
- M11 composer now explains why estimands are N/A for descriptive studies

**Verified**: Wilson's Phase 2 PK/PD study (no estimands in protocol or SAP) now correctly produces 0 estimands with `analysisApproach: "descriptive"`.

---

## Prevention Guidelines

1. **Extraction prompts** must never instruct the LLM to "infer", "construct", or "include even if not explicit"
2. **Schema `to_dict()` methods** must not manufacture default entities — empty collections should stay empty
3. **Post-processing** should only create entities from actual extracted data, never from boilerplate
4. **Any inferred data** must be clearly marked with provenance (e.g., `[Inferred — verify against protocol]`)
5. **Study type awareness** (confirmatory vs descriptive) should gate extraction of framework-dependent constructs (estimands, multiplicity adjustments, interim analyses)
