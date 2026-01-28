# Protocol2USDM Project Cleanup Plan

**Date:** January 28, 2026  
**Purpose:** Reorganize project structure, archive obsolete files, and update documentation

---

## Executive Summary

After thorough review of the project structure, the following cleanup actions are proposed:

| Category | Files | Action |
|----------|-------|--------|
| Empty debug scripts | 17 | Delete (0 bytes, no content) |
| Obsolete root docs | 5 | Move to archive/docs_legacy |
| Technical docs at root | 2 | Move to docs/ |
| Root test scripts | 3 | Move to tests/ |
| Debug/check scripts | 6 | Move to scripts/debug/ |
| Standalone extractors | 8 | Move to scripts/extractors/ |
| Documentation updates | 3 | Update content |

---

## 1. EMPTY FILES TO DELETE

These files are 0 bytes and contain no code:

```
check_dups.py (0 bytes)
check_epochs.py (0 bytes)
check_fields.py (0 bytes)
check_instance_names.py (0 bytes)
check_interventions.py (0 bytes)
check_missing_enc.py (0 bytes)
check_new_run.py (0 bytes)
check_orphan_instances.py (0 bytes)
check_orphans.py (0 bytes)
compare_interventions.py (0 bytes)
debug_categories.py (0 bytes)
debug_enc13.py (0 bytes)
debug_epoch_ids.py (0 bytes)
debug_orphans.py (0 bytes)
debug_provenance.py (0 bytes)
test_epoch_reconciler.py (0 bytes)
trace_encounter_ids.py (0 bytes)
verify_epoch_fix.py (0 bytes)
verify_fixes.py (0 bytes)
verify_referential_integrity.py (0 bytes)
```

---

## 2. OBSOLETE DOCUMENTATION → archive/docs_legacy/

| File | Reason | Action |
|------|--------|--------|
| `BRANCH_COMMIT_MESSAGE.md` | One-time commit message, no longer needed | Archive |
| `FILE_AUDIT.md` | Historical audit from v6.6.0, outdated | Archive |
| `INTEGRITY_ANALYSIS_REPORT.md` | One-time analysis report | Archive |
| `USDM_COVERAGE_STATUS.md` | Outdated (v6.5.0), info now in README | Archive |
| `parameter_tuning_report.md` | Historical tuning report | Archive |

---

## 3. TECHNICAL DOCUMENTATION → docs/

| File | Current Location | New Location |
|------|------------------|--------------|
| `web-ui/docs/IMPLEMENTATION_PLAN.md` | web-ui/docs/ | docs/web-ui/ |
| `web-ui/docs/UI_GAP_ANALYSIS.md` | web-ui/docs/ | docs/web-ui/ |

---

## 4. TEST SCRIPTS → tests/

| File | Current Location | New Location |
|------|------------------|--------------|
| `test_header_claude.py` | root | tests/ |
| `test_reconciliation_framework.py` | root | tests/ |

---

## 5. DEBUG/CHECK SCRIPTS → scripts/debug/

| File | Size | Action |
|------|------|--------|
| `check_groups.py` | 4915 bytes | Move to scripts/debug/ |
| `compare_outputs.py` | 2068 bytes | Move to scripts/debug/ |
| `debug_footnotes.py` | 3174 bytes | Move to scripts/debug/ |
| `debug_issues.py` | 1916 bytes | Move to scripts/debug/ |
| `debug_proc_diff.py` | 1009 bytes | Move to scripts/debug/ |

---

## 6. STANDALONE EXTRACTORS → scripts/extractors/

These are CLI wrappers for individual extraction modules. Move to scripts/extractors/:

| File | Size |
|------|------|
| `extract_advanced.py` | 4220 bytes |
| `extract_eligibility.py` | 6184 bytes |
| `extract_execution_model.py` | 10265 bytes |
| `extract_interventions.py` | 4238 bytes |
| `extract_metadata.py` | 5371 bytes |
| `extract_narrative.py` | 4442 bytes |
| `extract_objectives.py` | 6374 bytes |
| `extract_studydesign.py` | 6096 bytes |

---

## 7. DOCUMENTATION UPDATES NEEDED

