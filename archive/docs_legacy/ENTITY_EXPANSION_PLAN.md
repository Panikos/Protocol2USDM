# USDM Entity Expansion Plan

## Current Status (Updated: Nov 2025)
- **Covered:** 55/87 entities (63.2%)
- **Target:** Full USDM 4.0 coverage where source data is available

## Implementation Status

| Phase | Status | Entities Added |
|-------|--------|----------------|
| Phase 1-8 | ✅ Complete | 39 core entities |
| Phase 9: Biomedical | 🔮 Future Roadmap | Special approach planned |
| Phase 10: Procedures | ✅ Complete | Procedure, MedicalDevice, Ingredient, Strength |
| Phase 11: Scheduling | ✅ Complete | Timing, Condition, TransitionRule, ScheduleTimelineExit |
| Phase 14: SAP | ✅ Complete | AnalysisPopulation, Characteristic (conditional) |
| Phase 15: Sites | ✅ Complete | StudySite, StudyRole, AssignedPerson (conditional) |

---

## Missing Entities by Source Requirement

### Phase 9: Biomedical Concepts (from Protocol)
**Source:** Protocol PDF (can extract from SoA activities, endpoints, eligibility)
**Entities:**
| Entity | Description | Extraction Strategy |
|--------|-------------|---------------------|
| `BiomedicalConcept` | Lab tests, vital signs, assessments | Parse from Activity names/descriptions |
| `BiomedicalConceptCategory` | Grouping (Safety, Efficacy, PK) | Infer from activity groups |
| `BiomedicalConceptProperty` | Properties like units, ranges | Extract from footnotes/text |
| `BiomedicalConceptSurrogate` | Surrogate markers | Extract from endpoints |

### Phase 10: Procedures & Devices (from Protocol)
**Source:** Protocol PDF
**Entities:**
| Entity | Description | Extraction Strategy |
|--------|-------------|---------------------|
| `Procedure` | Clinical procedures linked to activities | Extract from SoA activity details |
| `MedicalDevice` | Devices used in study | Extract from interventions section |
| `MedicalDeviceIdentifier` | Device identifiers | Extract with MedicalDevice |
| `Ingredient` | Drug ingredients | Extract from IMP description |
| `Strength` | Drug strength/concentration | Extract from dosing info |

### Phase 11: Scheduling Logic (from Protocol)
**Source:** Protocol PDF (complex protocols only)
**Entities:**
| Entity | Description | Extraction Strategy |
|--------|-------------|---------------------|
| `Timing` | Timing constraints (windows, offsets) | Extract from visit windows |
| `TransitionRule` | Rules for moving between epochs | Extract from study design narrative |
| `Condition` | Conditional logic | Extract from branching protocols |
| `ConditionAssignment` | Condition-to-arm assignments | Extract from adaptive designs |
| `ScheduleTimelineExit` | Early termination criteria | Extract from discontinuation rules |
| `ScheduledDecisionInstance` | Decision points in timeline | Extract from adaptive protocols |

### Phase 12: Document Structure (from Protocol)
**Source:** Protocol PDF
**Entities:**
| Entity | Description | Extraction Strategy |
|--------|-------------|---------------------|
| `DocumentContentReference` | References to protocol sections | Parse document structure |
| `CommentAnnotation` | Annotations/notes | Extract footnotes, comments |
| `StudyDefinitionDocumentVersion` | Version info | Extract from cover page |

### Phase 13: Amendment Details (from Protocol)
**Source:** Protocol PDF (if amendments present)
**Entities:**
| Entity | Description | Extraction Strategy |
|--------|-------------|---------------------|
| `StudyAmendmentImpact` | Impact of amendments | Extract from amendment summary |
| `StudyAmendmentReason` | Reasons for amendments | Extract from amendment rationale |
| `StudyChange` | Specific changes made | Extract from change log |

---

## Conditional Phases (Require Additional Sources)

### Phase 14: Analysis Populations (from SAP)
**Source:** Statistical Analysis Plan (SAP) PDF
**CLI Flag:** `--sap <path>`
**Entities:**
| Entity | Description | Extraction Strategy |
|--------|-------------|---------------------|
| `AnalysisPopulation` | ITT, PP, Safety populations | Extract from SAP Section 3 |
| `PopulationDefinition` | Population criteria | Extract population definitions |
| `Characteristic` | Baseline characteristics | Extract from demographics table |

