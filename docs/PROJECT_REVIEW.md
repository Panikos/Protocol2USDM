# Protocol2USDM v7.2 — Comprehensive Project Review

**Date:** Feb 8, 2026  
**Scope:** Full codebase review covering backend pipeline, extraction modules, web UI, data model, editability, and UX

---

## 1. Architecture Overview

### What This Project Does
Protocol2USDM extracts clinical trial protocol information from PDF documents and converts it into USDM v4.0 (Unified Study Definitions Model) JSON format. It then provides a web viewer/editor for reviewing, editing, and publishing the extracted data.

### System Components
| Layer | Technology | Key Files |
|-------|-----------|-----------|
| **CLI entrypoint** | Python | `main_v3.py` |
| **Pipeline orchestrator** | Python, registry pattern | `pipeline/orchestrator.py`, `pipeline/base_phase.py` |
| **12 extraction phases** | Python + LLM (Gemini/GPT) | `pipeline/phases/*.py`, `extraction/` |
| **Core modules** | Python | `core/` (schema, validation, reconciliation, terminology) |
| **Execution model** | Python | `extraction/execution/` (13+ extractors + promoter) |
| **Validation** | Python + USDM package | `validation/`, `core/validation.py` |
| **Web UI** | Next.js 14, React, TypeScript | `web-ui/` |
| **State management** | Zustand + immer | `web-ui/stores/` (4 stores) |
| **Visualization** | AG Grid, Cytoscape.js | `web-ui/components/soa/`, `timeline/` |
| **Editing** | JSON Patch (RFC 6902) | `web-ui/lib/semantic/`, `web-ui/stores/semanticStore.ts` |

### Data Flow
```
PDF → (LLM extraction × 12 phases) → phase JSONs → combine_to_full_usdm() 
    → reconciliation → normalization → UUID conversion → validation 
    → protocol_usdm.json → Web UI (read from output dir via Next.js API)
```

---

## 2. Strengths

### 2.1 Pipeline Architecture (Excellent)
- **Registry-driven phase system**: `BasePhase` → `PhaseConfig` → `phase_registry` is clean, extensible, and well-separated. Adding a new extraction phase requires only subclassing `BasePhase` and registering.
- **Parallel execution**: `run_phases_parallel()` with dependency waves, context snapshots, and merge-back is production-grade. `PHASE_DEPENDENCIES` graph is explicit and enforced.
- **Fault isolation**: Individual try/except around promoter steps 2-10 prevents cascading failures — a critical operational requirement for LLM-dependent extraction.
- **Context propagation**: `PipelineContext` with `snapshot()` / `merge_from()` provides clean inter-phase data sharing.

### 2.2 USDM Compliance (Strong)
- Schema pinned to v4.0 with hash verification (`core/usdm_schema_loader.py`).
- `normalize_usdm_data()` and `convert_ids_to_uuids()` ensure output conformance.
- CDISC conformance engine integration (`validation/cdisc_conformance.py`).
- Run manifest with input hash, model, schema version for full reproducibility.

### 2.3 Execution Model (Ambitious, Deep)
- 10-step promotion pipeline converting extracted semantics into native USDM entities (ScheduledActivityInstances, TransitionRules, Conditions, Administrations).
- Full state machine extraction with protocol-specific epoch names.
- Visit window, dosing regimen, and footnote condition extraction.
- ISO 8601 duration parsing, fuzzy activity matching (3-tier: exact → substring → word overlap).

### 2.4 Reconciliation Framework (Well-Designed)
- `encounter_reconciler.py` merges encounter data from SoA, scheduling, and execution model sources.
- CDISC encounter type inference from names.
- Transition rule preservation through reconciliation (the fix we just applied).

### 2.5 Web UI Foundation (Solid)
- Modern stack: Next.js 14 + App Router, Zustand, AG Grid, Cytoscape.js, Tailwind, shadcn/ui.
- 21+ tabs covering every USDM domain (overview, eligibility, objectives, design, interventions, amendments, extensions, entities, procedures, sites, footnotes, schedule, narrative, quality, validation, documents, intermediate, SoA, timeline, provenance).
- Two-layer editing system: Overlay (layout/visual) + Semantic (data/JSON Patch).
- `usePatchedUsdm()` hook elegantly applies draft patches on top of raw USDM for all views.
- Export to CSV/JSON/PDF.

