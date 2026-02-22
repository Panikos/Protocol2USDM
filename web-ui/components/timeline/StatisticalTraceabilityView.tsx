'use client';

import { useState, useMemo } from 'react';
import {
  ArrowDown,
  Target,
  BarChart3,
  Users,
  Shield,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronRight,
  Link2,
  Layers,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { usePatchedStudyDesign, usePatchedUsdm } from '@/hooks/usePatchedUsdm';

// Types for the traceability chain
interface TraceEndpoint {
  id: string;
  text?: string;
  name?: string;
  level?: string; // Primary, Secondary, Exploratory
  levelDecode?: string;
  objectiveName?: string;
  objectiveLevel?: string;
}

interface TraceMethod {
  id: string;
  name: string;
  endpointName?: string;
  statoCode?: string;
  hypothesisType?: string;
  alphaLevel?: number;
  covariates?: string[];
  arsReason?: string;
}

interface TracePopulation {
  id: string;
  name: string;
  populationType?: string;
  label?: string;
}

interface TraceEstimand {
  id: string;
  name?: string;
  label?: string;
  treatment?: string;
  population?: string;
  variableOfInterest?: { text?: string; name?: string };
  intercurrentEvents?: Array<{ name: string; strategy?: string; text?: string }>;
  summaryMeasure?: string;
}

interface AnalysisSpec {
  id: string;
  endpointId?: string;
  endpointName?: string;
  methodId?: string;
  methodName?: string;
  populationId?: string;
  populationName?: string;
  estimandId?: string;
  analysisType?: string;
  missingDataStrategy?: string;
  modelSpecification?: string;
}

interface TraceChain {
  endpoint: TraceEndpoint;
  method?: TraceMethod;
  population?: TracePopulation;
  estimand?: TraceEstimand;
  spec?: AnalysisSpec;
  completeness: number; // 0-100
}

export function StatisticalTraceabilityView() {
  const studyDesign = usePatchedStudyDesign();
  const usdm = usePatchedUsdm();
  const [expandedChain, setExpandedChain] = useState<string | null>(null);

  // Build traceability chains from USDM data
  const { chains, coherenceScore, stats } = useMemo(() => {
    if (!studyDesign || !usdm) {
      return { chains: [] as TraceChain[], coherenceScore: 0, stats: { total: 0, linked: 0, partial: 0, unlinked: 0 } };
    }

    const study = (usdm as Record<string, unknown>).study as Record<string, unknown> | undefined;
    const versions = (study?.versions ?? []) as Array<Record<string, unknown>>;
    const version = versions[0] ?? {};
    const design = ((version.studyDesigns as Array<Record<string, unknown>> | undefined) ?? [{}])[0] ?? {};

    // Collect endpoints from objectives
    const endpoints: TraceEndpoint[] = [];
    const objectives = (design.objectives ?? []) as Array<Record<string, unknown>>;
    for (const obj of objectives) {
      const objName = (obj.name ?? obj.text ?? '') as string;
      const objLevel = ((obj.level as Record<string, unknown>)?.decode ?? '') as string;
      const eps = (obj.endpoints ?? []) as Array<Record<string, unknown>>;
      for (const ep of eps) {
        const levelObj = ep.level as Record<string, unknown> | undefined;
        endpoints.push({
          id: (ep.id ?? '') as string,
          text: (ep.text ?? ep.endpointText ?? ep.name ?? '') as string,
          name: (ep.name ?? '') as string,
          level: (levelObj?.code ?? '') as string,
          levelDecode: (levelObj?.decode ?? '') as string,
          objectiveName: objName,
          objectiveLevel: objLevel,
        });
      }
    }

    // Collect methods from SAP extensions
    const extensions = (design.extensionAttributes ?? []) as Array<Record<string, unknown>>;
    let methods: TraceMethod[] = [];
    let populations: TracePopulation[] = [];
    let analysisSpecs: AnalysisSpec[] = [];

    for (const ext of extensions) {
      const url = (ext.url ?? '') as string;
      const val = (ext.valueString ?? '') as string;
      try {
        if (url.includes('x-sap-statistical-methods') && val) {
          methods = JSON.parse(val) as TraceMethod[];
        }
        if (url.includes('x-sap-analysis-specifications') && val) {
          analysisSpecs = JSON.parse(val) as AnalysisSpec[];
        }
      } catch { /* ignore parse errors */ }
    }

    // Populations from core USDM
    const corePops = (design.analysisPopulations ?? []) as Array<Record<string, unknown>>;
    populations = corePops.map(p => ({
      id: (p.id ?? '') as string,
      name: (p.name ?? '') as string,
      populationType: (p.populationType ?? '') as string,
      label: (p.label ?? '') as string,
    }));

    // Estimands
    const estimands = (design.estimands ?? []) as TraceEstimand[];

    // Build spec lookup
    const specByEndpoint: Record<string, AnalysisSpec> = {};
    for (const spec of analysisSpecs) {
      if (spec.endpointId) {
        specByEndpoint[spec.endpointId] = spec;
      }
      if (spec.endpointName) {
        specByEndpoint[spec.endpointName.toLowerCase()] = spec;
      }
    }

    // Build method lookup by endpoint name
    const methodByEndpoint: Record<string, TraceMethod> = {};
    for (const m of methods) {
      if (m.endpointName) {
        methodByEndpoint[m.endpointName.toLowerCase()] = m;
      }
    }

    // Build population lookup
    const popById: Record<string, TracePopulation> = {};
    const popByName: Record<string, TracePopulation> = {};
    for (const p of populations) {
      if (p.id) popById[p.id] = p;
      if (p.name) popByName[p.name.toLowerCase()] = p;
    }

    // Build estimand lookup by endpoint text
    const estimandByEndpoint: Record<string, TraceEstimand> = {};
    for (const est of estimands) {
      const voiText = (est.variableOfInterest?.text ?? est.variableOfInterest?.name ?? '') as string;
      if (voiText) {
        estimandByEndpoint[voiText.toLowerCase()] = est;
      }
    }

    // Build trace chains
    const builtChains: TraceChain[] = endpoints.map(ep => {
      const epTextLower = (ep.text ?? '').toLowerCase();

      // Find matching spec
      const spec = specByEndpoint[ep.id] ?? specByEndpoint[epTextLower];

      // Find method (prefer spec, fall back to name matching)
      let method: TraceMethod | undefined;
      if (spec?.methodName) {
        method = methods.find(m => m.name === spec.methodName || m.id === spec.methodId);
      }
      if (!method) {
        method = methodByEndpoint[epTextLower];
      }

      // Find population
      let population: TracePopulation | undefined;
      if (spec?.populationId) {
        population = popById[spec.populationId];
      }
      if (!population && spec?.populationName) {
        population = popByName[spec.populationName.toLowerCase()];
      }
      if (!population && populations.length > 0) {
        population = populations.find(p => p.populationType === 'FullAnalysis') ?? populations[0];
      }

      // Find estimand
      const estimand = estimandByEndpoint[epTextLower];

      // Calculate completeness
      let score = 25; // endpoint exists = 25%
      if (method) score += 25;
      if (population) score += 25;
      if (estimand) score += 25;

      return {
        endpoint: ep,
        method,
        population,
        estimand,
        spec,
        completeness: score,
      };
    });

    // Sort: primary first, then by completeness
    builtChains.sort((a, b) => {
      const aLevel = a.endpoint.levelDecode?.toLowerCase() ?? '';
      const bLevel = b.endpoint.levelDecode?.toLowerCase() ?? '';
      if (aLevel.includes('primary') && !bLevel.includes('primary')) return -1;
      if (!aLevel.includes('primary') && bLevel.includes('primary')) return 1;
      return b.completeness - a.completeness;
    });

    const total = builtChains.length;
    const linked = builtChains.filter(c => c.completeness === 100).length;
    const partial = builtChains.filter(c => c.completeness > 25 && c.completeness < 100).length;
    const unlinked = builtChains.filter(c => c.completeness <= 25).length;
    const avgScore = total > 0 ? Math.round(builtChains.reduce((s, c) => s + c.completeness, 0) / total) : 0;

    return {
      chains: builtChains,
      coherenceScore: avgScore,
      stats: { total, linked, partial, unlinked },
    };
  }, [studyDesign, usdm]);

  if (chains.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Link2 className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
          <h3 className="text-lg font-semibold mb-2">No Traceability Data</h3>
          <p className="text-muted-foreground">
            Extract objectives and SAP data to see endpoint-to-method traceability.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Coherence Score Header */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Link2 className="h-5 w-5" />
            Statistical Coherence
          </CardTitle>
          <CardDescription>
            Traceability from endpoints through statistical methods, populations, and estimands
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {/* Score */}
            <div className="col-span-2 md:col-span-1 flex flex-col items-center justify-center p-4 bg-muted rounded-lg">
              <div className={cn(
                'text-4xl font-bold',
                chains.length > 0 && (
                  coherenceScore >= 75 ? 'text-green-600' :
                  coherenceScore >= 50 ? 'text-amber-600' :
                  'text-red-600'
                ),
              )}>
                {coherenceScore}%
              </div>
              <p className="text-sm text-muted-foreground mt-1">Coherence Score</p>
            </div>

            {/* Stats */}
            <StatBox
              icon={<CheckCircle2 className="h-5 w-5 text-green-500" />}
              label="Fully Linked"
              value={stats.linked}
              total={stats.total}
              color="bg-green-50 border-green-200"
            />
            <StatBox
              icon={<AlertTriangle className="h-5 w-5 text-amber-500" />}
              label="Partially Linked"
              value={stats.partial}
              total={stats.total}
              color="bg-amber-50 border-amber-200"
            />
            <StatBox
              icon={<XCircle className="h-5 w-5 text-red-500" />}
              label="Unlinked"
              value={stats.unlinked}
              total={stats.total}
              color="bg-red-50 border-red-200"
            />
            <StatBox
              icon={<Target className="h-5 w-5 text-blue-500" />}
              label="Total Endpoints"
              value={stats.total}
              total={stats.total}
              color="bg-blue-50 border-blue-200"
            />
          </div>

          {/* Progress bar */}
          <div className="mt-4 flex items-center gap-3">
            <div className="flex-1 bg-muted rounded-full h-3 overflow-hidden flex">
              <div
                className="bg-green-500 h-full transition-all"
                style={{ width: `${stats.total > 0 ? (stats.linked / stats.total) * 100 : 0}%` }}
              />
              <div
                className="bg-amber-400 h-full transition-all"
                style={{ width: `${stats.total > 0 ? (stats.partial / stats.total) * 100 : 0}%` }}
              />
              <div
                className="bg-red-300 h-full transition-all"
                style={{ width: `${stats.total > 0 ? (stats.unlinked / stats.total) * 100 : 0}%` }}
              />
            </div>
            <span className="text-sm text-muted-foreground whitespace-nowrap">
              {stats.linked}/{stats.total} complete
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Traceability Chains */}
      <div className="space-y-3">
        {chains.map((chain) => (
          <TraceChainCard
            key={chain.endpoint.id}
            chain={chain}
            isExpanded={expandedChain === chain.endpoint.id}
            onToggle={() => setExpandedChain(
              expandedChain === chain.endpoint.id ? null : chain.endpoint.id
            )}
          />
        ))}
      </div>
    </div>
  );
}

