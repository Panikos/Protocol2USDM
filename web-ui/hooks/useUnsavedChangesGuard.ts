'use client';

import { useEffect } from 'react';
import { useSemanticStore, selectHasSemanticDraft } from '@/stores/semanticStore';

/**
 * Warns the user before leaving the page if there are unsaved semantic draft changes.
 * Attaches a `beforeunload` handler that triggers the browser's native
 * "You have unsaved changes" dialog.
 */
export function useUnsavedChangesGuard() {
  const hasDraft = useSemanticStore(selectHasSemanticDraft);
  const isDirty = useSemanticStore((s) => s.isDirty);

  useEffect(() => {
    if (!hasDraft && !isDirty) return;

    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      // Modern browsers ignore custom messages but still show a generic dialog
      e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
      return e.returnValue;
    };

    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [hasDraft, isDirty]);
}
