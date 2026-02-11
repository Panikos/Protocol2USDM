# Protocol2USDM — AGENTS.md

## Project Overview

Protocol2USDM is an AI-powered pipeline that extracts structured data from clinical protocol PDFs and produces USDM v4.0-compliant JSON, ICH M11-formatted DOCX documents, and a web-based protocol viewer/editor.

**Tech Stack:**
- **Backend**: Python 3.11 (extraction pipeline, LLM orchestration, rendering)
- **Web UI**: Next.js 14 + TypeScript + TailwindCSS + Zustand + shadcn/ui
- **Data Model**: USDM v4.0 (CDISC, 2024-09-27) — 86 entity types
- **Regulatory**: ICH M11 Guideline, Template & Technical Specification (Step 4, 19 Nov 2025)
- **Schema Source**: `core/schema_cache/dataStructure.yml` (official CDISC DDF-RA YAML)
- **Visualization**: AG Grid (SoA table), Cytoscape.js (timeline graph)

---

## 1. Standards & Regulatory Framework

### 1.1 USDM v4.0 (Unified Study Definitions Model)
CDISC's data model for representing clinical study definitions. Our schema YAML defines **86 entity types** with NCI C-codes, cardinality, and relationships.

**Key entity categories:**
| Category | Entities | NCI C-codes |
|----------|----------|-------------|
| **Core** | Study, StudyVersion, StudyDesign, StudyDefinitionDocument | C63536, C142184 |
| **Design** | StudyArm (C174451), StudyEpoch, StudyCell, StudyElement, StudyCohort | C174266–C174268 (arm types) |
| **Population** | StudyDesignPopulation, EligibilityCriterion (C25532/C25370), EligibilityCriterionItem | C25532 (Inclusion), C25370 (Exclusion) |
| **Objectives** | Objective (C85826/C85827/C163559), Endpoint, Estimand, IntercurrentEvent | C85826 (Primary), C85827 (Secondary) |
| **SoA** | Activity (C71473), Encounter, ScheduleTimeline, ScheduledActivityInstance, Timing, ScheduledDecisionInstance | C71473, C25426 |
| **Interventions** | StudyIntervention, Administration (C25409), AdministrableProduct (C215492), Ingredient, Substance | C25409 |
| **Narrative** | NarrativeContent, NarrativeContentItem, Abbreviation (C42610) | C42610 |
| **Metadata** | StudyTitle, StudyIdentifier, Organization, GovernanceDate, Address | C70793 (Sponsor) |
| **Coded** | Code, AliasCode, CommentAnnotation, ExtensionAttribute, Range, Quantity, QuantityRange, Duration | — |
| **Safety** | BiospecimenRetention, Condition, ConditionAssignment, TransitionRule | — |
| **Amendments** | StudyAmendment, StudyAmendmentReason, StudyAmendmentImpact, StudyChange | — |
| **Other** | Masking, Indication, AnalysisPopulation, Procedure, MedicalDevice, Characteristic | — |

**Entity placement hierarchy (per `dataStructure.yml`):**
```
Study
├── versions[] → StudyVersion
│   ├── titles[], studyIdentifiers[], organizations[]
│   ├── eligibilityCriterionItems[] (NOT on studyDesign)
│   ├── narrativeContentItems[]
│   ├── abbreviations[], conditions[], amendments[]
│   ├── studyInterventions[] (NOT on studyDesign)
│   ├── administrableProducts[], medicalDevices[]
│   └── studyDesigns[] → StudyDesign
│       ├── arms[], epochs[], studyCells[], elements[]
│       ├── population → StudyDesignPopulation
│       ├── objectives[], endpoints[], estimands[]
│       ├── activities[] (each has definedProcedures[])
│       ├── encounters[]
│       ├── indications[] (NOT on study root)
│       ├── analysisPopulations[]
│       └── scheduleTimelines[]
│           ├── timings[] (NOT at root)
│           └── exits[]
├── documentedBy → StudyDefinitionDocumentVersion
│   └── versions[0].contents[] → NarrativeContent
└── studyIdentifiers[]
```

**Schema pinning**: URL pinned to `SCHEMA_TAG = "v4.0"`, cached with SHA256 hash + download timestamp. `get_schema_version_info()` returns version metadata. Regenerate types with `python scripts/generate_ts_types.py`.

### 1.2 ICH M11 (Clinical Electronic Structured Harmonised Protocol — CeSHarP)
Step 4 adopted 19 November 2025. Three deliverables:
1. **Guideline** (6pp) — design principles, scope (interventional trials, all phases/therapeutic areas)
2. **Template** (67pp) — 14 numbered sections with heading hierarchy, controlled terminology
3. **Technical Specification** (245pp) — every data element with NCI C-codes, conformance (Required/Optional/Conditional), cardinality, business rules, OIDs

**14 canonical sections**: §1 Protocol Summary, §2 Introduction, §3 Objectives & Estimands, §4 Trial Design, §5 Population, §6 Interventions, §7 Discontinuation, §8 Assessments, §9 AE/Safety, §10 Statistics, §11 Oversight, §12 Appendix: Supporting, §13 Appendix: Glossary, §14 Appendix: References

**Heading hierarchy**: L1=14pt BOLD ALL CAPS, L2=14pt Bold, L3/L4/L5=12pt Bold. Level determined by dot count in section number (e.g., `10.4.1.1` = 4 dots = L4).

