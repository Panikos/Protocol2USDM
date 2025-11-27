# Protocol2USDM User Guide

**Version:** 6.0  
**Last Updated:** 2025-11-27

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

# Configure API keys
echo "OPENAI_API_KEY=sk-..." > .env
echo "GOOGLE_API_KEY=AIza..." >> .env

# Run
python main_v2.py input/your_protocol.pdf

# View results
streamlit run soa_streamlit_viewer.py
```

**Expected runtime:** 2-5 minutes per protocol

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
# OpenAI (for GPT models)
OPENAI_API_KEY=sk-proj-...

# Google AI (for Gemini models)
GOOGLE_API_KEY=AIzaSy...

# CDISC API (for conformance validation)
CDISC_API_KEY=...
```

**Get API keys:**
- OpenAI: https://platform.openai.com/api-keys
- Google AI: https://makersuite.google.com/app/apikey
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
python main_v2.py <protocol.pdf>
```

### With Options
```bash
python main_v2.py protocol.pdf --model gpt-5.1      # Specify model
python main_v2.py protocol.pdf --full               # Run all post-processing
python main_v2.py protocol.pdf --view               # Open viewer after
python main_v2.py protocol.pdf --no-validate        # Skip vision validation
python main_v2.py protocol.pdf --verbose            # Detailed logging
```

### Pipeline Steps

The pipeline automatically executes:

1. **Find SoA Pages** - Identifies pages containing Schedule of Activities
2. **Extract Images** - Renders SoA pages as images
3. **Analyze Structure** - Uses vision to understand table headers
4. **Extract Data** - Extracts activities and timepoints from text
5. **Validate** - Vision model validates extraction against images
6. **Build Output** - Creates USDM-compliant JSON

### Post-Processing (Optional)

```bash
# Add all post-processing
python main_v2.py protocol.pdf --full

# Or individually:
--enrich            # Step 7: Add NCI terminology codes
--validate-schema   # Step 8: Validate against USDM schema
--conformance       # Step 9: Run CDISC CORE conformance
```

---

## Full Protocol Extraction

Extract everything from a protocol with a single command:

```bash
# Full protocol extraction (SoA + all expansion phases)
python main_v2.py protocol.pdf --full-protocol
```

### Selective Extraction

Run specific phases alongside SoA:

```bash
# SoA + metadata + eligibility
python main_v2.py protocol.pdf --metadata --eligibility

# SoA + objectives + interventions
python main_v2.py protocol.pdf --objectives --interventions
```

### Expansion-Only Mode

Skip SoA extraction and run only expansion phases:

```bash
# All expansion phases, no SoA
python main_v2.py protocol.pdf --expansion-only --metadata --eligibility --objectives --studydesign --interventions --narrative --advanced

# Just metadata and eligibility
python main_v2.py protocol.pdf --expansion-only --metadata --eligibility
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

### Combined Output

When running multiple phases, a combined `full_usdm.json` is generated containing all extracted data in a single USDM-compliant structure.

---

## Standalone Extractors

For individual phase extraction without the main pipeline:

### Study Metadata (Phase 2)
Extracts study identity from title page and synopsis.
```bash
python extract_metadata.py protocol.pdf
```
**Entities:** `StudyTitle`, `StudyIdentifier`, `Organization`, `StudyRole`, `Indication`

### Eligibility Criteria (Phase 1)
Extracts inclusion and exclusion criteria.
```bash
python extract_eligibility.py protocol.pdf
```
**Entities:** `EligibilityCriterion`, `EligibilityCriterionItem`, `StudyDesignPopulation`

### Objectives & Endpoints (Phase 3)
Extracts primary, secondary, exploratory objectives with linked endpoints.
```bash
python extract_objectives.py protocol.pdf
```
**Entities:** `Objective`, `Endpoint`, `Estimand`, `IntercurrentEvent`

### Study Design Structure (Phase 4)
Extracts design type, blinding, randomization, arms, cohorts.
```bash
python extract_studydesign.py protocol.pdf
```
**Entities:** `InterventionalStudyDesign`, `StudyArm`, `StudyCell`, `StudyCohort`

### Interventions & Products (Phase 5)
Extracts investigational products, dosing regimens, substances.
```bash
python extract_interventions.py protocol.pdf
```
**Entities:** `StudyIntervention`, `AdministrableProduct`, `Administration`, `Substance`

