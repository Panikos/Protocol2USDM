# Web UI Implementation Plan - Missing Features

## Overview
This document outlines the phased implementation plan to bring feature parity between the Streamlit viewer and the new Next.js web UI.

---

## Phase 1: Protocol Expansion Data Tabs (Priority: High)

Add new tabs to the protocol detail page for viewing extracted protocol data.

### 1.1 Study Metadata Tab
- [ ] Study title, acronym, identifier
- [ ] Phase, therapeutic area, indication
- [ ] Sponsor information
- [ ] Study dates (approval, start, end)

### 1.2 Eligibility Criteria Tab
- [ ] Inclusion criteria table
- [ ] Exclusion criteria table
- [ ] Age/sex requirements
- [ ] Population description

### 1.3 Objectives & Endpoints Tab
- [ ] Primary objectives with endpoints
- [ ] Secondary objectives with endpoints
- [ ] Exploratory objectives
- [ ] Endpoint hierarchy view

### 1.4 Study Design Tab
- [ ] Arms display (name, type, description)
- [ ] Epochs display
- [ ] Study cells matrix
- [ ] Blinding schema

### 1.5 Interventions Tab
- [ ] Study drugs/products
- [ ] Dosing information
- [ ] Administration routes
- [ ] Treatment duration

### 1.6 Amendment Details Tab
- [ ] Amendment history
- [ ] Changes per amendment
- [ ] Amendment dates

---

## Phase 2: Validation & Quality Metrics (Priority: High)

### 2.1 Validation Results Panel
- [ ] Schema validation status
- [ ] Validation errors/warnings list
- [ ] Error severity indicators
- [ ] Fix suggestions

### 2.2 Quality Metrics Dashboard
- [ ] Entity counts (activities, encounters, epochs)
- [ ] Linkage accuracy percentage
- [ ] Field population rate
- [ ] Completeness by entity type

### 2.3 Field Completeness View
- [ ] Per-entity attribute coverage
- [ ] Missing required fields
- [ ] Optional field population

---

## Phase 3: Intermediate Data Views (Priority: Medium)

### 3.1 Extraction Outputs
- [ ] Text extraction raw output
- [ ] Vision extraction output
- [ ] Reconciliation results

### 3.2 SoA Images
- [ ] Extracted page images viewer
- [ ] Image zoom/pan
- [ ] Page navigation

### 3.3 Header Structure
- [ ] Column detection results
- [ ] Row detection results
- [ ] Structure visualization

---

## Phase 4: Advanced Features (Priority: Low)

### 4.1 Narrative Structure
- [ ] Document sections
- [ ] M11 template mapping
- [ ] Section content preview

### 4.2 Advanced Entities
- [ ] Biomedical concepts
- [ ] Estimands
- [ ] Indications
- [ ] BC categories

### 4.3 Procedures & Devices
- [ ] Medical devices list
- [ ] Procedure definitions
- [ ] Safety requirements

### 4.4 Analysis Populations (SAP)
- [ ] Population definitions
- [ ] Analysis sets
- [ ] Subgroup definitions

### 4.5 Study Sites
- [ ] Site list
- [ ] Geographic distribution
- [ ] Site details

---

## API Routes Required

```
/api/protocols/[id]/metadata      - Study metadata
/api/protocols/[id]/eligibility   - Eligibility criteria
/api/protocols/[id]/objectives    - Objectives & endpoints
/api/protocols/[id]/design        - Study design structure
/api/protocols/[id]/interventions - Interventions
/api/protocols/[id]/amendments    - Amendment history
/api/protocols/[id]/validation    - Validation results
/api/protocols/[id]/quality       - Quality metrics
/api/protocols/[id]/images        - SoA page images
```

---

## Component Structure

```
components/
├── protocol/
│   ├── StudyMetadataView.tsx
│   ├── EligibilityCriteriaView.tsx
│   ├── ObjectivesEndpointsView.tsx
│   ├── StudyDesignView.tsx
│   ├── InterventionsView.tsx
│   ├── AmendmentHistoryView.tsx
│   └── ValidationPanel.tsx
├── quality/
│   ├── QualityMetricsDashboard.tsx
│   ├── FieldCompletenessView.tsx
│   └── ValidationResultsView.tsx
└── intermediate/
    ├── ExtractionOutputView.tsx
    ├── SoAImageViewer.tsx
    └── HeaderStructureView.tsx
```

---

## Timeline Estimate

| Phase | Duration | Status |
|-------|----------|--------|
| Phase 1 | 2-3 days | Not Started |
| Phase 2 | 1-2 days | Not Started |
| Phase 3 | 1 day | Not Started |
| Phase 4 | 2-3 days | Not Started |

---

## Current Progress

- [x] SoA Table (AG Grid)
- [x] Timeline Visualization (Cytoscape)
- [x] Provenance coloring
- [x] Overlay draft/publish workflow
- [x] Timing nodes with anchors
- [x] Protocol expansion data (Phase 1)
- [x] Quality metrics (Phase 2)
- [x] Document structure view (Phase 3)

## Commits

1. `7c3b14f` - Web UI improvements (Next.js 15+, AG Grid, Timeline)
2. `84fd72e` - Phase 1: Protocol Expansion Data Tabs
3. `91d4c6b` - Phase 2: Quality Metrics Dashboard
4. `1256e9f` - Fix missing Badge and Progress UI components
5. `0512ff5` - Phase 3: Intermediate Data Views
