# Review Prompts for MCP Mediator

These are the exact prompts to send to the claude-mediator for each step of the quality review.
Substitute `{study_id}`, `{indication}`, `{nct_id}` with actual values.

---

## A. Initial Review Prompts

### JSON Intake Prompt (Step 1 — always use minify="json")

```
I'm sending you a USDM v4.0 JSON file — the output of an AI extraction pipeline that converts clinical protocol PDFs into CDISC USDM v4.0 structured data. This is the digital protocol for study {study_id} ({indication}, {nct_id}).

Confirm receipt with: entity type count, arm/epoch/objective/endpoint counts, and any immediate structural issues (empty arrays, orphaned references). Keep response under 500 words.
```

### Combined PDF Intake + Review Prompt (Step 2 — saves a turn vs separate messages)

```
I'm now sending the source protocol PDF for the same study. Please confirm receipt briefly, then proceed directly to the full quality review below.

[PASTE FULL REVIEW PROMPT HERE — see "Full Protocol Review Prompt" below]
```

### SAP PDF Intake Prompt (Session 2, Step 2)

```
Now I'm sending you the Statistical Analysis Plan (SAP) PDF for the same study.

Please confirm receipt and briefly note:
- Analysis populations defined
- Primary analysis methodology
- Sample size and power calculations
- Multiplicity adjustments
- Interim analysis plans
```

### Full Protocol Review Prompt (Step 3)

```
Now please perform a comprehensive quality review of the USDM JSON against the source Protocol PDF. Structure your review under these four headings:

## 1. CDISC USDM v4.0 Conformance
- Are all required USDM entity types present with correct instanceType values?
- Are NCI C-codes used correctly (check controlled terminology for: trial phase, study type, arm type, blinding, objective level, endpoint level, eligibility category, sex)?
- Are entity relationships properly linked via UUIDs (e.g., StudyCell references valid arm and epoch IDs)?
- Are extension attributes used appropriately (prefixed with "ext_")?
- Is the entity placement hierarchy correct per USDM v4.0 (e.g., eligibilityCriterionItems on StudyVersion not StudyDesign, indications on StudyDesign not Study)?

## 2. Completeness
- Which M11 sections (§1–§14) have corresponding narrative content? Which are missing?
- Are all protocol-specified objectives, endpoints, and estimands captured?
- Are all arms, epochs, and study cells represented?
- Are all eligibility criteria (inclusion + exclusion) extracted?
- Are all interventions with dose, route, and schedule captured?
- Is the Schedule of Activities (SoA) complete with activities, encounters, timings?
- Are abbreviations extracted?

## 3. Referential Integrity
- Do all UUID cross-references resolve to existing entities?
- Do StudyCell arm/epoch references match defined arms and epochs?
- Do ScheduledActivityInstance references point to valid activities and encounters?
- Do Timing references point to valid encounters?
- Do Endpoint/Estimand references point to valid objectives?
- Are there orphaned entities (defined but never referenced)?
- Are there dangling references (referenced but never defined)?

## 4. Adherence to Source Documentation
- Compare key data points between the PDF and JSON:
  - Study title, phase, design type, blinding, randomization
  - Number and names of arms
  - Primary/secondary/exploratory objectives and endpoints
  - Key eligibility criteria (age, sex, condition-specific)
  - Intervention names, doses, routes, schedules
  - SoA structure (visits, procedures)
- Flag any data that appears in the JSON but NOT in the PDF (hallucinations)
- Flag any data that appears in the PDF but NOT in the JSON (extraction gaps)
- Note any data that appears transformed or simplified versus the source

For each finding, assign a severity:
- **CRITICAL**: Data is wrong, missing required entity, or breaks USDM conformance
- **HIGH**: Significant extraction gap or incorrect mapping
- **MEDIUM**: Minor gap, could be improved
- **LOW**: Cosmetic or optional improvement

Please be specific — reference USDM entity types, C-codes, M11 section numbers, and PDF page numbers where applicable.
```

### Continuation Prompt (if review was truncated)

```
The Section 4 (Adherence to Source Documentation) was truncated. Please continue from where you left off — specifically complete:
- The key data point comparison table (remaining rows)
- The hallucination check (data in JSON but NOT in PDF)
- The extraction gap check (data in PDF but NOT in JSON)
- Data transformation notes
- An overall summary with severity counts across all 4 sections and a quality score out of 10
```

### SAP-Focused Review Prompt (Session 2, Step 3)

```
Now please perform a quality review of the USDM JSON's statistical and analysis-related content against the SAP PDF. Focus on:

## 1. Analysis Populations
- Are all SAP-defined analysis populations captured in the USDM JSON (as AnalysisPopulation entities)?
- Are population definitions accurate vs the SAP?
- Are population links to study arms correct?

## 2. Statistical Methods
- Are primary and secondary analysis methods captured?
- Are estimands correctly structured with all 5 ICH E9(R1) attributes (population, variable, intercurrent events, population-level summary)?
- Are intercurrent event strategies correctly mapped?

## 3. Sample Size
- Is the planned sample size captured (overall and per-arm)?
- Are power calculations and assumptions documented (in extension attributes or narrative)?
- Does the USDM JSON sample size match the SAP?

## 4. Multiplicity & Interim Analysis
- Are multiplicity adjustment methods captured?
- Are interim analysis plans documented?
- Are alpha spending functions or stopping boundaries noted?

## 5. ARS Linkage (if present)
- Are CDISC ARS entities generated (ReportingEvent, Analysis, AnalysisMethod)?
- Do ARS operation IDs follow standard patterns?
- Are STATO ontology mappings present for statistical methods?

For each finding, assign severity (CRITICAL/HIGH/MEDIUM/LOW) and reference specific SAP sections and USDM entities.
```

