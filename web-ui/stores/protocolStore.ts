import { create } from 'zustand';
import { applySemanticPatch } from '@/lib/semantic/patcher';
import type { JsonPatchOp } from '@/lib/semantic/schema';

// USDM types — generated from dataStructure.yml via scripts/generate_ts_types.py
// Runtime-safe variants (Partial + index signatures) from the barrel
import type {
  USDMStudy,
  USDMStudyVersion,
  USDMStudyDesign,
  USDMActivity,
  USDMActivityGroup,
  USDMEncounter,
  USDMEpoch,
  USDMArm,
  USDMScheduleTimeline,
  USDMScheduledInstance,
  USDMTiming,
  USDMDocument,
} from '@/lib/types';

export type {
  USDMStudy,
  USDMStudyVersion,
  USDMStudyDesign,
  USDMActivity,
  USDMActivityGroup,
  USDMEncounter,
  USDMEpoch,
  USDMArm,
  USDMScheduleTimeline,
  USDMScheduledInstance,
  USDMTiming,
  USDMDocument,
};

// Protocol metadata
export interface ProtocolMetadata {
  id: string;
  name: string;
  revision: string;
  generatedAt: string;
  generator: string;
  usdmVersion: string;
}

interface ProtocolState {
  // Current protocol
  currentProtocolId: string | null;
  usdm: USDMDocument | null;
  revision: string | null;
  metadata: ProtocolMetadata | null;
  
  // Loading state
  isLoading: boolean;
  error: string | null;
  
  // Actions
  setProtocol: (protocolId: string, usdm: USDMDocument, revision: string) => void;
  clearProtocol: () => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useProtocolStore = create<ProtocolState>()((set) => ({
  currentProtocolId: null,
  usdm: null,
  revision: null,
  metadata: null,
  isLoading: false,
  error: null,

  setProtocol: (protocolId, usdm, revision) => {
    const metadata: ProtocolMetadata = {
      id: protocolId,
      name: protocolId, // Can be enhanced with actual name
      revision,
      generatedAt: usdm.generatedAt,
      generator: usdm.generator,
      usdmVersion: usdm.usdmVersion,
    };

    set({
      currentProtocolId: protocolId,
      usdm,
      revision,
      metadata,
      isLoading: false,
      error: null,
    });
  },

  clearProtocol: () => {
    set({
      currentProtocolId: null,
      usdm: null,
      revision: null,
      metadata: null,
      error: null,
    });
  },

  setLoading: (loading) => {
    set({ isLoading: loading });
  },

  setError: (error) => {
    set({ error, isLoading: false });
  },
}));

// Selectors
export const selectStudyDesign = (state: ProtocolState): USDMStudyDesign | null => {
  if (!state.usdm?.study?.versions?.[0]?.studyDesigns?.[0]) return null;
  return state.usdm.study.versions[0].studyDesigns[0];
};

// Get raw USDM (without patches)
export const selectRawUsdm = (state: ProtocolState): USDMDocument | null => state.usdm;

/**
 * Apply semantic patches to USDM and return the patched version.
 * This should be used by all views that need to show draft changes.
 * 
 * @param usdm - The raw USDM document
 * @param patch - The semantic draft patch operations
 * @returns The patched USDM document, or original if patching fails
 */
export function getPatchedUsdm(
  usdm: USDMDocument | null,
  patch: JsonPatchOp[] | undefined
): USDMDocument | null {
  if (!usdm) return null;
  if (!patch || patch.length === 0) return usdm;

  const result = applySemanticPatch(usdm, patch);
  if (result.success) {
    return result.result as USDMDocument;
  }
  
  // Log error but return original to avoid breaking UI
  console.warn('Failed to apply semantic patch:', result.error);
  return usdm;
}

/**
 * Get study design from patched USDM.
 * Use this when you need to show draft changes.
 */
export function getStudyDesignFromPatched(
  patchedUsdm: USDMDocument | null
): USDMStudyDesign | null {
  if (!patchedUsdm?.study?.versions?.[0]?.studyDesigns?.[0]) return null;
  return patchedUsdm.study.versions[0].studyDesigns[0];
}

export const selectActivities = (state: ProtocolState): USDMActivity[] => {
  const design = selectStudyDesign(state);
  return design?.activities ?? [];
};

export const selectEncounters = (state: ProtocolState): USDMEncounter[] => {
  const design = selectStudyDesign(state);
  return design?.encounters ?? [];
};

export const selectEpochs = (state: ProtocolState): USDMEpoch[] => {
  const design = selectStudyDesign(state);
  return design?.epochs ?? [];
};

export const selectScheduleTimelines = (state: ProtocolState): USDMScheduleTimeline[] => {
  const design = selectStudyDesign(state);
  return design?.scheduleTimelines ?? [];
};
