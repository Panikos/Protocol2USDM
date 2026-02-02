# Feature Branch: web-ui-modern-rewrite

## Summary

Major effort transforming Protocol2USDM from a basic extraction pipeline into a more comprehensive, clinical protocol digitization platform with modern web UI, execution model extraction, and aiming for **USDM 4.0 compliance**.

**Branch:** `feature/web-ui-modern-rewrite`
**Date Range:** December 30, 2025 - January 23, 2026
**Commits:** 127 commits
**Files Changed:** 277 files
**Lines Changed:** +67,896 / -23,290

---

## 1. COMPLETE WEB UI REWRITE (Next.js 14/15)

### New Web Application (`web-ui/`)
Replaced legacy Streamlit viewer with modern React/Next.js application featuring:

**Core Infrastructure (81 new files, +23,892 lines):**
- Next.js 14/15 with App Router and TypeScript
- TailwindCSS styling with dark mode support
- Zustand state management (protocolStore, overlayStore)
- AG Grid for high-performance data tables
- Cytoscape.js for interactive timeline visualization

**Protocol Viewer Components (42 React components):**
- `StudyMetadataView` - Study title, phase, indication, characteristics, abbreviations
- `EligibilityCriteriaView` - Inclusion/exclusion criteria display
- `ObjectivesEndpointsView` - Primary/secondary objectives and endpoints
- `StudyDesignView` - Arms, epochs, study cells, activity groups, transition rules
- `InterventionsView` - Treatments, administrations, substances, ingredients
- `ProceduresDevicesView` - Medical procedures and devices
- `AdvancedEntitiesView` - Biomedical concepts, analysis populations
- `AmendmentHistoryView` - Protocol amendment tracking
- `StudySitesView` - Geographic scope, site details with hover cards
- `FootnotesView` - SoA footnotes and protocol abbreviations
- `ExtensionsView` - USDM extension attributes display
- `NarrativeView` - Protocol narrative sections (collapsible)
- `ScheduleTimelineView` - Schedule timelines with instances and timings

**Schedule of Activities (SoA) Module:**
- `SoAView` / `SoAGrid` - Interactive activity matrix with AG Grid
- `SoAToolbar` - Filtering and display controls
- `FootnotePanel` - Footnote reference display
- `ProvenanceCellRenderer` - Cell-level provenance indicators

**Timeline Visualization:**
- `TimelineView` / `TimelineCanvas` - Cytoscape-based epoch/encounter visualization
- `ExecutionModelView` - Comprehensive execution model display (2,876 lines)
- `NodeDetailsPanel` - Detailed node inspection
- `TimelineToolbar` - Layout and filter controls

**Quality & Validation:**
- `QualityMetricsDashboard` - Extraction quality metrics
- `ValidationResultsView` - Schema and semantic validation results

**Provenance Tracking:**
- `ProvenanceView` / `ProvenanceExplorer` - Source tracking and exploration
- `ProvenanceStats` - Provenance statistics

**Data Adapters:**
- `toGraphModel.ts` - USDM to Cytoscape graph conversion
- `toSoATableModel.ts` - USDM to AG Grid table model
- `exportUtils.ts` - JSON/CSV export functionality

**API Routes:**
- `/api/protocols` - List available protocols
- `/api/protocols/[id]/usdm` - Fetch USDM JSON
- `/api/protocols/[id]/validation` - Validation results
- `/api/protocols/[id]/images` - SoA page images
- `/api/protocols/[id]/overlay/*` - Draft/publish overlay system

---

## 2. EXECUTION MODEL EXTRACTION FRAMEWORK

### New Extraction Module (`extraction/execution/`, 27 files, +17,112 lines)

Complete framework for extracting clinical trial execution semantics from protocols:

**Core Extractors:**
- `time_anchor_extractor.py` - Extract temporal anchors (VISIT/EVENT/CONCEPTUAL classification)
- `visit_window_extractor.py` - Visit window timing and tolerances
- `traversal_extractor.py` - Subject flow/traversal constraints
- `crossover_extractor.py` - Crossover design detection and period mapping
- `dosing_regimen_extractor.py` - Dosing schedules and regimens
- `repetition_extractor.py` - Cycle-based and conditional repetitions
- `footnote_condition_extractor.py` - Structured footnote condition parsing
- `binding_extractor.py` - Activity-to-instance bindings
- `sampling_density_extractor.py` - PK/PD sampling schedules
- `stratification_extractor.py` - Randomization stratification factors
- `derived_variable_extractor.py` - Computed/derived variables
- `endpoint_extractor.py` - Endpoint calculation algorithms
- `execution_type_classifier.py` - Study execution type classification
- `state_machine_generator.py` - Subject state machine generation

