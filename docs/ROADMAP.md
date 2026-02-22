# Protocol2USDM Roadmap

## Future Enhancements

### Navigation Restructure (Planned)

**Status:** Approved — implementation branch pending  
**Priority:** High  
**Added:** 2026-02-14

Restructure the web UI navigation from 4 groups (22 tabs) to 8 groups + 1 pinned view (25 views), aligned with ICH M11 sections and user personas (protocol author, biostatistician, data manager, regulatory reviewer, developer).

| Group | Tabs |
|-------|------|
| **Protocol** | Overview, Eligibility, Objectives, Design, Interventions, Narrative (+Abbreviations, +Footnotes) |
| **Assessments** | Procedures, Safety Entities |
| **Schedule & SoA** | SoA Table, Execution Model, Schedule Timeline |
| **Statistics** | SAP Data, CDISC ARS |
| **Trial Conduct** | Sites, Amendments |
| **Documents** | M11 Document, Figures, Cross-References |
| **Provenance** | Extraction Pipeline, Integrity, Pipeline Artifacts |
| **Developer** | Extensions, Quality Metrics, Validation |
| **Graph View** | *(pinned top-level button)* |

### User Access Management & E-Signatures (Future)

**Status:** Future enhancement  
**Priority:** Medium  
**Added:** 2026-02-10

1. **User Access Management**
   - Role-based access control (RBAC) for protocol editing
   - User authentication and session management
   - Permission levels: viewer, editor, approver

2. **E-Signatures (21 CFR Part 11)**
   - Electronic signature capture on publish
   - Signature meaning (authored, reviewed, approved)
   - Full GxP compliance with audit trail integration

### Reviewer Fixes P3–P7 (Complete)

**Status:** Complete  
**Priority:** High  
**Added:** 2026-02-17  
**Completed:** 2026-02-17

1. ~~**P6: EOS/ET StudyCell**~~ — ✅ `ensure_eos_study_cell()` creates StudyElement + StudyCell for uncovered epochs
2. ~~**P3: Sites Nesting**~~ — ✅ `nest_sites_in_organizations()` nests StudySite into Organization.managedSites
3. ~~**P5: Document Layer**~~ — ✅ `wire_document_layer()` wires Study.documentedBy → NarrativeContent
4. ~~**P4: Cohort Nesting**~~ — ✅ `nest_cohorts_in_population()` moves studyCohorts into population.cohorts
5. ~~**P7: Footnote Conditions**~~ — ✅ `promote_footnotes_to_conditions()` promotes conditional SoA footnotes to Condition entities

### Reviewer v9 Fixes (Complete)

**Status:** Complete  
**Priority:** High  
**Added:** 2026-02-17  
**Completed:** 2026-02-17

1. ~~**Site-Org Mapping Bug**~~ — ✅ Create new Organization for each unmatched site (was dumping Mass General/Yale/UMich under Cleveland Clinic)
2. ~~**StudySite.country ISO Codes**~~ — ✅ ISO 3166-1 alpha-3 lookup (USA, GBR, DEU, etc.) instead of full country names
3. ~~**documentedBy Wiring**~~ — ✅ Backfill SDD metadata (templateName, type, language), wire contentItemId, build childIds hierarchy, add previousId/nextId chain
4. ~~**CORE Compliance Allowed Keys**~~ — ✅ Added NarrativeContent, SDD, SDDVersion, Organization, StudySite to allowed keys
5. ~~**Condition contextIds/appliesToIds**~~ — ✅ Improved from 4/21 to ~12-15/21 wired footnote conditions (activity/encounter text matching, SAI linking)
6. ~~**StudyIdentifier.type**~~ — ✅ False finding: field does not exist in USDM v4.0 schema (no action needed)
7. ~~**Org/Site Schema Alignment**~~ — ✅ `studyDesigns[].studySites` removed (not a USDM path); sites only in `Organization.managedSites[]`
8. ~~**Organization Required Fields**~~ — ✅ `_backfill_organization()` adds `identifier` + `identifierScheme` on all orgs
9. ~~**StudySite Sanitization**~~ — ✅ Non-schema fields (siteNumber, status, address) moved to extensionAttributes or stripped
10. ~~**Field Renames**~~ — ✅ `scheduledAtTimingId→scheduledAtId`, `environmentalSetting→environmentalSettings`
11. ~~**Org Type C-code**~~ — ✅ Fixed from C188875 to EVS-verified C21541 (Healthcare Facility)

