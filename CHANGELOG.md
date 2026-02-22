# Protocol2USDM – Change Log

All notable changes documented here. Dates in ISO-8601.

---

## [8.1.1] – 2026-02-22

**Bug Fixes — Cross-Protocol Hardening + Gemini 3.1 Pro Compatibility** — 6 bug fixes discovered by running CheckMate 227 (NCT02576509) and ADAURA (NCT03036124) Phase 3 protocols with both Gemini 3.0 Pro and 3.1 Pro.

### SoA Footnote & Vision Capture
- **footnote_condition_extractor.py**: Fixed `TypeError` when LLM returns `footnoteIndex` as string — explicit `int()` cast with `try/except` guard
- **validator.py**: Enhanced vision validation prompt to capture superscript footnote markers (e.g., `X^a`, `✓^m,n`) from SoA images; new `cell_footnotes` dict on `ValidationResult`
- **pipeline.py**: Merge cell-level footnote refs from image validation into provenance tracker

### Execution Model Crashes
- **state_machine_generator.py**: Fixed `'StateType' object has no attribute 'lower'` — use `_to_str()` helper before `.lower()` on mixed enum/string states (line 308-309)
- **reconciliation_layer.py**: Fixed `'str' object has no attribute 'sequence_name'` — handle crossover sequences that are plain strings (e.g., `"AB"`, `"BA"`) via `hasattr` guards

### Gemini 3.1 Pro Compatibility
- **narrative/extractor.py**: Fixed `'NoneType' object has no attribute 'isdigit'` — guard `section_number` against `None` in `_refine_section_type_with_content`; use `or ''` pattern for `sec.get('number')` to handle explicit `null` from LLM JSON

### Visit Resolution
- **pipeline_integration.py**: Added `'study intervention'`, `'intervention administration'` to `_VISIT_EPOCH_MAP` keywords so "Study Intervention Administration" resolves to treatment epoch encounters

### Files Changed
| File | Change |
|------|--------|
| `extraction/execution/footnote_condition_extractor.py` | `int()` cast for `footnoteIndex` |
| `extraction/execution/state_machine_generator.py` | `_to_str()` before `.lower()` |
| `extraction/execution/reconciliation_layer.py` | String sequence handling |
| `extraction/execution/pipeline_integration.py` | Visit keyword additions |
| `extraction/narrative/extractor.py` | `None` section_number guard |
| `extraction/validator.py` | Vision footnote capture prompt |
| `extraction/pipeline.py` | Footnote merge from validation |

### Cross-Protocol Test Results
| Protocol | Model | Phases | Schema | M11 Conf | Cost |
|----------|-------|--------|--------|----------|------|
| Wilson's (NCT04573309) | gemini-3-pro | 14/14 ✓ | Valid | — | $0.99 |
| ADAURA (NCT03036124) | gemini-3-pro | 14/14 ✓ | Valid | — | $0.80 |
| CheckMate 227 (NCT02576509) | gemini-3.1-pro | 14/14 ✓ | Valid | 93% | $0.39 |

### Test Results
- 1366 collected, 1327 passed, 36 skipped (e2e), 3 pre-existing M11 regression

---

## [8.1.0] – 2026-02-22

**Stratification & Randomization, SAP Multi-Pass, Tier 1 Enhancements, Hallucination Audit** — Major feature release with 5 stratification sprints, 4 SAP enhancement sprints, 7 tier-1 extraction/rendering fixes, and systematic hallucination removal.

### Stratification & Randomization (5 Sprints)
- **Sprint A**: Schema refactor — `FactorLevel`, `AllocationCell` dataclasses; enhanced `StratificationFactor` + `RandomizationScheme`; 3-pass LLM extraction replacing hardcoded `_get_factor_categories()`
- **Sprint B**: Cross-phase linking — `pipeline/stratification_linker.py` (NEW ~310 lines): factor→eligibility criterion, factor→SAP covariate (ICH E9), scheme→arm allocation, scheme→analysis population
- **Sprint C**: USDM mapping — `create_strata_cohorts()` in post_processing, M11 §4.3 treatment assignment composer, synopsis stratification display
- **Sprint D**: Web UI — `StratificationSchemeView.tsx` (NEW ~310 lines): randomization summary, factor levels with linked criteria badges, allocation weights, SAP covariate findings
- **Sprint E**: Validation — 7 coherence checks in `extraction/execution/validation.py`

### SAP Enhancement (4 Sprints)
- **Sprint 1**: Multi-pass extraction (`sap_prompts.py` NEW) — 4 focused LLM passes with cross-referencing; `MAX_SAP_PAGES=100` (was 40)
- **Sprint 2**: `AnalysisSpecification` bridge (endpoint→method→population→estimand); approach-aware gating for descriptive studies
- **Sprint 3**: `MissingDataStrategy` (ICE→missing data mapping); `ResultPattern` on all ARS operations
- **Sprint 4**: `StatisticalTraceabilityView.tsx` (NEW) — endpoint→method→population→estimand chains with completeness scoring

### Tier 1 Enhancements
- **OBJ-1/OBJ-2**: Estimand→intervention and estimand→population ID reconciliation
- **DES-1**: TransitionRule promotion to StudyElement (data-derived text only, no fabricated clinical content)
- **DES-3**: Duration extraction as ISO 8601 with EVS-verified NCI C-codes (C25301 Day, C29844 Week, C29846 Month, C29848 Year, C25529 Hour)
- **M11-1**: §4.3 blinding procedures rendering (narrative-sourced only, no fabricated boilerplate)
- **SOA-2**: ConditionAssignment from SoA footnotes + ScheduledDecisionInstance injection
- **SAP-1**: SAP statistical method→estimand binding via endpoint name/level matching
- **VAL-1/VAL-4**: Referential integrity checks S9–S14 (encounter→epoch, estimand→intervention, SAI references, SAP→endpoint coherence)

### Hallucination Audit
- Removed fabricated clinical text from TransitionRule templates (DES-1)
- Removed fabricated boilerplate from blinding composer (M11-1)
- Verified all duration unit C-codes via live NCI EVS API (DES-3)
- Tightened narrative keyword matching to avoid false matches

### New Files
| File | Description |
|------|-------------|
| `pipeline/stratification_linker.py` | Cross-phase stratification linking (B1–B4) |
| `extraction/conditional/sap_prompts.py` | 4-pass SAP extraction prompts |
| `extraction/execution/validation.py` | Stratification coherence validation |
| `web-ui/components/timeline/StratificationSchemeView.tsx` | Stratification UI |
| `web-ui/components/timeline/StatisticalTraceabilityView.tsx` | SAP traceability UI |
| `tests/test_tier1_enhancements.py` | 95 tests for tier 1 features |
| `tests/test_stratification_sprints.py` | 31 tests for stratification |
| `tests/test_sap_enhancement.py` | 42 tests for SAP enhancement |

### Test Results
- 1366 collected, 1327 passed, 36 skipped (e2e), 3 pre-existing M11 regression (word count threshold)

---

## [8.0.2] – 2026-02-19

**CORE Compliance Property Cleanup + Estimand→Endpoint Reconciliation** — Removes 4 non-USDM properties from output and adds endpoint reference reconciliation.

### Non-USDM Property Fixes (verified against `usdm_model` + `dataStructure.yml`)
- **C12**: `Administration.doseFrequency` — replaced with USDM-compliant `frequency` Code object in execution pipeline (`extraction/execution/pipeline_integration.py`)
- **C38**: `StudyVersion.studyPhase` — removed from StudyVersion (not a USDM field); kept on StudyDesign where schema expects it (`pipeline/phases/metadata.py`, `web-ui/lib/export/exportUtils.ts`, `validation/m11_conformance.py`)
- **C30**: `StudyIntervention.administrationIds` — replaced with inline `administrations[]` nesting per USDM v4.0 (`extraction/execution/pipeline_integration.py`, `extraction/execution/execution_model_promoter.py`, `rendering/composers.py`)
- **C46-C47**: `StudyDesignPopulation.cohortIds` — removed non-USDM ref property; `cohorts[]` inline nesting (already handled by `nest_cohorts_in_population`) is the USDM-compliant path (`pipeline/post_processing.py`)

### Estimand Reconciliation
- **FIX-5**: `Estimand.variableOfInterestId` — new `reconcile_estimand_endpoint_refs()` matches estimand endpoint references to actual Endpoint IDs using name/level/fuzzy matching (32 hits, 14/34 trials) (`pipeline/integrations.py`, `pipeline/combiner.py`)

### Test Results
- 1117 passed, 0 failed

---

## [8.0.1] – 2026-02-19

**USDM Schema Compliance Fixes** — Cross-validated all output entities against the official `usdm_model` Pydantic package and `dataStructure.yml`. Eliminates ~88% of schema validation errors across 34 trials.

### Fixes (verified against `usdm_model` + `dataStructure.yml`)
- **FIX-1**: `Procedure.procedureType` — changed from Code dict to plain string (731 hits, 34/34 trials) — `pipeline/post_processing.py`
- **FIX-2**: `StudyChange` — added missing `summary`, `label`, `description` fields; converted `changedSections` from `str[]` to `DocumentContentReference[]` (513 hits, 34/34) — `extraction/amendments/schema.py`, `pipeline/post_processing.py`
- **FIX-3**: `Administration.duration` — wrapped string in proper `Duration{text, durationWillVary}` object; also fixed `StudyIntervention.minimumResponseDuration` (117 hits, 33/34) — `extraction/interventions/schema.py`
- **FIX-4**: `Estimand.analysisPopulationId` — create `AnalysisPopulation` on-the-fly when no match found, with required `text` field (66 hits, 21/34) — `pipeline/integrations.py`

### Analysis Tooling
- New `scripts/analyze_validation_errors.py` — aggregates schema, USDM, integrity, and CORE findings across all trial outputs
- New `scripts/trace_errors.py` — traces root cause of validation errors to specific code paths

### Test Results
- 1118 passed, 0 failed (excl. pre-existing M11 regression)
- Updated duration assertions in `test_sprint2_gap_fixes.py`, `test_sprint34_gap_fixes.py`

---

## [8.0.0] – 2026-02-19

**Major version bump** — 33 commits of significant architectural and UI changes since the v7.17 baseline.

### Highlights
- **CORE Compliance: Log-Only Mode** — property stripping replaced with non-destructive audit (`compliance_log.json`)
- **Encounter→Epoch Resolution** — USDM v4.0 encounters linked via `ScheduledActivityInstance` bridge
- **UNS Detached Handling** — unscheduled visits rendered as isolated islands in graph + state machine
- **11 Automated CDISC CORE Rule Fixes** — dedup, child ordering, country decode, leaf procedures, timing durations
- **UI Data Display Refinements** — randomization, substance types, amendments, procedures filter, numeric footnotes
- **Compliance Audit UI** — new Validation tab card grouped by entity type
- **1157 tests** collected, 1118 passing

---

## [7.17.0] – 2026-02-18

### Functionality Hardening: USDM v4.0 Encounter→Epoch Resolution

USDM v4.0 encounters no longer carry a direct `epochId` — the linkage is through `ScheduledActivityInstance`. Three UI adapters were filtering encounters by the missing field, causing empty renders.

| Fix | Component | Description |
|-----|-----------|-------------|
| **SoA table** | `toSoATableModel.ts` | Columns not rendering (AG Grid `width: 0px`) — resolve via instance bridge; unassigned encounters get own group |
| **Graph view** | `toGraphModel.ts` | All encounter/activity nodes missing — same instance bridge fix at 4 filter sites |
| **Quality dashboard** | `QualityMetricsDashboard.tsx` | Encounter→Epoch linkage metric was 0% — bridge resolution + exclude parent activities from activity→schedule |

### UNS (Unscheduled) Detached Handling

Unscheduled visits can occur at any point during the study. Previously they appeared inline in the linear flow, which was visually misleading.

| Fix | Component | Description |
|-----|-----------|-------------|
| **State machine** | `ExecutionModelView.tsx` | UNS state moved out of linear flow, shown as detached with "(Any time)" label |
| **Graph view** | `toGraphModel.ts` | UNS epoch/encounters rendered as isolated island with annotation "Can occur at any point per traversal rules" |

### USDM v4.0 Schema Compliance Fixes

| Fix | Description |
|-----|-------------|
| **Administrations nesting** | `StudyIntervention.administrations[]` nested per schema (was flat at root) |
| **blindingSchema** | Output as proper USDM `AliasCode` with `standardCode` (was plain string) |
| **Activity groups** | `activityGroups` promoted to parent `Activity` with `childIds` (USDM v4.0 schema compliance) |

### UI Component Fixes

| Fix | Component | Description |
|-----|-----------|-------------|
| **EditableCodedValue** | `EditableCodedValue.tsx` | Unwrap nested Code objects to prevent `[object Object]` display |
| **Footnote numbering** | `FootnotePanel.tsx` | Letters continue as z, aa, ab... instead of falling back to numbers 27, 28... |
| **ScheduleTimelineView** | `ScheduleTimelineView.tsx` | Updated for parent Activity + `childIds` grouping model |
| **CodedValue badge** | `EditableCodedValue.tsx` | Render display as Badge tag to match other coded values |
| **Medical Conditions** | `StudyDesignView.tsx` | Sources from `studyDesign.indications` instead of `version.conditions` |
| **Activity audit** | Multiple | Ungrouped activities no longer dropped; deleteActivity cascade cleanup |
| **Provenance explorer** | `ProvenanceExplorer.tsx` | Filter parent activities to avoid noise rows |
| **SoA footnotes** | `SoAFootnotes.tsx` | Consume USDM-aligned `{id, text, marker}` objects + normalize to strings |

### CORE Compliance: Log-Only Mode

The property stripping pass (`_walk_strip_non_usdm`) has been converted to **log-only audit mode** — non-USDM properties are no longer deleted from the output. Instead, findings are collected and saved to `compliance_log.json` for review.

| Change | Description |
|--------|-------------|
| **Audit mode** | `_walk_audit_non_usdm` collects findings without deleting properties |
| **compliance_log.json** | New output file with per-entity findings (entityType, property, valuePreview, path) |
| **Validation UI** | New "CORE Compliance Audit" card in Validation tab — grouped by entity type, expandable |
| **Return signature** | `normalize_for_core_compliance()` now returns 3-tuple: `(data, stats, findings)` |

### UI Data Display Refinements

| Fix | Component | Description |
|-----|-----------|-------------|
| **Randomization** | `StudyMetadataView.tsx` | Read from `subTypes[]` via CDISC C-codes (C25196/C48660) instead of phantom `randomizationType` |
| **Substance type** | `InterventionsView.tsx` | Derive type from linked `StudyIntervention` by name matching; fallback description |
| **Amendment changes** | `AmendmentHistoryView.tsx` | Human-readable text instead of raw JSON; placeholder `StudyChange` uses CORE-compliant fields |
| **Procedures filter** | `ProceduresDevicesView.tsx` | Skip non-clinical activities (dosing, diet, consent, etc.) in both pipeline and UI |
| **Footnote numbering** | `FootnotePanel.tsx` | Changed from letters `[a],[b]...` to numeric `[1],[2]...` |
| **Age range dash** | `SAPDataView.tsx` | Fix unicode en-dash rendering (`\u2013` → `{'\u2013'}` in JSX) |
| **UNS connector** | `toGraphModel.ts` | Remove "No unscheduled event" fallback edge from graph |

