# Web UI — Comprehensive Architecture Review

**Date**: 2026-02-09 (updated 2026-02-10 with external reviewer findings)  
**Scope**: Full review of `web-ui/` — stores, APIs, components, data flow, editing, audit trail  
**Files reviewed**: 40+ files across stores (6), hooks (3), lib (10+), API routes (8+), components (67)  
**External review**: Two independent reviewers validated findings and identified 6 additional bugs (marked with ⚠️ EXT below)

---

## 1. Architecture Overview

### 1.1 Data Flow (Current)

```
                    ┌──────────────────────────────────────────┐
                    │  protocol_usdm.json (file system)        │
                    └──────────────┬───────────────────────────┘
                                   │ GET /api/protocols/[id]/usdm
                                   ▼
                    ┌──────────────────────────────────────────┐
                    │  protocolStore (Zustand)                  │
                    │  • usdm: USDMDocument (raw, immutable)   │
                    │  • revision: SHA256 hash                  │
                    │  • metadata: ProtocolMetadata             │
                    └──────────────┬───────────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                     │
              ▼                    ▼                     ▼
    ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
    │ semanticStore    │  │ soaEditStore     │  │ overlayStore    │
    │ • draft.patch[]  │  │ • cell edits     │  │ • diagram nodes │
    │ • undo/redo      │  │ • activity names │  │ • table order   │
    │ • isDirty        │  │ → pushes to      │  │ • snap grid     │
    └────────┬────────┘  │   semanticStore   │  └─────────────────┘
             │           └──────────────────-┘
             ▼
    ┌─────────────────────────────────────────────────────────┐
    │  usePatchedUsdm() hook                                   │
    │  rawUsdm + draft.patch[] → getPatchedUsdm() → patched   │
    └─────────────────────────────────────────────────────────┘
             │
             ▼
    ┌─────────────────────────────────────────────────────────┐
    │  Domain Views (15 components in components/protocol/)    │
    │  • StudyDesignView, EligibilityCriteriaView, etc.       │
    │  • Use EditableField / EditableCodedValue / EditableList │
    └─────────────────────────────────────────────────────────┘
```

### 1.2 Editing Flow

```
User clicks field → EditableField.handleSave()
  → semanticStore.addPatchOp({ op: 'replace', path, value })
    → snapshot current patch[] to undoStack
    → append op to draft.patch[]
    → isDirty = true
  → usePatchedUsdm() recomputes → all views update

Save Draft:
  UnifiedDraftControls.handleSaveDraft()
    → PUT /api/protocols/[id]/semantic/draft
    → validates USDM revision (SHA256 match)
    → validates immutable paths
    → archives previous draft
    → writes draft_latest.json (atomic: .tmp + rename)

Publish:
  UnifiedDraftControls.handlePublish()
    → POST /api/protocols/[id]/semantic/publish
    → loads draft_latest.json
    → validates USDM revision match
    → loads current protocol_usdm.json
    → applies JSON Patch (fast-json-patch)
    → archives current USDM to history/
    → writes updated protocol_usdm.json (atomic)
    → archives draft, writes published_latest.json
    → deletes draft_latest.json
    → runs validation pipeline (reads existing validation files)
    → returns validation results
    → UI clears draft, reloads USDM from server
```

### 1.3 Storage Layout

```
semantic/<protocolId>/
├── drafts/
│   ├── draft_latest.json          ← current working draft
│   └── draft_<timestamp>.json     ← archived drafts
├── published/
│   ├── published_latest.json      ← most recent published edit
│   └── published_<timestamp>.json ← all published versions
└── history/
    └── protocol_usdm_<timestamp>.json ← USDM snapshots before publish
```

---

## 2. Strengths

### 2.1 JSON Patch Architecture (RFC 6902) — ★★★★★
The choice of JSON Patch as the editing primitive is **excellent**. This is the single best architectural decision in the web UI:
- **Atomic operations**: Each edit is a discrete, reversible operation
- **Composable**: Multiple edits accumulate as a patch array, can be applied/reverted as a unit
- **Standard**: RFC 6902 is well-understood, has library support (fast-json-patch)
- **Serializable**: Patches are plain JSON — trivially stored, transmitted, audited
- **Source-of-truth preservation**: `protocol_usdm.json` is never modified in-place during editing; patches are applied at publish time

