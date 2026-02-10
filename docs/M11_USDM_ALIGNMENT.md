# M11 ↔ USDM v4.0 Alignment Analysis

**Date**: 9 Feb 2026  
**Purpose**: Map every M11 section to its proper USDM v4.0 entities, identify architectural anti-patterns, and define the extractor remediation plan.

---

## 1. The Correct Architecture

The principle is simple: **M11 defines the output structure, USDM defines the data model, extractors populate the model, composers render it.**

```
  ICH M11 Template                USDM v4.0 Schema              Pipeline Extractors
  (14 sections)                   (86 entities)                  (11 phases)
  ┌──────────────────┐            ┌──────────────────┐           ┌──────────────────┐
  │ §1 Protocol      │◄───maps───│ StudyVersion     │◄──fills──│ metadata         │
  │    Summary       │            │ StudyTitle       │           │ narrative        │
  │                  │            │ StudyIdentifier  │           │                  │
  │ §3 Objectives    │◄───maps───│ Objective        │◄──fills──│ objectives       │
  │                  │            │ Endpoint         │           │                  │
  │ §5 Population    │◄───maps───│ StudyDesign      │◄──fills──│ eligibility      │
  │                  │            │   Population     │           │ studydesign      │
  │                  │            │ EligibilityCrit  │           │                  │
  │ §6 Intervention  │◄───maps───│ StudyIntervention│◄──fills──│ interventions    │
  │                  │            │ Administration   │           │                  │
  │                  │            │ Administrable    │           │                  │
  │                  │            │   Product        │           │                  │
  │ §9 Safety/AE     │◄───maps───│ NarrativeContent │◄──fills──│ ???              │
  │                  │            │  (type=Safety)   │           │                  │
  │ §10 Statistics   │◄───maps───│ Estimand         │◄──fills──│ advanced (SAP)   │
  │                  │            │ AnalysisPopn     │           │ objectives       │
  │                  │            │ IntercurrentEvt  │           │                  │
  └──────────────────┘            └──────────────────┘           └──────────────────┘
                                          │
                                          ▼
                                  ┌──────────────────┐
                                  │ Entity Composers │
                                  │ (pure functions)  │
                                  │ USDM → prose     │
                                  └──────┬───────────┘
                                         │
                                         ▼
                                  protocol_m11.docx
```

### The Key Rule

> **Composers must NEVER extract.** They read structured USDM entities and generate prose.  
> **Extractors must NEVER render.** They read source documents and populate USDM entities.  
> If a composer is scanning narrative text for keywords, that's an extractor's job that hasn't been built yet.

---

## 2. M11 Section → USDM Entity Map (Complete)

This is the authoritative mapping. For each M11 section, the table shows which USDM v4.0 entities carry the data, and the current status of our extractors.

### §1 Protocol Summary

| M11 Sub-section | USDM Entity | USDM Path | Extractor | Status |
|----------------|-------------|-----------|-----------|--------|
| Title Page | `StudyTitle` | `version.titles[]` | metadata | ✅ OK |
| Title Page | `StudyIdentifier` | `version.studyIdentifiers[]` | metadata | ✅ OK |
| Title Page | `Organization` (sponsor) | `version.organizations[]` | metadata | ⚠️ Missing address |
| Title Page | `GovernanceDate` | `version.dateValues[]` | metadata | ❌ Not extracted |
| Title Page | `StudyAmendment` | `version.amendments[]` | amendments | ✅ OK |
| §1.1.1 Schema | (SoA rendering) | — | execution | ✅ OK |
| §1.1.2 Synopsis | `StudyDesignPopulation.plannedEnrollmentNumber` | `design.population.plannedEnrollmentNumber` | eligibility/metadata | ❌ Not extracted |
| §1.1.2 Synopsis | `StudyDesignPopulation.plannedAge` | `design.population.plannedAge` | eligibility | ❌ Not extracted |
| §1.1.2 Synopsis | `StudyDesignPopulation.plannedSex` | `design.population.plannedSex` | eligibility | ❌ Not extracted |
| §1.1.2 Synopsis | `StudyDesign.characteristics` | `design.characteristics[]` | studydesign | ❌ Not extracted |
| §1.1.2 Synopsis | `Masking` | `design.maskingRoles[]` | studydesign | ⚠️ Partial |

