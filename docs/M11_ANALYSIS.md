# ICH M11 Publications — Comprehensive Analysis

> **Source Documents**: All 8 official ICH M11 publications (PDFs extracted 2026-02-09)
> **Final Standard**: Step 4, adopted 19 November 2025
> **Official Name**: Clinical Electronic Structured Harmonised Protocol (CeSHarP)

---

## 1. Document Inventory

| # | Document | Date | Pages | Purpose |
|---|----------|------|-------|---------|
| 1 | **Final Guideline** | 19 Nov 2025 | 6 | High-level design principles, scope, conventions |
| 2 | **Final Template** | 19 Nov 2025 | 67 | The actual protocol template with headings, instructions, controlled terms |
| 3 | **Final Technical Specification** | 19 Nov 2025 | 245 | Every data element: C-codes, conformance, cardinality, business rules, OIDs |
| 4 | Concept Paper | 14 Nov 2018 | 2 | Original problem statement and proposed deliverables |
| 5 | Business Plan | 14 Nov 2018 | 2 | Costs, resources, timeline, regulatory implications |
| 6 | EWG Work Plan | 25 Jul 2025 | 3 | Timeline through Step 4 adoption + FHIR TIG + training materials |
| 7 | Step 2 Presentation (2022) | 27 Sep 2022 | 32 | Overview slides for initial public consultation |
| 8 | Step 2 TS Presentation (2025) | 14 Mar 2025 | 13 | TS update slides: cardinality, definitions, CDISC terminology finalized |

**Key Dates**:
- Nov 2018: Concept Paper & Business Plan endorsed
- Sep 2022: Step 2 public consultation (Guideline + Template + draft TS)
- Feb 2025: Updated TS Step 2 for second public consultation
- Nov 2025: **Step 4 adoption** of all three deliverables
- May 2026: Training materials + FHIR TIG (in collaboration with M2)

---

## 2. Guideline Summary (6 pages)

The Guideline is the umbrella document. Key points:

### 2.1 Scope
- **Interventional clinical trials** of medicinal products across **all phases and therapeutic areas**
- "Medicinal product" includes pharmaceuticals, biologics, vaccines, drug-device combination products, cell/gene therapy
- Does **NOT** cover observational studies (though our pipeline derives `instanceType` for both)

### 2.2 Three Deliverables
1. **Guideline** — design principles
2. **Template** — format, structure, TOC, headings, instructions
3. **Technical Specification** — data elements with conformance, cardinality, C-codes for electronic exchange

### 2.3 Design Principles
- **Build common core content** — universal across all protocols
- **Serve stakeholders** — sponsors, investigators, site staff, participants, IRBs/ECs, regulators
- **Define content for electronic exchange** — via eCTD and future tech
- **Design for content re-use** — registries, transparency, data capture
- **Maintain flexibility** — universal vs optional text; higher-level headings fixed, lower-level flexible

### 2.4 Template Conventions
- Most vital info (Synopsis, Schema, SoA) placed **near the front**
- Main Body / Appendix framework
- Appendix content carries **equal weight** as Main Body

### 2.5 Out of Scope
- Does NOT specify processes for protocol development/maintenance
- Does NOT supersede other ICH guidelines (E6, E8, E9, E9(R1), etc.)
- Does NOT characterize a "well-crafted" protocol

---

## 3. Template Deep Dive (67 pages)

### 3.1 CRITICAL FINDING: Section Structure

The M11 Template defines **Section 0 (Foreword) + Title Page + 14 numbered sections**:

```
Section 0   Foreword (removed in final protocol)
  0.1  Template Revision History
  0.2  Intended Use of Template
  0.3  Template Conventions and General Instructions
  0.4  Abbreviations Used in This Template

TITLE PAGE  (unnumbered — metadata table)
AMENDMENT DETAILS (unnumbered)
TABLE OF CONTENTS

§1   PROTOCOL SUMMARY
  1.1  Protocol Synopsis
    1.1.1  Primary and Secondary Objectives and Estimands
    1.1.2  Overall Design
  1.2  Trial Schema
  1.3  Schedule of Activities

§2   INTRODUCTION
  2.1  Purpose of Trial
  2.2  Assessment of Risks and Benefits
    2.2.1  Risk Summary and Mitigation Strategy
    2.2.2  Benefit Summary
    2.2.3  Overall Risk-Benefit Assessment

§3   TRIAL OBJECTIVES AND ASSOCIATED ESTIMANDS
  3.1  Primary Objective(s) and Associated Estimand(s)
    3.1.1  Primary Objective <#>
  3.2  Secondary Objective(s) and Associated Estimand(s)
    3.2.1  {Secondary Objective <#>}
  3.3  Exploratory Objective(s)
    3.3.1  {Exploratory Objective <#>}

§4   TRIAL DESIGN
  4.1  Description of Trial Design
    4.1.1  Stakeholder Input into Design
  4.2  Rationale for Trial Design
    4.2.1  Rationale for Estimand(s)
    4.2.2  Rationale for Intervention Model
    4.2.3  Rationale for Control Type
    4.2.4  Rationale for Trial Duration
    4.2.5  Rationale for Adaptive or Novel Trial Design
    4.2.6  Rationale for Interim Analysis
    4.2.7  Rationale for Other Trial Design Aspects
  4.3  Trial Stopping Rules
  4.4  Start of Trial and End of Trial
  4.5  Access to Trial Intervention After End of Trial

§5   TRIAL POPULATION
  5.1  Description of Trial Population and Rationale
  5.2  Inclusion Criteria
  5.3  Exclusion Criteria
  5.4  Contraception
    5.4.1  Definitions Related to Childbearing Potential
    5.4.2  Contraception Requirements
  5.5  Lifestyle Restrictions
    5.5.1  Meals and Dietary Restrictions
    5.5.2  Caffeine, Alcohol, Tobacco, and Other Restrictions
    5.5.3  Physical Activity Restrictions
    5.5.4  Other Activity Restrictions
  5.6  Screen Failure and Rescreening

§6   TRIAL INTERVENTION AND CONCOMITANT THERAPY
  (Overview table: Arm/Type/Dose Form/Strength/Route/Regimen/IMP-NIMP)
  6.1   Description of Investigational Trial Intervention
  6.2   Rationale for Investigational Trial Intervention Dose and Regimen
  6.3   Investigational Trial Intervention Administration
  6.4   Investigational Trial Intervention Dose Modification
  6.5   Management of Investigational Trial Intervention Overdose
  6.6   Preparation, Storage, Handling and Accountability
    6.6.1  Preparation
    6.6.2  Storage and Handling
    6.6.3  Accountability
  6.7   Assignment, Randomisation and Blinding
    6.7.1  Participant Assignment
    6.7.2  {Randomisation}
    6.7.3  {Measures to Maintain Blinding}
    6.7.4  {Emergency Unblinding at the Site}
  6.8   Investigational Trial Intervention Adherence
  6.9   Description of Noninvestigational Trial Intervention
    6.9.1  {Background Trial Intervention}
    6.9.2  {Rescue Therapy}
    6.9.3  {Other Noninvestigational Trial Intervention}
  6.10  Concomitant Therapy
    6.10.1 {Prohibited Concomitant Therapy}
    6.10.2 {Permitted Concomitant Therapy}

§7   PARTICIPANT DISCONTINUATION OF TRIAL INTERVENTION
     AND DISCONTINUATION OR WITHDRAWAL FROM TRIAL
  7.1  Discontinuation of Trial Intervention for Individual Participants
    7.1.1  Permanent Discontinuation
    7.1.2  Temporary Discontinuation
    7.1.3  Rechallenge
  7.2  Participant Discontinuation or Withdrawal from the Trial
  7.3  Management of Loss to Follow-Up

§8   TRIAL ASSESSMENTS AND PROCEDURES
  8.1  Trial Assessments and Procedures Considerations
  8.2  Screening/Baseline Assessments and Procedures
  8.3  Efficacy Assessments and Procedures
  8.4  Safety Assessments and Procedures
    8.4.1  {Physical Examination}
    8.4.2  {Vital Signs}
    8.4.3  {Electrocardiograms}
    8.4.4  {Clinical Laboratory Assessments}
    8.4.5  {Pregnancy Testing}
    8.4.6  {Suicidal Ideation and Behaviour Risk Monitoring}
  8.5  Pharmacokinetics
  8.6  Biomarkers
    8.6.1  Genetics, Genomics, Pharmacogenetics, Pharmacogenomics
    8.6.2  Pharmacodynamic Biomarkers
    8.6.3  {Other Biomarkers}
  8.7  Immunogenicity Assessments
  8.8  Medical Resource Utilisation and Health Economics

§9   ADVERSE EVENTS, SERIOUS ADVERSE EVENTS, PRODUCT COMPLAINTS,
     PREGNANCY AND POSTPARTUM INFORMATION, AND SPECIAL SAFETY SITUATIONS
  9.1  Definitions
    9.1.1  Definitions of Adverse Events
    9.1.2  Definitions of Serious Adverse Events
    9.1.3  Definitions of Product Complaints
      9.1.3.1  {Definitions of Medical Device Product Complaints}
  9.2  Timing and Procedures for Collection and Reporting
    9.2.1  Timing
    9.2.2  Collection Procedures
    9.2.3  Reporting
      9.2.3.1  Regulatory Reporting Requirements
    9.2.4  Adverse Events of Special Interest
    9.2.5  Disease-Related Events or Outcomes Not Qualifying as AEs or SAEs
  9.3  Pregnancy and Postpartum Information
    9.3.1  {Participants Who Become Pregnant}
    9.3.2  {Partners Who Become Pregnant}
  9.4  Special Safety Situations

§10  STATISTICAL CONSIDERATIONS
  10.1   General Considerations
  10.2   Analysis Sets
  10.3   Analyses of Demographics and Other Baseline Variables
  10.4   Analyses Associated with the Primary Objective(s)
    10.4.1   Primary Objective <#>
      10.4.1.1  Statistical Analysis Method
      10.4.1.2  Handling of Data in Relation to Primary Estimand(s)
      10.4.1.3  Handling of Missing Data
      10.4.1.4  {Sensitivity Analysis}
      10.4.1.5  {Supplementary Analysis}
  10.5   Analyses Associated with the Secondary Objective(s)
    10.5.1   {Secondary Objective <#>}
      10.5.1.1–10.5.1.5  (same structure as 10.4.1)
  10.6   Analyses Associated with Exploratory Objective(s)
  10.7   Safety Analyses
  10.8   Other Analyses
  10.9   Interim Analyses
  10.10  Multiplicity Adjustments
  10.11  Sample Size Determination

§11  TRIAL OVERSIGHT AND OTHER GENERAL CONSIDERATIONS
  11.1   Regulatory and Ethical Considerations
  11.2   Trial Oversight
    11.2.1  Investigator Responsibilities
    11.2.2  Sponsor Responsibilities
  11.3   Informed Consent Process
    11.3.1  {Informed Consent for Rescreening}
    11.3.2  {Informed Consent for Remaining Samples}
  11.4   Committees
  11.5   Insurance and Indemnity
  11.6   Risk-Based Quality Management
  11.7   Data Governance
  11.8   Data Protection
  11.9   Source Records
  11.10  Protocol Deviations
  11.11  Early Site Closure
  11.12  Data Dissemination

§12  APPENDIX: SUPPORTING DETAILS
  12.1  Clinical Laboratory Tests
  12.2  Country/Region-Specific Differences
  12.3  Prior Protocol Amendment(s)
  12.X  {Additional Appendices}

§13  APPENDIX: GLOSSARY OF TERMS AND ABBREVIATIONS

§14  APPENDIX: REFERENCES
```