### 2.2 Immutable Base + Patch Overlay — ★★★★★
The `protocolStore` holds the raw (immutable) USDM, and `usePatchedUsdm()` computes a derived patched version. This separation is architecturally sound:
- Views always show current state (raw + patches)
- Raw USDM is never mutated during editing
- Patched computation is memoized via `useMemo`

### 2.3 SoA Processor — ★★★★☆
`SoAProcessor` is well-designed: it takes a USDM document, generates JSON Patch operations for SoA edits (cells, activities, encounters), and pushes them to `semanticStore`. This ensures SoA edits flow through the same patch pipeline as all other edits. The `validateSoAStructure()` utility checks referential integrity.

### 2.4 Typed USDM Interfaces — ★★★★☆
Auto-generated from `dataStructure.yml` via `scripts/generate_ts_types.py` → 68 strict interfaces in `usdm.generated.ts`, with runtime-safe variants in `index.ts` (optional fields + index signatures). This keeps Python and TypeScript schemas in sync.

### 2.5 Undo/Redo — ★★★★☆
`semanticStore` implements full undo/redo:
- Each `addPatchOp` snapshots the current `patch[]` to `undoStack`
- `beginGroup()`/`endGroup()` allows multi-op atomic undo (used by `EditableCodedValue`)
- Capped at 100 entries to prevent memory leaks
- Global keyboard shortcuts (Ctrl+Z / Ctrl+Shift+Z) via `useUndoRedoShortcuts`

### 2.6 Atomic File Operations — ★★★★☆
`storage.ts` uses `atomicWriteJson()` (write to `.tmp`, then `fs.rename`) for all file mutations. Publish uses the same pattern for `protocol_usdm.json`. This prevents corruption from crashes.

### 2.7 CDISC Terminology Dropdowns — ★★★★☆
`EditableCodedValue` ships with 14 pre-built CDISC terminology lists (study phase, arm type, blinding, sex, intervention role, route of administration, etc.) with proper NCI C-codes. This is production-quality.

### 2.8 Revision Conflict Detection — ★★★☆☆
The draft API validates `usdmRevision` (SHA256 hash) on both save and publish. If the USDM has changed underneath the draft (e.g., pipeline re-run), the API returns 409 Conflict. This prevents blind overwrites.

---

## 3. Weaknesses & Gaps

### 3.1 CRITICAL: Patches Reference Array Indices, Not Entity IDs — ★★★★★ severity

**This is the single most important architectural flaw.**

JSON Patch paths use array indices (`/study/versions/0/studyDesigns/0/arms/2/name`), not entity IDs. This means:
- If the pipeline re-extracts and the order of entities changes, **all saved patches break**
- If a user adds an arm (index 3), then another adds an arm at index 2, the first user's patches now point to the wrong arm
- Revision-conflict detection catches _file-level_ changes but not _entity-level_ reordering within the same file
- **SoAProcessor** compounds this: it finds indices at edit-time, but those indices may shift if earlier patches add/remove items from the same array

**How I would fix this**: Implement an **ID-based JSON Pointer resolver** that translates `arms/{id}/name` → `arms/2/name` at patch-application time. Store patches with entity IDs, resolve to indices only when applying. This is a fundamental change but essential for multi-user and re-extraction scenarios.

### 3.2 CRITICAL: No Real GxP Audit Trail — ★★★★★ severity

The current "history" system stores **patch documents** (what changed) but lacks the GxP-required audit metadata:
- **No authenticated user identity** — `updatedBy` is hardcoded to `'ui-user'`
- **No reason-for-change** — GxP requires a documented rationale for each edit
- **No electronic signature** — 21 CFR Part 11 requires meaning of signature
- **No tamper-evident trail** — files on disk can be manually edited; no hash chain or append-only log
- **No timestamps at operation level** — only at draft/publish level, not per-field-change
- **No role-based access control** — anyone with file access can edit anything

**How I would fix this**: 
1. Add an `AuditEntry` type: `{ timestamp, userId, action, reason, entityPath, oldValue, newValue, signature }`
2. Append-only audit log (one entry per `addPatchOp`) stored alongside patches
3. Hash-chain each entry (each entry includes SHA256 of the previous)
4. Require authentication (even basic username/password initially)
5. Require reason-for-change on publish (mandatory text field)
6. Add a `changeReason` field to `SemanticDraft` schema

### 3.3 HIGH: Editing Coverage Is Partial — ★★★★☆ severity

