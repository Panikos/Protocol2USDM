# Protocol2USDM File Audit

**Date**: 2026-01-02
**Version**: 6.6.0
**Status**: USDM PLACEMENT COMPLIANCE

## Changes Made (2026-01-02) - v6.6.0

### USDM Entity Placement Compliance

All entities now placed at correct USDM locations per `dataStructure.yml`:

| Entity | Before | After |
|--------|--------|-------|
| `eligibilityCriterionItems` | `studyDesign` | `studyVersion` |
| `organizations` | `study` | `studyVersion` |
| `narrativeContentItems` | root | `studyVersion` |
| `studyInterventions` | `studyDesign` | `studyVersion` |
| `administrableProducts` | root | `studyVersion` |
| `medicalDevices` | root | `studyVersion` |
| `timings` | root | `scheduleTimeline` |
| `exits` | root | `scheduleTimeline` |
| `conditions` | root | `studyVersion` |
| `procedures` | root | `activity.definedProcedures` |
| `indications` | `study` | `studyDesign` |
| `analysisPopulations` | root | `studyDesign` |

### Files Modified
- `main_v2.py` - Entity placement logic
- `web-ui/components/protocol/*.tsx` - UI component data paths
- All documentation files updated

---

## Changes Made (2025-11-29) - v6.3.0

### Archived to `archive/orphaned_cleanup/`
- `p2u_constants.py` - Backward compat wrapper, never imported
- `pipeline/` - Alternative pipeline module, superseded by main_v2.py
- `processing/` - enricher.py, normalizer.py - not used
- `usdm_renderer.html` - HTML renderer, not referenced
- `extract_full_usdm.py` - Superseded by main_v2.py --full-protocol

### New Features Added
- `core/provenance.py` - ProvenanceTracker for extraction source tracking
- Idempotent UUID generation in `USDMEntity._ensure_id()`
- `sync_provenance_with_data()` in main_v2.py for ID matching

---

## Changes Made (2025-11-29) - v6.2.0

### Deleted
- `Protocol2USDM Review.pdf` - Obsolete
- `debug_provenance.py` - Debug utility no longer needed
- `archive/logs/*` - 201 old log files

### New Directories Created
- `testing/` - Testing and benchmarking scripts
- `utilities/` - Setup and utility scripts

### Files Moved to `testing/`
- `benchmark_models.py`
- `compare_golden_vs_extracted.py`
- `test_pipeline_steps.py`
- `test_golden_comparison.py`

### Files Moved to `utilities/`
- `setup_google_cloud.ps1`

### Files Archived to `archive/legacy_pipeline/`
- `json_utils.py` (root) - Duplicate of core/json_utils.py
- `soa_prompt_example.json` - Old prompt example
- `usdm_examples.py` - Reference examples (can restore if needed)

### Files Archived to `archive/prompts_legacy/`
- `find_soa_pages.yaml` - Non-optimized version
- `soa_extraction.yaml` - Non-optimized version
- `soa_reconciliation.yaml` - Non-optimized version
- `vision_soa_extraction.yaml` - Non-optimized version

### Prompts Renamed (optimized → standard)
- `find_soa_pages_optimized.yaml` → `find_soa_pages.yaml`
- `soa_extraction_optimized.yaml` → `soa_extraction.yaml`
- `soa_reconciliation_optimized.yaml` → `soa_reconciliation.yaml`
- `vision_soa_extraction_optimized.yaml` → `vision_soa_extraction.yaml`

---

## Legend

| Status | Meaning |
|--------|---------|
| ✅ ACTIVE | In active use, current |
| ⚠️ REVIEW | Needs review/update |
| 🗑️ ARCHIVE | Should be archived |
| 📁 ARCHIVED | Already in archive |
| ❓ UNKNOWN | Needs investigation |

---

## Root Directory Files

### Documentation (Root)

