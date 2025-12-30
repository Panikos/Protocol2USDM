import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import type { OverlayDoc, OverlayPayload } from '@/lib/overlay/schema';
import { createEmptyOverlay } from '@/lib/overlay/schema';

interface OverlayState {
  // Data
  published: OverlayDoc | null;
  draft: OverlayDoc | null;
  isDirty: boolean;
  isLoading: boolean;
  error: string | null;

  // USDM revision tracking
  currentUsdmRevision: string | null;
  overlayUsdmRevision: string | null;
  needsReconciliation: boolean;

  // Actions
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  
  loadOverlays: (
    protocolId: string,
    usdmRevision: string,
    published: OverlayDoc | null,
    draft: OverlayDoc | null
  ) => void;
  
  updateDraftDiagramNode: (
    nodeId: string,
    position: { x: number; y: number }
  ) => void;
  
  updateDraftTableOrder: (
    rowOrder?: string[],
    columnOrder?: string[]
  ) => void;
  
  lockNode: (nodeId: string, locked: boolean) => void;
  highlightNode: (nodeId: string, highlight: boolean) => void;
  
  setSnapGrid: (snapGrid: number) => void;
  
  markClean: () => void;
  resetToPublished: () => void;
  
  promoteDraftToPublished: () => void;
}

export const useOverlayStore = create<OverlayState>()(
  immer((set, get) => ({
    // Initial state
    published: null,
    draft: null,
    isDirty: false,
    isLoading: false,
    error: null,
    currentUsdmRevision: null,
    overlayUsdmRevision: null,
    needsReconciliation: false,

    setLoading: (loading) => {
      set((state) => {
        state.isLoading = loading;
      });
    },

    setError: (error) => {
      set((state) => {
        state.error = error;
      });
    },

    loadOverlays: (protocolId, usdmRevision, published, draft) => {
      set((state) => {
        state.published = published;
        state.currentUsdmRevision = usdmRevision;
        state.overlayUsdmRevision = published?.usdmRevision ?? null;
        state.needsReconciliation =
          published !== null && published.usdmRevision !== usdmRevision;

        // If no draft, create one from published or empty
        if (draft) {
          state.draft = draft;
        } else if (published) {
          state.draft = structuredClone(published);
          state.draft.status = 'draft';
        } else {
          state.draft = createEmptyOverlay(protocolId, usdmRevision, 'system');
        }

        state.isDirty = false;
        state.isLoading = false;
        state.error = null;
      });
    },

    updateDraftDiagramNode: (nodeId, position) => {
      set((state) => {
        if (!state.draft) return;

        const existing = state.draft.payload.diagram.nodes[nodeId] ?? {};
        state.draft.payload.diagram.nodes[nodeId] = {
          ...existing,
          x: position.x,
          y: position.y,
        };
        state.draft.updatedAt = new Date().toISOString();
        state.isDirty = true;
      });
    },

    updateDraftTableOrder: (rowOrder, columnOrder) => {
      set((state) => {
        if (!state.draft) return;

        if (rowOrder !== undefined) {
          state.draft.payload.table.rowOrder = rowOrder;
        }
        if (columnOrder !== undefined) {
          state.draft.payload.table.columnOrder = columnOrder;
        }
        state.draft.updatedAt = new Date().toISOString();
        state.isDirty = true;
      });
    },

    lockNode: (nodeId, locked) => {
      set((state) => {
        if (!state.draft) return;

        const existing = state.draft.payload.diagram.nodes[nodeId] ?? { x: 0, y: 0 };
        state.draft.payload.diagram.nodes[nodeId] = {
          ...existing,
          locked,
        };
        state.draft.updatedAt = new Date().toISOString();
        state.isDirty = true;
      });
    },

    highlightNode: (nodeId, highlight) => {
      set((state) => {
        if (!state.draft) return;

        const existing = state.draft.payload.diagram.nodes[nodeId] ?? { x: 0, y: 0 };
        state.draft.payload.diagram.nodes[nodeId] = {
          ...existing,
          highlight,
        };
        state.draft.updatedAt = new Date().toISOString();
        state.isDirty = true;
      });
    },

    setSnapGrid: (snapGrid) => {
      set((state) => {
        if (!state.draft) return;

        if (!state.draft.payload.diagram.globals) {
          state.draft.payload.diagram.globals = { snapGrid };
        } else {
          state.draft.payload.diagram.globals.snapGrid = snapGrid;
        }
        state.draft.updatedAt = new Date().toISOString();
        state.isDirty = true;
      });
    },

    markClean: () => {
      set((state) => {
        state.isDirty = false;
      });
    },

    resetToPublished: () => {
      set((state) => {
        if (state.published) {
          state.draft = structuredClone(state.published);
          state.draft.status = 'draft';
        }
        state.isDirty = false;
      });
    },

    promoteDraftToPublished: () => {
      set((state) => {
        if (!state.draft) return;

        state.published = structuredClone(state.draft);
        state.published.status = 'published';
        state.published.updatedAt = new Date().toISOString();
        state.isDirty = false;
      });
    },
  }))
);

// Selectors
export const selectIsDirty = (state: OverlayState) => state.isDirty;
export const selectNeedsReconciliation = (state: OverlayState) => state.needsReconciliation;
export const selectDraftPayload = (state: OverlayState) => state.draft?.payload ?? null;
export const selectSnapGrid = (state: OverlayState) =>
  state.draft?.payload.diagram.globals?.snapGrid ?? 5;
