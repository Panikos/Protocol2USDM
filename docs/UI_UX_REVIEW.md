# Protocol2USDM — Comprehensive UI/UX Review

**Date:** 2026-02-11  
**Scope:** Full web-ui codebase (60+ components, 6 stores, 3 hooks, 3 pages, 9 UI primitives)  
**Frameworks:** Nielsen's Heuristics, Gestalt Principles, Hick's Law, Fitts's Law, WCAG 2.1, ISO 9241

---

## Executive Summary

The UI is **well-architected** with a solid technical foundation — shadcn/ui primitives, Zustand state management, Immer immutability, and a thoughtful semantic editing system with undo/redo. The overall design is clean, functional, and appropriate for a clinical data specialist audience.

However, the review identified **38 findings** across 8 categories, ranging from critical accessibility gaps to enhancement opportunities. The most impactful areas are: **accessibility** (missing ARIA, keyboard traps), **pattern inconsistency** (duplicated dropdown logic, mixed header patterns), and **error handling gaps** (silent failures in API calls).

### Severity Breakdown
| Severity | Count | Description |
|----------|-------|-------------|
| **CRITICAL** | 4 | Blocks usability or accessibility compliance |
| **HIGH** | 10 | Degrades experience significantly |
| **MEDIUM** | 14 | Inconsistency or missing best practice |
| **LOW** | 10 | Enhancement opportunity |

---

## 1. Design System & Component Consistency

### 1.1 GOOD: Solid Foundation
- shadcn/ui primitives (`Button`, `Card`, `Badge`, `Progress`, `HoverCard`) are well-implemented with CVA variants
- CSS custom properties for theming with light/dark mode support
- `cn()` utility (clsx + tailwind-merge) used consistently
- Tailwind config extends shadcn tokens properly
- Custom provenance/status color tokens defined in both Tailwind config and globals.css

### 1.2 FINDINGS

**[F1] MEDIUM — Duplicate Dropdown Pattern**  
Three components implement their own dropdown/popover logic with `fixed inset-0` backdrop + absolute menu:
- `TabGroup` (`tab-group.tsx:56-81`)
- `ExportButton` (`export-button.tsx:66-86`)
- `SoACellEditor` (popup positioning)

All should use a shared `Popover` or `DropdownMenu` primitive from Radix (already in dependencies: `@radix-ui/react-dropdown-menu`). The current pattern has:
- No focus trapping
- No Escape key handling (only backdrop click)
- No ARIA attributes (`role="menu"`, `aria-expanded`)
- Inconsistent z-index values (z-40, z-50, z-60, z-70)

**[F2] MEDIUM — Hardcoded Colors Bypass Design Tokens**  
Several components use raw Tailwind colors instead of semantic tokens:
- `tab-group.tsx:72-73`: `bg-blue-50`, `text-blue-600`, `text-gray-600`, `hover:bg-gray-100`
- `UnifiedDraftControls.tsx`: `bg-blue-600 hover:bg-blue-700`
- `DiffView.tsx`: `text-green-600`, `text-red-600`, `bg-green-50`, `bg-red-50`
- `globals.css:122-140`: Provenance cell colors are raw hex (`#4ade80`) duplicated from Tailwind config tokens

These should reference design tokens (`primary`, `destructive`, `accent`) or the custom `provenance.*` / `status.*` tokens.

**[F3] LOW — Two Tab Systems**  
`tab-group.tsx` (dropdown-style grouped tabs) and `tabs.tsx` (inline Radix-style tabs) coexist. The main protocol detail page uses `TabGroup` while sub-views (e.g., `TimelineTab`) use inline `Button` toggle groups. Consider unifying or documenting when to use which.

**[F4] LOW — Badge Quoting Style Inconsistency**  
`badge.tsx` uses double quotes while `button.tsx`, `card.tsx` use single quotes. Minor but should be consistent per project convention.

---

## 2. Navigation, Routing & Layout

### 2.1 GOOD
- Clean Next.js App Router structure: `/` → `/protocols` → `/protocols/[id]`
- Sticky header with breadcrumb-style back navigation
- Edit mode toggle clearly visible in header
- Draft controls contextually shown only in edit mode

### 2.2 FINDINGS

