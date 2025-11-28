# USDM Expansion Plan

**Created:** 2025-11-26  
**Status:** In Progress

---

## Overview

Expanding Protocol2USDM beyond Schedule of Activities (SoA) to cover the full USDM v4.0 model (~70 entities).

## Current Coverage (SoA-focused) ✅

| Entity | Status | Source |
|--------|--------|--------|
| Activity | ✅ Done | SoA Table |
| PlannedTimepoint | ✅ Done | SoA Table |
| ActivityTimepoint | ✅ Done | SoA Table |
| ActivityGroup | ✅ Done | SoA Table |
| Encounter | ✅ Done | SoA Table |
| Epoch (StudyEpoch) | ✅ Done | SoA Table |
| StudyArm | 🟡 Partial | Inferred |
| StudyElement | 🟡 Partial | Inferred |

---

## Expansion Phases

### Phase 1: Eligibility Criteria
*Source: Section 4-5 of protocols (Inclusion/Exclusion)*

| Entity | Description | Complexity |
|--------|-------------|------------|
| `EligibilityCriterion` | Individual I/E criterion with category | Medium |
| `EligibilityCriterionItem` | Reusable text of criterion | Low |
| `StudyDesignPopulation` | Links population to criteria | Medium |

**Rationale:**
- Well-structured in protocols (numbered lists)
- Clear boundaries (Inclusion vs Exclusion sections)
- Foundation for population-level entities
- High regulatory value (critical for CT.gov)

---

### Phase 2: Study Identity & Metadata ⬅️ CURRENT
*Source: Title page, Section 1-2*

| Entity | Description | Complexity | Status |
|--------|-------------|------------|--------|
| `Study` | Root study object | Low | 🔄 |
| `StudyVersion` | Protocol version info | Low | 🔄 |
| `StudyTitle` | Official/brief titles | Low | 🔄 |
| `StudyIdentifier` | NCT numbers, sponsor IDs | Low | 🔄 |
| `Organization` | Sponsor, CRO | Medium | 🔄 |
| `StudyRole` | Sponsor, PI roles | Medium | 🔄 |
| `Indication` | Disease/condition | Medium | 🔄 |

**Rationale:**
- Simple extraction from title page
- Foundational metadata other entities reference
- Required for regulatory submissions

---

### Phase 3: Objectives & Endpoints
*Source: Section 2-3 (Synopsis, Objectives)*

| Entity | Description | Complexity |
|--------|-------------|------------|
| `Objective` | Primary/Secondary/Exploratory | Medium |
| `Endpoint` | Outcome measures linked to objectives | Medium |
| `Estimand` | ICH E9(R1) framework | High |
| `IntercurrentEvent` | Events affecting estimands | High |

**Rationale:**
- Usually tabular or clearly enumerated
- Direct link to regulatory requirements
- Builds on population (Phase 1)

---

### Phase 4: Study Design Structure
*Source: Section 3 (Design), Synopsis*

| Entity | Description | Complexity |
|--------|-------------|------------|
| `InterventionalStudyDesign` | Design wrapper (vs Observational) | Medium |
| `StudyArm` | Treatment arms | Medium |
| `StudyCell` | Arm × Epoch matrix | Medium |
| `StudyCohort` | Sub-populations | Medium |

**Rationale:**
- Depends on Epochs (done) + Population (Phase 1)
- Structures the arm/epoch relationships
- Foundation for intervention mapping

---

### Phase 5: Interventions & Products
*Source: Section 5-6 (Investigational Product)*

| Entity | Description | Complexity |
|--------|-------------|------------|
| `StudyIntervention` | Treatment concept | Medium |
| `AdministrableProduct` | Drug product details | High |
| `Administration` | Dose, route, frequency | High |
| `MedicalDevice` | Device info if applicable | Medium |
| `Substance` | Active ingredient | Medium |

**Rationale:**
- Complex pharmaceutical details
- Requires domain expertise prompts
- Builds on study design structure

---

### Phase 6: Biomedical Concepts
*Source: Assessments in SoA + Procedures sections*

| Entity | Description | Complexity |
|--------|-------------|------------|
| `BiomedicalConcept` | Standardized assessment concept | High |
| `BiomedicalConceptProperty` | Properties of BC | High |
| `BiomedicalConceptCategory` | Groupings | Medium |

**Rationale:**
- Requires CDISC BC library integration
- Links Activities to standard definitions
- Advanced interoperability

---

### Phase 7: Document Structure
*Source: Protocol TOC, narrative sections*

| Entity | Description | Complexity |
|--------|-------------|------------|
| `NarrativeContent` | Section structure | Medium |
| `NarrativeContentItem` | Section text | Medium |
| `Abbreviation` | Abbreviation definitions | Low |
| `StudyDefinitionDocument` | Protocol document metadata | Low |

**Rationale:**
- Enables section-level traceability
- Supports DDF workflows
- Comprehensive protocol representation

---

### Phase 8: Advanced Entities
*Source: Various*