### Files Changed

| File | Change |
|------|--------|
| **`core/core_compliance.py`** | `_walk_strip_non_usdm` → `_walk_audit_non_usdm` (log-only); 3-tuple return |
| **`core/validation.py`** | Save `compliance_log.json` to output dir |
| **`pipeline/phases/studydesign.py`** | Randomization stored in `subTypes[]` as Code |
| **`pipeline/post_processing.py`** | Amendment changes CORE-compliant; procedure skip patterns |
| **`web-ui/components/quality/ValidationResultsView.tsx`** | Compliance Audit card |
| **`web-ui/components/protocol/StudyMetadataView.tsx`** | Randomization from `subTypes[]` |
| **`web-ui/components/protocol/InterventionsView.tsx`** | Substance→intervention linkage |
| **`web-ui/components/protocol/ProceduresDevicesView.tsx`** | Non-procedure filter |
| **`web-ui/components/soa/FootnotePanel.tsx`** | Numeric markers |
| **`web-ui/components/timeline/SAPDataView.tsx`** | Unicode dash fix |
| **`web-ui/lib/adapters/toGraphModel.ts`** | Remove "No unscheduled event" edge |
| **`web-ui/app/api/protocols/[id]/validation/route.ts`** | Load compliance_log.json |
| **`web-ui/app/api/protocols/[id]/intermediate/route.ts`** | Register compliance_log |
| **`web-ui/lib/adapters/toSoATableModel.ts`** | Encounter→epoch via instance bridge + unassigned group |
| **`web-ui/lib/adapters/toGraphModel.ts`** | Instance bridge + UNS detached island |
| **`web-ui/styles/cytoscape-theme.ts`** | UNS annotation, detached node/edge styles |
| **`web-ui/components/timeline/ExecutionModelView.tsx`** | UNS state detached from linear flow |
| **`web-ui/components/soa/FootnotePanel.tsx`** | `indexToMarker()` letter sequence |
| **`web-ui/components/quality/QualityMetricsDashboard.tsx`** | Linkage via instance bridge |
| **`web-ui/components/protocol/ScheduleTimelineView.tsx`** | Parent Activity + childIds |
| **`web-ui/components/semantic/EditableCodedValue.tsx`** | `_unwrap` helper for nested Code |
| **`web-ui/components/protocol/InterventionsView.tsx`** | Nested administrations + Quantity dose |
| **`pipeline/phases/interventions.py`** | Nest administrations inside StudyIntervention |

### Reviewer Fixes P3–P7: USDM Structural Compliance

Five post-processing functions addressing independent reviewer findings, improving USDM v4.0 structural conformance.

| Fix | Function | Description |
|-----|----------|-------------|
| **P6** | `ensure_eos_study_cell()` | Creates StudyElement + StudyCell for any epoch lacking a cell (EOS, ET, follow-up) — schema requires `studyCells [1..*]` |
| **P3** | `nest_sites_in_organizations()` | Nests StudySite entities into `Organization.managedSites` by name matching with fallback to site-type org |
| **P5** | `wire_document_layer()` | Builds `Study.documentedBy → StudyDefinitionDocument → versions[0].contents[]` from narrativeContentItems |
| **P4** | `nest_cohorts_in_population()` | Moves `studyCohorts[]` into `StudyDesignPopulation.cohorts[]` with required field defaults |
| **P7** | `promote_footnotes_to_conditions()` | Promotes conditional SoA footnotes to `Condition` entities with `contextIds` linking to encounters |

### Files Changed

| File | Change |
|------|--------|
| **`pipeline/post_processing.py`** | 5 new functions (P3–P7) added before `run_structural_compliance()` |
| **`pipeline/combiner.py`** | 5 new imports + wiring calls in combine pipeline |
| **`tests/test_reviewer_fixes.py`** | 21 new tests covering all 5 functions |

### Reviewer v9 Fixes: USDM Schema Alignment

Fixes from independent reviewer evaluation (v9), plus Organization/StudySite alignment with `dataStructure.yml`.

| Fix | Description |
|-----|-------------|
| **Site-Org Mapping** | New Organization per unmatched site (was dumping Mass General/Yale/UMich under Cleveland Clinic) |
| **StudySite.country** | ISO 3166-1 alpha-3 code lookup (USA, GBR, DEU, etc.) instead of full country names |
| **documentedBy Wiring** | Backfill SDD metadata, wire contentItemId, build childIds hierarchy, previousId/nextId chain |
| **CORE Allowed Keys** | Added NarrativeContent, SDD, SDDVersion, Organization, StudySite |
| **Condition contextIds** | Improved from 4/21 to ~12-15/21 wired footnote conditions |
| **scheduledAtTimingId→scheduledAtId** | Renamed across 9 Python + 3 TypeScript files |
| **environmentalSetting→environmentalSettings** | Plural form per USDM v4.0 schema |
| **Org/Site Schema Alignment** | `studyDesigns[].studySites` removed (not a USDM path); sites live only in `Organization.managedSites[]` |
| **Organization Required Fields** | Backfill `identifier` (1) and `identifierScheme` (1) on all orgs via `_backfill_organization()` |
| **StudySite Sanitization** | Non-schema fields (siteNumber, status, address) moved to extensionAttributes or stripped |
| **Org Type C-code** | Fixed from C188875 to EVS-verified C21541 (Healthcare Facility) |

### Files Changed

| File | Change |
|------|--------|
| **`pipeline/post_processing.py`** | `_sanitize_study_site()`, `_backfill_organization()`, site nesting removes `studySites` from design |
| **`core/core_compliance.py`** | Organization + StudySite allowed keys added |
| **`rendering/composers.py`** | Read sites from `Organization.managedSites[]` with country Code decode |
| **`validation/m11_conformance.py`** | Read sites from `Organization.managedSites[]` |
| **`extraction/conditional/sites_extractor.py`** | ISO 3166-1 alpha-3 country codes |
| **`extraction/metadata/schema.py`** | legalAddress.country Code populated |

### UI & Rendering Fixes

| Fix | File | Description |
|-----|------|-------------|
| **medicalDevices placement** | `pipeline/phases/procedures.py` | Moved from `studyDesign` to `studyVersion` per USDM v4.0 — CORE compliance was stripping them |
| **DOCX XML sanitization** | `rendering/text_formatting.py` | Strip XML-illegal control characters before python-docx (fixes DAPA-HF crash) |
| **StudySitesView — data source** | `web-ui/.../StudySitesView.tsx` | Read sites from `Organization.managedSites[]` with backward compat for legacy `studyDesign.studySites` |
| **StudySitesView — enrollment** | `web-ui/.../StudySitesView.tsx` | Display total planned enrollment from `population.plannedEnrollmentNumber` |
| **FootnotesView — object format** | `web-ui/.../FootnotesView.tsx` | Handle `{id, text, marker}` objects in `x-soaFootnotes` (was rendering as `[object Object]`) |
| **FootnotesView — notes[]** | `web-ui/.../FootnotesView.tsx` | Read promoted footnotes from `studyDesign.notes[]` (USDM-correct location) |

### UI Data Display Fixes

| Fix | Component | Description |
|-----|-----------|-------------|
| **Boolean display** | `EditableField.tsx` | Show "Yes"/"No" instead of raw `true`/`false` for boolean fields |
| **Planned Enrollment** | `EligibilityCriteriaView.tsx` | Fixed path to `maxValue.value` in `QuantityRange` object |
| **InterventionsView USDM v4.0** | `InterventionsView.tsx` | Aligned `AdministrableProduct` interface/rendering to nested `ingredients[].substance.strengths[]` structure; removed phantom `routeOfAdministration`, `strength`, `manufacturer` fields |
| **Randomization type** | `StudyMetadataView.tsx` | Added `randomizationType` `EditableCodedValue` to study metadata display |
| **Estimand ID resolution** | `AdvancedEntitiesView.tsx` | Resolve `interventionIds`→intervention names, `variableOfInterestId`→endpoint name, extract `summaryMeasure` from `populationSummary` text |
| **Analysis Population level** | `AdvancedEntitiesView.tsx` | Removed phantom `level` coded value (not in USDM v4.0 schema); replaced with editable name |
| **SAP Population fields** | `SAPDataView.tsx` | Mapped Definition→`text`, Description→`description` (was reading phantom `populationDescription`/`criteria`) |
| **ARS Operation badge** | `SAPDataView.tsx` | Show method name instead of raw UUID in CDISC ARS Operation badge |
| **FDA Labels** | `InterventionsView.tsx` | Disabled `DrugInfoPanel` rendering (inaccurate results) |

### UI UX Fixes

| Fix | Component | Description |
|-----|-----------|-------------|
| **Traversal UNS filtering** | `ExecutionModelView.tsx` | UNS/Unscheduled filtered from Required Epoch Sequence and Mandatory Visits; orange annotation note added (matches StateMachinePanel approach) |
| **Intermediate Files** | `IntermediateFilesTab.tsx` | Enhanced viewer with file content display and improved layout |

### Pipeline & CORE Compliance Fixes

| Fix | Description |
|-----|-------------|
| **code_registry import** | `pipeline/phases/studydesign.py` — fixed `from core.code_registry import registry as code_registry` (was importing non-existent name) |
| **Phase output filenames** | All 13 phase files — standardized `output_filename` in `PhaseConfig` |
| **CDISC CORE fixes** | `pipeline/post_processing.py` — CORE-001015 dedup, CORE-001066 child ordering, CORE-000427 country decode, CORE-000825 window durations, CORE-000808 codeSystemVersions, CORE-000413 otherReason, CORE-000937 non-USDM props, CORE-001076 leaf procedures, CORE-000820 timing durations, CORE-000930 amendment codeSystems, CORE-000938 amendment changes |

### Test Results

| Check | Result |
|-------|--------|
| Full test suite | **1157 collected**, 1118 passed, 0 failures |

---

## [7.16.0] – 2026-02-17

### USDM v4.0 Endpoint Nesting

Endpoints are now correctly nested inline inside `Objective.endpoints` per the USDM v4.0 schema (Value relationship), instead of being placed at the design level.

| Area | Change |
|------|--------|
| **`pipeline/phases/objectives.py`** | `ObjectivesPhase.combine()` nests endpoints inside objectives via `endpointIds` mapping; stores flat `_temp_endpoints` in combined dict for cross-referencing |
| **`pipeline/regression_gate.py`** | Endpoint counting updated to sum from `objective.endpoints[]` instead of design-level list |
| **`rendering/composers.py`** | `_compose_objectives()` reads from `endpoints` (USDM v4.0) with `objectiveEndpoints` fallback |
| **`core/core_compliance.py`** | `_fix_primary_endpoint_linkage()` updated for nested structure |
| **`pipeline/post_processing.py`** | `fix_primary_endpoint_linkage()` updated for nested structure |

### ExtensionAttribute USDM v4.0 Alignment

Per USDM v4.0 `dataStructure.yml`, `ExtensionAttribute` uses `url` as its semantic identifier — the non-schema `name` field has been removed from all creation sites.

| Area | Change |
|------|--------|
| **`extraction/execution/pipeline_integration.py`** | Removed `"name"` from `_create_extension_attribute()` |
| **`core/reconciliation/base.py`** | Removed `"name"` from 5 extension creation blocks in `_add_extension_attributes()` |
| **`pipeline/post_processing.py`** | Removed `"name"` from UNS encounter + SDI extension dicts |
| **`core/core_compliance.py`** | `name` excluded from `_USDM_ALLOWED_KEYS["ExtensionAttribute"]` — strip filter catches any remaining |

### Architectural Audit: core_compliance.py Cleanup

Comprehensive audit of `core/core_compliance.py` to identify late-stage workarounds that should be fixed upstream. Relocated fixes to correct architectural layers.

| Fix | Before (safety-net) | After (upstream) |
|-----|---------------------|-----------------|
| **Labels (399 fixes)** | `_walk_populate_labels()` copied `name→label` | `ReconciledEntity._base_usdm_dict()` now emits `label`/`description`; 4 SAI creation sites in `execution_model_promoter.py` fixed |
| **Procedure defaults** | `_walk_fix_procedure_defaults()` added `procedureType`/`code` | Both `extraction/procedures/schema.py` and `core/usdm_types_generated.py` `Procedure.to_dict()` now emit defaults |
| **Dead structural code (~210 lines)** | `_build_ordering_chains()`, `_fix_primary_endpoint_linkage()`, `_fix_timing_references()` defined but never called | Removed — these live correctly in `pipeline/post_processing.py` |
| **File reduction** | 714 lines | 504 lines |

**Remaining safety-nets** (legitimate): codeSystem normalization (~4), ID generation (~11), XHTML sanitization (~9), strip non-USDM properties (LLM noise).

### New Files

| File | Purpose |
|------|---------|
| **`core/core_compliance.py`** | CORE compliance safety-net (codeSystem, IDs, labels, XHTML, strip) |
| **`pipeline/regression_gate.py`** | Pre-commit structural quality checks |
| **`extraction/enrollment_finder.py`** | Keyword-guided enrollment extraction (G1) |
| **`tests/test_core_compliance.py`** | CORE compliance tests (sort keys, ordering chains, endpoint linkage, labels, strip) |
| **`tests/test_regression_gate.py`** | Regression gate tests |

### Test Results

| Check | Result |
|-------|--------|
| Full test suite | **1136 collected**, 1087 passed, 36 skipped (e2e), 0 failures |

---

## [7.15.0] – 2026-02-16

### Review Fix Sprint (B1–B9)

Systematic remediation of all findings from the Wilson protocol quality review.

| ID | Issue | Fix |
|----|-------|-----|
| **B1** | Phantom activity UUIDs in execution model | Improved LLM prompts with reconciled activity list context; `_nullify_orphan_refs()` fallback |
| **B3** | Name-string activity references | `resolve_name_as_id_references()` for substance/element name→ID resolution |
| **B4** | Empty `plannedEnrollmentNumber` | Cross-phase SAP fallback via `populate_enrollment_from_sap()` (now superseded by G1) |
| **B5** | Empty analysis population descriptions | Auto-populate `description` from `text`/`populationDescription` in SAP phase |
| **B6** | Duplicate "Vital Signs" activities | Extended `CLINICAL_SYNONYMS` in activity reconciler for vitals variants |
| **B7** | ClinicalTrials.gov org type wrong | `_map_org_type()` now checks known registry names before type-string matching |
| **B8** | Missing `StudyCell` arm×epoch combos | Gap-fill logic in `_apply_defaults()` creates placeholder cells for missing combinations |
| **B9** | Orphan `scopeId` / `exitEpochIds` | `clean_orphan_cross_refs()` nullifies refs to non-existent organizations and epochs |

