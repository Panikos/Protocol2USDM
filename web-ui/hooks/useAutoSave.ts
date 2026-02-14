'use client';

import { useEffect, useRef, useCallback } from 'react';
import { useSemanticStore } from '@/stores/semanticStore';
import { useOverlayStore } from '@/stores/overlayStore';
import { getCurrentUsername } from '@/hooks/useUserIdentity';

const AUTO_SAVE_INTERVAL_MS = 30_000; // 30 seconds
const DEBOUNCE_MS = 2_000; // 2 second debounce after edit

/**
 * Auto-save hook: saves semantic + overlay drafts every 30s and on tab blur.
 * Only fires when there are unsaved changes (isDirty).
 */
export function useAutoSave(protocolId: string | null) {
  const lastSaveRef = useRef<number>(0);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const saveDraft = useCallback(async () => {
    if (!protocolId) return;

    const semanticState = useSemanticStore.getState();
    const overlayState = useOverlayStore.getState();

    // Only save if there are unsaved changes
    if (!semanticState.isDirty && !overlayState.isDirty) return;

    const now = Date.now();
    // Debounce: don't save if we saved very recently
    if (now - lastSaveRef.current < DEBOUNCE_MS) return;
    lastSaveRef.current = now;

    // Save semantic draft
    if (semanticState.isDirty && semanticState.draft && semanticState.draft.patch.length > 0) {
      try {
        const response = await fetch(`/api/protocols/${protocolId}/semantic/draft`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            protocolId,
            usdmRevision: semanticState.usdmRevision ?? semanticState.draft.usdmRevision,
            updatedBy: getCurrentUsername(),
            patch: semanticState.draft.patch,
          }),
        });
        if (response.ok) {
          useSemanticStore.getState().markClean();
        }
      } catch {
        // Silent failure for auto-save — user can still manually save
      }
    }
  }, [protocolId]);

  // Interval-based auto-save (every 30s)
  useEffect(() => {
    if (!protocolId) return;

    const interval = setInterval(saveDraft, AUTO_SAVE_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [protocolId, saveDraft]);

  // Save on tab blur (visibility change)
  useEffect(() => {
    if (!protocolId) return;

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        saveDraft();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [protocolId, saveDraft]);

  // Save on beforeunload (page close/refresh)
  useEffect(() => {
    if (!protocolId) return;

    const handleBeforeUnload = () => {
      // Use sendBeacon for reliability on page close
      const semanticState = useSemanticStore.getState();
      if (semanticState.isDirty && semanticState.draft && semanticState.draft.patch.length > 0) {
        const body = JSON.stringify({
          protocolId,
          usdmRevision: semanticState.usdmRevision ?? semanticState.draft.usdmRevision,
          updatedBy: getCurrentUsername(),
          patch: semanticState.draft.patch,
        });
        navigator.sendBeacon(
          `/api/protocols/${protocolId}/semantic/draft`,
          new Blob([body], { type: 'application/json' })
        );
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [protocolId]);

  return { saveDraft };
}