### §2 Introduction

| M11 Sub-section | USDM Entity | USDM Path | Extractor | Status |
|----------------|-------------|-----------|-----------|--------|
| Background | `NarrativeContent` | `version.narrativeContents[]` | narrative | ✅ OK |
| Benefit-Risk | `NarrativeContent` | `version.narrativeContents[]` | narrative | ✅ OK (via mapper P7) |

### §3 Trial Objectives and Estimands

| M11 Sub-section | USDM Entity | USDM Path | Extractor | Status |
|----------------|-------------|-----------|-----------|--------|
| Objectives | `Objective` | `design.objectives[]` | objectives | ✅ OK |
| Endpoints | `Endpoint` | `design.endpoints[]` | objectives | ✅ OK |
| Estimands | `Estimand` | `design.estimands[]` | objectives | ✅ OK |
| Intercurrent Events | `IntercurrentEvent` | `design.estimands[].intercurrentEvents[]` | objectives | ✅ OK |

### §4 Trial Design

| M11 Sub-section | USDM Entity | USDM Path | Extractor | Status |
|----------------|-------------|-----------|-----------|--------|
| Design Overview | `InterventionalStudyDesign` | `design` (rationale, model, description) | studydesign | ✅ OK |
| Arms | `StudyArm` | `design.arms[]` | studydesign | ✅ OK |
| Epochs | `StudyEpoch` | `design.epochs[]` | studydesign | ✅ OK |
| Cells | `StudyCell` | `design.studyCells[]` | studydesign | ✅ OK |
| Elements | `StudyElement` | `design.studyElements[]` | studydesign | ✅ OK |
| Randomization | `StudyDesign` (no dedicated entity) | `design.randomizationType` | studydesign | ⚠️ Often missing |
| Blinding | `Masking` | `design.maskingRoles[]` | studydesign | ⚠️ `blindingSchema` not extracted |
| End of Study | `NarrativeContent` | narrative | narrative | ⚠️ Often unmapped |

### §5 Trial Population

| M11 Sub-section | USDM Entity | USDM Path | Extractor | Status |
|----------------|-------------|-----------|-----------|--------|
| Inclusion Criteria | `EligibilityCriterion` (category=Inclusion) | `design.eligibilityCriteria[]` | eligibility | ✅ OK |
| Exclusion Criteria | `EligibilityCriterion` (category=Exclusion) | `design.eligibilityCriteria[]` | eligibility | ✅ OK |
| Population Demographics | `StudyDesignPopulation` | `design.population` | eligibility | ❌ Missing age/sex/N |
| Screen Failures | `NarrativeContent` | narrative | narrative | ⚠️ Via mapper P7 |
| Lifestyle | `NarrativeContent` | narrative | narrative | ⚠️ Via mapper P7 |

### §6 Trial Intervention

| M11 Sub-section | USDM Entity | USDM Path | Extractor | Status |
|----------------|-------------|-----------|-----------|--------|
| Interventions | `StudyIntervention` | `version.studyInterventions[]` | interventions | ✅ OK |
| Administration | `Administration` | `version.administrations[]` | interventions | ✅ OK |
| Products | `AdministrableProduct` | `version.administrableProducts[]` | interventions | ⚠️ Incomplete linkage |
| Concomitant Therapy | `NarrativeContent` | narrative | narrative | ⚠️ Not tagged |

### §7 Participant Discontinuation ❌ MAJOR GAP