### 1.3 Related ICH Guidelines
| Guideline | Scope | M11 Sections | USDM Entities Affected |
|-----------|-------|--------------|----------------------|
| **ICH E9(R1)** | Estimand framework — 5 mandatory attributes | §3, §10 | Estimand, IntercurrentEvent, Endpoint |
| **ICH E6(R2)** | GCP — eligibility, consent, safety reporting | §5, §7, §9, §11 | EligibilityCriterion, NarrativeContent |
| **ICH E8(R1)** | Study design quality, fit-for-purpose | §4 | StudyDesign, StudyArm, Masking |
| **ICH E17** | Multi-regional trial design, sample size | §4, §5, §10 | StudyDesignPopulation, StudySite |

### 1.4 CDISC Controlled Terminology
NCI C-codes used throughout. Key codelists:
- **Trial Phase**: C15600–C15603, C49686 (Phase I–IV)
- **Study Type**: C98388 (Interventional), C142615 (Observational)
- **Arm Type**: C174266 (Investigational), C174268 (Placebo), C174267 (Active Comparator)
- **Blinding**: C15228 (Open Label → C49659), C15479 (Single), C15327 (Double), C66959 (Triple)
- **Objective Level**: C85826 (Primary), C85827 (Secondary), C163559 (Exploratory)
- **Endpoint Level**: C98772 (Primary), C98781 (Secondary), C98724 (Exploratory)
- **Sex**: C16576 (Female), C20197 (Male)
- **Eligibility Category**: C25532 (Inclusion), C25370 (Exclusion)

- **Intervention Type** (ICH M11): C1909 (Drug), C307 (Biological), C16830 (Device), C1505 (Dietary Supplement), C15329 (Procedure), C15313 (Radiation), C17649 (Other)

Codes are managed in `core/code_registry.py` (centralized CodeRegistry singleton), verified via `core/code_verification.py` (CodeVerificationService with EVS_VERIFIED_CODES), and enriched via `core/evs_client.py` (NCI EVS REST API with 30-day cache). The `scripts/generate_code_registry.py` pipeline auto-verifies supplementary codes at generation time.

### 1.5 CDISC ARS (Analysis Results Standard)
SAP extraction includes CDISC ARS linkage via `extraction/conditional/ars_generator.py`:
- Full ARS model: `ReportingEvent`, `Analysis`, `AnalysisSet`, `AnalysisMethod`, `Operation`
- STATO ontology mapping for statistical methods (ANCOVA→STATO:0000029, MMRM→STATO:0000325, etc.)
- ARS operation ID patterns: `Mth01_ContVar_Ancova`, `Mth01_TTE_KaplanMeier`, etc.

---

## 2. Architecture

### 2.1 Pipeline Phases
The extraction pipeline (`pipeline/orchestrator.py`) uses a registry-driven phase system with dependency resolution and parallel execution waves. The combine/post-processing logic is decomposed into focused modules:
- **`pipeline/orchestrator.py`** (332 lines) — `PipelineOrchestrator` class, dependency graph, parallel wave execution
- **`pipeline/combiner.py`** (420 lines) — `combine_to_full_usdm()`, USDM defaults, SoA data integration
- **`pipeline/integrations.py`** (289 lines) — SAP/sites integration, content reference resolution, estimand→population reconciliation
- **`pipeline/post_processing.py`** (~660 lines) — Entity reconciliation (epochs, encounters, activities), activity source marking, procedure linking, SoA footnotes, cohort→population linking, UNS tagging
- **`pipeline/promotion.py`** (260 lines) — Extension→USDM promotion rules (4 rules: sample size, completers, sex, age)

| Phase | Module | M11 §§ | Key USDM Entities | Dependencies |
|-------|--------|--------|-------------------|--------------|
| metadata | `extraction/metadata/` | Title page | Study, StudyVersion, StudyIdentifier, Organization | None |
| narrative | `extraction/narrative/` | §1–§14 text | NarrativeContent, NarrativeContentItem, Abbreviation | None |
| objectives | `extraction/objectives/` | §3 | Objective, Endpoint, Estimand, IntercurrentEvent | metadata |
| studydesign | `extraction/studydesign/` | §4 | StudyDesign, Arms, Epochs, Cells, Elements | None |
| eligibility | `extraction/eligibility/` | §5 | EligibilityCriteria, StudyDesignPopulation | metadata |
| interventions | `extraction/interventions/` | §6 | StudyIntervention, Administration, AdministrableProduct | metadata, studydesign |
| soa | `extraction/soa/` | §1.3 | ScheduleTimeline, Activities, Encounters, Timings | None |
| execution | `extraction/execution/` | §1.3 (enrichment) | ScheduledActivityInstance, TransitionRule, Condition | metadata, studydesign |
| procedures | `extraction/procedures/` | §8 | Activity, Procedure | None |
| advanced | `extraction/advanced/` | §8–§11 | Various | None |
| amendments | `extraction/amendments/` | §12.3 | StudyAmendment, StudyAmendmentReason | None |
| sap | `extraction/conditional/` | §10 | AnalysisPopulation, SampleSizeCalculation | None |
| sites | `extraction/conditional/` | — | StudySite, Organization | None |
| doc_structure | `extraction/document_structure/` | — | DocumentContentReference | None |

**Parallel execution**: Independent phases run concurrently in waves. `PipelineContext` uses `snapshot()` and `merge_from()` for thread isolation. Dependencies are auto-enforced transitively via `_enforce_dependencies()`.