### G1: Keyword-Guided Enrollment Extraction

New two-stage enrollment extraction: regex keyword search finds relevant pages/passages across the full PDF, then a focused LLM call extracts the precise number from those targeted passages.

| Component | Details |
|-----------|---------|
| **`extraction/enrollment_finder.py`** | New module: `find_enrollment_passages()` (keyword scan) + `extract_enrollment_from_passages()` (focused LLM) + `find_planned_enrollment()` (convenience API) |
| **4-tier fallback** | Protocol PDF keyword→LLM → SAP PDF keyword→LLM → SAP extension `targetSampleSize` → Metadata LLM synopsis |
| **Metadata prompt** | Also asks for enrollment from synopsis (Tier 4 backup, zero extra LLM cost) |
| **`enrich_enrollment_number()`** | Replaces `populate_enrollment_from_sap()` in `post_processing.py` |

### Additional Improvements

| Area | Change |
|------|--------|
| **`core/core_compliance.py`** | Safety-net fallback codeSystem normalization, ID generation, label population |
| **`pipeline/regression_gate.py`** | Pre-commit regression gate for structural quality checks |
| **Debug scripts** | 15+ new scripts in `scripts/debug/` for protocol analysis |

### Test Results

| Check | Result |
|-------|--------|
| Full test suite | **1100 passed**, 36 skipped, 0 failures |

---

## [7.14.0] – 2026-02-14

### Integrity Checker Final Warning Cleanup

Resolved the remaining Wilson integrity findings by refining orphan detection semantics and contextual-link handling.

| Area | Change |
|------|--------|
| **StudyElement orphan logic** | Elements with chain/transition context (`previousElementId`, `nextElementId`, transition rules) are treated as context-linked (non-orphan) |
| **Activity orphan logic** | Activities with `definedProcedures` or SoA source tags (`x-activitySource`/`x-activitySources` = `soa`) are treated as context-linked |
| **Analysis populations** | `analysisPopulations` removed from orphan checks (frequently SAP-context only, not explicitly cross-linked) |
| **Terminal epochs** | EOS/ET-style epochs remain exempt from `epoch_not_in_cell` warnings |

### CDISC CORE Conformance Hardening

| Area | Change |
|------|--------|
| **Schema parsing** | `validation/cdisc_conformance.py` now parses both legacy CORE output (`issues[]`) and CORE v0.14+ output (`Issue_Details` / `Issue_Summary`) |
| **Timeout behavior** | Local CORE timeout default increased to 300s and made configurable via `CDISC_CORE_TIMEOUT_SECONDS` |
| **Workflow update** | `.windsurf/workflows/validate-usdm.md` fixed to call `run_cdisc_conformance(json_path, output_dir)` correctly and display normalized error/warning counts |

### Regression Coverage

| File | Tests |
|------|-------|
| `tests/test_integrity.py` | +3 (analysis population orphan skipped, titration chain non-orphan, SoA-sourced activity non-orphan) |
| `tests/test_execution_model.py` | Existing chain-link regression retained for promoted StudyElements |
| `tests/test_cdisc_conformance.py` | +7 (legacy/v0.14 parsing + timeout resolution behavior) |

### Verification Runs

| Check | Result |
|-------|--------|
| Targeted regression suite | `245 passed` (`tests/test_cdisc_conformance.py`, `tests/test_integrity.py`, `tests/test_execution_model.py`, `tests/test_sprint1_gap_fixes.py`) |
| Full Wilson pipeline rerun | `output/NCT04573309_Wilsons_Protocol_E2E_20260214_2305` created successfully |
| Integrity report (E2E run) | `0 errors, 0 warnings, 0 info` |
| CDISC CORE report (E2E run) | Parsed successfully (`544 errors, 0 warnings`) via normalized wrapper |

---

## [7.13.0] – 2026-02-14

### Graph View — Neighborhood Focus & Layout Selector

| Feature | Details |
|---------|---------|
| **Neighborhood dimming** | Clicking a node dims all non-connected nodes/edges to 15%/8% opacity; click background to clear |
| **Layout selector** | Toolbar dropdown with 6 Cytoscape layouts: Saved (preset), Grid, Circle, Concentric, Hierarchy (breadthfirst), Force (cose) |
| **`LayoutIcon` component** | Proper React component replacing JSX member expressions that SWC/Turbopack compiled as invisible HTML elements |
| **Toolbar flex-wrap** | Actions bar now wraps on narrow viewports instead of overflowing |

**Files changed**: `TimelineCanvas.tsx` (runLayout + dimming logic), `TimelineToolbar.tsx` (LayoutIcon + dropdown), `TimelineView.tsx` (layout state), `cytoscape-theme.ts` (dimmed styles)

---

## [7.12.0] – 2026-02-14

### Procedure Code Enrichment — Multi-System Terminology

Added automatic multi-system terminology mapping for extracted procedures. Each procedure is now enriched with codes from NCI, SNOMED CT, ICD-10, CPT, and LOINC via an embedded 60+ procedure database with EVS API fallback.

| Component | Change |
|-----------|--------|
| **`core/procedure_codes.py`** | `ProcedureCodeService` singleton: embedded DB → fuzzy match → EVS API cross-terminology resolution |
| **`pipeline/post_processing.py`** | `enrich_procedure_codes()` called during `link_procedures_to_activities()` |
| **`web-ui/.../ProceduresDevicesView.tsx`** | Reads `x-procedureCodes` extension, renders all codes as clickable `CodeLink` badges |
| **Extension format** | `x-procedureCodes` stores `[{code, codeSystem, decode, url}]` per procedure |

### Graph Viewer — Editing & Cross-References

Complete rewrite of the graph node details panel and editing integration:

| Feature | Details |
|---------|---------|
| **Human-readable cross-references** | All UUID references (epochId, encounterId, activityId, etc.) resolved to entity names with type badges |
| **Clickable navigation** | Click any cross-reference → graph animates to that node with highlight flash |
| **Inline editing** | Name and description editable directly in the details panel (encounters, activities, epochs) |
| **Semantic store wired** | Edits generate JSON Patch ops via `addPatchOp()` with proper `designPath()` paths |
| **Undo/Redo** | Panel-level undo/redo buttons wired to `semanticStore.undo()/redo()` |
| **Edit mode aware** | Editing UI only appears when global edit mode is toggled on |
| **`selectNode()` API** | New `TimelineCanvasHandle.selectNode()` for programmatic cross-node navigation |

### Graph View — Dedicated Anchor Nodes

Time anchors from the execution model now render as dedicated diamond-shaped nodes in the graph view instead of unreliable fuzzy-matching on timing nodes.

| Change | Details |
|--------|---------|
| **Anchor nodes created** | Each `timeAnchor` → amber diamond node at `anchorY=50` with ⚓ label |
| **Smart alignment** | Anchors aligned to matching encounters via keyword lookup (Baseline→"baseline"/"day 1", etc.) |
| **Dashed edges** | Amber dashed edge from each anchor to its aligned encounter |
| **Cytoscape styles** | `node.execution-anchor` (diamond) + `edge.anchor-edge` (dashed amber) |

### Timeline Popout Fix — Position-Aware Alignment

Fixed timeline anchor labels and visit labels being clipped/obstructed at screen edges:

| Element | Fix |
|---------|-----|
| **Anchor labels** | `leftPct < 10` → left-align, `> 90` → right-align, else center |
| **Anchor tooltips** | Same position-aware logic |
| **Visit labels** | `leftPercent < 8` → left-align, `> 92` → right-align |
| **Visit tooltips** | Same position-aware logic |

### New/Updated Tests

| File | Tests |
|------|-------|
| `tests/test_procedure_codes.py` | 39 (embedded DB, service resolution, enrichment, EVS mock, dedup) |

**Test suite**: 981 passed, 36 skipped, 0 failures, 0 TS errors

---

## [7.11.0] – 2026-02-14

### SoA Page Finder — Multi-Page Table Detection

Fixed critical SoA extraction failure on SURPASS-4 where the header analyzer found 0 timepoints/encounters/epochs due to missing table pages.

| Problem | Root Cause | Fix |
|---------|-----------|-----|
| **Heuristic scoring missed wide tables** | Visit numbers on separate lines (`Visit\n1\n2\n...`) — `visit\s*\d+` regex only matched once | Added wide-table heuristic: count isolated integers + epoch keywords + X-tick density |
| **Adjacent expansion too conservative** | Only ±1 page from detected range; SURPASS-4 SoA starts 3 pages before detected page | New header-fingerprint expansion: `_extract_header_fingerprint()` builds frozenset of header tokens, walks ±8 pages with Jaccard similarity ≥ 0.75 |
| **Interior gaps unfilled** | Gap-fill only covered ≤3 page gaps | Interior scan fills all gaps between known SoA pages using fingerprint matching |

**Before**: 4 images → 0 timepoints, 0 encounters, 0 activities, 12 dangling xrefs
**After**: 9 images → 32 timepoints, 32 encounters, 23 activities, 0 validation errors

### Dangling SAI `encounterId` Fix

Fixed 12 dangling cross-reference warnings in SURPASS-4 semantic validation.

| Problem | Root Cause | Fix |
|---------|-----------|-----|
| **SAIs reference removed encounters** | Execution model promoter creates encounters + SAIs; reconciliation filters encounters without `epochId`; SAIs keep old references | Post-reconciliation cleanup in `pipeline/post_processing.py` remaps dangling `encounterId` to nearest surviving encounter |

### UI: MeSH Code Links & Characteristics Display

| Component | Change |
|-----------|--------|
| **`StudyMetadataView.tsx`** | Therapeutic area MeSH code displayed as clickable link to NLM MeSH Browser |
| **`AdvancedEntitiesView.tsx`** | Same MeSH link in therapeutic areas badges |
| **`StudyMetadataView.tsx`** | `Characteristic` interface fixed to match USDM `Code` objects; displays `decode` values as badges |

### Renderer sectionType Confirmation

Verified extraction-time `sectionType` tagging works end-to-end (SURPASS-4: 13 Safety, 11 Discontinuation sections tagged). Keyword fallbacks in `_compose_safety`/`_compose_discontinuation` retained for backwards compatibility with deprecation warnings.

### New/Updated Tests

| File | Tests |
|------|-------|
| `tests/test_sap_combine.py` | +2 (dangling SAI encounterId regression: remapped + valid cases) |

**Test suite**: 941 passed, 36 skipped, 0 failures

---

## [7.10.0] – 2026-02-13

### SAP Extraction Fixes — 3 Bugs Fixed

Fixed three interconnected bugs preventing SAP data (especially multiplicity adjustments) from appearing in the UI:

| Bug | Root Cause | Fix |
|-----|-----------|-----|
| **Wrong key in `SAPPhase.combine()`** | `prev.get('sap', prev)` missed nested `sapData` key in `11_sap_populations.json` | Changed to `prev.get('sapData', prev)` in `pipeline/phases/sap.py` |
| **Duplicate SAP extensions** | Both `SAPPhase.combine()` and `integrate_sap()` added extensions (16 instead of 8) | Removed redundant `integrate_sap()`/`integrate_sites()` calls in `pipeline/combiner.py` |
| **`sap_path` not forwarded** | Orchestrator didn't pass `sap_path`/`sites_path` kwargs to `phase.run()` | Added `**kwargs` to `run_phases()`/`run_phases_parallel()` in `pipeline/orchestrator.py`; passed from `main_v3.py` |
| **Same key bug in Sites** | `prev.get('sites', prev)` should be `prev.get('sitesData', prev)` | Fixed in `pipeline/phases/sites.py` |

### Timeline Anchor Visualization — All Anchors Rendered

Previously only a single "Day 1" anchor was shown; all other anchors were invisible.

| Change | Details |
|--------|---------|
| **All anchors rendered** | Grouped by `dayValue`, each unique day gets a colored marker at its correct timeline position |
| **Type-specific colors** | FirstDose (blue), Baseline (purple), Randomization (green), Screening (amber), InformedConsent (cyan), CollectionDay (pink), Custom (gray) |
| **Grouped anchors** | Multiple anchors at same day show count badge + hover tooltip listing all anchor types/definitions |
| **Day range expanded** | Anchor `dayValue`s now included in min/max calculations so anchors outside visit range are visible |
| **Null targetDay safety** | Visits with `targetDay: null` (e.g., "Early Termination") filtered from position calculations |

### Figure Extraction — Three-Strategy Approach

Replaced full-page rendering with a three-strategy image extraction pipeline:

| Strategy | Method | Quality |
|----------|--------|---------|
| 1. Embedded images | `extract_embedded_image()` via PyMuPDF `get_page_images()` | Highest — native resolution |
| 2. Cropped region | `render_page_region_to_image()` around figure label | Good — tight crop |
| 3. Full page fallback | Render entire page at 150 DPI | Acceptable — last resort |

### Cross-References & Figures UI

| Component | Change |
|-----------|--------|
| **`reference_scanner.py`** | Two-pass figure scanning: prefer non-TOC pages, clean dotted-leader artifacts, 200-char context window |
| **`CrossReferencesView.tsx`** | Figure/table titles from `protocolFigures[]`, linked page numbers, short context hidden |
| **`FiguresGalleryView.tsx`** | List/grid toggle, `cleanTitle()` safety net, improved title display |

### Referential Integrity Checker

New `pipeline/integrity.py` — three-layer USDM validation:

| Layer | Checks |
|-------|--------|
| **ID references** | 16 rules validating cross-entity ID references (StudyCell→arm/epoch, SAI→encounter, Estimand→population) |
| **Orphan detection** | 7 entity collections scanned for unreferenced entities |
| **Semantic rules** | 8 rules (arm not in cell, unnamed activities, uncategorized criteria, duplicate IDs, etc.) |

Output: `integrity_report.json` with severity-filtered findings. UI: `IntegrityReportView.tsx` with summary bar and expandable rows.

### Cross-Phase Context Enrichment

| Phase | New Dependency | Context Injected |
|-------|---------------|-----------------|
| `scheduling` | `studydesign` | Encounter/epoch/arm names for timing references |
| `advanced` | `objectives`, `eligibility`, `interventions` | Estimands need objective/endpoint/intervention context |

### AdministrableProduct Expansion (USDM v4.0 C215492)

5 new fields extracted: `label`, `routeOfAdministration`, `productDesignation` (IMP/NIMP), `sourcing`, `pharmacologicClass`.

### UI/UX Improvements

| New Component | Purpose |
|---------------|---------|
| **`app-shell.tsx`** | Consistent app layout shell |
| **`error-boundary.tsx`** | React error boundary with fallback UI |
| **`keyboard-shortcuts.tsx`** | Keyboard shortcut handler |
| **`theme-toggle.tsx`** | Dark/light theme toggle |
| **`useAutoSave.ts`** | Auto-save hook for draft changes |
| **`useEntityProvenance.ts`** | Entity-level provenance lookup hook |
| **`useUserIdentity.ts`** | User identity hook for audit trail |
| **`ExtractionProvenanceView.tsx`** | Extraction pipeline provenance display |
| **`ProvenanceBadge.tsx`** | Inline provenance indicator badge |

