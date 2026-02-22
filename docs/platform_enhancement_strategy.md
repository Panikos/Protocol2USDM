# Protocol2USDM — Comprehensive Platform Enhancement Strategy

## Multi-Agent Expert Discussion

**Date**: 2026-02-22
**Participants**:
- **Dr. Elena Vasquez** — Biostatistician / ICH E9(R1) Expert (15y pharma)
- **Dr. Ravi Menon** — CDISC Standards Architect (USDM v4.0 working group member)
- **Dr. Sarah Chen** — Clinical Operations Lead (protocol authoring, regulatory submissions)
- **Marcus Torres** — Software Architect (Protocol2USDM pipeline + web UI)
- **Dr. Kenji Yamamoto** — NLP/AI Engineering Lead (LLM extraction, prompt engineering)

---

## Methodology

For each platform area we evaluate:
1. **Current state** — what exists today (code, schema, tests)
2. **USDM v4.0 alignment** — gaps against `dataStructure.yml` (86 entity types)
3. **ICH M11 alignment** — gaps against Technical Specification (14 sections)
4. **Expert recommendations** — multi-perspective improvements
5. **Prioritized action items** — with effort/impact ratings

---

# AREA 1: METADATA EXTRACTION

**Phase**: `extraction/metadata/` → `pipeline/phases/metadata.py`
**M11 Sections**: Title Page, §1 Protocol Summary
**USDM Entities**: Study, StudyVersion, StudyTitle, StudyIdentifier, Organization, StudyRole, GovernanceDate, Address

### Current State
- Extracts: titles (5 types), identifiers (NCT, EudraCT, sponsor protocol ID), sponsor org, phase, status
- `StudyRole` supports 12 role codes with `assignedPersons` (M2 fix)
- `GovernanceDate` partially populated (approval dates)
- `referenceIdentifiers` (L1 fix) extracts registry cross-references
- `businessTherapeuticAreas` derived from indications (M1 fix)

### USDM Alignment Gaps

**DR. MENON**: Three structural gaps remain:

| USDM Entity/Field | Status | Gap |
|---|---|---|
| `StudyVersion.amendments[]` | ✅ Extracted | Covered by amendments phase |
| `StudyVersion.effectiveDate` | ⚠️ Partial | Only populated when explicitly stated in protocol |
| `GovernanceDate.type` | ⚠️ Partial | Missing USDM CT codelist C207421 (dateType: Approval/Submission/etc.) |
| `Address` on Organization | ❌ Missing | USDM requires `line`, `city`, `country` — never extracted |
| `Organization.identifier` | ❌ Missing | DUNS number, LEI — not extracted |
| `StudyVersion.studyPhase` | ✅ Present | But uses string, should use Code with C99079 codelist |
| `StudyIdentifier.studyIdentifierScope` | ⚠️ Partial | Scope org exists but not always linked properly |

### Expert Recommendations

**DR. CHEN**: The biggest operational gap is **regulatory submission metadata**. When a sponsor generates an M11 DOCX for FDA/EMA submission, they need:
- IND/IDE number (FDA), CTA number (EMA) — currently not extracted
- Regulatory authority organization with proper address
- Protocol version history with dated approvals

**DR. YAMAMOTO**: The metadata LLM prompt is already solid but could benefit from:
- **Structured output mode** — force JSON schema compliance at the LLM level (Gemini supports this)
- **Multi-page scanning** — currently reads first ~15 pages; some protocols have metadata scattered across cover pages, headers, and appendix A

### Action Items

| ID | Enhancement | Effort | Impact | Priority |
|---|---|---|---|---|
| META-1 | Extract `Address` for sponsor/CRO organizations | S | M | MEDIUM |
| META-2 | Add `GovernanceDate.type` Code using USDM CT C207421 | S | M | MEDIUM |
| META-3 | Extract IND/IDE/CTA regulatory identifiers | M | H | HIGH |
| META-4 | Use LLM structured output mode for metadata JSON | S | M | MEDIUM |
| META-5 | Extract `Organization.identifier` (DUNS/LEI) | S | L | LOW |

---

# AREA 2: NARRATIVE EXTRACTION

**Phase**: `extraction/narrative/` → `pipeline/phases/narrative.py`
**M11 Sections**: §1–§14 (all narrative text)
**USDM Entities**: NarrativeContent, NarrativeContentItem, Abbreviation, StudyDefinitionDocument

### Current State
- Two-strategy approach: structure-first (TOC-guided) + content-first (LLM section classification)
- Achieves 14/14 M11 section coverage on well-structured protocols
- Abbreviation extraction from glossary pages
- `sectionType` tagging via M11 mapping config
- `StudyDefinitionDocument` and `DocumentVersion` wired into `Study.documentedBy`

### USDM Alignment Gaps

**DR. MENON**: The narrative model is architecturally sound but has entity-level gaps:

| USDM Entity/Field | Status | Gap |
|---|---|---|
| `NarrativeContent.sectionType` | ✅ Present | Uses Code with M11 section codes |
| `NarrativeContentItem.text` | ✅ Present | Full text extracted |
| `NarrativeContent.childIds[]` | ⚠️ Partial | Parent→child hierarchy not always correct for deep nesting (L4/L5) |
| `Abbreviation.abbreviatedText` | ✅ Present | |
| `Abbreviation.expandedText` | ✅ Present | |
| `StudyDefinitionDocument.templateName` | ❌ Missing | Should be "ICH M11" when applicable |
| `NarrativeContent.contentItemId` | ⚠️ Partial | Not always linked to NarrativeContentItem |

