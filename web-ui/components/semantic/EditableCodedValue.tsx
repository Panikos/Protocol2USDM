'use client';

import { useState, useRef, useEffect } from 'react';
import { ChevronDown, Check, X, Pencil } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useSemanticStore } from '@/stores/semanticStore';
import { useEditModeStore } from '@/stores/editModeStore';
import { cn } from '@/lib/utils';

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
 * These can be extended or overridden per-field.
 */
export const CDISC_TERMINOLOGIES: Record<string, CodeOption[]> = {
  studyPhase: [
    { code: 'C15600', decode: 'Phase I Trial' },
    { code: 'C15693', decode: 'Phase I/II Trial' },
    { code: 'C15601', decode: 'Phase II Trial' },
    { code: 'C15694', decode: 'Phase II/III Trial' },
    { code: 'C15602', decode: 'Phase III Trial' },
    { code: 'C15603', decode: 'Phase IV Trial' },
    { code: 'C48660', decode: 'Not Applicable' },
  ],
  studyType: [
    { code: 'C98388', decode: 'Interventional Study' },
    { code: 'C142615', decode: 'Observational Study' },
    { code: 'C48660', decode: 'Not Applicable' },
  ],
  encounterType: [
    { code: 'C25716', decode: 'Visit' },
  ],
  blindingSchema: [
    { code: 'C49659', decode: 'Open Label Study' },
    { code: 'C28233', decode: 'Single Blind Study' },
    { code: 'C15228', decode: 'Double Blind Study' },
    { code: 'C66959', decode: 'Triple Blind Study' },
  ],
  epochType: [
    { code: 'C48262', decode: 'Trial Screening' },
    { code: 'C98779', decode: 'Run-in Period' },
    { code: 'C101526', decode: 'Treatment Epoch' },
    { code: 'C99158', decode: 'Clinical Study Follow-up' },
    { code: 'C48660', decode: 'Not Applicable' },
  ],
  armType: [
    { code: 'C174266', decode: 'Experimental Arm' },
    { code: 'C174267', decode: 'Active Comparator Arm' },
    { code: 'C174268', decode: 'Placebo Comparator Arm' },
    { code: 'C174269', decode: 'Sham Comparator Arm' },
    { code: 'C174270', decode: 'No Intervention Arm' },
    { code: 'C48660', decode: 'Not Applicable' },
  ],
  sex: [
    { code: 'C16576', decode: 'Female' },
    { code: 'C20197', decode: 'Male' },
    { code: 'C49636', decode: 'Both' },
  ],
  interventionRole: [
    { code: 'C41161', decode: 'Experimental Intervention' },
    { code: 'C68609', decode: 'Active Comparator' },
    { code: 'C753', decode: 'Placebo' },
    { code: 'C165835', decode: 'Rescue Medicine' },
    { code: 'C207614', decode: 'Additional Required Treatment' },
    { code: 'C165822', decode: 'Background Treatment' },
    { code: 'C158128', decode: 'Challenge Agent' },
    { code: 'C18020', decode: 'Diagnostic' },
  ],
  interventionType: [
    { code: 'C1909', decode: 'Drug' },
    { code: 'C1261', decode: 'Biological' },
    { code: 'C16203', decode: 'Device' },
    { code: 'C15329', decode: 'Dietary Supplement' },
    { code: 'C64858', decode: 'Procedure' },
    { code: 'C15692', decode: 'Radiation' },
    { code: 'C17998', decode: 'Other' },
  ],
  substanceType: [
    { code: 'C45305', decode: 'Active Ingredient' },
    { code: 'C42637', decode: 'Inactive Ingredient' },
    { code: 'C48660', decode: 'Not Applicable' },
  ],
  ingredientRole: [
    { code: 'C82499', decode: 'Active' },
    { code: 'C82500', decode: 'Inactive' },
    { code: 'C82501', decode: 'Adjuvant' },
    { code: 'C48660', decode: 'Not Applicable' },
  ],
  endpointPurpose: [
    { code: 'C94496', decode: 'Primary Endpoint' },
    { code: 'C139173', decode: 'Secondary Endpoint' },
    { code: 'C170559', decode: 'Exploratory Endpoint' },
  ],
  routeOfAdministration: [
    { code: 'C38288', decode: 'Oral' },
    { code: 'C38276', decode: 'Intravenous' },
    { code: 'C38299', decode: 'Subcutaneous' },
    { code: 'C38274', decode: 'Intramuscular' },
    { code: 'C38305', decode: 'Topical' },
    { code: 'C38284', decode: 'Nasal' },
    { code: 'C38246', decode: 'Inhalation' },
    { code: 'C17998', decode: 'Other' },
  ],
  populationLevel: [
    { code: 'C174264', decode: 'Intent-to-Treat' },
    { code: 'C174265', decode: 'Per-Protocol' },
    { code: 'C174263', decode: 'Safety' },
    { code: 'C17998', decode: 'Other' },
  ],
};

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

  // Normalize current value
  const currentDecode = typeof value === 'string'
    ? value
    : value?.decode ?? '';
  const currentCode = typeof value === 'string'
    ? options.find(o => o.decode === value)?.code ?? ''
    : value?.code ?? '';

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
        <span className="flex-1 text-sm">
          {currentDecode || placeholder}
        </span>
        {showCode && currentCode && (
          <Badge variant="outline" className="text-[10px] px-1 py-0 h-4">
            {currentCode}
          </Badge>
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
                      <span className="text-[10px] text-muted-foreground">{option.code}</span>
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