**What CAN be edited** (via EditableField/EditableCodedValue/EditableList/SoA):
| Area | Editing Support | Mechanism |
|------|----------------|-----------|
| Study metadata (names, IDs) | Scalar fields | EditableField |
| Arms (name, type) | List + coded values | EditableList + EditableCodedValue |
| Epochs (name, type) | List + coded values | EditableList + EditableCodedValue |
| Study phase, type, blinding | Coded dropdowns | EditableCodedValue |
| Eligibility criteria text | Text fields | EditableField |
| Population sex | Coded value | EditableCodedValue |
| Footnote text | Text fields | EditableField |
| SoA cell marks (X/O/−) | Keyboard + click | soaEditStore → SoAProcessor |
| SoA activity names | Inline edit | soaEditStore → SoAProcessor |
| SoA encounter names | Inline edit | soaEditStore → SoAProcessor |
| Epoch timeline (Gantt chart) | Click-to-edit detail panel | EpochTimelineChart |

**What CANNOT be edited** (major gaps):
| Area | Impact | Difficulty |
|------|--------|------------|
| Objectives/Endpoints text and level | Cannot correct objective wording or change Primary→Secondary | Medium |
| Estimand attributes | Cannot fix ICH E9(R1) data | Medium |
| Intervention details (dose, route, formulation) | Cannot correct drug/dose info | Medium |
| Timing values (visit windows, study days) | Cannot adjust ±3 day windows or study day numbers | High |
| Schedule timeline structure (add/remove timelines) | Cannot split SoA into multiple timelines | High |
| Narrative content text | Cannot edit the main protocol narrative | Medium |
| Population age/enrollment numbers | Cannot adjust demographics | Low |
| Organization/sponsor details | Cannot fix sponsor name/address | Low |
| Encounter visit windows | Cannot adjust window bounds | High |
| Graph view nodes and edges | View-only (read only on Cytoscape canvas) | High |
| Transition rules | Cannot modify state machine | High |
| Conditions/decision instances | Cannot edit scheduling conditions | High |
| Amendments | Read-only display | Medium |

### 3.4 HIGH: No Cross-Entity Referential Integrity Checking — ★★★★☆ severity

When editing via JSON Patch:
- Deleting an arm doesn't check if any `StudyCell` references it
- Deleting an encounter doesn't check if any `ScheduledActivityInstance` points to it
- Deleting an activity doesn't check if any `ScheduleTimeline.instances` reference it
- Renaming an arm doesn't propagate to the StudyCell's `armId`

`validateSoAStructure()` exists in `SoAProcessor` but is **not called during publish**. The publish endpoint only reads pre-existing validation files from disk — it doesn't run live validation on the patched USDM.

**How I would fix this**: Add a **pre-commit validation step** in the publish endpoint that:
1. Applies the patch to produce the candidate USDM
2. Runs referential integrity checks (all IDs resolve, no dangling references)
3. Runs schema validation against `dataStructure.yml`
4. Returns blocking errors if integrity is violated

### 3.5 CRITICAL: Publish Writes USDM Before Validation Gate — ★★★★★ severity ⚠️ EXT

The publish endpoint (`publish/route.ts`) writes the patched USDM to disk (step 6, lines 159-160) **before** running validation (step 9, line 178). If validation fails, the response reports `validation_failed` but the USDM file is already persisted with potentially invalid content. The source-of-record can become invalid while the UI reports "publish failed".

Additionally, `runValidation()` reads **pre-existing** validation report files from disk:
```typescript
const schemaContent = await fs.readFile(schemaPath, 'utf-8'); // reads OLD file
```
It does NOT run the Python validation pipeline on the newly-patched USDM. This means:
- Published edits bypass validation entirely
- Validation results shown after publish reflect the PREVIOUS pipeline run, not the edited document
- A user could break USDM conformance and see green checkmarks

**How I would fix this**: Implement a **candidate→validate→commit** pipeline:
1. Apply patches to produce candidate USDM (in memory)
2. Run validation on candidate (shell to Python or TypeScript-side)
3. Only write to disk if validation passes (or user explicitly force-publishes)
4. Archive and clean up draft only after successful write

### 3.6 HIGH: Timestamp Format Bug Breaks History Matching — ★★★★☆ severity ⚠️ EXT

`getTimestamp()` in `storage.ts:88-89` produces timestamps like `2026-02-09T2315Z` (with dashes, no seconds). But all history-matching regexes (`listSemanticFiles`, `getVersionHistory`, `findSnapshotForPublish`) expect format `\d{8}T\d{6}Z` (e.g., `20260209T231500Z`). The regex never matches, so:
- `listSemanticFiles` falls back to `stat.mtime` instead of filename-embedded timestamps
- `findSnapshotForPublish` can't match publish timestamps to USDM snapshots — revert may fail
- Minute-level resolution (no seconds) risks archive collisions for rapid operations

