'use client';

import { useMemo } from 'react';
import {
  Shuffle,
  Layers,
  Link2,
  AlertTriangle,
  CheckCircle2,
  Info,
  Shield,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { usePatchedStudyDesign } from '@/hooks/usePatchedUsdm';

// ── Types ──────────────────────────────────────────────────

interface FactorLevel {
  id: string;
  label: string;
  definition?: string | null;
  criterionId?: string | null;
}

interface StratificationFactor {
  id: string;
  name: string;
  categories: string[];
  factorLevels?: FactorLevel[];
  isBlocking: boolean;
  isNesting?: boolean;
  parentFactorId?: string | null;
  dataSource?: string | null;
}

interface AllocationCell {
  id: string;
  factorLevels: Record<string, string>;
  armId?: string | null;
  ratioWeight: number;
  isValid: boolean;
  plannedEnrollment?: number | null;
}

interface ArmWeight {
  armId: string;
  armName: string;
  allocationWeight: number;
}

interface CrossPhaseLinks {
  eligibilityLinks?: Array<{ factorName: string; levelLabel: string; criterionText: string; score: number }>;
  sapCovariateFindings?: Array<{ type: string; factorName?: string; message: string }>;
  armWeights?: ArmWeight[];
  populationLinks?: Array<{ populationName: string; factorName: string }>;
}

interface RandomizationScheme {
  id: string;
  ratio: string;
  method: string;
  algorithmType: string;
  blockSize?: number | null;
  blockSizes?: number[];
  stratificationFactors?: StratificationFactor[];
  allocationCells?: AllocationCell[];
  centralRandomization: boolean;
  iwrsSystem?: string | null;
  concealmentMethod?: string | null;
  isAdaptive?: boolean;
  adaptiveRules?: string | null;
  crossPhaseLinks?: CrossPhaseLinks;
}

// ── Component ──────────────────────────────────────────────

export function StratificationSchemeView() {
  const studyDesign = usePatchedStudyDesign();

  const scheme = useMemo<RandomizationScheme | null>(() => {
    const extensions = (studyDesign?.extensionAttributes ?? []) as Array<{
      url?: string;
      value?: unknown;
      valueObject?: unknown;
    }>;
    for (const ext of extensions) {
      if (ext?.url?.includes('randomizationScheme')) {
        const val = ext.valueObject ?? ext.value;
        if (val && typeof val === 'object') return val as RandomizationScheme;
        if (typeof val === 'string') {
          try { return JSON.parse(val); } catch { /* ignore */ }
        }
      }
    }
    return null;
  }, [studyDesign]);

  if (!scheme) {
    return (
      <div className="flex items-center justify-center h-48 text-muted-foreground">
        <Info className="w-5 h-5 mr-2" />
        No randomization scheme detected for this protocol.
      </div>
    );
  }

  const factors = scheme.stratificationFactors ?? [];
  const cells = scheme.allocationCells ?? [];
  const links = scheme.crossPhaseLinks;

  return (
    <div className="space-y-4">
      {/* Header summary */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Shuffle className="w-5 h-5" />
            Randomization Scheme
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Stat label="Ratio" value={scheme.ratio} />
            <Stat label="Algorithm" value={scheme.algorithmType} />
            <Stat label="Method" value={scheme.method} />
            <Stat
              label="IWRS"
              value={scheme.iwrsSystem ?? (scheme.centralRandomization ? 'Central' : 'None')}
            />
          </div>
          {scheme.blockSizes && scheme.blockSizes.length > 0 && (
            <div className="mt-3 text-sm text-muted-foreground">
              Block sizes: {scheme.blockSizes.join(', ')}
            </div>
          )}
          {scheme.concealmentMethod && (
            <div className="mt-1 text-sm text-muted-foreground">
              Concealment: {scheme.concealmentMethod}
            </div>
          )}
          {scheme.isAdaptive && (
            <Badge variant="outline" className="mt-2 text-amber-600 border-amber-300">
              Adaptive Randomization
            </Badge>
          )}
        </CardContent>
      </Card>

      {/* Stratification factors */}
      {factors.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Layers className="w-5 h-5" />
              Stratification Factors ({factors.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {factors.map((f) => {
                const levels = f.factorLevels ?? [];
                const cats = f.categories ?? [];
                const displayLevels: Array<{ id: string; label: string; criterionId?: string | null }> =
                  levels.length > 0
                    ? levels.map((l) => ({ id: l.id, label: l.label, criterionId: l.criterionId }))
                    : cats.map((c, i) => ({ id: `cat_${i}`, label: c }));

                return (
                  <div key={f.id} className="rounded-lg border p-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-medium">{f.name}</span>
                      <div className="flex gap-1">
                        {f.isBlocking && <Badge variant="secondary" className="text-xs">Blocking</Badge>}
                        {f.isNesting && <Badge variant="outline" className="text-xs">Nested</Badge>}
                        {f.dataSource && (
                          <Badge variant="outline" className="text-xs text-muted-foreground">
                            {f.dataSource}
                          </Badge>
                        )}
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {displayLevels.map((fl) => {
                        const hasLink = Boolean(fl.criterionId);
                        return (
                          <Badge
                            key={fl.id}
                            variant="secondary"
                            className={cn(
                              'text-xs',
                              hasLink && 'border-green-300 bg-green-50 text-green-800'
                            )}
                          >
                            {fl.label}
                            {hasLink && <Link2 className="w-3 h-3 ml-1" />}
                          </Badge>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Arm allocation weights */}
      {links?.armWeights && links.armWeights.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Shield className="w-5 h-5" />
              Arm Allocation
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2 flex-wrap">
              {links.armWeights.map((aw) => (
                <div key={aw.armId} className="flex items-center gap-2 rounded-lg border p-2 px-3">
                  <span className="font-medium">{aw.armName}</span>
                  <Badge>{aw.allocationWeight}</Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Coherence findings (B2) */}
      {links?.sapCovariateFindings && links.sapCovariateFindings.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Link2 className="w-5 h-5" />
              SAP Covariate Alignment
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {links.sapCovariateFindings.map((f, i) => (
                <div key={i} className="flex items-start gap-2 text-sm">
                  {f.type === 'ok' ? (
                    <CheckCircle2 className="w-4 h-4 text-green-500 mt-0.5 shrink-0" />
                  ) : f.type === 'warning' ? (
                    <AlertTriangle className="w-4 h-4 text-amber-500 mt-0.5 shrink-0" />
                  ) : (
                    <Info className="w-4 h-4 text-blue-500 mt-0.5 shrink-0" />
                  )}
                  <span>{f.message}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Allocation cells (if any) */}
      {cells.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Allocation Cells ({cells.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-1 pr-3">Cell</th>
                    <th className="text-left py-1 pr-3">Factor Levels</th>
                    <th className="text-left py-1 pr-3">Arm</th>
                    <th className="text-right py-1">Weight</th>
                    <th className="text-right py-1">Valid</th>
                  </tr>
                </thead>
                <tbody>
                  {cells.map((cell) => (
                    <tr key={cell.id} className={cn('border-b', !cell.isValid && 'opacity-50')}>
                      <td className="py-1 pr-3 font-mono text-xs">{cell.id}</td>
                      <td className="py-1 pr-3">
                        {Object.values(cell.factorLevels).join(' × ')}
                      </td>
                      <td className="py-1 pr-3">{cell.armId ?? '—'}</td>
                      <td className="py-1 text-right">{cell.ratioWeight}</td>
                      <td className="py-1 text-right">
                        {cell.isValid ? '✓' : '✗'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ── Helpers ─────────────────────────────────────────────────

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="font-medium text-sm truncate">{value}</div>
    </div>
  );
}
