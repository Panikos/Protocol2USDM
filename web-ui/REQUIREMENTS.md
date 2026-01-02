# Protocol2USDM Modern Web UI - Requirements Document

> Generated: 2025-12-30
> Version: 1.0

## Table of Contents
1. [Technology Stack](#1-technology-stack)
2. [Architecture](#2-architecture)
3. [Overlay Schema](#3-overlay-schema)
4. [Core Features](#4-core-features)
5. [API Endpoints](#5-api-endpoints)
6. [UX Requirements](#6-ux-requirements)
7. [MVP Milestones](#7-mvp-milestones)

---

## 1. Technology Stack

### 1.1 Core Framework
| Technology | Purpose | Justification |
|------------|---------|---------------|
| **Next.js 14+** | App framework | Server components, API routes, ISR for performance |
| **TypeScript** | Type safety | Critical for USDM schema enforcement |
| **Tailwind CSS** | Styling | Rapid iteration, design system consistency |
| **shadcn/ui** | Component library | Accessible, customizable primitives |

### 1.2 Locked-In Libraries
| Library | Purpose |
|---------|---------|
| **AG Grid Enterprise** | SoA tables with row/column reordering, grouping, virtualization |
| **Cytoscape.js** | Timeline/profile diagrams with manual layout |

### 1.3 Additional Libraries
| Library | Purpose |
|---------|---------|
| **Zustand** | State management (lightweight, TS-first) |
| **TanStack Query** | Server state, caching, mutations |
| **Zod** | Runtime schema validation (USDM + Overlay) |
| **Framer Motion** | Micro-interactions, transitions |
| **Lucide React** | Icons |
| **Monaco Editor** | JSON viewer/editor (provenance, overlay debug) |
| **React PDF** | PDF source document viewer |

---

## 2. Architecture

### 2.1 Data Layers

1. **USDM (canonical)** - Produced by pipeline, semantic source-of-truth
2. **Overlay (presentation + authoring)** - Stores layout, ordering, presentation-only data
3. **Adapters (pure functions)** - Transform USDM + Overlay into view models

### 2.2 USDM Entity Locations (v6.6)

UI components read data from USDM-compliant paths per `dataStructure.yml`:

| Data | USDM Path |
|------|----------|
| Eligibility Criteria | `studyDesign.eligibilityCriteria[]` |
| Criterion Items (text) | `studyVersion.eligibilityCriterionItems[]` |
| Organizations | `studyVersion.organizations[]` |
| Interventions | `studyVersion.studyInterventions[]` |
| Products | `studyVersion.administrableProducts[]` |
| Devices | `studyVersion.medicalDevices[]` |
| Timings | `scheduleTimeline.timings[]` |
| Indications | `studyDesign.indications[]` |
| Procedures | `activity.definedProcedures[]` |
| Narrative | `studyVersion.narrativeContentItems[]` |
| Abbreviations | `studyVersion.abbreviations[]` |

### 2.3 Key Principles

- **USDM is the semantic source-of-truth**
- **Overlay is presentation-only**, never semantic
- **Draft / Publish workflow** for authoring control
- Renderers consume adapter output, never parse USDM directly

### 2.4 Data Flow

```
BACKEND (Python Pipeline)
    ↓
USDM Store → Provenance Store
    ↓
NEXT.JS API ROUTES
    ↓
ADAPTERS (toSoATableModel, toGraphModel)
    ↓
RENDERERS (AG Grid, Cytoscape.js)
```

---

## 3. Overlay Schema

### 3.1 Overlay Document Structure

```typescript
type OverlayDoc = {
  version: number;
  protocolId: string;
  usdmRevision: string;
  status: "draft" | "published";
  updatedAt: string;
  updatedBy: string;
  basePublishedId?: string;
  payload: OverlayPayload;
};

type OverlayPayload = {
  diagram: {
    nodes: Record<string, { x: number; y: number; locked?: boolean; highlight?: boolean; icon?: string }>;
    edges?: Record<string, { style?: string }>;
    globals?: { snapGrid?: number };
  };
  table: {
    rowOrder?: string[];
    columnOrder?: string[];
    rowGroups?: { label: string; activityIds: string[] }[];
    columnGroups?: { label: string; visitIds: string[] }[];
    hiddenColumns?: string[];
  };
};
```

### 3.2 Hard Rule

Overlay keys must be **stable IDs derived from USDM** wherever possible.

---

## 4. Core Features

### 4.1 SoA Table (AG Grid)

- Activities as rows, visits/timepoints as columns
- Marks: X / Xa / Xb with provenance coloring
- Row/column reordering → updates draft overlay
- Grouping headers from USDM epochs/phases
- Footnote superscripts per cell
- Export to CSV

### 4.2 Timeline Diagram (Cytoscape.js)

- Graph structure from USDM scheduleTimelines
- Preset layout with positions from overlay
- Drag nodes to reposition (snap-to-grid)
- Lock/unlock nodes
- Node types: instance, timing, activity, condition, halo

### 4.3 Provenance System

- Cell-level provenance: text / vision / both / orphaned
- Color coding: green (confirmed), blue (text), orange (vision), red (orphaned)
- PDF source viewer with bounding box highlighting
- Footnote panel

### 4.4 Draft/Publish Workflow

- Load published overlay on open
- Edits mutate draft only
- Save Draft / Publish / Reset to Published
- Dirty state indicator
- USDM revision reconciliation

---

## 5. API Endpoints

### 5.1 USDM API
- `GET /protocols/:id/usdm` → returns latest USDM + revision

### 5.2 Overlay APIs
- `GET /protocols/:id/overlay/published?usdmRevision=...`
- `GET /protocols/:id/overlay/draft?user=...&usdmRevision=...`
- `PUT /protocols/:id/overlay/draft` → save draft
- `POST /protocols/:id/overlay/publish` → promote draft → published
- `POST /protocols/:id/overlay/reset` → reset draft to published

### 5.3 Semantic Patch API
- `POST /protocols/:id/patch` → submit semantic change (mark edits)

---

## 6. UX Requirements

### 6.1 Non-Negotiable

- Always show draft vs published state
- Always show dirty state
- Publish requires explicit confirmation
- Reset requires explicit confirmation
- JSON export/import for overlay (debug feature)
- Keyboard shortcuts (Save, Undo, Lock)

### 6.2 Provenance Colors

| State | Color | Meaning |
|-------|-------|---------|
| Confirmed | Green (#4ade80) | Text + vision agree |
| Text-only | Blue (#60a5fa) | Text extraction only |
| Vision-only | Orange (#fb923c) | Needs review |
| Orphaned | Red (#f87171) | No provenance data |

### 6.3 Accessibility

- WCAG 2.1 AA compliance
- Keyboard navigation
- Screen reader support
- Color contrast ≥ 4.5:1

---

## 7. MVP Milestones

### Milestone 1: Foundation (Week 1-2)
- Next.js project setup
- API routes (stub data)
- Overlay Zustand store
- Basic protocol pages

### Milestone 2: SoA Table (Week 3-4)
- AG Grid integration
- toSoATableModel adapter
- Provenance cell renderer
- Row/column reordering

### Milestone 3: Timeline Diagram (Week 5-6)
- Cytoscape.js integration
- toGraphModel adapter
- Preset layout with overlay
- Node drag, snap-to-grid, lock

### Milestone 4: Provenance & Polish (Week 7-8)
- Provenance explorer
- PDF source viewer
- Draft/publish workflow
- Reconciliation UI

### Milestone 5: Semantic Editing (Week 9-10)
- Mark editing → semantic patch
- Pipeline integration
- Real-time USDM reload
