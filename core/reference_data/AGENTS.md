# USDM Controlled Terminology — Reference Data

## Source
- **File**: `USDM_CT.xlsx`
- **Origin**: https://github.com/cdisc-org/DDF-RA/blob/main/Deliverables/CT/USDM_CT.xlsx
- **Standard**: USDM v4.0 (CDISC DDF-RA)
- **Downloaded**: 2026-02-11

## Purpose
This file contains the official CDISC controlled terminology (CT) for the Unified Study Definitions Model (USDM). It is the authoritative source for NCI C-codes used throughout the pipeline when populating coded fields on USDM entities.

**Always prefer codes from this file over NCI Thesaurus lookups** — the USDM CT is a curated subset with specific decode values that may differ from the broader NCI Thesaurus.

## Spreadsheet Structure
- **Sheet 1**: `DDF Entities&Attributes` — entity/attribute metadata
- **Sheet 2**: `DDF valid value sets` — the codelists (columns: Source, Entity, Attribute, Codelist C-Code, Extensible, Value C-Code, Decode, ...)

## How to Read
```python
import openpyxl
wb = openpyxl.load_workbook("core/reference_data/USDM_CT.xlsx")
ws = wb["DDF valid value sets"]
for row in ws.iter_rows(min_row=2, values_only=True):
    entity, attr, codelist, extensible, code, decode = row[1], row[2], row[3], row[4], row[5], row[6]
```

---

## Complete Codelist Reference (25 codelists)

### AdministrableProduct.productDesignation — Codelist C207418 (Extensible: No)
| Code | Decode |
|------|--------|
| C202579 | IMP |
| C156473 | NIMP |

### AdministrableProduct.sourcing — Codelist C215483 (Extensible: Yes)
| Code | Decode |
|------|--------|
| C215659 | Centrally Sourced |
| C215660 | Locally Sourced |

### AdministrableProductProperty.type — Codelist C215479 (Extensible: Yes)
| Code | Decode |
|------|--------|
| C45997 | pH |

### Encounter.type — Codelist C188728 (Extensible: Yes)
| Code | Decode |
|------|--------|
| C25716 | Visit |

### Endpoint.level — Codelist C188726 (Extensible: No)
| Code | Decode |
|------|--------|
| C170559 | Exploratory Endpoint |
| C94496 | Primary Endpoint |
| C139173 | Secondary Endpoint |

### GeographicScope.type — Codelist C207412 (Extensible: No)
| Code | Decode |
|------|--------|
| C25464 | Country |
| C68846 | Global |
| C41129 | Region |

### GovernanceDate.type — Codelist C207413 (Extensible: Yes)
| Code | Decode |
|------|--------|
| C71476 | Approval Date |
| C215663 | Effective Date |
| C215664 | Issued Date |

### MedicalDevice.sourcing — Codelist C215482 (Extensible: Yes)
| Code | Decode |
|------|--------|
| C215659 | Centrally Sourced |
| C215660 | Locally Sourced |

### MedicalDeviceIdentifier.type — Codelist C215484 (Extensible: Yes)
| Code | Decode |
|------|--------|
| C104504 | Batch Number |
| C112279 | FDA Unique Device Identification |
| C70848 | Lot Number |
| C99285 | Model Number |

### Objective.level — Codelist C188725 (Extensible: No)
| Code | Decode |
|------|--------|
| C163559 | Exploratory Objective |
| C85826 | Primary Objective |
| C85827 | Secondary Objective |

### ObservationalStudyDesign.subTypes — Codelist C215486 (Extensible: Yes)
| Code | Decode |
|------|--------|
| C215675 | Disease Prevalence |
| C215653 | Disease Incidence |
| C215654 | Disease Determinants |
| C215655 | Disease Prognosis |
| C215656 | Drug Utilization |
| C49667 | Safety |
| C215657 | Clinical Education |
| C215658 | Disease Etiology |

### Organization.type — Codelist C188724 (Extensible: Yes)
| Code | Decode |
|------|--------|
| C93453 | Clinical Study Registry |
| C188863 | Regulatory Agency |
| C21541 | Healthcare Facility |
| C54149 | Pharmaceutical Company |
| C37984 | Laboratory |
| C54148 | Contract Research Organization |
| C199144 | Government Institute |
| C18240 | Academic Institution |
| C215661 | Medical Device Company |

### ProductOrganizationRole.code — Codelist C215485 (Extensible: Yes)
| Code | Decode |
|------|--------|
| C25392 | Manufacturer |
| C43530 | Supplier |

### ReferenceIdentifier.type — Codelist C215478 (Extensible: Yes)
| Code | Decode |
|------|--------|
| C215674 | Pediatric Investigation Plan |
| C142424 | Clinical Development Plan |

### StudyAmendmentImpact.type — Codelist C215481 (Extensible: Yes)
| Code | Decode |
|------|--------|
| C215665 | Study Subject Safety |
| C215666 | Study Subject Rights |
| C215667 | Study Data Reliability |
| C215668 | Study Data Robustness |

### StudyAmendmentReason.code — Codelist C207415 (Extensible: Yes)
| Code | Decode |
|------|--------|
| C207600 | Change In Standard Of Care |
| C207601 | Change In Strategy |
| C207602 | IMP Addition |
| C207603 | Inconsistency And/Or Error In The Protocol |
| C207604 | Investigator/Site Feedback |
| C207605 | IRB/IEC Feedback |
| C207606 | Manufacturing Change |
| C207607 | New Data Available (Other Than Safety Data) |
| C207608 | New Regulatory Guidance |
| C207609 | New Safety Information Available |
| C207610 | Protocol Design Error |
| C207611 | Recruitment Difficulty |
| C207612 | Regulatory Agency Request To Amend |
| C17649 | Other |
| C48660 | Not Applicable |

