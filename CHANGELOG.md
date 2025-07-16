# Protocol2USDM – Change Log

All notable changes after the last GitHub check-in (2025-07-13) are documented here.  Dates in ISO-8601.

## [Unreleased] – 2025-07-14
### Added
* **Gemini-2.5-Pro default model** – `main.py` now defaults to this model unless `--model` overrides.
* **Header-aware extraction**
  * `analyze_soa_structure.py` unchanged, but its JSON is now fed as machine-readable `headerHints` into both `send_pdf_to_llm.py` and `vision_extract_soa.py` prompts to prevent ID hallucination.
* **Header-driven enrichment** – `soa_postprocess_consolidated.py` enriches missing `activityGroupId` fields and group memberships using the header structure.
* **Header validation utility** – new script `soa_validate_header.py` automatically repairs any remaining header-derived issues after post-processing.
* **Pipeline wiring** – `main.py` now calls the validation utility automatically after Steps 7 and 8.
* **Documentation** – README revised with new 11-step workflow and header features.

### Changed
* Updated README default run command (`--model` optional, defaults to gemini-2.5-pro).
* Updated pipeline step table to include `soa_validate_header.py`.
* Key Features section reflects header-driven enrichment & validation.

### Removed
* Deprecated mention of `send_pdf_to_openai.py` in favour of `send_pdf_to_llm.py`.

---

## [Unreleased] – 2025-07-13
### Added
* **Provenance tagging**  
  * `vision_extract_soa.py` now writes `p2uProvenance.<entityType>.<id> = "vision"` for every `PlannedTimepoint`, `Activity`, `Encounter` it emits.  
  * `send_pdf_to_llm.py` tags the same entities with `"text"`.
* **Quality-control post-processing** (`soa_postprocess_consolidated.py`)
  * Detects orphaned `PlannedTimepoints` (no `ActivityTimepoint` links) and moves them to `p2uOrphans.plannedTimepoints`.
  * Auto-fills missing `activityIds` for every `ActivityGroup` and records multi-group conflicts in `p2uGroupConflicts`.
* **Streamlit viewer** (`soa_streamlit_viewer.py`)
  * Sidebar toggle **Show orphaned columns**; default hides orphans.
  * Conflict banner when `p2uGroupConflicts` present.
* **Internal utilities** for provenance and QC now live outside the `study` node so USDM-4.0 compliance remains intact.

### Changed
* All calls to `render_soa_table()` now pass header-structure JSON for enrichment.
* Viewer filtering pipeline updated to respect orphan/visibility settings.

### Planned (next sprint)
* Provenance colour coding and tooltip (blue=text, green=vision, purple=both).
* Chronology sanity check with `p2uTimelineOrderIssues` and viewer highlighting.
* Completeness index badge per run.
* One-click diff between any two runs.
* QC rules externalised to `qc_rules.yaml`.
* Async concurrent chunk uploads during LLM extraction for faster runtime.
* Header-structure caching – skip step 4 if images unchanged.

---