### 2.6 Provenance Tracking
- Cell-level source attribution (text extraction vs. vision validation).
- `needsReview` flags for uncertain cells.
- Provenance-colored SoA cells in AG Grid.

---

## 3. Weaknesses

### 3.1 Editability Gap — The Core Problem

**Current state**: The system is fundamentally an *extraction viewer with limited editing*, not a *protocol authoring tool*. Here's the breakdown:

| Component | View | Edit | Gap |
|-----------|------|------|-----|
| Study metadata (title, phase, indication) | Yes | Yes (EditableField) | Acceptable |
| Eligibility criteria text | Yes | Yes (EditableField) | No add/remove/reorder |
| Objectives & endpoints | Yes | Yes (EditableField) | No add/remove |
| Study design (arms, epochs, elements) | Yes | Partial (names only) | Cannot add/remove arms/epochs |
| SoA table cells | Yes | Yes (double-click) | Good — best editing UX |
| SoA rows/columns (activities/encounters) | Yes | Add + rename | Cannot delete or reorder freely |
| Visit windows | Yes | No | Read-only display |
| Dosing regimens | Yes | No | Read-only display |
| State machine / transitions | Yes | No | Read-only display |
| Repetitions | Yes | No | Read-only display |
| Footnote conditions | Yes | No | Read-only display |
| Timeline graph | Yes | Layout only | Cannot add/remove nodes or edges |
| Schedule timeline (instances/timings) | Yes | No | Read-only display |
| Narrative sections | Yes | No | Read-only display |
| Crossover design | Yes | No | Read-only display |

**Root cause**: `EditableField` only handles scalar values via JSON Patch `replace` ops. There is no generic mechanism for:
- Adding items to arrays (new eligibility criterion, new arm, new epoch)
- Removing items from arrays
- Reordering arrays (drag-and-drop for arms, epochs, criteria)
- Editing complex nested objects (visit window with multiple fields)
- Inline table editing for structured data (dosing table, visit window table)

### 3.2 Store Complexity / Split-Brain Risk
There are **4 Zustand stores** managing editing state:
1. `protocolStore` — raw USDM data + metadata
2. `overlayStore` — diagram layout + table column/row order
3. `semanticStore` — JSON Patch operations for data changes
4. `soaEditStore` — SoA cell/activity/encounter edits (pending → committed → semantic)

The SoA editing flow is: `soaEditStore.pendingCellEdits` → `commitChanges()` → `semanticStore.addPatchOp()` → `semanticStore.draft.patch` → save to server → publish → apply to USDM → reload.

This 4-store chain creates:
- **Sync complexity**: `clearDraft` in semanticStore has a comment "Don't reset soaEditStore here" and uses a dynamic import hack (`let resetSoAEditStore: (() => void) | null = null; import(...)`)
- **State desync risk**: If any store gets out of sync, the UI shows stale/incorrect data
- **Mental model burden**: A developer must understand all 4 stores to trace any edit flow

### 3.3 No Undo/Redo
No undo capability exists. `semanticStore` accumulates patch ops but offers no way to step backward. If a user makes 10 edits and realizes edit #3 was wrong, the only option is `clearPatch()` (discard all).

### 3.4 Execution Model View is Read-Only
`ExecutionModelView.tsx` (3,184 lines) is the largest component. It renders 10 tabs (overview, anchors, visits, conditions, repetitions, dosing, state machine, traversal, issues, schedule) — all **read-only**. The `EditableField` import exists but is barely used (only on footnote conditions and only for display). The state machine, dosing regimens, visit windows, and repetitions cannot be edited at all.

### 3.5 Graph View Has No Data Editing
`TimelineView.tsx` + `TimelineCanvas.tsx` (Cytoscape.js) support:
- Zoom, pan, fit, fullscreen
- Drag-to-reposition nodes (persisted via overlay)
- Node detail panel on click
- PNG export