| M11 Sub-section | USDM Entity | USDM Path | Extractor | Status |
|----------------|-------------|-----------|-----------|--------|
| Discontinuation of Intervention | `NarrativeContent` (sectionType=Discontinuation) | `version.narrativeContents[]` | **NONE** | ❌ No extractor |
| Withdrawal from Trial | `NarrativeContent` (sectionType=Discontinuation) | `version.narrativeContents[]` | **NONE** | ❌ No extractor |
| Lost to Follow-up | `NarrativeContent` (sectionType=Discontinuation) | `version.narrativeContents[]` | **NONE** | ❌ No extractor |

**Note**: USDM v4.0 does NOT have a dedicated `DiscontinuationCriteria` entity. The correct USDM approach is to use `NarrativeContent` entities with `sectionType` set to a Discontinuation code, properly linked to M11 §7 sub-sections. `IntercurrentEvent` (on `Estimand`) covers discontinuation as an estimand strategy but NOT the protocol rules themselves.

### §8 Trial Assessments and Procedures

| M11 Sub-section | USDM Entity | USDM Path | Extractor | Status |
|----------------|-------------|-----------|-----------|--------|
| Efficacy Assessments | `Activity`, `Procedure` | `design.activities[]`, `design.procedures[]` | procedures, execution | ✅ OK (structured) |
| Safety Assessments | `Activity`, `Procedure` | `design.activities[]` | procedures | ⚠️ Not tagged as safety |
| Biospecimen | `BiospecimenRetention` | `design.biospecimenRetentions[]` | **NONE** | ❌ Not extracted |

### §9 Adverse Events / Safety ❌ ARCHITECTURAL ANTI-PATTERN

| M11 Sub-section | USDM Entity | USDM Path | Extractor | Status |
|----------------|-------------|-----------|-----------|--------|
| AE Definitions | `NarrativeContent` (sectionType=Safety) | `version.narrativeContents[]` | **NONE** | ❌ **Composer is doing extraction** |
| SAE Definitions | `NarrativeContent` (sectionType=Safety) | `version.narrativeContents[]` | **NONE** | ❌ **Composer is doing extraction** |
| AESI | `NarrativeContent` (sectionType=Safety) | `version.narrativeContents[]` | **NONE** | ❌ **Composer is doing extraction** |
| Reporting Rules | `NarrativeContent` (sectionType=Safety) | `version.narrativeContents[]` | **NONE** | ❌ **Composer is doing extraction** |
| Pregnancy | `NarrativeContent` (sectionType=Safety) | `version.narrativeContents[]` | **NONE** | ❌ **Composer is doing extraction** |

**Anti-pattern**: `_compose_safety` currently scans ALL narrative text at render time to find safety content. This should be an extractor that produces properly-tagged `NarrativeContent` items during pipeline execution.

### §10 Statistical Considerations

| M11 Sub-section | USDM Entity | USDM Path | Extractor | Status |
|----------------|-------------|-----------|-----------|--------|
| Analysis Populations | `AnalysisPopulation` | `design.analysisPopulations[]` | advanced (SAP) | ✅ OK |
| Sample Size | `StudyDesignPopulation.plannedEnrollmentNumber` | `design.population` | eligibility/metadata | ❌ Not extracted |
| Estimands | `Estimand` | `design.estimands[]` | objectives | ✅ OK |
| Statistical Methods | `ExtensionAttribute` | `design.extensionAttributes[]` | advanced (SAP) | ✅ OK |
| Interim Analysis | `ExtensionAttribute` | `design.extensionAttributes[]` | advanced (SAP) | ⚠️ Partial |

### §11 Trial Oversight ❌ MAJOR GAP

| M11 Sub-section | USDM Entity | USDM Path | Extractor | Status |
|----------------|-------------|-----------|-----------|--------|
| Regulatory Compliance | `NarrativeContent` (sectionType=Ethics) | narrative | **NONE** | ❌ No tagged content |
| Informed Consent | `NarrativeContent` | narrative | **NONE** | ❌ No tagged content |
| Data Monitoring | `NarrativeContent` | narrative | **NONE** | ❌ No tagged content |
| Committees | `Organization` (type=Committee) | `version.organizations[]` | metadata | ❌ Not extracted |
| Study Sites | `StudySite` | `design.studySites[]` | metadata | ✅ OK |

