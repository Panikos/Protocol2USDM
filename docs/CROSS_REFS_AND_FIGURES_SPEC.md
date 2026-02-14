# Cross-References & Figures/Tables Extraction — Design Spec

**Date**: 12 Feb 2026

---

## Problem

1. **Cross-references**: Protocol text contains inline references like "see Section 5.2", "refer to Table 3-1", "as described in Appendix 10.2". These are currently embedded in narrative text as plain strings — they aren't structured, so the UI can't link to the referenced section and the M11 renderer can't resolve them.

2. **Figures/Tables/Images**: Protocols contain study schema diagrams (§1.2), flowcharts, Kaplan-Meier plots, data tables, and other visual content. Currently we extract text only — these are lost. M11 §1.2 (Trial Schema) explicitly requires a visual diagram, and many other sections reference figures.

---

## Approach

### Part A: Inline Cross-References

**What we extract**: Every instance of a cross-reference pattern in the narrative text, with:
- The **source** (which section/page the reference appears in)
- The **target** (which section/figure/table/appendix is being referenced)
- The **context** (surrounding sentence fragment for display)
- The **referenceType** (Section, Table, Figure, Appendix)

**Where it lives in USDM**: Extend the existing `DocumentContentReference` entity (already in `extraction/document_structure/schema.py`) with:
- `sourceSection` — section number where the reference appears
- `referenceType` — enum: Section, Table, Figure, Appendix
- `contextText` — the surrounding sentence (for UI tooltip/display)

**How we extract**: Enhance the `doc_structure` phase with a deterministic regex pass + LLM enrichment:
1. **Regex pass** (no LLM cost): Scan all `narrativeContents` text for patterns like `see Section \d`, `Table \d`, `Figure \d`, `Appendix \d`. This catches 80%+ of references.
2. **LLM pass** (only for ambiguous): For references that can't be resolved to a known section number, use the existing doc_structure LLM call to clarify.

**Post-processing**: After extraction, a linker step matches each `targetSection` to the `id` of the corresponding `NarrativeContent` entity, populating `targetId`. This enables the UI to navigate directly.

### Part B: Figure/Table/Image Catalog + Extraction

**What we extract**: A catalog of every figure, table, and diagram in the PDF, with:
- **label** — e.g., "Figure 1", "Table 3-1"
- **title** — e.g., "Study Schema", "Eligibility Criteria Summary"
- **pageNumber** — PDF page (0-indexed) where it appears
- **sectionNumber** — which protocol section it belongs to
- **imagePath** — path to the extracted PNG image (rendered from PDF page)
- **contentType** — Figure, Table, Diagram, Chart, Image

**New schema entity**: `ProtocolFigure` (stored as extension data, not a core USDM entity)

**How we extract**:
1. **Deterministic scan**: Scan every PDF page for patterns like `Figure \d`, `Table \d`, `Diagram`. Build a catalog of (label, page, surrounding text).
2. **Page rendering**: For each detected figure/table page, render the PDF page to a PNG using the existing `render_page_to_image()` in `core/pdf_utils.py`. Save to `output/<run>/figures/`.
3. **LLM title extraction** (batch): Send the catalog to the LLM to extract proper titles and section assignments. This is a single cheap call.

**Where it lives in USDM**: Stored as an extension attribute on `StudyVersion`:
```json
{
  "url": "https://protocol2usdm.io/extensions/x-protocol-figures",
  "valueString": "[{\"label\": \"Figure 1\", \"title\": \"Study Schema\", ...}]"
}
```

Plus the actual image files are saved alongside the output and referenced by path.

### Part C: Integration Points

**UI**: 
- Cross-references become clickable links in narrative text (resolve `targetId` → navigate to section)
- Figures/tables get a gallery view and can be embedded inline

**M11 Renderer**:
- §1.2 Trial Schema: If a figure labeled "Study Schema" or "Trial Schema" exists, embed it as an image
- Cross-references in narrative text: Replace "see Section X" with proper Word cross-reference fields or at minimum hyperlinked text

**Pipeline**:
- Runs as part of the existing `doc_structure` phase (extended, not a new phase)
- Deterministic regex pass runs first (free), LLM enrichment runs second (cheap)
- Figure images saved to `output/<run>/figures/` directory

---

## Implementation Plan

### Step 1: Schema Extensions
- Add `InlineCrossReference` dataclass to `extraction/document_structure/schema.py`
- Add `ProtocolFigure` dataclass to `extraction/document_structure/schema.py`
- Extend `DocumentStructureData` to hold both

### Step 2: Deterministic Extractors (no LLM)
- `_extract_inline_references(narrative_contents)` — regex scanner for cross-ref patterns
- `_scan_figures_and_tables(pdf_path)` — PDF page scanner for figure/table labels

### Step 3: Image Rendering
- For each detected figure/table page, call `render_page_to_image()` 
- Save to `output/<run>/figures/figure_001.png` etc.

### Step 4: LLM Enrichment (extend existing prompt)
- Extend `get_document_structure_prompt()` to also ask for figure titles and cross-ref resolution
- Parse the enriched response

### Step 5: Post-Processing Linker
- Match cross-reference targets to NarrativeContent IDs
- Match figure section numbers to NarrativeContent section numbers

### Step 6: Pipeline Wiring
- Extend `DocStructurePhase.combine()` to add cross-refs and figures to combined dict
- Save figure catalog to `protocol_usdm.json` as extension attribute

### Step 7: Renderer Integration
- M11 renderer: embed figure images for §1.2, resolve cross-refs in narrative text
- UI: expose cross-refs and figures via API (future)