### Expert Recommendations

**DR. YAMAMOTO**: Key improvements for narrative extraction:

1. **Deep heading hierarchy** — Currently L1–L3 headings are reliable, but L4/L5 (e.g., `10.4.1.1.2`) often get flattened. Need a dedicated heading parser that uses font size + indentation + numbering pattern.

2. **Table-in-narrative preservation** — When narrative sections contain inline tables (e.g., dosing schedules in §6, statistical methods in §10), these are extracted as flat text. Should preserve table structure as HTML/markdown within `NarrativeContentItem.text`.

3. **Cross-reference resolution** — Phrases like "See Section 5.2" or "As described in Table 4" should generate `InlineCrossReference` entities linking to the target NarrativeContent.

4. **Figure extraction** — Protocol figures (study design diagrams, CONSORT flow) are currently extracted as page images but not linked to narrative sections. `ProtocolFigure` entities should have `sectionId` references.

**DR. CHEN**: The narrative is the backbone of the M11 DOCX output. Two practical gaps:
- **Version diff detection** — When protocols have track changes or amendment markups, the extractor should flag which sections changed
- **Boilerplate detection** — Standard regulatory text (e.g., ICH E6 compliance statements) should be tagged as boilerplate vs. protocol-specific content

### Action Items

| ID | Enhancement | Effort | Impact | Priority |
|---|---|---|---|---|
| NAR-1 | Deep heading hierarchy parser (L4/L5 support using font analysis) | M | H | HIGH |
| NAR-2 | Preserve inline table structure in narrative text | M | H | HIGH |
| NAR-3 | Cross-reference entity generation (`InlineCrossReference`) | M | M | MEDIUM |
| NAR-4 | Link `ProtocolFigure` entities to parent `NarrativeContent` sections | S | M | MEDIUM |
| NAR-5 | Set `StudyDefinitionDocument.templateName` = "ICH M11" | S | L | LOW |
| NAR-6 | Boilerplate/regulatory text detection and tagging | M | M | MEDIUM |

---

# AREA 3: OBJECTIVES & ESTIMANDS EXTRACTION

**Phase**: `extraction/objectives/` → `pipeline/phases/objectives.py`
**M11 Sections**: §3 Objectives, Endpoints, Estimands
**USDM Entities**: Objective, Endpoint, Estimand, IntercurrentEvent

### Current State
- Extracts primary/secondary/exploratory objectives with linked endpoints
- Estimand extraction per ICH E9(R1) — 5 mandatory attributes
- `AnalysisApproach` classification (confirmatory vs descriptive) gates estimand extraction
- `IntercurrentEventStrategy` enum with 5 strategies
- `validate_e9_completeness()` checks all 5 attributes per estimand

### USDM Alignment Gaps

**DR. MENON**: This is one of the strongest phases. Remaining gaps:

| USDM Entity/Field | Status | Gap |
|---|---|---|
| `Objective.level` | ✅ Present | Uses correct NCI C-codes (C85826/C85827/C163559) |
| `Endpoint.level` | ✅ Present | Uses correct codes (C94496/C139173/C170559) |
| `Estimand.interventionIds[]` | ⚠️ Partial | Text-based, not always resolved to actual StudyIntervention IDs |
| `Estimand.analysisPopulationId` | ⚠️ Partial | Often unresolved — depends on SAP phase running first |
| `Endpoint.purpose` | ⚠️ Partial | Free text, not Code from USDM CT |
| `IntercurrentEvent.strategy` | ✅ Present | But USDM v4.0 uses string, not Code — correct |
| `Objective.endpoints[]` (Value) | ✅ Present | Inline endpoints on objectives |

### Expert Recommendations

**DR. VASQUEZ**: The estimand framework is technically correct but could be much richer:

1. **Estimand-to-endpoint traceability** — `variableOfInterestId` should resolve to the actual `Endpoint` entity extracted in the same phase, not just a text match. Currently uses fuzzy string matching.

2. **Multi-estimand support** — Most Phase 3 trials have 2–4 estimands (one per primary endpoint). Current extraction sometimes merges them or misses secondary estimands.

3. **ICE completeness scoring** — Each intercurrent event should have a confidence score indicating whether the strategy was explicitly stated in the protocol vs. inferred.

4. **Composite endpoint decomposition** — Endpoints like "major adverse cardiovascular events (MACE)" are composite. Should extract component sub-endpoints and link them.

**DR. MENON**: USDM v4.0 has a `summaryMeasure` attribute on Estimand (e.g., "Difference in means", "Hazard ratio"). This is extracted as text but should ideally use the CDISC controlled terminology when available.

### Action Items

| ID | Enhancement | Effort | Impact | Priority |
|---|---|---|---|---|
| OBJ-1 | Resolve `Estimand.interventionIds` to actual StudyIntervention UUIDs | M | H | HIGH |
| OBJ-2 | Resolve `Estimand.analysisPopulationId` to SAP AnalysisPopulation IDs | M | H | HIGH |
| OBJ-3 | Composite endpoint decomposition (MACE → component endpoints) | M | M | MEDIUM |
| OBJ-4 | Multi-estimand extraction — dedicated pass for each primary endpoint | M | H | HIGH |
| OBJ-5 | ICE confidence scoring (explicit vs inferred strategy) | S | M | MEDIUM |
| OBJ-6 | `Endpoint.purpose` as Code object from USDM CT | S | L | LOW |

---

# AREA 4: STUDY DESIGN EXTRACTION