---

## B. Delta Review Prompts (Iteration Cycles)

Use these when re-reviewing after implementing fixes.

### Delta Review Prompt (replaces Full Review in iteration ≥2)

```
I'm sending you an updated USDM v4.0 JSON extraction for study {study_id} ({nct_id}). This is **iteration {N}** — the pipeline has been modified to address findings from the previous review.

Previous review (iteration {N-1}) scored **{prev_score}/10** with these top findings:

{paste_top_findings_table}

**Known false positives to IGNORE** (these are expected pipeline behaviors, not bugs):
- Study site names/details come from a separate sites data source, not the protocol PDF
- Age upper limit 99 is a convention for "no upper limit"
- _temp_ prefixed entities are pipeline staging data (flag as MEDIUM at most)
- Narrative text may appear in multiple M11 sections due to protocol→M11 section mapping
- Extension attributes use USDM ExtensionAttribute entities (not inline ext_ prefix)

Please perform a **delta review** structured as:

## 1. Resolved Findings
Which of the previous top findings are now fixed? For each, confirm what changed.

## 2. Persistent Findings
Which previous findings still exist? Note if they've improved partially.

## 3. New Findings / Regressions
Any new issues introduced by the changes? Flag regressions (things that worked before but are now broken) as CRITICAL.

## 4. Updated Quality Score
Provide an updated score out of 10 for each dimension:
- USDM Structural Conformance
- Extraction Completeness
- Referential Integrity
- Source Fidelity
- M11 Coverage
- OVERALL

## 5. Updated Severity Counts
Provide a consolidated count: CRITICAL / HIGH / MEDIUM / LOW

## 6. Remaining Action Items
Top 5 remaining findings to fix in the next iteration, with pipeline phase and file mapping.
```

### Quick Regression Check Prompt (lightweight, no PDF needed)

```
I'm sending you an updated USDM v4.0 JSON for study {study_id}. This is a quick structural check after pipeline code changes. No PDF comparison needed.

Please verify:
1. All required USDM entity types present with correct instanceType
2. No UUID collisions (same ID used for different entity types)
3. No empty activityIds arrays on ScheduledActivityInstance entities
4. StudyCell count matches arms × epochs
5. All Endpoint/Estimand objectiveId references resolve
6. No _temp_ or staging data leaked into the final output
7. NCI C-codes on objectives, endpoints, arms, epochs are valid CDISC CT values

Report only CRITICAL and HIGH findings. Skip MEDIUM/LOW for speed.
```

---

## C. Follow-up Drill-Down Prompts

Use these in the same session to dig deeper into specific areas flagged by the initial review.

### Eligibility Deep-Dive
```
Please compare every inclusion and exclusion criterion in the PDF (Section 5) against the EligibilityCriterion entities in the USDM JSON. For each criterion, note: captured/missing, text accuracy, correct category code (C25532 Inclusion / C25370 Exclusion).
```

### SoA Deep-Dive
```
Please compare the Schedule of Activities table in the PDF against the ScheduleTimeline, Activity, Encounter, and Timing entities in the USDM JSON. Check: all visits captured, all procedures mapped to activities, timing relationships correct, footnotes preserved.
```

### Objectives Deep-Dive
```
Please compare Section 3 (Objectives and Estimands) of the PDF against the Objective, Endpoint, and Estimand entities in the USDM JSON. Check: all objectives captured with correct level codes (C85826 Primary / C85827 Secondary / C163559 Exploratory), endpoint text accuracy, estimand completeness per ICH E9(R1).
```

### Interventions Deep-Dive
```
Please compare Section 6 (Study Intervention) of the PDF against the StudyIntervention, Administration, and AdministrableProduct entities in the USDM JSON. Check: all interventions captured, dose/route/schedule accuracy, concomitant medication representation, dose modification rules mapped to TransitionRule entities.
```

### Hallucination-Focused Check
```
Please perform a strict hallucination audit. For every entity in the USDM JSON that contains specific factual claims (names, numbers, codes, descriptions), verify it can be traced to a specific location in the PDF. Flag anything that cannot be traced, categorized as:
- FABRICATION: Data invented with no PDF basis
- INFERENCE: Data that could be reasonably inferred but is not explicitly stated
- EXTERNAL: Data likely from an external source (ClinicalTrials.gov, DrugBank, etc.)
```

---

## D. Cross-Protocol Comparison Prompt

Use after reviewing multiple protocols to identify systemic issues.

```
I've reviewed {N} protocols through the same extraction pipeline. Here are the common findings across protocols:

{paste_cross_protocol_findings_table}

For each finding that appears in 2+ protocols, please:
1. Classify as SYSTEMIC (pipeline code issue) or COINCIDENTAL (protocol-specific)
2. For systemic issues, suggest the root cause (prompt gap, parser logic, C-code mapping, combiner wiring)
3. Prioritize fixes by impact: which fixes would improve the most protocols?
```
