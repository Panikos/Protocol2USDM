# Protocol2USDM

**Extract clinical protocol content into USDM v4.0 format**

Protocol2USDM is an automated pipeline that extracts, validates, and structures clinical trial protocol content into data conformant to the [CDISC USDM v4.0](https://www.cdisc.org/standards/foundational/usdm) model.

---

## Features

- **Multi-Model Support**: GPT-5.1, GPT-4o, Gemini 2.5/3.x via unified provider interface
- **Vision-Validated Extraction**: Text extraction validated against actual PDF images
- **USDM v4.0 Compliant**: Outputs follow official CDISC schema
- **Rich Provenance**: Every cell tagged with source (text/vision/both)
- **Terminology Enrichment**: Activities enriched with NCI EVS codes
- **CDISC CORE Validation**: Built-in conformance checking
- **Interactive Viewer**: Streamlit-based SoA review interface

### Extraction Capabilities (v6.0)

| Module | Entities | CLI Tool |
|--------|----------|----------|
| **SoA** | Activity, PlannedTimepoint, Epoch, Encounter | `main_v2.py` |
| **Metadata** | StudyTitle, StudyIdentifier, Organization, Indication | `extract_metadata.py` |
| **Eligibility** | EligibilityCriterion, StudyDesignPopulation | `extract_eligibility.py` |
| **Objectives** | Objective, Endpoint, Estimand | `extract_objectives.py` |
| **Study Design** | StudyArm, StudyCell, StudyCohort | `extract_studydesign.py` |
| **Interventions** | StudyIntervention, AdministrableProduct, Substance | `extract_interventions.py` |

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
--keep-hallucinations  Don't remove probable hallucinations
--view              Launch Streamlit viewer after extraction
--verbose, -v       Enable verbose output
```

---

## Pipeline Steps

The pipeline executes the following steps:

| Step | Description | Output File |
|------|-------------|-------------|
| 1 | Find SoA pages in PDF | (internal) |
| 2 | Extract page images | `3_soa_images/` |
| 3 | Analyze header structure (vision) | `4_header_structure.json` |
| 4 | Extract SoA data (text) | `5_text_extraction.json` |
| 5 | Validate extraction (vision) | `6_validation_result.json` |
| 6 | Build final USDM output | `9_final_soa.json` ⭐ |
| 7 | Enrich terminology (optional) | `step7_enriched_soa.json` |
| 8 | Schema validation (optional) | `step8_schema_validation.json` |
| 9 | CORE conformance (optional) | `conformance_report.json` |

**Primary output:** `output/<protocol>/9_final_soa.json`

---

## Output Structure

The output follows USDM v4.0 Wrapper-Input format:

```json
{
  "usdmVersion": "4.0",
  "systemName": "Protocol2USDMv3",
  "study": {
    "versions": [{
      "timeline": {
        "epochs": [...],              // Study phases
        "encounters": [...],          // Visits
        "plannedTimepoints": [...],   // Timepoints
        "activities": [...],          // Procedures/assessments
        "activityTimepoints": [...],  // Activity-timepoint mappings
        "activityGroups": [...]       // Activity categories
      }
    }]
  }
}
```

Provenance metadata (which extraction method found each entity) is stored in a separate file: `9_final_soa_provenance.json`

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

Based on testing across 4 protocols:

| Model | Success Rate | Avg Time | Recommendation |
|-------|-------------|----------|----------------|
| **GPT-5.1** | 100% | 92s | **Best reliability** |
| Gemini-3-pro-preview | 75% | 400s | More thorough but slower |

---

## Project Structure

```
Protocol2USDMv3/
├── main_v2.py              # Main pipeline entry point
├── extraction/             # Core extraction modules
│   ├── __init__.py
│   ├── pipeline.py         # Pipeline orchestration
│   ├── structure.py        # Header structure analysis
│   ├── text.py             # Text extraction
│   └── validator.py        # Vision validation
├── core/                   # Shared utilities
├── processing/             # Post-processing modules
├── prompts/                # YAML prompt templates
├── soa_streamlit_viewer.py # Interactive viewer
├── llm_providers.py        # Multi-model provider layer
├── benchmark_models.py     # Model benchmarking utility
├── test_pipeline_steps.py  # Step-by-step testing
├── tools/
│   └── core/               # CDISC CORE engine
└── output/                 # Pipeline outputs
```

---

## Testing

```bash
# Run all tests
pytest

# Run specific test suites
pytest tests/test_pipeline_api.py -v    # Pipeline tests
pytest tests/test_llm_providers.py -v   # Provider tests
pytest tests/test_processing.py -v      # Processing tests
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

## License

Contact author for permission to use.

---

## Acknowledgments

- [CDISC](https://www.cdisc.org/) for USDM specification
- [CDISC CORE Engine](https://github.com/cdisc-org/cdisc-rules-engine) for conformance validation