### 3.2 Text Conventions (CRITICAL for renderer)

| Convention | Typeface | Meaning | Renderer Action |
|------------|----------|---------|-----------------|
| **Universal text** | Black Times New Roman | Must appear in all protocols | Emit verbatim |
| **Conditional universal** | Black TNR in `{braces}` | Appear if applicable | Emit if data exists |
| **Optional text** | Blue Arial | May modify/delete/replace | Emit if relevant |
| **Controlled terminology** | `[Square brackets]` grey shading | Pick list value | Map to CDISC code list |
| **Text insertion point** | `<Chevrons>` grey shading | Free text entry | Fill from USDM data |
| **Instructional text** | Red Calibri | Remove before finalization | Never emit |

### 3.3 Heading Hierarchy Rules

| Level | Example | Modification | Addition |
|-------|---------|-------------|----------|
| **L1** | `1 PROTOCOL SUMMARY` | **DO NOT** delete or modify | **DO NOT** add |
| **L2** | `1.1 Protocol Synopsis` | **DO NOT** delete or modify | Add at end of L1 section |
| **L3** (black) | `1.1.1 Primary and Secondary...` | **DO NOT** delete or modify | Add at end of L2 section |
| **L3** (blue/optional) | `8.4.1 {Physical Examination}` | May retain/delete/modify | Add at end |
| **L4+** | Same rules as L3 | | |

