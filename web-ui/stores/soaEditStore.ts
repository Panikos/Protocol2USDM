/**
 * SoA Edit Store - Zustand store for Schedule of Activities editing state
 * 
 * All edits are pushed to semanticStore immediately (no staging/commit flow).
 * This store tracks:
 * - Committed cell edits (visual indicators until publish/discard)
 * - User-edited cell tracking
 * - Activity/encounter name edits
 */

import { create } from 'zustand';
import { SoAProcessor, type CellMark, type SoACellEdit, type SoANewActivity, type SoANewEncounter, cellKey, parseCellKey } from '@/lib/soa/processor';
import { useSemanticStore } from './semanticStore';
import { useProtocolStore } from './protocolStore';
import { getExtBoolean } from '@/lib/extensions';

// ============================================================================
// Types
// ============================================================================

interface PendingCellEdit {
  activityId: string;
  encounterId: string;
  mark: CellMark;
  footnoteRefs: string[];
  editedAt: string;
}

interface SoAEditState {
  // Committed edits (added to semantic store, visible until publish/discard)
  committedCellEdits: Map<string, PendingCellEdit>;
  
  // User-edited cells (committed and persisted)
  userEditedCells: Set<string>;
  
  // Activity/encounter name edits
  pendingActivityNameEdits: Map<string, string>; // activityId -> new name
  pendingEncounterNameEdits: Map<string, string>; // encounterId -> new name
  
  // UI state
  selectedCellKey: string | null;
  isEditingCell: boolean;
  editingActivityId: string | null;
  editingEncounterId: string | null;
  
  // Status
  isDirty: boolean;
  lastError: string | null;
}

interface SoAEditActions {
  // Cell editing
  setCellMark: (activityId: string, encounterId: string, mark: CellMark, footnoteRefs?: string[]) => void;
  clearCell: (activityId: string, encounterId: string) => void;
  selectCell: (activityId: string, encounterId: string) => void;
  deselectCell: () => void;
  
  // Activity editing
  setActivityName: (activityId: string, name: string) => void;
  addActivity: (newActivity: SoANewActivity) => string | null;
  
  // Encounter editing
  setEncounterName: (encounterId: string, name: string) => void;
  addEncounter: (newEncounter: SoANewEncounter) => string | null;
  
  // Discard all edits
  discardChanges: () => void;
  
  // Load user-edited cells from USDM
  loadUserEditedCells: (usdm: Record<string, unknown>) => void;
  
  // Check if cell is user-edited
  isUserEdited: (activityId: string, encounterId: string) => boolean;
  
  // Get pending mark for a cell
  getPendingMark: (activityId: string, encounterId: string) => PendingCellEdit | null;
  
  // Reset
  reset: () => void;
}

type SoAEditStore = SoAEditState & SoAEditActions;

// ============================================================================
// Initial State
// ============================================================================

const initialState: SoAEditState = {
  committedCellEdits: new Map(),
  userEditedCells: new Set(),
  pendingActivityNameEdits: new Map(),
  pendingEncounterNameEdits: new Map(),
  selectedCellKey: null,
  isEditingCell: false,
  editingActivityId: null,
  editingEncounterId: null,
  isDirty: false,
  lastError: null,
};

// ============================================================================
// Store
// ============================================================================