| Entity | Description | Complexity |
|--------|-------------|------------|
| `StudyAmendment` | Protocol amendments | High |
| `Condition` | Conditional logic | High |
| `TransitionRule` | Visit/epoch transitions | High |
| `GeographicScope` | Regional applicability | Medium |

---

## Implementation Architecture

Each phase follows this module pattern:

```
extraction/
├── pipeline.py              # Main orchestrator
├── eligibility/             # Phase 1
│   ├── __init__.py
│   ├── extractor.py         # LLM extraction logic
│   ├── prompts.py           # Phase-specific prompts
│   └── schema.py            # Pydantic models
├── metadata/                # Phase 2
│   ├── __init__.py
│   ├── extractor.py
│   ├── prompts.py
│   └── schema.py
├── objectives/              # Phase 3
└── ...
```

Each phase module:
1. **Finds relevant pages** (section detection)
2. **Extracts with LLM** (vision+text pattern)
3. **Validates** against USDM schema
4. **Merges** into unified output

---

## Progress Log

| Date | Phase | Status | Notes |
|------|-------|--------|-------|
| 2025-11-26 | Phase 2 | ✅ Complete | Study Identity & Metadata |
| 2025-11-27 | Phase 1 | ✅ Complete | Eligibility Criteria (8 inclusion, 11 exclusion extracted) |
| 2025-11-27 | Phase 3 | ✅ Complete | Objectives & Endpoints (1 primary, 7 secondary, 3 exploratory) |
| 2025-11-27 | Phase 4 | ✅ Complete | Study Design (Open Label, 2 arms, 2 cohorts) |
| 2025-11-27 | Phase 5 | ✅ Complete | Interventions (ALXN1840, 3 dosing regimens, bis-choline tetrathiomolybdate) |
| 2025-11-27 | Phase 6 | ⏸️ Parked | Biomedical Concepts (will integrate from related project) |
| 2025-11-27 | Phase 7 | ✅ Complete | Narrative Structure (8 sections, 9 abbreviations) |
| 2025-11-27 | Phase 8 | ✅ Complete | Advanced Entities (4 amendments, 1 country, geographic scope) |
| 2025-11-27 | Integration | ✅ Complete | Pipeline integration + Streamlit viewer expansion |

## Files Created

### Phase 2: Study Metadata
```
extraction/metadata/
├── __init__.py          # Module exports
├── schema.py            # USDM models (StudyTitle, Organization, Indication, etc.)
├── prompts.py           # LLM extraction prompts
└── extractor.py         # Main extraction logic

extract_metadata.py      # CLI entry point
```

### Phase 1: Eligibility Criteria
```
extraction/eligibility/
├── __init__.py          # Module exports
├── schema.py            # USDM models (EligibilityCriterion, StudyDesignPopulation)
├── prompts.py           # LLM extraction prompts  
└── extractor.py         # Main extraction logic with auto page detection

extract_eligibility.py   # CLI entry point
```

### Phase 3: Objectives & Endpoints
```
extraction/objectives/
├── __init__.py          # Module exports
├── schema.py            # USDM models (Objective, Endpoint, Estimand, IntercurrentEvent)
├── prompts.py           # LLM extraction prompts
└── extractor.py         # Main extraction logic with auto page detection

extract_objectives.py    # CLI entry point
```

### Phase 4: Study Design Structure
```
extraction/studydesign/
├── __init__.py          # Module exports
├── schema.py            # USDM models (StudyArm, StudyCell, StudyCohort, InterventionalStudyDesign)
├── prompts.py           # LLM extraction prompts
└── extractor.py         # Main extraction logic with auto page detection

extract_studydesign.py   # CLI entry point
```

### Phase 5: Interventions & Products
```
extraction/interventions/
├── __init__.py          # Module exports
├── schema.py            # USDM models (StudyIntervention, AdministrableProduct, Administration, Substance)
├── prompts.py           # LLM extraction prompts
└── extractor.py         # Main extraction logic with auto page detection

extract_interventions.py # CLI entry point
```

### Phase 7: Narrative Structure
```
extraction/narrative/
├── __init__.py          # Module exports
├── schema.py            # USDM models (NarrativeContent, Abbreviation, StudyDefinitionDocument)
├── prompts.py           # LLM extraction prompts
└── extractor.py         # Main extraction logic with auto page detection

extract_narrative.py     # CLI entry point
```

### Phase 8: Advanced Entities
```
extraction/advanced/
├── __init__.py          # Module exports
├── schema.py            # USDM models (StudyAmendment, GeographicScope, Country, StudySite)
├── prompts.py           # LLM extraction prompts
└── extractor.py         # Main extraction logic with auto page detection

extract_advanced.py      # CLI entry point
```

### Core Utilities
```
core/
├── pdf_utils.py         # PDF text/image extraction utilities
└── llm_client.py        # Added call_llm, call_llm_with_image
```

### Pipeline Integration
```
main_v2.py               # Updated with expansion flags
                         # --full-protocol, --expansion-only
                         # --metadata, --eligibility, --objectives, etc.
                         # Combined output: full_usdm.json

soa_streamlit_viewer.py  # Updated with Protocol Expansion Data section
                         # Tabbed viewing for all expansion phases
```

