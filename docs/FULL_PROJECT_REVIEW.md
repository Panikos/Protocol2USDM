# Protocol2USDM — Full Project Review

**Date**: February 2026 (updated 2026-02-10 with external reviewer findings)
**Scope**: Complete codebase review covering all modules except web-ui (covered separately in `docs/WEB_UI_REVIEW.md`)
**Methodology**: Deep-read of every module's source code, architecture analysis, cross-module dependency tracing
**External review**: Two independent reviewers validated findings. New items marked with ⚠️ EXT

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Module-by-Module Analysis](#2-module-by-module-analysis)
   - 2.1 [core/](#21-core)
   - 2.2 [extraction/](#22-extraction)
   - 2.3 [pipeline/](#23-pipeline)
   - 2.4 [rendering/](#24-rendering)
   - 2.5 [validation/](#25-validation)
   - 2.6 [main_v3.py — Entry Point](#26-main_v3py--entry-point)
   - 2.7 [llm_providers.py — LLM Abstraction](#27-llm_providerspy--llm-abstraction)
   - 2.8 [llm_config.yaml — Task Configuration](#28-llm_configyaml--task-configuration)
   - 2.9 [enrichment/](#29-enrichment)
   - 2.10 [testing/ and tests/](#210-testing-and-tests)
   - 2.11 [scripts/ and tools/](#211-scripts-and-tools)
3. [Architectural Strengths](#3-architectural-strengths)
4. [Architectural Weaknesses](#4-architectural-weaknesses)
5. [Cross-Cutting Concerns](#5-cross-cutting-concerns)
6. [Enhancement Roadmap](#6-enhancement-roadmap)
7. [Open Critique — How I Would Approach This Differently](#7-open-critique)

---

## 1. Executive Summary

Protocol2USDM is a sophisticated AI-powered pipeline that transforms clinical protocol PDFs into USDM v4.0-compliant JSON, ICH M11-formatted DOCX documents, and a web-based protocol viewer/editor. The codebase spans ~35,000 lines of Python across 100+ files plus a Next.js web UI (~15,000 lines TypeScript).

**Overall assessment**: The project demonstrates **exceptional domain expertise** and a **well-thought-out architecture** for a deeply complex problem space (clinical protocol digitization). The schema-driven approach, registry-based pipeline, and dual-path rendering are strong design choices. However, the codebase shows signs of **organic growth** — the orchestrator's `combine_to_full_usdm()` function at 1,150+ lines is the primary bottleneck, and several cross-cutting concerns (error handling, logging consistency, configuration management) would benefit from systematization.

**Key metrics from review**:
| Metric | Value |
|--------|-------|
| Python modules reviewed | 100+ files |
| Extraction phases | 13 registered + 2 conditional |
| Execution model sub-extractors | 17 specialized extractors |
| LLM providers supported | 3 (OpenAI, Gemini, Claude) |
| USDM entity types modeled | 86 (from dataStructure.yml) |
| M11 sections covered | 14 (all) |
| Reconciliation systems | 3 (epoch, encounter, activity) |
| Test files | 18 unit + 5 integration/benchmark |
| Lines in orchestrator.py | 1,692 |

---

## 2. Module-by-Module Analysis

### 2.1 core/

**Files reviewed**: `constants.py`, `usdm_schema_loader.py`, `usdm_types.py`, `terminology_codes.py`, `provenance.py`, `evs_client.py`, `m11_mapping_config.py`, `schema_prompt_generator.py`, `epoch_reconciler.py`, `validation.py`, `reconciliation/` (4 files)

#### 2.1.1 Schema Loading (`usdm_schema_loader.py`)

**Architecture**: Dynamically parses the official CDISC `dataStructure.yml` and generates Python dataclasses at runtime. Schema is pinned to `SCHEMA_TAG = "v4.0"` with SHA256 hash verification and download timestamp via `version.json`.

**Strengths**:
- Single source of truth — both Python backend and TypeScript frontend types derive from the same YAML
- Lazy loading with singleton pattern (`get_schema_loader()`)
- Entity definitions expose required fields, NCI codes, cardinality, and relationship types
- Cache invalidation based on file hash

**Weaknesses**:
- **W-C1**: Runtime dataclass generation via `make_dataclass()` loses IDE autocomplete and type checking. The generated `usdm_types_generated.py` file (imported by `usdm_types.py`) mitigates this somewhat, but the generation step is manual
- **W-C2**: `_fetch_and_cache()` does a full HTTP download with no conditional GET (If-Modified-Since). On slow networks, this blocks startup
- **W-C3**: No schema migration path — if USDM v4.1 changes entity shapes, there's no tooling to detect breaking changes vs. additive ones

#### 2.1.2 Type System (`usdm_types.py`)

**Architecture**: Dual-layer type system — official USDM entities imported from `usdm_types_generated.py` plus 5 internal extraction types (`PlannedTimepoint`, `ActivityTimepoint`, `ActivityGroup`, `HeaderStructure`, `Timeline`).

**Strengths**:
- Clear separation: official USDM vs. internal extraction types
- Internal types have `to_<usdm_entity>()` conversion methods (e.g., `ActivityTimepoint.to_scheduled_instance()`)
- Backward compatibility via `@property` aliases (`PlannedTimepoint.name` → `visit`)
- `Timeline.to_study_design()` handles all 3 fallback strategies for group→activity linking

**Weaknesses**:
- **W-C4**: `Timeline.to_study_design()` contains a `re` import inside the method body (line 445) — should be at module top
- **W-C5**: The `EntityType` enum has duplicate values (`PLANNED_TIMEPOINT = "Timing"`, `EPOCH = "StudyEpoch"`) which is technically valid but confusing for reverse lookups
- **W-C6**: `ActivityTimepoint.from_dict()` and `to_dict()` duplicate logic for ID resolution across 3 fields (`encounterId`, `timepoint_id`, `plannedTimepointId`). This triple-fallback pattern indicates unresolved legacy data formats

#### 2.1.3 Terminology (`terminology_codes.py`, `evs_client.py`)

**Architecture**: `terminology_codes.py` is the single source of truth for all NCI/CDISC controlled terminology codes. `evs_client.py` provides live lookup against NCI EVS REST APIs with a 30-day file-based cache.

**Strengths**:
- All codes centralized with `get_code_object()` helper producing USDM-compliant Code dicts
- `find_code_by_text()` enables text-to-code inference across all codelists
- EVS client has graceful degradation — works offline from cache
- `USDM_CODES` dict provides offline fallback for 30+ commonly used codes
- Singleton pattern with module-level convenience functions

**Weaknesses**:
- **W-C7**: `evs_client.py` duplicates some codes that also exist in `terminology_codes.py` (e.g., objective levels, arm types). The `USDM_CODES` dict in evs_client and the dictionaries in terminology_codes overlap
- **W-C8**: Cache file is a single JSON blob — with many codes, this means full file rewrite on every new code fetch. A per-code or chunked cache would scale better
- **W-C9**: No cache warming at startup — codes are fetched on first access, which can cause latency spikes in extraction phases

#### 2.1.4 Provenance (`provenance.py`)

**Architecture**: `ProvenanceTracker` stores entity-level and cell-level provenance with source tags (TEXT, VISION, BOTH, LLM_INFERRED, HEADER, DEFAULT, NEEDS_REVIEW). Provenance is stored as a separate JSON file, not embedded in the USDM output.

**Strengths**:
- Clean separation from USDM output — provenance is stored externally
- Granular cell-level tracking for SoA matrix (`tag_cell()`)
- Source merging logic (`TEXT + VISION → BOTH`)
- Statistics method for extraction quality reporting

**Weaknesses**:
- **W-C10**: Only tracks SoA-related entities (activities, timepoints, encounters). Expansion phase entities (objectives, eligibility criteria, interventions) have no provenance tracking
- **W-C11**: No provenance chain — when reconciliation replaces an activity, the original provenance data may become orphaned if IDs change

#### 2.1.5 Reconciliation (`reconciliation/`, `epoch_reconciler.py`)

**Architecture**: Three specialized reconcilers (`EpochReconciler`, `EncounterReconciler`, `ActivityReconciler`) inherit from `BaseReconciler`. Each merges entity data from multiple extraction sources using priority-based contribution scoring.

**Strengths**:
- Priority system: SoA (10) → Scheduling (15) → Procedures (20) → Execution (25) → Footnotes/SAP (30)
- Fuzzy name matching via `SequenceMatcher` with configurable thresholds
- Footnote reference extraction and cleaning
- CDISC epoch type inference from name patterns
- Traversal sequence tracking for main epochs
- Extension attributes for raw name, sources, and footnotes (traceability)

**Weaknesses**:
- **W-C12**: `epoch_reconciler.py` (643 lines) is in `core/` while `activity_reconciler.py` and `encounter_reconciler.py` are in `core/reconciliation/`. This inconsistency suggests organic growth
- **W-C13**: Fuzzy matching threshold (0.55) is hardcoded. Different entity types may need different thresholds (e.g., activity names are short, epoch names are longer)
- **W-C14**: No reconciliation audit log — when entities are merged, the decision rationale (which source won, what was discarded) isn't persisted for human review

#### 2.1.6 M11 Mapping Config (`m11_mapping_config.py`)

**Architecture**: YAML-driven single source of truth for M11↔USDM mapping. Consumed by mapper, renderer, conformance validator, and orchestrator (promotion rules). Typed dataclasses (`M11SectionConfig`, `M11Subheading`, `ExtractorGap`, etc.) provide a clean API.

**Strengths**:
- Eliminates hardcoded M11 section lists across multiple consumers
- Includes extractor gap tracking, promotion rules, and regulatory references per section
- Backward-compatible accessors (`get_m11_template()`, `get_m11_subheadings()`)
- `lru_cache(1)` singleton for zero-cost repeated access

**Weaknesses**:
- **W-C15**: The YAML file (`m11_usdm_mapping.yaml`) is not validated at load time — a malformed YAML could silently produce incomplete config. Schema validation (e.g., JSON Schema or Pydantic for the YAML) would catch this early

#### 2.1.7 Schema Prompt Generator (`schema_prompt_generator.py`)

**Architecture**: Generates LLM prompts directly from the official USDM schema, ensuring prompt content always matches the schema.

**Strengths**:
- Entity groupings for different extraction tasks (soa_core, study_design, eligibility, etc.)
- Auto-generates entity instructions with NCI codes, required fields, and definitions
- Two prompt tiers: SoA-focused and full-schema

**Weaknesses**:
- **W-C16**: Only generates SoA and full prompts. Individual phase extractors (metadata, eligibility, etc.) don't use this generator — they have handcrafted prompts in their own `prompts.py`. This creates a dual-source-of-truth risk for entity definitions in prompts

---

### 2.2 extraction/

**Files reviewed**: 48 Python files across 9 subdirectories + 6 root-level files

#### 2.2.1 Phase Structure

Each extraction phase follows a consistent anatomy:
```
extraction/<phase>/
├── __init__.py      # Exports
├── schema.py        # Pydantic models for LLM response
├── extractor.py     # LLM call + response parsing
└── prompts.py       # System/user prompts
```

**Phases**: metadata, narrative, objectives, studydesign, eligibility, interventions, procedures, advanced, amendments, document_structure + conditional (SAP, sites) + execution (17 sub-extractors)

**Strengths**:
- Consistent phase anatomy across all 13 phases
- Pydantic schemas validate LLM output structure before pipeline processing
- Each phase is self-contained with its own prompts, schema, and extractor
- Pipeline context propagation allows downstream phases to reference upstream results

**Weaknesses**:
- **W-E1**: Prompt quality varies significantly across phases. Some prompts (SoA, execution) are extremely detailed with schema references and hard constraints. Others (advanced, amendments) are simpler and may produce less consistent output
- **W-E2**: No prompt versioning — when a prompt is updated, there's no way to track which prompt version produced a given extraction result. This hampers reproducibility
- **W-E3**: LLM response parsing has phase-specific fallback chains that are hard to reason about (e.g., eligibility extractor tries 4 different response formats before giving up)

#### 2.2.2 Execution Model (`extraction/execution/`)

This is the most complex extraction subsystem — 17 specialized sub-extractors feeding into a 10-step `ExecutionModelPromoter`.

**Sub-extractors**: `time_anchor`, `repetition`, `dosing_regimen`, `visit_window`, `footnote_condition`, `traversal`, `binding`, `crossover`, `derived_variable`, `endpoint`, `state_machine`, `stratification`, `sampling_density`, `entity_resolver`, `execution_type_classifier`, `reconciliation_layer`, `soa_context`

**Strengths**:
- Each promotion step is fault-isolated — failure in step 3 doesn't block steps 4-10
- Extension attributes provide debug transparency without polluting core USDM
- Crossover, titration, and adaptive design support via specialized extractors
- Processing warnings system tracks extraction quality issues
- Pipeline integration layer (`pipeline_integration.py`) cleanly wires sub-extractors

**Weaknesses**:
- **W-E4**: 17 sub-extractors × 1 LLM call each = potentially 17 LLM calls for one phase. With a ~10s latency per call, this phase alone can take 3+ minutes. No batching or parallelism within the phase
- **W-E5**: The `ExecutionModelPromoter` (10 steps) runs strictly sequentially even though some steps are independent (e.g., dosing normalization and visit window enrichment have no data dependency)
- **W-E6**: `soa_context.py` and `cache.py` implement a caching layer, but the cache key is the full PDF path — if the same PDF is processed with different models or prompts, the cache serves stale results

#### 2.2.3 Conditional Sources (`extraction/conditional/`)

**SAP Extractor**: Parses Statistical Analysis Plan PDFs into analysis populations, sample size calculations, derived variables, statistical methods, and multiplicity adjustments. Generates CDISC ARS (Analysis Results Standard) output.

**Sites Extractor**: Parses CSV/Excel site lists into USDM StudySite entities.

**ARS Generator**: Maps SAP statistical methods to STATO ontology terms and generates ARS `ReportingEvent` with `Analysis`, `AnalysisSet`, `AnalysisMethod`, and `Operation` entities.

**Strengths**:
- ARS output follows the CDISC Analysis Results Standard model
- STATO ontology mapping for 10+ statistical methods
- SAP integration enriches the main USDM via extension→promotion mechanism

**Weaknesses**:
- **W-E7**: SAP and sites are not registered pipeline phases — they're handled as special cases in `main_v3.py::_run_conditional_sources()`. This breaks the registry pattern and means they can't benefit from parallel execution or dependency management
- **W-E8**: ARS generator has hardcoded method→operation mappings. New statistical methods require code changes rather than configuration

#### 2.2.4 Root-Level Extraction Utilities

- **`pipeline_context.py`**: Accumulates results across phases. Thread-safe with `snapshot()`/`merge_from()` for parallel execution.
- **`confidence.py`**: Confidence scoring for extraction results.
- **`header_analyzer.py`**: Vision-based SoA table header analysis.
- **`extraction_enums.py`**: Shared enumerations.

**Strengths**:
- `PipelineContext.merge_from()` uses a phase→field mapping to prevent cross-contamination during parallel execution
- Lookup maps (`_epoch_by_id`, `_activity_by_name`) are rebuilt after every update

**Weaknesses**:
- **W-E9**: `PipelineContext` has 28 data fields + 7 lookup maps. It's becoming a god object. As more phases are added, this will only grow. Consider decomposing into domain-specific sub-contexts

---

### 2.3 pipeline/

**Files reviewed**: `orchestrator.py` (1,692 lines), `base_phase.py` (251 lines), `phase_registry.py` (78 lines), `phases/` (13 files)

#### 2.3.1 Registry Pattern

**Architecture**: Global `PhaseRegistry` singleton. Each phase registers via `BasePhase` subclass with `PhaseConfig` (name, display_name, phase_number, output_filename). Orchestrator iterates registry in phase_number order.

**Strengths**:
- Clean separation: registration is declarative, execution is generic
- Phase ordering via `phase_number` is explicit and stable
- `PhaseConfig.optional` flag handles graceful degradation when dependencies are missing
- Registry-driven combine — all phases get a chance to combine even when not re-run (fallback to `previous_extractions`)

**Weaknesses**:
- **W-P1**: Phase registration happens via `from pipeline.phases import *` in `main_v3.py` — this side-effect-based registration is fragile and implicit. If a phase file has an import error, all subsequent phases silently fail to register
- **W-P2**: `phase_registry` is a mutable global singleton. In testing, there's no way to reset or isolate the registry without monkey-patching

#### 2.3.2 Parallel Execution

**Architecture**: `run_phases_parallel()` builds execution waves from dependency graph. Each wave's phases get isolated `PipelineContext.snapshot()` copies. Results merge back via `merge_from()`.

**Strengths**:
- Dependency enforcement with transitive auto-enablement (`_enforce_dependencies()`)
- Cycle detection with graceful fallback (runs remaining if deadlocked)
- Thread-safe context isolation per phase
- Single-phase waves run directly (no thread overhead)

**Weaknesses**:
- **W-P3**: `ThreadPoolExecutor` is used, but Python's GIL means CPU-bound work doesn't benefit. Since phases are IO-bound (LLM API calls), this is acceptable, but `asyncio` with `aiohttp` would be more efficient and avoid the deep-copy overhead of `snapshot()`
- **W-P4**: Failed phases in a wave don't cancel other phases in the same wave. If metadata fails, eligibility and objectives still run (with empty context), wasting API tokens

#### 2.3.3 Combine Logic (`combine_to_full_usdm`)

**Architecture**: 1,150+ line function that merges SoA data, expansion results, conditional sources (SAP, sites), runs reconciliation, resolves cross-references, promotes extensions, links procedures to activities, and saves the final USDM JSON.

This is the **single most critical function** in the entire codebase.

**Strengths**:
- Comprehensive post-processing pipeline: defaults → SoA merge → type derivation → indications → sites → SAP → reconciliation → cross-references → activity sources → procedure linking → footnotes → extension promotion
- Graceful defaults for all required USDM fields (arms, epochs, cells, model, titles, identifiers, population)
- Estimand→population reconciliation with 3-pass matching (exact, alias, fuzzy)
- Extension→USDM promotion with idempotent rules

**Weaknesses**:
- **W-P5**: **God function** — `combine_to_full_usdm()` at 1,150+ lines violates single-responsibility. It handles SAP integration, ARS generation, reconciliation, cross-reference resolution, and 8 other concerns. Each concern should be a separate, testable function or class
- **W-P6**: SAP extension storage uses `json.dumps()` inside `valueString` — this double-serialization means SAP data is JSON-inside-JSON, making it hard to query or validate
- **W-P7**: The function modifies `study_version` and `study_design` dicts in place while also reading from them — this interleaved read/write makes the execution order extremely sensitive. Reordering any block could introduce subtle bugs
- **W-P8**: `_temp_study_type` and `_temp_indications` use dict key conventions (`_temp_*`) as inter-phase communication channels. This is a code smell — a proper result object would be safer
- **W-P9**: Error handling in combine is inconsistent — some blocks use try/except with `logger.warning()`, others let exceptions propagate. A failure in reconciliation silently skips all subsequent reconciliation but doesn't affect other post-processing steps

---

### 2.4 rendering/

**Files reviewed**: `m11_renderer.py` (2,227 lines)

#### 2.4.1 M11 DOCX Renderer

**Architecture**: Dual-path rendering — **Extractors** pull narrative text from the PDF extraction, while **Composers** generate prose from USDM entities. The renderer produces a professional DOCX with title page, TOC placeholder, all 14 M11 sections, and entity-composed content.

**Strengths**:
- ICH M11 Template compliance: Times New Roman, correct heading hierarchy (L1=14pt ALL CAPS, L2=14pt Bold, L3-L5=12pt Bold), proper margins
- 9 entity composers wired to M11 sections (§1 synopsis, §3 objectives, §3 estimands table, §4 design, §5 eligibility, §6 interventions, §7 discontinuation, §9 safety, §10 statistics)
- Composers work independently of extraction — enables future USDM-first authoring
- Synopsis table with USDM field mapping
- `M11RenderResult` tracks sections rendered, sections with content, and total words

**Weaknesses**:
- **W-R1**: Single 2,227-line file. The renderer, composers, style setup, and section mapper are all in one file. Extracting composers into separate modules would improve maintainability
- **W-R2**: ✅ FIXED — SoA table now renders in DOCX with group separators, header shading, column widths, empty-activity filtering, and repeat-header-on-page-break
- **W-R3**: No configurable template — the document styling is hardcoded. Sponsors may have their own protocol templates with different headers, footers, and branding
- **W-R4**: Heading level determination uses dot-counting in section numbers, which fails for non-standard numbering (e.g., appendix sub-sections)

---

### 2.5 validation/

**Files reviewed**: `usdm_validator.py` (545 lines), `cdisc_conformance.py` (521 lines), `__init__.py`

#### 2.5.1 USDM Validator

**Architecture**: Uses the official CDISC `usdm` Python package (Pydantic models) for authoritative validation. Falls back to `valid=False` with ERROR severity when the package is not installed.

**Strengths**:
- **Authoritative validation** — uses the official CDISC package, not custom schema parsing
- Smart union branch filtering — Pydantic reports errors for all union branches (InterventionalStudyDesign vs ObservationalStudyDesign), but the validator filters to only the relevant branch
- Grouped error reporting by error type with truncation for readability
- `ValidationResult` dataclass with severity levels (ERROR, WARNING, INFO)

**Weaknesses**:
- **W-V1**: The `usdm` package is an optional dependency. If not installed, validation silently produces `valid=False` without the user knowing the real cause. The installation instruction is only in a log warning
- **W-V2**: No incremental validation — the entire USDM document is validated at once. For large documents, this can be slow and produces hundreds of errors. Per-entity validation would allow fixing in batches

#### 2.5.2 CDISC CORE Conformance

**Architecture**: Runs the local CDISC CORE engine executable against the USDM JSON. Falls back to CDISC API if local engine is not available. Requires a CDISC Library API key for cache initialization.

**Strengths**:
- Local-first execution (no API dependency after initial cache)
- Standardized result dict with consistent keys across all paths
- Cache management with auto-download on first run

**Weaknesses**:
- **W-V3**: The CORE engine path is hardcoded to `tools/core/core/core.exe` — Windows-only. On Linux/macOS, this will silently fall through to the API path
- **W-V4**: CORE engine output parsing is brittle — it assumes specific JSON structure from the engine output

#### 2.5.3 Schema Auto-Fix (`core/validation.py`)

**Architecture**: `validate_and_fix_schema()` runs validation, then applies automated fixes (ID→UUID conversion, missing required field injection). Can optionally use LLM for complex fixes.

**Strengths**:
- Recursive ID→UUID conversion with reference integrity (`convert_ids_to_uuids()`)
- Handles JSON-encoded extension attributes (`valueString` containing JSON)
- Returns ID mapping for provenance synchronization
- `link_timing_ids_to_instances()` fixes dangling timing references

**Weaknesses**:
- **W-V5**: LLM-based schema fixing is opaque — when the LLM "fixes" a schema issue, there's no audit trail of what it changed or why. In a GxP context, this is problematic
- **W-V6**: `is_simple_id()` uses heuristics (contains `_` or `-`, length < 50) which could false-positive on legitimate string values

---

### 2.6 main_v3.py — Entry Point

**Architecture**: CLI entry point with 30+ command-line arguments covering SoA extraction, expansion phases, conditional sources (SAP, sites), validation, enrichment, and M11 rendering. Defaults to `--complete` mode if no specific phases are requested.

**Strengths**:
- `--complete` flag sets all phases + validation + conformance in one command
- `_write_run_manifest()` creates reproducibility metadata (input hash, model, phases, schema version)
- Hybrid footnote extraction merges vision and PDF text footnotes
- Graceful degradation — individual phase failures don't crash the pipeline
- Token usage summary with per-phase cost breakdown

**Weaknesses**:
- **W-M1**: 768 lines for an entry point is too much. Business logic (footnote merging, conditional source handling, schema validation orchestration) should be in dedicated modules
- **W-M2**: The function `_merge_header_footnotes()` reads the header JSON, modifies it, writes it back, and also modifies `soa_data` — this side-effect-heavy function is hard to test in isolation
- **W-M3**: Version string "7.2.0" is hardcoded in 3 places (`main_v3.py`, `orchestrator.py` generator metadata, and `_write_run_manifest()`). Should be a single constant
- **W-M4**: Exit code is binary (0 or 1). More granular exit codes (e.g., 2 for partial success, 3 for validation failure) would help CI/CD integration

---

### 2.7 llm_providers.py — LLM Abstraction

**Architecture**: Abstract `LLMProvider` base class with 3 concrete implementations (`OpenAIProvider`, `GeminiProvider`, `ClaudeProvider`). Factory pattern via `LLMProviderFactory.create()`. Global `TokenUsageTracker` with thread-safe per-phase tracking.

**Strengths**:
- **Unified interface** — `generate()` and `generate_with_image()` work identically across providers
- Thread-safe token tracking with `threading.Lock` and thread-local `current_phase`
- Exponential backoff retry for rate limiting (429 errors)
- Model-specific quirks handled cleanly (o-series no temperature, Claude no temp+top_p)
- Cost estimation with up-to-date pricing for 10+ models
- Vertex AI routing for Gemini 3 models with global endpoint support
- Safety controls disabled for clinical content (Gemini)

**Weaknesses**:
- **W-L1**: 1,274 lines in a single file. Three provider classes + factory + tracker + retry logic. Should be split into `providers/openai.py`, `providers/gemini.py`, `providers/claude.py`, etc.
- **W-L2**: `OpenAIProvider.generate()` uses the Responses API but `generate_with_image()` uses the Chat Completions API — this inconsistency means the two methods have different error handling and response parsing
- **W-L3**: No streaming support. For long extraction tasks, streaming would provide better UX (progress visibility) and allow early termination on malformed output
- **W-L4**: `usage_tracker` is a module-level global. In testing, there's no clean way to inject a mock tracker without monkey-patching

---

### 2.8 llm_config.yaml — Task Configuration

**Architecture**: YAML-based LLM parameter configuration with 4 task categories (deterministic, semantic, structured_gen, narrative) and a 4-level override hierarchy (base → provider → model → environment).

**Strengths**:
- **Excellent design** — task-based abstraction decouples extraction phases from LLM model specifics
- 30 extractors mapped to 4 task types with clear rationale
- Provider-specific overrides handle API differences (OpenAI no top_k, Claude no temp+top_p)
- Model-specific overrides for edge cases (o-series no temperature, Sonnet max tokens)
- Environment variable overrides for runtime tuning
- Optimized values backed by parameter optimization tests (Jan 2026)
- Comprehensive documentation inline

**Weaknesses**:
- **W-LC1**: No validation of the YAML at load time. Typos in extractor names silently fall through to defaults
- **W-LC2**: The `extractor_mapping` doesn't cover the `llm_task_config.py` consumer — there's a gap between config definition and config consumption that could be validated at startup

---

### 2.9 enrichment/

**Files reviewed**: `terminology.py` (334 lines)

**Architecture**: Post-extraction enrichment that walks the USDM JSON and adds/corrects NCI terminology codes using the EVS client.

**Strengths**:
- Modifies USDM JSON in place (avoids copy overhead)
- Maps from centralized `terminology_codes.py` via legacy adapter dicts
- Partial match support for fuzzy code inference

**Weaknesses**:
- **W-EN1**: `enrich_terminology()` reads and writes the same JSON file — no backup is created before modification
- **W-EN2**: Legacy mapping dicts (`STUDY_PHASE_MAPPINGS`, `BLINDING_MAPPINGS`) are derived from `terminology_codes.py` but could be eliminated entirely if enrichment used `find_code_by_text()` directly

---

### 2.10 testing/ and tests/

**Files reviewed**: `testing/benchmark.py`, `testing/test_pipeline_steps.py`, `tests/` directory listing (18 test files)

#### 2.10.1 Benchmark Tool (`testing/benchmark.py`)

**Architecture**: Compares extracted USDM against golden standard files with per-entity precision, recall, and F1 scores. Semantic matching with configurable thresholds.

**Strengths**:
- Comprehensive entity-type comparison (activities, encounters, epochs, objectives, endpoints, etc.)
- Keyword match bonus for semantic similarity
- JSON and human-readable report output
- Automatic path detection for timestamped output directories

#### 2.10.2 Unit Tests (`tests/`)

**Coverage**: 18 test files covering core modules, execution model, reconciliation, LLM providers, normalization, M11 regression, processing, prompt quality, provenance, viewer load, and EVS codes.

**Strengths**:
- `test_execution_model.py` at 76,695 bytes is comprehensive
- `test_core_modules.py` covers schema loader, terminology, and provenance
- `test_reconciliation_framework.py` tests the reconciliation system
- `test_m11_regression.py` catches rendering regressions
- `test_prompt_quality.py` validates prompt structure and content

**Weaknesses**:
- **W-T1**: No test runner configuration (pytest.ini, setup.cfg, or pyproject.toml). Test discovery relies on convention
- **W-T2**: No CI/CD integration — tests appear to be run manually
- **W-T3**: No coverage tracking — unclear which modules/branches are tested
- **W-T4**: `test_outputs/` contains 15 fixture files (JSON) but no mechanism to regenerate them if the schema changes
- **W-T5**: No integration test that runs the full pipeline end-to-end on a test PDF and validates the output
- **W-T6**: Mocking LLM calls for unit tests appears inconsistent — some tests may make real API calls

---

### 2.11 scripts/ and tools/

#### 2.11.1 scripts/

- **`debug/`**: 5 debugging utilities (check_groups, compare_outputs, debug_footnotes, etc.)
- **`extractors/`**: 8 standalone extractor scripts for running individual phases
- **`run_all_trials.py`**: Batch processing for all trial protocols
- **`optimize_llm_params.py`**: LLM parameter optimization (produced the optimized values in llm_config.yaml)

#### 2.11.2 tools/

- **`cdisc-rules-engine/`**: Local CDISC CORE engine (Git submodule)
- **`usdm-rules/`**: USDM conformance rules (Git submodule)
- **`core/download_core.py`**: Downloads CORE engine binary
- **`download_trials.py`** (3 batches): Downloads trial protocols from ClinicalTrials.gov

**Strengths**:
- Good separation of development/debug utilities from production code
- Parameter optimization script provides data-driven LLM config
- Trial download scripts enable reproducible benchmarking

**Weaknesses**:
- **W-S1**: `scripts/extractors/` duplicate the phase execution logic from `main_v3.py`. These should call into the pipeline programmatically rather than reimplementing
- **W-S2**: No documentation for scripts/ — `analyze_issues.py`, `optimize_llm_params.py` lack usage instructions

---

## 3. Architectural Strengths

### S1: Schema-Driven Everything
The official CDISC `dataStructure.yml` drives Python dataclasses, TypeScript interfaces, LLM prompts, and validation. This ensures consistency across the entire stack when the schema evolves.

### S2: Registry-Based Pipeline
The phase registry pattern eliminates duplicated phase-handling code and enables extensibility. Adding a new extraction phase requires only a `BasePhase` subclass and registration — no orchestrator changes.

### S3: Extension→USDM Promotion
The architectural principle that core USDM is self-sufficient while extensions provide additional detail is well-executed. The promotion mechanism (4 rules) cleanly enriches core entities from conditional sources without coupling.

### S4: Dual-Path Rendering
Separating extractors (narrative from PDF) from composers (USDM entities → prose) is a key architectural insight. Composers work independently of extraction, enabling future USDM-first authoring where no PDF exists.

### S5: Unified Reconciliation Framework
The priority-based reconciliation across 3 entity types (epochs, encounters, activities) from 5+ data sources is sophisticated and well-designed. Extension attributes preserve traceability.

### S6: Task-Based LLM Configuration
The 4-category task abstraction with hierarchical overrides is an elegant solution to the "every model has different optimal parameters" problem. The optimization data backing the config adds credibility.

### S7: Thread-Safe Parallel Execution
Context isolation via `snapshot()`/`merge_from()` with field-specific merge mappings is a correct approach to parallel phase execution with shared state.

### S8: M11 Mapping Config as Single Source of Truth
The YAML config consumed by mapper, renderer, conformance validator, and orchestrator eliminates redundant section definitions across the codebase.

### S9: Run Manifest for Reproducibility
`run_manifest.json` captures input hash, model, phases, schema version, and timestamp — essential for reproducing pipeline runs.

### S10: Graceful Degradation
The pipeline continues past individual phase failures, optional dependency handling (`ImportError` catch), and fallback defaults for required fields make the system robust in practice.

---

## 4. Architectural Weaknesses

### Critical (Architectural Impact)

#### W-CRIT-1: God Function — `combine_to_full_usdm()` — ✅ FIXED
~~At 1,150+ lines, this function handles 15+ distinct concerns.~~ Decomposed into 4 focused modules: `pipeline/combiner.py` (420 lines), `pipeline/integrations.py` (289 lines), `pipeline/post_processing.py` (436 lines), `pipeline/promotion.py` (260 lines). `orchestrator.py` reduced from 1,650 to 332 lines. Backward-compatible re-exports maintained.

#### W-CRIT-2: No End-to-End Integration Test
There is no automated test that runs the full pipeline on a test PDF and validates the output against a golden standard. The benchmark tool exists but isn't wired into a CI pipeline.

#### W-CRIT-3: Conditional Sources Break Registry Pattern
SAP and sites extraction bypass the phase registry, losing parallel execution, dependency management, and the combine lifecycle. They should be registered phases with conditional `requires_*` flags.

### High (Quality/Maintainability Impact)

#### W-HIGH-1: Monolithic Files
`llm_providers.py` (1,274 lines), `m11_renderer.py` (2,227 lines), and `orchestrator.py` (1,692 lines) each handle multiple concerns. Splitting these would improve maintainability and testability.

#### W-HIGH-2: PipelineContext Growing into God Object
28 data fields + 7 lookup maps with no decomposition. As phases are added, this will become unwieldy. Domain-specific sub-contexts (metadata, eligibility, design, scheduling) would scale better.

#### W-HIGH-3: ✅ FIXED — Provenance for Expansion Phases
All expansion phases now auto-capture provenance (phase, model, timing, entity counts, confidence) via `PhaseProvenance` in `BasePhase.run()`. Aggregated to `extraction_provenance.json` by `PipelineOrchestrator.save_provenance()`.

#### W-HIGH-4: Mutable Global State
`phase_registry`, `usage_tracker`, and EVS `_client` singleton are mutable module-level globals. This makes testing difficult and creates hidden coupling.

### Medium (Improvement Opportunities)

#### W-MED-1: Inconsistent Error Handling
Some modules use `try/except` with logging, others let exceptions propagate. No unified error type hierarchy for extraction failures vs. validation failures vs. rendering failures.

#### W-MED-2: Version String Duplication
"7.2.0" appears in multiple files. Should be `core.constants.VERSION`.

#### W-MED-3: No Prompt Versioning
When prompts change, existing extraction results become unreproducible. Storing a prompt hash or version in the output would help.

#### W-MED-4: Duplicate Terminology Code Sources
`evs_client.py::USDM_CODES` and `terminology_codes.py` overlap. One should be the source, the other should derive.

---

## 5. Cross-Cutting Concerns

### 5.1 Logging
- **Current**: Standard Python `logging` with `[%(levelname)s] %(message)s` format
- **Issue**: No structured logging. Log messages mix emoji icons, indentation levels, and formatting styles. In production/CI, structured JSON logging would enable better observability
- **Recommendation**: Adopt structured logging with context fields (phase, entity_count, duration_ms)

### 5.2 Configuration Management
- **Current**: Mix of `constants.py`, `llm_config.yaml`, environment variables, and CLI arguments
- **Issue**: No single place to see all configuration. Some config is in Python constants, some in YAML, some in `.env`
- **Recommendation**: Consolidate into a hierarchical config system (e.g., `pydantic-settings` or `dynaconf`)

### 5.3 Dependency Management
- **Current**: `requirements.txt` with pinned versions
- **Issue**: Some optional dependencies (`usdm`, `anthropic`) are imported conditionally. No `extras_require` or dependency groups
- **Recommendation**: Use `pyproject.toml` with optional dependency groups (`[pipeline]`, `[validation]`, `[web]`)

### 5.4 Error Taxonomy
- **Current**: Exceptions are caught and logged as strings. `PhaseResult.error` is a raw string
- **Issue**: No way to programmatically distinguish extraction failure from LLM timeout from schema validation error
- **Recommendation**: Define `PipelineError` hierarchy: `ExtractionError`, `ValidationError`, `RenderingError`, `LLMError`

### 5.5 Serialization
- **Current**: Mix of `to_dict()` methods, `vars()`, `json.dumps()`, and Pydantic `.model_dump()`
- **Issue**: No consistent serialization strategy. Some entities use dataclass-based `to_dict()`, others use Pydantic, others use raw dicts
- **Recommendation**: Standardize on Pydantic v2 models throughout, or define a `Serializable` protocol

### 5.6 Extension Namespace Inconsistency (Backend↔Frontend) ⚠️ EXT
- **Current**: The Python backend uses `https://protocol2usdm.io/extensions/x-...` (`orchestrator.py`, `execution_model_promoter.py`), while the TypeScript frontend uses `https://usdm.cdisc.org/extensions/x-...` (`web-ui/lib/extensions.ts:124-132`)
- **Issue**: Extensions written by the pipeline cannot be reliably matched by the web UI's `findExt()` function, and vice versa. This is a **data interoperability bug** between the two halves of the system
- **Recommendation**: Define a single canonical extension URL prefix (e.g., `https://protocol2usdm.io/extensions/`) and share the constant between both codebases. The `findExt()` suffix-matching approach provides partial mitigation but is fragile

### 5.7 Renderer Anti-Pattern (Externally Confirmed) ⚠️ EXT
- **Current**: `_compose_safety()` (§9) and `_compose_discontinuation()` (§7) in `m11_renderer.py` perform keyword scanning of narrative text at render time to decide which content maps to which M11 section
- **Issue**: This is extraction logic masquerading as rendering. Both external reviewers independently flagged this. The renderer should be a pure composer that reads pre-tagged USDM entities, not an inline content classifier
- **Recommendation**: Move keyword-based section inference to the narrative extraction phase. Tag `NarrativeContentItem` entities with `sectionType` at extraction time. Renderer reads the tag and places content accordingly (see P15 in `docs/M11_USDM_ALIGNMENT.md`)

---

## 6. Enhancement Roadmap

### Phase 1: Structural Refactoring (Weeks 1-2)
| ID | Enhancement | Priority | Effort |
|----|------------|----------|--------|
| E1 | Decompose `combine_to_full_usdm()` into 10+ focused functions | ✅ FIXED | 3d |
| E2 | Split `llm_providers.py` into `providers/` package | ✅ FIXED | 1d |
| E3 | Split `m11_renderer.py` — extract composers to `rendering/composers/` | ✅ FIXED | 2d |
| E4 | Register SAP/sites as proper pipeline phases | HIGH | 2d |
| E5 | Move version string to `core.constants.VERSION` | LOW | 1h |
| E6 | Move `epoch_reconciler.py` into `core/reconciliation/` | LOW | 1h |
| E25 | Unify extension namespace backend↔frontend (⚠️ EXT) | ✅ FIXED (already consistent) | 2h |
| E26 | Move renderer keyword scanning to extraction-time tagging (⚠️ EXT) | MEDIUM | 2d |

### Phase 2: Quality Infrastructure (Weeks 3-4)
| ID | Enhancement | Priority | Effort |
|----|------------|----------|--------|
| E7 | Add `pytest.ini` + `pyproject.toml` with test discovery | ✅ FIXED | 1d |
| E8 | Create end-to-end integration test with golden PDF | ✅ FIXED | 3d |
| E9 | Add coverage tracking (`pytest-cov`) | ✅ FIXED | 1d |
| E10 | Mock LLM calls in all unit tests | ✅ FIXED | 2d |
| E11 | CI/CD pipeline (GitHub Actions) | HIGH | 2d |
| E12 | Structured JSON logging | ✅ FIXED | 1d |

### Phase 3: Architecture Improvements (Weeks 5-8)
| ID | Enhancement | Priority | Effort |
|----|------------|----------|--------|
| E13 | Decompose `PipelineContext` into sub-contexts | ✅ FIXED | 2d |
| E14 | Add provenance tracking for expansion phases | ✅ FIXED | 3d |
| E15 | Prompt versioning — hash prompts, store in output metadata | ✅ FIXED | 1d |
| E16 | Define `PipelineError` hierarchy | ✅ FIXED | 1d |
| E17 | Consolidate terminology codes (eliminate `USDM_CODES` duplication) | ✅ FIXED | 1d |
| E18 | M11 mapping YAML schema validation at load time | ✅ FIXED | 1d |
| E19 | SoA table rendering in M11 DOCX | ✅ FIXED | 3d |

### Phase 4: Performance & Scalability (Weeks 9-12)
| ID | Enhancement | Priority | Effort |
|----|------------|----------|--------|
| E20 | Parallelize execution model sub-extractors | ✅ FIXED | 2d |
| E21 | LLM response streaming for progress visibility | ✅ FIXED | 2d |
| E22 | Chunked EVS cache (per-code files instead of single JSON) | ✅ FIXED | 1d |
| E23 | Async LLM calls (`asyncio`/`aiohttp` instead of threading) | ✅ FIXED | 5d |
| E24 | Cache-aware execution model (model+prompt hash in cache key) | ✅ FIXED | 1d |

---

## 7. Open Critique — How I Would Approach This Differently

### 7.1 Pipeline as DAG, Not Phases

The current linear/wave-based phase model works but limits flexibility. A **Directed Acyclic Graph (DAG)** scheduler (similar to Airflow/Prefect) would:
- Allow fine-grained dependencies (e.g., "estimands need objectives AND eligibility")
- Enable partial re-runs without dependency inference
- Provide built-in retry, caching, and logging per node
- Make the execution plan visualizable

The `_build_execution_waves()` function is essentially a naive topological sort — a proper DAG scheduler would be a natural evolution.

### 7.2 Pydantic All the Way Down

The current type system mixes dataclasses, Pydantic models (in extraction schemas), raw dicts (in combine/orchestrator), and generated types. I would standardize on **Pydantic v2 models** throughout:
- Extraction schemas → already Pydantic ✓
- Internal types (Timeline, HeaderStructure) → Pydantic
- PipelineContext → Pydantic with validators
- PhaseResult → Pydantic with discriminated union on error type
- Combined USDM → Pydantic model matching the official `usdm_model.Wrapper`

This would give runtime validation, serialization, and IDE support everywhere.

### 7.3 Separate Combine from Orchestration

`combine_to_full_usdm()` should not exist as a monolithic function. Instead:
1. Each phase's `combine()` method populates a **typed builder** (`USDMDocumentBuilder`)
2. The builder enforces schema invariants at each step
3. Post-processing passes (reconciliation, promotion, linking) are registered as **middleware** on the builder
4. The builder's `build()` method produces the final JSON with validation

### 7.4 Event-Sourced Phase Results

Instead of overwriting extraction results, I would use an **event-sourced** approach:
1. Each phase produces immutable extraction events
2. Events are persisted chronologically
3. The "current USDM" is a projection of all events
4. Re-running a phase appends new events rather than replacing old ones
5. This gives full audit trail, easy rollback, and diff capability

### 7.5 LLM Abstraction as Middleware Stack

The current provider abstraction is function-call based. A **middleware stack** approach would be more composable:
```
LLM Call → Rate Limiter → Token Counter → Cache Check → Retry Handler → Provider
```
Each concern (rate limiting, token tracking, caching, retry) would be a separate middleware, composable via configuration.

### 7.6 Rendering as Templates

The M11 renderer uses procedural Python to build DOCX elements. A **template-based** approach (e.g., `docxtpl` with Jinja2 templates) would:
- Allow non-developers to modify document structure
- Support sponsor-specific templates
- Separate content logic from presentation
- Enable multiple output formats (DOCX, PDF, HTML) from the same template data

---

*End of review. See `docs/WEB_UI_REVIEW.md` for the web UI analysis.*
