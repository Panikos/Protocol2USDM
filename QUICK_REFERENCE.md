# Protocol2USDM Quick Reference

**v7.0** | One-page command reference

> **Current:** Full USDM 4.0 compliance, execution model extraction, modern React/Next.js web UI, pipeline context architecture.

---

## Quick Start

```bash
pip install -r requirements.txt
echo "GOOGLE_API_KEY=AIza..." > .env

# Recommended: Full protocol extraction with viewer
python main_v2.py .\input\Alexion_NCT04573309_Wilsons.pdf --full-protocol --sap .\input\Alexion_NCT04573309_Wilsons_SAP.pdf --model gemini-2.5-pro --view
```

---

## Common Commands

### Basic Usage

```bash
# SoA only (default)
python main_v2.py protocol.pdf

# Full protocol extraction (SoA + all phases)
python main_v2.py protocol.pdf --full-protocol

# Select specific phases
python main_v2.py protocol.pdf --metadata --eligibility --objectives

# Expansion only (skip SoA)
python main_v2.py protocol.pdf --expansion-only --metadata --eligibility

# With specific model
python main_v2.py protocol.pdf --model gemini-2.5-pro

# Specify SoA pages
python main_v2.py protocol.pdf --pages 45,46,47
```

### SoA Pipeline
```bash
python main_v2.py protocol.pdf                      # Default extraction
python main_v2.py protocol.pdf --model gemini-2.5-pro
python main_v2.py protocol.pdf --full               # With post-processing
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
--model, -m         Model to use (default: gemini-2.5-pro)
--output-dir, -o    Output directory
--pages, -p         Specific SoA pages (comma-separated)
--no-validate       Skip vision validation
--remove-hallucinations  Remove cells not confirmed by vision
--view              Launch viewer after
--verbose, -v       Detailed logging

# Post-processing
--full              Run all post-processing steps
--enrich            Step 7: NCI terminology
--validate-schema   Step 8: Schema validation
--conformance       Step 9: CORE conformance

# Expansion phases (v6.0)
--full-protocol     Extract everything (SoA + all phases)
--expansion-only    Skip SoA, run only expansion phases
--metadata          Phase 2: Study metadata
--eligibility       Phase 1: I/E criteria
--objectives        Phase 3: Objectives & endpoints
--studydesign       Phase 4: Study design structure
--interventions     Phase 5: Interventions & products
--narrative         Phase 7: Sections & abbreviations
--advanced          Phase 8: Amendments & geography
```

---

## Models

| Model | Speed | Reliability |
|-------|-------|-------------|
| **claude-opus-4-5** ⭐ | Medium | Best accuracy |
| **gemini-3-pro-preview** ⭐ | Fast | Recommended |
| gemini-2.5-pro | Fast | Good |
| gpt-4o | Medium | Good |

---

## Output Files

```
output/<protocol>/
├── protocol_usdm.json            ⭐ Combined full protocol output
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
└── conformance_report.json        # CDISC CORE results (--conformance)
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
pytest                              # All tests
pytest tests/test_pipeline_api.py   # Pipeline tests
pytest tests/test_llm_providers.py  # Provider tests

# SoA step-by-step debugging
python test_pipeline_steps.py protocol.pdf --step 3  # Header
python test_pipeline_steps.py protocol.pdf --step 4  # Text
python test_pipeline_steps.py protocol.pdf --step 5  # Vision
python test_pipeline_steps.py protocol.pdf --step 6  # Output

# USDM Expansion steps
python test_pipeline_steps.py protocol.pdf --step M  # Metadata
python test_pipeline_steps.py protocol.pdf --step E  # Eligibility
python test_pipeline_steps.py protocol.pdf --step O  # Objectives
python test_pipeline_steps.py protocol.pdf --step D  # Study Design
python test_pipeline_steps.py protocol.pdf --step I  # Interventions
python test_pipeline_steps.py protocol.pdf --step N  # Narrative
python test_pipeline_steps.py protocol.pdf --step A  # Advanced
python test_pipeline_steps.py protocol.pdf --step expand  # All phases
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
|------|---------|
| `main_v2.py` | Main pipeline (SoA + expansions) |
| `llm_providers.py` | LLM provider interface |
| `core/usdm_types_generated.py` | 86+ auto-generated USDM types |
| `core/evs_client.py` | NCI EVS API client with caching |
| `extraction/pipeline.py` | SoA extraction pipeline |
| `extraction/pipeline_context.py` | Context passing between extractors |
| `extraction/execution/` | Execution model extractors (27 modules) |
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

## USDM Entity Placement (v6.6)

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
| `timings` | `scheduleTimeline` |
| `exits` | `scheduleTimeline` |
| `definedProcedures` | `activity` |

---

**Docs:** [README.md](README.md) | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

**Last Updated:** 2026-01-28  
**Version:** 7.0