But they **do not support**:
- Adding new nodes (visits, activities)
- Adding/removing edges (timings, transitions)
- Editing node properties inline
- Creating new schedule timelines

### 3.6 Backend is Extraction-Only, No Write-Back
The Python backend only produces `protocol_usdm.json` as output. The web UI saves edits as JSON Patch files in `semantic/<protocolId>/`, and the publish step applies patches to produce a new USDM file. But there is **no way to**:
- Re-run extraction with edits fed back as corrections
- Incrementally update a single phase (e.g., re-extract eligibility only)
- Trigger extraction from the web UI

### 3.7 Type Safety Gaps in Frontend
- USDM data is passed as `Record<string, unknown>` or `any` throughout components
- Every view component has to manually navigate `usdm.study.versions[0].studyDesigns[0]` with unsafe casts
- No shared TypeScript type definitions for the USDM schema (each component defines its own interfaces locally)

### 3.8 No Real-Time Collaboration
Single-user only. No WebSocket/SSE for multi-user awareness. The `updatedBy: 'ui-user'` field is hardcoded.

### 3.9 Dead Code / Debug Scripts
Root directory contains leftover scripts: `audit_promoter.py`, `check_usdm.py`, `check_em.py`, `test_promoter_direct.py`. The `archive/` directory has 135 items. The `tools/` directory has 901 items.

---

## 4. Enhancement Recommendations

### 4.1 Priority 1: Universal Editable Component System

**Problem**: `EditableField` only handles scalars. Most USDM entities are complex objects in arrays.

**Solution**: Build a component hierarchy:

```
EditableField          — scalar (text, number, boolean) ✅ exists
EditableObject         — multi-field form for a single object (new)
EditableList           — add/remove/reorder items in an array (new)
EditableTable          — tabular editor for array of uniform objects (new)
EditableCodedValue     — dropdown for CDISC coded values (new)
```

**Implementation plan**:

1. **`EditableObject`** — renders a card with multiple `EditableField`s for a single entity. Takes a `basePath` and a `schema` describing fields. Each field generates its own JSON Patch op.

```tsx
<EditableObject
  basePath="/study/versions/0/studyDesigns/0/arms/0"
  schema={[
    { key: 'name', label: 'Arm Name', type: 'text' },
    { key: 'description', label: 'Description', type: 'textarea' },
    { key: 'type.decode', label: 'Type', type: 'coded', codeList: 'armType' },
  ]}
/>
```

2. **`EditableList`** — wraps an array of `EditableObject`s with add/remove/reorder. Generates `add` / `remove` / `move` JSON Patch ops.

```tsx
<EditableList
  basePath="/study/versions/0/studyDesigns/0/arms"
  items={arms}
  renderItem={(arm, index) => <ArmEditor arm={arm} index={index} />}
  onAdd={() => ({ id: uuid(), name: 'New Arm', instanceType: 'StudyArm' })}
/>
```

3. **`EditableTable`** — AG Grid-based editor for tabular data (visit windows, dosing levels, eligibility criteria). Supports inline cell editing, row add/delete, column sorting.

4. **`EditableCodedValue`** — dropdown populated from CDISC terminology (already cached in `core/evs_cache/`). Generates proper `{ code, codeSystem, decode }` patch values.

### 4.2 Priority 2: Specific Domain Editors

Using the component system from 4.1, build editors for:

| Domain | Editor Type | Key Fields |
|--------|-----------|------------|
| **Arms** | EditableList + EditableObject | name, description, type (coded) |
| **Epochs** | EditableList + EditableObject | name, description, type (coded) |
| **Eligibility criteria** | EditableList + EditableObject | text, category (inclusion/exclusion), identifier |
| **Visit windows** | EditableTable | visitName, targetDay, windowBefore, windowAfter, epoch, isRequired |
| **Dosing regimens** | EditableTable | treatmentName, dose, unit, frequency, route, startDay, endDay |
| **Study design matrix** | Custom grid | arms × epochs → study cells → study elements |
| **State machine** | Visual editor (Cytoscape) | states (add/remove), transitions (draw edges), triggers |
| **Footnote conditions** | EditableList | footnoteId, text, conditionType, structured condition |
| **Repetitions** | EditableTable | activityName, type, interval, count, startOffset, endOffset |