### 7.1 README.md Updates

| Section | Issue | Fix |
|---------|-------|-----|
| Version | Shows "v6.6.0" in extraction table | Update to current version |
| Viewer command | References `streamlit run` (obsolete) | Update to `npm run dev` |
| Project Structure | Missing execution/ module | Add execution module |
| Model recommendations | GPT-5.1 listed as "not working well" | Clarify current model status |

### 7.2 QUICK_REFERENCE.md Updates

| Section | Issue | Fix |
|---------|-------|-----|
| Version | Shows "v6.6.0" | Update to current |
| View Results | Shows `streamlit run soa_streamlit_viewer.py` | Update to web-ui |
| Models table | Shows GPT-5.1 as "Best (100%)" | Update with current benchmarks |
| Key Files | Lists `soa_streamlit_viewer.py` | Remove, add web-ui reference |
| Standalone CLI Tools | Lists root-level extract_*.py | Update paths after move |

### 7.3 USER_GUIDE.md Updates

| Section | Issue | Fix |
|---------|-------|-----|
| Version | Shows "v6.9.0" | Verify current version |
| Clone URL | Shows "Protcol2USDMv3" (typo in original) | Keep as-is (matches repo) |

---

## 8. PROPOSED FINAL STRUCTURE

```
Protocol2USDMv3/
├── main_v2.py                    # Main pipeline entry point
├── llm_providers.py              # LLM provider interface
├── llm_config.yaml               # LLM configuration
├── requirements.txt              # Python dependencies
├── .env                          # API keys (gitignored)
│
├── README.md                     # Project overview (UPDATED)
├── USER_GUIDE.md                 # Detailed usage guide (UPDATED)
├── QUICK_REFERENCE.md            # Command reference (UPDATED)
├── CHANGELOG.md                  # Version history
│
├── core/                         # Core modules
├── extraction/                   # Extraction modules (including execution/)
├── enrichment/                   # Terminology enrichment
├── validation/                   # Validation modules
│
├── scripts/                      # Utility scripts
│   ├── extractors/               # Standalone CLI extractors
│   ├── debug/                    # Debug/check scripts
│   ├── analyze_issues.py
│   ├── optimize_llm_params.py
│   └── run_all_trials.py
│
├── tests/                        # All test files
│   ├── test_*.py
│   └── test_data/
│
├── testing/                      # Benchmarking & integration
│   ├── benchmark.py
│   └── test_pipeline_steps.py
│
├── tools/                        # External tools
│   ├── cdisc-rules-engine/
│   ├── download_trials*.py
│   └── verify_trials.py
│
├── docs/                         # All documentation
│   ├── ARCHITECTURE.md
│   ├── EXECUTION_MODEL_ARCHITECTURE.md
│   ├── EXECUTION_MODEL_FIXES.md
│   ├── TIMELINE_REVIEW_GUIDE.md
│   ├── ALEXION_FEEDBACK_ANALYSIS.md
│   ├── architecture/
│   └── web-ui/                   # Web UI docs (NEW)
│       ├── IMPLEMENTATION_PLAN.md
│       └── UI_GAP_ANALYSIS.md
│
├── web-ui/                       # React/Next.js application
│
├── archive/                      # Archived files
│   ├── docs_legacy/              # Old documentation
│   ├── legacy_pipeline/          # Old pipeline scripts
│   ├── optimization/             # Old optimization experiments
│   └── tests_legacy/             # Old test files
│
├── input/                        # Input protocols
├── output/                       # Pipeline outputs
└── test_data/                    # Test fixtures
```

---

## 9. EXECUTION ORDER

1. Delete empty files (20 files)
2. Move obsolete docs to archive/docs_legacy/ (5 files)
3. Move web-ui docs to docs/web-ui/ (2 files)
4. Move test scripts to tests/ (2 files)
5. Create scripts/debug/ and move debug scripts (5 files)
6. Create scripts/extractors/ and move extractors (8 files)
7. Update README.md
8. Update QUICK_REFERENCE.md
9. Update USER_GUIDE.md
10. Update archive/README.md
11. Delete this plan file (or archive it)
12. Commit all changes

---

**Awaiting approval to proceed.**
