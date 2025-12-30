'use client';

import { ICellRendererParams } from 'ag-grid-community';
import { cn } from '@/lib/utils';
import type { CellSource } from '@/lib/provenance/types';

export interface ProvenanceCellRendererParams extends ICellRendererParams {
  columnId: string;
  cellMap: Map<string, {
    mark: string | null;
    footnoteRefs: string[];
    provenance: {
      source: CellSource;
      needsReview: boolean;
    };
  }>;
}

export function ProvenanceCellRenderer(params: ProvenanceCellRendererParams) {
  const { value, data, columnId, cellMap } = params;
  
  // Get cell data from map
  const cellKey = `${data?.id}|${columnId}`;
  const cellData = cellMap?.get(cellKey);
  
  if (!value && !cellData?.mark) {
    return null;
  }

  const mark = cellData?.mark || value;
  const source = cellData?.provenance?.source || 'none';
  const footnotes = cellData?.footnoteRefs || [];
  const needsReview = cellData?.provenance?.needsReview || false;

  // Get background color based on provenance
  const bgColor = getProvenanceBackgroundColor(source);
  const tooltip = getProvenanceTooltip(source, needsReview);

  return (
    <div
      className={cn(
        'flex items-center justify-center h-full w-full font-medium text-sm',
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
    </div>
  );
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

function getProvenanceTooltip(source: CellSource, needsReview: boolean): string {
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
    { color: 'bg-green-400', label: 'Confirmed', desc: 'Text + Vision agree' },
    { color: 'bg-blue-400', label: 'Text-only', desc: 'Not confirmed by vision' },
    { color: 'bg-orange-400', label: 'Vision-only', desc: 'Needs review' },
    { color: 'bg-red-400', label: 'Orphaned', desc: 'No provenance' },
  ];

  return (
    <div className={cn('flex flex-wrap items-center gap-4 text-sm', className)}>
      <span className="font-medium text-muted-foreground">Provenance:</span>
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-1.5">
          <div className={cn('w-4 h-4 rounded', item.color)} />
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
