'use client';

import { useState, useMemo } from 'react';
import {
  Clock,
  CheckCircle,
  XCircle,
  Search,
  ChevronRight,
  FileText,
  Cpu,
  Hash,
  Layers,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import type {
  ExtractionProvenanceData,
  EntityProvenanceData,
  PhaseProvenanceRecord,
} from '@/lib/provenance/types';

interface ExtractionProvenanceViewProps {
  extractionProvenance: ExtractionProvenanceData | null;
  entityProvenance: EntityProvenanceData | null;
}

const PHASE_COLORS: Record<string, string> = {
  Metadata: 'bg-blue-500',
  Narrative: 'bg-purple-500',
  Objectives: 'bg-emerald-500',
  StudyDesign: 'bg-amber-500',
  Eligibility: 'bg-teal-500',
  Interventions: 'bg-rose-500',
  Scheduling: 'bg-indigo-500',
  Execution: 'bg-cyan-500',
  Procedures: 'bg-orange-500',
  Advanced: 'bg-slate-500',
  AmendmentDetails: 'bg-pink-500',
  SAP: 'bg-violet-500',
  Sites: 'bg-lime-500',
  DocStructure: 'bg-sky-500',
};

function getPhaseColor(phase: string): string {
  return PHASE_COLORS[phase] || 'bg-gray-400';
}

export function ExtractionProvenanceView({
  extractionProvenance,
  entityProvenance,
}: ExtractionProvenanceViewProps) {
  const [entitySearch, setEntitySearch] = useState('');
  const [expandedPhase, setExpandedPhase] = useState<string | null>(null);

  if (!extractionProvenance && !entityProvenance) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Cpu className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
          <p className="text-muted-foreground">
            No extraction provenance data available.
          </p>
          <p className="text-sm text-muted-foreground mt-2">
            Run the pipeline to generate extraction and entity provenance.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Pipeline Summary */}
      {extractionProvenance && (
        <PipelineSummary data={extractionProvenance} />
      )}

      {/* Phase Timeline */}
      {extractionProvenance && (
        <PhaseTimeline
          phases={extractionProvenance.phases}
          totalDuration={extractionProvenance.totalDurationSeconds}
          expandedPhase={expandedPhase}
          onTogglePhase={(p) => setExpandedPhase(expandedPhase === p ? null : p)}
        />
      )}

      {/* Entity Provenance Lookup */}
      {entityProvenance && (
        <EntityLookup
          data={entityProvenance}
          search={entitySearch}
          onSearchChange={setEntitySearch}
        />
      )}
    </div>
  );
}

