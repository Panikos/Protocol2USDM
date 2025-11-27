# Protocol2USDM Quick Reference

**v6.0** | One-page command reference

---

## Quick Start

```bash
pip install -r requirements.txt
echo "OPENAI_API_KEY=sk-..." > .env
python main_v2.py input/protocol.pdf
streamlit run soa_streamlit_viewer.py
```

---

## Common Commands

### SoA Pipeline
```bash
python main_v2.py protocol.pdf                      # Default extraction
python main_v2.py protocol.pdf --model gemini-2.5-pro
python main_v2.py protocol.pdf --full               # With post-processing
```

### Standalone Extractors (v6.0)
```bash
# Study Metadata (title, identifiers, sponsor)
python extract_metadata.py protocol.pdf

# Eligibility Criteria (inclusion/exclusion)
python extract_eligibility.py protocol.pdf

# Objectives & Endpoints
python extract_objectives.py protocol.pdf

# Study Design (arms, cohorts, blinding)
python extract_studydesign.py protocol.pdf

# Interventions & Products
python extract_interventions.py protocol.pdf
```

### View Results
```bash
streamlit run soa_streamlit_viewer.py
```

### Options
```bash
--model, -m         Model to use (default: gpt-5.1)
--output-dir, -o    Output directory
--pages, -p         Specific SoA pages (comma-separated)
--no-validate       Skip vision validation
--view              Launch viewer after
--verbose, -v       Detailed logging
--full              Run all post-processing steps
--enrich            Step 7: NCI terminology
--validate-schema   Step 8: Schema validation
--conformance       Step 9: CORE conformance
```

---

## Models

| Model | Speed | Reliability |
|-------|-------|-------------|
| **gpt-5.1** ⭐ | Medium | Best (100%) |
| gemini-3-pro-preview | Slow | 75% |
| gemini-2.5-pro | Fast | Good |
| gpt-4o | Medium | Good |

---

## Output Files

```
output/<protocol>/
├── 2_study_metadata.json          # Study identity (Phase 2)
├── 3_eligibility_criteria.json    # I/E criteria (Phase 1)
├── 4_objectives_endpoints.json    # Objectives (Phase 3)
├── 5_study_design.json            # Design structure (Phase 4)
├── 6_interventions.json           # Products (Phase 5)
├── 4_header_structure.json        # SoA table structure
├── 6_validation_result.json       # SoA validation details
├── 9_final_soa.json              ⭐ Main SoA output
├── 9_final_soa_provenance.json    # Source tracking
└── conformance_report.json        # CORE results
```

---

## Provenance Colors (Viewer)

| Color | Meaning |
|-------|---------|
| 🟦 Blue | Text extraction only |
| 🟩 Green | Vision confirmed |
| 🟧 Orange | Needs review |

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
| `main_v2.py` | SoA extraction pipeline |
| `extract_metadata.py` | Study metadata extraction |
| `extract_eligibility.py` | I/E criteria extraction |
| `extract_objectives.py` | Objectives extraction |
| `extract_studydesign.py` | Study design extraction |
| `extract_interventions.py` | Interventions extraction |
| `soa_streamlit_viewer.py` | Interactive viewer |
| `test_pipeline_steps.py` | Step-by-step testing |
| `extraction/` | Core extraction modules |

---

**Docs:** [README.md](README.md) | [USER_GUIDE.md](USER_GUIDE.md) | [USDM_EXPANSION_PLAN.md](USDM_EXPANSION_PLAN.md)

**Last Updated:** 2025-11-27