// ============================================================================
// Stat Box
// ============================================================================

function StatBox({
  icon,
  label,
  value,
  total,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  total: number;
  color: string;
}) {
  return (
    <div className={cn('p-3 rounded-lg border', color)}>
      <div className="flex items-center gap-2 mb-1">
        {icon}
        <span className="text-sm font-medium">{label}</span>
      </div>
      <p className="text-2xl font-bold">{value}</p>
    </div>
  );
}

// ============================================================================
// Trace Chain Card
// ============================================================================

function TraceChainCard({
  chain,
  isExpanded,
  onToggle,
}: {
  chain: TraceChain;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const { endpoint, method, population, estimand, spec, completeness } = chain;

  const levelColor =
    endpoint.levelDecode?.toLowerCase().includes('primary')
      ? 'bg-blue-100 text-blue-800 border-blue-300'
      : endpoint.levelDecode?.toLowerCase().includes('secondary')
      ? 'bg-purple-100 text-purple-800 border-purple-300'
      : 'bg-gray-100 text-gray-800 border-gray-300';

  const completenessColor =
    completeness === 100
      ? 'text-green-600'
      : completeness >= 50
      ? 'text-amber-600'
      : 'text-red-600';

  return (
    <Card className="overflow-hidden">
      <div
        className="p-4 cursor-pointer hover:bg-muted/50 transition-colors"
        onClick={onToggle}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3 flex-1 min-w-0">
            {isExpanded ? (
              <ChevronDown className="h-4 w-4 shrink-0" />
            ) : (
              <ChevronRight className="h-4 w-4 shrink-0" />
            )}
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                {endpoint.levelDecode && (
                  <Badge className={cn('text-xs border', levelColor)}>
                    {endpoint.levelDecode}
                  </Badge>
                )}
                <span className="font-medium text-sm truncate">
                  {endpoint.text || endpoint.name || 'Unnamed endpoint'}
                </span>
              </div>
              <div className="flex items-center gap-4 mt-1 text-xs text-muted-foreground">
                {method ? (
                  <span className="flex items-center gap-1">
                    <BarChart3 className="h-3 w-3" /> {method.name}
                    {method.statoCode && (
                      <Badge variant="outline" className="text-[10px] px-1 py-0">
                        {method.statoCode}
                      </Badge>
                    )}
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-red-500">
                    <BarChart3 className="h-3 w-3" /> No method linked
                  </span>
                )}
                {population ? (
                  <span className="flex items-center gap-1">
                    <Users className="h-3 w-3" /> {population.name}
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-red-500">
                    <Users className="h-3 w-3" /> No population
                  </span>
                )}
                {estimand && (
                  <span className="flex items-center gap-1">
                    <Shield className="h-3 w-3" /> Estimand linked
                  </span>
                )}
              </div>
            </div>
          </div>
          <div className={cn('text-sm font-bold shrink-0 ml-2', completenessColor)}>
            {completeness}%
          </div>
        </div>
      </div>

      {isExpanded && (
        <CardContent className="pt-0 border-t bg-muted/20">
          <div className="py-4 space-y-3">
            {/* Objective */}
            {endpoint.objectiveName && (
              <TraceStep
                icon={<Target className="h-4 w-4" />}
                label="Objective"
                content={endpoint.objectiveName}
                sublabel={endpoint.objectiveLevel}
                connected
              />
            )}

            {/* Endpoint */}
            <TraceStep
              icon={<Target className="h-4 w-4" />}
              label="Endpoint"
              content={endpoint.text || endpoint.name || 'Unnamed'}
              sublabel={endpoint.levelDecode}
              connected
              highlight
            />

            {/* Estimand */}
            {estimand ? (
              <TraceStep
                icon={<Shield className="h-4 w-4" />}
                label="Estimand"
                content={estimand.name || estimand.label || 'Linked estimand'}
                connected
              >
                <div className="grid grid-cols-2 gap-2 mt-2 text-xs">
                  {estimand.treatment && (
                    <div>
                      <span className="text-muted-foreground">Treatment:</span>{' '}
                      {estimand.treatment}
                    </div>
                  )}
                  {estimand.summaryMeasure && (
                    <div>
                      <span className="text-muted-foreground">Summary:</span>{' '}
                      {estimand.summaryMeasure}
                    </div>
                  )}
                  {estimand.intercurrentEvents && estimand.intercurrentEvents.length > 0 && (
                    <div className="col-span-2">
                      <span className="text-muted-foreground">ICEs:</span>{' '}
                      {estimand.intercurrentEvents.map((ice, i) => (
                        <Badge key={i} variant="outline" className="text-[10px] mr-1">
                          {ice.name} → {ice.strategy || ice.text || 'Unknown'}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
              </TraceStep>
            ) : (
              <TraceStep
                icon={<Shield className="h-4 w-4" />}
                label="Estimand"
                content="No estimand linked"
                missing
                connected
              />
            )}

            {/* Statistical Method */}
            {method ? (
              <TraceStep
                icon={<BarChart3 className="h-4 w-4" />}
                label="Analysis Method"
                content={method.name}
                connected
              >
                <div className="grid grid-cols-2 gap-2 mt-2 text-xs">
                  {method.statoCode && (
                    <div>
                      <span className="text-muted-foreground">STATO:</span>{' '}
                      <Badge variant="outline" className="text-[10px]">{method.statoCode}</Badge>
                    </div>
                  )}
                  {method.hypothesisType && (
                    <div>
                      <span className="text-muted-foreground">Hypothesis:</span>{' '}
                      {method.hypothesisType}
                    </div>
                  )}
                  {method.alphaLevel !== undefined && (
                    <div>
                      <span className="text-muted-foreground">Alpha:</span>{' '}
                      {method.alphaLevel}
                    </div>
                  )}
                  {method.covariates && method.covariates.length > 0 && (
                    <div className="col-span-2">
                      <span className="text-muted-foreground">Covariates:</span>{' '}
                      {method.covariates.join(', ')}
                    </div>
                  )}
                  {spec?.missingDataStrategy && (
                    <div className="col-span-2">
                      <span className="text-muted-foreground">Missing data:</span>{' '}
                      {spec.missingDataStrategy}
                    </div>
                  )}
                  {spec?.modelSpecification && (
                    <div className="col-span-2">
                      <span className="text-muted-foreground">Model:</span>{' '}
                      {spec.modelSpecification}
                    </div>
                  )}
                </div>
              </TraceStep>
            ) : (
              <TraceStep
                icon={<BarChart3 className="h-4 w-4" />}
                label="Analysis Method"
                content="No method linked"
                missing
                connected
              />
            )}

            {/* Population */}
            {population ? (
              <TraceStep
                icon={<Users className="h-4 w-4" />}
                label="Analysis Population"
                content={population.name}
                sublabel={population.populationType}
              />
            ) : (
              <TraceStep
                icon={<Users className="h-4 w-4" />}
                label="Analysis Population"
                content="No population linked"
                missing
              />
            )}
          </div>
        </CardContent>
      )}
    </Card>
  );
}

// ============================================================================
// Trace Step (visual step in the chain)
// ============================================================================

function TraceStep({
  icon,
  label,
  content,
  sublabel,
  children,
  connected,
  missing,
  highlight,
}: {
  icon: React.ReactNode;
  label: string;
  content: string;
  sublabel?: string;
  children?: React.ReactNode;
  connected?: boolean;
  missing?: boolean;
  highlight?: boolean;
}) {
  return (
    <div className="relative">
      {connected && (
        <div className="absolute left-[18px] -bottom-3 h-3 w-px bg-border" />
      )}
      <div
        className={cn(
          'flex items-start gap-3 p-3 rounded-lg border',
          missing
            ? 'bg-red-50/50 border-red-200 border-dashed'
            : highlight
            ? 'bg-blue-50 border-blue-200'
            : 'bg-background border-border',
        )}
      >
        <div
          className={cn(
            'w-9 h-9 rounded-full flex items-center justify-center shrink-0',
            missing ? 'bg-red-100 text-red-500' : 'bg-primary/10 text-primary',
          )}
        >
          {icon}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              {label}
            </span>
            {sublabel && (
              <Badge variant="secondary" className="text-[10px]">
                {sublabel}
              </Badge>
            )}
          </div>
          <p
            className={cn(
              'text-sm mt-0.5',
              missing ? 'text-red-500 italic' : 'font-medium',
            )}
          >
            {content}
          </p>
          {children}
        </div>
      </div>
    </div>
  );
}
