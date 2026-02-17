# Quality Review Criteria Checklist

Comprehensive checklist for evaluating a USDM v4.0 digital protocol extraction. Each item maps to a pipeline phase and file for remediation.

## 1. CDISC USDM v4.0 Structural Conformance

| # | Check | USDM Entity | Pipeline Phase | Remediation File |
|---|-------|-------------|----------------|-----------------|
| S1 | `instanceType` present on every entity | All | combiner | `pipeline/combiner.py` |
| S2 | Top-level structure: `study.versions[].studyDesigns[]` | Study, StudyVersion, StudyDesign | combiner | `pipeline/combiner.py` |
| S3 | `eligibilityCriterionItems` on StudyVersion (NOT StudyDesign) | EligibilityCriterionItem | eligibility | `pipeline/phases/eligibility.py` |
| S4 | `studyInterventions` on StudyVersion (NOT StudyDesign) | StudyIntervention | interventions | `pipeline/phases/interventions.py` |
| S5 | `indications` on StudyDesign (NOT Study root) | Indication | advanced | `pipeline/phases/advanced.py` |
| S6 | All UUIDs are valid v4 format | All | combiner | `pipeline/combiner.py` |
| S7 | `documentedBy` → StudyDefinitionDocumentVersion with contents[] | NarrativeContent | narrative | `pipeline/phases/narrative.py` |
| S8 | Extension attributes prefixed with `ext_` | ExtensionAttribute | all | Respective phase |

## 2. Controlled Terminology (NCI C-codes)

| # | Check | Codelist | Expected Values | Phase |
|---|-------|----------|----------------|-------|
| T1 | Trial phase | C15600–C15603, C49686 | Phase I, II, III, IV | metadata |
| T2 | Study type | C98388, C142615 | Interventional, Observational | metadata |
| T3 | Arm type | C174266–C174268 | Investigational, Placebo, Active Comparator | studydesign |
| T4 | Blinding | C49659, C28233, C15228, C66959 | Open Label, Single, Double, Triple | studydesign |
| T5 | Objective level | C85826, C85827, C163559 | Primary, Secondary, Exploratory | objectives |
| T6 | Endpoint level | C94496, C139173, C170559 | Primary, Secondary, Exploratory | objectives |
| T7 | Eligibility category | C25532, C25370 | Inclusion, Exclusion | eligibility |
| T8 | Sex | C16576, C20197 | Female, Male | eligibility |
| T9 | Encounter type | C25716 | Visit | soa/execution |
| T10 | Epoch type | C48262, C98779, C101526, C99158 | Screening, Treatment, Follow-up, Run-in | studydesign |
| T11 | Intervention type | C1909, C307, C16830 etc. | Drug, Biological, Device | interventions |
| T12 | Product designation | C207418 | IMP, NIMP | interventions |
| T13 | Organization type | C188724 codes | Sponsor, Regulatory Authority | metadata |

## 3. Completeness by M11 Section

| # | M11 Section | Required USDM Entities | Phase |
|---|-------------|----------------------|-------|
| C1 | §1 Protocol Summary | NarrativeContent (synopsis), StudyTitle, StudyIdentifier | metadata, narrative |
| C2 | §2 Introduction | NarrativeContent | narrative |
| C3 | §3 Objectives & Estimands | Objective, Endpoint, Estimand, IntercurrentEvent | objectives |
| C4 | §4 Trial Design | StudyDesign, Arms, Epochs, Cells, Elements, Masking | studydesign |
| C5 | §5 Population | EligibilityCriterion, StudyDesignPopulation | eligibility |
| C6 | §6 Interventions | StudyIntervention, Administration, AdministrableProduct | interventions |
| C7 | §7 Discontinuation | NarrativeContent | narrative |
| C8 | §8 Assessments | Activity, Procedure | procedures |
| C9 | §9 AE/Safety | NarrativeContent, Condition | advanced |
| C10 | §10 Statistics | AnalysisPopulation, NarrativeContent | sap |
| C11 | §11 Oversight | NarrativeContent | narrative |
| C12 | §12 Appendix: Supporting | StudyAmendment | amendments |
| C13 | §13 Appendix: Glossary | Abbreviation | narrative |
| C14 | §14 Appendix: References | NarrativeContent | narrative |

## 4. Referential Integrity Checks

