# Protocol2USDM User Guide

**Version:** 7.17  
**Last Updated:** 2026-02-17

> **📢 What's New in v7.17:** **Reviewer v9 Org/Site alignment** — `studySites` removed from studyDesign (not a USDM path), sites only in `Organization.managedSites[]`, required org fields backfilled, StudySite sanitized, ISO country codes, site-org mapping fix. P3–P7 structural compliance. **UI fixes** — StudySitesView reads from `Organization.managedSites[]` + shows planned enrollment; FootnotesView handles object footnotes + reads `studyDesign.notes[]`; medicalDevices on studyVersion; DOCX XML sanitization. **1157 tests** collected, 1118 passing.

> **v7.16:** USDM v4.0 endpoint nesting, ExtensionAttribute alignment, core_compliance architectural audit.
> **v7.15:** Review fix sprint (B1–B9), keyword-guided enrollment extraction (G1).
> **v7.13:** Graph view neighborhood focus, layout selector, toolbar flex-wrap.

---

## Table of Contents
1. [Quick Start](#quick-start)
2. [Installation](#installation)
3. [Running the Pipeline](#running-the-pipeline)
4. [Full Protocol Extraction](#full-protocol-extraction)
5. [Standalone Extractors](#standalone-extractors)
6. [Understanding the Output](#understanding-the-output)
7. [Using the Viewer](#using-the-viewer)
8. [Post-Processing Steps](#post-processing-steps)
9. [Model Selection](#model-selection)
10. [Troubleshooting](#troubleshooting)

---

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Configure Vertex AI for Gemini (recommended for clinical content)
echo "GOOGLE_CLOUD_PROJECT=your-project-id" > .env
echo "GOOGLE_CLOUD_LOCATION=us-central1" >> .env

# Run full protocol extraction (defaults to --complete with gemini-3-flash-preview)
python main_v3.py input/trial/NCT04573309_Wilsons/NCT04573309_Wilsons_Protocol.pdf --sap input/trial/NCT04573309_Wilsons/NCT04573309_Wilsons_SAP.pdf --sites input/trial/NCT04573309_Wilsons/NCT04573309_Wilsons_sites.csv
```

**Expected runtime:** 3-8 minutes for full protocol extraction

> **⚠️ Important:** Use **Vertex AI** (not AI Studio) for Gemini models to disable safety controls for clinical content.

---

## Installation

### System Requirements
- Python 3.9+
- 4GB RAM minimum
- Internet connection (for API calls)

### Step 1: Clone Repository
```bash
git clone https://github.com/Panikos/Protcol2USDMv3.git
cd Protcol2USDMv3
```

### Step 2: Virtual Environment (Recommended)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Configure API Keys

Create a `.env` file in the project root:
```bash
# RECOMMENDED: Google Cloud Vertex AI (for Gemini models)
# Required for clinical content - AI Studio may block medical text
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1

# Alternative: Google AI Studio (may have safety restrictions)
GOOGLE_API_KEY=AIzaSy...

# OpenAI (for GPT models)
OPENAI_API_KEY=sk-proj-...

# Anthropic (for Claude models)
CLAUDE_API_KEY=...

# CDISC API (for conformance validation)
CDISC_API_KEY=...
```

**Get API keys:**
- Google Cloud: https://console.cloud.google.com/ (enable Vertex AI API)
- OpenAI: https://platform.openai.com/api-keys
- Anthropic: https://console.anthropic.com/
- CDISC: https://library.cdisc.org/ (requires CDISC membership)

### Step 5: Install CDISC CORE Engine (Optional)
For conformance validation:
```bash
python tools/core/download_core.py
```

---

## Running the Pipeline

### Basic Usage
```bash
# Recommended: main_v3.py (phase registry architecture)
python main_v3.py <protocol.pdf>

# Legacy main_v2.py has been removed — use main_v3.py
```

### With Options
```bash
python main_v3.py protocol.pdf                      # Default: --complete with gemini-3-flash-preview
python main_v3.py protocol.pdf --parallel           # Run phases concurrently
python main_v3.py protocol.pdf --model gemini-2.5-pro  # Specify model
python main_v3.py protocol.pdf --no-validate        # Skip vision validation
python main_v3.py protocol.pdf --verbose            # Detailed logging
```

### Pipeline Steps

The pipeline automatically executes:

1. **Find SoA Pages** - Identifies pages containing Schedule of Activities
2. **Extract Images** - Renders SoA pages as images
3. **Analyze Structure** - Uses vision to understand table headers
4. **Extract Data** - Extracts activities and timepoints from text
5. **Validate** - Vision model validates extraction against images
6. **Build Output** - Creates USDM-aligned JSON

### Post-Processing (Optional)

```bash
# Add all post-processing
python main_v3.py protocol.pdf --complete

# Or individually:
--enrich            # Step 7: Add NCI terminology codes
--validate-schema   # Step 8: Validate against USDM schema
--conformance       # Step 9: Run CDISC CORE conformance
```

---

## Full Protocol Extraction

Extract everything from a protocol with a single command:

```bash
# Default behavior - runs --complete automatically (no flags needed!)
python main_v3.py protocol.pdf

# Explicit full protocol extraction
python main_v3.py protocol.pdf --full-protocol

# With parallel execution for faster processing
python main_v3.py protocol.pdf --parallel --max-workers 4
```

### Selective Extraction

Run specific phases alongside SoA:

```bash
# SoA + metadata + eligibility
python main_v3.py protocol.pdf --metadata --eligibility

# SoA + objectives + interventions
python main_v3.py protocol.pdf --objectives --interventions
```

### Expansion-Only Mode

Skip SoA extraction and run only expansion phases:

```bash
# All expansion phases, no SoA
python main_v3.py protocol.pdf --expansion-only --metadata --eligibility --objectives --studydesign --interventions --narrative --advanced

# Just metadata and eligibility
python main_v3.py protocol.pdf --expansion-only --metadata --eligibility
```

### Available Flags

| Flag | Phase | Description |
|------|-------|-------------|
| `--metadata` | 2 | Study titles, identifiers, organizations |
| `--eligibility` | 1 | Inclusion/exclusion criteria |
| `--objectives` | 3 | Objectives, endpoints, estimands |
| `--studydesign` | 4 | Arms, cohorts, blinding |
| `--interventions` | 5 | Products, dosing, substances |
| `--narrative` | 7 | Sections, abbreviations |
| `--advanced` | 8 | Amendments, geography |
| `--full-protocol` | All | Everything (SoA + all phases) |
| `--expansion-only` | - | Skip SoA extraction |
| `--procedures` | 10 | Procedures & medical devices |
| `--scheduling` | 11 | Scheduling logic & timings |
| `--execution` | 14 | Execution model (anchors, windows) |
| `--parallel` | - | Run independent phases concurrently |

### Combined Output

When running multiple phases, a combined `protocol_usdm.json` is generated containing all extracted data in a single USDM-aligned structure.

---

## Standalone Extractors

For individual phase extraction without the main pipeline:

### Study Metadata (Phase 2)
Extracts study identity from title page and synopsis.
```bash
python scripts/extractors/extract_metadata.py protocol.pdf
```
**Entities:** `StudyTitle`, `StudyIdentifier`, `Organization`, `StudyRole`, `Indication`

### Eligibility Criteria (Phase 1)
Extracts inclusion and exclusion criteria.
```bash
python scripts/extractors/extract_eligibility.py protocol.pdf
```
**Entities:** `EligibilityCriterion`, `EligibilityCriterionItem`, `StudyDesignPopulation`

### Objectives & Endpoints (Phase 3)
Extracts primary, secondary, exploratory objectives with linked endpoints.
```bash
python scripts/extractors/extract_objectives.py protocol.pdf
```
**Entities:** `Objective`, `Endpoint`, `Estimand`, `IntercurrentEvent`

### Study Design Structure (Phase 4)
Extracts design type, blinding, randomization, arms, cohorts.
```bash
python scripts/extractors/extract_studydesign.py protocol.pdf
```
**Entities:** `InterventionalStudyDesign`, `StudyArm`, `StudyCell`, `StudyCohort`

### Interventions & Products (Phase 5)
Extracts investigational products, dosing regimens, substances.
```bash
python scripts/extractors/extract_interventions.py protocol.pdf
```
**Entities:** `StudyIntervention`, `AdministrableProduct`, `Administration`, `Substance`

### Narrative Structure (Phase 7)
Extracts document structure, sections, and abbreviations.
```bash
python scripts/extractors/extract_narrative.py protocol.pdf
```
**Entities:** `NarrativeContent`, `Abbreviation`, `StudyDefinitionDocument`

### Advanced Entities (Phase 8)
Extracts amendments, geographic scope, and study sites.
```bash
python scripts/extractors/extract_advanced.py protocol.pdf
```
**Entities:** `StudyAmendment`, `GeographicScope`, `Country`, `StudySite`

### Common Options
All standalone extractors support:
```bash
--model, -m        Model to use (default: gemini-2.5-pro)
--pages, -p        Specific pages to extract from (auto-detected if not specified)
--output-dir, -o   Output directory
--verbose, -v      Verbose output
```

---

## Understanding the Output

### Output Directory Structure
```
output/<protocol_name>/
├── 2_study_metadata.json         # Study identity (Phase 2)
├── 3_eligibility_criteria.json   # I/E criteria (Phase 1)
├── 4_objectives_endpoints.json   # Objectives (Phase 3)
├── 5_study_design.json           # Design structure (Phase 4)
├── 6_interventions.json          # Products (Phase 5)
├── 7_narrative_structure.json    # Sections/abbreviations (Phase 7)
├── 8_advanced_entities.json      # Amendments/geography (Phase 8)
├── 3_soa_images/                 # SoA page images
│   ├── soa_page_010.png
│   └── ...
├── 4_header_structure.json       # SoA table structure
├── 6_validation_result.json      # SoA validation details
├── 9_final_soa.json             # ⭐ FINAL SoA OUTPUT
├── 9_final_soa_provenance.json   # Source tracking
├── protocol_usdm.json            ⭐ Combined full protocol output
├── protocol_usdm_provenance.json  # UUID-based provenance
├── schema_validation.json         # Schema validation results
├── usdm_validation.json           # USDM package validation
└── conformance_report.json        # CORE conformance report
```

### Primary Output: `9_final_soa.json`

```json
{
  "usdmVersion": "4.0",
  "systemName": "Protocol2USDMv3",
  "study": {
    "id": "study_1",
    "versions": [{
      "timeline": {
        "epochs": [
          {"id": "epoch_1", "name": "Screening", "instanceType": "Epoch"}
        ],
        "encounters": [
          {"id": "enc_1", "name": "Visit 1", "epochId": "epoch_1"}
        ],
        "plannedTimepoints": [
          {"id": "pt_1", "name": "Day 1", "encounterId": "enc_1"}
        ],
        "activities": [
          {"id": "act_1", "name": "Vital Signs", "instanceType": "Activity"}
        ],
        "activityTimepoints": [
          {"activityId": "act_1", "plannedTimepointId": "pt_1"}
        ],
        "activityGroups": [
          {"id": "ag_1", "name": "Safety", "childIds": ["act_1"]}
        ]
      }
    }]
  }
}
```

### Provenance File

The `9_final_soa_provenance.json` tracks the source of each entity:

```json
{
  "entities": {
    "activities": {
      "act_1": "text",      // Found by text extraction
      "act_2": "both"       // Confirmed by vision
    }
  },
  "activityTimepoints": {
    "act_1": {
      "pt_1": "both",       // Activity-timepoint confirmed by both sources
      "pt_2": "text"        // Text only (not vision-confirmed)
    }
  }
}
```

### Provenance Sources

| Source | Meaning | Action |
|--------|---------|--------|
| `both` | Text extraction confirmed by vision | High confidence |
| `text` | Text extraction only (vision didn't find it) | Review recommended |
| `vision` | Vision only (text didn't find it) | Possible scan artifact |
| `needs_review` | Ambiguous result | Manual review needed |

**Default behavior:** All text-extracted cells are kept in the final USDM output. Use `--remove-hallucinations` flag to exclude cells not confirmed by vision.

---

## Using the Viewer

### Launch
```bash
cd web-ui
npm install  # First time only
npm run dev
```

Opens at: http://localhost:3000

### Viewer Features

**1. Protocol Run Selection**
- Dropdown to select from all pipeline runs
- Shows run timestamp and protocol name

**2. SoA Table Display**
- Color-coded cells by provenance:
  - 🟩 **Green**: Confirmed by both text AND vision (high confidence)
  - 🟦 **Blue**: Text extraction only (not vision-confirmed, review recommended)
  - 🟧 **Orange**: Vision only or needs review (possible hallucination)
  - 🔴 **Red**: Orphaned (no provenance data)
- Epoch groupings with colspan merge
- Activity groupings by category with proper hierarchy
- SoA footnotes in collapsible section below table
- Export & search functionality with CSV download
- JSON viewer in collapsible expander

**3. Quality Metrics Sidebar**
- Entity counts (activities, timepoints, etc.)
- Linkage accuracy score
- Activity-visit mappings count

**4. Protocol Expansion Data (v6.0)**
- Automatically shows when expansion files are present
- Tabbed navigation for each section:
  - 📄 **Metadata**: Study titles, identifiers, phase, indication
  - ✅ **Eligibility**: Inclusion/exclusion criteria with counts
  - 🎯 **Objectives**: Primary/secondary objectives and endpoints
  - 🔬 **Design**: Arms, cohorts, blinding schema
  - 💊 **Interventions**: Products, administrations, substances
  - 📖 **Narrative**: Document sections, abbreviations
  - 🌍 **Advanced**: Amendments, countries, sites
- Each tab shows key metrics and expandable raw JSON

**5. Intermediate Tabs**
- **Text Extraction**: Raw extraction results
- **Data Files**: Intermediate outputs
- **Config Files**: Pipeline configuration
- **SoA Images**: Extracted page images
- **Quality Metrics**: Detailed statistics
- **Validation & Conformance**: Schema and CORE results

---

## Post-Processing Steps

### Step 7: Terminology Enrichment
Adds NCI EVS codes to activities:
```bash
python main_v3.py protocol.pdf --enrich
```

### Step 8: Schema Validation
Validates against USDM v4.0 schema:
```bash
python main_v3.py protocol.pdf --validate-schema
```

### Step 9: CDISC CORE Conformance
Runs CORE rules validation:
```bash
python main_v3.py protocol.pdf --conformance
```

**Note:** Requires CORE engine installed via `tools/core/download_core.py`

---

## Model Selection

### Supported Models

**Supported (optimised and tested):**

| Model | Provider | Speed | Best For |
|-------|----------|-------|----------|
| `gemini-3-flash` | Google | **Fast** | **Recommended — pipeline optimised and tuned for this model** |
| `gemini-2.5-pro` | Google | Medium | Tested fallback (auto-used for SoA text extraction) |

**Future (hooks exist, not yet tuned):**

| Model | Provider | Status |
|-------|----------|--------|
| `claude-opus-4-5` | Anthropic | Provider hook implemented, not tuned |
| `claude-sonnet-4` | Anthropic | Provider hook implemented, not tuned |
| `gpt-5.2` | OpenAI | Provider hook implemented, not tuned |

### Gemini 3 Flash with Intelligent Fallback

When using `gemini-3-flash`, the pipeline automatically uses `gemini-2.5-pro` for SoA text extraction only. This is because Gemini 3 Flash has issues with the specific JSON output format required for SoA extraction.

**What happens:**
1. SoA header analysis → Uses `gemini-3-flash` 
1. SoA text extraction → Falls back to `gemini-2.5-pro` (automatic)
3. All expansion phases → Uses `gemini-3-flash` 

**Log output:**
```
[INFO] Step 2: Extracting SoA data from text...
[INFO]   Using fallback model for SoA text extraction: gemini-2.5-pro
```

### Vertex AI Configuration (Required for Gemini)

Gemini models require Vertex AI for clinical protocol extraction (to properly disable safety controls):

```bash
# In .env file
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1  # or your preferred region
GOOGLE_API_KEY=AIzaSy...  # Still needed for authentication
```

### Benchmark Results

| Model | Success Rate | SoA Extraction | Expansion Phases |
|-------|-------------|----------------|------------------|
| gemini-3-flash | 100% | via fallback | All 12 ✓ |
| gemini-2.5-pro | 100% | Native | All 12 ✓ |

> Other provider hooks (OpenAI, Anthropic) exist in `llm_providers.py` for future tuning but are not currently optimised or tested.

### Specifying Model
```bash
# Recommended: Gemini 3 Flash (uses fallback for SoA automatically)
python main_v3.py protocol.pdf --model gemini-3-flash

# Alternative: Gemini 2.5 Pro
python main_v3.py protocol.pdf --model gemini-2.5-pro

# Claude Opus 4.5 (high accuracy)
python main_v3.py protocol.pdf --model claude-opus-4-5

# Full extraction with SAP and sites
python main_v3.py protocol.pdf --complete --sap sap.pdf --sites sites.csv --model gemini-3-flash
```

### LLM Task Configuration (`llm_config.yaml`)

The pipeline uses task-optimized LLM parameters defined in `llm_config.yaml`. This file controls temperature, top_p, top_k, and max_tokens for different extraction categories.

#### Task Categories

| Category | Temperature | Use Case |
|----------|-------------|----------|
| `deterministic` | 0.0 | Factual extraction (SoA, metadata, eligibility) |
| `semantic` | 0.1 | Entity resolution, footnote conditions |
| `structured_gen` | 0.2 | State machines, endpoint algorithms |
| `narrative` | 0.3 | Amendments, narrative sections |

#### Environment Variable Overrides

Override any parameter at runtime without editing the config file:

```bash
# Override temperature for all tasks
LLM_TEMPERATURE=0.1 python main_v3.py protocol.pdf

# Override multiple parameters
LLM_TEMPERATURE=0.2 LLM_TOP_P=0.9 LLM_MAX_TOKENS=16384 python main_v3.py protocol.pdf
```

| Variable | Description | Example |
|----------|-------------|---------|
| `LLM_TEMPERATURE` | Sampling temperature (0.0-2.0) | `0.1` |
| `LLM_TOP_P` | Nucleus sampling threshold | `0.9` |
| `LLM_TOP_K` | Top-K sampling (Gemini/Claude only) | `40` |
| `LLM_MAX_TOKENS` | Maximum output tokens | `8192` |
| `LLM_CONFIG_PATH` | Path to alternative config file | `./custom_config.yaml` |

#### Provider-Specific Behavior

The config includes optimized settings per provider:
- **Gemini**: Supports top_k for fine-grained control
- **OpenAI**: top_k not supported, uses stricter top_p
- **Claude**: Cannot use temperature + top_p together

#### Customizing Parameters

Edit `llm_config.yaml` to tune extraction behavior:

```yaml
# Example: Make eligibility extraction more deterministic
extractor_mapping:
  eligibility: deterministic  # Uses temperature=0.0

# Example: Add provider override
provider_overrides:
  gemini:
    deterministic:
      top_k: 60  # Increase diversity
```

---

## Troubleshooting

### API Key Errors
```
Error: GOOGLE_API_KEY environment variable not set
```
**Solution:** Check `.env` file exists and has correct keys. Restart terminal.

### Missing Visits
**Symptom:** Not all visits from protocol appear in output

**Check:**
1. View `4_header_structure.json` - correct timepoints found?
2. View `3_soa_images/` - correct pages extracted?
3. Try specifying pages: `--pages 10,11,12`

### Parse Errors
**Symptom:** Pipeline fails during extraction

**Solutions:**
1. Try different model: `--model gemini-3-flash` or `--model gemini-2.5-pro`
2. Enable verbose: `--verbose`
3. Check API quota/limits

### Schema Validation Errors
**Symptom:** `schema_validation.json` shows issues

**Note:** Most issues are auto-fixed during post-processing. Review the specific errors in the JSON file.

### Vision Validation Issues
**Symptom:** Many cells marked orange (needs review)

**Causes:**
- Low quality PDF scans
- Complex table layouts
- Unusual tick marks

**Solutions:**
1. Skip validation: `--no-validate`
2. Review in Web UI (`cd web-ui && npm run dev`)
3. Check source PDF quality

---

## Testing

### Unit Tests

```bash
# Run all unit tests (1136 collected, ~3 min)
python -m pytest tests/ -v

# Run with coverage report
python -m pytest tests/ --cov --cov-report=term-missing

# Run specific test modules
python -m pytest tests/test_extractors.py -v       # Mocked LLM extractor tests
python -m pytest tests/test_composers.py -v        # M11 composer tests
python -m pytest tests/test_pipeline_context.py -v  # PipelineContext tests
python -m pytest tests/test_async_llm.py -v         # Async LLM tests
python -m pytest tests/test_llm_streaming.py -v     # LLM streaming tests
python -m pytest tests/test_m11_regression.py -v    # M11 renderer tests
```

### E2E Integration Tests

```bash
# Requires recent pipeline output (reuses if <1h old)
python -m pytest tests/test_e2e_pipeline.py --run-e2e -v
```

### Benchmarking

```bash
python testing/benchmark.py <golden.json> <extracted_dir/> [--verbose]
```

---

## FAQ

**Q: Which model should I use?**
A: Start with `gemini-3-flash` (recommended). If it fails, try `gemini-2.5-pro` or `claude-opus-4-5`.

**Q: How long does extraction take?**
A: 2-5 minutes for typical protocols, depending on model and protocol size.

**Q: Can I run offline?**
A: No, API calls to OpenAI or Google are required.

**Q: What if extraction quality is poor?**
A: 
1. Try a different model
2. Check PDF quality (text-based vs scanned)
3. Verify correct pages were identified
4. Review in Web UI (`cd web-ui && npm run dev`)

**Q: How do I report issues?**
A: Check logs in `output/<protocol>/`, capture error messages, report to maintainer.

---

**Last Updated:** 2026-02-17  
**Version:** 7.17