**Phase anatomy**: Each phase has `schema.py` (Pydantic), `extractor.py` (LLM calls), `prompts.py`, and optionally `combiner.py`. All registered via `BasePhase` subclass in `pipeline/phases/`.

**Narrative extraction (two-strategy approach)**: The narrative phase (`extraction/narrative/extractor.py`) uses a two-strategy approach to achieve 14/14 M11 section coverage:
- **Strategy A (deterministic, no LLM cost)**: `_discover_sections_from_pdf()` scans the full PDF for numbered section headings the LLM missed from the TOC. Discovers sections like §7 Discontinuation, §8 Assessments, §9 Safety that appear beyond the first 30 pages. Uses `_discovered_page0` hints as fallback in `_find_section_pages()` for multi-line headings.
- **Strategy B (targeted LLM, only for gaps)**: `_fill_m11_gaps()` detects which M11 sections are still empty after Strategy A via `_detect_m11_gaps()`, then sends relevant PDF pages to the LLM with focused prompts per M11 section. Only fires for sections §7+ that have guidance defined in `_M11_SECTION_GUIDANCE`.
- **Bug fixes**: `_compute_section_page_ranges()` now handles multiple sections sharing a page (inverted range fix). `_find_section_pages()` Pass 3 uses discovery page hints bypassing TOC filtering for multi-line headings.

### 2.2 Execution Model (10-Step Promotion)
The execution model (`extraction/execution/`) enriches the base USDM with temporal and operational semantics. The `ExecutionModelPromoter` runs 10 promotion steps, each fault-isolated:

| Step | Input | Output USDM Entity |
|------|-------|-------------------|
| 1. Anchor Promotion | `time_anchors[]` | `ScheduledActivityInstance` with anchor metadata |
| 2. Repetition Expansion | `repetitions[]` + `activity_bindings[]` | Multiple `ScheduledActivityInstance` per occurrence |
| 3. Dosing Normalization | `dosing_regimens[]` | `Administration` linked to `StudyIntervention` |
| 4. Visit Window Enrichment | `visit_windows[]` | `Timing.windowLower/windowUpper` |
| 5. Reference Reconciliation | dangling `relativeFromScheduledInstanceId` | Fixed references |
| 6. Traversal Constraints | `traversal_constraints[]` | `StudyEpoch.previousId/nextId` chain |
| 7. Footnote Conditions | `footnote_conditions[]` | `Condition` + `ScheduledDecisionInstance` |
| 8. State Machine | `SubjectStateMachine` | `TransitionRule` on `Encounter` |
| 9. Endpoint Algorithms | `endpoint_algorithms[]` | `Estimand` with algorithm extension |
| 10. Titration Schedules | `titration_schedules[]` | `StudyElement` with `TransitionRule` |

**Key principle**: Core USDM is self-sufficient without parsing extensions. Extensions provide additional detail and debug transparency.

### 2.3 Extension→USDM Promotion
After all phases combine, `_promote_extensions_to_usdm()` moves extension data to proper USDM fields:

| Rule | Source | Target | Condition |
|------|--------|--------|-----------|
| 1 | SAP `sampleSizeCalculations[].targetSampleSize` | `population.plannedEnrollmentNumber` | target empty |
| 2 | SAP `sampleSizeCalculations[].plannedCompleters` | `population.plannedCompletionNumber` | target empty |
| 3 | Eligibility criteria text (regex) | `population.plannedSex` | target empty |
| 4 | Eligibility criteria text (regex) | `population.plannedAge` | target empty |

**Principle**: Explicit extraction always wins over inference. Idempotent. Logged.

### 2.4 Unified Reconciliation Framework
`core/reconciliation/` merges entities from multiple extraction sources:

| Reconciler | Entity | Key Features |
|------------|--------|--------------|
| **EpochReconciler** | StudyEpoch | Main/sub categorization, traversal sequence, CDISC type inference |
| **ActivityReconciler** | Activity | Type inference, group merging, conditional logic from footnotes |
| **EncounterReconciler** | Encounter | Visit windows, study day extraction, timing labels |

Priority: SoA (10) → Scheduling (15) → Procedures (20) → Execution/Traversal (25) → Footnotes/SAP (30).

### 2.5 Dual-Path Rendering
The M11 renderer (`rendering/m11_renderer.py`) uses two independent content paths:
- **Extractors**: Pull narrative text from PDF → map to M11 sections via 7-pass mapper
- **Composers**: Generate prose from USDM entities (objectives, arms, epochs, interventions, etc.)

9 entity composers wired: §1 (synopsis), §3 (objectives), §3 (estimands table), §4 (design), §5 (eligibility), §6 (interventions), §7 (discontinuation), §9 (safety), §10 (statistics).

**Future**: USDM-first authoring — composers produce complete M11 documents without source PDFs.

### 2.6 Validation Pipeline
Three-tier validation runs after extraction:

| Validator | File | What It Checks |
|-----------|------|---------------|
| **USDM Schema** | `validation/usdm_validator.py` | Entity structure against `dataStructure.yml` |
| **M11 Conformance** | `validation/m11_conformance.py` | Title page (12 fields), synopsis (18 fields), section coverage (14 sections) |
| **CDISC CORE** | `validation/cdisc_conformance.py` | CDISC conformance rules via local CORE engine or API |