**[F5] HIGH — No Shared Layout Component**  
Each page (home, protocols list, protocol detail) implements its own header with duplicated markup:
- `page.tsx:10-29`: Header with logo + nav
- `protocols/page.tsx:42-56`: Header with logo
- `protocols/[id]/page.tsx:305-393`: Header with back button + tabs

A shared `<AppShell>` or `<Layout>` component would enforce consistency and reduce duplication. Currently the home page has a "Documentation" link (`/docs`) that leads to a 404.

**[F6] MEDIUM — Tab Navigation Cognitive Overload (Hick's Law)**  
The protocol detail page has **21 tabs** across 4 groups (Protocol: 6, Advanced: 6, Quality: 2, Data: 6). This violates Hick's Law — too many choices slow decision-making. 

Recommendations:
- Merge "Overview" with "Design" (overlapping content — both show arms, blinding, randomization)
- Move "Footnotes" into the SoA view (they're SoA-specific)
- Consider whether "Extensions" and "Entities" (both show raw USDM data) need separate tabs
- The "M11 Protocol" tab under "Data" is confusing — it's a document view, not raw data

**[F7] MEDIUM — Dead `OverviewTab` Component**  
`protocols/[id]/page.tsx:483-561` defines an `OverviewTab` function that is **never used**. The `overview` tab renders `StudyMetadataView` instead. This dead code should be removed or the two should be reconciled.

**[F8] LOW — No URL-Synced Tab State**  
Active tab is local React state. Refreshing the page or sharing a URL always resets to "Overview". Should use URL search params (`?tab=soa`) so users can bookmark or share specific views.

---

## 3. Accessibility (WCAG 2.1)

### 3.1 GOOD
- `<html lang="en">` set correctly
- `Tabs` component uses `role="tab"` + `aria-selected`
- Focus ring styles on buttons via `focus-visible:ring-2`
- Keyboard shortcuts for undo/redo properly exclude input fields

### 3.2 FINDINGS

**[F9] CRITICAL — TabGroup Dropdown Has No Keyboard Support**  
`TabGroup` (`tab-group.tsx`) renders a custom dropdown with no keyboard navigation:
- No `role="menu"` / `role="menuitem"` attributes
- No arrow key navigation between items
- No Escape key to close
- No focus management — focus doesn't move into the dropdown when opened
- Screen readers see plain `<button>` elements with no relationship context

**[F10] CRITICAL — AG Grid Accessibility**  
The SoA grid (`SoAGrid.tsx`) does not configure AG Grid's accessibility features:
- No `ensureDomOrder` prop
- No `suppressCellFocus` configuration
- Custom cell renderers (`ProvenanceCellRenderer`) and editors (`SoACellEditor`) lack ARIA labels
- Quick-mark keyboard shortcuts (X, O, -) are undiscoverable — no help text or tooltip

**[F11] HIGH — Toast Notifications Missing ARIA Live Region**  
`ToastContainer.tsx` renders toasts without `role="alert"` or `aria-live="polite"`. Screen readers won't announce toast messages. The container should have `aria-live="polite"` and individual toasts should have `role="status"`.

**[F12] HIGH — Missing Form Labels**  
Several inline editing components lack associated `<label>` elements:
- `EditableField.tsx` renders `<input>` without `<label>` or `aria-label`
- `SoACellEditor.tsx` renders radio buttons without proper labeling
- Search input in `SoAToolbar` has placeholder text but no `aria-label`

**[F13] MEDIUM — Color-Only Information (Provenance)**  
Provenance cells use color alone to convey status (green=confirmed, blue=text-only, orange=vision-only, red=orphaned). This fails WCAG 1.4.1 (Use of Color). Need secondary indicators (icons, patterns, or text labels).

**[F14] MEDIUM — Missing Skip Navigation Link**  
No skip-to-content link for keyboard users to bypass the header and 21-tab navigation bar.

**[F15] MEDIUM — ExportButton and TabGroup Dropdown — No Focus Trap**  
When dropdowns open, Tab key moves focus to elements behind the backdrop overlay instead of cycling within the dropdown.

---

## 4. State Management & Data Flow

### 4.1 GOOD: Excellent Architecture
- **6 Zustand stores** with clear separation of concerns:
  - `protocolStore` — raw USDM + metadata
  - `overlayStore` — diagram/table layout (Immer)
  - `semanticStore` — JSON Patch editing with undo/redo (Immer)
  - `soaEditStore` — SoA cell editing bridging to semantic store
  - `editModeStore` — simple boolean toggle
  - `toastStore` — notification queue
- `usePatchedUsdm` hook cleanly computes USDM + patches with `useMemo`
- Undo/redo with bounded history (MAX_UNDO_HISTORY = 100)
- Group operations (`beginGroup`/`endGroup`) for atomic multi-op edits
- Unsaved changes guard (`useUnsavedChangesGuard`) prevents data loss

### 4.2 FINDINGS

**[F16] HIGH — Dynamic Import in semanticStore Initialization**  
`semanticStore.ts:9-11` uses a dynamic `import()` at module level to avoid circular deps:
```ts
let resetSoAEditStore: (() => void) | null = null;
import('@/stores/soaEditStore').then(({ useSoAEditStore }) => {
  resetSoAEditStore = () => useSoAEditStore.getState().reset();
});
```
This is a race condition — if `clearPatch()` or `undo()` is called before the dynamic import resolves, `resetSoAEditStore` will be null and SoA state won't reset. Should use lazy initialization pattern: `const getResetFn = () => require('@/stores/soaEditStore').useSoAEditStore.getState().reset;`

**[F17] MEDIUM — Protocol Detail Page Mixes Data Fetching Patterns**  
`protocols/[id]/page.tsx` uses raw `fetch()` in `useEffect` while the app has `@tanstack/react-query` configured. The protocols list page also uses raw `useEffect + fetch`. All data fetching should use React Query for caching, error boundaries, and loading states.

**[F18] MEDIUM — SoAEditStore Uses Vanilla Map/Set**  
`soaEditStore.ts` uses `new Map()` and `new Set()` without Immer. Zustand won't detect mutations to these — the store must create new instances on every update (which it does correctly via `new Map(state.committedCellEdits)`). However, this is fragile and easy to accidentally break. Consider using plain objects/arrays or enabling Immer middleware.

---

## 5. Error Handling, Loading & Empty States

### 5.1 GOOD
- Protocols list page has proper loading spinner, error card with retry, and empty state with CLI instructions
- Protocol detail page shows centered error with back-to-list button
- Toast store provides success/error/warning/info notifications
- `SoAEditStore` tracks `lastError` per operation

### 5.2 FINDINGS

**[F19] HIGH — Silent API Failures in Draft Controls**  
`UnifiedDraftControls.tsx` and `protocols/[id]/page.tsx` catch API errors but only `console.error()` them:
```ts
} catch (err) {
  console.error('Error saving draft:', err);
}
```
Users get no feedback when save/publish fails. Should show a toast notification (`toast.error('Failed to save draft')`).

**[F20] HIGH — handleReloadUsdm Silently Fails**  
`protocols/[id]/page.tsx:158-161`: If USDM reload fails after publish, the error is only logged to console. The UI will show stale data with no indication that the reload failed.

**[F21] MEDIUM — No Error Boundary**  
No React error boundary wraps the application. A crash in any component (e.g., bad USDM data causing a render error in `ExtensionsView`) will white-screen the entire app. Should wrap major sections in error boundaries.

**[F22] MEDIUM — Loading State Missing for Tab Content**  
When switching tabs, the new view renders immediately. For tabs that compute expensive models (e.g., SoA table, Quality Metrics, ExecutionModelView at 131KB), there's no loading indicator during computation. Consider `React.lazy` + `Suspense` for heavy tabs.

---

## 6. Interaction Design & UX Patterns

### 6.1 GOOD
- SoA grid supports keyboard shortcuts (X, O, -) for quick cell marking
- Drag-and-drop row/column reordering in SoA
- Edit mode toggle clearly separates view and edit states
- DiffView shows pending changes with color-coded op types and individual removal
- Unsaved changes warning on page leave

### 6.2 FINDINGS

**[F23] HIGH — Edit Mode Not Persisted Across Tab Switches**  
Edit mode is global (`editModeStore`), but switching to a tab that doesn't support editing (e.g., "Provenance", "Quality Metrics") doesn't indicate that edit mode is irrelevant there. Consider:
- Disable the Edit toggle on read-only tabs
- Show a subtle indicator: "Editing not available on this tab"

**[F24] MEDIUM — No Confirmation Before Destructive Actions**  
- "Clear All" button in `DiffView.tsx:167` deletes all pending changes with one click — no confirmation dialog
- The discard confirmation exists in `UnifiedDraftControls` but not in the DiffView's Clear All

**[F25] MEDIUM — Keyboard Shortcut Discoverability**  
SoA grid keyboard shortcuts (X, O, -, Delete, Backspace) and global undo/redo (Ctrl+Z/Ctrl+Shift+Z) are undiscoverable. No keyboard shortcut reference or help panel exists.

**[F26] LOW — Version History Panel — No Close on Escape**  
`VersionHistoryPanel` is a side panel controlled by `isOpen/onClose` but there's no Escape key handler to close it.

---

## 7. Responsive Design & Layout

### 7.1 GOOD
- Responsive grid layouts (`grid md:grid-cols-2 lg:grid-cols-4`)
- Home page and protocols list adapt well to mobile
- DiffView sidebar transitions from inline to sticky on large screens

### 7.2 FINDINGS

**[F27] MEDIUM — Tab Navigation Overflows on Smaller Screens**  
The tab bar uses `min-w-max` which prevents wrapping. On screens < 1200px, the 4 tab groups extend beyond the viewport with no horizontal scroll indicator. The `overflow-visible` class prevents scroll.

**[F28] MEDIUM — SoA Grid Not Responsive**  
AG Grid renders a fixed-width table. On tablets or narrow windows, it requires horizontal scrolling but has no visual indicator (scroll shadow, fade hint). The minimum height of 500px for the Cytoscape container forces excessive scrolling on mobile.

**[F29] LOW — Footer Version Hardcoded**  
`page.tsx:119`: `Protocol2USDM v7.2.0` is hardcoded. Should read from `package.json` or environment variable for consistency during releases.

---

## 8. Code Quality & Architecture Patterns

### 8.1 GOOD
- Clean component decomposition — each view is self-contained
- Proper use of `useMemo` for expensive computations (SoA table model, filtered models)
- `useCallback` for event handlers passed to child components
- TypeScript interfaces for all props and state
- Barrel exports via `index.ts` for clean imports
- Generated types from USDM schema ensure backend/frontend alignment

### 8.2 FINDINGS

**[F30] MEDIUM — ExecutionModelView is 131KB / 3600+ Lines**  
`components/timeline/ExecutionModelView.tsx` is by far the largest file. Should be decomposed into sub-components (e.g., `ExecutionModelSummary`, `ExecutionModelTable`, `ExecutionModelTimeline`).

**[F31] MEDIUM — `any` Type Usage**  
Several components use `any` types:
- `protocols/[id]/page.tsx:487-488`: `studyDesign: any; metadata: any`
- `SoAGrid.tsx:78`: `event: any` in `onCellKeyDown`
- Multiple protocol views cast USDM data with `as Record<string, unknown>` chains

The generated USDM types exist but aren't consistently used in all views. `Record<string, unknown>` should be replaced with proper types from `@/lib/types`.

**[F32] LOW — Unused Imports and Dead Code**  
- `protocols/[id]/page.tsx:55`: `UnifiedDraftControls, VersionHistoryPanel, DiffView` imported from `@/components/semantic` but `semantic/` component directory was empty in the listing (files are actually present based on imports working)
- `protocols/[id]/page.tsx:56-57`: Several imported components may not match the `semantic/index.ts` barrel
- `OverviewTab` component defined but never used (mentioned in F7)

**[F33] LOW — React Query Configured But Barely Used**  
`providers.tsx` sets up `QueryClientProvider` with a 1-minute stale time, but no component uses `useQuery` or `useMutation`. All API calls are raw `fetch()` in `useEffect`. This means no automatic caching, deduplication, or background refresh.

---

## 9. Functional Gaps & Enhancement Opportunities

**[F34] HIGH — No Dark Mode Toggle**  
The theme defines complete `.dark` CSS variables and Tailwind `darkMode: ['class']`, but there's no toggle button or system preference detection. Dark mode is completely inaccessible to users.

**[F35] MEDIUM — No Search/Filter on Most Views**  
SoA has search+filter, but other data-heavy views (Eligibility Criteria, Objectives, Interventions, Extensions, Entities) have no filtering capability. Users with large protocols must scroll through hundreds of items.

**[F36] MEDIUM — No Breadcrumb Trail**  
Protocol detail page shows a "Back" button but no breadcrumb showing the hierarchy (Home > Protocols > Protocol Name). This reduces spatial orientation per Nielsen's "Recognition rather than recall" heuristic.

**[F37] LOW — Documentation Link Returns 404**  
Home page links to `/docs` which doesn't exist. Either implement the page or remove the link.

**[F38] LOW — No Favicon or PWA Metadata**  
The app has no custom favicon, no `manifest.json`, and no PWA-ready metadata. For a professional clinical tool, branded identity matters.

---

## Priority Implementation Roadmap

### Phase 1: Critical Fixes (1-2 days)
1. **F9** — Add keyboard navigation + ARIA to `TabGroup` dropdown (or replace with Radix `DropdownMenu`)
2. **F10** — Configure AG Grid accessibility (`ensureDomOrder`, ARIA labels on custom renderers)
3. **F11** — Add `aria-live="polite"` to `ToastContainer`
4. **F19/F20** — Add toast notifications for all API failures

### Phase 2: High-Impact Improvements (2-3 days)
5. **F5** — Extract shared `AppShell` layout component
6. **F12** — Add `aria-label` to all form inputs
7. **F16** — Fix race condition in `semanticStore` dynamic import
8. **F23** — Context-aware edit mode indicator per tab
9. **F34** — Add dark mode toggle (theme already exists)
10. **F1** — Replace custom dropdowns with Radix `DropdownMenu`

### Phase 3: UX Polish (3-5 days)
11. **F6** — Consolidate tabs (reduce from 21 to ~14)
12. **F7** — Remove dead `OverviewTab` component
13. **F8** — URL-synced tab state
14. **F13** — Add secondary indicators for provenance colors
15. **F14** — Skip navigation link
16. **F17** — Migrate data fetching to React Query
17. **F25** — Keyboard shortcut help panel

### Phase 4: Code Quality (ongoing)
18. **F2** — Replace hardcoded colors with design tokens
19. **F30** — Decompose `ExecutionModelView`
20. **F31** — Replace `any` with generated USDM types
21. **F33** — Wire up React Query for all API calls

---

## Appendix: Component Inventory

### Pages (3)
| Page | File | Size | Pattern |
|------|------|------|---------|
| Home | `app/page.tsx` | 149 lines | Server component, static content |
| Protocol List | `app/protocols/page.tsx` | 149 lines | Client, `useEffect` + `fetch` |
| Protocol Detail | `app/protocols/[id]/page.tsx` | 630 lines | Client, 21 tabs, 6 stores |

### UI Primitives (9)
| Component | Source | Status |
|-----------|--------|--------|
| Button | shadcn/CVA | Clean |
| Card | shadcn | Clean |
| Badge | shadcn/CVA | Clean |
| Progress | Radix | Clean |
| HoverCard | Radix | Clean |
| TabGroup | Custom dropdown | Needs ARIA (F9) |
| Tabs | Custom context | Has ARIA |
| ToastContainer | Custom | Needs ARIA (F11) |
| ExportButton | Custom dropdown | Needs ARIA (F1) |

### Zustand Stores (6)
| Store | Middleware | Lines | Health |
|-------|-----------|-------|--------|
| protocolStore | — | 176 | Clean |
| overlayStore | Immer | 206 | Clean |
| semanticStore | Immer | 261 | Race condition (F16) |
| soaEditStore | — | 421 | Fragile Map/Set (F18) |
| editModeStore | — | 28 | Clean |
| toastStore | — | 56 | Clean |

### Protocol Views (15)
All follow consistent pattern: accept `usdm: Record<string, unknown> | null`, render Card-based layout with empty state handling.

### Interactive Components
| Component | Library | Lines | Notes |
|-----------|---------|-------|-------|
| SoAGrid | AG Grid | 411 | Keyboard shortcuts, cell editing |
| SoACellEditor | Custom | 300+ | Popup editor for cell marks |
| TimelineCanvas | Cytoscape.js | 350+ | Drag-and-drop node positioning |
| ExecutionModelView | Custom | 3600+ | Needs decomposition (F30) |
| EditableField | Custom | 307 | Inline text editing with JSON Patch |
| DiffView | Custom | 205 | Pending changes viewer |
| UnifiedDraftControls | Custom | 520 | Save/publish/discard workflow |