**Infrastructure:**
- `schema.py` - Comprehensive dataclass definitions (1,251 lines)
- `prompts.py` - LLM prompt templates for all extractors
- `pipeline_integration.py` - Main pipeline orchestration (1,588 lines)
- `execution_model_promoter.py` - Promote extensions to native USDM entities
- `reconciliation_layer.py` - Entity reconciliation and integrity
- `entity_resolver.py` - LLM-based semantic entity mapping
- `validation.py` - Execution model validation
- `soa_context.py` - SoA entity context for extractors
- `cache.py` - Extraction result caching
- `config.py` - Extractor configuration
- `export.py` - Export utilities

**Anchor Taxonomy (v6.7):**
- VISIT anchors → ScheduledActivityInstance with encounterId
- EVENT anchors → Instance linked to activity
- CONCEPTUAL anchors → Pure timing references (no instance)
- Intra-day ordering: InformedConsent(10) < Randomization(40) < Baseline(50) < FirstDose(60)

---

## 3. PIPELINE CONTEXT ARCHITECTURE

### Context-Aware Extraction (`extraction/pipeline_context.py`, 371 lines)

Implemented accumulative context passing across extraction phases:

```
SoA → PipelineContext (epochs, encounters, activities)
  ↓
Metadata → updates context (title, indication, phase)
  ↓
Eligibility → uses indication/phase
  ↓
Objectives → uses indication/phase
  ↓
Study Design → uses epochs/arms from SoA
  ↓
Interventions → uses arms, indication
  ↓
Execution Model → uses ALL accumulated context
```

**Extractors Enhanced with Context:**
- `eligibility` - study_indication, study_phase
- `objectives` - study_indication, study_phase
- `studydesign` - existing_epochs, existing_arms
- `interventions` - existing_arms, study_indication
- `traversal` - existing_epochs
- `crossover` - existing_epochs
- `footnote` - existing_activities

**Benefits:**
- No arbitrary labels requiring downstream resolution
- Consistent ID references across USDM output
- Better extraction accuracy with rich context

---

## 4. ENTITY RECONCILIATION FRAMEWORK

### Core Reconciliation (`core/reconciliation/`, 5 files, +1,669 lines)

Unified framework for reconciling extracted entities with existing USDM data:

- `base.py` - Base reconciler class with common functionality
- `epoch_reconciler.py` - Epoch name normalization and categorization
- `encounter_reconciler.py` - Encounter deduplication and merging
- `activity_reconciler.py` - Activity reconciliation with ID preservation

### Epoch Reconciliation (`core/epoch_reconciler.py`, 533 lines)
- Clean epoch names (strip footnote markers)
- Categorize epochs as main/sub based on traversal constraints
- Preserve extensionAttributes in normalize_epoch
- Filter epochs in UI based on traversal sequence

### LLM-Based Entity Resolution (`extraction/execution/entity_resolver.py`)
- Semantic mapping of abstract concepts to protocol entities
- Replaces fuzzy string matching with LLM understanding
- Handles variations like "Treatment Period" → "epoch_3"

---

## 5. USDM 4.0 COMPLIANCE

### Entity Placement Corrections
Moved entities to correct locations per CDISC dataStructure.yml:

- `indications` → studyDesign (was studyVersion)
- `timings`, `exits` → scheduleTimeline
- `conditions`, `abbreviations` → studyVersion
- `analysisPopulations` → studyDesign
- `procedures` → activity.definedProcedures
- `studySites` → studyVersion (where UI expects)
- `eligibilityCriterionItems` → linked via population.criterionIds

### Extension Attributes
Standardized extension attribute URLs:
- `x-executionModel` - Full execution model data
- `x-soaFootnotes` - Authoritative SoA footnotes
- `x-visitWindow` - Visit window on encounters
- `x-scheduledAtTimingId` - Timing linkage

---

## 6. CORE EXTRACTION MODULE ENHANCEMENTS (+827 lines across 22 files)

### Metadata Extraction (`extraction/metadata/`, +247 lines)

**New Identifier Type System:**
- Added `IdentifierType` enum with 9 standard types:
  - NCT (ClinicalTrials.gov), SPONSOR_PROTOCOL, EUDRACT, IND, IDE, ISRCTN, CTIS, WHO_UTN, OTHER
- Automatic mapping to USDM Code objects with proper codeSystem
- Human-readable decode generation for each identifier type

**Enhanced Study Characteristics:**
- Study phase extraction with NCI code mapping (C15600-C15603)
- Therapeutic area classification
- Study type detection (interventional/observational)
- Blinding/masking extraction
- Randomization method detection

