# Protocol2USDM — Semantic Editing Implementation Spec

> **Status:** ✅ Implemented  
> **Date:** 2026-02-07 (updated)  
> **Format:** JSON Patch (RFC 6902)
>
> Implementation completed in web-ui v7.2.0. **Unified draft architecture** added in v7.3.0 — all edits (inline fields, SoA cells) now flow through a single semantic draft system.

---

## 1. Design Decisions (Confirmed)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Edit storage | Layered diffs until publish | Non-destructive; rollback-friendly |
| Provenance | Separate file (`protocol_usdm_provenance.json`) | Size/performance; not embedded in USDM |
| Document previews | In-browser preview + download link | Structured UX for PDF/CSV/XLSX |
| Diff format | JSON Patch (RFC 6902) | Portable, standard, tooling-rich |
| Draft versioning | Single `draft_latest.json` with timestamped backups | Simple; no append-only complexity |
| Publish validation | Auto-trigger schema + USDM + CORE conformance | Block on errors, allow warnings |

---

## 2. Storage Layout

```
semantic/
  <protocolId>/
    drafts/
      draft_latest.json            # current working draft
      draft_<timestamp>.json       # versioned backup (auto on each save)
    published/
      published_latest.json        # most recent publish snapshot
      published_<timestamp>.json   # historical publish snapshots
    history/
      protocol_usdm_<timestamp>.json   # pre-publish USDM snapshots
```

### Behavior

- **Save draft:** Write `draft_latest.json`; archive previous as `draft_<timestamp>.json`.
- **Publish:** Apply patch → write new `protocol_usdm.json` → snapshot old USDM into `history/` → write `published_<timestamp>.json` + update `published_latest.json` → clear/archive draft.
- **Result:** `protocol_usdm.json` always equals the latest published semantic state.

---

## 3. Draft Schema

```jsonc
{
  "version": 1,
  "protocolId": "NCT04573309_Wilsons_Protocol_20260207_110101",
  "usdmRevision": "sha256:<hash-of-protocol_usdm.json>",
  "status": "draft",                          // "draft" | "published"
  "createdAt": "2026-02-07T12:00:00Z",
  "updatedAt": "2026-02-07T12:34:56Z",
  "updatedBy": "user@company.com",
  "patch": [
    // RFC 6902 JSON Patch operations
    {
      "op": "replace",
      "path": "/study/versions/0/studyDesigns/0/arms/1/name",
      "value": "Treatment Arm B"
    },
    {
      "op": "add",
      "path": "/study/versions/0/studyDesigns/0/arms/-",
      "value": { "id": "arm-3", "name": "Arm C", "description": "Open-label extension" }
    },
    {
      "op": "remove",
      "path": "/study/versions/0/studyDesigns/0/arms/2"
    },
    {
      "op": "test",
      "path": "/study/versions/0/studyDesigns/0/arms/1/name",
      "value": "Treatment Arm A"
    }
  ]
}
```

### Supported Operations

| Op | Description | Notes |
|----|-------------|-------|
| `add` | Insert new value at path | Array append via `/-` |
| `remove` | Delete value at path | |
| `replace` | Overwrite value at path | Path must exist |
| `move` | Move value between paths | |
| `copy` | Copy value between paths | |
| `test` | Assert value at path | Used for optimistic concurrency |

### Immutable Fields (reject patches targeting these)

- `study.id`
- `study.versions[*].id`
- `usdmVersion`
- `generatedAt`
- `_provenance` (any provenance metadata)

---

## 4. API Endpoints

### 4.1 Draft API

#### `GET /api/protocols/[id]/semantic/draft`

Returns the current draft or `null`.

**Response (200):**
```jsonc
// draft_latest.json contents, or null if no draft exists
```

#### `PUT /api/protocols/[id]/semantic/draft`

Save or update the current draft.

**Request body:**
```jsonc
{
  "protocolId": "NCT04573309...",
  "usdmRevision": "sha256:<hash>",
  "updatedBy": "user@company.com",
  "patch": [
    { "op": "replace", "path": "...", "value": "..." }
  ]
}
```

**Behavior:**
1. Validate JSON Patch syntax (RFC 6902).
2. Validate `usdmRevision` matches current `protocol_usdm.json` hash (optimistic concurrency).
3. Validate no patches target immutable fields.
4. Archive existing `draft_latest.json` as `draft_<timestamp>.json`.
5. Write new `draft_latest.json`.

