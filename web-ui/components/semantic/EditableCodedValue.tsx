'use client';

import { useState, useRef, useEffect } from 'react';
import { ChevronDown, Check, X, Pencil } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useSemanticStore } from '@/stores/semanticStore';
import { useEditModeStore } from '@/stores/editModeStore';
import { cn } from '@/lib/utils';
import { CodeLink, evsUrl } from './CodeLink';

/**
 * A coded value option — mirrors CDISC Code structure.
 */
export interface CodeOption {
  /** C-Code identifier, e.g. "C49487" */
  code: string;
  /** Human-readable decode, e.g. "Phase I Trial" */
  decode: string;
  /** Optional definition */
  definition?: string;
}

/**
 * Pre-built terminology lists for common CDISC coded values.
 *
 * Loaded from the generated JSON (scripts/generate_code_registry.py)
 * which is the single source of truth derived from USDM_CT.xlsx and
 * supplementary NCI EVS codes.
 *
 * To regenerate: `python scripts/generate_code_registry.py`
 */
import _generatedCodelists from '@/lib/codelist.generated.json';

export const CDISC_TERMINOLOGIES: Record<string, CodeOption[]> =
  _generatedCodelists as Record<string, CodeOption[]>;

export interface EditableCodedValueProps {
  /** JSON Patch path to the coded value object (containing code + decode) */
  path: string;
  /** Current value — can be { code, decode } or just a string */
  value: { code?: string; decode?: string } | string | null | undefined;
  /** Display label */
  label?: string;
  /** Available options */
  options: CodeOption[];
  /** Whether the field is editable (default true) */
  editable?: boolean;
  /** Placeholder when no value */
  placeholder?: string;
  /** Additional class name */
  className?: string;
  /** Whether to show the C-Code badge (default false) */
  showCode?: boolean;
  /** If true, the path points to the parent and we patch code + decode separately */
  patchAsObject?: boolean;
}

export function EditableCodedValue({
  path,
  value,
  label,
  options,
  editable = true,
  placeholder = 'Select...',
  className,
  showCode = false,
  patchAsObject = true,
}: EditableCodedValueProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const { addPatchOp, beginGroup, endGroup } = useSemanticStore();
  const isEditMode = useEditModeStore((s) => s.isEditMode);

  const canEdit = editable && isEditMode;

  // Normalize current value — defensively unwrap since USDM data
  // may contain nested objects in code/decode fields (e.g. amendments)
  const _unwrap = (v: unknown): string => {
    if (typeof v === 'string') return v;
    if (v && typeof v === 'object') {
      const obj = v as Record<string, unknown>;
      return (typeof obj.decode === 'string' ? obj.decode : '')
        || (typeof obj.code === 'string' ? obj.code : '');
    }
    return String(v ?? '');
  };
  const currentDecode = typeof value === 'string'
    ? value
    : _unwrap(value?.decode) || _unwrap(value);
  const rawCode = typeof value === 'string'
    ? options.find(o => o.decode === value)?.code ?? ''
    : (typeof value?.code === 'string' ? value.code : _unwrap(value?.code));
  // If the stored code is not a valid C-code (e.g. decode was stored in the code field),
  // look up the real C-code from the options list using the decode value.
  // Uses tolerant matching: exact → case-insensitive startsWith → includes.
  const currentCode = /^C\d{3,}$/i.test(rawCode)
    ? rawCode
    : (() => {
        const needle = String(currentDecode || rawCode).toLowerCase().trim();
        if (!needle) return rawCode;
        return (
          options.find(o => o.decode.toLowerCase() === needle)?.code ??
          options.find(o => o.decode.toLowerCase().startsWith(needle))?.code ??
          options.find(o => o.decode.toLowerCase().includes(needle))?.code ??
          rawCode
        );
      })();

  // Filter options by search
  const filtered = search
    ? options.filter(o =>
        o.decode.toLowerCase().includes(search.toLowerCase()) ||
        o.code.toLowerCase().includes(search.toLowerCase())
      )
    : options;

  // Close dropdown on outside click
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
        setSearch('');
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [isOpen]);

  // Focus search input when opened
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  const handleSelect = (option: CodeOption) => {
    if (patchAsObject) {
      beginGroup();
      addPatchOp({ op: 'replace', path: `${path}/code`, value: option.code });
      addPatchOp({ op: 'replace', path: `${path}/decode`, value: option.decode });
      endGroup();
    } else {
      addPatchOp({ op: 'replace', path, value: option.decode });
    }
    setIsOpen(false);
    setSearch('');
  };

  return (
    <div className={cn('relative', className)} ref={dropdownRef}>
      {label && (
        <span className="text-sm font-medium text-muted-foreground block mb-1">
          {label}
        </span>
      )}

      {/* Display / trigger */}
      <div
        className={cn(
          'flex items-center gap-2 min-h-[2rem] rounded-md px-2 py-1',
          canEdit && 'cursor-pointer hover:bg-muted/50 group',
          !currentDecode && 'text-muted-foreground italic'
        )}
        onClick={() => canEdit && setIsOpen(!isOpen)}
      >
        {currentDecode ? (
          <Badge variant="outline" className="text-sm font-normal">
            {currentDecode}
          </Badge>
        ) : (
          <span className="flex-1 text-sm">{placeholder}</span>
        )}
        {showCode && currentCode && (
          <CodeLink code={currentCode} codeOnly className="text-[10px] px-1 py-0 h-4" />
        )}
        {canEdit && (
          <ChevronDown className={cn(
            'h-3.5 w-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-all',
            isOpen && 'rotate-180 opacity-100'
          )} />
        )}
      </div>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute z-50 mt-1 w-full min-w-[220px] bg-popover border rounded-md shadow-lg">
          {/* Search */}
          {options.length > 5 && (
            <div className="p-2 border-b">
              <input
                ref={inputRef}
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search..."
                className="w-full px-2 py-1 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                onKeyDown={(e) => {
                  if (e.key === 'Escape') {
                    setIsOpen(false);
                    setSearch('');
                  }
                  if (e.key === 'Enter' && filtered.length === 1) {
                    handleSelect(filtered[0]);
                  }
                }}
              />
            </div>
          )}

          {/* Options */}
          <div className="max-h-[240px] overflow-y-auto py-1">
            {filtered.length === 0 ? (
              <p className="px-3 py-2 text-sm text-muted-foreground">No matches</p>
            ) : (
              filtered.map((option) => {
                const isSelected = option.code === currentCode || option.decode === currentDecode;
                return (
                  <button
                    key={option.code}
                    className={cn(
                      'w-full text-left px-3 py-1.5 text-sm hover:bg-accent flex items-center gap-2',
                      isSelected && 'bg-accent/50 font-medium'
                    )}
                    onClick={() => handleSelect(option)}
                  >
                    <span className="flex-1">{option.decode}</span>
                    {showCode && (
                      <CodeLink code={option.code} codeOnly className="text-[10px] px-1 py-0 h-4" />
                    )}
                    {isSelected && <Check className="h-3.5 w-3.5 text-primary" />}
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default EditableCodedValue;