### §12 Appendix: Supporting Details

| M11 Sub-section | USDM Entity | USDM Path | Extractor | Status |
|----------------|-------------|-----------|-----------|--------|
| Country-specific | `NarrativeContent` | narrative | narrative | ⚠️ Rarely mapped |

### §13 Appendix: Glossary

| M11 Sub-section | USDM Entity | USDM Path | Extractor | Status |
|----------------|-------------|-----------|-----------|--------|
| Abbreviations | `Abbreviation` | `version.abbreviations[]` | narrative | ✅ OK |
| Terms | `NarrativeContent` | narrative | narrative | ⚠️ Partial |

### §14 References

| M11 Sub-section | USDM Entity | USDM Path | Extractor | Status |
|----------------|-------------|-----------|-----------|--------|
| References | `NarrativeContent` | narrative | narrative | ✅ OK |

---

## 3. Anti-Pattern Analysis: Composers That Extract

Two composers currently violate the architecture by performing keyword-based extraction at render time:

### `_compose_safety` (rendering/m11_renderer.py)

**Current behaviour**: Scans ALL `narrativeContents` + `narrativeContentItems` for safety keywords (adverse event, SAE, pharmacovigilance, etc.), categorizes fragments into 7 buckets, and renders them.

**Problem**: This is extraction logic embedded in a composer. If you author USDM from scratch (no narrative text), this produces nothing. The safety content should already be in properly-tagged `NarrativeContent` entities before the composer runs.

**Fix**: Create a safety content tagger in the narrative extraction phase (or a dedicated phase) that:
1. Identifies safety-related sections during PDF extraction
2. Creates `NarrativeContent` entities with `sectionType` = Safety code
3. Tags sub-sections (AE def, SAE def, AESI, reporting, pregnancy) as `NarrativeContentItem` entities linked via `childIds`
4. The composer then simply reads `NarrativeContent` where `sectionType.code` matches Safety

### `_compose_discontinuation` (rendering/m11_renderer.py)

**Current behaviour**: Scans ALL narrative text for discontinuation keywords.

**Problem**: Same as above — extraction at render time.

**Fix**: Same pattern — tag discontinuation content during extraction, composer reads tagged entities.

---

## 4. Narrative Extractor Assessment

### Current State

The narrative extractor (`extraction/narrative/extractor.py`) is the weakest link in the pipeline. Here is a frank assessment:

#### What Works

- **Full-text extraction** (`_find_section_pages`, `_extract_section_texts`): Solid. TOC-page detection, heading-pattern matching, page-range computation, header/footer stripping all work well.
- **Abbreviation extraction**: Good. LLM-based, handles truncation retries, produces proper `Abbreviation` entities.
- **Subsection splitting** (`_split_subsection_texts`): Works for well-structured protocols.

#### What Is Weak / Broken

| Issue | Severity | Detail |
|-------|----------|--------|
| **Single-pass structure extraction** | HIGH | One LLM call extracts ALL sections from ~30 pages of text. Fragile, truncation-prone, no validation. |
| **No M11-aware section typing** | HIGH | Section types use a custom `SectionType` enum with 17 values. No NCI C-codes. No alignment to M11's 14 sections. The type assignment is a simple keyword match, not a semantic classification. |
| **NarrativeContentItem schema divergence** | MEDIUM | Our `NarrativeContentItem` adds `sectionNumber` and `sectionTitle` fields that don't exist in USDM v4.0. The real schema only has `name` and `text`. Section metadata belongs on `NarrativeContent`, not items. |
| **Flat structure, no linked list** | MEDIUM | USDM's `NarrativeContent` has `previousId`, `nextId`, `childIds` for a proper document tree. We populate `childIds` but not `previousId`/`nextId`. |
| **No `displaySectionTitle`/`displaySectionNumber`** | LOW | USDM has boolean flags for display control. We don't set them. |
| **No `GovernanceDate` extraction** | HIGH | The protocol title page has approval dates, version dates, etc. USDM has `GovernanceDate` on `StudyVersion.dateValues[]`. We never extract these. |
| **No `contentItemId` linkage** | MEDIUM | `NarrativeContent.contentItemId` should point to its `NarrativeContentItem`. We use `childIds` (a list) instead, which is also valid but different. |