| # | Check | Source Entity | Target Entity |
|---|-------|--------------|---------------|
| R1 | StudyCell.armId → valid StudyArm | StudyCell | StudyArm |
| R2 | StudyCell.epochId → valid StudyEpoch | StudyCell | StudyEpoch |
| R3 | ScheduledActivityInstance.activityId → valid Activity | ScheduledActivityInstance | Activity |
| R4 | ScheduledActivityInstance.encounterId → valid Encounter | ScheduledActivityInstance | Encounter |
| R5 | Timing.fromId / toId → valid Encounter | Timing | Encounter |
| R6 | Endpoint.objectiveId → valid Objective | Endpoint | Objective |
| R7 | Estimand.objectiveId → valid Objective | Estimand | Objective |
| R8 | StudyIntervention linked to Administration | StudyIntervention | Administration |
| R9 | Administration linked to AdministrableProduct | Administration | AdministrableProduct |
| R10 | No orphaned entities (defined but never referenced) | All | All |
| R11 | No dangling references (referenced but undefined) | All | All |

## 5. Source Adherence Spot-Checks

| # | Data Point | PDF Location | USDM Path |
|---|-----------|-------------|-----------|
| A1 | Study title | Title page | `study.versions[0].titles[]` |
| A2 | Protocol number | Title page | `study.versions[0].studyIdentifiers[]` |
| A3 | Sponsor name | Title page | `study.versions[0].organizations[]` |
| A4 | Phase | Title page / §1 | `study.versions[0].studyDesigns[0].trialPhase` |
| A5 | Number of arms | §4 | `study.versions[0].studyDesigns[0].arms[]` |
| A6 | Arm names | §4 | Each arm's `name` and `description` |
| A7 | Primary objective text | §3 | `objectives[].text` where level=Primary |
| A8 | Primary endpoint text | §3 | `endpoints[].text` where level=Primary |
| A9 | Key inclusion criteria | §5 | `eligibilityCriterionItems[]` with category=Inclusion |
| A10 | Key exclusion criteria | §5 | `eligibilityCriterionItems[]` with category=Exclusion |
| A11 | Drug name and dose | §6 | `studyInterventions[].administrations[].dose` |
| A12 | Number of visits in SoA | §1.3 or §8 | `scheduleTimelines[0].instances[]` count |
| A13 | Study duration | §4 | Epoch durations or narrative |
| A14 | Sample size | §10 or §1 | `population.plannedNumberOfSubjects` or ext_ |
| A15 | Randomization ratio | §4 | Arms or narrative |

## 6. Severity Classification

| Severity | Definition | Action | Iteration Target |
|----------|-----------|--------|-----------------|
| **CRITICAL** | Wrong data, missing required USDM entity, breaks schema validation | Fix immediately — likely extractor or combiner bug | Same iteration |
| **HIGH** | Significant data gap, incorrect C-code, missing M11 section content | Fix in next sprint — prompt or parser improvement | Next iteration |
| **MEDIUM** | Minor gap, optional field missing, could be richer | Backlog — enhancement | Future iteration |
| **LOW** | Cosmetic, formatting, optional metadata | Nice-to-have | Defer |

## 7. Mapping Findings to Pipeline Phases

| Finding Category | Primary Phase | Files to Check |
|-----------------|--------------|---------------|
| Missing/wrong metadata | metadata | `extraction/metadata/{prompts,extractor,schema}.py`, `pipeline/phases/metadata.py` |
| Missing narrative content | narrative | `extraction/narrative/{prompts,extractor}.py`, `pipeline/phases/narrative.py` |
| Objective/endpoint issues | objectives | `extraction/objectives/{prompts,extractor,schema}.py`, `pipeline/phases/objectives.py` |
| Design/arm/epoch issues | studydesign | `extraction/studydesign/{prompts,extractor,schema}.py`, `pipeline/phases/studydesign.py` |
| Eligibility gaps | eligibility | `extraction/eligibility/{prompts,extractor,schema}.py`, `pipeline/phases/eligibility.py` |
| Intervention issues | interventions | `extraction/interventions/{prompts,extractor,schema}.py`, `pipeline/phases/interventions.py` |
| SoA/timeline issues | soa + execution | `extraction/soa/`, `extraction/execution/`, `pipeline/post_processing.py` |
| Procedure issues | procedures | `extraction/procedures/{prompts,extractor,schema}.py`, `pipeline/phases/procedures.py` |
| SAP/statistics issues | sap | `extraction/conditional/sap_extractor.py`, `pipeline/phases/sap.py` |
| Amendment issues | amendments | `extraction/amendments/{prompts,extractor,schema}.py`, `pipeline/phases/amendments.py` |
| Cross-entity linkage | post_processing | `pipeline/post_processing.py`, `pipeline/promotion.py` |
| Entity reconciliation | reconciliation | `core/reconciliation/` |
| UUID collisions | combiner | `pipeline/combiner.py`, `pipeline/integrations.py` |
| Hallucinations | extraction prompts | `extraction/<phase>/prompts.py` — tighten "extract only" instructions |
| C-code errors | code_registry | `core/code_registry.py`, `core/terminology_codes.py`, `extraction/<phase>/schema.py` |