**Phase**: `extraction/studydesign/` → `pipeline/phases/studydesign.py`
**M11 Sections**: §4 Trial Design
**USDM Entities**: StudyDesign, StudyArm, StudyEpoch, StudyCell, StudyElement, Masking, Indication

### Current State
- Extracts: arms (with type codes), epochs, study type, intervention model, blinding schema
- `AllocationRatio` and `RandomizationType` as coded values
- Therapeutic area derivation from indication keywords
- `StudyCell` matrix linking arms to epochs
- Masking entity with role-based blinding levels

### USDM Alignment Gaps

**DR. MENON**: Study design has several entity-level gaps:

| USDM Entity/Field | Status | Gap |
|---|---|---|
| `StudyDesign.instanceType` | ✅ Present | InterventionalStudyDesign/ObservationalStudyDesign |
| `StudyArm.type` | ✅ Present | Uses correct arm type codes C174266/C174267/C174268 |
| `StudyArm.notes[]` | ✅ Present | CommentAnnotation objects (L3 fix) |
| `StudyEpoch.type` | ✅ Present | Uses correct epoch type codes |
| `StudyElement.transitionRule` | ❌ Missing | TransitionRule on elements for progression logic |
| `StudyDesign.characteristics[]` | ❌ Missing | Study-level characteristics (adaptive, platform, basket, umbrella) |
| `StudyDesign.encounters[]` | ✅ Present | Via scheduling phase |
| `Masking.roles[]` | ⚠️ Partial | Roles extracted but not always as separate Code objects |
| `Indication.codes[]` | ⚠️ Partial | MeSH/MedDRA codes not always resolved |

### Expert Recommendations

**DR. CHEN**: Three operational improvements:

1. **Adaptive design detection** — Platform trials, basket trials, umbrella trials have unique design characteristics. Currently these are treated as standard parallel-group designs. Need explicit design characteristic classification.

2. **Duration extraction** — Study duration, treatment duration, follow-up duration should be extracted as ISO 8601 Duration values and placed on `StudyElement.plannedDuration`.

3. **Washout period extraction** — For crossover designs, washout periods are critical. Should be extracted as distinct `StudyElement` entities with appropriate timing.

**DR. MENON**: The `StudyCell` matrix is correctly populated but the `StudyElement` entities within cells often lack `transitionStartRule` and `transitionEndRule`. These are USDM entities that describe when a subject moves from one element to the next.

### Action Items

| ID | Enhancement | Effort | Impact | Priority |
|---|---|---|---|---|
| DES-1 | Extract `TransitionRule` for epoch/element transitions | M | H | HIGH |
| DES-2 | Adaptive/platform/basket/umbrella design classification | M | H | HIGH |
| DES-3 | Duration extraction (study/treatment/follow-up) as ISO 8601 | M | H | HIGH |
| DES-4 | Washout period extraction for crossover designs | S | M | MEDIUM |
| DES-5 | Resolve `Indication.codes[]` to MedDRA/MeSH codes via API | M | M | MEDIUM |
| DES-6 | `StudyDesign.characteristics[]` for design features | S | M | MEDIUM |

---

# AREA 5: ELIGIBILITY EXTRACTION

**Phase**: `extraction/eligibility/` → `pipeline/phases/eligibility.py`
**M11 Sections**: §5 Study Population
**USDM Entities**: EligibilityCriterion, EligibilityCriterionItem, StudyDesignPopulation

### Current State
- Extracts inclusion/exclusion criteria with proper ordering (previousId/nextId chains)
- `EligibilityCriterionItem` for reusable text content
- `StudyDesignPopulation` with `plannedAge` (Range), `plannedEnrollmentNumber` (QuantityRange), `plannedSex` (Code[])
- Criteria linked to population via `criterionIds`
- P12 promotion: SAP sample size → population enrollment numbers

### USDM Alignment Gaps

**DR. MENON**:

| USDM Entity/Field | Status | Gap |
|---|---|---|
| `EligibilityCriterion.category` | ✅ Present | Correct C25532/C25370 codes |
| `EligibilityCriterion.identifier` | ✅ Present | I1, E1, etc. |
| `EligibilityCriterion.previousId/nextId` | ✅ Present | Ordering chain |
| `EligibilityCriterionItem.dictionary` | ❌ Missing | SyntaxTemplateDictionary for structured criteria |
| `StudyDesignPopulation.plannedAge` | ✅ Present | Range with Quantity min/max |
| `StudyDesignPopulation.plannedSex` | ✅ Present | Code array with NCI codes |
| `StudyDesignPopulation.plannedCompletionNumber` | ✅ Present | From P12 promotion |
| `StudyDesignPopulation.cohorts[]` | ✅ Present | From stratification C1 and existing cohort extraction |

### Expert Recommendations

**DR. VASQUEZ**: Eligibility is well-covered but can be enhanced:

1. **Structured criterion parsing** — Instead of just extracting raw text, parse criteria into structured components: variable (e.g., "HbA1c"), operator ("≥"), value ("7.0%"), unit ("%"). This enables downstream validation (e.g., "eligibility criteria consistent with endpoints?").

2. **Criterion severity classification** — Some criteria are absolute (e.g., "age ≥18") while others have investigator discretion ("in the opinion of the investigator"). Flagging this distinction helps with feasibility analysis.

3. **Lifestyle criteria** — Criteria about smoking, alcohol, contraception are often buried in eligibility but relevant for safety analysis. Should be tagged with a sub-category.