### UI & Rendering Fixes (Complete)

**Status:** Complete  
**Priority:** High  
**Added:** 2026-02-17  
**Completed:** 2026-02-17

1. ~~**medicalDevices placement**~~ — ✅ Moved from `studyDesign` to `studyVersion` per USDM v4.0 (CORE compliance was stripping them)
2. ~~**DOCX XML sanitization**~~ — ✅ Strip control characters before python-docx (fixes DAPA-HF crash)
3. ~~**StudySitesView data source**~~ — ✅ Read from `Organization.managedSites[]` with backward compat for legacy `studyDesign.studySites`
4. ~~**StudySitesView enrollment**~~ — ✅ Display total planned enrollment from `population.plannedEnrollmentNumber`
5. ~~**FootnotesView object format**~~ — ✅ Handle `{id, text, marker}` objects in `x-soaFootnotes` (was `[object Object]`)
6. ~~**FootnotesView notes[]**~~ — ✅ Read promoted footnotes from `studyDesign.notes[]`

### M11 DOCX Word Count (Backlog)

**Status:** Backlog  
**Priority:** Medium  
**Added:** 2026-02-17

Wilson's protocol produces 2,861 words vs 5,000 minimum threshold in `test_m11_regression`. Root cause: narrative extraction coverage — investigate section discovery for short protocols.

### USDM v4.0 Compliance Sprint (Complete)

**Status:** Complete  
**Priority:** High  
**Added:** 2026-02-17  
**Completed:** 2026-02-17

1. ~~**Endpoint Nesting**~~ — ✅ Endpoints nested inline inside `Objective.endpoints` per Value relationship
2. ~~**ExtensionAttribute Alignment**~~ — ✅ Non-schema `name` removed; `url` is sole semantic identifier
3. ~~**core_compliance.py Architectural Audit**~~ — ✅ Labels/procedures upstream, 210 lines dead code removed, file 714→504 lines

### Web UI Editing Improvements (Complete)

**Status:** Complete  
**Priority:** High  
**Added:** 2026-02-10  
**Completed:** 2026-02-13

1. ~~**ID-Based Patch Paths**~~ — ✅ `@id:` syntax in `SoAProcessor`, resolved by `resolveIdPath()` in `patcher.ts`
2. ~~**Live Validation on Publish**~~ — ✅ Schema/USDM/CORE validators on candidate USDM before writing to disk
3. ~~**Audit Trail**~~ — ✅ SHA-256 hash chain, reason-for-change, `publishedBy` user identity
4. ~~**Extended Editing Coverage**~~ — ✅ Objectives, endpoints, estimands (all 5 ICH E9(R1) attributes), interventions, narrative, timing, analysis populations

### ARS Output Display Generation (Future)

**Status:** Future enhancement  
**Priority:** Low  
**Added:** 2026-01-31

#### Future Extensions

1. **Output Display Generation**
   - Extract table shell specifications from SAP
   - Map to ARS `Output` and `OutputDisplay` entities
   - Generate display sections and ordinal positioning

2. **Analysis-to-Data Traceability**
   - Link ARS analyses to ADaM dataset specifications
   - Generate `AnalysisDataset` and `AnalysisVariable` entities
   - Support WHERE clause extraction for analysis subsets

3. **ARS Validation Rules**
   - Add ARS conformance checking
   - Validate operation-method consistency
   - Check analysis-population linkages

