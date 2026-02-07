'use client';

/**
 * Hook to get USDM with semantic draft patches applied.
 * 
 * This hook combines the raw USDM from protocolStore with any
 * pending semantic patches from semanticStore, returning a
 * patched version that reflects draft changes.
 * 
 * All views that need to show draft changes should use this hook
 * instead of reading directly from protocolStore.
 */

import { useMemo } from 'react';
import { useProtocolStore, getPatchedUsdm, getStudyDesignFromPatched } from '@/stores/protocolStore';
import { useSemanticStore, selectPatchOperations } from '@/stores/semanticStore';
import type { USDMDocument, USDMStudyDesign } from '@/stores/protocolStore';

/**
 * Get the USDM document with semantic draft patches applied.
 * Returns the patched USDM or the original if no patches exist.
 */
export function usePatchedUsdm(): USDMDocument | null {
  const rawUsdm = useProtocolStore(state => state.usdm);
  const patch = useSemanticStore(selectPatchOperations);

  return useMemo(() => {
    return getPatchedUsdm(rawUsdm, patch);
  }, [rawUsdm, patch]);
}

/**
 * Get the study design from the patched USDM.
 * This is a convenience hook that extracts the first study design
 * from the patched USDM document.
 */
export function usePatchedStudyDesign(): USDMStudyDesign | null {
  const patchedUsdm = usePatchedUsdm();

  return useMemo(() => {
    return getStudyDesignFromPatched(patchedUsdm);
  }, [patchedUsdm]);
}

/**
 * Check if there are any semantic patches that would change the USDM.
 */
export function useHasSemanticPatches(): boolean {
  const patch = useSemanticStore(selectPatchOperations);
  return patch.length > 0;
}