**Root cause**: `getTimestamp()` removes `:` and `.` via `/[:.]/g` but does NOT remove `-` dashes. Also `.slice(0, 15)` truncates seconds.

**Fix**: Change the regex to `/[-:.]/g` to also strip dashes, producing `20260209T231500Z`.

### 3.7 HIGH: SoA Cell Mark Edits Retain Stale Values — ★★★★☆ severity ⚠️ EXT

`SoAProcessor.addMarkExtension()` (`processor.ts:249-256`) appends new extension attributes via `op: 'add', path: '.../-'`. But `findExt()` (`extensions.ts:30`) uses `.find()` which returns the **first** (oldest) match. After editing a cell mark twice, the reader still sees the original mark value.

**Fix**: Either replace-in-place (find existing extension by URL and use `op: 'replace'`) or normalize before write (remove existing extensions with the same URL key before appending).

### 3.8 HIGH: SoA Undo Granularity Bug — ★★★★☆ severity ⚠️ EXT

`soaEditStore.setCellMark()` (`soaEditStore.ts:131-133`) loops through result patches calling `addPatchOp()` individually. Each sub-op (mark extension, userEdited flag, optional footnote) creates a **separate** undo entry. Undoing once removes only the last sub-op, leaving the cell in an inconsistent state (e.g., mark removed but userEdited flag still set).

**Fix**: Wrap in `beginGroup()`/`endGroup()`:
```typescript
semanticStore.beginGroup();
for (const patch of result.patches) {
  semanticStore.addPatchOp(patch);
}
semanticStore.endGroup();
```

### 3.9 HIGH: SoA Visual State Desync on Undo — ★★★★☆ severity ⚠️ EXT

When `semanticStore.undo()` restores a previous `draft.patch` array, `soaEditStore.committedCellEdits` is **not** cleared or synced. The SoA grid continues showing visual edit indicators for cells whose patches have been undone.

**Fix**: Either derive `committedCellEdits` reactively from the current `draft.patch` array (eliminate the duplicate tracking), or add a subscription in `soaEditStore` that resets when `semanticStore.draft.patch` changes.

### 3.10 MEDIUM: Overlay Routes Missing Input Sanitization — ★★★☆☆ severity ⚠️ EXT

`overlay/draft/route.ts` and `overlay/publish/route.ts` accept `protocolId` from URL params without calling `validateProtocolId()`. The semantic routes all use this sanitization (preventing path traversal), but overlay routes skip it entirely.

**Fix**: Add `validateProtocolId(protocolId)` check at the start of all overlay route handlers, matching the pattern in semantic routes.

### 3.11 MEDIUM: Extension Namespace Inconsistency Between Backend and Frontend

The Python backend uses `https://protocol2usdm.io/extensions/x-...` for extension URLs (e.g., `orchestrator.py:673`, `execution_model_promoter.py:1086`), while the TypeScript frontend uses `https://usdm.cdisc.org/extensions/x-...` (`extensions.ts:124-132`). Extensions written by one side cannot be reliably found by the other.

**Fix**: Define a shared extension namespace constant in both codebases. Use a single canonical URL prefix.

### 3.12 LOW: `sha256:unknown` Concurrency Bypass

Both `draft/route.ts:84` and `publish/route.ts:115` skip the revision check when `usdmRevision === 'sha256:unknown'`. A buggy client could always send `sha256:unknown` to bypass conflict detection on publish.

**Fix**: Reject `sha256:unknown` on publish. Only allow it on initial draft creation when no USDM file exists yet.

### 3.13 LOW: `Math.random()` UUID in SoAProcessor

`processor.ts:89-95` generates UUIDs with `Math.random()` instead of `crypto.randomUUID()`. While collision risk is negligible in practice, `crypto.randomUUID()` is available in all modern browsers and Node.js 19+ and should be preferred for consistency.

### 3.14 MEDIUM: Information Flow Across Views Is Incomplete — ★★★☆☆ severity

`usePatchedUsdm()` provides patched data to any view that uses it. However:
- **Not all views use `usePatchedUsdm()`** — some read directly from `protocolStore.usdm`
- The SoA view correctly uses `usePatchedStudyDesign()`, but the Timeline/Graph views read raw USDM
- The `ExecutionModelView` (131KB — the largest component) appears to build its own data structures from raw USDM, meaning it won't reflect draft edits

