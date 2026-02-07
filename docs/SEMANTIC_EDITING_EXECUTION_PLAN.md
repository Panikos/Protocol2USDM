# Semantic Editing — Execution Plan

> **Based on:** Enterprise Architect Review (2026-02-07)  
> **Spec:** `docs/SEMANTIC_EDITING_SPEC.md`

---

## Phase 0: Foundation (Immediate — No Dependencies)

**Goal:** Fix known issues, establish file structure conventions.

| Task | Req ID | Owner | Effort | Status |
|------|--------|-------|--------|--------|
| Fix `main_v2.py` → `main_v3.py` in protocols page | UI-4 | — | 5 min | ✅ Done |
| Fix footer version `v6.5.0` → `v7.2.0` | UI-5 | — | 5 min | ✅ Done |
| Create `semantic/` folder structure utility | ST-1–4 | Backend | 1 hr | Pending |
| Add `jsonpatch` to Python requirements | SE-2 | Backend | 5 min | Pending |
| Add `fast-json-patch` to web-ui package.json | SE-2 | Frontend | 5 min | Pending |

---

## Phase 1: Semantic Draft API (Backend)

**Goal:** Implement draft storage and retrieval.

**Dependencies:** Phase 0

| Task | Req ID | File(s) | Effort |
|------|--------|---------|--------|
| Create `/api/protocols/[id]/semantic/draft` GET route | API-1 | `web-ui/app/api/protocols/[id]/semantic/draft/route.ts` | 1 hr |
| Create `/api/protocols/[id]/semantic/draft` PUT route | API-2 | Same file | 2 hr |
| Create `/api/protocols/[id]/semantic/draft` DELETE route | API-3 | Same file | 30 min |
| Add JSON Patch validation (RFC 6902 syntax) | SE-2 | `web-ui/lib/semantic/validation.ts` | 1 hr |
| Add USDM revision hash computation | SE-2 | `web-ui/lib/semantic/revision.ts` | 1 hr |
| Add immutable field protection | SE-2 | `web-ui/lib/semantic/validation.ts` | 1 hr |
| Create draft versioning logic (archive on save) | SE-3 | Shared util | 1 hr |

**Subtotal:** ~8 hrs

---

## Phase 2: Semantic Publish API (Backend)

**Goal:** Implement publish flow with validation.

**Dependencies:** Phase 1

| Task | Req ID | File(s) | Effort |
|------|--------|---------|--------|
| Create `/api/protocols/[id]/semantic/publish` POST route | API-4 | `web-ui/app/api/protocols/[id]/semantic/publish/route.ts` | 3 hr |
| Implement JSON Patch application to USDM | SE-1 | `web-ui/lib/semantic/patcher.ts` | 2 hr |
| Implement USDM snapshot before publish | SE-4 | Publish route | 1 hr |
| Integrate Python validation pipeline call | SE-6 | Publish route or Python wrapper | 3 hr |
| Create `/api/protocols/[id]/semantic/history` GET route | API-5 | `web-ui/app/api/protocols/[id]/semantic/history/route.ts` | 1 hr |
| Handle validation result parsing and response | SE-6 | Publish route | 1 hr |

**Subtotal:** ~11 hrs

---

## Phase 3: Documents & Intermediate APIs (Backend)

**Goal:** Expose source docs and intermediate files.

**Dependencies:** None (can run parallel to Phase 1-2)

| Task | Req ID | File(s) | Effort |
|------|--------|---------|--------|
| Create `/api/protocols/[id]/documents` GET route | API-6 | `web-ui/app/api/protocols/[id]/documents/route.ts` | 2 hr |
| Create `/api/protocols/[id]/documents/[filename]` GET route | API-7 | `web-ui/app/api/protocols/[id]/documents/[filename]/route.ts` | 2 hr |
| Add CSV/XLSX preview generation (first N rows) | UI-2 | `web-ui/lib/preview/tabular.ts` | 2 hr |
| Create `/api/protocols/[id]/intermediate` GET route | API-8 | `web-ui/app/api/protocols/[id]/intermediate/route.ts` | 1 hr |
| Create `/api/protocols/[id]/intermediate/[filename]` GET route | API-9 | `web-ui/app/api/protocols/[id]/intermediate/[filename]/route.ts` | 1 hr |

**Subtotal:** ~8 hrs

---

## Phase 4: UI — Documents & Intermediate Tabs (Frontend)

**Goal:** Replace SoA Images tab with Documents tab, add Intermediate tab.

**Dependencies:** Phase 3

| Task | Req ID | File(s) | Effort |
|------|--------|---------|--------|
| Create `DocumentsTab` component | UI-2 | `web-ui/components/documents/DocumentsTab.tsx` | 3 hr |
| Create `DocumentPreview` component (PDF iframe, CSV table) | UI-2 | `web-ui/components/documents/DocumentPreview.tsx` | 3 hr |
| Create `IntermediateFilesTab` component | UI-3 | `web-ui/components/intermediate/IntermediateFilesTab.tsx` | 2 hr |
| Create `JsonPreview` component (collapsible tree) | UI-3 | `web-ui/components/intermediate/JsonPreview.tsx` | 2 hr |
| Update `dataTabs` in protocol detail page | UI-1,2,3 | `web-ui/app/protocols/[id]/page.tsx` | 1 hr |
| Remove `SoAImagesTab` import and tab entry | UI-1 | Same file | 30 min |
| Remove `/api/protocols/[id]/images` routes | UI-1 | Delete files | 15 min |
| Remove `SoAImagesTab.tsx`, `SoAImagesViewer.tsx` | UI-1 | Delete files | 15 min |

