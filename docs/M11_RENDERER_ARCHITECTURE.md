# M11 Renderer Architecture

**Date**: 9 Feb 2026
**Reference**: ICH M11 Guideline, Template & Technical Specification (Step 4, 19 Nov 2025)

---

## 1. Overview

The M11 renderer transforms a `protocol_usdm.json` into an ICH M11-structured Word document (DOCX). It is designed around a **dual-path architecture** where content comes from two independent sources:

```
                      ┌─────────────────────┐
                      │  protocol_usdm.json  │
                      └─────────┬───────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                  │
              ▼                 ▼                  ▼
     ┌────────────────┐ ┌──────────────┐ ┌───────────────────┐
     │   Extractors   │ │  M11 Mapper  │ │    Composers      │
     │ (narrative)    │ │ (7-pass)     │ │ (entity→prose)    │
     └───────┬────────┘ └──────┬───────┘ └────────┬──────────┘
             │                 │                   │
             ▼                 ▼                   ▼
     ┌───────────────────────────────────────────────────────┐
     │              M11 Rendering Loop                       │
     │  For each of 14 M11 sections:                        │
     │    1. Emit L1 heading (ALL CAPS)                     │
     │    2. Distribute narrative to sub-headings (L2/L3)   │
     │    3. Append entity-composed content                  │
     │    4. Run conformance check                           │
     └──────────────────────┬────────────────────────────────┘
                            │
              ┌─────────────┼──────────────┐
              ▼             ▼              ▼
        protocol_m11.docx   m11_conformance_report.json
```

### Why This Matters

The extractor/composer duality is the key architectural decision. **Extractors** pull unstructured narrative text from the source PDF via the pipeline. **Composers** generate structured prose from USDM entities (objectives, arms, epochs, interventions, etc.). This means:

- **Today**: We extract a PDF → USDM, then render M11 from that USDM. Composers fill gaps where narrative extraction missed content.
- **Future**: A user or system could **author USDM from scratch** (e.g., via the semantic editor UI or an API) and the composers would produce a complete M11 document without ever needing a source PDF. The narrative path becomes optional.

This makes the composers a general-purpose **USDM → M11 prose generation layer** that is decoupled from the extraction pipeline.

---

## 2. Module Map

| Module | Role |
|--------|------|
| `extraction/narrative/m11_mapper.py` | M11 template definition (14 sections), sub-heading definitions, 7-pass section mapper |
| `rendering/m11_renderer.py` | DOCX generation: title page, rendering loop, all 9 entity composers, sub-heading distribution |
| `validation/m11_conformance.py` | Post-render conformance validator: title page, synopsis, section coverage checks |
| `tests/test_m11_regression.py` | Golden-protocol regression tests |

---

## 3. The Extractor Path (Narrative)

### 3.1 How It Works

1. **PDF → Section Detection** (`extraction/narrative/extractor.py`): Scans the PDF for structure pages (TOC, synopsis). Uses LLM to extract section numbers, titles, and types.
2. **Full-Text Extraction** (`_find_section_pages`, `_extract_section_texts`): Locates each section heading in the PDF body (skipping TOC pages), computes page ranges, extracts and cleans text.
3. **Sub-section Splitting** (`_split_subsection_texts`): Splits parent section text into sub-section chunks using heading boundary detection.
4. **M11 Mapping** (`m11_mapper.map_sections_to_m11`): 7-pass mapper that aligns protocol-native sections to M11 sections:

