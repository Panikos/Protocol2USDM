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

// Max undo history entries to avoid unbounded memory growth
const MAX_UNDO_HISTORY = 100;

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
  
  // Undo/redo stacks — each entry is a snapshot of draft.patch at that point
  undoStack: JsonPatchOp[][];
  redoStack: JsonPatchOp[][];
  // When > 0, ops are being grouped and won't push individual undo entries
  _groupDepth: number;
  _groupStartPatch: JsonPatchOp[] | null;
  
  // Actions
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  
  loadDraft: (protocolId: string, usdmRevision: string, draft: SemanticDraft | null) => void;
  
  addPatchOp: (op: JsonPatchOp) => void;
  removePatchOp: (index: number) => void;
  clearPatch: () => void;
  
  // Undo/redo
  undo: () => void;
  redo: () => void;
  beginGroup: () => void;
  endGroup: () => void;
  
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
    undoStack: [],
    redoStack: [],
    _groupDepth: 0,
    _groupStartPatch: null,

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
        // Snapshot current patch for undo (only if not inside a group)
        if (state._groupDepth === 0 && state.draft?.patch) {
          state.undoStack.push([...state.draft.patch]);
          if (state.undoStack.length > MAX_UNDO_HISTORY) {
            state.undoStack.shift();
          }
          // New action clears redo
          state.redoStack = [];
        }

        if (!state.draft) {
          // Create new draft if none exists
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
          // If this is the first op and not in a group, snapshot empty state for undo
          if (state._groupDepth === 0) {
            state.undoStack.push([]);
            if (state.undoStack.length > MAX_UNDO_HISTORY) {
              state.undoStack.shift();
            }
            state.redoStack = [];
          }
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
        // Snapshot for undo
        if (state._groupDepth === 0) {
          state.undoStack.push([...state.draft.patch]);
          if (state.undoStack.length > MAX_UNDO_HISTORY) state.undoStack.shift();
          state.redoStack = [];
        }
        state.draft.patch.splice(index, 1);
        state.draft.updatedAt = new Date().toISOString();
        state.isDirty = true;
      });
    },

    clearPatch: () => {
      set((state) => {
        if (!state.draft) return;
        // Snapshot for undo
        state.undoStack.push([...state.draft.patch]);
        if (state.undoStack.length > MAX_UNDO_HISTORY) state.undoStack.shift();
        state.redoStack = [];
        state.draft.patch = [];
        state.draft.updatedAt = new Date().toISOString();
        state.isDirty = true;
      });
      // Also clear SoA visual tracking synchronously
      if (resetSoAEditStore) resetSoAEditStore();
    },

    undo: () => {
      set((state) => {
        if (state.undoStack.length === 0 || !state.draft) return;
        // Push current state to redo
        state.redoStack.push([...state.draft.patch]);
        // Restore previous state
        const previousPatch = state.undoStack.pop()!;
        state.draft.patch = previousPatch;
        state.draft.updatedAt = new Date().toISOString();
        state.isDirty = true;
      });
      // Reset SoA visual tracking so it re-derives from the restored patch state
      if (resetSoAEditStore) resetSoAEditStore();
    },

    redo: () => {
      set((state) => {
        if (state.redoStack.length === 0 || !state.draft) return;
        // Push current state to undo
        state.undoStack.push([...state.draft.patch]);
        // Restore next state
        const nextPatch = state.redoStack.pop()!;
        state.draft.patch = nextPatch;
        state.draft.updatedAt = new Date().toISOString();
        state.isDirty = true;
      });
      // Reset SoA visual tracking so it re-derives from the restored patch state
      if (resetSoAEditStore) resetSoAEditStore();
    },

    beginGroup: () => {
      set((state) => {
        if (state._groupDepth === 0) {
          // Snapshot patch at group start for undo
          state._groupStartPatch = state.draft?.patch ? [...state.draft.patch] : [];
        }
        state._groupDepth += 1;
      });
    },

    endGroup: () => {
      set((state) => {
        state._groupDepth = Math.max(0, state._groupDepth - 1);
        if (state._groupDepth === 0 && state._groupStartPatch !== null) {
          // Push the group-start snapshot as a single undo entry
          state.undoStack.push(state._groupStartPatch);
          if (state.undoStack.length > MAX_UNDO_HISTORY) state.undoStack.shift();
          state.redoStack = [];
          state._groupStartPatch = null;
        }
      });
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
        state.undoStack = [];
        state.redoStack = [];
        state._groupDepth = 0;
        state._groupStartPatch = null;
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

export const selectCanUndo = (state: SemanticState) => state.undoStack.length > 0;
export const selectCanRedo = (state: SemanticState) => state.redoStack.length > 0;

// Stable empty array to avoid infinite loops in React 18+ with Zustand
const EMPTY_PATCH: JsonPatchOp[] = [];
export const selectPatchOperations = (state: SemanticState) => 
  state.draft?.patch ?? EMPTY_PATCH;
