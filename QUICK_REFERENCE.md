# Protocol2USDM Quick Reference

**v7.17** | One-page command reference

> **Current:** Encounter→epoch resolution via `ScheduledActivityInstance` bridge (SoA table, graph view, quality dashboard), UNS detached islands in graph + state machine, administrations nested in StudyIntervention, blindingSchema as AliasCode, activityGroups→parent Activity with childIds, footnote letter sequence (z→aa→ab), EditableCodedValue unwrap + Badge, SoA footnote objects. Reviewer v9 Org/Site alignment, P3–P7 structural compliance, 1157 tests / 1118 passing, USDM v4.0 endpoint nesting, M11 DOCX rendering, phase registry (`main_v3.py`), `gemini-3-flash-preview` default.

---

## Quick Start

```bash
pip install -r requirements.txt

# Configure Vertex AI for Gemini (recommended)
echo "GOOGLE_CLOUD_PROJECT=your-project-id" > .env
echo "GOOGLE_CLOUD_LOCATION=us-central1" >> .env

# Run full protocol extraction (defaults to --complete with gemini-3-flash-preview)
python main_v3.py input/trial/NCT04573309_Wilsons/NCT04573309_Wilsons_Protocol.pdf --sap input/trial/NCT04573309_Wilsons/NCT04573309_Wilsons_SAP.pdf --sites input/trial/NCT04573309_Wilsons/NCT04573309_Wilsons_sites.csv
```

> **Note:** Use Vertex AI (not AI Studio) for Gemini to disable safety controls for clinical content.

---

## Common Commands

### Basic Usage

```bash
# Default: --complete mode with gemini-3-flash-preview (no flags needed!)
python main_v3.py protocol.pdf

# With parallel execution for faster processing
python main_v3.py protocol.pdf --parallel --max-workers 4

# Select specific phases
python main_v3.py protocol.pdf --metadata --eligibility --objectives

# Expansion only (skip SoA)
python main_v3.py protocol.pdf --expansion-only --metadata --eligibility

# With specific model
python main_v3.py protocol.pdf --model gemini-2.5-pro

# Specify SoA pages
python main_v3.py protocol.pdf --pages 45,46,47
```

### SoA Pipeline
```bash
python main_v3.py protocol.pdf                      # Default: full extraction
python main_v3.py protocol.pdf --model gemini-2.5-pro
python main_v3.py protocol.pdf --soa                # SoA only with post-processing
```

### Standalone Extractors
```bash
# Study Metadata (title, identifiers, sponsor)
python scripts/extractors/extract_metadata.py protocol.pdf

# Eligibility Criteria (inclusion/exclusion)
python scripts/extractors/extract_eligibility.py protocol.pdf

# Objectives & Endpoints
python scripts/extractors/extract_objectives.py protocol.pdf

# Study Design (arms, cohorts, blinding)
python scripts/extractors/extract_studydesign.py protocol.pdf

# Interventions & Products
python scripts/extractors/extract_interventions.py protocol.pdf

# Narrative Structure (sections, abbreviations)
python scripts/extractors/extract_narrative.py protocol.pdf

# Advanced (amendments, geography)
python scripts/extractors/extract_advanced.py protocol.pdf

# Execution Model
python scripts/extractors/extract_execution_model.py protocol.pdf
```

### View Results
```bash
cd web-ui && npm run dev
# Open http://localhost:3000
```

### Options
```bash
# Core options
--model, -m         Model to use (default: gemini-3-flash-preview)
--output-dir, -o    Output directory
--pages, -p         Specific SoA pages (comma-separated)
--no-validate       Skip vision validation
--remove-hallucinations  Remove cells not confirmed by vision
--verbose, -v       Detailed logging

# Parallel execution (v7.1+)
--parallel          Run independent phases concurrently
--max-workers N     Max parallel workers (default: 4)

# Post-processing
--enrich            Step 7: NCI terminology
--validate-schema   Step 8: Schema validation
--conformance       Step 9: CORE conformance

# Expansion phases
--complete          Full extraction + post-processing (DEFAULT when no phases specified)
--full-protocol     Extract everything (SoA + all phases)
--expansion-only    Skip SoA, run only expansion phases
--metadata          Phase 2: Study metadata
--eligibility       Phase 1: I/E criteria
--objectives        Phase 3: Objectives & endpoints
--studydesign       Phase 4: Study design structure
--interventions     Phase 5: Interventions & products
--narrative         Phase 7: Sections & abbreviations
--advanced          Phase 8: Amendments & geography
--procedures        Phase 10: Procedures & devices
--scheduling        Phase 11: Scheduling logic
--execution         Phase 14: Execution model
```

---

## Models

**Supported (optimised and tested):**

| Model | Speed | Status |
|-------|-------|--------|
| **gemini-3-flash-preview** ⭐ | Fast | **Default — pipeline optimised and tuned** |
| gemini-2.5-pro | Fast | Tested fallback (auto for SoA text) |

> Provider hooks for OpenAI and Anthropic exist in `llm_providers.py` for future tuning but are **not yet optimised or tested**.

---

## Output Files

