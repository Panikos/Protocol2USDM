import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import type { SemanticDraft, JsonPatchOp, PublishResponse } from '@/lib/semantic/schema';
import { useProtocolStore } from '@/stores/protocolStore';
import { getCurrentUsername } from '@/hooks/useUserIdentity';

// Lazy getter to avoid circular dependency — resolves synchronously after first call
function getResetSoAEditStore(): () => void {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const { useSoAEditStore } = require('@/stores/soaEditStore');
  return () => useSoAEditStore.getState().reset();
}

// Max undo history entries to avoid unbounded memory growth
const MAX_UNDO_HISTORY = 100;

// SessionStorage persistence for undo/redo stacks
const UNDO_STORAGE_KEY = 'protocol2usdm_undo_state';

interface PersistedUndoState {
  protocolId: string;
  undoStack: JsonPatchOp[][];
  redoStack: JsonPatchOp[][];
}

function persistUndoState(protocolId: string | null, undoStack: JsonPatchOp[][], redoStack: JsonPatchOp[][]) {
  if (!protocolId) return;
  try {
    const data: PersistedUndoState = { protocolId, undoStack, redoStack };
    sessionStorage.setItem(UNDO_STORAGE_KEY, JSON.stringify(data));
  } catch { /* sessionStorage unavailable or quota exceeded */ }
}

function restoreUndoState(protocolId: string): { undoStack: JsonPatchOp[][]; redoStack: JsonPatchOp[][] } | null {
  try {
    const raw = sessionStorage.getItem(UNDO_STORAGE_KEY);
    if (!raw) return null;
    const data: PersistedUndoState = JSON.parse(raw);
    if (data.protocolId !== protocolId) return null;
    return { undoStack: data.undoStack, redoStack: data.redoStack };
  } catch { return null; }
}

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
            updatedBy: getCurrentUsername(),
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
      try { getResetSoAEditStore()(); } catch (_) { /* store not yet loaded */ }
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
      try { getResetSoAEditStore()(); } catch (_) { /* store not yet loaded */ }
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
      try { getResetSoAEditStore()(); } catch (_) { /* store not yet loaded */ }
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

// Persist undo/redo stacks to sessionStorage on change (debounced)
let _persistTimer: ReturnType<typeof setTimeout> | null = null;
useSemanticStore.subscribe((state, prevState) => {
  if (state.undoStack !== prevState.undoStack || state.redoStack !== prevState.redoStack) {
    if (_persistTimer) clearTimeout(_persistTimer);
    _persistTimer = setTimeout(() => {
      persistUndoState(state.protocolId, state.undoStack, state.redoStack);
    }, 500);
  }
});

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
