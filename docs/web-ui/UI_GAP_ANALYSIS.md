# Web UI Gap Analysis - January 23, 2026 (Updated February 1, 2026)

> **Note (Feb 2026):** Since this analysis, v6.10/6.11 added SAP Data (`SAPDataView.tsx`) and CDISC ARS (`ARSDataView.tsx`) tabs. v7.2 added `ScheduledDecisionInstance`, `ConditionAssignment`, `StudyElement`, and enhanced `Encounter`/`StudyDesign` with new fields (`conditions[]`, `estimands[]`, `elements[]`, `transitionStartRule`/`transitionEndRule`). These are not yet reflected in the gap inventory below.

## Overview

Analysis of protocol_usdm.json outputs from January 23rd (19 protocols) to identify USDM data fields not fully presented in the web UI.

## USDM Data Inventory (from NCT02706951 sample)

### Study Version Level
| Field | Count | UI Component | Status |
|-------|-------|--------------|--------|
| titles | 1 | StudyMetadataView | ✅ Displayed |
| studyIdentifiers | 3 | StudyMetadataView | ✅ Displayed |
| organizations | 155 | StudyMetadataView | ⚠️ Partial (sponsor only) |
| studyPhase | 1 | StudyMetadataView | ✅ Displayed |
| eligibilityCriterionItems | 25 | EligibilityCriteriaView | ✅ Displayed |
| studyInterventions | 11 | InterventionsView | ✅ Displayed |
| administrableProducts | 2 | InterventionsView | ✅ Displayed |
| narrativeContents | 8 | - | ❌ **NOT DISPLAYED** |
| narrativeContentItems | 20 | - | ❌ **NOT DISPLAYED** |
| abbreviations | 39 | - | ❌ **NOT DISPLAYED** |
| amendments | 8 | AmendmentHistoryView | ✅ Displayed |
| medicalDevices | 3 | ProceduresDevicesView | ✅ Displayed |
| conditions | 3 | AdvancedEntitiesView | ⚠️ Partial |
| studySites | 153 | StudySitesView | ✅ Displayed |

### Study Design Level
| Field | Count | UI Component | Status |
|-------|-------|--------------|--------|
| arms | 4 | StudyDesignView | ✅ Displayed |
| epochs | 3 | StudyDesignView | ✅ Displayed |
| encounters | 7 | SoAView | ✅ Displayed |
| activities | 26 | SoAView | ✅ Displayed |
| activityGroups | 5 | - | ❌ **NOT DISPLAYED** |
| studyCells | 16 | StudyDesignView | ✅ Displayed |
| studyElements | 16 | StudyDesignView | ⚠️ Partial |
| maskingRoles | 2 | StudyDesignView | ✅ Displayed |
| objectives | 4 | ObjectivesEndpointsView | ✅ Displayed |
| endpoints | 18 | ObjectivesEndpointsView | ✅ Displayed |
| estimands | 3 | AdvancedEntitiesView | ✅ Displayed |
| scheduleTimelines | 1 | - | ❌ **NOT DISPLAYED** |
| scheduleTimelines.instances | 98 | - | ❌ **NOT DISPLAYED** |
| scheduleTimelines.timings | 6 | - | ❌ **NOT DISPLAYED** |
| notes (footnotes) | 8 | FootnotesView | ✅ Displayed |
| indications | 1 | AdvancedEntitiesView | ✅ Displayed |
| procedures | 6 | ProceduresDevicesView | ✅ Displayed |
| analysisPopulations | 3 | - | ❌ **NOT DISPLAYED** |
| characteristics | 3 | - | ❌ **NOT DISPLAYED** |
| model | 1 | StudyDesignView | ✅ Displayed (enhanced) |
| allocationRatio | 1 | StudyDesignView | ✅ Displayed (newly added) |