| Pass | Strategy | Score |
|------|----------|-------|
| 1 | Exact/fuzzy title match against aliases | 0.95 |
| 2 | Keyword overlap scoring (unmapped M11 sections only) | 0.30+ |
| 3 | Section type matching (Synopsis, Introduction, etc.) | 0.60 |
| 4 | Section number prefix (e.g., `10.x` → M11 §10) | 0.70 |
| 5 | **Subsection-to-parent rescue** (e.g., `5.1` → parent `5`'s M11) | 0.85 |
| 6 | **Text-content keyword matching** (use actual text, not just title) | 0.24–0.80 |
| 7 | **Keyword-append** (add strong matches to already-mapped M11 sections) | 0.40+ |

Passes 5–7 were added in this implementation round and reduced unmapped sections from **14 → 0** on the Wilson's protocol.

5. **M11 Narrative Assembly** (`build_m11_narrative`): Combines mapped section texts into M11-organized structure.

### 3.2 Extractor Outputs in USDM

The narrative extraction phase populates these USDM entities on `StudyVersion`:

| Entity | Location in USDM | Description |
|--------|-------------------|-------------|
| `narrativeContents` | `study.versions[0].narrativeContents` | Major sections (L1/L2) with full text |
| `narrativeContentItems` | `study.versions[0].narrativeContentItems` | Sub-sections (L3+) with text |
| `abbreviations` | `study.versions[0].abbreviations` | Protocol abbreviation table |

---

## 4. The Composer Path (Entity → Prose)

### 4.1 How It Works

Each composer is a pure function: `fn(usdm: Dict) -> str` that reads USDM entities and returns formatted prose. Composers are registered in the `entity_composers` dict, keyed by M11 section number:

```python
entity_composers = {
    '1':  _compose_synopsis,        # §1.1.2 Overall Design
    '3':  _compose_objectives,      # §3 Objectives + Endpoints
    '4':  _compose_study_design,    # §4 Arms, Epochs, Cells
    '5':  _compose_eligibility,     # §5 Inclusion/Exclusion
    '6':  _compose_interventions,   # §6 Intervention Overview
    '7':  _compose_discontinuation, # §7 (narrative keyword scan)
    '9':  _compose_safety,          # §9 (narrative keyword scan, categorized)
    '10': _compose_statistics,      # §10 SAP, Estimands, Analysis Pops
}
```

Additionally, `_compose_estimands` is called specifically for §3.1.

### 4.3 Direct Table Renderers (Non-Composer)

Two M11 sub-sections are rendered as proper Word tables rather than text:

| Function | M11 Section | Description |
|----------|-------------|-------------|
| `_add_synopsis_table` | §1.1.2 | 2-column table with field labels (bold, grey bg) and values. Parses `_compose_synopsis` output. |
| `_add_soa_table` | §1.3 | Full SoA grid: epoch header row (merged), encounter header row, activity rows grouped by category, X/O/− marks with footnote superscripts, footnotes below. Landscape orientation. |
| `_build_soa_data` | (helper) | Extracts SoA data from USDM: epochs, encounters, activities, groups, cells, footnotes from `scheduleTimelines` and `extensionAttributes`. |

The SoA table renderer (`_add_soa_table`):
- Switches to **landscape orientation** for the table, then back to portrait
- Renders **epoch header row** with merged cells spanning encounters
- Renders **encounter/visit header row** with compact font
- Inserts **group header rows** (merged, grey background) between activity categories
- Shows **X/O/−** marks with **footnote superscripts** (e.g., X^a,b^)
- Lists all **30 footnotes** below the table in 8pt grey text
- Uses compact 7pt font and 240twip row height for dense tables

### 4.2 Composer Details

#### `_compose_synopsis` (§1.1.2 — Overall Design)

Extracts ~27 structured fields from USDM study design entities. Sources:

| Field | USDM Source | Status |
|-------|-------------|--------|
| Intervention Model | `studyDesign.model.decode` | **OK** |
| Population Type | `population.includesHealthySubjects` | **OK** |
| Population Diagnosis | `studyDesign.indications[].name` | **OK** |
| Control Type | Derived from arm types | **OK** |
| Population Age | `population.plannedMinimumAgeOfSubjects` | **GAP** — not extracted |
| Intervention Assignment | `studyDesign.randomizationType.decode` | **PARTIAL** — missing for non-randomized |
| Stratification Indicator | Derived from conditions | **OK** |
| Site Distribution | `studyDesign.studySites` count | **OK** |
| Site Geographic Scope | `studySites[].address.country` | **OK** |
| Master Protocol Indicator | Heuristic (always "No") | **OK** |
| Drug/Device Combination | Heuristic (always "No") | **OK** |
| Adaptive Trial Design | Heuristic (always "No") | **OK** |
| Number of Arms | `studyDesign.arms` count | **OK** |
| Trial Blind Schema | `studyDesign.blindingSchema.decode` | **GAP** — often not extracted |
| Blinded Roles | `studyDesign.maskingRoles[].decode` | **OK** |
| Number of Participants | `population.plannedNumberOfSubjects` | **GAP** — not extracted |
| Trial Duration | Derived from epochs | **OK** |
| Committees | Not in USDM schema | **GAP** — no USDM entity |

#### `_compose_objectives` (§3)

| USDM Source | Status |
|-------------|--------|
| `studyDesign.objectives[]` with level (primary/secondary/exploratory) | **OK** |
| `studyDesign.endpoints[]` linked via `objectiveId` | **OK** |

#### `_compose_study_design` (§4)

| USDM Source | Status |
|-------------|--------|
| `studyDesign.arms[]` | **OK** |
| `studyDesign.epochs[]` | **OK** |
| `studyDesign.studyCells[]` | **OK** |
| `studyDesign.studyElements[]` | **OK** |

#### `_compose_eligibility` (§5)

| USDM Source | Status |
|-------------|--------|
| `studyDesign.eligibilityCriteria[]` with inclusion/exclusion category | **OK** — 31 criteria extracted |
| `population.plannedSex` | **GAP** — not extracted |
| `population.plannedMinimumAgeOfSubjects` | **GAP** — not extracted |
| `population.plannedMaximumAgeOfSubjects` | **GAP** — not extracted |

#### `_compose_interventions` (§6)

| USDM Source | Status |
|-------------|--------|
| `studyInterventions[]` | **OK** — 6 interventions |
| `administrations[]` (route, frequency) | **OK** — 2 administrations |
| `administrableProducts[]` (dose form, strength) | **PARTIAL** — only 1 product linked |
| Cross-reference via `administrationIds` and `productIds` | **OK** |

#### `_compose_discontinuation` (§7)

Uses **narrative keyword scan** — no dedicated USDM entity exists.

| Approach | Status |
|----------|--------|
| Scan all narrative sections for discontinuation keywords | **WEAK** — no sections matched for Wilson's |
| No USDM entity for `WithdrawalCriteria` or `DiscontinuationRules` | **GAP** |

#### `_compose_safety` (§9)

Uses **categorized narrative keyword scan** with 7 safety sub-categories.

| Approach | Status |
|----------|--------|
| AE/SAE definitions from narrative | **OK** — 6 sections matched |
| AESI definitions | Keyword-matched from narrative | **OK** |
| Reporting requirements | Keyword-matched | **OK** |
| Pregnancy/postpartum | Keyword-matched | **OK** |
| Conditions (stopping rules) | `studyDesign.conditions[]` | **OK** |
| No USDM entity for `AdverseEventDefinition` | **GAP** |

#### `_compose_statistics` (§10)

| USDM Source | Status |
|-------------|--------|
| `studyDesign.analysisPopulations[]` | **OK** — 7 populations |
| `studyDesign.extensionAttributes[]` (SAP data) | **OK** — 22 attributes |
| `studyDesign.estimands[]` | **OK** — 2 estimands |
| Sample size rationale | From extension attributes | **PARTIAL** |
| Interim analysis plan | From extension attributes | **PARTIAL** |

---

## 5. Sub-Heading Architecture

The M11 Template defines detailed L2/L3 sub-headings within each major section. These are codified in `M11_SUBHEADINGS` (in `m11_mapper.py`) as:

```python
M11_SUBHEADINGS: Dict[str, List[Tuple[str, str, int, List[str]]]]
# section_number → list of (sub_number, title, heading_level, keywords)
```

**8 sections** have sub-heading definitions: §1, §3, §5, §6, §8, §9, §10, §11.

The rendering loop uses `_distribute_to_subsections()` to split narrative text into paragraphs and assign each to the best-matching sub-heading by keyword scoring. Unmatched paragraphs go under a `_general` bucket at the top of the section.

---

## 6. Conformance Validation

`validation/m11_conformance.py` checks the USDM against M11 Technical Specification requirements across three categories:

| Category | What It Checks | Fields |
|----------|---------------|--------|
| **Title Page** | 7 Required + 5 Optional fields (identifiers, sponsor, phase, version, IP names) | 12 |
| **Synopsis §1.1.2** | 9 Required + 9 Optional structured fields | 18 |
| **Section Coverage** | 11 Required + 3 Optional M11 sections have content | 14 |

**Output**: `m11_conformance_report.json` with overall score, per-category scores, and issue list.

**Current Score (Wilson's)**: 88.9% — 24/27 required fields present, 3 errors.

---

## 7. Title Page Architecture

The title page (`_add_title_page`) extracts M11-required fields from USDM using C-code lookups:

| Field | C-Code | USDM Path |
|-------|--------|-----------|
| Sponsor Protocol Identifier | C132351 | `studyIdentifiers[].type.code` |
| NCT Number | C172240 | `studyIdentifiers[].type.code` |
| EU CT Number | C218684 | `studyIdentifiers[].type.code` |
| FDA IND Number | C218685 | `studyIdentifiers[].type.code` |
| Original Protocol Indicator | C217046 | Derived from `amendments` presence |
| Trial Phase | C15601 | `studyPhase.decode` |
| Sponsor Name | C54086 | `organizations[].type.code` |

---

## 8. USDM Extractor Gaps — Action Items

These are concrete gaps where USDM extractors are not populating fields that M11 composers need. Each gap reduces M11 conformance score and document quality.

### 8.1 CRITICAL — Directly Cause M11 Conformance Errors

| # | Gap | M11 Field | USDM Path | Affected Extractor | Impact |
|---|-----|-----------|-----------|-------------------|--------|
| G1 | **Planned number of participants not extracted** | §1.1.2 Number of Participants | `population.plannedNumberOfSubjects` | `metadata` or `studydesign` phase | Conformance ERROR; synopsis incomplete |
| G2 | **Sponsor approval date not extracted** | Title Page: Sponsor Approval | `version.effectiveDate` | `metadata` phase | Conformance ERROR; title page incomplete |
| G3 | **No discontinuation/withdrawal content** | §7 Participant Discontinuation | No USDM entity | `narrative` phase or new `discontinuation` phase | Entire M11 §7 empty; conformance ERROR |

### 8.2 HIGH — Significantly Degrade Document Quality

| # | Gap | M11 Field | USDM Path | Affected Extractor | Impact |
|---|-----|-----------|-----------|-------------------|--------|
| G4 | **Age range not extracted** | §1.1.2 Population Age, §5 Eligibility | `population.plannedMinimumAgeOfSubjects`, `plannedMaximumAgeOfSubjects` | `eligibility` phase | Synopsis field missing; eligibility section incomplete |
| G5 | **Sex/gender not extracted** | §5 Eligibility | `population.plannedSex` | `eligibility` phase | Not rendered in eligibility criteria summary |
| G6 | **Blinding schema not extracted** | §1.1.2 Trial Blind Schema | `studyDesign.blindingSchema.decode` | `studydesign` phase | Synopsis shows "Not specified" |
| G7 | **Randomization type often missing** | §1.1.2 Intervention Assignment | `studyDesign.randomizationType.decode` | `studydesign` phase | Synopsis shows "Not specified" for non-randomized studies |
| G8 | **AdministrableProduct linkage incomplete** | §6 Intervention Table | `studyInterventions[].productIds` | `interventions` phase | Only 1 of 6 interventions has product link; dose form/strength missing |

### 8.3 MEDIUM — Reduce Conformance Score (Optional Fields)

| # | Gap | M11 Field | USDM Path | Affected Extractor | Impact |
|---|-----|-----------|-----------|-------------------|--------|
| G9 | **Sponsor address not extracted** | Title Page: Sponsor Address | `organizations[].legalAddress.text` | `metadata` phase | Address shows "Not available" |
| G10 | **Version date not extracted** | Title Page: Version Date | `version.effectiveDate` | `metadata` phase | Same as G2 |
| G11 | **Committees not in USDM schema** | §1.1.2 Committees, §11 Oversight | N/A (not a USDM entity) | Would need custom extension | Synopsis/oversight field missing |
| G12 | **Oversight narrative not captured** | §11 Trial Oversight | Narrative sections | `narrative` phase | Entire M11 §11 relies on narrative mapping |

### 8.4 LOW — Heuristic Defaults (Acceptable for Now)

| # | Field | Current Approach |
|---|-------|-----------------|
| G13 | Master Protocol Indicator | Hardcoded "No" — would need protocol classification |
| G14 | Drug/Device Combination Indicator | Hardcoded "No" — would need product analysis |
| G15 | Adaptive Trial Design Indicator | Hardcoded "No" — would need design classification |

---

## 9. Recommended Extractor Improvements (Priority Order)

### Priority 1: Fix Population Demographics (G1, G4, G5)

**Where**: `pipeline/phases/eligibility.py` and/or `pipeline/phases/metadata.py`

The eligibility extractor already extracts 31 inclusion/exclusion criteria but does NOT populate the population-level demographics fields. The LLM prompt should be updated to also extract:

- `plannedNumberOfSubjects` (from "approximately N participants" text)
- `plannedMinimumAgeOfSubjects` / `plannedMaximumAgeOfSubjects` (from age criteria)
- `plannedSex` (from sex/gender criteria)

These are typically stated explicitly in the eligibility section or synopsis and should be straightforward to extract.

**Impact**: Fixes G1 (conformance ERROR), G4, G5. Adds ~3 synopsis fields.

### Priority 2: Extract Blinding and Randomization (G6, G7)

**Where**: `pipeline/phases/studydesign.py`

The study design extractor captures arms, epochs, and model but misses:

- `blindingSchema` (Open-label / Single-blind / Double-blind)
- `randomizationType` (Randomized / Non-randomized)

These are almost always stated in the protocol synopsis or design section title.

**Impact**: Fixes G6, G7. Completes synopsis.

### Priority 3: Sponsor Metadata Completeness (G2, G9, G10)

**Where**: `pipeline/phases/metadata.py`

The metadata extractor captures protocol identifiers and sponsor name but misses:

- `effectiveDate` (protocol approval date / version date)
- `legalAddress` on sponsor Organization

These appear on the title page of almost every protocol.

**Impact**: Fixes G2 (conformance ERROR), G9, G10. Completes title page.

### Priority 4: Discontinuation Content (G3)

**Where**: `pipeline/phases/narrative.py` or new dedicated phase

Discontinuation criteria are typically embedded in §5 (Population) or §6 (Intervention) of the source protocol. Options:

1. **Narrative approach**: Enhance the narrative extraction prompt to specifically tag discontinuation-related paragraphs
2. **Entity approach**: Create a dedicated extraction for withdrawal criteria, treatment discontinuation rules, and study completion definitions
3. **Hybrid**: Use the existing `_compose_discontinuation` keyword scanner but also add extraction-time tagging

**Impact**: Fixes G3 (conformance ERROR). Populates M11 §7.

### Priority 5: Product-Intervention Linkage (G8)

**Where**: `pipeline/phases/interventions.py`

The interventions extractor creates `StudyIntervention` entities with `administrationIds` but often fails to link `productIds` to `AdministrableProduct` entities. The extractor should:

- Create `AdministrableProduct` for each distinct drug/dose form mentioned
- Link via `productIds` on the intervention

**Impact**: Fixes G8. Completes §6 intervention overview table.

---

## 10. Future: USDM-First Authoring Path

When authoring USDM from scratch (e.g., via the semantic editor), the composer path becomes the **primary** content generation path. The narrative path is not needed because there is no source PDF.

```
  Author/Editor                    Composers
  ┌────────────┐                   ┌──────────────┐
  │  Edit USDM │ ──(save)──────► │  protocol     │
  │  entities   │                  │  _usdm.json   │
  └────────────┘                   └──────┬───────┘
                                          │
                                          ▼
                                   ┌──────────────┐
                                   │  M11 Renderer │
                                   │  (composers   │
                                   │   only)       │
                                   └──────┬───────┘
                                          │
                                   ┌──────┴───────┐
                                   ▼              ▼
                             protocol_m11   conformance
                             .docx          _report.json
```

For this to work well, the **gap items G1–G8** must be resolvable from USDM entities alone, without narrative text. This means:

1. All population demographics (G1, G4, G5) must be populated in `StudyDesignPopulation`
2. Blinding/randomization (G6, G7) must be in `StudyDesign`
3. Discontinuation rules (G3) need a USDM entity — either `WithdrawalCriteria` or use `Condition` entities with a discontinuation category
4. Committees (G11) need either an extension attribute or a new USDM entity

The composers are already designed to read from USDM entities, so once the data is there (whether extracted or authored), the M11 document will be complete.

---

## 11. Style Compliance

The renderer follows ICH M11 Template (Step 4, Nov 2025) formatting conventions:

### 11.1 Document Setup

| Property | Value |
|----------|-------|
| Page size | Letter (8.5 × 11 in) |
| Margins | 1 inch (2.54 cm) all sides |
| Font | Times New Roman throughout |
| Line spacing | 1.15 (body text) |

### 11.2 Heading Hierarchy

Per the ICH M11 Template heading table (Step 4, Nov 2025):

| Level | Size | Weight | Style | Spacing |
|-------|------|--------|-------|----------|
| H1 (§N) | 14pt | Bold | ALL CAPS (via `all_caps`) | 24pt before, 6pt after |
| H2 (§N.N) | 14pt | Bold | Title case | 18pt before, 6pt after |
| H3 (§N.N.N) | 12pt | Bold | Title case | 12pt before, 3pt after |
| H4 (§N.N.N.N) | 12pt | Bold | Title case | 6pt before, 3pt after |
| H5 (§N.N.N.N.N) | 12pt | Bold | Title case | 6pt before, 3pt after |

All headings: Times New Roman, black, keep-with-next enabled.

Heading level is determined automatically from section number depth via `_heading_level()` (count dots + 1, capped at 5).

### 11.3 Body & List Styles

| Element | Style |
|---------|-------|
| Body text | 11pt, 6pt after, 1.15 line spacing |
| List Bullet | 11pt, 0.5in indent, 3pt after |
| List Number | 11pt, 0.5in indent, 3pt after |
| Empty section notice | Italic, red (#C00000) |

### 11.4 Title Page

| Element | Style |
|---------|-------|
| Confidentiality | 11pt bold red, centered |
| Confidentiality notice | 8pt italic grey, centered |
| Full title | 16pt bold, centered |
| Short title / acronym | 12pt italic, centered |
| Metadata table | 10pt, Table Grid, label col grey bg (#F2F2F2), 6cm/10cm widths |
| Generation timestamp | 8pt italic light grey, centered |

### 11.5 Headers & Footers

| Element | Style |
|---------|-------|
| Header | Protocol ID (8pt bold) + "CONFIDENTIAL" (8pt bold red), right-aligned |
| Footer | "Page X of Y" (8pt), centered, using PAGE/NUMPAGES fields |

Applied to all sections including landscape SoA.

### 11.6 Table of Contents

Real Word TOC field code (`TOC \o "1-3" \h \z \u`) — right-click and "Update Field" in Word to populate.

### 11.7 SoA Table (§1.3)

| Element | Style |
|---------|-------|
| Orientation | Landscape (switches back to portrait after) |
| Epoch header | 7pt bold, merged cells, blue bg (#D9E2F3) |
| Visit header | 6pt bold, green bg (#E2EFDA) |
| Group header | 7pt bold, merged row, grey bg (#F2F2F2) |
| Activity cells | 7pt, centered marks (X/O/−) |
| Footnote superscripts | 5pt superscript on cell marks |
| Footnotes | 8pt grey below table, 2pt spacing |
| Row height | 240 twips minimum |
| Activity col width | 5cm; data cols auto-fit (min 1.2cm) |

### 11.8 Synopsis Table (§1.1.2)

| Element | Style |
|---------|-------|
| Layout | 2-column (label / value), Table Grid |
| Label column | 9pt bold, grey bg (#F2F2F2), 6cm width |
| Value column | 9pt, 10cm width |

### 11.9 Narrative Text Rendering

`_add_narrative_text` handles:
- Double-newline paragraph breaks
- `**bold**` and `*italic*` inline markers
- Bullet lists (`- item` or `• item`) → List Bullet style
- Numbered lists (`1. item`, `a. item`) → List Number style
- Markdown headings (`## H2`, `### H3`)
- Regular paragraphs with preserved line breaks

### 11.10 Section Layout

- Page breaks between L1 sections §1–§11 only
- Appendices §12–§14 flow continuously without page breaks
- No source attribution annotations (clean output)
- §1 Protocol Summary includes all M11-required sub-sections:
  - §1.1 Protocol Synopsis
  - §1.1.1 Primary and Secondary Objectives and Estimands
  - §1.1.2 Overall Design (structured synopsis table)
  - §1.2 Trial Schema (placeholder)
  - §1.3 Schedule of Activities (DOCX table)

---

## 12. Regression Test Coverage

`tests/test_m11_regression.py` provides 3 tests:

1. **`test_m11_all_protocols`**: Renders DOCX for each golden protocol and checks sections, words, and conformance score.
2. **`test_m11_entity_composers`**: Verifies critical composers (synopsis, objectives, study_design) produce non-empty output.
3. **`test_m11_section_mapping_coverage`**: Checks that the 7-pass mapper achieves ≥50% M11 coverage and <30% unmapped sections.

**Current results (Wilson's NCT04573309)**:
- 12/14 sections with content
- 48,293 words
- 88.9% conformance (render-time) / 77.8% conformance (standalone validator)
- 0 unmapped protocol sections
- All 3 tests PASS

---

## 13. File Inventory

```
rendering/
  m11_renderer.py          # Main renderer + 9 composers + title page + sub-heading distribution

extraction/narrative/
  m11_mapper.py            # M11_TEMPLATE (14 sections), M11_SUBHEADINGS (8 sections),
                           # 7-pass mapper, build_m11_narrative
  extractor.py             # PDF → sections + abbreviations (LLM-based)
  schema.py                # NarrativeContent, NarrativeContentItem, Abbreviation
  prompts.py               # LLM prompts for structure/abbreviation extraction

validation/
  m11_conformance.py       # Conformance validator (title page + synopsis + section coverage)

tests/
  test_m11_regression.py   # Golden-protocol regression tests (Wilson's only for now)
```
