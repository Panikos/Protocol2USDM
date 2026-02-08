'use client';

import { useEffect } from 'react';
import { useSemanticStore } from '@/stores/semanticStore';

/**
 * Registers global Ctrl+Z / Ctrl+Shift+Z (or Cmd on Mac) keyboard
 * shortcuts that call undo/redo on the semantic store.
 *
 * Only fires when the active element is NOT an input/textarea/contenteditable
 * to avoid interfering with native browser undo inside form fields.
 */
export function useUndoRedoShortcuts() {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      if (!mod || e.key.toLowerCase() !== 'z') return;

      // Don't intercept if user is typing in an input
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;
      if ((e.target as HTMLElement)?.isContentEditable) return;

      e.preventDefault();

      if (e.shiftKey) {
        useSemanticStore.getState().redo();
      } else {
        useSemanticStore.getState().undo();
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);
}