### Top-Level Data
| Field | Count | UI Component | Status |
|-------|-------|--------------|--------|
| administrations | 4 | - | ❌ **NOT DISPLAYED** |
| substances | 2 | - | ❌ **NOT DISPLAYED** |
| ingredients | 4 | - | ❌ **NOT DISPLAYED** |
| strengths | 5 | - | ❌ **NOT DISPLAYED** |
| transitionRules | 4 | - | ❌ **NOT DISPLAYED** |
| documentContentReferences | 9 | - | ❌ **NOT DISPLAYED** |
| commentAnnotations | 4 | FootnotesView | ✅ Displayed |
| studyDefinitionDocumentVersions | 3 | - | ❌ **NOT DISPLAYED** |
| countries | 3 | StudySitesView | ⚠️ Partial |
| geographicScope | 1 | - | ❌ **NOT DISPLAYED** |
| computationalExecution | 1 | - | ❌ **NOT DISPLAYED** |

### Extension Attributes (x-executionModel-*)
| Extension | UI Component | Status |
|-----------|--------------|--------|
| x-executionModel-timeAnchors | ExtensionsView | ✅ Displayed |
| x-executionModel-visitWindows | ExtensionsView | ✅ Displayed |
| x-executionModel-dosingRegimens | ExtensionsView | ✅ Displayed |
| x-executionModel-repetitions | ExtensionsView | ✅ Displayed |
| x-executionModel-crossoverDesign | StudyDesignView + ExtensionsView | ✅ Displayed (enhanced) |
| x-executionModel-traversalConstraints | ExtensionsView | ✅ Displayed |
| x-executionModel-stateMachine | ExtensionsView | ✅ Displayed |
| x-executionModel-randomizationScheme | ExtensionsView | ✅ Displayed |
| x-executionModel-endpointAlgorithms | ExtensionsView | ✅ Displayed |
| x-executionModel-derivedVariables | ExtensionsView | ✅ Displayed |
| x-executionModel-entityMappings | ExtensionsView | ✅ Displayed |
| x-executionModel-promotionIssues | ExtensionsView | ⚠️ Debug only |
| x-executionModel-classifiedIssues | StudyDesignView | ✅ Displayed (newly added) |
| x-footnoteConditions | FootnotesView | ✅ Displayed |
| x-soaFootnotes | FootnotesView | ✅ Displayed |
| x-executionModel-conceptualAnchors | ExtensionsView | ⚠️ Raw JSON only |

---

## Gap List (Priority Ranked)

### HIGH PRIORITY - Missing Core USDM Data

#### 1. Schedule Timelines (ScheduledActivityInstance + Timing)
**Data Available:**
- scheduleTimelines[0].instances: 98 scheduled activity instances
- scheduleTimelines[0].timings: 6 timing definitions
- Links activities to encounters with specific timing

**Impact:** This is core USDM scheduling data that defines WHEN activities happen. Critical for study execution.

**Proposal:** Create `ScheduleTimelineView.tsx` component showing:
- Visual timeline of instances per encounter
- Timing definitions (windowBefore/windowAfter)
- Activity-to-encounter-to-timing relationships

---

#### 2. Abbreviations
**Data Available:**
- 39 abbreviations with abbreviatedText + expandedText
- Used throughout the protocol document

**Impact:** Important for protocol readability and terminology understanding.

**Proposal:** Create `AbbreviationsView.tsx` or add to `StudyMetadataView`:
- Searchable/filterable abbreviation glossary
- Alphabetically sorted list
- Quick reference panel

---

#### 3. Analysis Populations (SAP Integration)
**Data Available:**
- Full Analysis Set, Per Protocol Analysis Set, Safety Analysis Set
- Definitions and criteria for each

**Impact:** Critical for understanding statistical analysis approach.

**Proposal:** Add to `AdvancedEntitiesView.tsx`:
- New "Analysis Populations" card
- Display name, description, criteria
- Link to SAP populations if available

---

#### 4. Narrative Contents & Items
**Data Available:**
- 8 narrativeContents (protocol sections)
- 20 narrativeContentItems (specific text blocks)
- Section numbers, titles, text content