## 8. Common Fix Patterns

These are the most common fix types encountered during iterative improvement, with specific code patterns.

### 8.1 Prompt Fix (LLM not extracting data)

**Symptom**: Data exists in PDF but not in USDM JSON.
**Root cause**: Extraction prompt doesn't ask for this data.
**Fix**: Add explicit instructions and JSON schema fields to the prompt.

```
File: extraction/<phase>/prompts.py
Pattern: Add a new field to the JSON example in the prompt
         Add explicit instruction: "Extract ALL [thing], including [specific thing reviewer flagged]"
```

### 8.2 Parser Fix (LLM extracted but parser dropped it)

**Symptom**: LLM returns data in raw JSON but it doesn't appear in the final USDM.
**Debug**: Add logging to `extraction/<phase>/extractor.py` to see raw LLM output.
**Fix**: Update parser to handle the field.

```
File: extraction/<phase>/extractor.py
Pattern: Add parsing logic for the new field from the LLM response
         Map to the Pydantic schema model
```

### 8.3 Schema Fix (parser needs a new field)

**Symptom**: Pydantic model doesn't have a field for the data.
**Fix**: Add field to schema, update `to_dict()` to emit USDM-compliant output.

```
File: extraction/<phase>/schema.py
Pattern: Add field to Pydantic model
         Update to_dict() to emit proper USDM entity with instanceType, id, C-codes
```

### 8.4 Combiner Fix (data extracted but lost during assembly)

**Symptom**: Phase extraction succeeds but data missing from final protocol_usdm.json.
**Fix**: Wire the new data into the combiner's USDM assembly.

```
File: pipeline/phases/<phase>.py (combine method)
      pipeline/combiner.py (combine_to_full_usdm)
Pattern: Add data from phase result to the appropriate USDM location
         Respect entity placement hierarchy (see AGENTS.md §1.1)
```

### 8.5 Post-Processing Fix (cross-entity linkage broken)

**Symptom**: Entities exist but references between them are wrong or missing.
**Fix**: Add reconciliation logic in post-processing.

```
File: pipeline/post_processing.py
      core/reconciliation/<entity>_reconciler.py
Pattern: Match entities by name/description when UUIDs don't resolve
         Use fuzzy matching for activity/encounter names
```

### 8.6 C-Code Fix (wrong controlled terminology)

**Symptom**: Entity has wrong NCI C-code or uses a fabricated code.
**Fix**: Use CodeRegistry for verified codes.

```
File: extraction/<phase>/schema.py or core/code_registry.py
Pattern: Replace hardcoded C-code with registry.make_code("codelist", "value")
         Verify against NCI EVS: https://ncit.nci.nih.gov/ncitbrowser/
```

### 8.7 Hallucination Fix (data not in source)

**Symptom**: USDM JSON contains data that doesn't appear in the source PDF.
**Root cause**: LLM inferred or fabricated data.
**Fix**: Tighten prompt with "extract ONLY what is explicitly stated in the document" guard rails.

```
File: extraction/<phase>/prompts.py
Pattern: Add: "Do NOT infer or fabricate data. If a field is not explicitly stated
         in the document, leave it empty/null. Only extract what you can cite."
         Add: "For [specific field], extract the exact text from the document."
```

## 9. Regression Test Patterns

For each fix, add a corresponding test:

```python
# tests/test_review_fixes.py

def test_safety_objective_not_coded_as_secondary():
    """Regression: reviewer found safety objective miscoded as C85827 (Secondary)."""
    result = run_objectives_extractor(MOCK_PROTOCOL_WITH_SAFETY_OBJ)
    safety_objs = [o for o in result.objectives if 'safety' in o.name.lower()]
    assert len(safety_objs) >= 1
    # Safety should NOT have Secondary level code
    for obj in safety_objs:
        assert obj.level != 'C85827', "Safety objective should not be coded as Secondary"

def test_all_epochs_have_study_cells():
    """Regression: reviewer found EOS/ET epoch with no StudyCell."""
    usdm = json.load(open('output/.../protocol_usdm.json'))
    design = usdm['study']['versions'][0]['studyDesigns'][0]
    epoch_ids = {e['id'] for e in design['studyEpochs']}
    cell_epoch_ids = {c['epochId'] for c in design['studyCells']}
    assert epoch_ids == cell_epoch_ids, f"Orphaned epochs: {epoch_ids - cell_epoch_ids}"

def test_no_uuid_collisions():
    """Regression: reviewer found Population UUID collision."""
    usdm = json.load(open('output/.../protocol_usdm.json'))
    all_ids = collect_all_entity_ids(usdm)
    assert len(all_ids) == len(set(all_ids)), "UUID collision detected"
```