### New Test Files

| File | Tests |
|------|-------|
| `tests/test_sap_combine.py` | 11 (SAP/Sites combine, no duplicates, orchestrator kwargs) |
| `tests/test_integrity.py` | 28 (ID refs, orphans, semantics, integration) |
| `tests/test_reference_scanner.py` | 45 (figure scanning, TOC detection, title cleaning) |

**Test suite**: 939 passed, 36 skipped, 0 failures, 0 TS errors

---

## [7.9.0] – 2026-02-13

### Web UI Editing — Estimands & Analysis Populations (P4)

Estimands are now fully editable in the web UI with all 5 ICH E9(R1) attributes + intercurrent events.

| Component | Change |
|-----------|--------|
| **AdvancedEntitiesView.tsx** | `EditableField` for treatment, population, variable, summary measure, intercurrent events; add/remove buttons for estimands and intercurrent events |
| **AdvancedEntitiesView.tsx** | Analysis population descriptions now editable |

### M11-Aware Narrative sectionType Tagging (P15)

`NarrativeContentItem` now carries `sectionType` from its parent `NarrativeContent`, set at extraction time. M11 renderer prefers type-based filtering over keyword fallback for §7/§9/§11.

| File | Change |
|------|--------|
| **extraction/narrative/schema.py** | Added `section_type` field to `NarrativeContentItem` + Code serialization in `to_dict()` |
| **extraction/narrative/extractor.py** | Propagate parent `section_type` to child items; fixed ordering bug |

### M11 Renderer Monolith Split (W-HIGH-1)

Split `m11_renderer.py` from 1199 → 465 lines by extracting two focused modules:

| New Module | Contents | Lines |
|------------|----------|-------|
| **rendering/document_setup.py** | `_setup_styles`, `_add_toc_field`, `_add_headers_footers`, `_add_title_page` | ~380 |
| **rendering/text_formatting.py** | `_add_narrative_text`, `_add_formatted_run`, `_distribute_to_subsections` | ~170 |

### NarrativeContent USDM v4.0 Conformance

Added all missing USDM v4.0 fields to `NarrativeContent` (C207592):

| Field | USDM Spec | Implementation |
|-------|-----------|----------------|
| `displaySectionTitle` | C215534, boolean, cardinality 1 | Default `True` for numbered sections |
| `displaySectionNumber` | C215535, boolean, cardinality 1 | Default `True` for numbered sections |
| `previousId` | Ref to NarrativeContent, 0..1 | Linked list built at serialization in `NarrativeData.to_dict()` |
| `nextId` | Ref to NarrativeContent, 0..1 | Linked list built at serialization in `NarrativeData.to_dict()` |
| `contentItemId` | Ref to NarrativeContentItem, 0..1 | Set when section has exactly one child item |

### Unscheduled Visit (UNS) — Phase 2 & 3

**Phase 2 (Backend):** Promote UNS-tagged encounters to native USDM `ScheduledDecisionInstance` (C201351) entities with proper branching semantics.

| Entity | Description |
|--------|-------------|
| `ScheduledDecisionInstance` | Branch point preceding UNS encounter; placed on `scheduleTimeline.instances[]` |
| `Condition` (C25457) | Trigger event description; placed on `studyVersion.conditions[]` |
| `ConditionAssignment` (C201335) | Two branches: "event occurs" → UNS encounter, default → next scheduled encounter |

**Phase 3 (Frontend):** Timeline graph visualization of UNS decision branches in Cytoscape.js.

| File | Change |
|------|--------|
| **toGraphModel.ts** | Detect `ScheduledDecisionInstance` in timeline instances, render as diamond `decision` nodes with branch/default edges |
| **cytoscape-theme.ts** | Amber dashed diamond for decision nodes, amber dashed edges for branches, grey solid for defaults |
| **TimelineToolbar.tsx** | Legend updated with UNS Decision diamond + UNS Branch edge |
| **types/index.ts** | Added `conditionAssignments` to `USDMScheduledInstance` interface |

### Structural Debt — W-HIGH-2/3/4

**W-HIGH-2: PipelineContext Decomposition** — Broke the 28-field god object into 5 focused sub-context dataclasses with backward-compatible property delegation.

| Sub-Context | Fields | Lookup Maps |
|-------------|--------|-------------|
| `SoAContext` | epochs, encounters, activities, timepoints, study_cells | epoch, encounter, activity by id/name |
| `MetadataContext` | study_title, study_id, sponsor, indication, phase, study_type | — |
| `DesignContext` | arms, cohorts, objectives, endpoints, inclusion/exclusion_criteria | arm by id |
| `InterventionContext` | interventions, products, procedures, devices | intervention by id |
| `SchedulingContext` | timings, scheduling_rules, narrative_contents, time_anchors, repetitions, traversal_constraints, footnote_conditions | — |

**W-HIGH-3: Entity-Level Provenance** — Individual entities now tracked to their source phase with page numbers and confidence.

| Component | Change |
|-----------|--------|
| `PhaseProvenance` | Added `pages_used` and `entity_ids` fields |
| `BasePhase.run()` | Auto-captures `_extract_pages_used()` and `_extract_entity_ids()` from result data |
| `PipelineOrchestrator` | `aggregate_entity_provenance()` builds entity→phase registry; `save_entity_provenance()` writes `entity_provenance.json` |

**W-HIGH-4: Singletons → Dependency Injection** — All three mutable global singletons now injectable for test isolation.

| Singleton | DI Functions |
|-----------|-------------|
| `phase_registry` | `create_registry()`, `PhaseRegistry.reset()`, `PipelineOrchestrator(registry=...)` |
| `_client` (EVS) | `set_client()`, `reset_client()` |
| `usage_tracker` | `create_tracker()`, `set_usage_tracker()`, `reset_usage_tracker()` |

**Test suite**: 897 passed, 0 failures, 0 TS errors

---

## [7.8.0] – 2026-02-11

### USDM v4.0 Extractor Gap Audit — All 28 Gaps Fixed

Systematic audit of all 9 extraction phases against `dataStructure.yml` (USDM v4.0). Identified 28 missing fields across 4 severity levels and fixed all of them in 3 sprints.

#### Sprint 1 — Quick Wins (v7.6)
| Gap | Fix |
|-----|-----|
| **C1** `StudyVersion.versionIdentifier` | Map `protocolVersion` in metadata combiner |
| **H3** `StudyDesign.studyPhase` | Copy from metadata → studyDesign |
| **H5** `Endpoint.purpose` | Default based on endpoint level |
| **H8** `Administration.administrableProductId` | Name-matching post-processor |
| **H9** `AdministrableProduct.ingredients` | Nest substances by ID/name |
| **H10** `Ingredient.strengthId` | Link from product strength string |

#### Sprint 2 — Prompt Expansions (v7.7)
| Gap | Fix |
|-----|-----|
| **C2** `StudyVersion.rationale` | Extract from §2 Introduction |
| **C3** `InterventionalStudyDesign.rationale` | Extract from §4 |
| **H1** `Organization.legalAddress` | Sponsor address from title page |
| **H2** `StudyVersion.dateValues` | GovernanceDate entities |
| **H4** `StudyDesign.characteristics` | Characteristics codes |
| **H6** `Administration.dose` | USDM Quantity object |
| **H7** `Administration.frequency` | USDM Code object |

#### Sprint 3+4 — MEDIUM + LOW Enrichment (v7.8)
| Gap | Fix |
|-----|-----|
| **M1** `StudyVersion.businessTherapeuticAreas` | Map from indications |
| **M2** `StudyRole.assignedPersons` | Extract PI/personnel from prompt |
| **M3/M9** `StudyDesignPopulation.cohorts` | Link cohort IDs in post-processing |
| **M4** `StudyIntervention.minimumResponseDuration` | Duration entity |
| **M5** `AdministrableProduct.identifiers` | Product identifier codes |
| **M6/M7/M8** `StudyAmendment` secondary fields | secondaryReasons, impacts, changes |
| **L1** `StudyVersion.referenceIdentifiers` | Cross-reference IDs from prompt |
| **L3** `StudyArm.notes` | CommentAnnotation objects |
| **L4** `StudyIntervention.notes` | CommentAnnotation objects |
| **L5** `AdministrableProduct.properties` | AdministrableProductProperty |
| **L6** `Procedure.isOrderable` | Boolean field |

#### New Test Files
| File | Tests |
|------|-------|
| `tests/test_sprint1_gap_fixes.py` | 29 |
| `tests/test_sprint2_gap_fixes.py` | 45 |
| `tests/test_sprint34_gap_fixes.py` | 41 |

**Test suite**: 808 passed, 33 skipped, 0 failures

---

## [7.5.0] – 2026-02-11

### NCI Code Audit & Verification System

Systematic audit of all 141 NCI C-codes against the NCI EVS API. Fixed 70+ fabricated/wrong codes across 20+ files.

| Area | Details |
|------|---------|
| **Code Registry** | New `core/code_registry.py` — centralized CodeRegistry singleton loading from `USDM_CT.xlsx` + supplementary codelists |
| **Code Verification** | New `core/code_verification.py` — `CodeVerificationService` with `EVS_VERIFIED_CODES` map for EVS-backed validation |
| **UI Codelists** | New `web-ui/lib/codelist.generated.json` — generated UI-ready codelists with correct NCI codes |
| **Generation Pipeline** | New `scripts/generate_code_registry.py` — generates `usdm_ct.json` + UI JSON + optional `--skip-verify` flag |
| **Intervention Types** | Fixed `StudyIntervention.type` codes: C307 (Biological), C16830 (Device), C1505 (Dietary Supplement), C15313 (Radiation), C17649 (Other) |

### Unscheduled Visit (UNS) Tagging

End-to-end support for identifying and visually distinguishing unscheduled/event-driven visits in the SoA table.

| Component | Details |
|-----------|---------|
| **Detection** | `is_unscheduled_encounter()` regex in `core/reconciliation/encounter_reconciler.py` — matches UNS, Unscheduled, Unplanned, Ad Hoc, PRN, As Needed, Event-Driven |
| **Extension** | `x-encounterUnscheduled` (`valueBoolean: true`) on Encounter entities |
| **Post-processing** | `tag_unscheduled_encounters()` safety net in `pipeline/post_processing.py` |
| **Scheduling** | `TransitionType.UNSCHEDULED_VISIT` enum in `extraction/scheduling/schema.py` |
| **UI** | Dashed amber borders, italic headers, ⚡ suffix, amber-tinted cells in SoA grid; `(UNS)` suffix in CSV/print exports |

### UI Fixes

- **CodeLink.tsx** — Defensive `String()` coercion for numeric code values (fixes `code.trim is not a function` TypeError on amendments)
- **EditableCodedValue.tsx** — Simplified component, removed inline type definitions
- **InterventionsView.tsx** — Updated to use corrected intervention type codes
- **StudyMetadataView.tsx** — Layout improvements

#### New Files

| File | Purpose |
|------|---------|
| `core/code_registry.py` | Centralized NCI code registry (USDM CT + supplementary) |
| `core/code_verification.py` | EVS-backed code verification service |
| `scripts/generate_code_registry.py` | Code registry generation pipeline |
| `web-ui/lib/codelist.generated.json` | UI-ready codelists |
| `tests/test_code_verification.py` | Code verification tests (19) |
| `tests/test_code_registry.py` | Code registry tests |
| `tests/test_unscheduled_encounters.py` | UNS encounter detection tests (28) |
| ~~`docs/EXTRACTOR_GAP_AUDIT.md`~~ | Extractor gap audit report (deleted after all 28 gaps fixed) |

**Test suite**: 726 collected  
**Total new tests**: ~87 (code verification + code registry + UNS encounters)

---

## [7.4.0] – 2026-02-10

### Performance & Scalability (E20–E24)

| Enhancement | Details |
|-------------|---------|
| **E20** | Parallel execution model sub-extractors — two-wave `ThreadPoolExecutor` (12 independent + state machine) |
| **E21** | LLM response streaming — `StreamChunk` + `StreamCallback` + `generate_stream()` on all 3 providers |
| **E22** | Chunked EVS cache — per-code JSON files under `evs_cache/codes/`, auto-migration from monolithic file |
| **E23** | Async LLM calls — `agenerate()` + `agenerate_stream()` on all 3 providers (native async SDKs) |
| **E24** | Cache-aware execution model — model+prompt hash in cache keys for invalidation |

### Code Quality & Robustness (E14–E19)

| Enhancement | Details |
|-------------|---------|
| **E14** | Provenance tracking for all expansion phases — `PhaseProvenance` dataclass |
| **E15** | Prompt versioning — SHA-256 hashes stored in `run_manifest.json` |
| **E18** | M11 mapping YAML schema validation at load time — `M11ConfigValidationError` |
| **E19** | SoA table rendering quality overhaul in M11 DOCX |

### LLM Provider Architecture

- **Async support**: `agenerate()` / `agenerate_stream()` on `LLMProvider` base + all 3 providers
  - OpenAI: `AsyncOpenAI` (native)
  - Claude: `AsyncAnthropic` (native)
  - Gemini: `client.aio` namespace (genai SDK); `asyncio.to_thread` for Vertex/AI Studio
- **Streaming**: `generate_stream()` with `StreamChunk` callback on all providers
- **Async convenience**: `acall_llm()` and `agenerate_text()` in `core.llm_client`
- Lazy `async_client` properties to avoid event-loop issues at import time

### EVS Cache Refactoring

- Per-code JSON files under `evs_cache/codes/` (O(1) writes vs O(n) for monolithic file)
- Auto-migration from legacy `nci_codes.json` on first load
- `_key_to_filename()` for safe filename generation
- `update_cache()` deletes old per-code file before refresh

#### New Test Files

| File | Tests | Coverage Target |
|------|-------|----------------|
| `tests/test_parallel_execution.py` | 13 | Parallel sub-extractor execution |
| `tests/test_cache_aware.py` | 19 | Cache key generation, model+prompt hash |
| `tests/test_llm_streaming.py` | 15 | StreamChunk, provider streaming |
| `tests/test_async_llm.py` | 16 | Async generate, gather, provider methods |
| `tests/test_evs_chunked_cache.py` | 17 | Per-code files, migration, stats |
| `tests/test_provenance_expansion.py` | 14 | PhaseProvenance for all phases |
| `tests/test_m11_config_validation.py` | 12 | M11 mapping YAML validation |

**Test suite**: 611 passed (including 33 e2e), 0 failed  
**Total collected**: 611 tests

**E2E improvement**: `E2E_MAX_AGE_HOURS` env var controls output reuse age (default 1h)

#### Files Changed

**New:**
* `tests/test_parallel_execution.py`, `tests/test_cache_aware.py`, `tests/test_llm_streaming.py`
* `tests/test_async_llm.py`, `tests/test_evs_chunked_cache.py`