#### Verdict: Needs Significant Enhancement, Not Full Rewrite

The text extraction backbone is solid. What needs work is:
1. **Section classification** — replace custom enum with M11-aligned typing using NCI C-codes
2. **Population demographics extraction** — add to eligibility phase prompts
3. **GovernanceDate extraction** — add to metadata phase
4. **M11-aware content tagging** — tag safety, discontinuation, oversight sections during extraction, not at render time

---

## 5. USDM Entities We Have But Don't Fully Populate

These are entities that exist in the USDM v4.0 schema AND in our output, but where we're leaving fields empty that M11 needs.

### 5.1 `StudyDesignPopulation` — 4 missing fields

| Field | USDM Type | M11 Use | Current Value | Fix |
|-------|-----------|---------|---------------|-----|
| `plannedEnrollmentNumber` | `QuantityRange` | §1.1.2 Number of Participants | ❌ Not set | Extract from eligibility/synopsis text |
| `plannedCompletionNumber` | `QuantityRange` | §10 Sample Size | ❌ Not set | Extract from statistics section |
| `plannedAge` | `Range` | §1.1.2 Population Age, §5 | ❌ Not set | Extract from inclusion criteria age range |
| `plannedSex` | `Code` (0..2) | §5 Sex eligibility | ❌ Not set | Extract from inclusion criteria |

### 5.2 `GovernanceDate` — Not created at all

USDM has `StudyVersion.dateValues[]` as a list of `GovernanceDate` entities. Each has:
- `name`: e.g. "Sponsor Approval Date", "Protocol Version Date"
- `type`: Code with NCI C-code
- `dateValue`: actual date
- `geographicScopes`: geographic applicability

We never create these. The metadata extractor should extract protocol dates from the title page.

### 5.3 `Organization.legalAddress` — Not populated

We extract sponsor `Organization` but don't fill the `legalAddress` (an `Address` entity). Available on the title page of most protocols.

### 5.4 `InterventionalStudyDesign.characteristics` — Not populated

USDM has `characteristics` (list of `Code`) on the study design for things like:
- Adaptive design indicator
- Master protocol indicator  
- Platform trial indicator

We currently hardcode these as "No" in the synopsis composer. Should be extracted from the design description and stored as coded characteristics.

### 5.5 `Masking.isMasked` and blinding schema

Our extractor creates `Masking` entities in `maskingRoles` but doesn't set `blindingSchema` (a Code on the design level — actually stored as an extension or derived from masking). The blinding schema (open-label, single-blind, double-blind) should be extracted and stored.

### 5.6 `BiospecimenRetention` — Not extracted

USDM has `design.biospecimenRetentions[]` for §8 biospecimen information. We never create these.

---

## 6. Extractor Remediation Plan

### Phase 1: Population Demographics (Highest Impact)

**Target**: Fix G1, G4, G5 — populate `StudyDesignPopulation` fully.

**Where to fix**: `pipeline/phases/eligibility.py` and/or `extraction/eligibility/extractor.py`

**What to add to the eligibility extraction prompt**:
```
Also extract the following population-level fields:
- plannedEnrollmentNumber: The planned number of participants (e.g., "approximately 24 participants")
- plannedAge: The age range {minValue, maxValue, unit} (e.g., "18 to 75 years")
- plannedSex: The sex eligibility criteria (Male, Female, or Both)
```

