/**
 * SoA Edit Store - Zustand store for Schedule of Activities editing state
 * 
 * Manages:
 * - Pending cell edits before committing to semantic store
 * - User-edited cell tracking for visual indicators
 * - Activity/encounter additions pending commit
 * - Integration with SoAProcessor and SemanticStore
 */

import { create } from 'zustand';
import { SoAProcessor, type CellMark, type SoACellEdit, cellKey, parseCellKey } from '@/lib/soa/processor';
import { useSemanticStore } from './semanticStore';
import { useProtocolStore } from './protocolStore';

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

interface PendingActivityAdd {
  tempId: string;
  name: string;
  label?: string;
  groupId?: string;
  insertAfter?: string;
}

interface PendingEncounterAdd {
  tempId: string;
  name: string;
  epochId: string;
  timing?: string;
  insertAfter?: string;
}

interface SoAEditState {
  // Pending edits (not yet committed to semantic store)
  pendingCellEdits: Map<string, PendingCellEdit>; // key: "activityId|encounterId"
  pendingActivityAdds: PendingActivityAdd[];
  pendingEncounterAdds: PendingEncounterAdd[];
  
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
  addActivity: (name: string, groupId?: string, insertAfter?: string) => string;
  
  // Encounter editing
  setEncounterName: (encounterId: string, name: string) => void;
  addEncounter: (name: string, epochId: string, timing?: string, insertAfter?: string) => string;
  
  // Commit changes to semantic store
  commitChanges: () => Promise<{ success: boolean; errors: string[] }>;
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
  pendingCellEdits: new Map(),
  pendingActivityAdds: [],
  pendingEncounterAdds: [],
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

    // Add patches to semantic store (like EditableField does)
    const semanticStore = useSemanticStore.getState();
    for (const patch of result.patches) {
      semanticStore.addPatchOp(patch);
    }

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

    // Add patches to semantic store
    const semanticStore = useSemanticStore.getState();
    for (const patch of result.patches) {
      semanticStore.addPatchOp(patch);
    }

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

  addActivity: (name, groupId, insertAfter) => {
    const tempId = `temp_activity_${Date.now()}`;
    set(state => ({
      pendingActivityAdds: [
        ...state.pendingActivityAdds,
        { tempId, name, groupId, insertAfter },
      ],
      isDirty: true,
      lastError: null,
    }));
    return tempId;
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

  addEncounter: (name, epochId, timing, insertAfter) => {
    const tempId = `temp_encounter_${Date.now()}`;
    set(state => ({
      pendingEncounterAdds: [
        ...state.pendingEncounterAdds,
        { tempId, name, epochId, timing, insertAfter },
      ],
      isDirty: true,
      lastError: null,
    }));
    return tempId;
  },

  // ============================================================================
  // Commit Changes
  // ============================================================================

  commitChanges: async () => {
    const state = get();
    const usdm = useProtocolStore.getState().usdm;
    
    if (!usdm) {
      return { success: false, errors: ['No USDM data available'] };
    }

    const processor = new SoAProcessor(usdm as Record<string, unknown>);
    const errors: string[] = [];

    // Process cell edits
    for (const [, edit] of state.pendingCellEdits) {
      processor.editCell({
        activityId: edit.activityId,
        encounterId: edit.encounterId,
        mark: edit.mark,
        footnoteRefs: edit.footnoteRefs,
      });
    }

    // Process activity name edits
    for (const [activityId, name] of state.pendingActivityNameEdits) {
      processor.editActivity({ activityId, name });
    }

    // Process encounter name edits
    for (const [encounterId, name] of state.pendingEncounterNameEdits) {
      processor.editEncounter({ encounterId, name });
    }

    // Process new activities
    for (const add of state.pendingActivityAdds) {
      processor.addActivity({
        name: add.name,
        label: add.label,
        groupId: add.groupId,
        insertAfter: add.insertAfter,
      });
    }

    // Process new encounters
    for (const add of state.pendingEncounterAdds) {
      processor.addEncounter({
        name: add.name,
        epochId: add.epochId,
        timing: add.timing,
        insertAfter: add.insertAfter,
      });
    }

    const result = processor.getResult();
    
    if (result.errors.length > 0) {
      errors.push(...result.errors);
    }

    if (result.warnings.length > 0) {
      console.warn('SoA Edit Warnings:', result.warnings);
    }

    // Add patches to semantic store
    if (result.patches.length > 0 && errors.length === 0) {
      const semanticStore = useSemanticStore.getState();
      for (const patch of result.patches) {
        semanticStore.addPatchOp(patch);
      }

      // Move pending edits to committed edits (keep visible until publish)
      set(state => {
        const newCommitted = new Map(state.committedCellEdits);
        for (const [key, edit] of state.pendingCellEdits) {
          newCommitted.set(key, edit);
        }
        return {
          userEditedCells: new Set([...state.userEditedCells, ...result.userEditedCells]),
          pendingCellEdits: new Map(),
          committedCellEdits: newCommitted,
          pendingActivityAdds: [],
          pendingEncounterAdds: [],
          pendingActivityNameEdits: new Map(),
          pendingEncounterNameEdits: new Map(),
          isDirty: false,
          lastError: null,
        };
      });

      return { success: true, errors: [] };
    }

    if (errors.length > 0) {
      set({ lastError: errors.join('; ') });
      return { success: false, errors };
    }

    return { success: true, errors: [] };
  },

  discardChanges: () => {
    // Also clear the semantic store draft patches
    const semanticStore = useSemanticStore.getState();
    semanticStore.clearPatch();
    
    set({
      pendingCellEdits: new Map(),
      committedCellEdits: new Map(),
      pendingActivityAdds: [],
      pendingEncounterAdds: [],
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
        extensionAttributes?: Array<{ url?: string; valueString?: string }>;
      }>;
    }>) ?? [];

    for (const timeline of timelines) {
      for (const instance of timeline.instances ?? []) {
        const encId = instance.encounterId;
        if (!encId) continue;

        // Check for user-edited extension
        let isEdited = false;
        for (const ext of instance.extensionAttributes ?? []) {
          if (ext.url?.includes('x-userEdited') && ext.valueString === 'true') {
            isEdited = true;
            break;
          }
        }

        if (isEdited) {
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
    return state.userEditedCells.has(key) || state.pendingCellEdits.has(key);
  },

  getPendingMark: (activityId, encounterId) => {
    const key = cellKey(activityId, encounterId);
    return get().pendingCellEdits.get(key) ?? null;
  },

  reset: () => {
    set(initialState);
  },
}));

export default useSoAEditStore;
