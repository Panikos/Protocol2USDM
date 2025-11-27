# Protocol2USDM – Change Log

All notable changes documented here. Dates in ISO-8601.

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
