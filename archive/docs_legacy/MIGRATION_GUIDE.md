# Protocol2USDM Migration Guide

## Overview

The Protocol2USDM codebase has been refactored from a complex multi-step pipeline with reconciliation to a simplified modular architecture. This guide helps you migrate from the legacy pipeline to the new one.

## Architecture Comparison

### Legacy Pipeline (main.py)
```
PDF → Find Pages → Vision Extract → Text Extract → Reconcile → Postprocess → Output
                         ↓                ↓              ↓
                    Full SoA data    Full SoA data  Complex merge logic
```

**Problems:**
- Two parallel extractions requiring reconciliation
- Complex anti-smear and fuzzy matching logic
- ID mismatches between Vision and Text
- Many workaround scripts accumulated

### New Pipeline (main_v2.py)
```
PDF → Find Pages → Vision (Structure) → Text (Data) → Validate → Output
                         ↓                   ↓            ↓
                   HeaderStructure     Uses Header IDs   Confirms ticks
                   (epochs, visits)    (activities, ticks)
```

**Benefits:**
- Vision provides STRUCTURE, not data
- Text uses structure as anchor (consistent IDs)
- Simple validation replaces complex reconciliation
- Cleaner, more maintainable code

## Migration Steps

### 1. Switch Entry Point

```bash
# Before (legacy)
python main.py protocol.pdf

# After (new)
python main_v2.py protocol.pdf --model gemini-2.5-pro --pages 52,53,54
```

### 2. Update Script Imports

If you have custom scripts that import from legacy modules:

```python
# Before
from reconcile_soa_llm import reconcile_soa
from vision_extract_soa import extract_soa_vision
from soa_postprocess_consolidated import postprocess_usdm

# After
from extraction import run_extraction_pipeline, PipelineConfig
from processing import normalize_names_vs_timing, ensure_required_fields
from core import USDM_VERSION, standardize_ids
```

### 3. Use New Modules

| Old Module | New Module | Purpose |
|------------|------------|---------|
| `vision_extract_soa.py` | `extraction/header_analyzer.py` | Structure only |
| `send_pdf_to_llm.py` | `extraction/text_extractor.py` | Data extraction |
| `reconcile_soa_llm.py` | `extraction/validator.py` | Validation (not reconciliation) |
| `find_soa_pages.py` | `extraction/soa_finder.py` | Page detection |
| Various fixes | `processing/normalizer.py` | Normalization |
| Scattered constants | `core/constants.py` | Centralized |
| Scattered JSON utils | `core/json_utils.py` | Consolidated |

### 4. Programmatic Usage

```python
from extraction import run_from_files, PipelineConfig

# Configure pipeline
config = PipelineConfig(
    model_name="gemini-2.5-pro",
    validate_with_vision=True,
    remove_hallucinations=True,
)

# Run extraction
result = run_from_files(
    pdf_path="protocol.pdf",
    output_dir="output/study_name",
    soa_pages=[52, 53, 54],  # Optional: auto-detected if not provided
    config=config,
)

# Check results
if result.success:
    print(f"Extracted {result.activities_count} activities")
    print(f"Output: {result.output_path}")
```

## Module Structure

```
Protcol2USDMv3/
├── core/                    # Consolidated utilities
│   ├── constants.py         # USDM_VERSION, SYSTEM_NAME, etc.
│   ├── json_utils.py        # JSON parsing, standardize_ids
│   ├── llm_client.py        # Unified LLM client
│   ├── provenance.py        # Provenance tracking
│   └── usdm_types.py        # Typed dataclasses
│
├── extraction/              # Clean pipeline
│   ├── soa_finder.py        # Find SoA pages
│   ├── header_analyzer.py   # Vision → Structure
│   ├── text_extractor.py    # Text → Data
│   ├── validator.py         # Vision validates text
│   └── pipeline.py          # Orchestrator
│
├── processing/              # Normalization
│   ├── normalizer.py        # Name/timing normalization
│   └── enricher.py          # Required fields, codes
│
├── main_v2.py               # New entry point
├── main.py                  # Legacy (deprecated)
└── archive/                 # Deprecated scripts
```

## Deprecated Files

The following files are marked as deprecated and will be removed in a future version:

| File | Replacement | Status |
|------|-------------|--------|
| `main.py` | `main_v2.py` | Deprecated |
| `reconcile_soa_llm.py` | `extraction/validator.py` | Deprecated |
| `vision_extract_soa.py` | `extraction/header_analyzer.py` | Deprecated |
| `fix_*.py` scripts | Archived | Moved to `archive/` |

## FAQ

### Q: Can I still use the legacy pipeline?
A: Yes, `main.py` still works but is deprecated. New features will only be added to `main_v2.py`.

### Q: What happened to reconciliation?
A: It's replaced by simple validation. Since Vision now only extracts structure and Text uses those IDs, there's nothing to reconcile.

### Q: Do I need to update my prompts?
A: The new modules have updated prompts built in. Custom prompts in `prompts/` still work.

### Q: How do I view the output?
A: `streamlit run soa_streamlit_viewer.py -- output/study/9_final_soa.json`

---

*Last updated: November 2025*