**CDISC CORE auto-install**: On first pipeline run, `ensure_core_engine()` downloads the appropriate pre-built executable from GitHub releases (`cdisc-org/cdisc-rules-engine`). Supports Windows, Linux (Ubuntu), macOS (Intel + Apple Silicon). Version tracked in `tools/core/bin/.version.json`. Update via `python tools/core/download_core.py --update`.

Normalization pipeline: Type inference → UUID conversion → Provenance conversion → NCI enrichment → Validation → CDISC CORE.

---

## 3. Key Files

### 3.1 Pipeline & Core
| File | Purpose |
|------|---------|
| `main_v3.py` | CLI entry point, `--complete` mode, run manifest generation |
| `pipeline/orchestrator.py` | Phase orchestration, dependency resolution, parallel execution, USDM assembly, extension→USDM promotion |
| `pipeline/base_phase.py` | `BasePhase` abstract class, `PhaseConfig`, `PhaseResult` dataclasses |
| `pipeline/phase_registry.py` | `PhaseRegistry` singleton, `register_phase()` decorator |
| `extraction/pipeline_context.py` | `PipelineContext` with `snapshot()`/`merge_from()` for parallel safety |
| `core/m11_usdm_mapping.yaml` | Single source of truth: 14 M11 sections, USDM entity paths, conformance rules, extractor coverage matrix, 6 regulatory frameworks |
| `core/m11_mapping_config.py` | `M11MappingConfig` dataclass + `get_m11_config()` singleton (`@lru_cache`) |
| `core/usdm_schema_loader.py` | Schema downloader/parser, `EntityDefinition` objects, pinned to v4.0 |
| `core/usdm_types_generated.py` | 86+ Python dataclasses with idempotent UUID generation |
| `core/usdm_types.py` | Unified interface: official USDM types + internal extraction types |
| `core/code_registry.py` | Centralized CodeRegistry singleton — USDM CT + supplementary codelists |
| `core/code_verification.py` | CodeVerificationService with EVS_VERIFIED_CODES for offline validation |
| `core/terminology_codes.py` | Legacy NCI code constants (being migrated to CodeRegistry) |
| `core/evs_client.py` | NCI EVS REST API client with 30-day cache |
| `core/schema_prompt_generator.py` | LLM prompt generator from schema YAML |
| `core/constants.py` | Pipeline constants: USDM_VERSION, DEFAULT_MODEL, OUTPUT_FILES, REASONING_MODELS |
| `core/provenance.py` | `ProvenanceTracker` for extraction source tracking |
| `tools/core/download_core.py` | CDISC CORE auto-installer: OS detection, GitHub release download, `--update`/`--force`/`--status` CLI |

### 3.2 Extraction
| File | Purpose |
|------|---------|
| `extraction/narrative/m11_mapper.py` | 7-pass protocol→M11 section mapper, M11_TEMPLATE, M11_SUBHEADINGS |
| `extraction/narrative/extractor.py` | Full-text extraction, sub-section splitting, abbreviation extraction |
| `extraction/execution/execution_model_promoter.py` | 10-step promotion: anchors, repetitions, dosing, windows, transitions |
| `extraction/execution/reconciliation_layer.py` | Entity resolution, crossover promotion, integrity issue classification |
| `extraction/execution/entity_resolver.py` | LLM-based semantic entity resolution (abstract concepts → protocol entities) |
| `extraction/execution/pipeline_integration.py` | Integration into enrichment flow |
| `extraction/conditional/sap_extractor.py` | SAP extraction: analysis populations, statistical methods, sample size |
| `extraction/conditional/ars_generator.py` | CDISC ARS model generation from SAP data |

### 3.3 Rendering & Validation
| File | Purpose |
|------|---------|
| `rendering/m11_renderer.py` | M11 DOCX: title page, TOC, 14 sections, 9 composers, SoA table, headers/footers |
| `validation/m11_conformance.py` | M11 conformance: title page (12 fields), synopsis (18 fields), section coverage |
| `validation/usdm_validator.py` | USDM schema validation against `usdm` Pydantic package |
| `validation/cdisc_conformance.py` | CDISC CORE engine runner (local or API) |

### 3.4 Web UI
| File | Purpose |
|------|---------|
| `web-ui/stores/protocolStore.ts` | Zustand store for USDM protocol data |
| `web-ui/stores/semanticStore.ts` | Draft/patch management, undo/redo stack |
| `web-ui/stores/soaEditStore.ts` | SoA table editing: cell marks, activity/encounter names |
| `web-ui/stores/editModeStore.ts` | Edit mode toggle |
| `web-ui/stores/toastStore.ts` | Toast notification system |
| `web-ui/stores/overlayStore.ts` | Overlay layout state |
| `web-ui/lib/types/usdm.generated.ts` | Auto-generated TS types from USDM schema (68 interfaces) |
| `web-ui/lib/types/index.ts` | Runtime-safe USDM interfaces with `[key: string]: unknown` |
| `web-ui/lib/semantic/schema.ts` | Zod schemas, IMMUTABLE_PATHS, validation functions |
| `web-ui/lib/semantic/storage.ts` | File operations, hashing, archiving |
| `web-ui/lib/semantic/patcher.ts` | JSON Patch application via fast-json-patch |
| `web-ui/hooks/usePatchedUsdm.ts` | Hook: applies draft patches on top of raw USDM |
| `web-ui/hooks/useUnsavedChangesGuard.ts` | Beforeunload guard for unsaved edits |
| `web-ui/components/semantic/` | EditableField, EditableObject, EditableList, EditableCodedValue, DiffView |
| `web-ui/components/protocol/EpochTimelineChart.tsx` | Gantt-style epoch visualization |