### 4.3 Priority 3: Graph-Based Schedule Editor

Transform the Timeline Graph View from read-only visualization to an interactive schedule editor:

1. **Add nodes**: Right-click canvas → "Add Visit" / "Add Activity" → positions new node
2. **Draw edges**: Drag from node handle → target node → creates timing relationship with configurable offset
3. **Edit inline**: Double-click node → popup form for encounter/activity properties
4. **Delete**: Select + Delete key, with confirmation for entities that have dependencies
5. **Validate live**: Show validation errors as red borders / warning icons on invalid nodes
6. **Sync to USDM**: All graph edits generate JSON Patch ops through the semantic store

This requires extending `toGraphModel.ts` to support bidirectional conversion (graph → USDM patches) and adding Cytoscape event handlers for `cxttap`, `ehcomplete` (edge handle), etc.

### 4.4 Priority 4: Undo/Redo Stack

```ts
// Add to semanticStore
undoStack: JsonPatchOp[][];  // previous states
redoStack: JsonPatchOp[][];

undo: () => void;  // pop last op group from patch, push to redo
redo: () => void;  // pop from redo, push back to patch
```

Group related ops (e.g., adding an arm also adds a study cell) into atomic undo groups.

### 4.5 Priority 5: Consolidated Store Architecture

Merge the 4 stores into 2:

| Current | Proposed |
|---------|----------|
| `protocolStore` | `protocolStore` (unchanged — raw data source) |
| `overlayStore` + `soaEditStore` + `semanticStore` | `editStore` (single editing store) |

The unified `editStore` would:
- Hold all JSON Patch ops (semantic + layout)
- Track dirty state in one place
- Support undo/redo at the unified level
- Eliminate the `soaEditStore` → `semanticStore` commit indirection

### 4.6 Priority 6: Shared USDM Type Definitions

Generate TypeScript types from the USDM v4.0 schema (the schema is already downloaded and cached in `core/schema_cache/`):

```ts
// Generated from USDM schema
export interface StudyDesign {
  id: string;
  name?: string;
  arms: StudyArm[];
  epochs: StudyEpoch[];
  activities: Activity[];
  encounters: Encounter[];
  scheduleTimelines: ScheduleTimeline[];
  // ... full type
}
```

This replaces all the `Record<string, unknown>` casts and per-component interface redefinitions.

### 4.7 Priority 7: Web UI → Backend Integration

Add API routes to:
1. **Trigger extraction**: `POST /api/protocols/extract` — upload PDF, start pipeline, return job ID
2. **Re-extract single phase**: `POST /api/protocols/:id/reextract/:phase` — re-run one phase using existing data
3. **Status polling**: `GET /api/protocols/:id/status` — extraction progress
4. **Feedback loop**: Published edits inform re-extraction (e.g., corrected eligibility criteria improve next extraction)

### 4.8 Priority 8: Clean Up Technical Debt

1. Delete root-level debug scripts (`audit_promoter.py`, `check_usdm.py`, `check_em.py`, `test_promoter_direct.py`, `debug_anchors.py` tab)
2. Audit `archive/` (135 items) and `tools/` (901 items) — move or delete unused files
3. Add `py.typed` marker and strict mypy config for the Python codebase
4. Consolidate duplicate type definitions across `ExecutionModelView.tsx`, `toGraphModel.ts`, `ScheduleTimelineView.tsx`

---

## 5. UI/UX Recommendations

### 5.1 Edit Mode Toggle
Add a global "Edit Mode" toggle in the header. When off, all `EditableField`s render as plain text (no hover pencil icon). When on, editable fields show subtle blue borders and the pencil icon. This reduces visual noise in review mode.

### 5.2 Inline Validation Feedback
When a user edits a field, validate immediately:
- Type validation (number field must be numeric)
- Referential integrity (arm ID referenced in study cell must exist)
- USDM schema validation (required fields)
Show inline red/yellow borders with tooltips, not just after publish.