| File | Size | Status | Notes |
|------|------|--------|-------|
| `README.md` | 14KB | ✅ ACTIVE | Updated for v6.3.0 |
| `CHANGELOG.md` | 31KB | ✅ ACTIVE | Updated for v6.3.0 |
| `USER_GUIDE.md` | 16KB | ⚠️ REVIEW | Check if reflects new architecture |
| `QUICK_REFERENCE.md` | 7KB | ✅ ACTIVE | Updated for v6.3.0 |
| `USDM_COVERAGE_STATUS.md` | 5KB | ✅ ACTIVE | Updated for v6.3.0 |
| `docs/ARCHITECTURE.md` | 10KB | ✅ ACTIVE | Schema-driven architecture docs |

### Main Pipeline Scripts

| File | Size | Status | Notes |
|------|------|--------|-------|
| `main_v2.py` | 66KB | ✅ ACTIVE | Main extraction pipeline |
| `soa_streamlit_viewer.py` | 104KB | ✅ ACTIVE | Viewer app |
| `extract_full_usdm.py` | - | 📁 ARCHIVED | Superseded by main_v2.py --full-protocol |

### Individual Extractors

| File | Size | Status | Notes |
|------|------|--------|-------|
| `extract_eligibility.py` | 6KB | ✅ ACTIVE | Phase 1 extractor |
| `extract_metadata.py` | 5KB | ✅ ACTIVE | Metadata extractor |
| `extract_objectives.py` | 6KB | ✅ ACTIVE | Objectives extractor |
| `extract_interventions.py` | 4KB | ✅ ACTIVE | Interventions extractor |
| `extract_studydesign.py` | 6KB | ✅ ACTIVE | Study design extractor |
| `extract_narrative.py` | 4KB | ✅ ACTIVE | Narrative extractor |
| `extract_advanced.py` | 4KB | ✅ ACTIVE | Advanced entities extractor |

### Testing & Benchmarking

| File | Size | Status | Notes |
|------|------|--------|-------|
| `test_pipeline_steps.py` | 61KB | ✅ ACTIVE | Pipeline step tests |
| `test_golden_comparison.py` | 53KB | ✅ ACTIVE | Golden standard comparison |
| `benchmark_models.py` | 12KB | ✅ ACTIVE | Model benchmarking |
| `compare_golden_vs_extracted.py` | 32KB | ⚠️ REVIEW | Duplicate of test_golden? |
| `debug_provenance.py` | 2KB | 🗑️ ARCHIVE | Debug utility, probably obsolete |

### Utilities (Root - Potentially Redundant)

| File | Size | Status | Notes |
|------|------|--------|-------|
| `json_utils.py` | 1KB | 🗑️ ARCHIVE | Duplicate? core/json_utils.py exists |
| `llm_providers.py` | 13KB | ⚠️ REVIEW | Is this used or replaced by core/llm_client? |
| `p2u_constants.py` | 0.4KB | ⚠️ REVIEW | Used? core/constants.py exists |
| `prompt_templates.py` | 14KB | ⚠️ REVIEW | Used or replaced by prompts/? |

### Other Root Files

| File | Size | Status | Notes |
|------|------|--------|-------|
| `soa_prompt_example.json` | 2KB | ⚠️ REVIEW | Used by old prompt generation? |
| `usdm_renderer.html` | 13KB | ⚠️ REVIEW | Is this used? |
| `setup_google_cloud.ps1` | 6KB | ✅ ACTIVE | Setup script |
| `requirements.txt` | 0.3KB | ✅ ACTIVE | Dependencies |

---

## core/ Directory

| File | Size | Status | Notes |
|------|------|--------|-------|
| `__init__.py` | 2KB | ✅ ACTIVE | Package init |
| `usdm_schema_loader.py` | 14KB | ✅ ACTIVE | NEW - Schema parser |
| `usdm_types_generated.py` | 45KB | ✅ ACTIVE | NEW - Official USDM types |
| `usdm_types.py` | 16KB | ✅ ACTIVE | UPDATED - Main interface |
| `schema_prompt_generator.py` | 14KB | ✅ ACTIVE | NEW - Prompt generator |
| `llm_client.py` | 10KB | ✅ ACTIVE | LLM client |
| `json_utils.py` | 10KB | ✅ ACTIVE | JSON utilities |
| `pdf_utils.py` | 4KB | ✅ ACTIVE | PDF utilities |
| `provenance.py` | 11KB | ✅ ACTIVE | Provenance tracking |
| `constants.py` | 1KB | ✅ ACTIVE | Constants |