**How I would fix this**: Mandate that all domain views use `usePatchedUsdm()` or `usePatchedStudyDesign()`. Grep for direct `useProtocolStore(state => state.usdm)` usage and replace.

### 3.15 MEDIUM: Undo/Redo Stores Full Patch Snapshots — ★★★☆☆ severity

Each undo entry is a **complete copy** of `draft.patch[]`. With 100 undo slots and a patch array that could grow to hundreds of operations, this could consume significant memory:
- 100 edits × 100 patches × ~500 bytes per patch = ~5MB
- In practice this is likely fine for now, but it's an O(n²) pattern

**How I would fix this**: Store inverse operations instead of full snapshots. For `replace`, store `{ op: 'replace', path, value: previousValue }`. For `add`, store `{ op: 'remove', path }`. This gives O(n) undo history.

### 3.16 MEDIUM: DiffView Shows Raw JSON Paths, Not Human-Friendly Names — ★★★☆☆ severity

The `humanizePath()` function in `DiffView.tsx` makes a reasonable effort to convert paths like `/study/versions/0/studyDesigns/0/arms/2/name` to `arms[2].name`, but:
- It doesn't resolve entity IDs to display names (e.g., "Arm: Placebo" instead of "arms[2]")
- Complex paths (deep nesting, extension attributes) are barely readable
- No "before" value is shown for `replace` operations — only the new value

**How I would fix this**: Enhance `humanizePath()` to accept the current USDM and resolve array indices to entity `name`/`label` fields. Show both old and new values for replace ops (requires looking up the old value from raw USDM at the given path).

### 3.17 LOW: overlayStore Is a Separate Editing Concern — ★★☆☆☆ severity

`overlayStore` manages **visual layout** (diagram node positions, table row/column order, snap grid). This is a separate concern from USDM editing but:
- It has its own draft/publish lifecycle (separate from semantic editing)
- Its save/publish is wired through the same UnifiedDraftControls
- It uses a different storage format (`OverlayDoc`) not related to JSON Patch
- This split is actually reasonable for now, but complicates the "publish" UX

### 3.18 LOW: No Offline or Optimistic Update Support — ★★☆☆☆ severity

- Drafts are saved to the server filesystem; no IndexedDB/localStorage fallback
- Network errors during save can lose in-memory edits
- No queued-mutation pattern for resilience

---

## 4. Detailed Assessment by Requirement

### 4.1 Editing & Source-of-Record Consistency

| Requirement | Status | Notes |
|-------------|--------|-------|
| Edit scalar fields on USDM entities | ✅ Working | EditableField generates JSON Patch ops |
| Edit coded values (CDISC terminology) | ✅ Working | EditableCodedValue with 14 codelists |
| Edit list items (add/remove/reorder) | ⚠️ Partial | EditableList supports add/remove; reorder is visually present but untested at scale |
| Publish patches to protocol_usdm.json | ⚠️ Bug | Writes USDM before validation gate (§3.5) |
| Detect stale USDM (revision conflict) | ⚠️ Bypass | `sha256:unknown` skips check (§3.12) |
| All views show draft state | ⚠️ Partial | 15+ views get raw USDM; only 5 use getPatchedUsdm (§3.14) |
| Referential integrity after edit | ❌ Missing | No cross-entity validation on publish |
| Version history matching | ⚠️ Bug | Timestamp format mismatch breaks filename regex (§3.6) |
| SoA cell mark consistency | ⚠️ Bug | Stale values on re-edit due to extension append (§3.7) |

### 4.2 Timing, Visit Schedules, Graph View Editing

| Requirement | Status | Notes |
|-------------|--------|-------|
| Edit SoA cell marks | ✅ Working | Keyboard navigation (X/O/−/Del), mouse click |
| Edit activity/encounter names | ✅ Working | Via soaEditStore → SoAProcessor → semanticStore |
| Add new activities/encounters | ⚠️ Implemented but not wired to UI | SoAProcessor has `addActivity()`, `addEncounter()` but no UI exposes them |
| Edit visit windows (±days) | ❌ Missing | Timing values are read-only |
| Edit study day numbers | ❌ Missing | No edit mechanism for Timing.studyDay |
| Edit epoch durations | ❌ Missing | EpochTimelineChart is click-to-view, not click-to-edit timing |
| Edit graph view (Cytoscape) | ❌ Missing | Graph is read-only; node positions are in overlayStore but edge/node data is not editable |
| Edit transition rules | ❌ Missing | State machine is read-only |