**Subtotal:** ~12 hrs

---

## Phase 5: UI — Semantic Draft Controls (Frontend)

**Goal:** Extend existing draft/publish UX for semantic edits.

**Dependencies:** Phase 2

| Task | Req ID | File(s) | Effort |
|------|--------|---------|--------|
| Create `semanticStore.ts` (Zustand store for semantic draft) | SE-1 | `web-ui/stores/semanticStore.ts` | 2 hr |
| Update `DraftPublishControls` to handle semantic draft | UI-6,7 | `web-ui/components/overlay/DraftPublishControls.tsx` | 2 hr |
| Add "Semantic Draft" badge when draft exists | UI-6 | Same component | 1 hr |
| Add discard draft button | UI-7 | Same component | 30 min |
| Add validation results toast/modal on publish | SE-6 | `web-ui/components/semantic/PublishResultsModal.tsx` | 2 hr |
| Wire up protocol detail page to load semantic draft | — | `web-ui/app/protocols/[id]/page.tsx` | 1 hr |

**Subtotal:** ~8.5 hrs

---

## Phase 6: UI — Inline Editing (Frontend)

**Goal:** Enable editing of USDM primitives with JSON Patch generation.

**Dependencies:** Phase 5

| Task | Req ID | File(s) | Effort |
|------|--------|---------|--------|
| Create `useSemanticEdit` hook (generates JSON Patch ops) | SE-2 | `web-ui/hooks/useSemanticEdit.ts` | 3 hr |
| Add inline edit to `StudyDesignView` (arm names) | — | `web-ui/components/protocol/StudyDesignView.tsx` | 2 hr |
| Add inline edit to `EligibilityCriteriaView` | — | `web-ui/components/protocol/EligibilityCriteriaView.tsx` | 2 hr |
| Add inline edit to `ObjectivesEndpointsView` | — | `web-ui/components/protocol/ObjectivesEndpointsView.tsx` | 2 hr |
| Add inline edit to other views (Epochs, Encounters, Activities) | — | Multiple components | 4 hr |

**Subtotal:** ~13 hrs

---

## Phase 7: Data Sourcing Alignment (Backend + Frontend)

**Goal:** Ensure execution model sourcing follows priority rules.

**Dependencies:** Phase 4

| Task | Req ID | File(s) | Effort |
|------|--------|---------|--------|
| Update `ExecutionModelView` to check USDM extensions first | DS-3 | `web-ui/components/timeline/ExecutionModelView.tsx` | 2 hr |
| Add fallback to `11_execution_model.json` | DS-3 | Same component | 1 hr |
| Add "Source" indicator badge | DS-4 | Same component | 30 min |
| Update `/api/protocols/[id]/usdm` to include extension detection | DS-3 | `web-ui/app/api/protocols/[id]/usdm/route.ts` | 1 hr |

**Subtotal:** ~4.5 hrs

---

## Summary

| Phase | Description | Effort | Dependencies |
|-------|-------------|--------|--------------|
| 0 | Foundation | 2 hrs | — |
| 1 | Semantic Draft API | 8 hrs | 0 |
| 2 | Semantic Publish API | 11 hrs | 1 |
| 3 | Documents & Intermediate APIs | 8 hrs | — (parallel) |
| 4 | UI — Documents & Intermediate Tabs | 12 hrs | 3 |
| 5 | UI — Semantic Draft Controls | 8.5 hrs | 2 |
| 6 | UI — Inline Editing | 13 hrs | 5 |
| 7 | Data Sourcing Alignment | 4.5 hrs | 4 |

**Total estimated effort:** ~67 hrs

---

## Recommended Execution Order

```
Week 1:
├── Phase 0 (Foundation)                    [Day 1]
├── Phase 1 (Semantic Draft API)            [Day 1-2]
├── Phase 3 (Documents & Intermediate APIs) [Day 2-3, parallel]
└── Phase 2 (Semantic Publish API)          [Day 3-4]

Week 2:
├── Phase 4 (Documents & Intermediate Tabs) [Day 1-2]
├── Phase 5 (Semantic Draft Controls)       [Day 2-3]
├── Phase 7 (Data Sourcing Alignment)       [Day 3, parallel]
└── Phase 6 (Inline Editing)                [Day 3-5]
```

---

## What I Can Execute Now

The following tasks require no additional input and can be implemented immediately:

### Backend (Python/Next.js API routes)
1. **Phase 0:** Add `jsonpatch` to requirements.txt
2. **Phase 1:** Create semantic draft API routes (GET/PUT/DELETE)
3. **Phase 3:** Create documents and intermediate file API routes

### Frontend (React/TypeScript)
1. **Phase 0:** Add `fast-json-patch` to package.json
2. **Phase 4:** Create DocumentsTab and IntermediateFilesTab components
3. **Phase 4:** Remove SoA Images tab and related files

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Python validation subprocess from Next.js may be slow | Consider validation API endpoint in Python (FastAPI) |
| Large USDM files may hit memory limits during patch | Stream JSON Patch application; test with large protocols |
| Concurrent edits may conflict | `usdmRevision` hash acts as optimistic lock; 409 on mismatch |
| Existing overlay system confusion with new semantic system | Clear UI separation; different badges/colors |