**What to add to the combine step** (`eligibility.py` combine method):
```python
population = study_design.get('population', {})
population['plannedEnrollmentNumber'] = {...}  # QuantityRange
population['plannedAge'] = {...}               # Range
population['plannedSex'] = [...]               # list of Code
```

**Impact**: Resolves 1 conformance ERROR (Number of Participants) + 2 HIGH gaps. Synopsis completeness jumps significantly.

### Phase 2: Governance Dates

**Target**: Fix G2, G10 — extract protocol dates into `GovernanceDate` entities.

**Where to fix**: `pipeline/phases/metadata.py`

**What to extract**: 
- Sponsor approval date → `GovernanceDate(type=C215XXX, name="Sponsor Approval Date")`
- Protocol version date → `GovernanceDate(type=C215XXX, name="Protocol Version Date")`

**What to add to combine step**:
```python
study_version['dateValues'] = [governance_date.to_dict()]
```

**Impact**: Resolves 1 conformance ERROR (Sponsor Approval). Title page completeness.

### Phase 3: Blinding and Randomization

**Target**: Fix G6, G7 — extract blinding schema and randomization type.

**Where to fix**: `pipeline/phases/studydesign.py`

**What to add to design extraction prompt**:
```
Also extract:
- blindingSchema: Open-label | Single-blind | Double-blind | Triple-blind
- randomizationType: Randomized | Non-randomized
- studyDesignCharacteristics: [Adaptive, Master Protocol, Platform, etc.]
```

**Impact**: Synopsis fields complete. Design section richer.

### Phase 4: M11-Aware Narrative Tagging

**Target**: Fix the safety/discontinuation anti-pattern — tag content at extraction time.

**Where to fix**: `extraction/narrative/extractor.py` OR new `pipeline/phases/narrative_tagger.py`

**Approach**: After the narrative extractor produces `NarrativeContent` sections with full text, run a post-processing step that:

1. Classifies each section's `sectionType` using M11-aligned codes (not just the basic enum)
2. For sections that map to M11 §7 (Discontinuation) or §9 (Safety), creates properly-tagged sub-section `NarrativeContentItem` entities
3. Sets `sectionNumber` to the M11 section number, not just the source protocol number

This allows the composers to simply read tagged content instead of re-scanning everything.

**Revised composer pattern**:
```python
def _compose_safety(usdm: Dict) -> str:
    """Read NarrativeContent entities tagged as Safety (M11 §9)."""
    # Find NarrativeContent where sectionType matches Safety
    # Read their text and childIds for sub-sections
    # Format as prose — NO keyword scanning
```

### Phase 5: Product Linkage and Sponsor Address

**Target**: Fix G8 (product linkage), G9 (sponsor address).

**Where to fix**: 
- `pipeline/phases/interventions.py` — ensure every `StudyIntervention` links to `AdministrableProduct` via `productIds`
- `pipeline/phases/metadata.py` — extract sponsor `legalAddress` from title page

---

## 7. NarrativeContent Schema Alignment

### Current vs Correct

| Field | USDM v4.0 Spec | Our Current Schema | Fix Needed |
|-------|----------------|-------------------|------------|
| `name` | ✅ Required | ✅ Has it | — |
| `sectionNumber` | ✅ Optional (0..1) | ✅ Has it | — |
| `sectionTitle` | ✅ Optional (0..1) | ✅ Has it | — |
| `displaySectionTitle` | ✅ Required (boolean) | ❌ Missing | Add, default `true` |
| `displaySectionNumber` | ✅ Required (boolean) | ❌ Missing | Add, default `true` |
| `contentItemId` | ✅ Optional (0..1, Ref) | ❌ Missing | Add |
| `previousId` | ✅ Optional (0..1, Ref) | ❌ Missing | Add — linked list |
| `nextId` | ✅ Optional (0..1, Ref) | ❌ Missing | Add — linked list |
| `childIds` | ✅ Optional (0..*, Ref) | ✅ Has it | — |