### 3.4 Title Page Data Elements

The title page is a structured metadata table with these fields:

| Field | Conformance | Controlled Term |
|-------|-------------|-----------------|
| Sponsor Confidentiality Statement | Optional | Free text |
| Full Title | **Required** | Free text |
| Trial Acronym | Optional | Free text |
| Sponsor Protocol Identifier | **Required** | Free text |
| Original Protocol Indicator | **Required** | Yes/No (C217046) |
| Version Number | Optional | Free text |
| Version Date | Optional | Date |
| Amendment Identifier | Conditional | Free text |
| Amendment Scope | Conditional | Global/Not Global (C217047) |
| Sponsor's Investigational Product Code(s) | Optional | Free text (repeatable) |
| Investigational Product Name(s) | Optional | Nonproprietary + Proprietary |
| Trial Phase | **Required** | Code List C217045 |
| Short Title | Optional | Free text |
| Sponsor Name and Address | **Required** | Free text |
| Co-Sponsor Name and Address | Optional | Free text (repeatable) |
| Local Sponsor Name and Address | Optional | Free text (repeatable) |
| Device Manufacturer Name and Address | Optional | Free text |
| Regulatory/Clinical Trial Identifiers | **Required** heading | EU CT, FDA IND, IDE, jRCT, NCT, NMPA IND, WHO/UTN, Other |
| Sponsor Approval | **Required** | Date or location text |
| Sponsor Signatory | Optional | Text/Image |
| Medical Expert Contact | Optional | Text or location |

### 3.5 Synopsis (§1.1.2) Structured Fields

The Synopsis "Overall Design" block contains these controlled-terminology fields:

| Field | Code List |
|-------|-----------|
| Population Type | [Population Type] |
| Intervention Model | [Intervention Model] |
| Population Diagnosis or Condition | MedDRA PT or free text |
| Control Type | [Control Type] |
| Population Age (Min/Max + Units) | [Units of Age] |
| Control Description | [Nonproprietary Name]/[INN] |
| Site Distribution | [Site Distribution] |
| Site Geographic Scope | [Site Geographic Scope] |
| Intervention Assignment Method | [Intervention Assignment Method] |
| Master Protocol Indicator | [Master Protocol Indicator] |
| Stratification Indicator | [Stratification Indicator] |
| Drug/Device Combination Indicator | [Drug/Device Combination Product Indicator] |
| Adaptive Trial Design Indicator | [Adaptive Trial Design Indicator] |
| Number of Arms | [Number of Arms] |
| Trial Blind Schema | [Trial Blind Schema] |
| Blinded Roles | [Blinded Roles] |
| Number of Participants | Target/Maximum + count |
| Duration (intervention + participation) | Free text + [unit of time] |
| Committees | Free text |

### 3.6 Section 6 Intervention Table

The optional overview table at the start of §6 has these columns:
- Arm Name, Arm Type, Intervention Name, Intervention Type
- Pharmaceutical Dose Form, Dosage Strength(s), Dosage Level(s)
- Route of Administration, Regimen/Treatment Period
- Use, IMP/NIMP, Sourcing

All with controlled terminology pick lists.

### 3.7 Estimand Table (§3)

For each objective, an estimand table with:
- Population, Treatment, Endpoint, Population-level Summary
- Intercurrent Event(s) and Strategy(ies)

---

## 4. Technical Specification Deep Dive (245 pages)

### 4.1 Structure
The TS is a flat catalog of every data element from the Template. For each element:

| Attribute | Description |
|-----------|-------------|
| **Term (Variable)** | Verbatim term from Template |
| **Data Type** | Text, Valid Value, Date, Number, Image |
| **D/V/H** | Data, Value, or Heading |
| **Definition** | NCI C-code (e.g., C132346 for Full Title) |
| **User Guidance** | Instructions from Template |
| **Conformance** | Required / Optional / Conditional |
| **Cardinality** | One-to-one, one-to-many, etc. |
| **Relationship** | ToC hierarchy position |
| **Value** | Actual value, code list reference, or "Text" |
| **Business Rules** | Value Allowed, Relationship chains, Concept + OID |
| **Repeating/Reuse** | Whether element repeats or is reused elsewhere |