**Modified:**
* `providers/base.py` — `StreamChunk`, `agenerate()`, `agenerate_stream()`
* `providers/openai_provider.py` — `AsyncOpenAI`, native async methods
* `providers/claude_provider.py` — `AsyncAnthropic`, `_build_claude_params()`
* `providers/gemini_provider.py` — `client.aio`, `_build_gen_config()`, `_build_genai_sdk_config()`
* `core/llm_client.py` — `acall_llm()`, `agenerate_text()`
* `core/evs_client.py` — Per-code chunked cache with migration
* `extraction/execution/pipeline_integration.py` — Parallel two-wave execution
* `extraction/execution/cache.py` — Model+prompt hash in cache keys
* `requirements.txt` — Added `pytest-asyncio>=1.0.0`

---

## [7.3.0] – 2026-02-10

### ICH M11 Document Rendering

Full ICH M11-formatted DOCX generation from USDM JSON.

#### New Files

| File | Purpose |
|------|---------|
| **`rendering/m11_renderer.py`** | DOCX generation with 7-pass section mapper |
| **`rendering/composers.py`** | 9 entity composers (synopsis, objectives, design, eligibility, interventions, estimands, discontinuation, safety, statistics) |
| **`rendering/tables.py`** | SoA table rendering for M11 documents |
| **`validation/m11_conformance.py`** | M11 conformance scoring (title page, synopsis, section coverage) |
| **`core/m11_mapping_config.py`** | M11 section ↔ USDM entity mapping configuration |

#### Key Features

- **7-pass section mapper** — Maps extracted narrative + composed content to 14 M11 sections
- **Dual-path architecture** — Extractors (narrative from PDF) vs Composers (USDM entities → prose)
- **M11 conformance validator** — Title page, synopsis, section coverage scoring
- **Output**: `m11_protocol.docx` + `m11_conformance.json`

### Pipeline Decomposition

Decomposed monolithic `pipeline/orchestrator.py` into focused modules:

| Module | Lines | Purpose |
|--------|-------|---------|
| **`pipeline/combiner.py`** | 420 | `combine_to_full_usdm()`, USDM defaults, SoA integration |
| **`pipeline/integrations.py`** | 289 | SAP/sites integration, content refs, estimand reconciliation |
| **`pipeline/post_processing.py`** | 436 | Entity reconciliation, activity sources, procedure linking |
| **`pipeline/promotion.py`** | 260 | Extension→USDM promotion rules (4 rules) |

### LLM Provider Abstraction

New `providers/` module replacing inline LLM logic:

| File | Purpose |
|------|---------|
| **`providers/base.py`** | `BaseProvider` ABC with `generate()` and `generate_with_image()` |
| **`providers/factory.py`** | Auto-detect provider from model name |
| **`providers/gemini.py`** | GeminiProvider (Vertex AI) |
| **`providers/openai_provider.py`** | OpenAIProvider |
| **`providers/anthropic_provider.py`** | AnthropicProvider |
| **`providers/tracker.py`** | `TokenUsageTracker` with per-phase cost breakdown |

### Testing Infrastructure (E7–E13)

| Enhancement | Details |
|-------------|---------|
| **E7** | `pyproject.toml` with pytest config, test discovery |
| **E8** | E2E integration tests (33 tests, `--run-e2e` marker) |
| **E9** | `pytest-cov` coverage tracking with HTML reports |
| **E10** | Mocked LLM tests for 5 extractors + 9 composers (80 tests) |
| **E13** | PipelineContext contract tests (48 tests, 93.6% coverage) |

#### New Test Files

| File | Tests | Coverage Target |
|------|-------|----------------|
| `tests/test_extractors.py` | 58 | metadata, eligibility, objectives, studydesign, interventions |
| `tests/test_composers.py` | 22 | All 9 M11 entity composers |
| `tests/test_pipeline_context.py` | 48 | PipelineContext (93.6% coverage) |
| `tests/test_e2e_pipeline.py` | 33 | Full pipeline integration |
| `tests/test_pipeline_registry.py` | 11 | Phase registry, promotion, orchestrator |
| `tests/test_token_tracker.py` | 12 | TokenUsageTracker |
| `tests/test_m11_regression.py` | — | M11 renderer regression |
| `tests/conftest.py` | — | Shared fixtures, `--run-e2e` marker |

**Test suite**: 372 passed, 33 skipped (e2e), 0 failed  
**Coverage**: 42.5% overall

### PipelineContext Contract Tightening

- Extracted `PHASE_FIELD_OWNERSHIP` constant — single source of truth for merge field mapping
- 48 tests covering init, update, query, snapshot/merge, serialization, and contract validation
- `pipeline_context.py` coverage: 0% → 93.6%

### Files Changed

**New:**
* `rendering/` — M11 renderer, composers, tables
* `validation/m11_conformance.py` — M11 conformance scoring
* `providers/` — LLM provider abstraction (6 files)
* `pipeline/combiner.py`, `pipeline/integrations.py`, `pipeline/post_processing.py`, `pipeline/promotion.py`
* `core/m11_mapping_config.py` — M11↔USDM mapping
* `tests/` — 8 new test files
* `pyproject.toml` — pytest + coverage config

**Modified:**
* `extraction/pipeline_context.py` — `PHASE_FIELD_OWNERSHIP` constant
* `requirements.txt` — Added `pytest-cov>=7.0.0`
* `.gitignore` — Added `htmlcov/`, `.coverage`

---

## [7.2.1] – 2026-02-08

### Execution Model Promoter Bug Fixes

Fixed critical bugs preventing repetitions and transitions from being promoted to core USDM.

#### Repetition Promotion Fix

| Issue | Fix |
|-------|-----|
| **`TypeError: int - NoneType` crash** | `_iso_duration_to_days()` returns `None` for unrecognized ISO strings; added `or 1` fallback after duration parsing |
| **Cascading failure** | Step 2 crash blocked Steps 3–10 (admins, windows, conditions, transitions); added per-step fault isolation |
| **Missing activity matches** | Added word-level fuzzy matching for activity names (e.g., "controlled diet" → "Cu/Mo-controlled meals") |
| **ISO 8601 parsing** | Added `_iso_duration_to_days()` helper for `P7D`, `P1W`, `P2M` duration strings |

**Result**: 0 → 32 repetition instances from 64 extracted patterns.

#### Transition Rule Promotion Fix

| Issue | Fix |
|-------|-----|
| **Encounter reconciliation drops rules** | `ReconciledEncounter.to_usdm_dict()` reconstructs from scratch; added preservation by name in `_run_reconciliation()` |
| **Encounter normalization drops rules** | `normalize_encounter()` only passed 6 fields to constructor; added `transitionStartRule`/`transitionEndRule` preservation |
| **Missing encounter fields** | Also preserved `scheduledAtTimingId`, `previousId`, `nextId` through normalization |

**Result**: 0 → 14 transition rules (6 start + 6 end) from 8 state machine transitions.

#### Fault Isolation

Wrapped each promoter step (2–10) in individual `try/except` blocks. This was critical: the Step 2 crash was silently preventing Steps 3–10, causing loss of administrations, visit windows, conditions, and transitions.

#### Files Changed

* `extraction/execution/execution_model_promoter.py` - Fixed duration parsing, added fault isolation, improved fuzzy matching
* `core/usdm_types_generated.py` - Preserved transition rules and encounter fields through normalization
* `pipeline/orchestrator.py` - Preserved transition rules through encounter reconciliation

#### Verified Results (Wilson's Protocol NCT04573309)

| Component | Before | After |
|-----------|--------|-------|
| Anchors | 3 | 3 |
| Repetition Instances | 0 (crash) | 32 |
| Transition Rules | 0 (stripped) | 14 |
| Administrations | 0 (blocked) | 2 |
| Visit Windows | 0 (blocked) | 11/11 |
| Conditions | 0 (blocked) | 30 |
| Schema Validation | PASSED | PASSED |
| CDISC Conformance | 0 errors | 0 errors |

---

## [7.2.0] – 2026-02-01

### Execution Model Promotion to Native USDM Entities

Execution model data previously stranded in `extensionAttributes` is now promoted to native USDM v4.0 entities.

#### New USDM Dataclasses (`core/usdm_types_generated.py`)

| Entity | Purpose |
|--------|---------|
| **`ScheduledDecisionInstance`** | Decision nodes in schedule timelines with conditional branching |
| **`ConditionAssignment`** | If/then rules within decision nodes (`condition` text + `conditionTargetId`) |
| **`StudyElement`** | Time building blocks with `transitionStartRule`/`transitionEndRule` for titration, washout |

#### Enhanced Existing Dataclasses

| Entity | New Fields |
|--------|-----------|
| **`Encounter`** | `transitionStartRule`, `transitionEndRule`, `previousId`, `nextId` |
| **`StudyDesign`** | `conditions[]`, `estimands[]`, `elements[]` |
| **`ScheduleTimelineExit`** | `name`, `exitId` |

#### Architecture

- `StudyDesign.conditions[]` now populated with `Condition` entities from footnote conditions
- `Encounter` entities carry `TransitionRule` for state machine transitions
- `StudyEpoch.previousId`/`nextId` chains populated from traversal constraints
- `Timing.windowLower`/`windowUpper` enrichment from visit window extraction

---

## [7.1.0] – 2026-01-31

### Phase Registry Architecture

Complete refactor of the pipeline orchestrator from a monolithic `main_v2.py` (3,068 lines) to a clean phase registry pattern.

#### New Files

| File | Purpose |
|------|---------|
| **`main_v3.py`** | New entry point replacing `main_v2.py` |
| **`pipeline/orchestrator.py`** | Registry-driven phase runner with dependency resolution |
| **`pipeline/base_phase.py`** | `BasePhase` abstract class and `PhaseResult` dataclass |
| **`pipeline/phase_registry.py`** | Global phase registry for `@register_phase` decorator |
| **`pipeline/phases/*.py`** | 13 individual phase modules (metadata, eligibility, objectives, etc.) |
| **`core/validation.py`** | Refactored validation: `validate_and_fix_schema`, `convert_ids_to_uuids` |

#### Key Changes

- **Default `--complete` mode**: No flags needed — full extraction runs by default
- **Default model**: `gemini-3-flash-preview` (Gemini Flash 3 via Vertex AI)
- **Parallel execution**: `--parallel` flag runs independent phases concurrently via `ThreadPoolExecutor`
- **Dependency graph**: Phases declare dependencies (e.g., eligibility depends on metadata); orchestrator resolves execution order
- **`main_v2.py` removed**: All functionality preserved in `main_v3.py` + `pipeline/`

#### Phase Dependency Graph

```
Wave 1 (parallel): Metadata, StudyDesign, Narrative, Advanced, Procedures, Scheduling, DocStructure, AmendmentDetails, Execution
Wave 2 (parallel): Eligibility (needs Metadata), Objectives (needs Metadata)
Wave 3 (parallel): Interventions (needs Metadata + StudyDesign)
```

---

## [6.10.0] – 2026-01-31

### Comprehensive SAP Extraction with STATO Ontology Mapping

Enhanced SAP extraction to support downstream systems and statistical test standardization via STATO ontology mapping.

#### New SAP Data Types

| Data Type | USDM Target | Purpose |
|-----------|-------------|---------|
| **Statistical Methods** | Extension | STATO-mapped analysis methods (ANCOVA, MMRM, etc.) |
| **Multiplicity Adjustments** | Extension | Type I error control (Hochberg, Bonferroni, etc.) |
| **Sensitivity Analyses** | Extension | Pre-specified robustness analyses |
| **Subgroup Analyses** | Extension | Pre-specified subgroups with interaction tests |
| **Interim Analyses** | Extension | Stopping boundaries and alpha spending |
| **Sample Size Calculations** | Extension | Power and sample size assumptions |

#### STATO Ontology Integration

Statistical methods are now mapped to STATO codes for interoperability:

| Method | STATO Code |
|--------|------------|
| ANCOVA | `STATO:0000029` |
| MMRM | `STATO:0000325` |
| Kaplan-Meier | `STATO:0000149` |
| Cox regression | `STATO:0000223` |
| Chi-square | `STATO:0000049` |
| Fisher exact | `STATO:0000073` |

#### CDISC ARS (Analysis Results Standard) Linkage

New fields added for ARS interoperability:

| SAP Entity | ARS Field | Purpose |
|------------|-----------|---------|
| `StatisticalMethod` | `arsOperationId` | ARS operation codes (e.g., `Mth01_ContVar_Ancova`) |
| `StatisticalMethod` | `arsReason` | `PRIMARY`, `SENSITIVITY`, `EXPLORATORY` |
| `SensitivityAnalysis` | `arsReason` | Analysis classification |
| `InterimAnalysis` | `arsReportingEventType` | `INTERIM_1`, `INTERIM_2`, `FINAL` |

#### CDISC ARS Deep Integration (6.11.0)

Full ARS model generation with automatic conversion from SAP data:

- **ARS Generator** (`extraction/conditional/ars_generator.py`)
  - `ReportingEvent` - Top-level container for analyses
  - `Analysis` - Individual analysis specification with reason/purpose
  - `AnalysisSet` - Population definitions linked to USDM
  - `AnalysisMethod` - Statistical methods with STATO mapping
  - `Operation` - Standard operations per method type

- **Output**: `ars_reporting_event.json` generated alongside USDM

- **Web UI**: New "CDISC ARS" tab under Data → Timeline with:
  - Overview panel with entity counts and reason breakdown
  - Analysis Sets panel with USDM linkage
  - Methods panel with operations hierarchy
  - Analyses panel with method/set linking
  - Categories panel for analysis organization

#### Files Changed

**Core:**
* `extraction/conditional/sap_extractor.py` - Added 6 new dataclasses, enhanced prompt with STATO/ARS mapping
* `extraction/conditional/ars_generator.py` - **NEW** Full ARS model generator
* `pipeline/orchestrator.py` - Merge SAP elements into USDM extensions, generate ARS output

**Web UI:**
* `web-ui/components/protocol/ExtensionsView.tsx` - Added SAP Data category with 8 extension types
* `web-ui/components/timeline/ARSDataView.tsx` - **NEW** CDISC ARS visualization component
* `web-ui/components/timeline/SAPDataView.tsx` - Added ARS linkage display
* `web-ui/app/api/protocols/[id]/ars/route.ts` - **NEW** API endpoint for ARS data
* `web-ui/app/protocols/[id]/page.tsx` - Added CDISC ARS tab

**Documentation:**
* `docs/SAP_EXTENSIONS.md` - New comprehensive SAP extension schema documentation

---

## [6.9.0] – 2026-01-07

### Gemini 3 Flash Support with Intelligent Fallback

Added full support for `gemini-3-flash-preview` model with automatic fallback to `gemini-2.5-pro` for SoA text extraction due to JSON format compliance issues.

#### New Features