**Impact:** Full protocol narrative is extracted but not displayed.

**Proposal:** Create `NarrativeView.tsx`:
- Collapsible section tree
- Section numbers and titles
- Full text content with search

---

#### 5. Administrations (Dosing Records)
**Data Available:**
- 4 administration records
- Links interventions → substances → dosing
- Route, dose, frequency details

**Impact:** Complete dosing information not visible.

**Proposal:** Enhance `InterventionsView.tsx`:
- Add "Administration Details" section
- Show linked substances and dosing
- Display route, frequency, instructions

---

### MEDIUM PRIORITY - Partial/Missing Display

#### 6. Activity Groups
**Data Available:**
- 5 activity groups organizing related activities
- Group names and member activity IDs

**Proposal:** Add to `StudyDesignView` or `SoAView`:
- Show activity groupings
- Collapsible group display

---

#### 7. Substances & Ingredients
**Data Available:**
- 2 substances (drug compounds)
- 4 ingredients with strength info

**Proposal:** Add to `InterventionsView`:
- "Drug Substances" section
- Chemical/ingredient details

---

#### 8. Transition Rules
**Data Available:**
- 4 transition rules defining epoch transitions
- Conditions for moving between study phases

**Proposal:** Add to `StudyDesignView`:
- "Transition Rules" card
- Visual epoch-to-epoch transitions with conditions

---

#### 9. Characteristics (Study-Level)
**Data Available:**
- 3 characteristics (study properties)
- Name/value pairs for study attributes

**Proposal:** Add to `StudyMetadataView`:
- "Study Characteristics" section

---

#### 10. Geographic Scope & Countries
**Data Available:**
- geographicScope object
- 3 countries list

**Proposal:** Enhance `StudySitesView`:
- "Geographic Coverage" summary card
- Countries with site counts

---

### LOW PRIORITY - Debug/Provenance Data

#### 11. Computational Execution Metadata
**Data Available:**
- modelUsed, totalTokens
- Processing timestamps

**Proposal:** Add to processing report or debug view:
- "Extraction Details" footer
- Model used, token count, timing

---

#### 12. Document Content References
**Data Available:**
- 9 references to source document pages/sections

**Proposal:** Add provenance links to relevant sections

---

#### 13. Organizations (Full List)
**Data Available:**
- 155 organizations (sponsors, sites, CROs, etc.)

**Proposal:** Enhance `StudyMetadataView` or add to `StudySitesView`:
- Categorized organization list
- Filter by type (Sponsor, Site, CRO)

---

## Implementation Roadmap

### Phase 1 - Quick Wins (1-2 days)
1. Add Abbreviations section to StudyMetadataView
2. Add Analysis Populations to AdvancedEntitiesView
3. Add Characteristics to StudyMetadataView
4. Add Geographic Scope summary to StudySitesView

### Phase 2 - Core Enhancements (3-5 days)
1. Create ScheduleTimelineView component
2. Add Administration details to InterventionsView
3. Add Activity Groups display
4. Add Transition Rules to StudyDesignView

### Phase 3 - Full Coverage (1 week)
1. Create NarrativeView component
2. Add Substances/Ingredients display
3. Add full Organizations view
4. Add Document References panel

---

## Summary Statistics

| Category | Total Fields | Displayed | Partial | Missing |
|----------|-------------|-----------|---------|---------|
| Study Version | 14 | 9 (64%) | 2 (14%) | 3 (21%) |
| Study Design | 18 | 13 (72%) | 1 (6%) | 4 (22%) |
| Top-Level | 11 | 2 (18%) | 2 (18%) | 7 (64%) |
| Extensions | 15 | 13 (87%) | 2 (13%) | 0 (0%) |
| **TOTAL** | **58** | **37 (64%)** | **7 (12%)** | **14 (24%)** |

**Key Finding:** 24% of USDM data fields are not displayed in the UI, with the most significant gaps being Schedule Timelines, Abbreviations, Analysis Populations, and Narrative Contents.