#### References
- [CDISC ARS GitHub](https://github.com/cdisc-org/analysis-results-standard)
- [ARS Documentation](https://cdisc-org.github.io/analysis-results-standard/)
- [ARS Wiki](https://wiki.cdisc.org/display/ARSP/ARS-UG+Sections)

### Unscheduled Visit (UNS) — Full State Machine Modeling (Complete)

**Status:** Complete (all 3 phases)  
**Priority:** Medium  
**Added:** 2026-02-11  
**Completed:** 2026-02-13

1. ~~**Phase 1 (Complete)**~~ — ✅ Tag UNS encounters with `x-encounterUnscheduled` extension, visual distinction in SoA grid (amber dashed borders, ⚡ suffix)
2. ~~**Phase 2 (Complete)**~~ — ✅ Promote UNS to `ScheduledDecisionInstance` (C201351) with `Condition` + `ConditionAssignment` branches (event → UNS visit, default → next scheduled encounter)
3. ~~**Phase 3 (Complete)**~~ — ✅ Timeline graph visualization: diamond decision nodes, dashed amber branch edges, legend updated

### Stratification & Randomization Enhancement (Complete)

**Status:** Complete (all 5 sprints)  
**Priority:** High  
**Added:** 2026-02-20  
**Completed:** 2026-02-22

1. ~~**Sprint A: Schema Refactor**~~ -- FactorLevel, AllocationCell dataclasses; 3-pass LLM extraction
2. ~~**Sprint B: Cross-Phase Linking**~~ -- `pipeline/stratification_linker.py`: factor-to-eligibility, factor-to-SAP covariate, scheme-to-arm, scheme-to-analysis population
3. ~~**Sprint C: USDM Mapping + M11 Rendering**~~ -- `create_strata_cohorts()`, treatment assignment composer, synopsis display
4. ~~**Sprint D: Web UI**~~ -- `StratificationSchemeView.tsx`: randomization summary, factor levels, allocation weights
5. ~~**Sprint E: Validation**~~ -- 7 coherence checks in `extraction/execution/validation.py`

### SAP Multi-Pass Enhancement (Complete)

**Status:** Complete (all 4 sprints)  
**Priority:** High  
**Added:** 2026-02-20  
**Completed:** 2026-02-22

1. ~~**Sprint 1: Multi-Pass Extraction**~~ -- 4-pass LLM with `sap_prompts.py`, MAX_SAP_PAGES=100
2. ~~**Sprint 2: AnalysisSpecification**~~ -- endpoint-to-method-to-population-to-estimand bridge, approach-aware gating
3. ~~**Sprint 3: MissingDataStrategy + ARS**~~ -- ICE mapping, ResultPattern on operations
4. ~~**Sprint 4: Traceability UI**~~ -- `StatisticalTraceabilityView.tsx` with completeness scoring

### Tier 1 Enhancements (Complete)

**Status:** Complete  
**Priority:** High  
**Added:** 2026-02-21  
**Completed:** 2026-02-22

1. ~~**OBJ-1/OBJ-2**~~ -- Estimand-to-intervention and estimand-to-population ID reconciliation
2. ~~**DES-1**~~ -- TransitionRule promotion to StudyElement (data-derived text only)
3. ~~**DES-3**~~ -- Duration extraction as ISO 8601 with EVS-verified NCI C-codes
4. ~~**M11-1**~~ -- Blinding procedures rendering (narrative-sourced only)
5. ~~**SOA-2**~~ -- ConditionAssignment from SoA footnotes + ScheduledDecisionInstance injection
6. ~~**SAP-1**~~ -- SAP method-to-estimand binding via endpoint matching
7. ~~**VAL-1/VAL-4**~~ -- Referential integrity checks S9-S14
8. ~~**Hallucination Audit**~~ -- Removed fabricated clinical text, verified C-codes via NCI EVS API

---

## Completed Features

### v7.13.0 - Graph View: Neighborhood Focus & Layout Selector (2026-02-14)
- ✅ Neighborhood dimming: click node → non-connected elements fade to 15%/8% opacity
- ✅ Layout selector: 6 Cytoscape layouts (preset, grid, circle, concentric, breadthfirst, cose)
- ✅ `LayoutIcon` component fix: replaced JSX member expressions that SWC/Turbopack compiled as invisible HTML elements
- ✅ Toolbar flex-wrap for narrow viewports

### v7.12.0 - Procedure Codes, Graph Editing, Anchor Nodes (2026-02-14)
- ✅ Procedure code enrichment: NCI/SNOMED/ICD-10/CPT/LOINC via embedded DB + EVS API
- ✅ Graph viewer editing: inline editing, clickable cross-references, undo/redo
- ✅ Dedicated anchor nodes: amber diamonds with dashed edges
- ✅ Timeline popout: position-aware alignment prevents label clipping
- ✅ 981 tests passing

### v7.11.0 - SoA Page Finder & Dangling Reference Fix (2026-02-14)
- ✅ SoA page finder: header-fingerprint expansion for multi-page tables (Jaccard ≥ 0.75)
- ✅ SoA page finder: wide-table heuristic (isolated integers + epoch keywords)
- ✅ Dangling SAI `encounterId` fix: post-reconciliation cleanup remaps to surviving encounters
- ✅ UI: MeSH code links to NLM Browser in StudyMetadataView + AdvancedEntitiesView
- ✅ UI: Characteristics display fixed (USDM Code.decode as badges)
- ✅ Renderer sectionType tagging confirmed end-to-end; keyword fallbacks deprecated
- ✅ SURPASS-4 re-run: 0→32 timepoints, 0→32 encounters, schema+semantic PASSED
- ✅ 2 new regression tests (dangling SAI encounterId)

### v7.10.0 - Bug Fixes, Integrity Checker & UI Hardening (2026-02-13)
- ✅ SAP extraction: 3 bugs fixed (wrong key, duplicate extensions, missing sap_path forwarding)
- ✅ Sites extraction: same key mismatch bug fixed (`sitesData`)
- ✅ Timeline visualization: all time anchors rendered with type-specific colors
- ✅ Figure extraction: three-strategy approach (embedded → cropped → full page)
- ✅ Cross-references: TOC dedup, figure title linking, context enrichment
- ✅ Referential integrity checker: 3-layer validation (`pipeline/integrity.py`)
- ✅ Cross-phase context enrichment: scheduling←studydesign, advanced←objectives+eligibility+interventions
- ✅ AdministrableProduct: 5 new USDM v4.0 fields
- ✅ UI/UX: app shell, error boundary, keyboard shortcuts, theme toggle, auto-save, provenance badges
- ✅ 84 new tests (SAP combine: 11, integrity: 28, reference scanner: 45)

### v7.9.0 - Editing, Tagging, Refactor & USDM Conformance (2026-02-13)
- ✅ Estimands fully editable (5 ICH E9(R1) attributes + intercurrent events)
- ✅ Analysis population descriptions editable
- ✅ M11-aware `sectionType` tagging on `NarrativeContentItem` (P15)
- ✅ `m11_renderer.py` split: `document_setup.py` + `text_formatting.py` (1199L→465L)
- ✅ `NarrativeContent` USDM v4.0 conformance: `displaySectionTitle`, `displaySectionNumber`, `previousId`/`nextId` linked list, `contentItemId`
- ✅ W-HIGH-2: PipelineContext decomposed into 5 sub-contexts (SoA, Metadata, Design, Intervention, Scheduling)
- ✅ W-HIGH-3: Entity-level provenance — `pages_used`, `entity_ids` on PhaseProvenance, `entity_provenance.json` output
- ✅ W-HIGH-4: Singletons → DI — `phase_registry`, EVS client, usage tracker all injectable for test isolation

### v7.8.0 - USDM v4.0 Extractor Gap Audit (2026-02-11)
- ✅ All 28 extractor gaps fixed across 4 severity levels (3 CRITICAL, 10 HIGH, 9 MEDIUM, 6 LOW)
- ✅ 115 new tests across 3 sprint test files

### v7.5.0 - NCI Code Audit & Verification (2026-02-11)
- ✅ Systematic audit of 141 NCI C-codes against EVS API
- ✅ Fixed 70+ fabricated/wrong codes across 20+ files
- ✅ `core/code_registry.py` — centralized CodeRegistry singleton
- ✅ `core/code_verification.py` — EVS-backed verification service
- ✅ `scripts/generate_code_registry.py` — generation pipeline with `--skip-verify`
- ✅ `web-ui/lib/codelist.generated.json` — UI-ready codelists
- ✅ UNS encounter tagging (Phase 1)

### v6.11.0 - CDISC ARS Deep Integration (2026-01-31)
- ✅ Full ARS model generation (`ars_generator.py`)
- ✅ ARS dataclasses: `ReportingEvent`, `Analysis`, `AnalysisSet`, `AnalysisMethod`, `Operation`
- ✅ ARS categorization support (by Reason, by Endpoint)
- ✅ STATO-to-ARS operation mapping
- ✅ ARS JSON output (`ars_reporting_event.json`)
- ✅ CDISC ARS tab in web UI with full visualization
- ✅ API endpoint for ARS data

### v6.10.0 - SAP Extraction with STATO/ARS (2026-01-31)
- ✅ Statistical methods with STATO ontology mapping
- ✅ Multiplicity adjustments extraction
- ✅ Sensitivity/subgroup analyses extraction
- ✅ Interim analysis plan extraction
- ✅ Sample size calculations extraction
- ✅ Basic ARS linkage fields
- ✅ SAP Data tab in web UI