```
output/<protocol>/
├── protocol_usdm.json            ⭐ Combined full protocol output
├── m11_protocol.docx             ⭐ ICH M11-formatted Word document
├── m11_conformance.json          # M11 conformance scoring
├── protocol_usdm_provenance.json  # UUID-based provenance
├── 9_final_soa.json              ⭐ SoA extraction
├── 9_final_soa_provenance.json    # Source tracking (text/vision/both)
├── 2_study_metadata.json          # Study identity
├── 3_eligibility_criteria.json    # I/E criteria
├── 4_objectives_endpoints.json    # Objectives
├── 5_study_design.json            # Design structure
├── 6_interventions.json           # Products
├── 7_narrative_structure.json     # Sections/abbreviations
├── 8_advanced_entities.json       # Amendments/geography
├── 10_scheduling_logic.json       # Scheduling constraints
├── 11_execution_model.json        # Execution model
├── 4_header_structure.json        # SoA table structure (vision)
├── terminology_enrichment.json    # NCI EVS codes (--enrich)
├── schema_validation.json         # Schema validation results
├── usdm_validation.json           # USDM package validation
├── conformance_report.json        # CDISC CORE results (--conformance)
└── run_manifest.json              # Run metadata for reproducibility
```

---

## Provenance Colors (Viewer)

| Color | Source | Meaning |
|-------|--------|--------|
| 🟩 Green | `both` | Confirmed by text AND vision (high confidence) |
| 🟦 Blue | `text` | Text only (not vision-confirmed, review recommended) |
| 🟧 Orange | `vision` | Vision only or needs review |
| 🔴 Red | (none) | Orphaned (no provenance) |

**Note:** All text-extracted cells are kept by default. Use `--remove-hallucinations` to exclude unconfirmed cells.

---

## Testing

```bash
# All unit tests (1136 collected, ~3 min)
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ --cov --cov-report=term-missing

# Specific test modules
python -m pytest tests/test_extractors.py -v       # Mocked LLM tests (58)
python -m pytest tests/test_composers.py -v        # M11 composers (22)
python -m pytest tests/test_pipeline_context.py -v  # PipelineContext (48)
python -m pytest tests/test_async_llm.py -v         # Async LLM (16)
python -m pytest tests/test_llm_streaming.py -v     # LLM streaming (15)
python -m pytest tests/test_evs_chunked_cache.py -v # EVS cache (17)
python -m pytest tests/test_pipeline_registry.py -v # Phase registry (11)
python -m pytest tests/test_m11_regression.py -v    # M11 renderer

# E2E integration (requires recent pipeline output)
python -m pytest tests/test_e2e_pipeline.py --run-e2e -v
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| API key error | Check `.env`, restart terminal |
| Missing visits | Check `4_header_structure.json` |
| Parse errors | Try different model |
| Many orange cells | Try `--no-validate` |

---

## API Keys

```bash
# .env file
OPENAI_API_KEY=sk-proj-...   # For GPT models
GOOGLE_API_KEY=AIzaSy...     # For Gemini models
CDISC_API_KEY=...            # For CORE (optional)
```

**Get keys:**
- OpenAI: https://platform.openai.com/api-keys
- Google: https://makersuite.google.com/app/apikey

---

## Key Files

| File | Purpose |
|------|--------|
| `main_v3.py` | Entry point (phase registry architecture) |
| `pipeline/` | Phase registry architecture module |
| `pipeline/orchestrator.py` | Pipeline orchestration with parallel support |
| `pipeline/phases/` | Individual phase implementations |
| `llm_providers.py` | LLM provider abstraction layer |
| `core/constants.py` | Centralized constants (DEFAULT_MODEL, etc.) |
| `core/usdm_types_generated.py` | 86+ USDM types (hand-written, schema-aligned) |
| `extraction/pipeline.py` | SoA extraction pipeline |
| `extraction/pipeline_context.py` | Context passing between extractors |
| `extraction/execution/` | Execution model extractors (27 modules) |
| `core/code_registry.py` | Centralized NCI code registry |
| `core/code_verification.py` | EVS-backed code verification |
| `enrichment/terminology.py` | NCI terminology enrichment |
| `validation/cdisc_conformance.py` | CDISC CORE validation |
| `web-ui/` | React/Next.js protocol viewer |

### Standalone CLI Tools (in `scripts/extractors/`)

| File | Purpose |
|------|---------|
| `extract_metadata.py` | Study metadata only |
| `extract_eligibility.py` | I/E criteria only |
| `extract_objectives.py` | Objectives only |
| `extract_studydesign.py` | Study design only |
| `extract_interventions.py` | Interventions only |
| `extract_narrative.py` | Narrative only |
| `extract_advanced.py` | Amendments/geography only |
| `extract_execution_model.py` | Execution model only |

---

---

## USDM Entity Placement (v7.17)

| Entity | Location |
|--------|----------|
| `eligibilityCriterionItems` | `studyVersion` |
| `organizations` | `studyVersion` |
| `narrativeContentItems` | `studyVersion` |
| `abbreviations` | `studyVersion` |
| `conditions` | `studyVersion` |
| `amendments` | `studyVersion` |
| `administrableProducts` | `studyVersion` |
| `medicalDevices` | `studyVersion` |
| `studyInterventions` | `studyVersion` |
| `eligibilityCriteria` | `studyDesign` |
| `indications` | `studyDesign` |
| `analysisPopulations` | `studyDesign` |
| `endpoints` | `objective` (inline, Value relationship) |
| `timings` | `scheduleTimeline` |
| `exits` | `scheduleTimeline` |
| `definedProcedures` | `activity` |

---

**Docs:** [README.md](README.md) | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

**Last Updated:** 2026-02-18  
**Version:** 7.17
