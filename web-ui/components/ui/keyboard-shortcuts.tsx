'use client';

import { useEffect, useState } from 'react';
import { Keyboard, X } from 'lucide-react';
import { Button } from './button';

interface Shortcut {
  keys: string[];
  description: string;
  context?: string;
}

const SHORTCUTS: Shortcut[] = [
  { keys: ['Ctrl', 'Z'], description: 'Undo last change', context: 'Edit mode' },
  { keys: ['Ctrl', 'Shift', 'Z'], description: 'Redo last change', context: 'Edit mode' },
  { keys: ['X'], description: 'Mark cell as Required', context: 'SoA grid' },
  { keys: ['O'], description: 'Mark cell as Optional', context: 'SoA grid' },
  { keys: ['-'], description: 'Mark cell as N/A', context: 'SoA grid' },
  { keys: ['Del'], description: 'Clear cell mark', context: 'SoA grid' },
  { keys: ['Enter'], description: 'Open full cell editor', context: 'SoA grid' },
  { keys: ['Esc'], description: 'Cancel editing / close panel' },
  { keys: ['?'], description: 'Show this shortcuts panel' },
];

export function KeyboardShortcutsPanel() {
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Only trigger on ? key when not in an input
      if (e.key !== '?' || e.ctrlKey || e.metaKey) return;
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;
      if ((e.target as HTMLElement)?.isContentEditable) return;
      e.preventDefault();
      setIsOpen(prev => !prev);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsOpen(false);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <>
      <div className="fixed inset-0 z-[90] bg-black/50" onClick={() => setIsOpen(false)} />
      <div
        className="fixed z-[95] top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-popover border border-border rounded-xl shadow-2xl p-6 w-[400px] max-h-[80vh] overflow-y-auto"
        role="dialog"
        aria-label="Keyboard shortcuts"
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Keyboard className="h-5 w-5" />
            Keyboard Shortcuts
          </h2>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setIsOpen(false)}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-2">
          {SHORTCUTS.map((shortcut, i) => (
            <div key={i} className="flex items-center justify-between py-1.5">
              <div className="flex items-center gap-2">
                <span className="text-sm text-foreground">{shortcut.description}</span>
                {shortcut.context && (
                  <span className="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                    {shortcut.context}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1">
                {shortcut.keys.map((key, j) => (
                  <span key={j}>
                    <kbd className="px-1.5 py-0.5 text-xs font-mono bg-muted border border-border rounded shadow-sm">
                      {key}
                    </kbd>
                    {j < shortcut.keys.length - 1 && (
                      <span className="text-muted-foreground mx-0.5">+</span>
                    )}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>

        <p className="text-xs text-muted-foreground mt-4 pt-3 border-t">
          Press <kbd className="px-1 py-0.5 text-[10px] font-mono bg-muted border rounded">?</kbd> to toggle this panel
        </p>
      </div>
    </>
  );
}

export default KeyboardShortcutsPanel;