### 4.2 Terminology Governance
- ICH + CDISC signed agreement for maintenance
- Terminology published in **NCI Thesaurus Subset C217023** (ICH M11 Terminology)
- Each concept assigned an **NCI C-code**
- ICH OIDs published on ESTRI webpage
- CDISC conducted public review in 2024

### 4.3 Key Code Lists (from TS)

| Code List | ICH OID | Example Values |
|-----------|---------|----------------|
| C217045 Trial Phase | 2.16.840.1.113883.3.989.2.3.1.18 | Early Phase 1, Phase 1, Phase 1/2, Phase 2, Phase 2/3, Phase 3, Phase 3/4, Phase 4 |
| C217046 Original Protocol Indicator | 2.16.840.1.113883.3.989.2.3.1.11 | Yes (C49488), No (C49487) |
| C217047 Amendment Scope | 2.16.840.1.113883.3.989.2.3.1.3 | Global (C68846), Not Global (C217026) |
| Population Type | — | (e.g., Healthy Volunteers, Patients) |
| Intervention Model | — | (e.g., Single Group, Parallel, Crossover, Factorial) |
| Control Type | — | (e.g., Placebo, Active Comparator, No Intervention) |
| Arm Type | — | (e.g., Experimental, Active Comparator, Placebo Comparator) |
| Intervention Type | — | (e.g., Drug, Biological, Device, Combination) |
| Route of Administration | — | (standard pharma routes) |
| Pharmaceutical Dose Form | — | (standard dose forms) |

### 4.4 Business Rules Patterns
- `Value Allowed: No` → heading-only, no data entry
- `Value Allowed: Yes` → data element accepts content
- `Value Allowed: Yes if Original Protocol = No; blank if Original Protocol = Yes` → conditional
- Relationship chains trace data element dependencies
- Repeating rules specify where elements can recur across sections

---

## 5. Gap Analysis: Our Implementation vs. M11 Final Standard

### 5.1 CRITICAL: Section Numbering is WRONG

Our `m11_mapper.py` defines 12 sections numbered 1–12. The actual M11 has **14 numbered sections** with different content assignments from §9 onward:

| M11 § | M11 Title | Our § | Our Title | Status |
|-------|-----------|-------|-----------|--------|
| Title Page | (metadata table) | — | `_add_title_page` | ⚠️ Partial |
| 1 | Protocol Summary | 1 | Protocol Summary | ✅ Match |
| 2 | Introduction | 2 | Introduction | ✅ Match |
| 3 | Trial Objectives and Associated Estimands | 3 | Study Objectives and Endpoints | ⚠️ Title wrong |
| 4 | Trial Design | 4 | Study Design | ⚠️ Title wrong |
| 5 | Trial Population | 5 | Study Population | ⚠️ Title wrong |
| 6 | Trial Intervention and Concomitant Therapy | 6 | Study Intervention | ⚠️ Title wrong |
| 7 | Participant Discontinuation... | 7 | Discontinuation... | ✅ Close |
| 8 | Trial Assessments and Procedures | 8 | Study Assessments and Procedures | ⚠️ Title wrong |
| **9** | **Adverse Events, SAEs, Product Complaints...** | — | **❌ MISSING** | 🔴 Gap |
| 10 | Statistical Considerations | 9 | Statistical Considerations | 🔴 Wrong number |
| 11 | Trial Oversight and Other General Considerations | 10 | Supporting Documentation | 🔴 Wrong number + title |
| 12 | Appendix: Supporting Details | 12 | Appendices | ⚠️ Title wrong |
| **13** | **Appendix: Glossary of Terms and Abbreviations** | — | **❌ MISSING** | 🔴 Gap |
| **14** | **Appendix: References** | 11 | References | 🔴 Wrong number |

### 5.2 Title Page Gaps

| M11 Required Field | Our Implementation | Status |
|--------------------|--------------------|--------|
| Full Title | ✅ From `titles[]` | OK |
| Sponsor Protocol Identifier | ✅ From `studyIdentifiers[]` | OK |
| Original Protocol Indicator | ❌ Not rendered | Gap |
| Trial Phase | ✅ From `studyPhase` | OK |
| Sponsor Name and Address | ❌ Not rendered | Gap |
| Regulatory Identifiers (NCT, IND, etc.) | ❌ Not rendered | Gap |
| Sponsor Approval Date | ❌ Not rendered | Gap |
| Trial Acronym | ❌ Not rendered | Gap |
| Short Title | ❌ Not rendered | Gap |
| Version Number/Date | ✅ From `versionIdentifier`/`effectiveDate` | OK |
| Amendment details | ❌ Not rendered | Gap |
| Investigational Product info | ❌ Not rendered | Gap |