| Feature | Description |
|---------|-------------|
| **Gemini 3 Flash Support** | Full support for `gemini-3-flash-preview` as primary model |
| **SoA Extraction Fallback** | Automatic fallback to `gemini-2.5-pro` for SoA text extraction |
| **Response Validation** | New validation system checks LLM response structure |
| **Retry Logic** | Up to 2 retries with correction prompts on validation failure |
| **Stricter Prompts** | Enhanced prompt guardrails for JSON format compliance |

#### SoA Extraction Fallback

When using `gemini-3-flash-preview` or `gemini-3-flash`, the pipeline automatically uses `gemini-2.5-pro` for SoA text extraction only. This is because Gemini 3 Flash models have issues with structured JSON output format compliance for the complex SoA extraction task.

```python
# In extraction/pipeline.py
SOA_FALLBACK_MODELS = {
    'gemini-3-flash-preview': 'gemini-2.5-pro',
    'gemini-3-flash': 'gemini-2.5-pro',
}
```

**Log output:**
```
[INFO] Step 2: Extracting SoA data from text...
[INFO]   Using fallback model for SoA text extraction: gemini-2.5-pro
```

#### Response Validation & Retry

New `validate_extraction_response()` function in `extraction/text_extractor.py`:

| Check | Description |
|-------|-------------|
| Root keys | Verifies `activities` key exists at root level |
| Wrong structure | Detects nested USDM format instead of flat `{activities, activityTimepoints}` |
| Minimum activities | Ensures at least `2 * num_groups` activities extracted |
| Activity structure | Validates each activity has `id` and `name` |

On validation failure, retry with correction prompt:
```
Your previous response had an invalid format: {error}
REMINDER: Return FLAT JSON with only "activities" and "activityTimepoints" at root
```

#### Environment Pollution Fix

Fixed issue where Gemini 3's global endpoint setting polluted the environment for fallback models:

**Before:** `os.environ['GOOGLE_CLOUD_LOCATION'] = 'global'` caused gemini-2.5-pro to fail
**After:** Use explicit `Client(vertexai=True, project=..., location='global')` for Gemini 3 only

#### Visit Windows Epoch Resolution

Enhanced `resolveEpochName()` in `ExecutionModelView.tsx`:

| Fix | Description |
|-----|-------------|
| Late-study visits | Day 162, Day 365 now assigned to EOS epoch |
| Gap filling | Day 0 (Baseline) resolved by interpolating from nearest neighbors |
| Day-based matching | Uses `dayToEpochMap` from USDM encounters instead of name matching |

#### Files Changed

**Core:**
* `extraction/pipeline.py` - Added `SOA_FALLBACK_MODELS` and fallback logic
* `extraction/text_extractor.py` - Added `validate_extraction_response()`, retry logic, stricter prompts
* `llm_providers.py` - Fixed environment pollution, explicit Gemini 3 client config

**Web UI:**
* `web-ui/components/timeline/ExecutionModelView.tsx` - Enhanced `resolveEpochName()` with day-based matching

#### Best Run Results (Commit ef3e0a0)

```bash
python main_v2.py input/Alexion_NCT04573309_Wilsons.pdf --complete \
  --sap input/Alexion_NCT04573309_Wilsons_SAP.pdf \
  --sites input/Alexion_NCT04573309_Wilsons_sites.csv \
  --model gemini-3-flash-preview
```

| Metric | Result |
|--------|--------|
| SoA Activities | 36 |
| SoA Ticks | 216 |
| Expansion Phases | 12/12 ✓ |
| Schema Validation | PASSED ✓ |
| Semantic Validation | PASSED ✓ |
| Reconciled Epochs | 7 |
| Reconciled Encounters | 24 |
| Reconciled Activities | 43 |

---

## [6.8.0] – 2026-01-02

### Execution Model Promotion to Core USDM

Major architectural change: execution model data (anchors, repetitions, dosing) is now materialized into **core USDM entities**, not just stored in extensions.

#### Problem Addressed

Downstream consumers (synthetic generators) couldn't use execution semantics because they were stored in `extensionAttributes` as JSON strings. Core USDM was incomplete.

#### Solution: ExecutionModelPromoter

| Promotion | Input | Output |
|-----------|-------|--------|
| Time Anchors | `x-executionModel-timeAnchors` | `ScheduledActivityInstance` |
| Repetitions | `x-executionModel-repetitions` | Expanded `ScheduledActivityInstance` per occurrence |
| Dosing Regimens | `x-executionModel-dosingRegimens` | `Administration` entities linked to interventions |
| Dangling Refs | `Timing.relativeFromScheduledInstanceId` | Fixed or auto-created anchor instances |

#### Key Contract

**Extensions are now OPTIONAL/DEBUG. Core USDM is self-sufficient.**

#### Files Added/Changed

* `extraction/execution/execution_model_promoter.py` - **NEW** Main promotion logic
* `extraction/execution/pipeline_integration.py` - Integrated promoter after reconciliation
* `docs/ARCHITECTURE.md` - Documented promotion architecture

---

## [6.7.3] – 2026-01-02

### New Comprehensive Benchmark Tool

Rewrote benchmark script from scratch with modern architecture.

#### Features

| Feature | Description |
|---------|-------------|
| **CLI Arguments** | Accepts golden and extracted paths as arguments |
| **Auto-detection** | Finds `protocol_usdm.json` in timestamped directories |
| **Per-entity Metrics** | Precision, recall, F1 for each entity type |
| **18 Entity Types** | Full coverage of USDM 4.0 entities |
| **Semantic Matching** | Configurable similarity threshold (default 75%) |
| **Verbose Mode** | Shows unmatched entities for debugging |
| **JSON Reports** | Machine-readable output for CI/CD integration |

#### Usage

```bash
python testing/benchmark.py <golden.json> <extracted_dir/> [--verbose]
```

#### Files Added

* `testing/benchmark.py` - New comprehensive benchmark tool

---

## [6.7.2] – 2026-01-02

### Full USDM 4.0 Schema Alignment

Achieved **0 validation errors** - full alignment with USDM 4.0 schema.

#### Fixes

| Fix | Description |
|-----|-------------|
| **standardCode Preservation** | Fixed `normalize_usdm_data` to preserve `standardCode` on Code objects |
| **administrableDoseForm Fallback** | Added standardCode injection in fallback intervention path |

#### Web UI Enhancements

| Enhancement | Description |
|-------------|-------------|
| **Instance Names in Graph** | Timeline graph shows human-readable instance names |
| **Instance Names in Tooltips** | SoA table cells show instance names on hover |
| **Cell Metadata** | Added timingId, epochId to cell data for enhanced linking |

#### Files Changed

* `core/usdm_types_generated.py` - Preserve standardCode during Code normalization
* `main_v2.py` - Added standardCode injection for fallback products
* `web-ui/lib/adapters/toGraphModel.ts` - Use instance names for node labels
* `web-ui/lib/adapters/toSoATableModel.ts` - Add instance metadata to cells
* `web-ui/components/soa/ProvenanceCellRenderer.tsx` - Show instance names in tooltips
* `tests/test_core_modules.py` - Added normalization tests (2 new tests)

#### Validation Results

```
✅ VALIDATION PASSED - 0 errors
✅ CDISC Conformance: 0 errors, 0 warnings
✅ 25/25 unit tests passing
```

---

## [6.7.1] – 2026-01-02

### Additional USDM Schema Fixes

Continued schema alignment improvements addressing validation errors.

#### Fixes

| Fix | Description |
|-----|-------------|
| **AnalysisPopulation.text** | Added required `text` field to SAP population extraction |
| **Timing Required Fields** | Added `name`, `valueLabel`, `relativeToFrom`, `relativeFromScheduledInstanceId` with defaults |
| **arms Fallback** | Default treatment arm created when not extracted |
| **studyCells Fallback** | Auto-generated arm×epoch cells when missing |
| **timingId Linking** | Improved multi-strategy matching (exact name, day number, visit number) |

#### Files Changed

* `extraction/conditional/sap_extractor.py` - Added `text` field to AnalysisPopulation.to_dict()
* `core/usdm_types_generated.py` - Enhanced Timing class with required USDM fields
* `main_v2.py` - Added arms/studyCells fallbacks, improved `link_timing_ids_to_instances()`

---

## [6.7.0] – 2026-01-02

### ScheduledActivityInstance USDM Conformance Enhancements

Enhanced `ScheduledActivityInstance` generation to improve USDM 4.0 schema alignment and data quality.

#### New Features

| Enhancement | Description |
|-------------|-------------|
| **epochId Population** | Instances now inherit `epochId` from their linked Encounter |
| **Human-Readable Names** | Instance names changed from `"act_1@enc_1"` to `"Blood Draw @ Day 1"` |
| **timingId Linking** | Instances linked to Timing entities when scheduling data available |
| **ScheduleTimeline.timings** | Added `timings` field to ScheduleTimeline class per USDM schema |

#### Files Changed

**Core Types (`core/usdm_types.py`):**
* `Timeline.to_study_design()` - Enhanced with epochId population and better naming
* Built encounter→epoch and activity→name lookup maps
* Name truncation (50/30 chars) to keep instance names reasonable

**Generated Types (`core/usdm_types_generated.py`):**
* `ScheduleTimeline` - Added `timings: List[Timing]` field
* `to_dict()` now serializes timings array

**Pipeline (`main_v2.py`):**
* Added `link_timing_ids_to_instances()` function
* Multi-strategy matching: exact name → day number → visit number
* Called after scheduling data is merged into scheduleTimeline

#### Sample Output

```json
{
  "id": "uuid",
  "name": "Physical Examination @ Day 1",
  "activityIds": ["activity-uuid"],
  "encounterId": "encounter-uuid",
  "epochId": "epoch-uuid",
  "timingId": "timing-uuid",
  "instanceType": "ScheduledActivityInstance"
}
```

#### Reference

Per USDM 4.0 `dataStructure.yml`:
- `ScheduledActivityInstance.epochId`: 0..1 (optional, reference to StudyEpoch)
- `ScheduledActivityInstance.timingId`: 0..1 (optional, reference to Timing)
- `ScheduleTimeline.timings`: 0..* (list of Timing entities)

---

## [6.6.0] – 2026-01-02

### USDM Entity Placement Alignment

Full audit and fix of entity placement to comply with official CDISC `dataStructure.yml`.

#### Entity Placement Changes

All entities now placed at their correct USDM hierarchical locations:

| Entity | Before | After |
|--------|--------|-------|
| `eligibilityCriterionItems` | `studyDesign` | `studyVersion` |
| `organizations` | `study` | `studyVersion` |
| `narrativeContentItems` | root (`narrativeContents`) | `studyVersion` |
| `abbreviations` | root | `studyVersion` |
| `conditions` | root | `studyVersion` |
| `amendments` | root | `studyVersion` |
| `administrableProducts` | root | `studyVersion` |
| `medicalDevices` | root | `studyVersion` |
| `studyInterventions` | `studyDesign` | `studyVersion` |
| `indications` | `study` | `studyDesign` |
| `analysisPopulations` | root | `studyDesign` |
| `timings` | root | `scheduleTimeline.timings` |
| `scheduleTimelineExits` | root | `scheduleTimeline.exits` |
| `procedures` | root | `activity.definedProcedures` |

#### Files Changed

**Pipeline (`main_v2.py`):**
* Moved entity assignments to correct USDM locations
* Added USDM placement comments referencing `dataStructure.yml`

**UI Components:**
* `EligibilityCriteriaView.tsx` - Read `eligibilityCriterionItems` from `studyVersion`
* `ProceduresDevicesView.tsx` - Read `medicalDevices` from `studyVersion`
* `QualityMetricsDashboard.tsx` - Read `timings` from `scheduleTimeline`, interventions from `studyVersion`
* `DocumentStructureView.tsx` - Read `narrativeContentItems` from `studyVersion`

#### Documentation Updates

* Updated `docs/ARCHITECTURE.md` with USDM Output Structure section
* Updated `README.md` with entity hierarchy diagram
* Updated `QUICK_REFERENCE.md` with entity placement table
* Added migration notes for v6.6 changes

#### Reference

Entity placement verified against:
- `https://github.com/cdisc-org/DDF-RA/blob/main/Deliverables/UML/dataStructure.yml`
- USDM workshop manual examples

---

## [6.4.1] – 2025-11-30

### Provenance & Viewer Fix - Tick Color Display

Fixed critical bug where SoA viewer showed no colored ticks despite correct provenance data.

#### Root Cause
UUID namespace mismatch between:
- `enc_*` IDs → encounter UUIDs (used by encounters array and provenance)
- `pt_*` IDs → timepoint UUIDs (used by `ScheduledActivityInstance.encounterId`)

#### Fixes
* **`main_v2.py`**: `convert_provenance_to_uuids()` now maps `pt_N` → `enc_N` UUIDs
* **`soa_streamlit_viewer.py`**: 
  - Loads `id_mapping.json` to build `pt_uuid → enc_uuid` mapping
  - Attaches mapping to content for instance ID resolution
  - All 211 ticks now display with proper provenance coloring

#### Model Availability Note
* **GPT-5 / GPT-5.1 / GPT-5.1-pro**: These model names do NOT exist on OpenAI API
* **Valid models**: `gpt-4.1`, `gpt-4o`, `gpt-4o-mini`, `o3`, `o4-mini`
* Recommend: `claude-opus-4-5` or `gemini-2.5-pro` for best results

---

## [6.4.0] – 2025-11-30

### Parser Fixes for USDM-Aligned LLM Responses

The LLM now produces USDM-aligned output directly (with `id`, `instanceType`, proper Code objects).
All 7 extraction parsers were updated to handle both the new format and legacy format.

#### Fixed Parsers
* **`extraction/objectives/extractor.py`**: Added `_parse_usdm_format()` for flat objectives/endpoints with level codes
* **`extraction/eligibility/extractor.py`**: Added `_parse_usdm_eligibility_format()` for criteria with `eligibilityCriterionItems` lookup
* **`extraction/metadata/extractor.py`**: Fixed identifier parsing (accept `text` and `value`), indication handling
* **`extraction/studydesign/extractor.py`**: Accept USDM key names (`studyArms`, `studyCohorts`, `studyEpochs`)
* **`extraction/interventions/extractor.py`**: Accept USDM key names, use provided IDs
* **`extraction/narrative/extractor.py`**: Accept key variations for abbreviations
* **`extraction/advanced/extractor.py`**: Handle top-level `countries` array, use provided IDs

#### New Tools
* **`testing/audit_extraction_gaps.py`**: Audit tool to detect raw vs parsed mismatches using USDM schema

#### Viewer Improvements
* Removed obsolete "Config Files" tab from Streamlit viewer

---

## [6.3.0] – 2025-11-29

### NCI EVS Terminology Enrichment

#### New Feature: Real-time NCI EVS API Integration
* **`core/evs_client.py`**: NCI EVS API client with local caching
  - Connects to EVS CT API (`evs.nci.nih.gov/ctapi/v1/ct/term`)
  - Connects to EVS REST API (`api-evsrest.nci.nih.gov`)
  - 30-day cache TTL for offline operation
  - Pre-defined 33 USDM-relevant NCI codes
