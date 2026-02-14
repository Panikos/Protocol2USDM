'use client';

import { useEntityProvenance } from '@/hooks/useEntityProvenance';
import { cn } from '@/lib/utils';

interface ProvenanceBadgeProps {
  entityId: string | undefined;
  className?: string;
}

const PHASE_BADGE_COLORS: Record<string, string> = {
  Metadata: 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300',
  Narrative: 'bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-300',
  Objectives: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300',
  StudyDesign: 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300',
  Eligibility: 'bg-teal-100 text-teal-700 dark:bg-teal-950 dark:text-teal-300',
  Interventions: 'bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300',
  Scheduling: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300',
  Execution: 'bg-cyan-100 text-cyan-700 dark:bg-cyan-950 dark:text-cyan-300',
  Procedures: 'bg-orange-100 text-orange-700 dark:bg-orange-950 dark:text-orange-300',
  Advanced: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
};

/**
 * Displays a small badge showing which extraction phase produced an entity.
 * Must be used inside an EntityProvenanceContext.Provider.
 * Renders nothing if no provenance data is available for the entity.
 */
export function ProvenanceBadge({ entityId, className }: ProvenanceBadgeProps) {
  const prov = useEntityProvenance(entityId);
  if (!prov) return null;

  const colorClass = PHASE_BADGE_COLORS[prov.phase] || 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300';
  const pages = prov.pagesUsed;
  const pageStr = pages && pages.length > 0
    ? `pp. ${pages.slice(0, 3).map((p) => p + 1).join(',')}${pages.length > 3 ? '…' : ''}`
    : null;

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium leading-none',
        colorClass,
        className,
      )}
      title={`Extracted by ${prov.phase}${pageStr ? ` from ${pageStr}` : ''}${prov.confidence != null ? ` (${(prov.confidence * 100).toFixed(0)}% confidence)` : ''}`}
    >
      {prov.phase}
      {pageStr && <span className="opacity-70">{pageStr}</span>}
    </span>
  );
}

export default ProvenanceBadge;