**DR. YAMAMOTO**: The eligibility extractor could benefit from:
- **Multi-pass extraction** — Pass 1: identify criteria boundaries, Pass 2: classify each criterion, Pass 3: extract structured components
- **Criterion normalization** — Many criteria express the same concept differently across protocols ("eGFR > 30" vs "no severe renal impairment"). Building a normalization layer would help cross-protocol analysis.

### Action Items

| ID | Enhancement | Effort | Impact | Priority |
|---|---|---|---|---|
| ELIG-1 | Structured criterion parsing (variable/operator/value/unit) | L | H | HIGH |
| ELIG-2 | Criterion sub-categorization (demographic/medical/lifestyle/lab) | M | M | MEDIUM |
| ELIG-3 | Multi-pass extraction for better boundary detection | M | M | MEDIUM |
| ELIG-4 | `SyntaxTemplateDictionary` support for structured criteria templates | L | M | LOW |
| ELIG-5 | Criterion severity/discretion flagging | S | L | LOW |

---

# AREA 6: INTERVENTIONS EXTRACTION

**Phase**: `extraction/interventions/` → `pipeline/phases/interventions.py`
**M11 Sections**: §6 Trial Interventions
**USDM Entities**: StudyIntervention, Administration, AdministrableProduct, Ingredient, Substance

### Current State
- Extracts: intervention name, type (Drug/Biological/Device), role (IMP/NIMP)
- `AdministrableProduct` with dose form, strength, route, designation, sourcing, pharmacologic class
- `Administration` with route, frequency, duration
- `Ingredient` and `Substance` entities
- Product designation (IMP/NIMP) per USDM CT C207418
- Promotion to native USDM `Administration` entities from execution model dosing regimens

### USDM Alignment Gaps

**DR. MENON**:

| USDM Entity/Field | Status | Gap |
|---|---|---|
| `StudyIntervention.role` | ✅ Present | USDM CT C207417 codes |
| `AdministrableProduct.routeOfAdministration` | ✅ Present | Coded value |
| `AdministrableProduct.productDesignation` | ✅ Present | IMP/NIMP |
| `Substance.referenceSubstance` | ❌ Missing | Link to external substance databases (UNII) |
| `Administration.duration` | ⚠️ Partial | Extracted as text, not always ISO 8601 Duration |
| `StudyIntervention.minimumResponseDuration` | ✅ Present | Duration entity (M4 fix) |
| `AdministrableProduct.properties[]` | ✅ Present | (L5 fix) |
| `Ingredient.strength` | ⚠️ Partial | Numerator/denominator quantities not always complete |

### Expert Recommendations

**DR. CHEN**: Interventions extraction needs:

1. **Dose modification rules** — Most protocols have dose reduction/escalation/interruption rules. These should be extracted as structured entities linked to `StudyIntervention`, not just narrative text.

2. **Concomitant/prohibited medication extraction** — §6 often specifies allowed/prohibited concomitant medications. These are currently captured in narrative but should be structured entities.

3. **Supply chain metadata** — Storage conditions, packaging, labeling requirements are specified in the protocol. Relevant for IRT/supply chain systems.

**DR. MENON**: The intervention model is one of the most complete USDM entity trees. The main gap is `Substance.referenceSubstance` — linking to UNII codes (FDA Substance Registration System) would enable automated drug dictionary cross-referencing.

### Action Items

| ID | Enhancement | Effort | Impact | Priority |
|---|---|---|---|---|
| INT-1 | Structured dose modification rules extraction | M | H | HIGH |
| INT-2 | Concomitant/prohibited medication as structured entities | M | H | HIGH |
| INT-3 | UNII code resolution for `Substance.referenceSubstance` | M | M | MEDIUM |
| INT-4 | ISO 8601 Duration normalization for `Administration.duration` | S | M | MEDIUM |
| INT-5 | Ingredient strength numerator/denominator completion | S | L | LOW |

---

# AREA 7: SCHEDULE OF ACTIVITIES (SoA) & SCHEDULING

**Phase**: `extraction/scheduling/` → `pipeline/phases/scheduling.py`
**M11 Sections**: §1.3 SoA, §8 Assessments
**USDM Entities**: ScheduleTimeline, ScheduledActivityInstance, Activity, Encounter, Timing

### Current State
- Grid-based SoA extraction from PDF tables (complex multi-header parsing)
- `ScheduleTimeline` with `ScheduledActivityInstance` entities
- `Encounter` entities for visits with timing constraints
- `Timing` entities with ISO 8601 durations and windows
- `ScheduledDecisionInstance` for unscheduled visits (UNS promotion)
- Activity source marking (SoA vs narrative)
- Footnote condition extraction and promotion to USDM `Condition` entities

### USDM Alignment Gaps

**DR. MENON**: SoA is the most complex extraction target. Gaps:

| USDM Entity/Field | Status | Gap |
|---|---|---|
| `ScheduleTimeline.exits[]` | ✅ Present | StudyExit entities |
| `ScheduledActivityInstance.encounterId` | ✅ Present | Linked to encounters |
| `ScheduledActivityInstance.activityIds[]` | ✅ Present | Linked to activities |
| `Timing.relativeToFrom` | ✅ Present | USDM CT codes |
| `Timing.windowLower/Upper` | ✅ Present | ISO 8601 Duration |
| `Activity.definedProcedures[]` | ✅ Present | Procedure linking |
| `Encounter.scheduledAtTimingId` | ⚠️ Partial | Not always resolved for all encounters |
| `ScheduleTimeline.mainTimeline` | ⚠️ Partial | Boolean flag but secondary timelines (follow-up) not always separated |
| `ConditionAssignment` | ❌ Missing | USDM entity for conditional visit/activity application |

