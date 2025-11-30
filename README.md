# Protocol2USDM

**Extract clinical protocol content into USDM v4.0 format**

Protocol2USDM is an automated pipeline that extracts, validates, and structures clinical trial protocol content into data conformant to the [CDISC USDM v4.0](https://www.cdisc.org/standards/foundational/usdm) model.

> **📢 v6.3.0 Update:** NCI EVS terminology enrichment! Entities are now enriched with official NCI codes via the EVS API with local caching. Use `--enrich` to enable. Also includes CDISC CORE integration with `--update-cache` for rule management. Schema-driven architecture with 86+ auto-generated entity types from `dataStructure.yml`.

---

## 🚀 Try It Now

```bash
python main_v2.py .\input\Alexion_NCT04573309_Wilsons.pdf --full-protocol --enrich --sap .\input\Alexion_NCT04573309_Wilsons_SAP.pdf --model gemini-3-pro-preview --view
```

```bash
python main_v2.py .\input\Alexion_NCT04573309_Wilsons.pdf --full-protocol --enrich --sap .\input\Alexion_NCT04573309_Wilsons_SAP.pdf --model claude-opus-4-5 --view
```

```bash
python main_v2.py .\input\Alexion_NCT04573309_Wilsons.pdf --full-protocol --enrich --sap .\input\Alexion_NCT04573309_Wilsons_SAP.pdf --model gpt-5.1 --view
```

This extracts the full protocol, enriches entities with NCI terminology codes, includes SAP analysis populations, and launches the interactive viewer.

---

## Features

- **Multi-Model Support**: GPT-5.1, GPT-4o, Gemini 2.5/3.x via unified provider interface
- **Vision-Validated Extraction**: Text extraction validated against actual PDF images
- **USDM v4.0 Compliant**: Outputs follow official CDISC schema with proper entity hierarchy
- **NCI Terminology Enrichment**: Automatic enrichment with official NCI codes via EVS API
- **Activity Group Hierarchy**: Groups represented as parent Activities with `childIds` (USDM v4.0 pattern)
- **SoA Footnotes**: Captured and stored as `CommentAnnotation` objects in `StudyDesign.notes`
- **Rich Provenance**: Every cell tagged with source (text/vision/both) for confidence tracking
- **CDISC CORE Validation**: Built-in conformance checking with local engine
- **Interactive Viewer**: Streamlit-based SoA review interface with collapsible sections

### Extraction Capabilities (v6.2)

| Module | Entities | CLI Flag |
|--------|----------|----------|
| **SoA** | Activity, PlannedTimepoint, Epoch, Encounter, CommentAnnotation | (default) |
| **Metadata** | StudyTitle, StudyIdentifier, Organization, Indication | `--metadata` |
| **Eligibility** | EligibilityCriterion, StudyDesignPopulation | `--eligibility` |
| **Objectives** | Objective, Endpoint, Estimand | `--objectives` |
| **Study Design** | StudyArm, StudyCell, StudyCohort | `--studydesign` |
| **Interventions** | StudyIntervention, AdministrableProduct, Substance | `--interventions` |
| **Narrative** | NarrativeContent, Abbreviation, StudyDefinitionDocument | `--narrative` |
| **Advanced** | StudyAmendment, GeographicScope, Country | `--advanced` |
| **Procedures** | Procedure, MedicalDevice, Ingredient, Strength | `--procedures` |
| **Scheduling** | Timing, Condition, TransitionRule, ScheduleTimelineExit | `--scheduling` |

#### Conditional Sources (Additional Documents)

| Source | Entities | CLI Flag |
|--------|----------|----------|
| **SAP** | AnalysisPopulation, Characteristic | `--sap <path>` |
| **Site List** | StudySite, StudyRole, AssignedPerson | `--sites <path>` |

---

## Full Protocol Extraction

Extract everything with a single command:

```bash
python main_v2.py protocol.pdf --full-protocol
```

Or select specific sections:

```bash
python main_v2.py protocol.pdf --metadata --eligibility --objectives
python main_v2.py protocol.pdf --expansion-only --metadata  # Skip SoA
python main_v2.py protocol.pdf --procedures --scheduling   # New phases
```

With additional source documents:

```bash
python main_v2.py protocol.pdf --full-protocol --sap sap.pdf --sites sites.xlsx
```

Output: Individual JSONs + combined `protocol_usdm.json`

---

## Quick Start

```bash
# 1. Clone repository
git clone https://github.com/Panikos/Protcol2USDMv3.git
cd Protcol2USDMv3

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up API keys (.env file)
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...

# 4. Run the pipeline
python main_v2.py input/your_protocol.pdf

# 5. View results
streamlit run soa_streamlit_viewer.py
```

---

## Installation

### Requirements
- Python 3.9+
- API keys: OpenAI and/or Google AI

### Setup

```bash
# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Create .env file with API keys
echo "OPENAI_API_KEY=sk-your-key" > .env
echo "GOOGLE_API_KEY=AIza-your-key" >> .env
echo "CDISC_API_KEY=your-cdisc-key" >> .env
```

### CDISC CORE Engine (Optional)
For conformance validation, download the CORE engine:
```bash
python tools/core/download_core.py
```

**Note:** Get your CDISC API key from https://library.cdisc.org/ (requires CDISC membership)

---

## Usage

### Basic Usage

```bash
python main_v2.py <protocol.pdf> [options]
```

### Model Selection

```bash
# Use GPT-5.1 (default)
python main_v2.py protocol.pdf --model gpt-5.1

# Use Gemini 3 Pro Preview
python main_v2.py protocol.pdf --model gemini-3-pro-preview

# Use Gemini 2.5 Pro
python main_v2.py protocol.pdf --model gemini-2.5-pro

# Use GPT-4o
python main_v2.py protocol.pdf --model gpt-4o
```

### Full Pipeline with Post-Processing

```bash
# Run extraction + enrichment + schema validation + CORE conformance
python main_v2.py protocol.pdf --full

# Or run post-processing steps individually
python main_v2.py protocol.pdf --enrich              # Step 7: NCI terminology
python main_v2.py protocol.pdf --validate-schema     # Step 8: Schema validation
python main_v2.py protocol.pdf --conformance         # Step 9: CORE conformance
```

### Additional Options

```bash
--output-dir, -o    Output directory (default: output/<protocol_name>)
--pages, -p         Specific SoA page numbers (comma-separated)
--no-validate       Skip vision validation
--remove-hallucinations  Remove cells not confirmed by vision (default: keep all)
--view              Launch Streamlit viewer after extraction
--verbose, -v       Enable verbose output
```

---

## Pipeline Steps

### SoA Extraction (Steps 1-4)

| Step | Description | Output File |
|------|-------------|-------------|
| 1 | Find SoA pages & analyze header structure (vision) | `4_header_structure.json` |
| 2 | Extract SoA data from text | `5_text_extraction.json` |
| 3 | Validate extraction against images | `6_validation_result.json` |
| 4 | Build final SoA output | `9_final_soa.json` |

### Expansion Phases (with `--full-protocol`)

| Phase | Entities | Output File |
|-------|----------|-------------|
| Metadata | StudyTitle, Organization, Indication | `2_study_metadata.json` |
| Eligibility | EligibilityCriterion, Population | `3_eligibility_criteria.json` |
| Objectives | Objective, Endpoint, Estimand | `4_objectives_endpoints.json` |
| Study Design | StudyArm, StudyCell, StudyCohort | `5_study_design.json` |
| Interventions | StudyIntervention, Product | `6_interventions.json` |
| Narrative | Abbreviation, NarrativeContent | `7_narrative_structure.json` |
| Advanced | StudyAmendment, Country | `8_advanced_entities.json` |
| Procedures | Procedure, MedicalDevice | `9_procedures_devices.json` |
| Scheduling | Timing, Condition, TransitionRule | `10_scheduling_logic.json` |

### Post-Processing (Steps 7-9)

| Step | Description | Output File |
|------|-------------|-------------|
| Combine | Merge all extractions | `protocol_usdm.json` ⭐ |
| Terminology | NCI EVS code enrichment | `terminology_enrichment.json` |
| Schema Fix | Auto-fix schema issues (UUIDs, Codes) | `schema_validation.json` |
| Conformance | CDISC CORE validation | `conformance_report.json` |

**Primary output:** `output/<protocol>/protocol_usdm.json`

---

## Output Structure

The output follows the USDM v4.0 schema with proper `Study → StudyVersion → StudyDesign` hierarchy.

For detailed output structure and entity relationships, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#output-structure).

### Provenance Tracking

Provenance metadata is stored separately in `9_final_soa_provenance.json` and visualized in the Streamlit viewer:

| Source | Color | Meaning |
|--------|-------|---------|
| `both` | 🟩 Green | Confirmed (text + vision agree) |
| `text` | 🟦 Blue | Text-only (NOT confirmed by vision) |
| `vision` | 🟧 Orange | Vision-only (possible hallucination, needs review) |
| (none) | 🔴 Red | Orphaned (no provenance data) |

View provenance in the interactive viewer:
```bash
streamlit run soa_streamlit_viewer.py
```

**Note:** By default, all text-extracted cells are kept in the output. Use `--remove-hallucinations` to exclude cells not confirmed by vision.

### SoA Footnotes

Footnotes extracted from SoA tables are stored in `StudyDesign.notes` as USDM v4.0 `CommentAnnotation` objects:

```json
"notes": [
  {"id": "soa_fn_1", "text": "a. Within 32 days of administration", "instanceType": "CommentAnnotation"},
  {"id": "soa_fn_2", "text": "b. Participants admitted 10 hours prior", "instanceType": "CommentAnnotation"}
]
```

---

## Viewing Results

Launch the interactive Streamlit viewer:

```bash
streamlit run soa_streamlit_viewer.py
```

**Features:**
- Visual SoA table with color-coded provenance
- Epoch and encounter groupings
- Filtering by activity/timepoint
- Quality metrics dashboard
- Validation & conformance results tab
- Raw JSON inspection

---

## Model Benchmark

SoA extraction tested on Alexion Wilson's Disease protocol (Nov 2025):

| Model | Activities | Timepoints | Ticks | Vision Header | Recommendation |
|-------|------------|------------|-------|---------------|----------------|
| **Claude Opus 4.5** | 36 ✓ | 24 ✓ | 212 (100% confirmed) | ✅ | **Best accuracy** |
| **Gemini 3 Pro** | 36 ✓ | 24 ✓ | 207 (10 flagged) | ✅ | Good, slower |
| GPT-5.1 | 36 ✓ | 0 ❌ | 0 ❌ | ❌ | Vision issues |

**Notes:**
- Claude Opus 4.5: Best overall - all ticks confirmed by vision validation
- Gemini 3 Pro: Good accuracy, flags potential hallucinations for review
- GPT-5.1: Vision-based header analysis fails; text extraction works but no tick matrix

---

## Project Structure

```
Protocol2USDMv3/
├── main_v2.py                # Main pipeline entry point
├── core/                     # Core modules
│   ├── usdm_schema_loader.py # Official CDISC schema parser + USDMEntity base
│   ├── usdm_types_generated.py # 86+ auto-generated USDM types
│   ├── usdm_types.py         # Unified type interface
│   ├── evs_client.py         # NCI EVS API client with caching
│   ├── provenance.py         # ProvenanceTracker for source tracking
│   ├── llm_client.py         # LLM client
│   └── json_utils.py         # JSON utilities
├── extraction/               # Extraction modules
│   ├── header_analyzer.py    # Vision-based structure
│   ├── text_extractor.py     # Text-based extraction
│   ├── pipeline.py           # SoA extraction pipeline
│   ├── validator.py          # Extraction validation
│   └── */                    # Domain extractors (11 modules)
├── enrichment/               # Terminology enrichment
│   └── terminology.py        # NCI EVS enrichment
├── validation/               # Validation package
│   ├── usdm_validator.py     # Official USDM validation
│   └── cdisc_conformance.py  # CDISC CORE conformance
├── prompts/                  # YAML prompt templates
├── testing/                  # Benchmarking & integration tests
├── utilities/                # Setup scripts
├── docs/                     # Architecture documentation
├── soa_streamlit_viewer.py   # Interactive viewer
├── tools/core/               # CDISC CORE engine
└── output/                   # Pipeline outputs
```

For detailed architecture, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Testing

```bash
# Run unit tests
pytest tests/

# Run integration tests
python testing/test_pipeline_steps.py

# Run golden standard comparison
python testing/compare_golden_vs_extracted.py

# Benchmark models
python testing/benchmark_models.py
```

---

## Configuration

### Environment Variables

```bash
# Required - at least one LLM provider
OPENAI_API_KEY=sk-...       # For GPT models
GOOGLE_API_KEY=AIza...      # For Gemini models

# Required for CDISC conformance validation
CDISC_API_KEY=...           # For CORE rules cache (get from library.cdisc.org)
```

### Supported Models

**OpenAI:**
- `gpt-5.1` (recommended)
- `gpt-4o`
- `gpt-4`

**Google:**
- `gemini-3-pro-preview`
- `gemini-2.5-pro`
- `gemini-2.5-flash`
- `gemini-2.0-flash`

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| API key error | Check `.env` file, restart terminal |
| Missing visits | Verify correct SoA pages found (check `4_header_structure.json`) |
| Parse errors | Try different model, check verbose logs |
| Schema errors | Post-processing auto-fixes most issues |

---

## Roadmap / TODO

The following items are planned for upcoming releases:

- [ ] **Biomedical Concepts**: Add extraction via a separate comprehensive canonical model for standardized concept mapping
- [x] **Provenance ID Consistency**: Idempotent UUID generation ensures provenance IDs match data *(completed v6.3.0)*
- [x] **NCI EVS Terminology Enrichment**: Real-time EVS API integration with local caching *(completed v6.3.0)*
- [x] **CDISC CORE Integration**: Local CORE engine for conformance validation with cache update *(completed v6.3.0)*
- [x] **Schema-Driven Architecture**: All types from official `dataStructure.yml` *(completed v6.2.0)*
- [x] **Repository Cleanup**: Cleaned codebase, archived orphaned files *(completed v6.3.0)*
- [x] **Activity Group Hierarchy**: Groups now use USDM v4.0 `childIds` pattern *(completed v6.1.2)*
- [x] **SoA Footnotes**: Stored as `CommentAnnotation` in `StudyDesign.notes` *(completed v6.1.2)*

---

## License

Contact author for permission to use.

---

## Acknowledgments

- [CDISC](https://www.cdisc.org/) for USDM specification
- [CDISC CORE Engine](https://github.com/cdisc-org/cdisc-rules-engine) for conformance validation
- [NCI EVS](https://evs.nci.nih.gov/) for terminology services