---

## extraction/ Directory

### Main Extraction Files

| File | Size | Status | Notes |
|------|------|--------|-------|
| `__init__.py` | 5KB | ✅ ACTIVE | Package init |
| `header_analyzer.py` | 16KB | ✅ ACTIVE | Vision-based header extraction |
| `text_extractor.py` | 12KB | ✅ ACTIVE | Text-based extraction |
| `soa_finder.py` | 15KB | ✅ ACTIVE | SoA page finder |
| `pipeline.py` | 19KB | ✅ ACTIVE | Extraction pipeline |
| `validator.py` | 16KB | ✅ ACTIVE | Extraction validation |
| `confidence.py` | 11KB | ✅ ACTIVE | Confidence scoring |

### Extraction Submodules (*/schema.py updated)

| Module | Status | Notes |
|--------|--------|-------|
| `eligibility/` | ✅ ACTIVE | schema.py updated |
| `metadata/` | ✅ ACTIVE | schema.py updated |
| `objectives/` | ✅ ACTIVE | schema.py updated |
| `interventions/` | ✅ ACTIVE | schema.py updated |
| `studydesign/` | ✅ ACTIVE | schema.py updated |
| `scheduling/` | ✅ ACTIVE | schema.py updated |
| `narrative/` | ✅ ACTIVE | schema.py updated |
| `procedures/` | ✅ ACTIVE | schema.py updated |
| `amendments/` | ✅ ACTIVE | schema.py updated |
| `advanced/` | ✅ ACTIVE | schema.py updated |
| `document_structure/` | ✅ ACTIVE | schema.py updated |

---

## validation/ Directory

| File | Size | Status | Notes |
|------|------|--------|-------|
| `__init__.py` | 4KB | ✅ ACTIVE | Package init, exports validators |
| `usdm_validator.py` | 11KB | ✅ ACTIVE | Official USDM package validation |
| `llm_schema_fixer.py` | 46KB | ✅ ACTIVE | Schema fixer |
| `openapi_validator.py` | 24KB | ⚠️ REVIEW | Deprecated? Still used for issue detection |
| `schema_validator.py` | 6KB | ⚠️ REVIEW | Used or redundant with usdm_validator? |
| `usdm_examples.py` | 17KB | ⚠️ REVIEW | Used for reference examples |
| `cdisc_conformance.py` | 12KB | ⚠️ REVIEW | Is this used? |

---

## pipeline/ Directory

| File | Size | Status | Notes |
|------|------|--------|-------|
| `__init__.py` | 0.4KB | ✅ ACTIVE | Package init |
| `protocol_pipeline.py` | 31KB | ✅ ACTIVE | Protocol pipeline orchestration |

---

## prompts/ Directory

| File | Size | Status | Notes |
|------|------|--------|-------|
| `README.md` | 5KB | ⚠️ REVIEW | Check if current |
| `find_soa_pages.yaml` | 5KB | ⚠️ REVIEW | Duplicate of optimized? |
| `find_soa_pages_optimized.yaml` | 5KB | ✅ ACTIVE | Active prompt |
| `soa_extraction.yaml` | 7KB | ⚠️ REVIEW | Duplicate of optimized? |
| `soa_extraction_optimized.yaml` | 7KB | ✅ ACTIVE | Active prompt |
| `soa_reconciliation.yaml` | 8KB | ⚠️ REVIEW | Duplicate of optimized? |
| `soa_reconciliation_optimized.yaml` | 8KB | ✅ ACTIVE | Active prompt |
| `vision_soa_extraction.yaml` | 6KB | ⚠️ REVIEW | Duplicate of optimized? |
| `vision_soa_extraction_optimized.yaml` | 5KB | ✅ ACTIVE | Active prompt |