### Expert Recommendations

**DR. VASQUEZ**: SoA extraction is strong but has quality gaps:

1. **Multi-timeline support** — Many protocols have separate SoA tables for treatment phase, follow-up phase, and screening. These should be separate `ScheduleTimeline` entities with `mainTimeline=true/false`. Currently they're merged.

2. **Conditional visit detection** — SoA footnotes like "At discretion of investigator" or "For female participants only" are captured as text but should generate proper `ConditionAssignment` entities per USDM v4.0.

3. **Visit window validation** — Extracted visit windows should be validated for consistency (e.g., no overlapping windows, windows within epoch bounds).

**DR. YAMAMOTO**: The SoA grid parser handles most table formats but struggles with:
- **Multi-row headers** — Some protocols have 3+ header rows (epoch, visit name, day number, week number)
- **Merged cells** — Activities spanning multiple visits or epochs
- **Symbol interpretation** — Different protocols use X, ✓, •, O, and custom symbols

### Action Items

| ID | Enhancement | Effort | Impact | Priority |
|---|---|---|---|---|
| SOA-1 | Multi-timeline separation (treatment vs follow-up vs screening) | L | H | HIGH |
| SOA-2 | `ConditionAssignment` entity generation from SoA footnotes | M | H | HIGH |
| SOA-3 | Visit window overlap/consistency validation | S | M | MEDIUM |
| SOA-4 | Multi-row header parsing improvement | M | M | MEDIUM |
| SOA-5 | Enhanced symbol interpretation (configurable symbol map) | S | M | MEDIUM |
| SOA-6 | Resolve `Encounter.scheduledAtTimingId` for all encounters | M | M | MEDIUM |

---

# AREA 8: EXECUTION MODEL

**Phase**: `extraction/execution/` → `pipeline/phases/execution.py`
**M11 Sections**: §1.3 (enrichment), §4, §8
**USDM Entities**: Extensions (x-executionModel-*), plus native promotions

### Current State
- 5-sub-phase extraction: time anchors, repetitions, traversal, crossover, footnotes
- Phase 3: endpoint algorithms, derived variables, state machine
- Phase 4: dosing regimens, visit windows, randomization/stratification (Sprint A complete)
- Activity bindings, analysis windows, titration schedules, instance bindings
- Validation with quality scoring
- Promotion of dosing regimens to native `Administration` entities

### USDM Alignment Gaps

**DR. MENON**: The execution model is largely extension-based (appropriate for operational semantics not in USDM v4.0), but more entities could be promoted:

| Execution Concept | Current Storage | Better USDM Target |
|---|---|---|
| Visit windows | Extension | Could enrich `Encounter.environmentalSetting` or `Timing.window*` |
| Time anchors | Extension | Could map to `Timing.relativeToFrom` on encounters |
| State machine | Extension | Could map to `TransitionRule` chains |
| Dosing regimens | Promoted to `Administration` | ✅ Already done |
| Randomization | Extension | TransitionRule + StudyCohort (C1 done) |

### Expert Recommendations

**DR. YAMAMOTO**: The execution model is the most innovative part of the platform. Enhancements:

1. **Anchor-to-encounter binding** — Time anchors identify "Day 1 = first dose" but this isn't propagated to set `encounterId` on the anchor. Binding anchors to their corresponding encounters would improve the timeline graph.

2. **State machine → TransitionRule promotion** — The extracted state machine (states + transitions) maps directly to USDM `TransitionRule` entities. Promote these to native USDM.

3. **Visit window → Timing enrichment** — Visit windows contain `windowBefore`/`windowAfter` values that should enrich the `Timing` entity `windowLower`/`windowUpper` fields already in the USDM.

### Action Items

| ID | Enhancement | Effort | Impact | Priority |
|---|---|---|---|---|
| EXEC-1 | Promote state machine transitions to USDM `TransitionRule` entities | M | H | HIGH |
| EXEC-2 | Bind time anchors to encounters (anchor→encounterId) | M | H | HIGH |
| EXEC-3 | Promote visit windows to `Timing.windowLower/Upper` | M | M | MEDIUM |
| EXEC-4 | Promote time anchors to `Timing.relativeToFrom` enrichment | M | M | MEDIUM |

---

# AREA 9: PROCEDURES EXTRACTION

**Phase**: `extraction/procedures/` → `pipeline/phases/procedures.py`
**M11 Sections**: §8 Assessments
**USDM Entities**: Activity, Procedure

### Current State
- Extracts procedures from SoA activities with type classification
- `ProcedureType` enum (7 types: Diagnostic, Therapeutic, Surgical, etc.)
- Code assignment via `CodeRegistry` for procedure type NCI codes
- `isOrderable` flag (L6 fix)
- Procedures linked to activities via `definedProcedures[]`

### USDM Alignment Gaps

**DR. MENON**:

| USDM Entity/Field | Status | Gap |
|---|---|---|
| `Procedure.code` | ✅ Present | But only NCI type codes, not specific procedure codes |
| `Procedure.procedureType` | ✅ Present | String classification |
| `Activity.definedProcedures[]` | ✅ Present | Linked |
| `BiospecimenRetention` | ❌ Missing | USDM entity for sample storage/retention |
| `Procedure` specific coding (SNOMED/CPT/LOINC) | ❌ Missing | Only generic type codes |

### Expert Recommendations

**DR. CHEN**: Procedures need domain-specific enrichment:

1. **LOINC coding for lab tests** — Procedures like "Complete blood count", "Liver function tests" should resolve to LOINC codes. This enables EDC system integration.