**Organization Type Mapping:**
- Sponsor, CRO, IRB/Ethics Committee identification
- Organization role classification with NCI codes

### Interventions Extraction (`extraction/interventions/`, +132 lines)

**Dose Form Code Mapping:**
Added NCI code mappings for 13 dose forms:
```
TABLET → C42998    CAPSULE → C25158    SOLUTION → C42986
SUSPENSION → C42993 INJECTION → C42945  CREAM → C28944
OINTMENT → C42966   GEL → C42906        PATCH → C42968
POWDER → C42970     SPRAY → C42989      INHALER → C42940
```

**Enhanced USDM Output:**
- `administrableDoseForm` with proper Code structure
- `productDesignation` field population
- `standardCode` nested Code objects
- Route of administration with NCI codes

**Context-Aware Extraction:**
- Receives existing arms from SoA for accurate arm assignment
- Study indication context for treatment categorization

### Scheduling Extraction (`extraction/scheduling/`, +96 lines)

**ISO 8601 Duration Conversion:**
- Automatic conversion of numeric values to ISO 8601 format
- Support for days (P#D), weeks (P#W), hours (PT#H), minutes (PT#M)
- Negative duration handling for pre-dose windows

**Timing Type Code Mapping:**
```
BEFORE → C71149    AFTER → C71150     WITHIN → C71151
AT → C71148        BETWEEN → C71152
```

**Relative Reference Codes:**
```
STUDY_START → C71153      RANDOMIZATION → C71154
FIRST_DOSE → C71155       LAST_DOSE → C71156
PREVIOUS_VISIT → C71157   SCREENING → C71158
BASELINE → C71159         END_OF_TREATMENT → C71160
```

### Study Design Extraction (`extraction/studydesign/`, +141 lines)

**Titration Study Support:**
- New `DoseEpoch` dataclass for within-subject dose escalation
- `is_titration` flag for arm classification
- Sequential dose level tracking (dose, start_day, end_day)
- Extension attributes for titration metadata (`x-titration`, `x-doseEpochs`)

**Context-Aware Extraction:**
- Receives existing epochs from SoA for consistency
- Existing arms passed for accurate cell mapping
- Avoids creating duplicate epochs/arms

### Eligibility Extraction (`extraction/eligibility/`, +35 lines)

**Context Integration:**
- Study indication passed for relevant criteria extraction
- Study phase context for age-appropriate criteria
- Better handling of disease-specific criteria

**Enhanced Criterion Classification:**
- Improved inclusion/exclusion categorization
- Criterion item linking to populations

### Objectives Extraction (`extraction/objectives/`, +35 lines)

**Context-Aware Prompts:**
- Study indication context for objective relevance
- Phase-appropriate objective expectations
- Better primary/secondary classification

### SAP Extraction (`extraction/conditional/sap_extractor.py`, +110 lines)

**Flexible Section Parsing:**
- Handles varying SAP section structures across protocols
- Robust type checking for LLM response parsing
- Explicit instruction to not return placeholder text

**Analysis Population Extraction:**
- Complete population definitions with criteria
- Intent-to-treat, per-protocol, safety population identification
- Population linkage to eligibility criteria

### Sites Extraction (`extraction/conditional/sites_extractor.py`, +70 lines)

**Enhanced Site Data:**
- Geographic scope extraction (countries, regions)
- Site status tracking (active, recruiting, completed)
- Principal investigator information
- Site address and contact details

### Narrative Extraction (`extraction/narrative/`, +18 lines)

**Null Safety:**
- Ensure NarrativeContent name/text are never None
- Default value handling for missing sections

### Procedures Extraction (`extraction/procedures/`, +43 lines)

**Activity Linkage:**
- Procedures linked to activities via `definedProcedures`
- Procedure category classification
- Medical device association

### Advanced Entities (`extraction/advanced/`, +30 lines)

**Schema Enhancements:**
- Biomedical concept extraction improvements
- Analysis population schema refinement

---

## 7. GEMINI 3 FLASH INTEGRATION

### LLM Provider Updates (`llm_providers.py`)
- Added Gemini 3 Flash support via Vertex AI
- Automatic fallback to gemini-2.5-pro for SoA text extraction
- Response validation with retry logic (up to 2 retries)
- Safety controls disabled (BLOCK_NONE) for clinical content
- Environment isolation preventing model pollution

### Model Configuration
- Default model: `gemini-3-flash-preview`
- Fallback for complex SoA: `gemini-2.5-pro`
- Vertex AI routing with global endpoint

---

## 8. MAIN PIPELINE ENHANCEMENTS (`main_v2.py`, +1,173 lines)

### New Extraction Phases
- Execution model extraction (12+ sub-phases)
- Entity reconciliation post-processing
- Provenance tracking throughout pipeline

### New Command Line Options
- `--complete` - Run all extraction phases
- `--sap` - Include SAP document
- `--sites` - Include sites CSV
- `--model` - Specify LLM model

### Output Artifacts
- `10_scheduling_logic.json` - Scheduling constraints
- `11_execution_model.json` - Full execution model
- `11_sap_populations.json` - Analysis populations from SAP
- `protocol_usdm_provenance.json` - Cell-level provenance
- `conformance_report.json` - CDISC conformance results

---

## 9. VALIDATION ENHANCEMENTS

### USDM Validator (`validation/usdm_validator.py`, +178 lines)
- Schema validation against USDM 4.0
- Semantic validation for referential integrity
- Traversal constraint validation

### Conformance Checking
- Integration with CDISC rules engine
- Classified integrity issues (blocking/warning/info)
- JSONPath pointers for issue location

---

## 10. DOCUMENTATION

### New Documentation Files
- `docs/ARCHITECTURE.md` - Complete system architecture (+747 lines)
- `docs/EXECUTION_MODEL_ARCHITECTURE.md` - Execution model design (+212 lines)
- `docs/EXECUTION_MODEL_FIXES.md` - Bug fix documentation (+192 lines)
- `docs/ALEXION_FEEDBACK_ANALYSIS.md` - Alexion trial feedback (+134 lines)
- `docs/TIMELINE_REVIEW_GUIDE.md` - Timeline review procedures (+504 lines)
- `web-ui/docs/IMPLEMENTATION_PLAN.md` - UI implementation plan (+215 lines)
- `extraction/execution/README.md` - Execution module documentation (+762 lines)

### Updated Documentation
- `README.md` - Updated with new features
- `USER_GUIDE.md` - Usage instructions
- `QUICK_REFERENCE.md` - Quick reference guide
- `CHANGELOG.md` - Version history

---

## 11. TESTING

### New Test Files
- `tests/test_execution_model.py` - Execution model tests (+1,612 lines)
- `testing/benchmark.py` - Performance benchmarking

### Debug Utilities (Root Directory)
- `check_*.py` - Various validation scripts
- `debug_*.py` - Debugging utilities
- `verify_*.py` - Verification scripts
- `trace_encounter_ids.py` - ID tracing

---

## 12. BUG FIXES (76 fixes)

### Critical Fixes
- Visit Windows epoch resolution uses day-based USDM matching
- Handle Day 0 gap - interpolate epoch from nearest neighbors
- Handle late-study visits (Day 162, 365) - assign to EOS epoch
- CDISC engine epochIds keys with spaces (sanitize to underscores)
- Filter encounters without epochId to prevent Unknown Epoch
- Don't create Early Termination epoch if not in SoA

### Data Integrity Fixes
- Preserve original IDs in entity reconciliation
- Update activityGroups.childIds after activity reconciliation
- Support childIds for activity group linking in SoA table
- Filter out activities with empty names in post-reconcile
- Handle ProceduresDevicesData dataclass in activity reconciliation

### UI Fixes
- React child object rendering errors
- ActivityGroups using childIds instead of activityIds
- ScheduleTimelineView instance/timing field names
- Populate encounter/activity name mappings in provenance

### LLM/Extraction Fixes
- Handle dose ranges in LLM dosing extraction
- Deduplicate CollectionDay anchors
- Strengthen dosing regimen name filtering
- SAP prompt flexibility for varying structures
- Titration pattern matching improvements

---

## 13. FILE STATISTICS

### New Files: 164
- `extraction/execution/` - 27 Python modules
- `web-ui/components/` - 42 React components
- `web-ui/lib/` - 8 utility modules
- `web-ui/app/` - 12 pages and API routes
- `core/reconciliation/` - 5 reconciliation modules
- `docs/` - 5 documentation files

### Modified Files: 42
- Core extraction modules updated with context support
- Schema files enhanced with new types
- Main pipeline significantly expanded
- Validation modules enhanced

### Deleted Files: 48
- Legacy output directories cleaned up

---

## Suggested Commit Message (Short Form)

```
feat: Complete web UI rewrite, execution model extraction, and USDM 4.0 compliance

- Modern Next.js 14/15 web application with 42 React components
- Execution model extraction framework (27 modules, 17K+ lines)
- Core extraction modules enhanced with NCI code mappings (+827 lines)
- Pipeline context architecture for context-aware extraction
- Entity reconciliation framework with LLM-based resolution
- USDM 4.0 entity placement compliance
- Gemini 3 Flash integration with fallback logic
- 76 bug fixes for data integrity and UI rendering

277 files changed, +67,896 / -23,290 lines
```
