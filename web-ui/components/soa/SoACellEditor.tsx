'use client';

import { useState, useRef, useEffect } from 'react';
import { Check, X, Circle, Minus, Plus, Hash, Pencil } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { CellMark } from '@/lib/soa/processor';

// Mark options for the cell editor - aligned with clinical SoA conventions
const MARK_OPTIONS: { value: CellMark; label: string; icon: React.ReactNode; color: string }[] = [
  { value: 'X', label: 'Required', icon: <Check className="h-4 w-4" />, color: 'bg-green-100 text-green-700 border-green-300' },
  { value: 'Xa', label: 'Required (a)', icon: <span className="text-xs font-bold">Xᵃ</span>, color: 'bg-green-100 text-green-700 border-green-300' },
  { value: 'Xb', label: 'Required (b)', icon: <span className="text-xs font-bold">Xᵇ</span>, color: 'bg-green-100 text-green-700 border-green-300' },
  { value: 'Xc', label: 'Required (c)', icon: <span className="text-xs font-bold">Xᶜ</span>, color: 'bg-green-100 text-green-700 border-green-300' },
  { value: 'O', label: 'Optional', icon: <Circle className="h-4 w-4" />, color: 'bg-blue-100 text-blue-700 border-blue-300' },
  { value: '−', label: 'Not Applicable', icon: <Minus className="h-4 w-4" />, color: 'bg-gray-100 text-gray-600 border-gray-300' },
  { value: 'clear', label: 'Clear', icon: <X className="h-4 w-4" />, color: 'bg-red-50 text-red-600 border-red-200' },
];

interface SoACellEditorProps {
  activityId: string;
  encounterId: string;
  currentMark: CellMark;
  footnoteRefs: string[];
  availableFootnotes: string[];
  onSave: (mark: CellMark, footnoteRefs: string[]) => void;
  stopEditing: () => void;
}

export function SoACellEditor({
  currentMark,
  footnoteRefs: initialFootnotes,
  availableFootnotes,
  onSave,
  stopEditing,
}: SoACellEditorProps) {
  const [selectedMark, setSelectedMark] = useState<CellMark>(currentMark);
  const [footnotes, setFootnotes] = useState<string[]>(initialFootnotes ?? []);
  const [showFootnotePanel, setShowFootnotePanel] = useState(false);
  const [customFootnote, setCustomFootnote] = useState('');
  
  const containerRef = useRef<HTMLDivElement>(null);

  // Focus the container when opened
  useEffect(() => {
    containerRef.current?.focus();
  }, []);

  const handleMarkSelect = (mark: CellMark) => {
    setSelectedMark(mark);
  };

  const handleSave = () => {
    onSave(selectedMark, footnotes);
    stopEditing();
  };

  const handleCancel = () => {
    stopEditing();
  };

  const toggleFootnote = (fn: string) => {
    setFootnotes(prev => 
      prev.includes(fn) ? prev.filter(f => f !== fn) : [...prev, fn]
    );
  };

  const addCustomFootnote = () => {
    if (customFootnote.trim() && !footnotes.includes(customFootnote.trim())) {
      setFootnotes(prev => [...prev, customFootnote.trim()]);
      setCustomFootnote('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      handleCancel();
    } else if (e.key === 'Enter' && !showFootnotePanel) {
      handleSave();
    }
  };

  return (
    <div
      ref={containerRef}
      tabIndex={0}
      onKeyDown={handleKeyDown}
      className="bg-white border-2 border-blue-500 rounded-lg shadow-xl p-3 min-w-[280px] focus:outline-none"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3 pb-2 border-b">
        <span className="text-sm font-medium text-gray-700">Edit Cell</span>
        <div className="flex gap-1">
          <button
            onClick={() => setShowFootnotePanel(!showFootnotePanel)}
            className={cn(
              'p-1 rounded hover:bg-gray-100',
              showFootnotePanel && 'bg-blue-100 text-blue-600'
            )}
            title="Add footnotes"
          >
            <Hash className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Mark Options Grid */}
      <div className="grid grid-cols-4 gap-2 mb-3">
        {MARK_OPTIONS.map(option => (
          <button
            key={option.value ?? 'clear'}
            onClick={() => handleMarkSelect(option.value)}
            className={cn(
              'flex flex-col items-center justify-center p-2 rounded border-2 transition-all',
              option.color,
              selectedMark === option.value
                ? 'ring-2 ring-blue-500 ring-offset-1'
                : 'opacity-70 hover:opacity-100'
            )}
            title={option.label}
          >
            {option.icon}
            <span className="text-[10px] mt-1">{option.label}</span>
          </button>
        ))}
      </div>

      {/* Footnote Panel */}
      {showFootnotePanel && (
        <div className="mb-3 p-2 bg-gray-50 rounded border">
          <div className="text-xs font-medium text-gray-600 mb-2">Footnotes</div>
          
          {/* Available Footnotes */}
          {availableFootnotes.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-2">
              {availableFootnotes.map(fn => (
                <button
                  key={fn}
                  onClick={() => toggleFootnote(fn)}
                  className={cn(
                    'px-2 py-0.5 text-xs rounded border',
                    footnotes.includes(fn)
                      ? 'bg-blue-100 text-blue-700 border-blue-300'
                      : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-100'
                  )}
                >
                  {fn}
                </button>
              ))}
            </div>
          )}

          {/* Selected Footnotes */}
          {footnotes.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-2">
              <span className="text-xs text-gray-500">Selected:</span>
              {footnotes.map(fn => (
                <span
                  key={fn}
                  className="px-1.5 py-0.5 text-xs bg-blue-500 text-white rounded cursor-pointer hover:bg-blue-600"
                  onClick={() => toggleFootnote(fn)}
                  title="Click to remove"
                >
                  {fn} ×
                </span>
              ))}
            </div>
          )}

          {/* Custom Footnote Input */}
          <div className="flex gap-1">
            <input
              type="text"
              value={customFootnote}
              onChange={e => setCustomFootnote(e.target.value)}
              placeholder="Add custom (e.g., 'a')"
              className="flex-1 px-2 py-1 text-xs border rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
              onKeyDown={e => e.key === 'Enter' && addCustomFootnote()}
            />
            <button
              onClick={addCustomFootnote}
              className="px-2 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-600"
            >
              <Plus className="h-3 w-3" />
            </button>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex justify-end gap-2 pt-2 border-t">
        <button
          onClick={handleCancel}
          className="px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-100 rounded"
        >
          Cancel
        </button>
        <button
          onClick={handleSave}
          className="px-3 py-1.5 text-xs bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Save
        </button>
      </div>
    </div>
  );
}