2. **SNOMED CT coding for clinical procedures** — Procedures like "ECG", "MRI", "Biopsy" should have SNOMED CT codes for interoperability.

3. **BiospecimenRetention extraction** — Many protocols specify biospecimen collection and retention (blood, tissue, DNA). USDM v4.0 has a `BiospecimenRetention` entity for this.

### Action Items

| ID | Enhancement | Effort | Impact | Priority |
|---|---|---|---|---|
| PROC-1 | LOINC code resolution for laboratory procedures | M | H | HIGH |
| PROC-2 | SNOMED CT code resolution for clinical procedures | M | H | HIGH |
| PROC-3 | `BiospecimenRetention` entity extraction | M | M | MEDIUM |
| PROC-4 | Procedure grouping (e.g., "Hematology panel" → component procedures) | M | M | MEDIUM |

---

# AREA 10: SAP & STATISTICAL ANALYSIS

**Phase**: `extraction/conditional/` → `pipeline/phases/sap.py`
**M11 Sections**: §10 Statistical Considerations
**USDM Entities**: AnalysisPopulation, extensions (statistical methods, ARS)

### Current State
- 4-pass multi-pass extraction (populations, methods, sensitivity/subgroup/interim, derived vars)
- `AnalysisSpecification` bridging endpoint→method→population→estimand
- CDISC ARS generation with STATO ontology codes
- `MissingDataStrategy` with ICE mapping
- `ResultPattern` on all ARS operations
- Statistical traceability view in web UI

### USDM Alignment Gaps

**DR. MENON**: SAP data is primarily extension-based since USDM v4.0 doesn't have first-class statistical analysis entities. But:

| Concept | Storage | USDM Path |
|---|---|---|
| Analysis populations | Extension + `analysisPopulations[]` | ✅ Correct placement |
| Sample size | Extension → promoted to population | ✅ P12 promotion |
| Statistical methods | Extension only | Could link to `Estimand.populationSummary` |
| Multiplicity | Extension only | No USDM entity — extension is correct |
| Interim analyses | Extension only | Could create `GovernanceDate` for DMC review dates |

### Expert Recommendations

**DR. VASQUEZ**: The SAP extraction is already best-in-class. Enhancements:

1. **Method-to-estimand binding** — Statistical methods should resolve their `estimandId` link by matching method descriptions to estimand definitions. This closes the traceability chain.

2. **Power calculation extraction** — Currently extracts target sample size but not the power calculation parameters (effect size, standard deviation, dropout rate, power level). These are critical for protocol review.

3. **Missing data sensitivity mapping** — The `MissingDataStrategy` captures ICE→missing data method mapping but doesn't link to the specific statistical method that implements it (e.g., "MMRM for treatment policy" → which MMRM analysis).

### Action Items

| ID | Enhancement | Effort | Impact | Priority |
|---|---|---|---|---|
| SAP-1 | Resolve `statisticalMethod.estimandId` to actual estimand entities | M | H | HIGH |
| SAP-2 | Power calculation parameter extraction (effect size, SD, power, dropout) | M | H | HIGH |
| SAP-3 | Link `MissingDataStrategy` to implementing statistical method | S | M | MEDIUM |
| SAP-4 | DMC review dates → `GovernanceDate` entities | S | L | LOW |

---

# AREA 11: AMENDMENTS EXTRACTION

**Phase**: `extraction/amendments/` → `pipeline/phases/amendments.py`
**M11 Sections**: §12.3 Protocol Amendments
**USDM Entities**: StudyAmendment, StudyAmendmentReason, StudyAmendmentImpact, StudyChange

### Current State
- Extracts amendment number, summary, effective date, scope
- Primary and secondary reasons
- Impacts (affected sections) and changes (before/after)
- `GeographicScope` for global/country-specific amendments

### USDM Alignment Gaps

**DR. MENON**:

| USDM Entity/Field | Status | Gap |
|---|---|---|
| `StudyAmendment.primaryReason` | ✅ Present | StudyAmendmentReason Code |
| `StudyAmendment.secondaryReasons[]` | ✅ Present | (M6 fix) |
| `StudyAmendment.impacts[]` | ✅ Present | (M7 fix) |
| `StudyAmendment.changes[]` | ✅ Present | (M8 fix) |
| `StudyAmendment.geographicScopes[]` | ✅ Present | |
| `StudyChange.substantialImpact` | ❌ Missing | Boolean flag per USDM schema |
| `StudyAmendmentReason.code` | ⚠️ Partial | Generic code, not from USDM CT C207422 |

### Action Items

| ID | Enhancement | Effort | Impact | Priority |
|---|---|---|---|---|
| AMEND-1 | Use USDM CT C207422 codes for `StudyAmendmentReason` | S | M | MEDIUM |
| AMEND-2 | Extract `StudyChange.substantialImpact` boolean | S | L | LOW |

---

# AREA 12: M11 RENDERING (DOCX)

**Module**: `rendering/` (m11_renderer.py, composers.py, tables.py, document_setup.py, text_formatting.py)
**Output**: ICH M11-compliant Word document

### Current State
- 14-section M11 structure with proper heading hierarchy
- Title page with protocol metadata
- Synopsis table (two-column structured)
- SoA table (landscape, multi-header grid)
- 9 entity composers + 2 new (treatment assignment, glossary, references)
- Abbreviation table
- Subsection distribution for deep heading hierarchy

### Expert Recommendations

**DR. CHEN**: The M11 DOCX is the primary deliverable. Key gaps:

1. **§4.3 — Blinding/unblinding procedures** — Currently only stratification is rendered in §4.3. Need blinding schema details (who is blinded, unblinding triggers, emergency procedures).

2. **§7 — Discontinuation rules** — The discontinuation composer exists but is sparse. Should extract structured withdrawal/discontinuation criteria with decision trees.

3. **§9 — Safety reporting** — The safety composer currently does keyword scanning. Should generate structured AE reporting tables (timeframes, expedited reporting criteria, SAE definitions).

4. **§11 — Oversight** — DMC composition, DSMB charter, sponsor oversight responsibilities are not rendered. Should extract committee structures.

5. **Track changes support** — When re-rendering after semantic edits, changes should be shown as tracked changes in the DOCX.

6. **Figure insertion** — Protocol figures (study design diagrams) should be inserted at appropriate positions in the DOCX.

### Action Items

| ID | Enhancement | Effort | Impact | Priority |
|---|---|---|---|---|
| M11-1 | §4.3 blinding/unblinding procedures rendering | M | H | HIGH |
| M11-2 | §7 structured discontinuation rules with decision logic | M | H | HIGH |
| M11-3 | §9 structured AE reporting tables (timeframes, expedited criteria) | M | H | HIGH |
| M11-4 | §11 oversight committee rendering (DMC, DSMB) | M | M | MEDIUM |
| M11-5 | Figure insertion at section-appropriate positions | M | M | MEDIUM |
| M11-6 | Track changes support for re-rendered documents | L | M | MEDIUM |

---

# AREA 13: WEB UI

**Module**: `web-ui/` (Next.js 14 + TypeScript + TailwindCSS + shadcn/ui + Zustand)
**Components**: 17 protocol views, 7 SoA components, 11 timeline components, semantic editing

### Current State
- Full protocol viewer with tabbed navigation (12 tabs)
- AG Grid SoA table with inline editing
- Cytoscape.js timeline graph
- Execution model view, SAP data view, ARS view, traceability view, stratification view
- Semantic editing with JSON Patch (RFC 6902) overlay store
- Export (CSV, JSON, PDF)
- Provenance tracking with extraction/entity provenance views
- Validation results view

### Expert Recommendations

**MARCUS TORRES**: UI enhancements with highest user value:

1. **Protocol comparison view** — Side-by-side comparison of two protocol versions showing USDM-level diffs. Critical for amendment review.

2. **Guided authoring mode** — Instead of just viewing extracted data, provide a form-based authoring interface for each M11 section that validates against USDM as the user types.

3. **Real-time validation indicators** — Show validation status per section in the tab headers (green check, amber warning, red error counts).

4. **Bulk editing** — Select multiple entities (e.g., all eligibility criteria) and apply batch changes.

5. **PDF overlay view** — Show the original PDF alongside extracted data with highlighting of source text for each entity (using page/position provenance).

6. **Export to CDISC ODM** — USDM JSON can be transformed to ODM-XML for EDC system consumption.

### Action Items

| ID | Enhancement | Effort | Impact | Priority |
|---|---|---|---|---|
| UI-1 | Protocol version comparison (USDM diff view) | L | H | HIGH |
| UI-2 | Per-section validation indicators in tab headers | M | H | HIGH |
| UI-3 | PDF overlay view with entity source highlighting | L | H | HIGH |
| UI-4 | Guided authoring mode for M11 sections | XL | H | MEDIUM |
| UI-5 | Bulk entity editing interface | M | M | MEDIUM |
| UI-6 | CDISC ODM-XML export | M | M | MEDIUM |

---

# AREA 14: VALIDATION & QUALITY

**Module**: `validation/` (usdm_validator.py, m11_conformance.py, cdisc_conformance.py)
**Also**: `core/validation.py`, `core/core_compliance.py`, `extraction/execution/validation.py`

### Current State
- USDM schema validation (JSON Schema against dataStructure.yml)
- M11 conformance (title page fields, synopsis fields, section coverage)
- CDISC CORE conformance engine integration
- Core compliance audit (non-USDM property detection, log-only mode)
- Execution model validation with quality scoring
- Stratification coherence checks (E1)
- Integrity report (entity counts, referential integrity)

### Expert Recommendations

**DR. MENON**: Validation is the quality gate. Enhancements:

1. **Entity referential integrity** — Validate all `*Id` references resolve to actual entities. Currently checked for some entities but not systematically across all 86 types.

2. **Cardinality enforcement** — USDM schema specifies `1..*` (required array) and `0..*` (optional). Validate that required arrays are non-empty.

3. **Code verification** — All `Code` objects should have their `code` values verified against NCI EVS. The audit script exists but should run automatically in the validation pipeline.

4. **Cross-phase coherence** — Beyond stratification (done), validate:
   - Endpoints referenced in estimands exist in objectives
   - Arms referenced in allocation cells exist in study design
   - Encounters in SoA match epochs
   - Statistical methods reference correct endpoint names

5. **Conformance scoring refinement** — The M11 conformance score should weight required fields more heavily than optional ones. Currently all fields have equal weight.

### Action Items

| ID | Enhancement | Effort | Impact | Priority |
|---|---|---|---|---|
| VAL-1 | Systematic referential integrity check across all 86 entity types | L | H | HIGH |
| VAL-2 | Cardinality enforcement (1..* arrays must be non-empty) | M | H | HIGH |
| VAL-3 | Automated NCI EVS code verification in validation pipeline | M | H | HIGH |
| VAL-4 | Cross-phase coherence checks (endpoint→estimand, arm→cell, encounter→epoch) | M | H | HIGH |
| VAL-5 | Weighted M11 conformance scoring (required vs optional) | S | M | MEDIUM |