---

## tests/ Directory

| File | Size | Status | Notes |
|------|------|--------|-------|
| `test_core_modules.py` | 10KB | ✅ ACTIVE | Core module tests |
| `test_llm_providers.py` | 12KB | ✅ ACTIVE | LLM provider tests |
| `test_prompt_templates.py` | 12KB | ✅ ACTIVE | Prompt tests |
| `test_prompt_quality.py` | 13KB | ✅ ACTIVE | Prompt quality tests |
| `test_normalization.py` | 10KB | ✅ ACTIVE | Normalization tests |
| `test_json_extraction.py` | 4KB | ✅ ACTIVE | JSON extraction tests |
| `test_processing.py` | 7KB | ✅ ACTIVE | Processing tests |
| `test_viewer_load.py` | 3KB | ✅ ACTIVE | Viewer tests |
| `test_pipeline_api.py` | 2KB | ✅ ACTIVE | Pipeline API tests |
| `test_provenance_split.py` | 2KB | ✅ ACTIVE | Provenance tests |
| `test_batch_driver.py` | 1KB | ⚠️ REVIEW | Is this used? |
| `test_clean_llm_json.py` | 0.4KB | ⚠️ REVIEW | Is this used? |

---

## docs/ Directory

| File | Size | Status | Notes |
|------|------|--------|-------|
| `ARCHITECTURE.md` | 13KB | ✅ ACTIVE | NEW - Architecture docs |

---

## archive/ Directory (Already Archived)

### archive/legacy_pipeline/ (21 files)
📁 Contains old pipeline code, now archived:
- `usdm_types_v4.py` - Old manual types
- `soa_entity_mapping.json` - Old entity mapping
- `generate_soa_llm_prompt.py` - Old prompt generator
- Various other legacy scripts

### archive/docs_legacy/ (45 files)
📁 Contains old documentation

### archive/logs/ (201 files)
📁 Contains old log files - **Consider deleting**

### archive/optimization/ (9 files)
📁 Contains old optimization scripts

### archive/tests_legacy/ (6 files)
📁 Contains old tests

### archive/Visual_guide_SOA/ (4 files)
📁 Contains visual guides

### archive/ root files
| File | Status | Notes |
|------|--------|-------|
| `README.md` | 📁 ARCHIVED | Archive documentation |
| `align_structure.py` | 📁 ARCHIVED | Old alignment script |
| `apply_clinical_corrections.py` | 📁 ARCHIVED | Old corrections script |
| `audit_timepoints.py` | 📁 ARCHIVED | Old audit script |
| `fix_provenance_keys.py` | 📁 ARCHIVED | Old fix script |
| `fix_reconciled_soa.py` | 📁 ARCHIVED | Old fix script |
| `pipeline_api.py` | 📁 ARCHIVED | Old API |
| `regenerate_instances.py` | 📁 ARCHIVED | Old regeneration script |
| `validate_pipeline.py` | 📁 ARCHIVED | Old validation script |

---

## Other Directories

### useful_material/
| File | Status | Notes |
|------|--------|-------|
| `USDM_CT.xlsx` | ✅ ACTIVE | USDM controlled terminology |
| `evs_cache.json` | ✅ ACTIVE | EVS cache |

### tools/
Contains third-party tools - **DO NOT MODIFY**

### USDM OpenAPI schema/
| File | Status | Notes |
|------|--------|-------|
| `USDM_API.json` | ⚠️ REVIEW | Is this still used? Schema now from dataStructure.yml |

---

## Investigation Results

### Root Utility Files (Analysis)

