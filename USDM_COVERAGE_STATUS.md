# USDM v4.0 Entity Coverage Status

**Last Updated:** 2025-11-29  
**Version:** 6.3.0  
**Coverage:** 62/87 entities (71.3%)

---

## Implemented Phases

### From Protocol PDF (Automatic)

| Phase | Entities | CLI Flag | Status |
|-------|----------|----------|--------|
| **SoA Extraction** | Activity, ScheduledActivityInstance, Encounter, StudyEpoch, ScheduleTimeline, CommentAnnotation | `--soa` | ✅ |
| **Phase 1: Eligibility** | EligibilityCriterion, EligibilityCriterionItem, StudyDesignPopulation | `--eligibility` | ✅ |
| **Phase 2: Metadata** | StudyTitle, StudyIdentifier, Organization, Indication, StudyPhase | `--metadata` | ✅ |
| **Phase 3: Objectives** | Objective, Endpoint, Estimand, IntercurrentEvent | `--objectives` | ✅ |
| **Phase 4: Study Design** | InterventionalStudyDesign, StudyArm, StudyCell, StudyCohort | `--studydesign` | ✅ |
| **Phase 5: Interventions** | StudyIntervention, AdministrableProduct, Administration, Substance | `--interventions` | ✅ |
| **Phase 7: Narrative** | NarrativeContent, NarrativeContentItem, Abbreviation, StudyDefinitionDocument | `--narrative` | ✅ |
| **Phase 8: Advanced** | StudyAmendment, GeographicScope, Country | `--advanced` | ✅ |
| **Phase 10: Procedures** | Procedure, MedicalDevice, MedicalDeviceIdentifier, Ingredient, Strength | `--procedures` | ✅ |
| **Phase 11: Scheduling** | Timing, Condition, TransitionRule, ScheduleTimelineExit, ConditionAssignment | `--scheduling` | ✅ |
| **Phase 12: Document Structure** | DocumentContentReference, CommentAnnotation, StudyDefinitionDocumentVersion | `--docstructure` | ✅ |
| **Phase 13: Amendment Details** | StudyAmendmentImpact, StudyAmendmentReason, StudyChange | `--amendmentdetails` | ✅ |

### From Additional Sources (Conditional)

| Phase | Entities | CLI Flag | Source Required |
|-------|----------|----------|-----------------|
| **Phase 14: SAP** | AnalysisPopulation, Characteristic, PopulationDefinition | `--sap <path>` | SAP PDF |
| **Phase 15: Sites** | StudySite, StudyRole, AssignedPerson, PersonName | `--sites <path>` | Site List (CSV/Excel) |

---

## Parked for Future

### Phase 9: Biomedical Concepts 🔮

**Entities:** BiomedicalConcept, BiomedicalConceptCategory, BiomedicalConceptProperty, BiomedicalConceptSurrogate

**Reason:** Special approach planned - will integrate with CDISC BC library for standardized concept mapping.

---

## Not Yet Implemented

### Phase 16: eCOA/CDASH Mapping

| Entity | Description | Source |
|--------|-------------|--------|
| `ResponseCode` | Questionnaire response options | **eCOA Specification PDF** |
| `ParameterMap` | CDASH variable mappings | **CDASH Annotation Spec** |
| `SyntaxTemplate` | CRF template definitions | **CRF Annotations** |
| `SyntaxTemplateDictionary` | Template dictionary | **CRF Annotations** |

**Priority:** Low  
**Value:** EDC/eCOA system integration  
**Requires:** Separate eCOA specification document (`--ecoa <path>`)

---

## Source Summary

| Source Type | Phases | Availability |
|-------------|--------|--------------|
| **Protocol PDF** | 1-5, 7-8, 10-13 | Always available |
| **SAP PDF** | 14 | Often available |
| **Site List** | 15 | Sponsor-internal |
| **eCOA Spec** | 16 | Sponsor-internal |

---

## Usage

### Full Protocol Extraction
```bash
python main_v2.py protocol.pdf --full-protocol
```

### With SAP
```bash
python main_v2.py protocol.pdf --full-protocol --sap sap.pdf
```

### With Sites
```bash
python main_v2.py protocol.pdf --full-protocol --sites sites.xlsx
```

### All Sources
```bash
python main_v2.py protocol.pdf --full-protocol --sap sap.pdf --sites sites.xlsx
```

---

## Wrapper/Implicit Types (No Extraction Needed)

These are structural containers used implicitly:
- `Study` - Root container
- `StudyVersion` - Version wrapper
- `StudyDesign` - Design container (we use InterventionalStudyDesign)
- `ScheduledInstance` - Base class
- `Identifier` - Generic (we use specific types)
- `QuantityRange`, `Range` - Value containers
- `AliasCode`, `Code` - Coding structures

---

## Next Steps

1. **Phase 9: Biomedical Concepts** - Pending special integration with CDISC BC library
2. **Phase 16: eCOA/CDASH** - Implement when eCOA spec integration required

## Recent Additions (v6.3.0)

- **NCI EVS Enrichment**: Entities enriched with official NCI codes via EVS API (`--enrich`)
- **CDISC CORE Integration**: Local conformance engine with cache management (`--conformance`)
- **Provenance ID Sync**: IDs now consistent between data and provenance for accurate viewer display
- **Idempotent UUID Generation**: Entity IDs generated once and reused for consistency
- **CommentAnnotation**: SoA footnotes stored in `StudyDesign.notes`
- **Activity hierarchy**: Groups use USDM v4.0 `childIds` pattern