### Phase 15: Site & Personnel (from Site List)
**Source:** Site List CSV/Excel or separate document
**CLI Flag:** `--sites <path>`
**Entities:**
| Entity | Description | Extraction Strategy |
|--------|-------------|---------------------|
| `StudySite` | Investigator sites | Parse site list |
| `StudyRole` | Roles (PI, Sub-I, Coordinator) | Parse from site list |
| `AssignedPerson` | Personnel assignments | Parse from site list |
| `PersonName` | Person name structure | Parse with AssignedPerson |
| `SubjectEnrollment` | Enrollment by site | Parse enrollment data |

### Phase 16: eCOA/CDASH Mapping (from eCOA Spec)
**Source:** eCOA Specification or CDASH mapping
**CLI Flag:** `--ecoa <path>`
**Entities:**
| Entity | Description | Extraction Strategy |
|--------|-------------|---------------------|
| `ResponseCode` | eCOA response options | Parse from questionnaire specs |
| `ParameterMap` | CDASH variable mapping | Parse from CDASH spec |
| `SyntaxTemplate` | Template definitions | Parse from CRF annotations |
| `SyntaxTemplateDictionary` | Template dictionary | Parse with SyntaxTemplate |

---

## Wrapper/Base Types (No Extraction Needed)
These are used implicitly as containers:
- `Study` - Top-level wrapper
- `StudyVersion` - Version container
- `StudyDesign` - Design container (we use InterventionalStudyDesign)
- `ScheduledInstance` - Base class for ScheduledActivityInstance
- `Identifier` - Generic identifier (we use specific types)

---

## Implementation Priority

### Priority 1: Protocol-Extractable (Phases 9-13)
These can be added immediately with LLM extraction from protocol PDF.

### Priority 2: Conditional Sources (Phases 14-16)
Add CLI flags and conditional logic:
```bash
python main_v2.py protocol.pdf --full-protocol \
    --sap sap.pdf \
    --sites sites.xlsx \
    --ecoa ecoa_spec.pdf
```

---

## New CLI Arguments

```python
parser.add_argument("--sap", help="Path to SAP PDF for analysis population extraction")
parser.add_argument("--sites", help="Path to site list (CSV/Excel) for site extraction")
parser.add_argument("--ecoa", help="Path to eCOA specification for response code extraction")
```

---

## File Structure for New Phases

```
extraction/
├── biomedical/           # Phase 9
│   ├── __init__.py
│   ├── extractor.py
│   ├── prompts.py
│   └── schema.py
├── procedures/           # Phase 10
│   ├── __init__.py
│   ├── extractor.py
│   ├── prompts.py
│   └── schema.py
├── scheduling/           # Phase 11
│   ├── __init__.py
│   ├── extractor.py
│   ├── prompts.py
│   └── schema.py
├── document_structure/   # Phase 12
│   ├── __init__.py
│   ├── extractor.py
│   ├── prompts.py
│   └── schema.py
├── amendments/           # Phase 13
│   ├── __init__.py
│   ├── extractor.py
│   ├── prompts.py
│   └── schema.py
├── analysis_populations/ # Phase 14 (conditional)
│   ├── __init__.py
│   ├── extractor.py
│   ├── prompts.py
│   └── schema.py
├── sites/                # Phase 15 (conditional)
│   ├── __init__.py
│   ├── extractor.py
│   └── schema.py
└── ecoa/                 # Phase 16 (conditional)
    ├── __init__.py
    ├── extractor.py
    └── schema.py
```

---

## Summary

| Phase | Entities | Source | Priority |
|-------|----------|--------|----------|
| 9. Biomedical | 4 | Protocol | High |
| 10. Procedures | 5 | Protocol | High |
| 11. Scheduling | 6 | Protocol | Medium |
| 12. Document | 3 | Protocol | Low |
| 13. Amendments | 3 | Protocol | Medium |
| 14. Analysis | 3 | SAP | Conditional |
| 15. Sites | 5 | Site List | Conditional |
| 16. eCOA | 4 | eCOA Spec | Conditional |

**Total new entities:** 33 (bringing coverage to 72/87 = 83%)
**Remaining 15:** Wrapper types and niche entities rarely needed
