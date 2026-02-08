import { create } from 'zustand';

interface EditModeState {
  /** Whether the UI is in edit mode (true) or read-only view mode (false) */
  isEditMode: boolean;

  /** Toggle edit mode on/off */
  toggleEditMode: () => void;

  /** Explicitly set edit mode */
  setEditMode: (enabled: boolean) => void;
}

export const useEditModeStore = create<EditModeState>()((set) => ({
  isEditMode: false,

  toggleEditMode: () => {
    set((state) => ({ isEditMode: !state.isEditMode }));
  },

  setEditMode: (enabled) => {
    set({ isEditMode: enabled });
  },
}));

// Selectors
export const selectIsEditMode = (state: EditModeState) => state.isEditMode;