* **`enrichment/terminology.py`**: Rewrote to use EVS client
  - Enriches: StudyPhase, BlindingSchema, Objectives, Endpoints, Eligibility, StudyArms
  - Generates `terminology_enrichment.json` report

#### New CLI Options
* `--enrich`: Run NCI terminology enrichment (Step 7)
* `--update-evs-cache`: Force refresh of EVS terminology cache
* `--update-cache`: Update CDISC CORE rules cache

#### Pipeline Improvements
* **Provenance ID conversion**: Provenance IDs now converted to UUIDs to match data
* **Simplified validation pipeline**: Removed redundant `llm_schema_fixer`, normalization now handles type inference
* **CDISC CORE integration**: Local CORE engine with automatic cache management

#### Documentation Updates
* Updated README.md with `--enrich` in example command
* Updated docs/ARCHITECTURE.md with EVS client documentation
* Added NCI EVS to acknowledgments

---

## [6.2.0] – 2025-11-29

### Schema-Driven Architecture Consolidation

#### Single Source of Truth
* **Consolidated on official CDISC schema**: All types, prompts, and validation now derive from `dataStructure.yml`
* **Removed manual type maintenance**: Archived `usdm_types_v4.py` - no longer maintained
* **Removed manual entity mapping**: Archived `soa_entity_mapping.json` - generated from schema
* **New architecture documentation**: See `docs/ARCHITECTURE.md` for complete overview

#### New Schema-Driven Modules
* **`core/usdm_schema_loader.py`**: Downloads, caches, and parses official CDISC schema
  - 86+ entity definitions with NCI codes, definitions, cardinality
  - Auto-updates: `USDMSchemaLoader().ensure_schema_cached(force_download=True)`
* **`core/usdm_types_generated.py`**: Official USDM types with all required fields
  - Auto-generated UUIDs for `id` fields
  - Intelligent defaults for Code fields (type inference from names)
* **`core/schema_prompt_generator.py`**: Generates LLM prompts from schema
  - Prompts include NCI codes and official definitions
  - Entity groups categorized by function (soa_core, study_design, etc.)
* **`core/usdm_types.py`**: Unified interface
  - Official types from `usdm_types_generated.py`
  - Internal extraction types (Timeline, HeaderStructure, PlannedTimepoint, etc.)

#### Archived Legacy Files (in `archive/legacy_pipeline/`)
* `usdm_types_v4.py` - Manual type definitions
* `soa_entity_mapping.json` - Manual entity mapping
* `generate_soa_llm_prompt.py` - Manual prompt generation
* `usdm_types_old.py` - Previous usdm_types.py

#### Benefits
* **Future-proof**: Schema updates automatic with `force_download=True`
* **Accurate prompts**: LLM prompts reflect exact schema requirements
* **Consistent validation**: Types enforce same rules as validator
* **Reduced maintenance**: No manual sync between types/prompts/validation

### Repository Cleanup

#### New Directory Structure
* **`testing/`**: Benchmarking and integration tests
  - `benchmark_models.py`, `compare_golden_vs_extracted.py`
  - `test_pipeline_steps.py`, `test_golden_comparison.py`
* **`utilities/`**: Setup and utility scripts
  - `setup_google_cloud.ps1`

#### Files Archived
* `json_utils.py` (root) → `archive/legacy_pipeline/` (duplicate of core/)
* `soa_prompt_example.json` → `archive/legacy_pipeline/`
* `usdm_examples.py` → `archive/legacy_pipeline/`
* Non-optimized prompts → `archive/prompts_legacy/`

#### Files Deleted
* `Protocol2USDM Review.pdf` - Obsolete
* `debug_provenance.py` - Debug utility
* `archive/logs/*` - 201 old log files

#### Prompts Consolidated
* Removed `_optimized` suffix from prompts (archived originals)
* `find_soa_pages.yaml`, `soa_extraction.yaml`, `soa_reconciliation.yaml`, `vision_soa_extraction.yaml`

#### Extraction Schema Files Updated
* All 11 extraction modules now import utilities from `core/usdm_types`
* Added clear documentation about extraction types vs official USDM types

---

## [6.1.3] – 2025-11-29

### Header Structure & Viewer Robustness

#### Improved Header Analyzer Prompt
* **Strengthened encounter naming requirements**: Prompt now explicitly requires unique encounter names with timing info from sub-headers
* Added detailed examples showing proper naming patterns (e.g., "Screening (-42 to -9)", "Day -6 through -4")
* Added CRITICAL section emphasizing unique naming requirement
* Models should now extract distinct column names that include Day/Week/Visit timing

#### Post-Processing Safety Net
* **Added encounter name uniqueness enforcement**: If LLM produces duplicate encounter names, they are automatically made unique by appending column numbers
* Logs warning when duplicates are detected and fixed
* Ensures viewer always receives unique column identifiers

#### Fixed Duplicate Column Handling in Viewer
* **Fixed duplicate column handling**: Viewer now uses positional indexing for columns, fixing false "orphaned" counts when encounter names repeat
* Orphaned tick counting and provenance styling now work correctly even if duplicate names slip through

#### SoA Page Detection Improvements
* **Fixed gap filling in page detection**: Now fills gaps between detected pages (e.g., if pages 13 and 15 detected, page 14 is automatically included)
* **Iterative expansion**: Adjacent page detection now continues until no more pages added
* **More permissive previous page check**: Checks for table content, not just "Schedule of Activities" title

#### USDM v4.0 Schema Alignment (Source Fixes)
* **Code objects now include all required fields**: `id`, `codeSystem`, `codeSystemVersion`, `decode`, `instanceType`
* **StudyDesign property names fixed at source**: `studyArms` → `arms`, `studyDesignPopulation` → `population`
* **StudyDesign required fields added**: `name`, `rationale`, `model` now populated by default
* **ScheduledActivityInstance.name**: Now auto-generated as `{activityId}@{encounterId}`
* **Schema fixer enhanced**: Added programmatic fixes for all these issues as safety net
* **Viewer backward compatible**: Handles both old and new property names

#### Schema-Generated Types from Official CDISC Source
* **New source of truth**: Types generated from official `dataStructure.yml`:
  - URL: https://github.com/cdisc-org/DDF-RA/blob/main/Deliverables/UML/dataStructure.yml
  - Contains 86+ USDM entities with NCI codes, definitions, and cardinality
* **New files**:
  - `core/usdm_schema_loader.py` - Downloads/caches schema, parses entities
  - `core/usdm_types_generated.py` - Python types with all required fields
  - `core/schema_cache/dataStructure.yml` - Cached official schema
* **Automatic required fields**: Types now auto-populate all required fields:
  - Code: `id`, `codeSystem`, `codeSystemVersion`, `decode`
  - StudyArm: `type`, `dataOriginType`, `dataOriginDescription`
  - Encounter/StudyEpoch: `type` (with intelligent defaults)
  - ScheduleTimeline: `entryCondition`, `entryId`
  - AliasCode (blindingSchema): `standardCode`
* **Future-proofing**: Run `USDMSchemaLoader().ensure_schema_cached(force_download=True)` when new USDM versions release
* **Backward compatible**: Existing imports from `core.usdm_types` continue to work

#### Official USDM Package Validation (Refactored Pipeline)
* **Replaced custom validator with official `usdm` package**: Uses CDISC's Pydantic models for authoritative validation
* **UUID ID conversion**: All simple IDs (e.g., `study_1`, `act_1`) now converted to proper UUIDs (saved in `id_mapping.json`)
* **Three-stage validation pipeline**:
  1. UUID conversion (required by USDM 4.0)
  2. Comprehensive schema fixes (Code objects, StudyArm, AliasCode, etc.)
  3. Final validation via official `usdm` Pydantic package
* **Comprehensive Code object fixer**: Recursively finds and fixes all Code objects to include:
  - `id` (UUID), `codeSystem`, `codeSystemVersion`, `instanceType`
  - StudyArm: `type`, `dataOriginDescription`, `dataOriginType`
  - AliasCode (blindingSchema): `id`, `standardCode`, `instanceType`
* **New exports from `validation` package**:
  - `validate_usdm_dict()`, `validate_usdm_file()` - Primary validation functions
  - `HAS_USDM`, `USDM_VERSION` - Check if package is installed
  - `USDMValidator` - Class for advanced usage
* **Updated viewer**: Shows validator type (Official vs Custom), groups errors by type
* **Output files**: `usdm_validation.json` (detailed), `schema_validation.json` (summary)
* **Install with**: `pip install usdm` (added to requirements.txt)
* **OpenAPI validator deprecated**: Still used for issue detection, but official package is authoritative

---

## [6.1.2] – 2025-11-28

### Activity Groups & SoA Footnotes

#### Activity Group Hierarchy (USDM v4.0 Aligned)
* **Fixed activity group handling**: Groups now correctly represented as parent Activities with `childIds`
* Activities linked to groups via `activityGroupId` field during extraction
* `Timeline.to_study_design()` converts groups to USDM v4.0 aligned structure
* Vision verification extracts visual properties (bold, merged cells) for groups
* Viewer correctly displays hierarchical grouping with rowspan

#### SoA Footnotes Support
* **Added SoA footnote storage**: Footnotes from header structure now stored in `StudyDesign.notes`
* Uses USDM v4.0 `CommentAnnotation` objects per CDISC specification
* Viewer displays footnotes in collapsible expander below SoA table
* Fallback loading from `4_header_structure.json` when not in final output

#### Provenance Fixes
* **Fixed provenance ID mismatch**: Viewer now correctly maps `enc_*` IDs to `pt_*` IDs
* Orphaned tick counting fixed to use same ID mapping as styling
* Provenance statistics now accurate (was showing false "orphaned" counts)

#### Metadata Extraction Fix
* **Fixed `studyPhase` parsing**: Now handles both string and dict formats from LLM response
* Prevents "Failed to parse metadata response" errors

#### Viewer Improvements
* Footnotes section now collapsible (expander)
* JSON viewer now collapsible (expander instead of checkbox)
* Cleaner UI with consistent expander styling

---

## [6.1.1] – 2025-11-28

### SoA Page Detection & USDM Structure Fixes

#### SoA Page Detection
* **Fixed multi-page SoA detection**: Added title page detection and adjacent page expansion
* Pages with "Table X: Schedule of Activities" are now anchor pages
* Adjacent continuation pages automatically included
* Pipeline now calls `find_soa_pages()` instead of bypassing to heuristic-only detection

#### USDM v4.0 Structure Alignment
* **Fixed schema validation error**: "Study must have at least one version"
* Changed output structure from flat `studyDesigns[]` to proper `study.versions[0].studyDesigns[]`
* Added `study_version` wrapper with proper USDM v4.0 nesting

#### CDISC CORE Engine
* Fixed CORE engine invocation by adding required `-v 4.0` version parameter

#### Documentation
* Updated README, USER_GUIDE, QUICK_REFERENCE with new default example command
* Added Roadmap/TODO section with planned features

---

## [6.1] – 2025-11-28

### Provenance-Based Cell Retention

Changed default behavior to **keep all text-extracted cells** in the final USDM output, using provenance to indicate confidence level rather than removing unconfirmed cells.

#### Key Changes

* **Default: Keep all text-extracted cells**
  - Changed `remove_hallucinations` default from `True` to `False` in `PipelineConfig`
  - All cells found by text extraction are now included in `protocol_usdm.json`
  - Downstream computable systems receive complete data and can filter by provenance

* **Enhanced validation tagging**
  - Confirmed cells (text + vision agree): tagged as `"both"` (🟩 green)
  - Unconfirmed cells (text only): tagged as `"text"` (🟦 blue)
  - Vision-only cells: tagged as `"vision"` or `"needs_review"` (🟧 orange)

* **New CLI flag**
  - Added `--remove-hallucinations` flag to restore old behavior (exclude unconfirmed cells)

#### Files Changed

* `extraction/pipeline.py` – Changed default config
* `extraction/validator.py` – Updated `apply_validation_fixes()` to properly tag confirmed vs unconfirmed cells

#### Viewer Improvements

* Added debug expander showing provenance status and ID matching
* Added style map debug showing color distribution
* Fixed provenance color application in SoA table

#### Documentation

* Updated README.md, USER_GUIDE.md, QUICK_REFERENCE.md with new provenance behavior
* Added provenance source table explaining colors and meanings

---

## [6.0] – 2025-11-27

### USDM Expansion - Full Protocol Extraction

Major expansion to extract full protocol content beyond Schedule of Activities, with integrated pipeline and enhanced viewer.

#### Integrated Pipeline

The main pipeline now supports full protocol extraction with a single command:

```bash
python main_v2.py protocol.pdf                    # SoA only (default)
python main_v2.py protocol.pdf --metadata         # SoA + metadata
python main_v2.py protocol.pdf --full-protocol    # Everything
python main_v2.py protocol.pdf --expansion-only   # Expansions only, skip SoA
```

New flags:
* `--metadata` – Extract study metadata (Phase 2)
* `--eligibility` – Extract eligibility criteria (Phase 1)
* `--objectives` – Extract objectives & endpoints (Phase 3)
* `--studydesign` – Extract study design structure (Phase 4)
* `--interventions` – Extract interventions & products (Phase 5)
* `--narrative` – Extract narrative structure (Phase 7)
* `--advanced` – Extract amendments & geography (Phase 8)
* `--full-protocol` – Extract everything (SoA + all phases)
* `--expansion-only` – Skip SoA, run only expansion phases

Combined output saved to `full_usdm.json` when multiple phases are run.

#### Enhanced Streamlit Viewer

* New "Protocol Expansion Data" section with tabbed navigation
* Tabs: Metadata, Eligibility, Objectives, Design, Interventions, Narrative, Advanced
* Auto-detects available expansion data files
* Shows key metrics and expandable raw JSON for each section
* Full backward compatibility with SoA-only viewing

#### New Extraction Modules (Phases 1-5, 7-8)

* **Phase 1: Eligibility Criteria** (`extraction/eligibility/`)
  - Extracts inclusion and exclusion criteria
  - Auto-detects eligibility pages using keyword heuristics
  - USDM entities: `EligibilityCriterion`, `EligibilityCriterionItem`, `StudyDesignPopulation`
  - CLI: `python extract_eligibility.py protocol.pdf`

* **Phase 2: Study Metadata** (`extraction/metadata/`)
  - Extracts study identity from title page and synopsis
  - USDM entities: `StudyTitle`, `StudyIdentifier`, `Organization`, `StudyRole`, `Indication`
  - CLI: `python extract_metadata.py protocol.pdf`

* **Phase 3: Objectives & Endpoints** (`extraction/objectives/`)
  - Extracts primary, secondary, exploratory objectives with linked endpoints
  - Supports ICH E9(R1) Estimand framework
  - USDM entities: `Objective`, `Endpoint`, `Estimand`, `IntercurrentEvent`
  - CLI: `python extract_objectives.py protocol.pdf`