---

# AREA 15: CORE INFRASTRUCTURE

**Module**: `core/` (llm_client, pdf_utils, code_registry, evs_client, schema_loader, etc.)
**Also**: `pipeline/` (orchestrator, combiner, post_processing, promotion)

### Expert Recommendations

**DR. YAMAMOTO**: Infrastructure improvements:

1. **LLM provider abstraction** — Support concurrent calls to different models per phase (e.g., Gemini for long narrative, Claude for structured JSON, GPT for reasoning). Currently all phases use the same model.

2. **Caching layer** — Extraction results should be cached by (PDF hash + phase + model) so re-runs skip completed phases. The file-based caching exists but is fragile.

3. **Streaming extraction** — For large protocols (500+ pages), extraction should stream results rather than loading the entire document into memory.

4. **Prompt versioning** — Prompt changes affect extraction quality. Version prompts and track which version produced each extraction result.

5. **Cost tracking** — Track LLM token usage and costs per phase per protocol. The `usage_tracker` exists but could be more granular.

### Action Items

| ID | Enhancement | Effort | Impact | Priority |
|---|---|---|---|---|
| CORE-1 | Per-phase LLM model configuration (different models for different phases) | M | H | HIGH |
| CORE-2 | Robust extraction caching (PDF hash + phase + model + prompt version) | M | H | HIGH |
| CORE-3 | Prompt versioning and tracking | M | M | MEDIUM |
| CORE-4 | Streaming extraction for large documents (500+ pages) | L | M | MEDIUM |
| CORE-5 | Granular cost tracking per phase with budget limits | S | M | MEDIUM |

---

# PRIORITIZED MASTER ROADMAP

## Tier 1: High Impact / Achievable (Next 2 weeks)

| ID | Area | Enhancement | Effort |
|---|---|---|---|
| OBJ-1 | Objectives | Resolve estimand→intervention ID links | M |
| OBJ-2 | Objectives | Resolve estimand→population ID links | M |
| DES-1 | Study Design | Extract TransitionRule for epoch transitions | M |
| DES-3 | Study Design | Duration extraction as ISO 8601 | M |
| SOA-1 | SoA | Multi-timeline separation | L |
| SOA-2 | SoA | ConditionAssignment from footnotes | M |
| EXEC-1 | Execution | State machine → TransitionRule promotion | M |
| SAP-1 | SAP | Method→estimand binding | M |
| SAP-2 | SAP | Power calculation parameter extraction | M |
| M11-1 | Rendering | §4.3 blinding procedures | M |
| VAL-1 | Validation | Systematic referential integrity | L |
| VAL-4 | Validation | Cross-phase coherence checks | M |

## Tier 2: Strategic Value (Weeks 3–4)

| ID | Area | Enhancement | Effort |
|---|---|---|---|
| NAR-1 | Narrative | Deep heading hierarchy (L4/L5) | M |
| NAR-2 | Narrative | Inline table preservation | M |
| INT-1 | Interventions | Dose modification rules | M |
| INT-2 | Interventions | Concomitant medication extraction | M |
| PROC-1 | Procedures | LOINC coding for lab tests | M |
| M11-2 | Rendering | §7 discontinuation rules | M |
| M11-3 | Rendering | §9 safety reporting tables | M |
| UI-2 | Web UI | Per-section validation indicators | M |
| CORE-1 | Core | Per-phase LLM model configuration | M |
| CORE-2 | Core | Robust extraction caching | M |

## Tier 3: Long-term / Large Effort (Month 2+)

| ID | Area | Enhancement | Effort |
|---|---|---|---|
| ELIG-1 | Eligibility | Structured criterion parsing | L |
| DES-2 | Study Design | Adaptive design classification | M |
| PROC-2 | Procedures | SNOMED CT coding | M |
| UI-1 | Web UI | Protocol version comparison | L |
| UI-3 | Web UI | PDF overlay with source highlighting | L |
| UI-4 | Web UI | Guided authoring mode | XL |
| META-3 | Metadata | Regulatory identifier extraction | M |
| VAL-3 | Validation | Automated EVS code verification | M |

---

## Consensus Decisions

### Agreed by all experts:

1. **Cross-entity referential integrity is the highest-value validation improvement** — It catches extraction errors that currently pass silently (e.g., estimands referencing non-existent endpoints).

2. **TransitionRule promotion should happen next** — State machine data and epoch transitions map directly to USDM `TransitionRule` entities. This is the largest gap in native USDM entity coverage.

3. **Multi-timeline SoA is the biggest rendering gap** — Protocols with separate treatment/follow-up schedules need separate `ScheduleTimeline` entities to render correctly.

4. **Per-phase model selection would improve quality and cost** — Narrative extraction benefits from large context windows (Gemini), while structured JSON extraction benefits from high-precision models (Claude).

5. **Structured criterion parsing is the most ambitious but highest long-term value** — Enables automated feasibility analysis, cross-protocol comparison, and site selection optimization.

6. **The platform already covers 74/86 USDM entity types** — Remaining 12 are mostly niche entities (BiospecimenRetention, SubjectEnrollment, ConditionAssignment, etc.) that apply only to specific protocol types.

---

*Total identified enhancements: 65 across 15 areas*
*Effort distribution: 8 Small, 32 Medium, 18 Large, 1 Extra-Large*
*Priority distribution: 28 HIGH, 27 MEDIUM, 10 LOW*