### 5.3 Synopsis (§1.1.2) Gaps

The M11 synopsis requires a structured "Overall Design" block with ~20 controlled-terminology fields. Our renderer has **no synopsis composer** — §1 only gets narrative text from mapping.

**Missing structured fields**: Population Type, Intervention Model, Control Type, Population Age, Site Distribution, Geographic Scope, Assignment Method, Master Protocol Indicator, Stratification Indicator, Drug/Device Indicator, Adaptive Design Indicator, Number of Arms, Trial Blind Schema, Blinded Roles, Number of Participants, Duration, Committees.

### 5.4 Entity Composer Gaps

| M11 Section | Composer Exists? | Quality |
|-------------|------------------|---------|
| §1 Synopsis | ❌ No | Need structured field composer |
| §3 Objectives/Estimands | ✅ `_compose_objectives` + `_compose_estimands` | Good but needs estimand table format |
| §4 Trial Design | ✅ `_compose_study_design` | Basic — arms/epochs only, missing rationale subsections |
| §5 Population | ✅ `_compose_eligibility` | ⚠️ Looks for `category` field; needs `criterionDesc` path too |
| §6 Intervention | ❌ No | Need intervention table composer |
| §7 Discontinuation | ✅ `_compose_discontinuation` | Keyword-search approach, adequate |
| §8 Assessments | ❌ No | Could compose from SoA data |
| §9 AE/SAE | ❌ No + Section missing | Need section + narrative |
| §10 Statistics | ✅ `_compose_statistics` | Good — uses SAP extensions |
| §11 Oversight | ❌ No + wrong mapping | Need section |
| §12 Appendix | ❌ No | Need lab tests, country diffs |
| §13 Glossary | ❌ No + Section missing | Need section |
| §14 References | ❌ No | Need section |

### 5.5 Template Convention Compliance

| Convention | Our Status |
|------------|-----------|
| L1 headings immutable | ⚠️ Our L1 titles are wrong (see §5.1) |
| L2 headings immutable | ❌ We don't render L2 headings |
| Font: Times New Roman for universal | ❌ We use Calibri |
| Heading colors: black | ❌ We use blue (RGBColor 0,51,102) |
| Heading sizes: L1=14pt, L2=14pt bold, L3=12pt bold | ❌ L1=16pt, L2=14pt, L3=12pt |
| Controlled terminology rendering | ❌ No pick-list formatting |
| Instructional text removal | N/A (we generate, not fill template) |

### 5.6 Technical Specification Compliance

| Requirement | Our Status |
|-------------|-----------|
| NCI C-codes for data elements | ❌ Not tracked |
| ICH OIDs | ❌ Not tracked |
| Conformance levels (Required/Optional/Conditional) | ❌ Not enforced |
| Cardinality constraints | ❌ Not validated |
| CDISC controlled terminology (NCI Thesaurus C217023) | ❌ Not integrated |
| Business rules validation | ❌ Not implemented |

---

## 6. Priority Remediation Plan

### P0 — Section Structure Fix (BLOCKING)

**Fix `M11_TEMPLATE` in `m11_mapper.py`** to match the actual 14-section M11 structure:
- Renumber sections 9–14
- Add missing §9 (AE/SAE)
- Add missing §13 (Glossary)
- Correct all section titles to match M11 verbatim
- Use "Trial" not "Study" throughout (M11 convention)

### P1 — Title Page Enhancement

- Add all Required fields from TS
- Render as structured table matching M11 layout
- Map USDM `studyIdentifiers` to correct identifier types (NCT, IND, etc.)
- Add Original Protocol Indicator, Sponsor Name/Address

### P2 — Synopsis Composer (§1.1.2)

Build `_compose_synopsis()` that generates the structured "Overall Design" block from:
- `studyDesign.studyType` → Intervention Model
- `studyDesign.studyPhase` → Trial Phase
- `studyDesign.studyArms` → Number of Arms, Arm types
- `studyDesign.studyEpochs` → Duration calculation
- `studyDesign.population` → Population Type, Age range
- `studyDesign.studyInterventions` → Intervention info
- Blinding/randomization from design attributes

### P3 — Intervention Table Composer (§6)