### 4.3 GxP Audit Trail

| Requirement | Status | Notes |
|-------------|--------|-------|
| Authenticated user identity | ❌ Missing | Hardcoded 'ui-user' |
| Reason for change | ❌ Missing | No UI prompt, no schema field |
| Per-field change timestamp | ⚠️ Partial | Draft-level updatedAt, not per-op |
| Tamper-evident log | ❌ Missing | Plain JSON files, no hash chain |
| Electronic signature | ❌ Missing | No 21 CFR Part 11 support |
| Version history browsing | ✅ Working | VersionHistoryPanel shows published versions |
| Revert to previous version | ✅ Working | Via `/semantic/revert` endpoint |
| Validation status per version | ✅ Working | Stored on published entries |

### 4.4 Undo/Redo, Human-Readable History

| Requirement | Status | Notes |
|-------------|--------|-------|
| Undo (Ctrl+Z) | ✅ Working | Full patch-level undo |
| Redo (Ctrl+Shift+Z) | ✅ Working | Full patch-level redo |
| Grouped undo (multi-op as one) | ✅ Working | beginGroup()/endGroup() available but not used by SoA (§3.8) |
| SoA undo consistency | ⚠️ Bug | Cell edits not grouped; partial undo corrupts cell state (§3.8) |
| SoA visual state after undo | ⚠️ Bug | committedCellEdits not synced on undo (§3.9) |
| Unsaved changes guard | ✅ Working | beforeunload dialog |
| DiffView of pending changes | ✅ Working | Color-coded, per-op display |
| Remove individual pending ops | ✅ Working | Per-op delete in DiffView |
| Human-readable change descriptions | ⚠️ Basic | Path-based, not entity-name-based |
| Before/after values in diff | ⚠️ Partial | Only shows new value, not old |

---

## 5. Enhancement Recommendations (Prioritized)

### P0: Quick-Fix Bugs (External Review — all Small effort) ⚠️ EXT
These are verified bugs with straightforward fixes. Should be addressed before any architectural work.

| # | Bug | Fix | Ref |
|---|-----|-----|-----|
| 0.1 | Timestamp format mismatch — history matching broken | Change `/[:.]/g` to `/[-:.]/g` in `getTimestamp()` | §3.6 |
| 0.2 | SoA cell mark stale values — appends instead of replaces | Replace-in-place or normalize extensions before write | §3.7 |
| 0.3 | SoA undo granularity — partial undo corrupts cells | Wrap `setCellMark` patches in `beginGroup()`/`endGroup()` | §3.8 |
| 0.4 | SoA visual desync on undo — committedCellEdits stale | Derive from `draft.patch` reactively or add sync listener | §3.9 |
| 0.5 | Overlay routes missing `validateProtocolId()` | Add sanitization matching semantic routes | §3.10 |
| 0.6 | `sha256:unknown` bypass on publish | Reject on publish; allow only on initial draft | §3.12 |
| 0.7 | `Math.random()` UUID | Replace with `crypto.randomUUID()` | §3.13 |
| 0.8 | Extension namespace mismatch backend↔frontend | Unify to single canonical URL prefix | §3.11 |

### P1: ID-Based Patch Paths (Architecture Fix)
**Effort**: Large  
**Impact**: Eliminates the fundamental brittleness of index-based patches  
- Store patches as `{ path: "/arms/{armId}/name", value: "..." }`
- Resolve `{armId}` → array index at apply time
- Requires: patch path resolver, schema-aware path parser
- Benefits: Multi-user safety, re-extraction compatibility, predictable patch semantics

### P2: Transactional Publish Pipeline (Candidate→Validate→Commit)
**Effort**: Medium  
**Impact**: Prevents publishing invalid USDM (fixes §3.5 write-before-validate bug)  
- Apply patches to produce candidate USDM **in memory**
- Run validation on candidate before any disk write
- Only write to disk if validation passes (or user explicitly force-publishes with acknowledgment)
- Add referential integrity checks (`validateSoAStructure()`) as publish gate
- Archive and clean up draft only after successful commit

### P3: GxP Audit Trail Foundation
**Effort**: Medium  
**Impact**: Required for regulated use  
- Add `userId` field (even without full auth, allow username input)
- Add `changeReason` to `SemanticDraft` schema + UI modal on publish
- Add per-operation `timestamp` and `operationId` to each `JsonPatchOp`
- Hash-chain the audit entries for tamper evidence
- Store audit log separately from draft (append-only `audit_log.jsonl`)