| File | Used By | Recommendation |
|------|---------|----------------|
| `json_utils.py` | Itself, archived code, tests | 🗑️ ARCHIVE - duplicate of core/ |
| `llm_providers.py` | core/llm_client.py, archived code, tests | ✅ KEEP - used by core |
| `p2u_constants.py` | Archived code, tests only | 🗑️ ARCHIVE - only legacy uses |
| `prompt_templates.py` | Archived code, tests only | 🗑️ ARCHIVE - only legacy uses |

### Validation Files (Analysis)

| File | Used By | Status |
|------|---------|--------|
| `usdm_validator.py` | validation/__init__.py (primary) | ✅ ACTIVE |
| `openapi_validator.py` | main_v2.py, llm_schema_fixer.py | ✅ ACTIVE |
| `schema_validator.py` | pipeline/protocol_pipeline.py | ✅ ACTIVE |
| `llm_schema_fixer.py` | main_v2.py | ✅ ACTIVE |
| `cdisc_conformance.py` | main_v2.py, pipeline/ | ✅ ACTIVE |
| `usdm_examples.py` | Not directly imported | 📁 ARCHIVED |

### Standalone Scripts (Analysis)

| File | Purpose | Recommendation |
|------|---------|----------------|
| `extract_full_usdm.py` | Standalone script | ⚠️ REVIEW - vs main_v2.py? |
| `compare_golden_vs_extracted.py` | Comparison tool | ⚠️ REVIEW - vs test_golden? |

---

## ACTION PLAN

### Phase 1: Immediate Cleanup (Archive)

**Files to move to `archive/legacy_pipeline/`:**
```
json_utils.py (root)
p2u_constants.py
prompt_templates.py
debug_provenance.py
soa_prompt_example.json
```

**Files to delete (obsolete):**
```
archive/logs/*.log (201 files - old logs)
```

### Phase 2: Documentation Update

**Files to update for v6.2:**
```
README.md - Add schema-driven architecture section
USER_GUIDE.md - Update workflow for new pipeline
QUICK_REFERENCE.md - Verify commands are current
```

**Files to archive (outdated docs):**
```
USDM_COVERAGE_STATUS.md → archive/docs_legacy/
Protocol2USDM Review.pdf → archive/docs_legacy/ (or delete)
```

### Phase 3: Prompts Cleanup

**Keep only optimized versions:**
- Remove `find_soa_pages.yaml` (keep `_optimized`)
- Remove `soa_extraction.yaml` (keep `_optimized`)
- Remove `soa_reconciliation.yaml` (keep `_optimized`)
- Remove `vision_soa_extraction.yaml` (keep `_optimized`)

**Or rename optimized → standard and archive originals**

### Phase 4: Tests Update

**Tests that may need updating:**
- `test_clean_llm_json.py` - Uses root json_utils.py
- `test_core_modules.py` - May reference archived files
- `test_prompt_templates.py` - Uses prompt_templates.py

### Phase 5: Final Review

**Files to investigate:**
- `extract_full_usdm.py` - Keep or merge into main_v2.py?
- `compare_golden_vs_extracted.py` - Keep or merge into test_golden?
- `usdm_renderer.html` - Is this used by viewer?
- `usdm_examples.py` - Document purpose or remove

---

## Summary: File Counts (Post-Cleanup)

| Category | Count | Status |
|----------|-------|--------|
| Active pipeline code | ~40 | ✅ Kept |
| Documentation (current) | 5 | ✅ Kept |
| Deleted files | 3 | ✅ Done (PDF, debug, 201 logs) |
| New directories | 2 | ✅ Created (testing/, utilities/) |
| Archived files | 6 | ✅ Done |
| Renamed prompts | 4 | ✅ Done |

### Remaining Items for Later Review

| Item | Notes |
|------|-------|
| `llm_providers.py` | May be used by core - deeper analysis needed |
| `p2u_constants.py` | May still be referenced |
| `prompt_templates.py` | May still be referenced |
| `usdm_renderer.html` | Usage unclear |
| `extract_full_usdm.py` | vs main_v2.py? |
| Documentation (README, USER_GUIDE) | Update for v6.2 architecture |