### 5.3 Diff View Before Publish
Before publishing, show a visual diff of all changes:
- Side-by-side or unified diff of JSON Patch ops
- Color-coded: green (added), red (removed), yellow (changed)
- Group by entity type (arms, encounters, activities, etc.)

### 5.4 Better SoA Editing UX
The SoA grid is the most complete editor but could improve:
- **Keyboard navigation**: Arrow keys to move between cells, Enter to toggle X/O
- **Bulk operations**: Select multiple cells → "Mark all X" / "Clear all"
- **Column operations**: Right-click column header → "Delete visit" / "Insert visit before"
- **Row grouping drag**: Drag activities between groups

### 5.5 Visit Schedule Gantt Chart
Add a horizontal Gantt-style chart showing:
- X-axis: study days
- Y-axis: epochs/visits
- Bars: visit windows (target ± window)
- Hover: show all activities at that visit
- Click-to-edit: drag bar edges to adjust windows

### 5.6 State Machine Visual Editor
Replace the read-only state list with an interactive Cytoscape graph:
- Drag-and-drop to add new states
- Draw edges between states to define transitions
- Click edge to set trigger/guard condition
- Auto-layout with dagre
- Show unreachable states as warnings

### 5.7 Breadcrumb Navigation
The 21-tab layout is overwhelming. Add breadcrumb context:
```
Protocol > NCT04573309 > Design > Arms
```
And consider collapsing rarely-used tabs into a "More..." dropdown.

### 5.8 Keyboard Shortcuts
| Shortcut | Action |
|----------|--------|
| `Ctrl+S` | Save draft |
| `Ctrl+Z` | Undo |
| `Ctrl+Shift+Z` | Redo |
| `Ctrl+E` | Toggle edit mode |
| `Ctrl+P` | Publish |
| `Tab` / `Shift+Tab` | Next/previous editable field |

---

## 6. Prioritized Implementation Roadmap

### Phase A: Foundation (1-2 weeks)
1. Shared USDM TypeScript types (4.6)
2. Undo/redo in semantic store (4.4)
3. Edit mode toggle (5.1)
4. Clean up debug scripts (4.8)

### Phase B: Component System (2-3 weeks)
1. `EditableObject` component (4.1)
2. `EditableList` component with add/remove/reorder (4.1)
3. `EditableCodedValue` with CDISC terminology (4.1)
4. Diff view before publish (5.3)

### Phase C: Domain Editors (3-4 weeks)
1. Arms/epochs editor (4.2)
2. Eligibility criteria editor with add/remove (4.2)
3. Visit windows table editor (4.2)
4. Dosing regimens table editor (4.2)
5. Footnote conditions editor (4.2)

### Phase D: Visual Editors (4-6 weeks)
1. Graph-based schedule editor (4.3)
2. State machine visual editor (5.6)
3. Gantt chart for visit schedule (5.5)
4. SoA keyboard navigation + bulk ops (5.4)

### Phase E: Integration (2-3 weeks)
1. Store consolidation (4.5)
2. Web UI → backend extraction trigger (4.7)
3. Keyboard shortcuts (5.8)

---

## 7. Summary Verdict

**Protocol2USDM is a technically impressive extraction pipeline with a strong architectural foundation.** The registry-driven phase system, parallel execution, reconciliation framework, and USDM v4.0 compliance are production-quality. The execution model promotion (10-step pipeline converting extracted semantics to native USDM entities) is particularly ambitious and well-executed.

**The primary gap is editability.** The web UI excels at *displaying* extracted data across 21 tabs but only allows editing of scalar text fields and SoA table cells. Complex entities (arms, epochs, visit windows, dosing regimens, state machines, transitions) are read-only. The 4-store architecture adds unnecessary complexity.

**The highest-impact improvements are:**
1. A reusable component system (`EditableObject`, `EditableList`, `EditableTable`) that enables editing any USDM entity
2. Undo/redo support
3. Visual editors for the state machine and schedule timeline
4. Shared TypeScript types from the USDM schema

The extraction pipeline is the strong suit; the editing layer is where investment should focus next.