---

## 4. USDM Schema Navigation

### 4.1 Common Entity Paths
| Path | Entity | Description |
|------|--------|-------------|
| `studyDesigns[0].arms[]` | StudyArm | Treatment arms with type codes |
| `studyDesigns[0].epochs[]` | StudyEpoch | Trial periods with previousId/nextId chain |
| `studyDesigns[0].studyCells[]` | StudyCell | Arm×Epoch intersection matrix |
| `studyDesigns[0].population` | StudyDesignPopulation | Demographics: plannedAge (Range), plannedEnrollmentNumber (QuantityRange), plannedSex (Code[]) |
| `studyDesigns[0].objectives[]` | Objective | With level Code, endpoints[], estimands[] |
| `studyDesigns[0].activities[]` | Activity | With definedProcedures[], childIds[], nextId/previousId |
| `studyDesigns[0].encounters[]` | Encounter | Visits with epochId extension, transitionStartRule/EndRule |
| `studyDesigns[0].scheduleTimelines[]` | ScheduleTimeline | With timings[], instances[], exits[] |
| `studyDesigns[0].indications[]` | Indication | Disease/condition with MedDRA codes |
| `studyDesigns[0].analysisPopulations[]` | AnalysisPopulation | ITT, Per Protocol, Safety |
| `studyDesigns[0].blindingSchema` | AliasCode | Open/Single/Double/Triple Blind |
| `studyDesigns[0].randomizationType` | Code | Randomized/Non-Randomized |
| `studyDesigns[0].model` | Code | Parallel/Crossover/Factorial/Sequential |
| `studyDesigns[0].trialPhase` | AliasCode | Phase I–IV |
| `versions[0]` | StudyVersion | versionIdentifier, effectiveDate, rationale |
| `versions[0].titles[]` | StudyTitle | Official, Short, Acronym |
| `versions[0].studyIdentifiers[]` | StudyIdentifier | NCT, EudraCT, Sponsor ID |
| `versions[0].organizations[]` | Organization | Sponsor, CRO (with legalAddress) |
| `versions[0].studyInterventions[]` | StudyIntervention | (NOT on studyDesign) |
| `versions[0].administrableProducts[]` | AdministrableProduct | (NOT at root) |
| `versions[0].narrativeContentItems[]` | NarrativeContentItem | Sub-section text |
| `versions[0].abbreviations[]` | Abbreviation | abbreviatedText + expandedText |
| `versions[0].conditions[]` | Condition | Scheduling conditions |
| `versions[0].amendments[]` | StudyAmendment | Protocol amendments |
| `documentedBy.versions[0].contents[]` | NarrativeContent | M11 section narrative text |

### 4.2 USDM Type Patterns
```python
# Code (CDISC Controlled Terminology)
{"code": "C49488", "codeSystem": "http://www.cdisc.org",
 "codeSystemVersion": "2024-09-27", "decode": "Double Blind",
 "instanceType": "Code"}

# AliasCode (multiple code systems)
{"standardCode": {"code": "C49488", "decode": "Phase III"},
 "standardCodeAliases": [], "instanceType": "AliasCode"}

# QuantityRange (enrollment, completers)
{"maxValue": 200, "unit": {"code": "C25613", "decode": "Participants"},
 "instanceType": "QuantityRange"}

# Range (age)
{"minValue": 18, "maxValue": 75,
 "unit": {"code": "C29848", "decode": "Year"},
 "instanceType": "Range"}
```

### 4.3 Extension Attributes
Extensions store data that doesn't fit USDM v4.0 natively. Namespace: `https://protocol2usdm.io/extensions/`

Key extensions:
| Extension | Attached To | Purpose |
|-----------|-------------|---------|
| `x-executionModel-timeAnchors` | StudyDesign | Time anchor metadata |
| `x-executionModel-repetitions` | StudyDesign | Repetition patterns |
| `x-executionModel-visitWindows` | StudyDesign | Visit window bounds |
| `x-executionModel-stateMachine` | StudyDesign | Subject state machine |
| `x-executionModel-dosingRegimens` | StudyDesign | Dosing regimen details |
| `x-sap-statistical-methods` | StudyDesign | STATO-mapped analysis methods |
| `x-sap-multiplicity-adjustments` | StudyDesign | Type I error control |
| `x-sap-sample-size-calculations` | StudyDesign | Power/sample size assumptions |
| `soaFootnoteRef` | Activity | Links to SoA footnote letters |
| `epochId` | Encounter | Links encounter to its epoch |
| `x-encounterUnscheduled` | Encounter | `valueBoolean: true` for event-driven / UNS visits |
| `x-encounterTimingLabel` | Encounter | Original timing string from SoA header |

#### Unscheduled Visit (UNS) Handling
Encounters whose names match `UNS`, `Unscheduled`, `Unplanned`, `Ad Hoc`, `PRN`, `As Needed`, or `Event-Driven` are automatically tagged with `x-encounterUnscheduled: true` via:
1. **Extraction** — `EncounterReconciler._create_contribution()` calls `is_unscheduled_encounter()` (regex in `core/reconciliation/encounter_reconciler.py`)
2. **Post-processing** — `tag_unscheduled_encounters()` in `pipeline/post_processing.py` catches any encounters missed during reconciliation (safety net)
3. **UI** — `toSoATableModel.ts` reads the extension into `SoAColumn.isUnscheduled`; `SoAGrid.tsx` renders unscheduled columns with dashed amber borders, italic headers, ⚡ suffix, and amber-tinted cells
4. **Scheduling** — `TransitionType.UNSCHEDULED_VISIT` in `extraction/scheduling/schema.py` models UNS as a reentrant branch (medium-term: promote to `ScheduledDecisionInstance`)