### NarrativeContentItem — Current vs Correct

| Field | USDM v4.0 Spec | Our Current Schema | Fix Needed |
|-------|----------------|-------------------|------------|
| `name` | ✅ Required | ✅ Has it | — |
| `text` | ✅ Required | ✅ Has it | — |
| `sectionNumber` | ❌ Not in spec | ⚠️ We add it | Remove or move to extension |
| `sectionTitle` | ❌ Not in spec | ⚠️ We add it | Remove or move to extension |
| `order` | ❌ Not in spec | ⚠️ We add it | Remove — use `previousId`/`nextId` on parent |

**Action**: Update `extraction/narrative/schema.py` to:
1. Add `displaySectionTitle` and `displaySectionNumber` to `NarrativeContent`
2. Add `previousId` and `nextId` to `NarrativeContent`
3. Move `sectionNumber`/`sectionTitle` off `NarrativeContentItem` — these are parent metadata, use `name` for the item title
4. Remove `order` field — ordering comes from linked list

---

## 8. Summary: What Goes Where

### Extractors to Fix (in priority order)

| Priority | Extractor | What to Add | M11 Sections Impacted |
|----------|-----------|-------------|----------------------|
| **P1** | `eligibility` | `plannedEnrollmentNumber`, `plannedAge`, `plannedSex` on `StudyDesignPopulation` | §1 Synopsis, §5 Population |
| **P2** | `metadata` | `GovernanceDate` entities, sponsor `Address` | §1 Title Page |
| **P3** | `studydesign` | `blindingSchema`, `randomizationType`, `characteristics` | §1 Synopsis, §4 Design |
| **P4** | `narrative` (enhance) | M11-aware `sectionType` tagging, safety/discontinuation/oversight section classification | §7, §9, §11 |
| **P5** | `interventions` | Complete `AdministrableProduct` linkage via `productIds` | §6 Intervention |

### Composers to Refactor (after extractors are fixed)

| Composer | Current Pattern | Target Pattern |
|----------|----------------|----------------|
| `_compose_safety` | Keyword scan at render time | Read `NarrativeContent(sectionType=Safety)` |
| `_compose_discontinuation` | Keyword scan at render time | Read `NarrativeContent(sectionType=Discontinuation)` |
| `_compose_synopsis` | Mix of entity read + hardcoded defaults | Pure entity read from `StudyDesignPopulation`, `StudyDesign.characteristics`, `GovernanceDate` |

### New Extractors Needed

| Extractor | USDM Entities | M11 Section |
|-----------|---------------|-------------|
| None needed — existing phases cover the entities. The work is enhancing existing extractor prompts and combine steps. | | |

---

## 9. Future: USDM-First Authoring Readiness

Once the extractor remediation is complete, the composers become a **pure USDM → M11 prose layer**. This means:

1. **Semantic editor** creates/edits USDM entities directly
2. **No source PDF needed** — all data lives in `protocol_usdm.json`
3. **Composers generate M11 document** from entities alone
4. **Conformance validator** checks completeness against M11 requirements

The only prerequisite is that the USDM data is complete. The extractors are just one way to populate it. The semantic editor is another. An API is a third.

```
  Extraction Path           Authoring Path           API Path
  ┌──────────┐              ┌──────────────┐         ┌──────────┐
  │ PDF →    │              │ Semantic     │         │ External │
  │ Pipeline │              │ Editor UI   │         │ System   │
  └────┬─────┘              └──────┬───────┘         └────┬─────┘
       │                           │                      │
       └──────────┬────────────────┘──────────────────────┘
                  │
                  ▼
           protocol_usdm.json
                  │
                  ▼
           M11 Composers → protocol_m11.docx
```

This is the endgame architecture. The extractor fixes in this document get us there.

---

## 10. Extension → USDM Promotion Mechanism (Implemented)

