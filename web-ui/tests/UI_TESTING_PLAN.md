# Protocol2USDM Web UI — Testing Plan

> **Framework:** Playwright (E2E) + Vitest (unit/integration)
> **Target:** Next.js 16 app at `web-ui/`
> **Last Updated:** 2026-02-08

---

## Table of Contents

1. [Setup & Infrastructure](#1-setup--infrastructure)
2. [Test Data Strategy](#2-test-data-strategy)
3. [Page-Level Smoke Tests](#3-page-level-smoke-tests)
4. [Navigation & Routing](#4-navigation--routing)
5. [Protocol List Page](#5-protocol-list-page)
6. [Protocol Detail Page — Tab Rendering](#6-protocol-detail-page--tab-rendering)
7. [SoA Table (AG Grid)](#7-soa-table-ag-grid)
8. [Edit Mode & Semantic Drafts](#8-edit-mode--semantic-drafts)
9. [Inline Editing Primitives](#9-inline-editing-primitives)
10. [Draft Lifecycle (Save / Publish / Discard)](#10-draft-lifecycle-save--publish--discard)
11. [Undo / Redo](#11-undo--redo)
12. [Version History & Revert](#12-version-history--revert)
13. [Timeline Views](#13-timeline-views)
14. [Documents & Intermediate Files](#14-documents--intermediate-files)
15. [Export Functionality](#15-export-functionality)
16. [Quality & Validation Tabs](#16-quality--validation-tabs)
17. [Unsaved Changes Guard](#17-unsaved-changes-guard)
18. [Toast Notifications](#18-toast-notifications)
19. [Responsive / Layout](#19-responsive--layout)
20. [API Route Tests (Integration)](#20-api-route-tests-integration)
21. [Store Unit Tests (Vitest)](#21-store-unit-tests-vitest)
22. [Adapter / Helper Unit Tests](#22-adapter--helper-unit-tests)
23. [Accessibility](#23-accessibility)
24. [Performance](#24-performance)
25. [Security (UI Surface)](#25-security-ui-surface)

---

## 1. Setup & Infrastructure

### 1.1 Install Dependencies

```bash
cd web-ui
npm install -D @playwright/test vitest @vitejs/plugin-react jsdom @testing-library/react
npx playwright install --with-deps chromium firefox
```

### 1.2 Config Files

| File | Purpose |
|------|---------|
| `playwright.config.ts` | E2E config — base URL `http://localhost:3000`, projects for chromium + firefox + mobile-chrome |
| `vitest.config.ts` | Unit/integration — jsdom env, path aliases matching `tsconfig.json` |
| `tests/fixtures/` | Shared test data (mock USDM JSON, protocol stubs) |
| `tests/e2e/` | Playwright specs |
| `tests/unit/` | Vitest specs |

### 1.3 CI Integration

```yaml
# .github/workflows/ui-tests.yml
jobs:
  e2e:
    steps:
      - uses: actions/checkout@v4
      - run: npm ci && npx playwright install --with-deps
        working-directory: web-ui
      - run: npm run build
        working-directory: web-ui
      - run: npx playwright test
        working-directory: web-ui
  unit:
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
        working-directory: web-ui
      - run: npx vitest run
        working-directory: web-ui
```

### 1.4 Scripts (add to `package.json`)

```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest",
    "test:e2e": "playwright test",
    "test:e2e:ui": "playwright test --ui"
  }
}
```

---

## 2. Test Data Strategy

### 2.1 Fixture Protocol

Create `tests/fixtures/wilson_protocol_usdm.json` — a trimmed snapshot of a real extraction output (~50 activities, ~12 encounters, 3 epochs, 2 arms). This ensures tests exercise real data shapes.

### 2.2 Minimal Protocol

Create `tests/fixtures/minimal_usdm.json` — smallest valid USDM with 1 activity, 1 encounter, 1 epoch. Used for fast unit tests.

### 2.3 API Mocking Strategy

| Layer | Approach |
|-------|----------|
| **E2E (Playwright)** | `page.route()` to intercept `/api/protocols/**` and return fixture JSON |
| **Unit (Vitest)** | Direct import of adapters/stores; mock `fetch` via `vi.fn()` |

### 2.4 Seed Script (optional)

```bash
# Copy fixture USDM to output dir so the real API can serve it
cp tests/fixtures/wilson_protocol_usdm.json ../output/TEST_PROTO/protocol_usdm.json
```

---

## 3. Page-Level Smoke Tests

**File:** `tests/e2e/smoke.spec.ts`

| # | Test | Assertion |
|---|------|-----------|
| 3.1 | Home page loads | Title "Protocol2USDM", "Browse Protocols" button visible |
| 3.2 | `/protocols` loads | "Available Protocols" heading visible |
| 3.3 | `/protocols/TEST_PROTO` loads | Protocol ID in header, no error card |
| 3.4 | Unknown protocol shows error | `/protocols/NONEXISTENT` → "Error Loading Protocol" card |
| 3.5 | Back button navigates | Click "Back" → URL is `/protocols` |

---

## 4. Navigation & Routing

**File:** `tests/e2e/navigation.spec.ts`

| # | Test | Steps | Assertion |
|---|------|-------|-----------|
| 4.1 | Home → Protocols | Click "Browse Protocols" | URL = `/protocols` |
| 4.2 | Protocols → Detail | Click "View Protocol" on card | URL = `/protocols/{id}` |
| 4.3 | Detail → Back | Click "Back" button | URL = `/protocols` |
| 4.4 | Header logo → Home | Click logo from `/protocols` | URL = `/` |
| 4.5 | Direct URL access | Navigate to `/protocols/TEST_PROTO` directly | Page renders correctly |

---

## 5. Protocol List Page

**File:** `tests/e2e/protocol-list.spec.ts`

| # | Test | Assertion |
|---|------|-----------|
| 5.1 | Loading spinner shown | Loader2 icon visible before data loads |
| 5.2 | Protocol cards render | Card count matches API response |
| 5.3 | Card shows metadata | Activity count, encounter count, USDM version, date visible |
| 5.4 | Empty state | Mock API returns 0 protocols → "No Protocols Found" + extraction command shown |
| 5.5 | Error state | Mock API returns 500 → error message + "Retry" button visible |
| 5.6 | Retry reloads | Click "Retry" after error → loading spinner reappears |

---

## 6. Protocol Detail Page — Tab Rendering

**File:** `tests/e2e/tabs.spec.ts`

Each tab should render without crashing and display its primary content. Use `page.route()` to mock the USDM API response with fixture data.

### 6.1 Protocol Tab Group

| Tab ID | Expected Content |
|--------|-----------------|
| `overview` | Study design name, stats cards (Activities, Encounters, Epochs, Arms) |
| `eligibility` | Inclusion/exclusion criteria list or "No criteria" |
| `objectives` | Primary/secondary objectives or "No objectives" |
| `design` | Arms table, epochs, blinding info |
| `interventions` | Drug/intervention cards or "No interventions" |
| `amendments` | Amendment history or "No amendments" |

### 6.2 Advanced Tab Group

| Tab ID | Expected Content |
|--------|-----------------|
| `extensions` | Extension attribute list with URL + value columns |
| `entities` | Entity cards (biospecimens, etc.) |
| `procedures` | Procedure/device list |
| `sites` | Study site list or "No sites" |
| `footnotes` | Footnote text items |
| `schedule` | ScheduleTimeline detail view |
| `narrative` | Narrative content blocks |

### 6.3 Quality Tab Group

| Tab ID | Expected Content |
|--------|-----------------|
| `quality` | Quality metrics dashboard with score/bar chart |
| `validation` | Validation results — schema, USDM, CDISC conformance |

### 6.4 Data Tab Group

| Tab ID | Expected Content |
|--------|-----------------|
| `documents` | Source document list (PDF/CSV names) |
| `intermediate` | Intermediate JSON file list |
| `document` | Document structure tree |
| `soa` | AG Grid table with activities × encounters |
| `timeline` | Execution model panels |
| `provenance` | Provenance stats/explorer |

### Test Template

```typescript
test('tab: overview renders stats', async ({ page }) => {
  await page.goto('/protocols/TEST_PROTO');
  // Overview is default tab
  await expect(page.getByText('Activities')).toBeVisible();
  await expect(page.getByText('Encounters')).toBeVisible();
});

test('tab: soa renders grid', async ({ page }) => {
  await page.goto('/protocols/TEST_PROTO');
  await page.getByRole('button', { name: /Data/i }).click();
  await page.getByRole('button', { name: /SoA Table/i }).click();
  await expect(page.locator('.ag-root-wrapper')).toBeVisible();
});
```

---

## 7. SoA Table (AG Grid)

**File:** `tests/e2e/soa-table.spec.ts`

### 7.1 Rendering

| # | Test | Assertion |
|---|------|-----------|
| 7.1.1 | Grid renders | `.ag-root-wrapper` visible, row count > 0 |
| 7.1.2 | Activities as rows | Row labels match fixture activity names |
| 7.1.3 | Encounters as columns | Column headers match fixture encounter names |
| 7.1.4 | Cell marks displayed | Cells with `X` marks are visible |
| 7.1.5 | Grouped rows | Activity groups appear as expandable sections |

### 7.2 Toolbar

| # | Test | Assertion |
|---|------|-----------|
| 7.2.1 | Search filter | Type activity name → only matching rows visible |
| 7.2.2 | "Needs Review" toggle | Toggle on → only flagged rows shown |
| 7.2.3 | Stats bar | "X activities × Y visits" count shown |

### 7.3 Keyboard Navigation (Edit Mode Only)

> **Precondition:** Toggle edit mode ON first.

| # | Key | Expected |
|---|-----|----------|
| 7.3.1 | `X` | Cell mark set to "X" |
| 7.3.2 | `O` | Cell mark set to "O" |
| 7.3.3 | `-` | Cell mark set to "−" |
| 7.3.4 | `Delete` | Cell mark cleared |
| 7.3.5 | `Enter` | Cell editor opens |
| 7.3.6 | Arrow keys | Focus moves to adjacent cell |
| 7.3.7 | No keys in view mode | Pressing X/O/- does NOT change cell |

### 7.4 Cell Editing

| # | Test | Assertion |
|---|------|-----------|
| 7.4.1 | Set mark via editor | Open editor → select "Xa" → cell shows "Xa" |
| 7.4.2 | Footnote assignment | Add footnote ref → superscript appears on cell |
| 7.4.3 | Clear cell | Clear mark → cell shows empty |
| 7.4.4 | User-edited highlight | Edited cell gets visual indicator (e.g., colored border) |

### 7.5 Provenance Overlay

| # | Test | Assertion |
|---|------|-----------|
| 7.5.1 | Color coding | Cells with different sources show different bg colors |
| 7.5.2 | Hover tooltip | Hover provenance cell → tooltip shows source info |

---

## 8. Edit Mode & Semantic Drafts

**File:** `tests/e2e/edit-mode.spec.ts`

| # | Test | Steps | Assertion |
|---|------|-------|-----------|
| 8.1 | Default is view mode | Load page | Button says "View Only", Lock icon |
| 8.2 | Toggle to edit mode | Click toggle | Button says "Editing", Pencil icon, blue bg |
| 8.3 | Draft controls visible | Enter edit mode | Save/Publish/Discard buttons appear |
| 8.4 | DiffView sidebar | Make a change in edit mode | Right sidebar shows diff |
| 8.5 | Exit edit mode | Toggle back | Draft controls hidden, DiffView hidden |
| 8.6 | Edit mode persists across tabs | Toggle edit → switch tab → switch back | Still in edit mode |

---

## 9. Inline Editing Primitives

**File:** `tests/e2e/inline-editing.spec.ts`

> Precondition: Edit mode ON.

### 9.1 EditableField

| # | Test | Assertion |
|---|------|-----------|
| 9.1.1 | Click to edit | Click text → input appears with current value |
| 9.1.2 | Save on blur | Change text, click away → new value displayed |
| 9.1.3 | Cancel on Escape | Change text, press Escape → original value restored |
| 9.1.4 | Patch generated | After save → semanticStore has a patch op |

### 9.2 EditableList

| # | Test | Assertion |
|---|------|-----------|
| 9.2.1 | Add item | Click "+" → new empty item in list |
| 9.2.2 | Remove item | Click "×" on item → item removed |
| 9.2.3 | Reorder | Drag item up/down → order changes |

### 9.3 EditableCodedValue

| # | Test | Assertion |
|---|------|-----------|
| 9.3.1 | Dropdown opens | Click coded value → dropdown with CDISC terminology options |
| 9.3.2 | Select option | Pick option → value updates, patch generated |
| 9.3.3 | Search filter | Type in dropdown → options filtered |

### 9.4 View Mode Guard

| # | Test | Assertion |
|---|------|-----------|
| 9.4.1 | Fields not editable | In view mode, clicking text does NOT open input |
| 9.4.2 | No add/remove buttons | List add/remove controls hidden in view mode |

---

## 10. Draft Lifecycle (Save / Publish / Discard)

**File:** `tests/e2e/draft-lifecycle.spec.ts`

### 10.1 Save Draft

| # | Test | Steps | Assertion |
|---|------|-------|-----------|
| 10.1.1 | Save button state | No changes → Save disabled; make change → Save enabled |
| 10.1.2 | Save succeeds | Click Save → mock PUT returns 200 | Success toast, button reverts to disabled |
| 10.1.3 | Save fails | Mock PUT returns 500 | Error toast shown |

### 10.2 Publish

| # | Test | Steps | Assertion |
|---|------|-------|-----------|
| 10.2.1 | Publish button state | No draft → Publish disabled |
| 10.2.2 | Confirmation dialog | Click Publish → "Are you sure?" dialog appears |
| 10.2.3 | Publish succeeds | Confirm → mock POST returns 200 + validation result | Success toast, draft cleared, USDM reloaded |
| 10.2.4 | Publish with validation warnings | Mock returns warnings | Warning icon + details shown |
| 10.2.5 | Publish fails | Mock POST returns 409 (revision conflict) | Error message shown |

### 10.3 Discard

| # | Test | Steps | Assertion |
|---|------|-------|-----------|
| 10.3.1 | Discard confirmation | Click Discard → confirmation dialog |
| 10.3.2 | Confirm discard | Confirm → draft cleared | No pending patches, DiffView empty |
| 10.3.3 | Cancel discard | Cancel → draft preserved |

---

## 11. Undo / Redo

**File:** `tests/e2e/undo-redo.spec.ts`

| # | Test | Steps | Assertion |
|---|------|-------|-----------|
| 11.1 | Undo available after edit | Make edit | Undo button enabled |
| 11.2 | Ctrl+Z undoes | Make edit → Ctrl+Z | Previous value restored |
| 11.3 | Ctrl+Shift+Z redoes | Undo → Ctrl+Shift+Z | Edit re-applied |
| 11.4 | Undo button in controls | Click Undo button in toolbar | Same as Ctrl+Z |
| 11.5 | Empty undo stack | No edits → Ctrl+Z | Nothing happens, no error |
| 11.6 | Multi-step undo | Make 3 edits → undo 3× | All reverted in order |

---

## 12. Version History & Revert

**File:** `tests/e2e/version-history.spec.ts`

| # | Test | Steps | Assertion |
|---|------|-------|-----------|
| 12.1 | History panel opens | Click "History" button | Side panel slides in |
| 12.2 | History entries listed | Mock history API | Entries with timestamps shown |
| 12.3 | Revert to version | Click "Revert" on entry → confirm | Mock revert API called, USDM reloaded |
| 12.4 | Close panel | Click close/overlay | Panel closes |

---

## 13. Timeline Views

**File:** `tests/e2e/timeline.spec.ts`

### 13.1 View Mode Switching

| # | Test | Assertion |
|---|------|-----------|
| 13.1.1 | Default is Execution Model | "Execution Model" button active |
| 13.1.2 | Switch to SAP Data | Click → SAP panels visible |
| 13.1.3 | Switch to CDISC ARS | Click → ARS data visible |
| 13.1.4 | Switch to Graph View | Click → Cytoscape canvas visible |

### 13.2 Execution Model View

| # | Test | Assertion |
|---|------|-----------|
| 13.2.1 | Panels render | State machine, repetitions, transitions, windows panels |
| 13.2.2 | State machine table | States listed with transitions |
| 13.2.3 | Visit windows table | Window ranges displayed |
| 13.2.4 | Empty state | No execution model data → "No execution model" message |

### 13.3 Graph View (Cytoscape)

| # | Test | Assertion |
|---|------|-----------|
| 13.3.1 | Canvas renders | Cytoscape container visible with nodes |
| 13.3.2 | Nodes interactive | Click node → info panel appears |

---

## 14. Documents & Intermediate Files

**File:** `tests/e2e/documents.spec.ts`

### 14.1 Documents Tab

| # | Test | Assertion |
|---|------|-----------|
| 14.1.1 | File list loads | Document names from API displayed |
| 14.1.2 | PDF preview | Click PDF → embedded viewer or download |
| 14.1.3 | CSV preview | Click CSV → table preview |
| 14.1.4 | Empty state | No documents → appropriate message |

### 14.2 Intermediate Files Tab

| # | Test | Assertion |
|---|------|-----------|
| 14.2.1 | File list loads | JSON file names displayed |
| 14.2.2 | JSON preview | Click file → JSON viewer renders |
| 14.2.3 | Expandable tree | JSON tree nodes expand/collapse |

---

## 15. Export Functionality

**File:** `tests/e2e/export.spec.ts`

| # | Test | Steps | Assertion |
|---|------|-------|-----------|
| 15.1 | Export dropdown opens | Click Export button | CSV/JSON/PDF options visible |
| 15.2 | Export JSON | Click JSON | Download triggered, file is valid JSON |
| 15.3 | Export CSV | Switch to eligibility tab → Export CSV | Download triggered, file has headers |
| 15.4 | Export PDF | Click PDF | Download triggered |

---

## 16. Quality & Validation Tabs

**File:** `tests/e2e/quality.spec.ts`

| # | Test | Assertion |
|---|------|-----------|
| 16.1 | Quality dashboard loads | Score/metric cards visible |
| 16.2 | Metrics calculated | Activity count, encounter count match expected |
| 16.3 | Validation results load | Schema/USDM/CDISC sections visible |
| 16.4 | Validation errors shown | Mock validation with errors → error list rendered |
| 16.5 | Validation pass | Mock clean validation → success indicators |

---

## 17. Unsaved Changes Guard

**File:** `tests/e2e/unsaved-guard.spec.ts`

| # | Test | Steps | Assertion |
|---|------|-------|-----------|
| 17.1 | No guard when clean | Navigate away with no changes | No dialog |
| 17.2 | Guard on dirty state | Make edit → navigate away | `beforeunload` event fires (Playwright: check `dialog` event) |
| 17.3 | Guard on tab close | Make edit → `page.close()` | `beforeunload` fires |

> **Note:** Playwright can detect `beforeunload` dialogs via `page.on('dialog')`.

---

## 18. Toast Notifications

**File:** `tests/e2e/toasts.spec.ts`

| # | Test | Trigger | Assertion |
|---|------|---------|-----------|
| 18.1 | Success toast | Save draft | Green/check toast visible, auto-dismisses |
| 18.2 | Error toast | Mock API failure | Red/error toast visible |
| 18.3 | Warning toast | Publish with warnings | Yellow/warning toast visible |
| 18.4 | Toast dismissal | Click close on toast | Toast removed |

---

## 19. Responsive / Layout

**File:** `tests/e2e/responsive.spec.ts`

| # | Viewport | Test | Assertion |
|---|----------|------|-----------|
| 19.1 | Desktop (1280×720) | Tab groups visible | All tab group labels visible |
| 19.2 | Tablet (768×1024) | Page renders | No horizontal overflow |
| 19.3 | Mobile (375×667) | Page renders | Content stacks vertically, scrollable |
| 19.4 | DiffView sidebar | Desktop edit mode | Sidebar at `lg:w-[380px]` on right |
| 19.5 | DiffView mobile | Mobile edit mode | Sidebar stacks below content |

---

## 20. API Route Tests (Integration)

**File:** `tests/unit/api/` — use Vitest with `fetch` against running dev server, or mock `fs` directly.

### 20.1 Protocol List API

| # | Route | Method | Test |
|---|-------|--------|------|
| 20.1.1 | `/api/protocols` | GET | Returns array of protocol summaries |

### 20.2 USDM API

| # | Route | Method | Test |
|---|-------|--------|------|
| 20.2.1 | `/api/protocols/[id]/usdm` | GET | Returns USDM + revision + provenance |
| 20.2.2 | `/api/protocols/[id]/usdm` | GET (nonexistent valid-format ID) | Returns 404 "Protocol not found" |
| 20.2.3 | `/api/protocols/[id]/usdm` | GET (traversal attempt `../etc`) | Returns 400 "Invalid protocol ID" |

### 20.3 Semantic Draft API

| # | Route | Method | Test |
|---|-------|--------|------|
| 20.3.1 | `semantic/draft` | GET | Returns current draft or 404 |
| 20.3.2 | `semantic/draft` | PUT | Saves draft, returns 200 |
| 20.3.3 | `semantic/draft` | PUT (bad revision) | Returns 409 conflict |
| 20.3.4 | `semantic/draft` | DELETE | Clears draft |

### 20.4 Publish API

| # | Route | Method | Test |
|---|-------|--------|------|
| 20.4.1 | `semantic/publish` | POST | Applies patches, validates, returns result |
| 20.4.2 | `semantic/publish` | POST (no draft) | Returns 400 |
| 20.4.3 | `semantic/publish` | POST (invalid patch) | Returns 400 with validation errors |

### 20.5 History / Revert API

| # | Route | Method | Test |
|---|-------|--------|------|
| 20.5.1 | `semantic/history` | GET | Returns version entries |
| 20.5.2 | `semantic/revert` | POST | Reverts to target version |
| 20.5.3 | `semantic/revert` | POST (invalid version) | Returns 400 |

### 20.6 Documents / Intermediate API

| # | Route | Method | Test |
|---|-------|--------|------|
| 20.6.1 | `documents` | GET | Lists source documents |
| 20.6.2 | `documents/[filename]` | GET | Returns file stream |
| 20.6.3 | `documents/[filename]` | GET (traversal) | Returns 400 |
| 20.6.4 | `intermediate/[filename]` | GET | Returns JSON |
| 20.6.5 | `intermediate/[filename]` | GET (traversal) | Returns 400 |

### 20.7 Security — Path Traversal (P0 regression)

| # | Input | Expected |
|---|-------|----------|
| 20.7.1 | `protocolId = "../etc/passwd"` | 400 |
| 20.7.2 | `protocolId = "..\\windows\\system32"` | 400 |
| 20.7.3 | `filename = "../../etc/shadow"` | 400 |
| 20.7.4 | `filename = "valid.json"` | 200 (if exists) |

---

## 21. Store Unit Tests (Vitest)

**File:** `tests/unit/stores/`

### 21.1 `semanticStore`

| # | Test |
|---|------|
| 21.1.1 | `loadDraft` initializes state with protocolId, revision, patch |
| 21.1.2 | `pushPatch` adds op to draft.patch and pushes to undo stack |
| 21.1.3 | `undo` pops last patch op, pushes to redo stack |
| 21.1.4 | `redo` re-applies undone op |
| 21.1.5 | `clearDraft` resets all state |
| 21.1.6 | `isDirty` tracks unsaved changes correctly |
| 21.1.7 | `selectHasSemanticDraft` returns true only when patch.length > 0 |

### 21.2 `soaEditStore`

| # | Test |
|---|------|
| 21.2.1 | `commitCellEdit` stores mark in committedCellEdits map |
| 21.2.2 | `setActivityName` stores name in pendingActivityNameEdits |
| 21.2.3 | `setEncounterName` stores name in pendingEncounterNameEdits |
| 21.2.4 | `loadUserEditedCells` parses extension attributes correctly |
| 21.2.5 | `isUserEdited` returns true for committed + USDM user-edited cells |
| 21.2.6 | `reset` clears all state to initial |

### 21.3 `overlayStore`

| # | Test |
|---|------|
| 21.3.1 | `loadOverlays` sets published and draft payloads |
| 21.3.2 | `promoteDraftToPublished` moves draft → published |
| 21.3.3 | `resetToPublished` clears draft changes |
| 21.3.4 | `isDirty` tracks overlay changes |
| 21.3.5 | `markClean` resets dirty flag |

### 21.4 `editModeStore`

| # | Test |
|---|------|
| 21.4.1 | Default `isEditMode` is false |
| 21.4.2 | `toggleEditMode` flips the flag |

### 21.5 `toastStore`

| # | Test |
|---|------|
| 21.5.1 | `toast()` adds item to store |
| 21.5.2 | `dismiss(id)` removes item |
| 21.5.3 | Auto-dismiss after timeout |

---

## 22. Adapter / Helper Unit Tests

**File:** `tests/unit/lib/`

### 22.1 `toSoATableModel`

| # | Test |
|---|------|
| 22.1.1 | Returns empty model for null studyDesign |
| 22.1.2 | Maps activities to rows with correct order |
| 22.1.3 | Maps encounters to columns grouped by epoch |
| 22.1.4 | Builds cells from ScheduledActivityInstances |
| 22.1.5 | Separates procedure enrichment activities into `procedureActivities` |
| 22.1.6 | Reads cell marks from extensionAttributes via `getExtString` |
| 22.1.7 | Reads user-edited flag from extensionAttributes via `getExtBoolean` |
| 22.1.8 | Handles missing extensionAttributes gracefully |

### 22.2 `lib/extensions.ts`

| # | Test |
|---|------|
| 22.2.1 | `findExt` finds by full URL |
| 22.2.2 | `findExt` finds by URL suffix |
| 22.2.3 | `findExt` returns undefined for missing |
| 22.2.4 | `getExtString` returns valueString |
| 22.2.5 | `getExtString` falls back to valueBoolean as string |
| 22.2.6 | `getExtString` falls back to valueInteger as string |
| 22.2.7 | `getExtBoolean` returns boolean from valueBoolean |
| 22.2.8 | `getExtBoolean` parses "true"/"false" from valueString |
| 22.2.9 | `makeStringExt` creates valid ExtensionAttribute |
| 22.2.10 | `makeBooleanExt` writes both valueBoolean and valueString (legacy compat) |
| 22.2.11 | `hasExt` returns true/false correctly |
| 22.2.12 | `findAllExts` returns all matching extensions |
| 22.2.13 | Handles null/undefined/empty array inputs gracefully |

### 22.3 `lib/sanitize.ts`

| # | Test |
|---|------|
| 22.3.1 | `validateProtocolId` accepts valid alphanumeric + dashes |
| 22.3.2 | `validateProtocolId` rejects `../`, `..\\`, empty string |
| 22.3.3 | `validateFilename` accepts `protocol_usdm.json` |
| 22.3.4 | `validateFilename` rejects `../../etc/passwd` |
| 22.3.5 | `ensureWithinRoot` passes for child paths |
| 22.3.6 | `ensureWithinRoot` throws for escaped paths |

### 22.4 `lib/semantic/patcher.ts`

| # | Test |
|---|------|
| 22.4.1 | `validatePatchOps` accepts valid add/replace/remove ops |
| 22.4.2 | `validatePatchOps` rejects missing path |
| 22.4.3 | `validatePatchOps` rejects path not starting with `/` |
| 22.4.4 | `validatePatchOps` rejects immutable path targets |
| 22.4.5 | `validatePatchOps` rejects add/replace without value |
| 22.4.6 | `validatePatchOps` rejects move/copy without from |

### 22.5 `lib/soa/processor.ts`

| # | Test |
|---|------|
| 22.5.1 | `SoAProcessor.editCell` generates correct JSON Patch ops |
| 22.5.2 | `SoAProcessor.addActivity` creates activity with extension attributes |
| 22.5.3 | `SoAProcessor.addEncounter` creates encounter with extension attributes |
| 22.5.4 | `isUserEditedCell` reads from extensionAttributes correctly |
| 22.5.5 | `getCellMark` returns mark from extensionAttributes |
| 22.5.6 | `getCellMark` defaults to 'X' when no mark extension exists |
| 22.5.7 | Extension attributes use `EXT_URLS` constants |

---

## 23. Accessibility

**File:** `tests/e2e/a11y.spec.ts`

| # | Test | Tool |
|---|------|------|
| 23.1 | Home page — no violations | `@axe-core/playwright` |
| 23.2 | Protocol list — no violations | axe scan |
| 23.3 | Protocol detail (overview) — no violations | axe scan |
| 23.4 | SoA table — ARIA grid roles | Check `role="grid"` / `role="gridcell"` |
| 23.5 | Tab navigation — keyboard accessible | Tab through tab groups with keyboard |
| 23.6 | Edit mode button — ARIA label | `aria-pressed` or equivalent state |
| 23.7 | Modal dialogs — focus trap | Discard/publish confirmation dialogs trap focus |
| 23.8 | Toast — ARIA live region | `role="alert"` or `aria-live="polite"` |

---

## 24. Performance

**File:** `tests/e2e/performance.spec.ts`

| # | Test | Threshold |
|---|------|-----------|
| 24.1 | Protocol list TTI | < 3s (with mocked API) |
| 24.2 | Protocol detail load | < 5s (with mocked API) |
| 24.3 | SoA grid render (50 activities × 12 visits) | < 2s to first paint |
| 24.4 | Tab switch latency | < 500ms between tabs |
| 24.5 | Edit → patch generation | < 100ms for single cell edit |

> Use `page.evaluate(() => performance.now())` or Playwright's built-in `page.metrics()`.

---

## 25. Security (UI Surface)

**File:** `tests/e2e/security.spec.ts`

| # | Test | Assertion |
|---|------|-----------|
| 25.1 | XSS in protocol name | Protocol name with `<script>` tag → rendered as text, not executed |
| 25.2 | XSS in activity name | Activity with `<img onerror>` → rendered as text |
| 25.3 | Path traversal in URL | `/protocols/..%2F..%2Fetc%2Fpasswd` → 400 or 404, no file content |
| 25.4 | Overlong input | Activity name > 10000 chars → no crash |
| 25.5 | JSON injection in edit | Patch value with deeply nested object → handled gracefully |

---

## Appendix A: Priority Matrix

| Priority | Category | Est. Tests | Est. Effort |
|----------|----------|-----------|-------------|
| **P0** | Smoke + Navigation | ~10 | 2h |
| **P0** | SoA Table rendering + editing | ~15 | 4h |
| **P0** | Draft lifecycle (save/publish/discard) | ~12 | 3h |
| **P0** | API security (path traversal regression) | ~8 | 2h |
| **P1** | Store unit tests | ~25 | 4h |
| **P1** | Adapter/helper unit tests | ~30 | 4h |
| **P1** | Tab rendering (all 21 tabs) | ~21 | 3h |
| **P1** | Inline editing + undo/redo | ~15 | 3h |
| **P2** | Export / Documents / Timeline | ~15 | 3h |
| **P2** | Accessibility | ~8 | 2h |
| **P2** | Responsive / Performance | ~10 | 2h |
| **P3** | Security (XSS, injection) | ~5 | 1h |
| | **Total** | **~174** | **~33h** |

## Appendix B: Suggested Implementation Order

1. **Infrastructure setup** — install deps, config files, CI workflow
2. **Unit tests for `lib/extensions.ts` and `lib/sanitize.ts`** — fastest to write, highest confidence
3. **Store unit tests** — semanticStore, soaEditStore (core state logic)
4. **E2E smoke tests** — verify pages load
5. **SoA table E2E** — the most complex interactive surface
6. **Draft lifecycle E2E** — save/publish/discard flow
7. **Tab rendering E2E** — systematically cover all 21 tabs
8. **API integration tests** — especially security regression
9. **Everything else** — accessibility, performance, responsive, export