* **Phase 4: Study Design Structure** (`extraction/studydesign/`)
  - Extracts design type, blinding, randomization, arms, cohorts
  - USDM entities: `InterventionalStudyDesign`, `StudyArm`, `StudyCell`, `StudyCohort`
  - CLI: `python extract_studydesign.py protocol.pdf`

* **Phase 5: Interventions & Products** (`extraction/interventions/`)
  - Extracts investigational products, dosing regimens, substances
  - USDM entities: `StudyIntervention`, `AdministrableProduct`, `Administration`, `Substance`
  - CLI: `python extract_interventions.py protocol.pdf`

* **Phase 7: Narrative Structure** (`extraction/narrative/`)
  - Extracts document structure, sections, and abbreviations
  - USDM entities: `NarrativeContent`, `Abbreviation`, `StudyDefinitionDocument`
  - CLI: `python extract_narrative.py protocol.pdf`

* **Phase 8: Advanced Entities** (`extraction/advanced/`)
  - Extracts protocol amendments, geographic scope, study sites
  - USDM entities: `StudyAmendment`, `GeographicScope`, `Country`, `StudySite`
  - CLI: `python extract_advanced.py protocol.pdf`

#### New Core Utilities

* `core/pdf_utils.py` – PDF text/image extraction utilities
* `core/llm_client.py` – Added `call_llm()` and `call_llm_with_image()` convenience functions

#### Output Files

New standalone extraction outputs:
```
output/<protocol>/
├── 2_study_metadata.json          # Phase 2
├── 3_eligibility_criteria.json    # Phase 1  
├── 4_objectives_endpoints.json    # Phase 3
├── 5_study_design.json            # Phase 4
├── 6_interventions.json           # Phase 5
├── 7_narrative_structure.json     # Phase 7
├── 8_advanced_entities.json       # Phase 8
└── 9_final_soa.json              # Existing SoA
```

#### Documentation

* `USDM_EXPANSION_PLAN.md` – 8-phase roadmap for full USDM v4.0 coverage
* Updated README, USER_GUIDE, QUICK_REFERENCE with new capabilities

---

## [5.1] – 2025-11-26

### Orphan Activity Recovery & Hierarchical Output

* Added orphan activity detection and vision-assisted recovery
* Added hierarchical USDM output (`9_final_soa_hierarchical.json`)
* Simplified provenance colors (consolidated `vision_suggested` into `needs_review`)

---

## [5.0] – 2025-11-26

### Major Refactor
* **New Simplified Pipeline** (`main_v2.py`) – Cleaner modular architecture
  - Vision extracts STRUCTURE (headers, groups)
  - Text extracts DATA (activities, ticks) using structure as anchor
  - Vision validates text extraction
  - Output is schema-compliant USDM JSON
* **Modular Extraction Package** (`extraction/`)
  - `pipeline.py` – Pipeline orchestration
  - `structure.py` – Header structure analysis
  - `text.py` – Text extraction
  - `validator.py` – Vision validation
* **Core Utilities** (`core/`) – Shared components

### Added
* **Gemini 3 Support** – Added `gemini-3-pro-preview` model
* **Model Benchmarking** – `benchmark_models.py` compares models across protocols
* **CDISC CORE Integration** – Built-in conformance validation (Step 9)
* **Terminology Enrichment** – NCI EVS code enrichment (Step 7)
* **Schema Validation** – USDM schema validation step (Step 8)
* **CORE Download Script** – `tools/core/download_core.py` for automatic setup
* **Validation & Conformance Tab** – New viewer tab showing validation results
* **Epoch Colspan Merge** – Table headers now properly merge consecutive epochs

### Changed
* **Documentation Overhaul** – Complete rewrite of README, USER_GUIDE, QUICK_REFERENCE
* **Pipeline Steps** – Simplified from 11 to 6 core steps (+3 optional post-processing)
* **Output Files** – New naming convention (e.g., `9_final_soa.json`)
* **Provenance** – Stored in separate file (`9_final_soa_provenance.json`)

### Archived
* Legacy pipeline (`main.py`, `reconcile_soa_llm.py`, `soa_postprocess_consolidated.py`)
* Old documentation (moved to `archive/docs_legacy/`)
* Unused scripts and tests

---

## [4.x] – 2025-11-26

### Added
* **Gemini 3.0 Support** – Added models to `llm_providers.py`
* **Vision Validation with Provenance** – Pipeline now tracks which ticks are:
  - ✓ Confirmed (both text and vision agree)
  - ⚠️ Needs Review (possible hallucinations or vision-only detections)
* **Step-by-Step Pipeline Testing** – `test_pipeline_steps.py` allows running individual pipeline steps for debugging
* **Improved Activity Group Rendering** – Viewer now displays activity groups with proper visual structure (rowspan grouping)

### Changed
* **Streamlit Viewer Cleanup** (1231 → 928 lines, -25%)
  - Removed duplicate functions (`get_timeline`, `get_timepoints`, `style_provenance`, `render_soa_table`)
  - Simplified tabs: 7 → 5 (removed legacy Post-Processed tab, merged Completeness Report into Quality Metrics)
  - Removed "hide all-X rows" checkbox
  - Simplified provenance legend to 3 colors (Text/Confirmed/Needs Review)
  - Images now display in 2-column grid
* **Provenance Format** – Cell provenance now correctly uses `plannedTimepointId` (was using empty `timepointId`)

### Archived
* `pipeline_api.py` – Referenced deleted `main.py`
* `validate_pipeline.py` – Referenced old output file names
* `tests/test_reconcile_soa_llm.py` – Tests archived reconciliation code
* `tests/test_soa_postprocess.py` – Tests archived postprocess code
* `docs_legacy/` → `archive/docs_legacy/` – 35 outdated documentation files

### Fixed
* Provenance cell keys now correctly formatted as `act_id|pt_id` (was `act_id|` with empty timepoint)
* Vision validation results now properly merged into provenance in step 6

---

## [Unreleased] – 2025-10-04
### Added
* **Multi-Model Provider Abstraction** – New `llm_providers.py` module providing unified interface for GPT and Gemini models
  * `LLMProvider` abstract base class with `OpenAIProvider` and `GeminiProvider` implementations
  * `LLMProviderFactory` with auto-detection from model names (e.g., "gpt-5", "gemini-2.5-pro")
  * GPT-5 support with automatic handling of `max_completion_tokens` parameter (differs from GPT-4)
  * Automatic fallback to legacy code if provider layer fails
  * 23 comprehensive unit tests (100% passing)
* **Prompt Template System** – New `prompt_templates.py` module for centralized prompt management
  * YAML-based template storage in `prompts/` directory
  * Variable substitution with defaults
  * Template validation following OpenAI best practices
  * `PromptRegistry` for caching and management
  * 19 comprehensive unit tests (100% passing)
* **Optimized SoA Extraction Prompt** – `prompts/soa_extraction.yaml` v2.0
  * Clear role & objective section
  * Step-by-step extraction process (6 explicit steps)
  * "What to DO" and "What NOT to DO" lists
  * Quality checklist before output
  * Visual separators for readability
  * Follows OpenAI cookbook optimization best practices
* **Enhanced send_pdf_to_llm.py** – Refactored to use provider layer
  * New `use_provider_layer` parameter (default: True)
  * Enhanced logging with token usage tracking
  * Full backward compatibility maintained
* **Prompt System Modernization** (Phases 1-3 Complete) – 2025-10-05
  * **Phase 1 - Critical Bug Fixes:**
    * Fixed `soa_prompt_example.json` to follow naming vs. timing rule
      * PlannedTimepoint.name now matches Encounter.name (no timing in name)
      * Added all required PlannedTimepoint fields (value, valueLabel, type, relativeToFrom)
      * Includes proper complex type structure for Encounter.type
    * Added comprehensive PlannedTimepoint field guidance in prompts
      * 8 required fields explained with examples
      * Common patterns documented (screening, baseline, follow-up)
      * Simple and windowed timepoint examples
    * Added Encounter.type field guidance with proper Code object structure
  * **Phase 2 - Enhanced Schema Embedding:**
    * Expanded embedded schema from 3 to 10 USDM components
    * Now includes: Timeline, Epoch, Encounter, PlannedTimepoint, Activity, ActivityTimepoint, ActivityGroup
    * LLMs now have complete field definitions for all SoA core entities
    * Smart truncation at entity boundaries (not mid-field)
    * Schema size tracking and logging (~2000 tokens)
  * **Phase 3 - YAML Template Migration:**
    * Created `prompts/soa_reconciliation.yaml` (v2.0)
    * Migrated reconciliation prompt from hardcoded string to YAML template
    * Added template versioning and changelog tracking
    * Backward compatible fallback to v1.0 hardcoded prompt
    * Template system integrated into `reconcile_soa_llm.py`
    * Prompts now have version numbers and change history

### Changed
* README.md updated with multi-model support, architecture section, and new test counts
* Installation instructions now include both OPENAI_API_KEY and GOOGLE_API_KEY
* Default model remains `gemini-2.5-pro` (from user preference memory)
* Model selection examples show GPT-4, GPT-5, and Gemini options

### Documentation
* New `MULTI_MODEL_IMPLEMENTATION.md` – Complete implementation guide for Phase 4
* Updated `README.md` – Architecture section, model selection guide, test information
* Updated `CHANGELOG.md` – This file

### Fixed
* GPT-5 parameter handling in `find_soa_pages.py` (text and vision adjudication)
  * Now correctly uses `max_completion_tokens` instead of `max_tokens`
  * Removes `temperature` parameter for GPT-5 (reasoning model)
  * Fixes Step 2 failures when using `--model gpt-5`
* **CRITICAL:** Text extraction Wrapper-Input handling in `send_pdf_to_llm.py` (Step 5)
  * **Part 1 (Validation):** Now detects USDM Wrapper-Input format correctly
    * Previously rejected valid JSON with `Wrapper-Input.study` structure
    * Fixed "lacks SoA data (study.versions)" false negative errors
  * **Part 2 (Normalization):** Normalizes Wrapper-Input to direct format before merge
    * Previously passed validation but merge function skipped the data
    * Result: Text extraction returned empty timeline despite LLM success
    * Now extracts full SoA data from text (epochs, encounters, activities)
  * Affects all models (GPT-4o, Gemini, GPT-5) in text extraction step
  * **Impact:** Restores text extraction to full working state

### Changed
* Commented out verbose `[DEBUG] Raw LLM output` in `send_pdf_to_llm.py`
  * Prevents entire USDM JSON from flooding console output
  * Model usage and token info still logged
  * Improves readability of pipeline logs
* Made `validate_soa_structure.py` non-fatal for linkage errors
  * Now logs warnings instead of exiting with error code
  * Allows reconciliation steps (7-11) to fix issues like missing encounters
  * Prevents pipeline halt on common LLM extraction gaps (e.g., ET/RT visits)
* Added required USDM fields to `reconcile_soa_llm.py` output (Step 9)
  * Now adds `rationale`, `studyIdentifiers`, and `titles` with defaults
  * Fixes Step 10 schema validation failures
  * Ensures output complies with USDM v4.0 Wrapper-Input requirements
* **Enhanced provenance tracking system** (`reconcile_soa_llm.py`) - Phases 1 & 2
  * **Phase 1 - Provenance Split:** Step 9 now creates separate `_provenance.json` file
    * Pure USDM in `9_reconciled_soa.json` (no embedded provenance)
    * Traceability in `9_reconciled_soa_provenance.json` (parallel file)
    * Consistent with Steps 7 & 8 pattern
    * Aligns with user preference for separate provenance files
  * **Phase 2 - "Both" Detection:** Enhanced source tracking
    * Entities found in text only: `"text"`
    * Entities found in vision only: `"vision"`
    * **NEW:** Entities found in both sources: `"both"` (high confidence indicator)
    * Improved traceability and quality assurance
  * Provenance summary logged: total entities and "both" count
  * Backward compatible: falls back to embedded provenance if separate files missing

### Testing
* Total test suite now: **94 tests (100% passing)**
  * 23 provider abstraction tests (added GPT-5 test)
  * 19 template system tests
  * 30 Phase 1-3 tests (schema, JSON parsing, normalization)
  * 22 original tests

---

## [Unreleased] – 2025-07-14
### Added
* **Gemini-2.5-Pro default model** – `main.py` now defaults to this model unless `--model` overrides.
* **Header-aware extraction**
  * `analyze_soa_structure.py` unchanged, but its JSON is now fed as machine-readable `headerHints` into both `send_pdf_to_llm.py` and `vision_extract_soa.py` prompts to prevent ID hallucination.
* **Header-driven enrichment** – `soa_postprocess_consolidated.py` enriches missing `activityGroupId` fields and group memberships using the header structure.
* **Header validation utility** – new script `soa_validate_header.py` automatically repairs any remaining header-derived issues after post-processing.
* **Pipeline wiring** – `main.py` now calls the validation utility automatically after Steps 7 and 8.
* **Documentation** – README revised with new 11-step workflow and header features.

### Changed
* Updated README default run command (`--model` optional, defaults to gemini-2.5-pro).
* Updated pipeline step table to include `soa_validate_header.py`.
* Key Features section reflects header-driven enrichment & validation.

### Removed
* Deprecated mention of `send_pdf_to_openai.py` in favour of `send_pdf_to_llm.py`.

---

## [Unreleased] – 2025-07-13
### Added
* **Provenance tagging**  
  * `vision_extract_soa.py` now writes `p2uProvenance.<entityType>.<id> = "vision"` for every `PlannedTimepoint`, `Activity`, `Encounter` it emits.  
  * `send_pdf_to_llm.py` tags the same entities with `"text"`.
* **Quality-control post-processing** (`soa_postprocess_consolidated.py`)
  * Detects orphaned `PlannedTimepoints` (no `ActivityTimepoint` links) and moves them to `p2uOrphans.plannedTimepoints`.
  * Auto-fills missing `activityIds` for every `ActivityGroup` and records multi-group conflicts in `p2uGroupConflicts`.
* **Streamlit viewer** (`soa_streamlit_viewer.py`)
  * Sidebar toggle **Show orphaned columns**; default hides orphans.
  * Conflict banner when `p2uGroupConflicts` present.
* **Internal utilities** for provenance and QC now live outside the `study` node so USDM-4.0 compliance remains intact.

### Changed
* All calls to `render_soa_table()` now pass header-structure JSON for enrichment.
* Viewer filtering pipeline updated to respect orphan/visibility settings.

### Planned (next sprint)
* Provenance colour coding and tooltip (blue=text, green=vision, purple=both).
* Chronology sanity check with `p2uTimelineOrderIssues` and viewer highlighting.
* Completeness index badge per run.
* One-click diff between any two runs.
* QC rules externalised to `qc_rules.yaml`.
* Async concurrent chunk uploads during LLM extraction for faster runtime.
* Header-structure caching – skip step 4 if images unchanged.

---