A key architectural requirement is that data extracted by later phases (e.g., SAP) can
**promote** back into core USDM entities created by earlier phases (e.g., eligibility).

### The Problem

The SAP extractor produces `SampleSizeCalculation.targetSampleSize` but the orchestrator
stored it as an `ExtensionAttribute` on the study design. Meanwhile,
`StudyDesignPopulation.plannedEnrollmentNumber` remained empty — the exact field that
the synopsis composer and conformance validator need.

### The Solution: `_promote_extensions_to_usdm()`

Added to `pipeline/orchestrator.py`, this function runs **after all phase combines and
conditional integrations** but **before saving** the final USDM JSON. It applies
promotion rules that are each a no-op if the target already has a value (respecting
explicit extraction over inference).

```
  Phase Combines     Conditional     Reconciliation    PROMOTION     Save
  (eligibility,      (SAP, sites,    (epochs,          ─────────►    protocol_usdm.json
   metadata, ...)    execution)       encounters)
       │                  │                │                │
       ▼                  ▼                ▼                ▼
  study_design      extensions       cross-refs      extension data
  population        added            fixed           promoted to
  (maybe empty)                                      core USDM fields
```

### Current Promotion Rules

| # | Source | Target USDM Field | Condition |
|---|--------|-------------------|-----------|
| 1 | SAP `sampleSizeCalculations[].targetSampleSize` | `population.plannedEnrollmentNumber` | Only if eligibility didn't extract it |
| 2 | SAP `sampleSizeCalculations[].plannedCompleters` | `population.plannedCompletionNumber` | Only if not already set |
| 3 | Eligibility criteria text (regex) | `population.plannedSex` | Inferred if not explicitly extracted |
| 4 | Eligibility criteria text (regex) | `population.plannedAge` | Inferred from "aged ≥18", "18-75 years" patterns |

### How to Add New Rules

Add a new block in `_promote_extensions_to_usdm()`:
```python
# --- Rule N: <Source> → <Target> ---
if not population.get('<target_field>'):
    value = _extract_<source>_from_extensions(design)
    if value is not None:
        population['<target_field>'] = value
        promotions += 1
```

### Design Principles

- **No-op if target exists**: Explicit extraction always wins over inference
- **SAP wins over eligibility**: SAP provides the authoritative sample size
- **Inference is last resort**: Regex-based age/sex inference only runs if no extractor populated the field
- **Idempotent**: Running promotion twice produces the same result
- **Logged**: Every promotion is logged with source and target for traceability

---

## 11. Implementation Status

### Completed (P12)

| Item | Status | Files Changed |
|------|--------|---------------|
| `StudyDesignPopulation` schema aligned to USDM v4.0 | ✅ | `extraction/eligibility/schema.py` |
| Population parser handles all LLM response formats | ✅ | `extraction/eligibility/extractor.py` |
| Synopsis composer reads USDM v4.0 field names | ✅ | `rendering/m11_renderer.py` |
| Conformance validator checks USDM v4.0 fields | ✅ | `validation/m11_conformance.py` |
| Extension→USDM promotion mechanism | ✅ | `pipeline/orchestrator.py` |
| SAP sample size → population promotion | ✅ | `pipeline/orchestrator.py` |
| Age/Sex inference from criteria text | ✅ | `pipeline/orchestrator.py` |
| Regression tests pass | ✅ | `tests/test_m11_regression.py` |

### Pending

| Item | Priority | Files to Change |
|------|----------|----------------|
| GovernanceDate extraction (metadata phase) | HIGH | `pipeline/phases/metadata.py` |
| Sponsor Address extraction | HIGH | `pipeline/phases/metadata.py` |
| blindingSchema / randomizationType | MEDIUM | `pipeline/phases/studydesign.py` |
| M11-aware narrative section tagging | MEDIUM | `extraction/narrative/extractor.py` |
| AdministrableProduct linkage | LOW | `pipeline/phases/interventions.py` |