### 4.4 Internal Extraction Types (not official USDM)
| Type | Purpose | Converts To |
|------|---------|-------------|
| `PlannedTimepoint` | SoA column representation | `Timing` |
| `ActivityTimepoint` | SoA tick/matrix cell | `ScheduledActivityInstance` |
| `ActivityGroup` | Row section header (USDMIG concept) | `Activity` with `childIds` |
| `HeaderStructure` | Vision extraction anchor | Discarded after use |
| `Timeline` | Extraction container | `StudyDesign` |

---

## 5. Conventions & Rules

### 5.1 Code Style
- Python: No trailing whitespace, type hints on public functions, docstrings on classes/public functions
- TypeScript: Strict mode, no `any` types in production code, prefer interfaces over type aliases for USDM entities
- Comments: Do not add or remove comments unless explicitly asked

### 5.2 Anti-Patterns — MUST AVOID
1. **No protocol-specific hardcoding**: All solutions must be abstract enough to work with any clinical protocol, not just the Wilson's protocol (NCT04573309) used for testing
2. **No extraction logic in composers**: Composers read from USDM entities; they do not parse PDF text or call LLMs. If a composer is scanning narrative text for keywords, that's an extractor's job that hasn't been built yet.
3. **No inline type definitions in stores**: Use generated types from `@/lib/types`
4. **No duplicate data sources**: `protocol_usdm.json` is the single source of truth; provenance is separate
5. **No entity placement violations**: Follow `dataStructure.yml` hierarchy — e.g., `studyInterventions` on `StudyVersion` not `StudyDesign`
6. **No hardcoded NCI codes in extractors**: Use `core/code_registry.py` (or `core/terminology_codes.py` for legacy constants)
7. **No validation-by-deletion**: Never remove entities to make validation pass. Fix at the source or add explicit exceptions with documented rationale.
8. **No silent data loss**: Prefer failing with actionable errors over silently dropping data. Partial outputs must be clearly marked as partial.

### 5.3 M11 DOCX Formatting (ICH M11 Template, Step 4, Nov 2025)
- **Font**: Times New Roman throughout
- **Body**: 11pt, 1.15 line spacing, 6pt after paragraph
- **L1 (§N)**: 14pt BOLD ALL CAPS (via `all_caps=True` style, NOT `.upper()`)
- **L2 (§N.N)**: 14pt Bold
- **L3 (§N.N.N)**: 12pt Bold
- **L4 (§N.N.N.N)**: 12pt Bold
- **L5 (§N.N.N.N.N)**: 12pt Bold (capped at level 5)
- **Margins**: 1 inch all sides, Letter size
- **Page breaks**: Between §1–§11 only; appendices §12–§14 flow continuously
- **TOC**: Real Word TOC field code (updates on open)
- **Headers**: Protocol ID (left), CONFIDENTIAL (right)
- **Footers**: Page X of Y (centered)

### 5.4 Data Safety
- Protocol documents may contain sensitive clinical content. Do not leak raw protocol text into logs by default.
- Use structured logging; redact long free-text fields in debug output.
- Never commit real clinical documents, site lists, SAPs, or extracted outputs containing patient/site info.
- API keys must be in environment variables, never in code or config files checked into git.

### 5.5 LLM Guardrails
- **Treat LLM output as untrusted input** — always validate before use.
- Validation chain: (1) JSON parse → (2) required fields present → (3) schema/type checks.
- Prefer constrained prompts: explicit JSON schema, allowed enums, examples.
- Enforce strict JSON-only outputs; reject responses containing explanations mixed with data.
- Use bounded retries only (max 3). If retries fail, return a clear error object — never loop indefinitely.
- When reconciling entities across phases, prioritize ID preservation and traceability.

### 5.6 Parallel Safety
- No hidden shared mutable state between phases. Use `PipelineContext.snapshot()` / `merge_from()`.
- No non-deterministic writes to shared output paths during parallel execution.
- Write outputs atomically (temp file + rename) where appropriate.
- Use clear, deterministic merge rules for combined outputs (priority-based reconciliation).

### 5.7 Testing
- **Regression tests**: `tests/test_m11_regression.py` — renders DOCX for golden protocols
- **Unit tests**: `tests/test_core_modules.py`, `tests/test_execution_model.py`, etc.
- **Conformance**: M11 conformance report auto-generated alongside DOCX output
- **EVS verification**: `tests/verify_evs_codes.py` — verify NCI codes against NIH EVS API
- **Test data**: `semantic/NCT04573309_Wilsons_Protocol_*/history/protocol_usdm_*.json`
- **Trial inputs**: `input/trial/NCT*/` directories (30 trials) with PDF + metadata
- **LLM mocking**: Mock LLM calls and external APIs in unit tests by default. Use recorded fixtures / golden JSON outputs for deterministic tests.
- **Regression discipline**: When fixing a bug, add a regression test that fails pre-fix and passes post-fix.
- **Phase integration tests**: Prefer small integration tests around phases: input fixture → phase run → validated output.