### P4: Extend Editing Coverage
**Effort**: Medium per domain  
**Impact**: Makes the editor usable for clinical review  
Priority order:
1. **Objectives/Endpoints** — EditableField on text, EditableCodedValue on level
2. **Intervention details** — dose, route, formulation via EditableField
3. **Population demographics** — age Range editor, enrollment QuantityRange editor
4. **Narrative content** — rich text editor for section narrative
5. **Timing/windows** — custom TimingEditor component for study days and windows
6. **Transition rules** — visual state machine editor

### ~~P5: Consistent Use of usePatchedUsdm~~ ✅ FIXED
**Effort**: Small  
**Impact**: Ensures all views reflect draft changes  
- Protocol page now uses `usePatchedUsdm()` — all 15 child views receive patched USDM
- `ExecutionModelView` already used `usePatchedStudyDesign()` internally
- `soaEditStore` correctly reads raw USDM for patch generation (intentional — avoids double-application)

### P6: Enhanced DiffView
**Effort**: Small-Medium  
**Impact**: Better human readability of pending changes  
- Resolve entity IDs to display names in `humanizePath()`
- Show before/after values for replace operations
- Group related changes (e.g., code + decode from EditableCodedValue)
- Add filtering by entity type

### P7: Inverse-Operation Undo
**Effort**: Medium  
**Impact**: O(n) memory instead of O(n²)  
- Store inverse ops instead of full patch snapshots
- For `replace`: store `{ inverseOp: 'replace', path, value: previousValue }`
- For `add`: store `{ inverseOp: 'remove', path }`
- For `remove`: store `{ inverseOp: 'add', path, value: removedValue }`

### ~~P8: Expose SoAProcessor's Add Capabilities in UI~~ ✅ FIXED
**Effort**: Small  
**Impact**: Enables adding new visits and activities from the SoA grid  
- `soaEditStore.addActivity()` and `addEncounter()` wired with `beginGroup()`/`endGroup()` for atomic undo
- "Add Row" and "Add Visit" buttons in SoA toolbar (dashed border, edit-mode only)
- Simple `window.prompt()` dialogs for name input; encounters default to first epoch

---

## 6. How I Would Have Architected This Differently

### 6.1 Command Pattern Instead of Raw Patches

Instead of accumulating raw JSON Patch operations, I would have used a **domain-specific command pattern**:

```typescript
type EditCommand = 
  | { type: 'UPDATE_ARM_NAME'; armId: string; name: string }
  | { type: 'SET_BLINDING'; code: string; decode: string }
  | { type: 'ADD_ENCOUNTER'; name: string; epochId: string; afterId?: string }
  | { type: 'SET_CELL_MARK'; activityId: string; encounterId: string; mark: CellMark }
  | ...

function commandToPatches(cmd: EditCommand, usdm: USDMDocument): JsonPatchOp[] {
  // Resolve IDs to indices at application time, not edit time
}
```

**Benefits**:
- Commands are human-readable by nature (`SET_BLINDING` vs `replace /study/versions/0/studyDesigns/0/blindingSchema/standardCode/code`)
- Commands can validate preconditions before generating patches
- Commands can generate inverse commands for true undo
- Commands provide natural audit log entries
- Commands are resilient to entity reordering (they use IDs, not indices)
- Commands can enforce business rules (e.g., "cannot delete an arm if it has study cells")

The current JSON Patch approach would remain as the **serialization format** — commands produce patches for storage and application, but the user-facing abstraction is commands.

### 6.2 Server-Side Patch Application

Currently, patch application happens in two places:
1. **Client-side** (`usePatchedUsdm` for preview)
2. **Server-side** (publish endpoint)

I would add a **server-side preview endpoint**: `POST /api/protocols/[id]/semantic/preview` that:
- Takes the current draft patches
- Applies them to the USDM
- Runs validation
- Returns the patched USDM + validation results
- This ensures client and server agree on the result before publish

### 6.3 Event-Sourced Audit Log

Instead of storing patches as the primary edit representation, I would use **event sourcing**:
- Each edit is an immutable event with full metadata
- Events are append-only (never modified)
- Current state is derived by replaying events
- This naturally provides a complete, tamper-evident audit trail
- Events can be projected into JSON Patches for application

