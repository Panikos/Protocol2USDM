# Web UI Implementation Plan - Missing Features

## Overview
This document outlines the phased implementation plan to bring feature parity between the Streamlit viewer and the new Next.js web UI.

---

## Phase 1: Protocol Expansion Data Tabs (Priority: High) ✅

Add new tabs to the protocol detail page for viewing extracted protocol data.

### 1.1 Study Metadata Tab
- [x] Study title, acronym, identifier
- [x] Phase, therapeutic area, indication
- [x] Sponsor information
- [x] Study dates (approval, start, end)

### 1.2 Eligibility Criteria Tab
- [x] Inclusion criteria table
- [x] Exclusion criteria table
- [x] Age/sex requirements
- [x] Population description

### 1.3 Objectives & Endpoints Tab
- [x] Primary objectives with endpoints
- [x] Secondary objectives with endpoints
- [x] Exploratory objectives
- [x] Endpoint hierarchy view

### 1.4 Study Design Tab
- [x] Arms display (name, type, description)
- [x] Epochs display
- [x] Study cells matrix
- [x] Blinding schema

### 1.5 Interventions Tab
- [x] Study drugs/products
- [x] Dosing information
- [x] Administration routes
- [x] Treatment duration

### 1.6 Amendment Details Tab
- [x] Amendment history
- [x] Changes per amendment
- [x] Amendment dates

---

## Phase 2: Validation & Quality Metrics (Priority: High) ✅

### 2.1 Validation Results Panel
- [x] Schema validation status
- [x] Validation errors/warnings list
- [x] Error severity indicators
- [x] Fix suggestions

### 2.2 Quality Metrics Dashboard
- [x] Entity counts (activities, encounters, epochs)
- [x] Linkage accuracy percentage
- [x] Field population rate
- [x] Completeness by entity type

### 2.3 Field Completeness View
- [x] Per-entity attribute coverage
- [x] Missing required fields
- [x] Optional field population

---

## Phase 3: Intermediate Data Views (Priority: Medium) ✅

### 3.1 Extraction Outputs
- [x] Text extraction raw output
- [x] Vision extraction output
- [x] Reconciliation results

### 3.2 SoA Images
- [x] Extracted page images viewer
- [x] Image zoom/pan
- [x] Page navigation

### 3.3 Header Structure
- [x] Document structure view
- [x] M11 template coverage
- [x] Section navigation

---

## Phase 4: Advanced Features (Priority: Low) ✅

### 4.1 USDM Extensions
- [x] Extension summary
- [x] Extension types by URL
- [x] Entity-level extension details

### 4.2 Advanced Entities
- [x] Biomedical concepts
- [x] Estimands
- [x] Indications
- [x] Therapeutic areas

### 4.3 Procedures & Devices
- [x] Medical devices list
- [x] Procedure definitions
- [x] Safety requirements

### 4.4 Study Sites
- [x] Site list
- [x] Geographic distribution
- [x] Organization details

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
| Phase 1 | 2-3 days | ✅ Complete |
| Phase 2 | 1-2 days | ✅ Complete |
| Phase 3 | 1 day | ✅ Complete |
| Phase 4 | 2-3 days | ✅ Complete |

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
- [x] USDM Extensions tab
- [x] Validation API integration
- [x] SoA Images viewer
- [x] Advanced Entities tab (Phase 4)
- [x] Procedures & Devices tab (Phase 4)
- [x] Study Sites tab (Phase 4)
- [x] Tab overflow handling

## Final Tab Count: 17

| Tab | Component | Description |
|-----|-----------|-------------|
| Overview | StudyMetadataView | Study identification, sponsor, dates |
| Eligibility | EligibilityCriteriaView | Inclusion/exclusion criteria |
| Objectives | ObjectivesEndpointsView | Primary/secondary/exploratory |
| Design | StudyDesignView | Arms, epochs, cells matrix |
| Interventions | InterventionsView | Drugs, products, dosing |
| Amendments | AmendmentHistoryView | Amendment timeline |
| Extensions | ExtensionsView | USDM custom extensions |
| Entities | AdvancedEntitiesView | Indications, biomedical concepts |
| Procedures | ProceduresDevicesView | Medical procedures/devices |
| Sites | StudySitesView | Study sites, organizations |
| Quality | QualityMetricsDashboard | Entity counts, linkage metrics |
| Validation | ValidationResultsView | Extraction validation issues |
| Document | DocumentStructureView | M11 template coverage |
| Images | SoAImagesTab | SoA page image viewer |
| SoA | SoAView | Schedule of Activities grid |
| Timeline | TimelineView | Cytoscape visualization |
| Provenance | ProvenanceView | Source attribution |

## Commits

1. `7c3b14f` - Web UI improvements (Next.js 15+, AG Grid, Timeline)
2. `84fd72e` - Phase 1: Protocol Expansion Data Tabs
3. `91d4c6b` - Phase 2: Quality Metrics Dashboard
4. `1256e9f` - Fix missing Badge and Progress UI components
5. `0512ff5` - Phase 3: Intermediate Data Views
6. `82d1a43` - Add USDM Extensions display tab
7. `4d0c0cf` - Add Validation API endpoint and tab
8. `4798f65` - Add SoA Images API and viewer tab
9. `TBD` - Phase 4: Advanced Features (Entities, Procedures, Sites)