**Response (200):**
```json
{ "success": true, "archivedPrevious": "draft_20260207T123456Z.json" }
```

**Error (409 — revision mismatch):**
```json
{ "error": "usdm_revision_mismatch", "expected": "sha256:abc...", "actual": "sha256:def..." }
```

#### `DELETE /api/protocols/[id]/semantic/draft`

Discard the current draft.

**Response (200):**
```json
{ "success": true }
```

---

### 4.2 Publish API

#### `POST /api/protocols/[id]/semantic/publish`

Apply draft patch to `protocol_usdm.json` and trigger validation.

**Behavior:**
1. Load `protocol_usdm.json`.
2. Load `draft_latest.json`.
3. Verify `usdmRevision` matches.
4. Apply JSON Patch operations to USDM.
5. Snapshot old `protocol_usdm.json` → `semantic/<id>/history/protocol_usdm_<timestamp>.json`.
6. Write updated `protocol_usdm.json`.
7. Write `published_<timestamp>.json` and update `published_latest.json`.
8. Archive `draft_latest.json` → `draft_<timestamp>.json`, clear draft.
9. **Trigger auto-validation pipeline:**
   - Schema validation → `schema_validation.json`
   - USDM semantic validation → `usdm_validation.json`
   - CDISC CORE conformance → `conformance_report.json`
10. Return validation results.

**Response (200):**
```jsonc
{
  "success": true,
  "publishedAt": "2026-02-07T12:34:56Z",
  "publishedFile": "published_20260207T123456Z.json",
  "validation": {
    "schema": { "valid": true, "errors": 0, "warnings": 0 },
    "usdm":   { "valid": true, "errors": 0, "warnings": 0 },
    "core":   { "success": true, "issues": 0, "warnings": 0 }
  }
}
```

**Error (422 — patch application failed):**
```json
{ "error": "patch_failed", "details": "Path /study/versions/0/arms/5 does not exist" }
```

**Error (422 — validation failed, publish blocked):**
```jsonc
{
  "error": "validation_failed",
  "published": true,  // USDM was updated but has errors
  "validation": {
    "schema": { "valid": false, "errors": 2, "warnings": 0, "details": [...] },
    "usdm":   { "valid": true, "errors": 0, "warnings": 0 },
    "core":   { "success": true, "issues": 0, "warnings": 1 }
  }
}
```

> **Policy:** Publish is **blocked** if schema or USDM validation returns errors. CORE conformance warnings do **not** block publish.

---

### 4.3 History API

#### `GET /api/protocols/[id]/semantic/history`

List all published versions and USDM snapshots.

**Response (200):**
```jsonc
{
  "published": [
    { "file": "published_20260207T123456Z.json", "timestamp": "2026-02-07T12:34:56Z", "updatedBy": "user@company.com" }
  ],
  "usdmSnapshots": [
    { "file": "protocol_usdm_20260207T123400Z.json", "timestamp": "2026-02-07T12:34:00Z" }
  ]
}
```

---

### 4.4 Documents API

#### `GET /api/protocols/[id]/documents`

List source documents (protocol PDF, SAP, sites CSV/XLSX).

**Response (200):**
```jsonc
{
  "documents": [
    {
      "filename": "NCT04573309_Wilsons_Protocol.pdf",
      "type": "protocol",
      "mimeType": "application/pdf",
      "size": 2456789,
      "updatedAt": "2026-02-07T10:00:00Z"
    },
    {
      "filename": "NCT04573309_Wilsons_SAP.pdf",
      "type": "sap",
      "mimeType": "application/pdf",
      "size": 1234567,
      "updatedAt": "2026-02-07T10:00:00Z"
    },
    {
      "filename": "NCT04573309_Wilsons_sites.csv",
      "type": "sites",
      "mimeType": "text/csv",
      "size": 4567,
      "updatedAt": "2026-02-07T10:00:00Z"
    }
  ]
}
```

#### `GET /api/protocols/[id]/documents/[filename]`

Stream file for download or preview.

**Query params:**
- `preview=true` — return preview-friendly response (first N rows for CSV, first page for PDF)

---

### 4.5 Intermediate Files API

#### `GET /api/protocols/[id]/intermediate`

List intermediate JSON artifacts.

