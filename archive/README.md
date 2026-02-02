# Archive Directory

This directory contains files that are no longer part of the active pipeline but are kept for reference.

## Directory Structure

```
archive/
├── legacy_pipeline/       # Old multi-step pipeline scripts
├── optimization/          # Prompt optimization experiments
├── tests_legacy/          # Old test files
├── docs_legacy/           # Outdated documentation
├── fix_*.py               # Workaround scripts
└── README.md              # This file
```

## Archived Components

### Legacy Pipeline (`legacy_pipeline/`)

These scripts implemented the old multi-step pipeline with complex reconciliation:

| File | Original Purpose | Replaced By |
|------|------------------|-------------|
| `main.py` | Old entry point | `main_v2.py` |
| `reconcile_soa_llm.py` | Merge text + vision | `extraction/validator.py` |
| `vision_extract_soa.py` | Full SoA from images | `extraction/header_analyzer.py` |
| `send_pdf_to_llm.py` | Text extraction | `extraction/text_extractor.py` |
| `soa_postprocess_consolidated.py` | Heavy post-processing | `processing/` module |
| `find_soa_pages.py` | Page detection | `extraction/soa_finder.py` |
| `analyze_soa_structure.py` | Structure analysis | `extraction/header_analyzer.py` |
| `generate_soa_llm_prompt.py` | Prompt generation | Built into extractors |
| `map_epochs_encounters_llm.py` | Epoch/encounter mapping | Built into header analyzer |

### Optimization Scripts (`optimization/`)

Experimental prompt optimization tools:

| File | Purpose |
|------|---------|
| `benchmark_prompts.py` | Prompt benchmarking |
| `optimize_all_prompts.py` | Batch optimization |
| `prompt_optimizer.py` | Optimization logic |
| `compare_benchmark_results.py` | Results comparison |

### Legacy Tests (`tests_legacy/`)

Old test files that may need updating:

| File | Purpose |
|------|---------|
| `test_optimizer.py` | Tests for prompt optimizer |
| `validate_soa_structure.py` | Structure validation |
| `validate_usdm_schema.py` | Schema validation |

### Workaround Scripts (root of archive/)

| File | Original Purpose | Replaced By |
|------|------------------|-------------|
| `fix_provenance_keys.py` | Align provenance IDs | Consistent ID generation |
| `fix_reconciled_soa.py` | Fix reconciliation bugs | Eliminated reconciliation |
| `apply_clinical_corrections.py` | Manual hallucination fixes | Better prompts + validation |
| `align_structure.py` | Restructure USDM output | Correct structure from start |
| `regenerate_instances.py` | Transform flat timeline | Correct structure from start |
| `audit_timepoints.py` | Debug timepoint issues | Integrated into validation |

### Documentation (`docs_legacy/`)

Outdated documentation files:

| File | Original Purpose | Status |
|------|------------------|--------|
| `MIGRATION_GUIDE.md` | Migration from main.py | Archived (main.py deprecated) |
| `USDM_EXPANSION_PLAN.md` | Original expansion plan | Historical reference |
| `BRANCH_COMMIT_MESSAGE.md` | v7.0 commit message | Archived 2026-01-28 |
| `FILE_AUDIT.md` | v6.6.0 file audit | Archived 2026-01-28 |
| `INTEGRITY_ANALYSIS_REPORT.md` | One-time integrity analysis | Archived 2026-01-28 |
| `USDM_COVERAGE_STATUS.md` | v6.5.0 coverage status | Archived 2026-01-28 |
| `parameter_tuning_report.md` | LLM parameter tuning | Archived 2026-01-28 |
| Various *.md | Old design docs | Historical reference only |

---

## Recovery

If you need to restore any of these files:
1. Copy from this directory back to root
2. Or recover from git history

## Current Architecture

See main project documentation:
- `README.md` - Project overview
- `USER_GUIDE.md` - Detailed usage guide
- `QUICK_REFERENCE.md` - Command reference
- `docs/ARCHITECTURE.md` - System architecture

---

**Last Updated:** 2026-01-28