### StudyArm.dataOriginType — Codelist C188727 (Extensible: Yes)
| Code | Decode |
|------|--------|
| C188866 | Data Generated Within Study |
| C188864 | Historical Data |
| C165830 | Real World Data |
| C176263 | Synthetic Data |

### StudyDefinitionDocument.type — Codelist C215477 (Extensible: Yes)
| Code | Decode |
|------|--------|
| C70817 | Protocol |

### StudyDefinitionDocumentVersion.status — Codelist C188723 (Extensible: No)
| Code | Decode |
|------|--------|
| C25425 | Approved |
| C85255 | Draft |
| C25508 | Final |
| C63553 | Obsolete |
| C188862 | Pending Review |

### StudyDesign.characteristics — Codelist C207416 (Extensible: Yes)
| Code | Decode |
|------|--------|
| C98704 | Adaptive |
| C207613 | Extension |
| C46079 | Randomized |
| C217004 | Single-Centre |
| C217005 | Multicentre |
| C217006 | Single Country |
| C217007 | Multiple Countries |
| C25689 | Stratification |
| C147145 | Stratified Randomisation |

### StudyIntervention.role — Codelist C207417 (Extensible: No)
| Code | Decode |
|------|--------|
| C207614 | Additional Required Treatment |
| C165822 | Background Treatment |
| C158128 | Challenge Agent |
| C18020 | Diagnostic |
| C41161 | Experimental Intervention |
| C753 | Placebo |
| C165835 | Rescue Medicine |
| C68609 | Active Comparator |

### StudyRole.code — Codelist C215480 (Extensible: Yes)
| Code | Decode |
|------|--------|
| C17445 | Care Provider |
| C25936 | Investigator |
| C207599 | Outcomes Assessor |
| C70793 | Sponsor |
| C41189 | Study Subject |
| C78726 | Adjudication Committee |
| C215669 | Co-Sponsor |
| C25392 | Manufacturer |
| C215670 | Local Sponsor |
| C188863 | Regulatory Agency  |
| C51876 | Medical Expert |
| C142578 | Independent Data Monitoring Committee |
| C215671 | Dose Escalation Committee |
| C142489 | Data Safety Monitoring Board |
| C19924 | Principal investigator |
| C215672 | Clinical Trial Physician |
| C51851 | Project Manager |
| C37984 | Laboratory |
| C215673 | Pharmacovigilance |
| C215662 | Contract Research |
| C80403 | Study Site |
| C51877 | Statistician |

### StudyTitle.type — Codelist C207419 (Extensible: No)
| Code | Decode |
|------|--------|
| C207615 | Brief Study Title |
| C207616 | Official Study Title |
| C207617 | Public Study Title |
| C207618 | Scientific Study Title |
| C94108 | Study Acronym |

### Timing.relativeToFrom — Codelist C201265 (Extensible: No)
| Code | Decode |
|------|--------|
| C201352 | End to End |
| C201353 | End to Start |
| C201354 | Start to End |
| C201355 | Start to Start |

### Timing.type — Codelist C201264 (Extensible: No)
| Code | Decode |
|------|--------|
| C201356 | After |
| C201357 | Before |
| C201358 | Fixed Reference |

---

## Codes NOT in USDM CT (from NCI Thesaurus / ICH M11 directly)

The following coded fields have no USDM CT codelist and use NCI Thesaurus codes directly:

| Entity.Attribute | Source | Example Codes |
|-----------------|--------|---------------|
| StudyIntervention.type | ICH M11 | C1909 (Drug), C1261 (Biological), C16203 (Device) |
| StudyDesign.studyType | NCI Thesaurus | C98388 (Interventional), C142615 (Observational) |
| StudyArm.type | NCI Thesaurus | C174266 (Experimental Arm), C174267 (Active Comparator Arm), C174268 (Placebo Comparator Arm) |
| EligibilityCriterion.category | NCI Thesaurus | C25532 (Inclusion), C25370 (Exclusion) |
| StudyDesign.trialPhase | NCI Thesaurus | C15600–C15603 (Phase I–IV), C15693 (Phase I/II) |
| Masking.blindingSchema | NCI Thesaurus | C49659 (Open Label Study), C28233 (Single Blind Study), C15228 (Double Blind Study), C66959 (Triple Blind Study) |
| StudyEpoch.type | NCI Thesaurus | C48262 (Trial Screening), C98779 (Run-in Period), C101526 (Treatment Epoch), C99158 (Clinical Study Follow-up) |

## Usage in Pipeline

The pipeline uses these codes in:
- `extraction/interventions/schema.py` — `StudyIntervention.to_dict()`, `AdministrableProduct.to_dict()`
- `extraction/eligibility/schema.py` — `StudyDesignPopulation.to_dict()`
- `extraction/metadata/schema.py` — title types, organization types
- `extraction/procedures/schema.py` — procedure type codes
- `pipeline/combiner.py` — studyType derivation, organization defaults
- `pipeline/promotion.py` — plannedSex, plannedAge inference
- `pipeline/post_processing.py` — procedure code sanitization
- `core/terminology_codes.py` — objective/endpoint levels, arm types, study phases, blinding
- `core/usdm_types_generated.py` — epoch types, blinding, dataOriginType defaults
- `core/reconciliation/epoch_reconciler.py` — epoch type inference
- `web-ui/components/semantic/EditableCodedValue.tsx` — UI dropdown options