**Response (200):**
```jsonc
{
  "files": [
    { "filename": "2_study_metadata.json", "size": 1234, "phase": "metadata" },
    { "filename": "6_validation_result.json", "size": 5678, "phase": "soa" },
    { "filename": "11_execution_model.json", "size": 45678, "phase": "execution" },
    { "filename": "schema_validation.json", "size": 2345, "phase": "validation" },
    { "filename": "usdm_validation.json", "size": 1234, "phase": "validation" },
    { "filename": "conformance_report.json", "size": 3456, "phase": "conformance" },
    { "filename": "token_usage.json", "size": 890, "phase": "meta" },
    { "filename": "run_manifest.json", "size": 567, "phase": "meta" }
  ]
}
```

#### `GET /api/protocols/[id]/intermediate/[filename]`

Return JSON file contents for preview, with download header option.

---

## 5. Validation Pipeline on Publish

Triggered automatically after applying the JSON Patch to `protocol_usdm.json`:

| Step | Tool | Output | Blocks Publish? |
|------|------|--------|-----------------|
| 1 | `validation/usdm_validator.py` — schema check | `schema_validation.json` | **Yes** on errors |
| 2 | `validation/usdm_validator.py` — semantic check | `usdm_validation.json` | **Yes** on errors |
| 3 | `validation/cdisc_conformance.py` — CORE engine | `conformance_report.json` | No (warnings only) |

### Integration

The publish API endpoint should invoke the Python validation pipeline via subprocess or HTTP call:

```bash
python -m validation.usdm_validator <protocol_usdm.json> --output-dir <output_dir>
python -m validation.cdisc_conformance <protocol_usdm.json> --output-dir <output_dir>
```

Or expose a validation-only endpoint:

```
POST /api/protocols/[id]/validate
```

---

## 6. UI/UX Changes

### 6.1 Semantic Draft Controls

**Location:** Protocol detail header (existing `DraftPublishControls` component).

**Current state:** The overlay system already has draft/publish for layout (diagram nodes, table order). Semantic editing extends this to USDM data.

**New behavior:**
- **"Draft" badge** shown when `semantic/drafts/draft_latest.json` exists.
- **Save Draft** button — `PUT /api/protocols/[id]/semantic/draft`
- **Publish** button — `POST /api/protocols/[id]/semantic/publish`
- **Discard Draft** button — `DELETE /api/protocols/[id]/semantic/draft`
- After publish, show validation results inline (toast or modal).

**Editable primitives:**
- Arm names and descriptions
- Epoch names
- Encounter names and descriptions
- Activity names
- Eligibility criteria text
- Objective/endpoint text
- **SoA cell marks** (X, O, −, Xa, Xb, Xc) and footnotes
- Activity/encounter names from SoA grid

**Not editable:**
- Extension data (`extensionAttributes`) — read-only
- Provenance data — read-only
- System IDs (`study.id`, `study.versions[*].id`)

### 6.2 Documents Tab (replaces Images tab)

**Remove:**
- `SoAImagesTab` component
- `SoAImagesViewer` component
- `/api/protocols/[id]/images` route
- `/api/protocols/[id]/images/[filename]` route

**Add:**
- **Documents** tab in Data tab group (icon: `FileText`)
- Left panel: document list (protocol PDF, SAP, sites)
- Right panel: preview area
  - PDF → `<iframe>` embed or open-in-new-tab link
  - CSV → in-browser table preview (first 100 rows)
  - XLSX → first sheet table preview
- Download button per document

### 6.3 Intermediate Files Tab

**Add:**
- **Intermediate** tab in Data tab group (icon: `FolderOpen`)
- List of JSON artifacts with:
  - Filename, size, phase label
  - JSON tree preview (collapsible)
  - Download button per file
- No PDF rendering here

### 6.4 Quick Fixes (Implemented)

| Fix | File | Change |
|-----|------|--------|
| Empty-state command | `web-ui/app/protocols/page.tsx` | `main_v2.py` → `main_v3.py` |
| Footer version | `web-ui/app/page.tsx` | `v6.5.0` → `v7.2.0` |

---

## 7. Data Sourcing Policy

### Primary source
- `protocol_usdm.json` — canonical USDM data for all UI views.

