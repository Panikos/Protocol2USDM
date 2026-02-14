'use client';

import { ICellRendererParams } from 'ag-grid-community';
import { CheckCircle2, FileText, Eye, AlertTriangle, Pencil, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { CellSource } from '@/lib/provenance/types';

export interface ProvenanceCellRendererParams extends ICellRendererParams {
  columnId: string;
  cellMap: Map<string, {
    mark: string | null;
    footnoteRefs: string[];
    instanceName?: string;  // Human-readable instance name
    timingId?: string;
    epochId?: string;
    userEdited?: boolean;   // True if cell was manually edited by user
    provenance: {
      source: CellSource;
      needsReview: boolean;
    };
  }>;
  pendingEditsRef?: React.RefObject<Map<string, { mark: string; footnoteRefs: string[] }> | null>;
}

export function ProvenanceCellRenderer(params: ProvenanceCellRendererParams) {
  const { value, data, columnId, cellMap, pendingEditsRef } = params;
  
  // Get cell data from map
  const cellKey = `${data?.id}|${columnId}`;
  const cellData = cellMap?.get(cellKey);
  const pendingEdit = pendingEditsRef?.current?.get(cellKey);
  
  if (!value && !cellData?.mark && !pendingEdit) {
    return null;
  }

  // Prioritize value (from rowData, includes pending edits) over cellData
  const mark = value || cellData?.mark;
  const source = cellData?.provenance?.source || 'none';
  const footnotes = pendingEdit?.footnoteRefs || cellData?.footnoteRefs || [];
  const needsReview = cellData?.provenance?.needsReview || false;
  const instanceName = cellData?.instanceName;
  const userEdited = cellData?.userEdited || false;
  const hasPendingEdit = !!pendingEdit;

  // Get background color based on: pending edit > user edited > provenance
  let bgColor: string;
  if (hasPendingEdit) {
    bgColor = 'bg-amber-200 hover:bg-amber-300 border-l-2 border-amber-500';
  } else if (userEdited) {
    bgColor = 'bg-purple-300 hover:bg-purple-400';
  } else {
    bgColor = getProvenanceBackgroundColor(source);
  }
  const provenanceText = getProvenanceTooltip(source, needsReview, userEdited);
  
  // Build tooltip with instance name if available
  const tooltip = instanceName 
    ? `${instanceName}\n\n${provenanceText}`
    : provenanceText;

  // Secondary indicator icon for provenance (F13 — WCAG 1.4.1)
  const ProvenanceIcon = getProvenanceIcon(hasPendingEdit ? 'pending' : userEdited ? 'userEdited' : source);

  return (
    <div
      className={cn(
        'flex items-center justify-center h-full w-full font-medium text-sm relative',
        'transition-colors cursor-default',
        bgColor
      )}
      title={tooltip}
    >
      <span className="select-none">{mark}</span>
      {footnotes.length > 0 && (
        <sup className="text-blue-700 text-[10px] ml-0.5 font-normal">
          {footnotes.join(',')}
        </sup>
      )}
      {ProvenanceIcon && (
        <span className="absolute bottom-0 right-0 opacity-60">
          <ProvenanceIcon className="h-2.5 w-2.5" />
        </span>
      )}
    </div>
  );
}

function getProvenanceIcon(source: string): React.ComponentType<{ className?: string }> | null {
  switch (source) {
    case 'both': return CheckCircle2;
    case 'text': return FileText;
    case 'vision':
    case 'needs_review': return Eye;
    case 'none': return AlertTriangle;
    case 'userEdited': return Pencil;
    case 'pending': return Clock;
    default: return null;
  }
}

function getProvenanceBackgroundColor(source: CellSource): string {
  switch (source) {
    case 'both':
      return 'bg-green-400/80 hover:bg-green-400';
    case 'text':
      return 'bg-blue-400/80 hover:bg-blue-400';
    case 'vision':
    case 'needs_review':
      return 'bg-orange-400/80 hover:bg-orange-400';
    case 'none':
      return 'bg-red-400/80 hover:bg-red-400';
    default:
      return 'bg-gray-100';
  }
}

function getProvenanceTooltip(source: CellSource, needsReview: boolean, userEdited?: boolean): string {
  if (userEdited) {
    return 'User Edited: Manually modified by user';
  }
  
  const base = {
    both: 'Confirmed: Text + Vision agree',
    text: 'Text-only: Not confirmed by vision',
    vision: 'Vision-only: May need review',
    needs_review: 'Needs review: Possible extraction issue',
    none: 'Orphaned: No provenance data',
  }[source] || 'Unknown provenance';

  return needsReview ? `${base} (Needs Review)` : base;
}

// Legend component for provenance colors
export function ProvenanceLegend({ className }: { className?: string }) {
  const items = [
    { color: 'bg-green-400', icon: CheckCircle2, label: 'Confirmed', desc: 'Text + Vision agree' },
    { color: 'bg-blue-400', icon: FileText, label: 'Text-only', desc: 'Not confirmed by vision' },
    { color: 'bg-orange-400', icon: Eye, label: 'Vision-only', desc: 'Needs review' },
    { color: 'bg-red-400', icon: AlertTriangle, label: 'Orphaned', desc: 'No provenance' },
    { color: 'bg-purple-300', icon: Pencil, label: 'User Edited', desc: 'Manually modified' },
    { color: 'bg-amber-200 border-l-2 border-amber-500', icon: Clock, label: 'Pending', desc: 'Unsaved edit' },
  ];

  return (
    <div className={cn('flex flex-wrap items-center gap-4 text-sm', className)}>
      <span className="font-medium text-muted-foreground">Provenance:</span>
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-1.5">
          <div className={cn('w-4 h-4 rounded flex items-center justify-center', item.color)}>
            <item.icon className="h-2.5 w-2.5 text-white/80" />
          </div>
          <span className="text-muted-foreground">
            <strong>{item.label}</strong>
            <span className="hidden sm:inline"> - {item.desc}</span>
          </span>
        </div>
      ))}
    </div>
  );
}

export default ProvenanceCellRenderer;