function PipelineSummary({ data }: { data: ExtractionProvenanceData }) {
  const failedCount = data.totalPhases - data.succeededPhases;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <Card>
        <CardContent className="pt-4 pb-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
            <Layers className="h-4 w-4" />
            Phases
          </div>
          <p className="text-2xl font-bold">{data.totalPhases}</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="pt-4 pb-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
            <CheckCircle className="h-4 w-4 text-green-500" />
            Succeeded
          </div>
          <p className="text-2xl font-bold text-green-600">{data.succeededPhases}</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="pt-4 pb-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
            <Clock className="h-4 w-4" />
            Duration
          </div>
          <p className="text-2xl font-bold">{data.totalDurationSeconds.toFixed(1)}s</p>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="pt-4 pb-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
            {failedCount > 0 ? (
              <XCircle className="h-4 w-4 text-red-500" />
            ) : (
              <CheckCircle className="h-4 w-4 text-green-500" />
            )}
            {failedCount > 0 ? 'Failed' : 'Status'}
          </div>
          <p className={cn('text-2xl font-bold', failedCount > 0 ? 'text-red-600' : 'text-green-600')}>
            {failedCount > 0 ? failedCount : 'All OK'}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

function PhaseTimeline({
  phases,
  totalDuration,
  expandedPhase,
  onTogglePhase,
}: {
  phases: PhaseProvenanceRecord[];
  totalDuration: number;
  expandedPhase: string | null;
  onTogglePhase: (phase: string) => void;
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <Clock className="h-4 w-4" />
          Phase Timeline
        </CardTitle>
      </CardHeader>
      <CardContent>
        {/* Duration bar */}
        <div className="flex h-6 rounded-full overflow-hidden mb-4 bg-muted">
          {phases.map((phase) => {
            const pct = totalDuration > 0
              ? (phase.durationSeconds / totalDuration) * 100
              : 0;
            if (pct < 0.5) return null;
            return (
              <div
                key={phase.phase}
                className={cn(getPhaseColor(phase.phase), 'relative group cursor-pointer hover:opacity-80 transition-opacity')}
                style={{ width: `${pct}%` }}
                onClick={() => onTogglePhase(phase.phase)}
                title={`${phase.phase}: ${phase.durationSeconds.toFixed(1)}s`}
              >
                <div className="absolute inset-0 flex items-center justify-center">
                  {pct > 10 && (
                    <span className="text-[10px] font-medium text-white truncate px-1">
                      {phase.phase}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Phase list */}
        <div className="space-y-1">
          {phases.map((phase) => (
            <PhaseRow
              key={phase.phase}
              phase={phase}
              isExpanded={expandedPhase === phase.phase}
              onToggle={() => onTogglePhase(phase.phase)}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function PhaseRow({
  phase,
  isExpanded,
  onToggle,
}: {
  phase: PhaseProvenanceRecord;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const entityTotal = useMemo(() => {
    if (!phase.entityCounts) return 0;
    return Object.values(phase.entityCounts).reduce((a, b) => a + b, 0);
  }, [phase.entityCounts]);

  return (
    <div className="border rounded-lg">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-muted/50 transition-colors"
      >
        <ChevronRight
          className={cn('h-4 w-4 text-muted-foreground transition-transform', isExpanded && 'rotate-90')}
        />
        <div className={cn('w-2.5 h-2.5 rounded-full shrink-0', getPhaseColor(phase.phase))} />
        <span className="font-medium text-sm flex-1">{phase.phase}</span>

        {phase.error ? (
          <span className="text-xs text-red-500 flex items-center gap-1">
            <XCircle className="h-3 w-3" /> Failed
          </span>
        ) : (
          <>
            {phase.confidence != null && (
              <span className="text-xs text-muted-foreground">
                {(phase.confidence * 100).toFixed(0)}%
              </span>
            )}
            {entityTotal > 0 && (
              <span className="text-xs text-muted-foreground">
                {entityTotal} entities
              </span>
            )}
            <span className="text-xs text-muted-foreground tabular-nums">
              {phase.durationSeconds.toFixed(1)}s
            </span>
          </>
        )}
      </button>

      {isExpanded && (
        <div className="px-4 pb-3 border-t text-sm space-y-2 pt-2">
          <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs">
            <div className="text-muted-foreground">Model</div>
            <div className="font-mono">{phase.model || '—'}</div>
            {phase.startedAt && (
              <>
                <div className="text-muted-foreground">Started</div>
                <div>{new Date(phase.startedAt).toLocaleTimeString()}</div>
              </>
            )}
            {phase.pagesUsed && phase.pagesUsed.length > 0 && (
              <>
                <div className="text-muted-foreground">Pages Used</div>
                <div className="font-mono">
                  {phase.pagesUsed.length <= 8
                    ? phase.pagesUsed.map((p) => p + 1).join(', ')
                    : `${phase.pagesUsed.slice(0, 6).map((p) => p + 1).join(', ')}… (${phase.pagesUsed.length} total)`}
                </div>
              </>
            )}
          </div>

          {phase.entityCounts && Object.keys(phase.entityCounts).length > 0 && (
            <div className="mt-2">
              <p className="text-xs text-muted-foreground mb-1">Entity Counts:</p>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(phase.entityCounts).map(([key, count]) => (
                  <span
                    key={key}
                    className="inline-flex items-center gap-1 px-2 py-0.5 bg-muted rounded-full text-xs"
                  >
                    <Hash className="h-3 w-3 text-muted-foreground" />
                    {key}: {count}
                  </span>
                ))}
              </div>
            </div>
          )}

          {phase.error && (
            <div className="mt-2 p-2 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900 rounded text-xs text-red-700 dark:text-red-400">
              {phase.error}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function EntityLookup({
  data,
  search,
  onSearchChange,
}: {
  data: EntityProvenanceData;
  search: string;
  onSearchChange: (v: string) => void;
}) {
  const filteredEntities = useMemo(() => {
    if (!search.trim()) return [];
    const q = search.toLowerCase();
    return Object.entries(data.entities)
      .filter(([id]) => id.toLowerCase().includes(q))
      .slice(0, 50);
  }, [data.entities, search]);

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <FileText className="h-4 w-4" />
          Entity Provenance Lookup
          <span className="ml-auto text-xs font-normal text-muted-foreground">
            {data.totalEntities} entities tracked
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {/* By-phase summary chips */}
        <div className="flex flex-wrap gap-1.5 mb-4">
          {Object.entries(data.byPhase)
            .sort((a, b) => b[1] - a[1])
            .map(([phase, count]) => (
              <span
                key={phase}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-muted"
              >
                <span className={cn('w-2 h-2 rounded-full', getPhaseColor(phase))} />
                {phase}: {count}
              </span>
            ))}
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search entity IDs (e.g., obj_, arm_, inc_)…"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-primary/50 text-sm"
          />
        </div>

        {/* Results */}
        {search.trim() && (
          <div className="mt-3 max-h-64 overflow-y-auto space-y-1">
            {filteredEntities.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">
                No entities matching &ldquo;{search}&rdquo;
              </p>
            ) : (
              filteredEntities.map(([id, rec]) => (
                <div
                  key={id}
                  className="flex items-center gap-2 px-3 py-1.5 rounded hover:bg-muted text-sm"
                >
                  <span className={cn('w-2 h-2 rounded-full shrink-0', getPhaseColor(rec.phase))} />
                  <span className="font-mono text-xs truncate flex-1">{id}</span>
                  <span className="text-xs text-muted-foreground shrink-0">{rec.phase}</span>
                  {rec.pagesUsed && rec.pagesUsed.length > 0 && (
                    <span className="text-xs text-muted-foreground shrink-0">
                      pp. {rec.pagesUsed.slice(0, 3).map((p) => p + 1).join(',')}
                      {rec.pagesUsed.length > 3 && '…'}
                    </span>
                  )}
                  {rec.confidence != null && (
                    <span className="text-xs text-muted-foreground shrink-0">
                      {(rec.confidence * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
              ))
            )}
            {filteredEntities.length >= 50 && (
              <p className="text-xs text-muted-foreground text-center py-1">
                Showing first 50 results. Refine your search.
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default ExtractionProvenanceView;