### Separate artifacts (allowed)
| File | Reason |
|------|--------|
| `protocol_usdm_provenance.json` | Size/performance; cell-level provenance |
| `9_final_soa_provenance.json` | SoA-specific provenance |
| `11_execution_model.json` | Fallback if extension data missing in USDM |
| `schema_validation.json` | Validation artifact |
| `usdm_validation.json` | Validation artifact |
| `conformance_report.json` | Conformance artifact |

### Execution model sourcing priority
1. `protocol_usdm.json` → `extensionAttributes` (preferred)
2. `11_execution_model.json` (fallback)
3. UI should indicate which source is active

---

## 8. Required Libraries

### Backend (Python — publish endpoint)
- `jsonpatch` — RFC 6902 implementation (`pip install jsonpatch`)
- Existing: `validation/usdm_validator.py`, `validation/cdisc_conformance.py`

### Frontend (Next.js)
- `fast-json-patch` — RFC 6902 for TypeScript (`npm install fast-json-patch`)
- Existing: `zod` for schema validation, `zustand` for state

---

## 9. Migration from Current Overlay System

The current overlay system (`lib/overlay/schema.ts`, `overlayStore.ts`) handles **layout** (diagram node positions, table row/column order). Semantic editing is a **separate concern**.

**Recommendation:** Keep both systems:
- **Overlay** = layout/visual customization (existing)
- **Semantic** = USDM data edits (new, this spec)

They share the draft/publish UX pattern but operate on different data. The UI should show both draft states clearly.

---

## 10. Open Questions for Team

| # | Question | Recommendation |
|---|----------|----------------|
| 1 | Maximum retained history size? | Cap at 50 versions, configurable via env var |
| 2 | Should `updatedBy` require authentication? | Yes — audit trail essential for clinical context |
| 3 | Should publish with CORE warnings show a confirmation dialog? | Yes — "Publish with warnings?" modal |
| 4 | Should the Documents tab support drag-and-drop upload of new source docs? | Defer to Phase 2 |
| 5 | Should intermediate files be deletable from the UI? | No — read-only QA view |

---

## 11. Implementation Details

### 11.1 Files Created

#### Backend API Routes (`web-ui/app/api/protocols/[id]/`)

| File | Methods | Description |
|------|---------|-------------|
| `semantic/draft/route.ts` | GET, PUT, DELETE | Manage semantic drafts with revision validation |
| `semantic/publish/route.ts` | POST | Apply patches to USDM, trigger validation |
| `semantic/history/route.ts` | GET | List published versions and USDM snapshots |
| `documents/route.ts` | GET | List source documents (PDF, SAP, sites) |
| `documents/[filename]/route.ts` | GET | Download/preview source documents |
| `intermediate/route.ts` | GET | List extraction artifacts |
| `intermediate/[filename]/route.ts` | GET | Preview/download intermediate JSON |

#### Libraries (`web-ui/lib/semantic/`)

| File | Description |
|------|-------------|
| `schema.ts` | Zod schemas for JSON Patch ops, SemanticDraft, validation results, immutable paths |
| `storage.ts` | File system utilities for semantic folder structure, archiving, revision hashing |
| `patcher.ts` | JSON Patch application using `fast-json-patch` |
| `index.ts` | Module exports |

#### UI Components

| File | Description |
|------|-------------|
| `components/documents/DocumentsTab.tsx` | Source documents viewer with preview panel |
| `components/documents/IntermediateFilesTab.tsx` | Intermediate JSON artifacts browser with tree view |
| `components/semantic/SemanticDraftControls.tsx` | Draft save/publish/discard controls with validation modal |
| `components/semantic/EditableField.tsx` | Inline editing components for protocol views |

#### State Management

| File | Description |
|------|-------------|
| `stores/semanticStore.ts` | Zustand store for semantic draft state management |
| `stores/soaEditStore.ts` | SoA-specific edit tracking (visual indicators) |
| `hooks/usePatchedUsdm.ts` | Hook to get USDM with draft patches applied |

### 11.2 Protocol Page Updates

The protocol detail page (`app/protocols/[id]/page.tsx`) was updated:

- **Removed:** "Images" tab and `SoAImagesTab` component import
- **Added:** "Documents" tab using `DocumentsTab` component
- **Added:** "Intermediate" tab using `IntermediateFilesTab` component
- **Updated:** `TabId` type to include new tab identifiers