### 5.8 Web UI Architecture
- **Framework**: Next.js 14 (App Router)
- **State**: 6 Zustand stores (protocolStore, semanticStore, soaEditStore, editModeStore, overlayStore, toastStore)
- **Editing**: JSON Patch (RFC 6902) via fast-json-patch, undo/redo stack, `usePatchedUsdm()` hook
- **Components**: 10 component directories — semantic editors, SoA grid, timeline graph, documents, overlay, provenance, quality
- **Types**: Auto-generated from USDM YAML via `scripts/generate_ts_types.py` → 68 interfaces
- **Storage**: File-based (`semantic/<protocolId>/drafts/`, `published/`, `history/`)
- **Tabs**: 21+ tabs covering every USDM domain (overview, eligibility, objectives, design, interventions, amendments, extensions, entities, procedures, sites, footnotes, schedule, narrative, quality, validation, documents, intermediate, SoA, timeline, provenance, ARS)
- **APIs**: `web-ui/app/api/protocols/[id]/` — semantic draft/publish/history, documents, intermediate files

**Data flow**: `protocol_usdm.json` → `protocolStore` (raw, immutable) → `usePatchedUsdm()` applies `semanticStore.draft.patch[]` → domain views. The protocol page uses `usePatchedUsdm()` so **all 15 child views** receive patched USDM. SoA edits flow through `soaEditStore` → `SoAProcessor` → `semanticStore`. Publish validates candidate in memory before writing, with `forcePublish` override.

**Editing capabilities**: Scalar fields (EditableField), CDISC coded values (EditableCodedValue, 14 codelists), lists with add/remove/reorder (EditableList), SoA cell marks (X/O/−/Del via keyboard), activity/encounter names, **add new activities and encounters** (via SoA toolbar "Add Row"/"Add Visit" buttons in edit mode). Revision conflict detection via SHA256 hash. Immutable paths protected (study ID, version ID).

**Known web UI gaps** (see `docs/WEB_UI_REVIEW.md` for full analysis):
1. **Index-based patch paths** — patches use array indices not entity IDs; fragile across re-extraction
2. **No GxP audit trail** — no authenticated user, no reason-for-change, no hash chain
3. **No live validation on publish** — reads pre-existing validation files, does not run validators on patched USDM
4. **Partial editing coverage** — objectives, estimands, interventions, timing, narrative, transition rules are read-only
5. ~~**Not all views use `usePatchedUsdm()`**~~ — ✅ Fixed: protocol page now uses `usePatchedUsdm()`, all 15 child views receive patched USDM

---

## 6. Known Gaps & Implementation Status

### 6.1 Extractor Gaps (from `docs/M11_USDM_ALIGNMENT.md`)
All 28 extractor gaps (3 CRITICAL, 10 HIGH, 9 MEDIUM, 6 LOW) identified in the USDM v4.0 field audit have been fixed across Sprints 1–4 (v7.6–v7.8). See `CHANGELOG.md` for full details.

| Priority | Gap | M11 Section | Status |
|----------|-----|-------------|--------|
| ~~P12~~ | Population demographics (age, sex, enrollment) | §1, §5 | ✅ Fixed |
| ~~P13~~ | GovernanceDate + sponsor Address | §1 title page | ✅ Fixed (v7.7) |
| ~~P14~~ | blindingSchema, randomizationType, characteristics | §1 synopsis, §4 | ✅ Fixed (v7.7) |
| P15 | M11-aware narrative sectionType tagging | §7, §9, §11 | ❌ Pending |
| ~~P16~~ | Configurable M11↔USDM mapping YAML | All | ✅ Fixed |
| ~~P17~~ | Generic code (protocol-specific refs removed) | All | ✅ Fixed |

### 6.2 Web UI Bug Fixes (External Review, Feb 2026)
| Bug | Fix | File(s) |
|-----|-----|---------|
| Timestamp format mismatch — history matching broken | `/[-:.]/g` in `getTimestamp()` | `lib/semantic/storage.ts` |
| SoA cell mark stale values on re-edit | Remove-then-append in `addMarkExtension()` | `lib/soa/processor.ts` |
| SoA undo granularity — partial undo corrupts cells | `beginGroup()`/`endGroup()` in `setCellMark`/`clearCell` | `stores/soaEditStore.ts` |
| SoA visual desync on undo | Reset `soaEditStore` on `undo()`/`redo()` | `stores/semanticStore.ts` |
| Overlay routes missing `validateProtocolId` | Added sanitization to both draft + publish routes | `overlay/draft/route.ts`, `overlay/publish/route.ts` |
| `sha256:unknown` bypass on publish | Reject on publish; allow only on draft save | `semantic/publish/route.ts` |
| `Math.random()` UUID | `crypto.randomUUID()` with fallback | `lib/soa/processor.ts` |
| Extension namespace mismatch backend↔frontend | Unified to `https://protocol2usdm.io/extensions/` | `lib/extensions.ts` |
| Publish writes USDM before validation | Candidate→validate→commit flow with `forcePublish` option | `semantic/publish/route.ts` |
| Version string duplication | `core.constants.SYSTEM_NAME` + `SYSTEM_VERSION` | `main_v3.py`, `orchestrator.py`, `core/constants.py` |