### Narrative Structure (Phase 7)
Extracts document structure, sections, and abbreviations.
```bash
python extract_narrative.py protocol.pdf
```
**Entities:** `NarrativeContent`, `Abbreviation`, `StudyDefinitionDocument`

### Advanced Entities (Phase 8)
Extracts amendments, geographic scope, and study sites.
```bash
python extract_advanced.py protocol.pdf
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
├── step8_schema_validation.json  # Schema validation results
└── conformance_report.json       # CORE conformance report
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
  "cells": {
    "act_1|pt_1": "both",   // Activity-timepoint confirmed
    "act_1|pt_2": "text"    // Text only (not vision-confirmed)
  }
}
```

---

## Using the Viewer

### Launch
```bash
streamlit run soa_streamlit_viewer.py
```

Opens at: http://localhost:8504

### Viewer Features

**1. Protocol Run Selection**
- Dropdown to select from all pipeline runs
- Shows run timestamp and protocol name

**2. SoA Table Display**
- Color-coded cells by provenance:
  - 🟦 Blue: Text extraction only
  - 🟩 Green: Vision confirmed
  - 🟧 Orange: Needs review
- Epoch groupings with colspan merge
- Activity groupings by category

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
python main_v2.py protocol.pdf --enrich
```

### Step 8: Schema Validation
Validates against USDM v4.0 schema:
```bash
python main_v2.py protocol.pdf --validate-schema
```

### Step 9: CDISC CORE Conformance
Runs CORE rules validation:
```bash
python main_v2.py protocol.pdf --conformance
```

**Note:** Requires CORE engine installed via `tools/core/download_core.py`

---

## Model Selection

### Supported Models

| Model | Provider | Speed | Best For |
|-------|----------|-------|----------|
| `gpt-5.1` | OpenAI | Medium | **Default - Best reliability** |
| `gemini-3-pro-preview` | Google | Slow | Thorough extraction |
| `gemini-2.5-pro` | Google | Fast | Good balance |
| `gpt-4o` | OpenAI | Medium | OpenAI preference |

### Benchmark Results

| Model | Success Rate | Avg Time |
|-------|-------------|----------|
| GPT-5.1 | 100% | 92s |
| Gemini-3-pro-preview | 75% | 400s |

### Specifying Model
```bash
python main_v2.py protocol.pdf --model gpt-5.1
python main_v2.py protocol.pdf --model gemini-3-pro-preview
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
1. Try different model: `--model gemini-2.5-pro`
2. Enable verbose: `--verbose`
3. Check API quota/limits

### Schema Validation Errors
**Symptom:** `step8_schema_validation.json` shows issues

**Note:** Most issues are auto-fixed during post-processing. Review the specific errors in the JSON file.

### Vision Validation Issues
**Symptom:** Many cells marked orange (needs review)

**Causes:**
- Low quality PDF scans
- Complex table layouts
- Unusual tick marks

**Solutions:**
1. Skip validation: `--no-validate`
2. Review in Streamlit viewer
3. Check source PDF quality

---

## Step-by-Step Testing

For debugging, run individual steps:

```bash
python test_pipeline_steps.py protocol.pdf --step 3   # Header analysis
python test_pipeline_steps.py protocol.pdf --step 4   # Text extraction
python test_pipeline_steps.py protocol.pdf --step 5   # Vision validation
python test_pipeline_steps.py protocol.pdf --step 6   # Build output
python test_pipeline_steps.py protocol.pdf --step all # All steps
```

---

## FAQ

**Q: Which model should I use?**
A: Start with `gpt-5.1` (default). If it fails, try `gemini-2.5-pro`.

**Q: How long does extraction take?**
A: 2-5 minutes for typical protocols, depending on model and protocol size.

**Q: Can I run offline?**
A: No, API calls to OpenAI or Google are required.

**Q: What if extraction quality is poor?**
A: 
1. Try a different model
2. Check PDF quality (text-based vs scanned)
3. Verify correct pages were identified
4. Review in Streamlit viewer

**Q: How do I report issues?**
A: Check logs in `output/<protocol>/`, capture error messages, report to maintainer.

---

**Last Updated:** 2025-11-26