### 11.3 Dependencies

| Package | Location | Purpose |
|---------|----------|---------|
| `jsonpatch>=1.33` | `requirements.txt` | Python RFC 6902 implementation |
| `fast-json-patch@^3.1.1` | `web-ui/package.json` | TypeScript RFC 6902 implementation |

### 11.4 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PROTOCOL_OUTPUT_DIR` | `../output` | Base directory for protocol outputs |
| `SEMANTIC_DIR` | `../semantic` | Base directory for semantic drafts/history |
| `PROTOCOL_INPUT_DIR` | `../input` | Base directory for source documents |

### 11.5 Unified Draft Architecture (v7.3+)

All edits now flow through a single semantic draft system. This ensures that changes from any source (inline fields, SoA grid) are bundled together and can be previewed across all views before publishing.

#### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Edit Sources                                  │
│                                                                  │
│  EditableField         SoACellEditor        Future editors...   │
│  (inline text)         (cell marks)                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Semantic Store                                │
│                                                                  │
│  draft.patch: JsonPatchOp[]    ◄── All edits add patches here   │
│  isDirty: boolean                                                │
│  clearDraft() → also clears soaEditStore                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 usePatchedUsdm() Hook                            │
│                                                                  │
│  Applies draft patches to raw USDM → patched USDM               │
│  All views consume patched USDM for consistent preview          │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
   SoAView              TimelineView         ExecutionModelView
   (SoA Grid)           (Graph View)         (Visit Schedule)
```

#### Key Files

| File | Purpose |
|------|--------|
| `hooks/usePatchedUsdm.ts` | Returns USDM with draft patches applied |
| `stores/protocolStore.ts` | `getPatchedUsdm()` utility function |
| `stores/semanticStore.ts` | Central draft state, clears soaEditStore on discard/publish |
| `stores/soaEditStore.ts` | Visual tracking for SoA edits (amber indicators) |
| `lib/soa/processor.ts` | Generates JSON patches from SoA edits |

#### SoA Edit Flow

1. User double-clicks SoA cell → `SoACellEditor` opens
2. User selects mark (X, O, Xa, Xb, Xc, −, clear) → clicks Save
3. `soaEditStore.setCellMark()` generates JSON patch via `SoAProcessor`
4. Patch added to `semanticStore.addPatchOp()`
5. `committedCellEdits` updated for visual indicator (amber background)
6. All views using `usePatchedUsdm()` immediately reflect the change
7. User can Save Draft / Publish / Discard via `SemanticDraftControls`
8. On Discard/Publish → `semanticStore.clearDraft()` also calls `soaEditStore.reset()`

#### Visual Indicators

| State | Visual | Description |
|-------|--------|-------------|
| Pending edit | Amber background + left border | Edit in draft, not yet published |
| User-edited (published) | Purple background | Cell was manually edited by user (persists after publish via `x-userEdited` extension) |
| Confirmed | Green background | Text + Vision extraction agree |
| Text-only | Blue background | Not confirmed by vision |
| Vision-only | Orange background | Needs review |
| Orphaned | Red background | No provenance data |

#### SoA Extension Attributes

User edits to SoA cells are persisted as USDM `extensionAttributes` on `ScheduledActivityInstance` objects:

| Extension URL | Type | Description |
|---------------|------|-------------|
| `https://usdm.cdisc.org/extensions/x-soaCellMark` | `valueString` | Cell mark value (X, O, Xa, Xb, Xc, −) |
| `https://usdm.cdisc.org/extensions/x-userEdited` | `valueString` | `"true"` if cell was manually edited |
| `https://usdm.cdisc.org/extensions/x-soaFootnoteRefs` | `valueString` | JSON array of footnote references |

All extension attributes include required USDM schema fields: `id` (UUID), `instanceType` (`"ExtensionAttribute"`), `url`, and `valueString`.

#### Cell Mark Priority (toSoATableModel)

When building the SoA grid from USDM data, cell marks are determined in this order:

1. `x-soaCellMark` from `ScheduledActivityInstance.extensionAttributes` (user-edited cells)
2. Default `X` if a `ScheduledActivityInstance` exists (extraction-created cells)
3. `X` if provenance data indicates a cell should exist (extraction without instances)
4. `null` (empty cell)

### 11.6 Post-Implementation Setup

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies
cd web-ui
npm install
```