### 6.3 Architectural Anti-Patterns
- ~~`_compose_safety` (§9) and `_compose_discontinuation` (§7) perform keyword scanning at render time~~ — ✅ Fixed: now prefer `sectionType`-based filtering (extraction-time tagging), keyword fallback for backward compat. Added `DISCONTINUATION` to `SectionType` enum.
- `NarrativeContentItem` has extra fields (`sectionNumber`, `sectionTitle`, `order`) not in USDM v4.0 spec
- `NarrativeContent` missing `previousId`/`nextId` for linked list, `displaySectionTitle`/`displaySectionNumber` booleans

### 6.4 Structural Debt (from `docs/FULL_PROJECT_REVIEW.md`)
| ID | Issue | Severity | File(s) |
|----|-------|----------|--------|
| ~~W-CRIT-1~~ | ~~`combine_to_full_usdm()` god function~~ | ~~CRITICAL~~ | ✅ Extracted `_integrate_sites()`, `_integrate_sap()`, data-driven `_SAP_EXTENSION_TYPES` |
| W-CRIT-2 | No automated end-to-end integration test with golden PDF | CRITICAL | `testing/` |
| ~~W-CRIT-3~~ | ~~SAP/sites bypass phase registry~~ | ~~HIGH~~ | ✅ `SAPPhase` + `SitesPhase` registered (14 phases total) |
| W-HIGH-1 | Monolithic files: `llm_providers.py` (1,274L), `m11_renderer.py` (2,227L), `orchestrator.py` (1,692L) | HIGH | Multiple |
| W-HIGH-2 | `PipelineContext` growing into god object (28 fields + 7 lookup maps) | HIGH | `extraction/pipeline_context.py` |
| W-HIGH-3 | No provenance tracking for expansion phase entities (objectives, eligibility, etc.) | HIGH | `core/provenance.py` |
| W-HIGH-4 | Mutable global singletons (`phase_registry`, `usage_tracker`, EVS `_client`) hinder testing | MEDIUM | Multiple |

---

## 7. LLM Configuration
- Config file: `llm_config.yaml`
- Provider abstraction: `providers/` package (backward-compat shim: `llm_providers.py`)
- Supported: OpenAI (GPT-4o, GPT-4-turbo, GPT-5), Google (Gemini 2.5 Pro, Gemini 3 Flash), Anthropic (Claude)
- Default model: `gemini-3-flash-preview` (with Gemini 2.5 Pro fallback for SoA text extraction)
- Reasoning models (special parameter handling): o1, o3, gpt-5, gpt-5.1
- API keys: Environment variables, never hardcoded

### 7.1 Provider Architecture
| Class | File | Sync Client | Async Client |
|-------|------|-------------|--------------|
| `LLMProvider` (ABC) | `providers/base.py` | `generate()`, `generate_stream()` | `agenerate()`, `agenerate_stream()` (default: `asyncio.to_thread`) |
| `OpenAIProvider` | `providers/openai_provider.py` | `OpenAI` | `AsyncOpenAI` (lazy via `async_client` property) |
| `ClaudeProvider` | `providers/claude_provider.py` | `anthropic.Anthropic` | `AsyncAnthropic` (lazy via `async_client` property) |
| `GeminiProvider` | `providers/gemini_provider.py` | 3 backends (genai SDK, Vertex, AI Studio) | `client.aio` namespace (genai SDK); `asyncio.to_thread` for Vertex/AI Studio |

**Streaming**: `generate_stream()` / `agenerate_stream()` emit `StreamChunk` objects via `StreamCallback`. Each chunk has `text`, `accumulated_text`, `done`, `usage`, `finish_reason`.

**Async convenience**: `core.llm_client.acall_llm()` and `agenerate_text()` mirror sync `call_llm()` / `generate_text()`.

**Non-breaking**: All async methods are additive. Existing sync callers are unaffected.

---

## 8. Documentation Index
| Document | Purpose |
|----------|---------|
| `docs/ARCHITECTURE.md` | Full system architecture: schema-driven design, phase registry, reconciliation, provenance, entity resolution |
| `docs/M11_RENDERER_ARCHITECTURE.md` | Dual-path rendering, 7-pass mapper, 9 composers, conformance validator |
| `docs/M11_USDM_ALIGNMENT.md` | Complete M11→USDM entity mapping, gap analysis, remediation plan |
| `docs/M11_ANALYSIS.md` | Deep analysis of all 8 ICH M11 publications (Guideline, Template, Technical Spec) |
| `docs/EXECUTION_MODEL_EXTENSIONS.md` | Extension schemas for execution model concepts, promotion status |
| `docs/SAP_EXTENSIONS.md` | SAP extension schemas with STATO mapping and ARS linkage |
| `docs/PROJECT_REVIEW.md` | v7.2 comprehensive review: strengths, weaknesses, editability gaps |
| `docs/FULL_PROJECT_REVIEW.md` | Full codebase review: module-by-module analysis, 40+ weakness IDs, 24-item enhancement roadmap, architectural critique |
| `docs/ROADMAP.md` | Future: ARS output display, analysis-to-data traceability |
| `docs/SEMANTIC_EDITING_SPEC.md` | JSON Patch editing spec: storage layout, API endpoints, validation pipeline |
| ~~`docs/EXTRACTOR_GAP_AUDIT.md`~~ | *(Deleted)* All 28 gaps fixed — see `CHANGELOG.md` v7.8 |
| `docs/TIMELINE_REVIEW_GUIDE.md` | Timeline tab reviewer guide: execution model view, graph view |
| `docs/WEB_UI_REVIEW.md` | Web UI deep dive: architecture, data flow, editing, audit trail, strengths/weaknesses, enhancement roadmap |