// ============================================================================
// Cell Renderer with Edit Indicator
// ============================================================================

interface SoACellRendererProps {
  value: CellMark;
  isUserEdited?: boolean;
  footnoteRefs?: string[];
  needsReview?: boolean;
  onClick?: () => void;
}

export function SoACellRenderer({
  value,
  isUserEdited,
  footnoteRefs,
  needsReview,
  onClick,
}: SoACellRendererProps) {
  if (!value || value === 'clear' || value === null) {
    return (
      <div 
        className="w-full h-full flex items-center justify-center cursor-pointer hover:bg-gray-50 group"
        onClick={onClick}
      >
        <Pencil className="h-3 w-3 text-gray-300 opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>
    );
  }

  // Determine cell styling based on mark type and edit status
  const baseClasses = 'w-full h-full flex items-center justify-center relative cursor-pointer';
  let markClasses = 'font-bold text-sm';
  let bgClass = '';

  // User-edited cells get a distinct background
  if (isUserEdited) {
    bgClass = 'bg-amber-50 border-l-2 border-amber-400';
  } else if (needsReview) {
    bgClass = 'bg-yellow-50';
  }

  // Mark-specific styling
  switch (value) {
    case 'X':
    case 'Xa':
    case 'Xb':
    case 'Xc':
      markClasses += ' text-green-700';
      break;
    case 'O':
      markClasses += ' text-blue-600';
      break;
    case '−':
      markClasses += ' text-gray-500';
      break;
    default:
      markClasses += ' text-gray-700';
  }

  // Format display value with superscript
  let displayValue = value;
  if (value.startsWith('X') && value.length > 1) {
    displayValue = 'X';
  }

  return (
    <div className={cn(baseClasses, bgClass)} onClick={onClick}>
      <span className={markClasses}>
        {displayValue}
        {/* Superscript for Xa, Xb, etc. */}
        {value.startsWith('X') && value.length > 1 && (
          <sup className="text-[10px] ml-0.5">{value.slice(1)}</sup>
        )}
        {/* Footnote superscripts */}
        {footnoteRefs && footnoteRefs.length > 0 && (
          <sup className="text-[10px] text-blue-600 ml-0.5">
            {footnoteRefs.join(',')}
          </sup>
        )}
      </span>
      
      {/* User edit indicator */}
      {isUserEdited && (
        <div className="absolute top-0 right-0 w-0 h-0 border-t-[8px] border-t-amber-400 border-l-[8px] border-l-transparent" />
      )}
    </div>
  );
}

export default SoACellEditor;