Build `_compose_interventions()` rendering the §6 overview table:
- Arms × Interventions matrix
- Dose form, strength, route from USDM entities
- IMP/NIMP classification

### P4 — Sub-heading Rendering

Currently we only render L1 headings. Need L2 and L3:
- §3.1, §3.2, §3.3 for objective categories
- §5.2, §5.3 for inclusion/exclusion
- §6.1–6.10 for intervention subsections
- §10.1–10.11 for statistics subsections
- Full §11 subsection tree

### P5 — Style Compliance

- Switch to Times New Roman (TNR) per M11 convention
- L1 headings: 14pt TNR Bold Black ALL CAPS
- L2 headings: 14pt TNR Bold Black
- L3 headings: 12pt TNR Bold Black
- Body: 12pt TNR (or 11pt, template doesn't mandate exact body size)
- Remove blue heading color

### P6 — Missing Section Composers

- §8 Assessments: compose from SoA encounter/activity data
- §9 AE/SAE: compose from safety narrative extraction
- §11 Oversight: compose from regulatory/ethical narrative
- §12 Appendix: lab tests table, country differences
- §13 Glossary: compile abbreviations from document
- §14 References: extract from narrative

---

## 7. Controlled Terminology Reference

### 7.1 Trial Phase (C217045)
```
Early Phase 1 (C54721)
Phase 1 (C15600)
Phase 1/Phase 2 (C15693)
Phase 1/Phase 2/Phase 3 (C198366)
Phase 1/Phase 3 (C198367)
Phase 2 (C15601)
Phase 2/Phase 3 (C15694)
Phase 2/Phase 3/Phase 4 (C217024)
Phase 3 (C15602)
Phase 3/Phase 4 (C217025)
Phase 4 (C15603)
```

### 7.2 Original Protocol Indicator (C217046)
```
Yes (C49488)
No (C49487)
```

### 7.3 Amendment Scope (C217047)
```
Global (C68846)
Not Global (C217026)
```

### 7.4 Regulatory Identifier Types
```
EU CT Number (C218684) — format: yyyy-5xxxxx-xx
FDA IND Number (C218685)
IDE Number (C218686)
jRCT Number (C218687)
NCT Number (C172240)
NMPA IND Number (C218688)
WHO/UTN Number (C218689) — format: Uxxxx-xxxx-xxxx
Other (C218690) — repeatable
```

---

## 8. FHIR & Future Considerations

From the Work Plan (Jul 2025):
- **FHIR TIG** (Technical Implementation Guide) is being developed with M2 EWG
- Target: May 2026 publication on M2 ESTRI page
- The TIG will define FHIR resources for M11 protocol exchange
- This means our USDM → M11 pipeline may eventually need a USDM → FHIR path as well

---

## 9. Key Differences from Training Data

Items in the **Final Step 4 (Nov 2025)** that may differ from earlier drafts:

1. **Section 9** is now explicitly "Adverse Events, Serious Adverse Events, Product Complaints, Pregnancy and Postpartum Information, and Special Safety Situations" — significantly expanded from Step 2
2. **§10 Statistical Considerations** has 11 subsections (10.1–10.11) — more granular than Step 2
3. **§11 Trial Oversight** has 12 subsections (11.1–11.12) — expanded from Step 2
4. **Controlled terminology** is now finalized with NCI C-codes and ICH OIDs
5. **Cardinality and conformance** are now fully specified (were incomplete in Step 2 TS)
6. **CDISC public review** of terminology completed in 2024
7. **Template word usage**: "Trial" (not "Study"), "Participant" (not "Subject"), "Trial intervention" (not "Study drug")
8. **Sections 13 and 14** (Glossary and References) are separate numbered appendix sections

---

## 10. Summary of Actionable Items

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| **P0** | Fix M11_TEMPLATE to 14 sections with correct titles | Small | Critical — everything else depends on this |
| **P1** | Enhanced title page with all Required fields | Medium | High — first thing reviewers see |
| **P2** | Synopsis composer with structured fields | Medium | High — §1.1.2 is key for registry/review |
| **P3** | §6 intervention overview table | Medium | Medium — structured data exists in USDM |
| **P4** | L2/L3 sub-heading rendering | Medium | High — proper document structure |
| **P5** | Style compliance (TNR, heading sizes, colors) | Small | Medium — cosmetic but expected |
| **P6** | Missing section composers (§8,§9,§11,§12,§13,§14) | Large | Medium — fills content gaps |