### 6.4 Collaborative Editing Foundation

The current architecture is single-user (file-based, no locking). For multi-user:
- Use **Operational Transformation** or **CRDTs** for real-time collaboration
- Or simpler: **pessimistic locking** per entity (user X is editing arm 2, locked for others)
- The command pattern above would enable either approach

---

## 7. Component Inventory

### 7.1 Stores (6)
| Store | Size | Purpose | Quality |
|-------|------|---------|---------|
| `protocolStore.ts` | 176 lines | Raw USDM + selectors + patch helpers | ★★★★★ Clean, well-typed |
| `semanticStore.ts` | 257 lines | Draft/patch/undo/redo management | ★★★★☆ Solid, good group support |
| `soaEditStore.ts` | 361 lines | SoA cell/activity/encounter edits | ★★★★☆ Good processor integration |
| `editModeStore.ts` | 28 lines | Edit mode toggle | ★★★★★ Minimal, correct |
| `toastStore.ts` | 56 lines | Toast notifications | ★★★★★ Clean convenience API |
| `overlayStore.ts` | 206 lines | Visual layout state | ★★★☆☆ Separate concern, adds complexity |

### 7.2 Semantic Editors (9)
| Component | Size | Purpose | Quality |
|-----------|------|---------|---------|
| `EditableField.tsx` | 307 lines | Inline text/number/boolean editing | ★★★★☆ Well-designed |
| `EditableCodedValue.tsx` | 305 lines | CDISC terminology dropdown | ★★★★★ Production-quality |
| `EditableList.tsx` | 248 lines | Array add/remove/reorder | ★★★★☆ Good, reorder needs testing |
| `EditableObject.tsx` | ~150 lines | Object property editor | ★★★☆☆ Less used |
| `DiffView.tsx` | 205 lines | Pending changes visualization | ★★★☆☆ Functional, needs enhancement |
| `UnifiedDraftControls.tsx` | 449 lines | Save/publish/discard/undo/redo | ★★★★☆ Comprehensive |
| `VersionHistoryPanel.tsx` | 306 lines | Version history browser + revert | ★★★☆☆ Functional, needs auth |
| `SemanticDraftControls.tsx` | ~300 lines | Older draft controls | ★★☆☆☆ Superseded by Unified |
| `index.ts` | 22 lines | Barrel exports | ★★★★★ |

### 7.3 Key Libraries
| Library | Purpose | Quality |
|---------|---------|---------|
| `lib/semantic/patcher.ts` | JSON Patch apply + validate | ★★★★★ Solid safety checks |
| `lib/semantic/schema.ts` | Zod schemas, immutable paths | ★★★★★ Well-structured |
| `lib/semantic/storage.ts` | File-based draft/publish/history | ★★★★☆ Good atomic writes |
| `lib/soa/processor.ts` | SoA edit → JSON Patch | ★★★★☆ Comprehensive |
| `lib/adapters/toSoATableModel.ts` | USDM → grid model adapter | ★★★★☆ |
| `lib/types/usdm.generated.ts` | 68 USDM TypeScript interfaces | ★★★★★ Auto-generated |
| `lib/sanitize.ts` | Input sanitization | ★★★★☆ Good security practice |

---

## 8. Summary

The web UI has a **strong architectural foundation** (JSON Patch, immutable base + patch overlay, typed USDM interfaces, atomic file operations) but is at an **early-to-mid stage of maturity** for the editing use case. The core editing flow (edit → preview → undo/redo → save → publish) works correctly for the supported field types.

**External review (Feb 2026)** identified 8 concrete bugs (P0 items) that should be fixed before any architectural work:
- **Timestamp format mismatch** breaks all history file matching (§3.6)
- **SoA cell mark stale values** on re-edit (§3.7)
- **Publish writes USDM before validation gate** — source-of-record can become invalid (§3.5)
- **SoA undo granularity** and **visual desync** bugs (§3.8, §3.9)
- **Overlay routes missing input sanitization** (§3.10)
- **Extension namespace inconsistency** between backend and frontend (§3.11)

The four critical architectural gaps remain:
1. **Index-based patch paths** (fragile across re-extraction)
2. **Publish writes before validation** (source-of-record corruption risk)
3. **No GxP audit trail** (blocks regulated use)
4. **Incomplete view propagation** (15+ views read raw USDM, not patched)

Addressing P0 (quick-fix bugs) then P1-P3 would transform this from a viewer-with-editing into a credible clinical protocol authoring tool.
