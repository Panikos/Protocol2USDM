import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import type { SemanticDraft, JsonPatchOp, PublishResponse } from '@/lib/semantic/schema';
import { useProtocolStore } from '@/stores/protocolStore';

// Import soaEditStore reset function - we can't import the hook directly to avoid circular deps
// but we can call getState() on it after the store is created
let resetSoAEditStore: (() => void) | null = null;
import('@/stores/soaEditStore').then(({ useSoAEditStore }) => {
  resetSoAEditStore = () => useSoAEditStore.getState().reset();
});

interface SemanticState {
  // Data
  draft: SemanticDraft | null;
  isDirty: boolean;
  isLoading: boolean;
  error: string | null;
  
  // Publish results
  lastPublishResult: PublishResponse | null;
  
  // Protocol context
  protocolId: string | null;
  usdmRevision: string | null;
  
  // Actions
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  
  loadDraft: (protocolId: string, usdmRevision: string, draft: SemanticDraft | null) => void;
  
  addPatchOp: (op: JsonPatchOp) => void;
  removePatchOp: (index: number) => void;
  clearPatch: () => void;
  
  markClean: () => void;
  setPublishResult: (result: PublishResponse | null) => void;
  clearDraft: () => void;
}

export const useSemanticStore = create<SemanticState>()(
  immer((set, get) => ({
    // Initial state
    draft: null,
    isDirty: false,
    isLoading: false,
    error: null,
    lastPublishResult: null,
    protocolId: null,
    usdmRevision: null,

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

    loadDraft: (protocolId, usdmRevision, draft) => {
      set((state) => {
        state.protocolId = protocolId;
        state.usdmRevision = usdmRevision;
        state.draft = draft;
        state.isDirty = false;
        state.isLoading = false;
        state.error = null;
      });
    },

    addPatchOp: (op) => {
      set((state) => {
        if (!state.draft) {
          // Create new draft if none exists
          // Get revision from protocolStore as fallback if semanticStore not initialized yet
          const protocolRevision = useProtocolStore.getState().revision;
          const now = new Date().toISOString();
          state.draft = {
            version: 1,
            protocolId: state.protocolId ?? useProtocolStore.getState().currentProtocolId ?? '',
            usdmRevision: state.usdmRevision ?? protocolRevision ?? '',
            status: 'draft',
            createdAt: now,
            updatedAt: now,
            updatedBy: 'ui-user',
            patch: [op],
          };
        } else {
          state.draft.patch.push(op);
          state.draft.updatedAt = new Date().toISOString();
        }
        state.isDirty = true;
      });
    },

    removePatchOp: (index) => {
      set((state) => {
        if (!state.draft) return;
        state.draft.patch.splice(index, 1);
        state.draft.updatedAt = new Date().toISOString();
        state.isDirty = true;
      });
    },

    clearPatch: () => {
      set((state) => {
        if (!state.draft) return;
        state.draft.patch = [];
        state.draft.updatedAt = new Date().toISOString();
        state.isDirty = true;
      });
      // Also clear SoA visual tracking synchronously
      if (resetSoAEditStore) resetSoAEditStore();
    },

    markClean: () => {
      set((state) => {
        state.isDirty = false;
      });
    },

    setPublishResult: (result) => {
      set((state) => {
        state.lastPublishResult = result;
      });
    },

    clearDraft: () => {
      set((state) => {
        state.draft = null;
        state.isDirty = false;
      });
      // NOTE: Don't reset soaEditStore here - it should be reset AFTER USDM is reloaded
      // to avoid showing stale data. The page.tsx handleReloadUsdm handles this.
    },
  }))
);

// Selectors
export const selectSemanticIsDirty = (state: SemanticState) => state.isDirty;
export const selectSemanticDraft = (state: SemanticState) => state.draft;
export const selectHasSemanticDraft = (state: SemanticState) => 
  state.draft !== null && state.draft.patch.length > 0;

// Stable empty array to avoid infinite loops in React 18+ with Zustand
const EMPTY_PATCH: JsonPatchOp[] = [];
export const selectPatchOperations = (state: SemanticState) => 
  state.draft?.patch ?? EMPTY_PATCH;