export const useSoAEditStore = create<SoAEditStore>((set, get) => ({
  ...initialState,

  // ============================================================================
  // Cell Editing
  // ============================================================================

  setCellMark: (activityId, encounterId, mark, footnoteRefs = []) => {
    const key = cellKey(activityId, encounterId);
    const usdm = useProtocolStore.getState().usdm;
    
    if (!usdm) {
      set({ lastError: 'No USDM data available' });
      return;
    }

    // Generate patch immediately and add to semantic store
    const processor = new SoAProcessor(usdm as Record<string, unknown>);
    processor.editCell({ activityId, encounterId, mark, footnoteRefs });
    const result = processor.getResult();

    if (result.errors.length > 0) {
      set({ lastError: result.errors.join('; ') });
      return;
    }

    // Add patches to semantic store as a single undoable group
    const semanticStore = useSemanticStore.getState();
    semanticStore.beginGroup();
    for (const patch of result.patches) {
      semanticStore.addPatchOp(patch);
    }
    semanticStore.endGroup();

    // Track edit visually in committedCellEdits
    set(state => {
      const newCommitted = new Map(state.committedCellEdits);
      newCommitted.set(key, {
        activityId,
        encounterId,
        mark,
        footnoteRefs,
        editedAt: new Date().toISOString(),
      });
      return {
        committedCellEdits: newCommitted,
        userEditedCells: new Set([...state.userEditedCells, key]),
        lastError: null,
      };
    });
  },

  clearCell: (activityId, encounterId) => {
    const key = cellKey(activityId, encounterId);
    const usdm = useProtocolStore.getState().usdm;
    
    if (!usdm) {
      set({ lastError: 'No USDM data available' });
      return;
    }

    // Generate patch immediately and add to semantic store
    const processor = new SoAProcessor(usdm as Record<string, unknown>);
    processor.editCell({ activityId, encounterId, mark: 'clear', footnoteRefs: [] });
    const result = processor.getResult();

    if (result.errors.length > 0) {
      set({ lastError: result.errors.join('; ') });
      return;
    }

    // Add patches to semantic store as a single undoable group
    const semanticStore = useSemanticStore.getState();
    semanticStore.beginGroup();
    for (const patch of result.patches) {
      semanticStore.addPatchOp(patch);
    }
    semanticStore.endGroup();

    // Track edit visually
    set(state => {
      const newCommitted = new Map(state.committedCellEdits);
      newCommitted.set(key, {
        activityId,
        encounterId,
        mark: 'clear',
        footnoteRefs: [],
        editedAt: new Date().toISOString(),
      });
      return {
        committedCellEdits: newCommitted,
        userEditedCells: new Set([...state.userEditedCells, key]),
        lastError: null,
      };
    });
  },

  selectCell: (activityId, encounterId) => {
    set({
      selectedCellKey: cellKey(activityId, encounterId),
      isEditingCell: true,
    });
  },

  deselectCell: () => {
    set({
      selectedCellKey: null,
      isEditingCell: false,
    });
  },

  // ============================================================================
  // Activity Editing
  // ============================================================================

  setActivityName: (activityId, name) => {
    const usdm = useProtocolStore.getState().usdm;
    if (!usdm) {
      set({ lastError: 'No USDM data available' });
      return;
    }

    // Generate patch and push to semantic store immediately
    const processor = new SoAProcessor(usdm as Record<string, unknown>);
    processor.editActivity({ activityId, name });
    const result = processor.getResult();

    if (result.errors.length > 0) {
      set({ lastError: result.errors.join('; ') });
      return;
    }

    const semanticStore = useSemanticStore.getState();
    for (const patch of result.patches) {
      semanticStore.addPatchOp(patch);
    }

    set(state => {
      const newEdits = new Map(state.pendingActivityNameEdits);
      newEdits.set(activityId, name);
      return {
        pendingActivityNameEdits: newEdits,
        lastError: null,
      };
    });
  },

  addActivity: (newActivity) => {
    const usdm = useProtocolStore.getState().usdm;
    if (!usdm) {
      set({ lastError: 'No USDM data available' });
      return null;
    }

    const processor = new SoAProcessor(usdm as Record<string, unknown>);
    const activityId = processor.addActivity(newActivity);
    const result = processor.getResult();

    if (result.errors.length > 0) {
      set({ lastError: result.errors.join('; ') });
      return null;
    }

    const semanticStore = useSemanticStore.getState();
    semanticStore.beginGroup();
    for (const patch of result.patches) {
      semanticStore.addPatchOp(patch);
    }
    semanticStore.endGroup();

    set({ lastError: null, isDirty: true });
    return activityId;
  },

  // ============================================================================
  // Encounter Editing
  // ============================================================================

  setEncounterName: (encounterId, name) => {
    const usdm = useProtocolStore.getState().usdm;
    if (!usdm) {
      set({ lastError: 'No USDM data available' });
      return;
    }

    // Generate patch and push to semantic store immediately
    const processor = new SoAProcessor(usdm as Record<string, unknown>);
    processor.editEncounter({ encounterId, name });
    const result = processor.getResult();

    if (result.errors.length > 0) {
      set({ lastError: result.errors.join('; ') });
      return;
    }

    const semanticStore = useSemanticStore.getState();
    for (const patch of result.patches) {
      semanticStore.addPatchOp(patch);
    }

    set(state => {
      const newEdits = new Map(state.pendingEncounterNameEdits);
      newEdits.set(encounterId, name);
      return {
        pendingEncounterNameEdits: newEdits,
        lastError: null,
      };
    });
  },

  addEncounter: (newEncounter) => {
    const usdm = useProtocolStore.getState().usdm;
    if (!usdm) {
      set({ lastError: 'No USDM data available' });
      return null;
    }

    const processor = new SoAProcessor(usdm as Record<string, unknown>);
    const encounterId = processor.addEncounter(newEncounter);
    const result = processor.getResult();

    if (result.errors.length > 0) {
      set({ lastError: result.errors.join('; ') });
      return null;
    }

    const semanticStore = useSemanticStore.getState();
    semanticStore.beginGroup();
    for (const patch of result.patches) {
      semanticStore.addPatchOp(patch);
    }
    semanticStore.endGroup();

    set({ lastError: null, isDirty: true });
    return encounterId;
  },

  discardChanges: () => {
    // Also clear the semantic store draft patches
    const semanticStore = useSemanticStore.getState();
    semanticStore.clearPatch();
    
    set({
      committedCellEdits: new Map(),
      pendingActivityNameEdits: new Map(),
      pendingEncounterNameEdits: new Map(),
      isDirty: false,
      lastError: null,
      selectedCellKey: null,
      isEditingCell: false,
    });
  },

  // ============================================================================
  // Load User-Edited Cells
  // ============================================================================

  loadUserEditedCells: (usdm) => {
    const userEdited = new Set<string>();
    
    const study = usdm.study as Record<string, unknown> | undefined;
    const versions = study?.versions as unknown[] | undefined;
    const version = versions?.[0] as Record<string, unknown> | undefined;
    const studyDesigns = version?.studyDesigns as Record<string, unknown>[] | undefined;
    const studyDesign = studyDesigns?.[0];

    if (!studyDesign) {
      set({ userEditedCells: userEdited });
      return;
    }

    const timelines = (studyDesign.scheduleTimelines as Array<{
      instances?: Array<{
        activityIds?: string[];
        encounterId?: string;
        extensionAttributes?: unknown[];
      }>;
    }>) ?? [];

    for (const timeline of timelines) {
      for (const instance of timeline.instances ?? []) {
        const encId = instance.encounterId;
        if (!encId) continue;

        if (getExtBoolean(instance.extensionAttributes, 'userEdited') === true) {
          for (const actId of instance.activityIds ?? []) {
            userEdited.add(cellKey(actId, encId));
          }
        }
      }
    }

    set({ userEditedCells: userEdited });
  },

  // ============================================================================
  // Utility Methods
  // ============================================================================

  isUserEdited: (activityId, encounterId) => {
    const state = get();
    const key = cellKey(activityId, encounterId);
    return state.userEditedCells.has(key) || state.committedCellEdits.has(key);
  },

  getPendingMark: (activityId, encounterId) => {
    const key = cellKey(activityId, encounterId);
    return get().committedCellEdits.get(key) ?? null;
  },

  reset: () => {
    set(initialState);
  },
}));

export default useSoAEditStore;
