'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  ChevronDown,
  ChevronRight,
  FileBarChart,
  Users,
  FlaskConical,
  FolderTree,
  Target,
  ExternalLink,
  Database,
} from 'lucide-react';

// =============================================================================
// Types
// =============================================================================

interface Operation {
  id: string;
  name: string;
  label?: string;
  order: number;
  resultPattern?: string;
}

interface AnalysisMethod {
  id: string;
  name: string;
  label?: string;
  description?: string;
  operations?: Operation[];
  _statoMapping?: {
    code?: string;
    label?: string;
  };
}

interface AnalysisSet {
  id: string;
  name: string;
  label?: string;
  description?: string;
  level: number;
  order: number;
  condition?: { value: string };
  _usdmLinkage?: {
    populationId?: string;
    populationType?: string;
  };
}

interface AnalysisCategory {
  id: string;
  label: string;
  order: number;
  subCategorizations?: AnalysisCategorization[];
}

interface AnalysisCategorization {
  id: string;
  label: string;
  categories?: AnalysisCategory[];
}

interface Analysis {
  id: string;
  name: string;
  version: number;
  description?: string;
  reason?: { id: string; value: string; controlledTerm?: string };
  purpose?: { id: string; value: string; controlledTerm?: string };
  methodId?: string;
  analysisSetId?: string;
  categoryIds?: string[];
  _sapLinkage?: {
    endpointName?: string;
    hypothesisType?: string;
  };
}

interface ReportingEvent {
  id: string;
  name: string;
  version: number;
  description?: string;
  analysisCategorizations?: AnalysisCategorization[];
  analysisSets?: AnalysisSet[];
  analysisMethods?: AnalysisMethod[];
  analyses?: Analysis[];
}

interface ARSData {
  reportingEvent?: ReportingEvent;
}

interface ARSDataViewProps {
  protocolId: string;
}

// =============================================================================
// Main Component
// =============================================================================

export function ARSDataView({ protocolId }: ARSDataViewProps) {
  const [arsData, setArsData] = useState<ARSData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    const fetchARSData = async () => {
      try {
        setLoading(true);
        const response = await fetch(`/api/protocols/${protocolId}/ars`);
        if (!response.ok) {
          if (response.status === 404) {
            setError('ARS data not available. Run extraction with --sap flag to generate.');
            return;
          }
          throw new Error('Failed to fetch ARS data');
        }
        const data = await response.json();
        setArsData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchARSData();
  }, [protocolId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          <Database className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p>{error}</p>
        </CardContent>
      </Card>
    );
  }

  if (!arsData?.reportingEvent) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          <FileBarChart className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p>No ARS data available</p>
        </CardContent>
      </Card>
    );
  }

  const re = arsData.reportingEvent;

  return (
    <div className="space-y-4">
      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <FileBarChart className="h-5 w-5 text-purple-600" />
                CDISC ARS - {re.name}
              </CardTitle>
              <p className="text-sm text-muted-foreground mt-1">{re.description}</p>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="bg-purple-50 text-purple-700">
                v{re.version}
              </Badge>
              <a
                href="https://github.com/cdisc-org/analysis-results-standard"
                target="_blank"
                rel="noopener noreferrer"
                className="text-muted-foreground hover:text-purple-600"
              >
                <ExternalLink className="h-4 w-4" />
              </a>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid grid-cols-5 w-full">
          <TabsTrigger value="overview" className="flex items-center gap-1">
            <Target className="h-4 w-4" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="sets" className="flex items-center gap-1">
            <Users className="h-4 w-4" />
            Sets
            <Badge variant="secondary" className="ml-1 h-5 px-1">
              {re.analysisSets?.length || 0}
            </Badge>
          </TabsTrigger>
          <TabsTrigger value="methods" className="flex items-center gap-1">
            <FlaskConical className="h-4 w-4" />
            Methods
            <Badge variant="secondary" className="ml-1 h-5 px-1">
              {re.analysisMethods?.length || 0}
            </Badge>
          </TabsTrigger>
          <TabsTrigger value="analyses" className="flex items-center gap-1">
            <FileBarChart className="h-4 w-4" />
            Analyses
            <Badge variant="secondary" className="ml-1 h-5 px-1">
              {re.analyses?.length || 0}
            </Badge>
          </TabsTrigger>
          <TabsTrigger value="categories" className="flex items-center gap-1">
            <FolderTree className="h-4 w-4" />
            Categories
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-4">
          <OverviewPanel reportingEvent={re} />
        </TabsContent>

        <TabsContent value="sets" className="mt-4">
          <AnalysisSetsPanel sets={re.analysisSets || []} />
        </TabsContent>

        <TabsContent value="methods" className="mt-4">
          <MethodsPanel methods={re.analysisMethods || []} />
        </TabsContent>

        <TabsContent value="analyses" className="mt-4">
          <AnalysesPanel 
            analyses={re.analyses || []} 
            methods={re.analysisMethods || []}
            sets={re.analysisSets || []}
          />
        </TabsContent>

        <TabsContent value="categories" className="mt-4">
          <CategoriesPanel categorizations={re.analysisCategorizations || []} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

// =============================================================================
// Overview Panel
// =============================================================================

function OverviewPanel({ reportingEvent }: { reportingEvent: ReportingEvent }) {
  const stats = [
    { label: 'Analysis Sets', value: reportingEvent.analysisSets?.length || 0, icon: Users },
    { label: 'Methods', value: reportingEvent.analysisMethods?.length || 0, icon: FlaskConical },
    { label: 'Analyses', value: reportingEvent.analyses?.length || 0, icon: FileBarChart },
    { label: 'Categorizations', value: reportingEvent.analysisCategorizations?.length || 0, icon: FolderTree },
  ];

  // Count analyses by reason
  const byReason: Record<string, number> = {};
  reportingEvent.analyses?.forEach(a => {
    const reason = a.reason?.value || 'Unclassified';
    byReason[reason] = (byReason[reason] || 0) + 1;
  });

  return (
    <div className="space-y-4">
      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {stats.map(stat => (
          <Card key={stat.label}>
            <CardContent className="pt-4">
              <div className="flex items-center gap-2">
                <stat.icon className="h-5 w-5 text-muted-foreground" />
                <span className="text-2xl font-bold">{stat.value}</span>
              </div>
              <p className="text-sm text-muted-foreground mt-1">{stat.label}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Analyses by Reason */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Analyses by Reason</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {Object.entries(byReason).map(([reason, count]) => (
              <Badge 
                key={reason} 
                variant="outline"
                className={
                  reason.includes('PRIMARY') ? 'bg-green-50 text-green-700 border-green-200' :
                  reason.includes('SENSITIVITY') ? 'bg-blue-50 text-blue-700 border-blue-200' :
                  reason.includes('EXPLORATORY') ? 'bg-amber-50 text-amber-700 border-amber-200' :
                  ''
                }
              >
                {reason}: {count}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* STATO Coverage */}
      {reportingEvent.analysisMethods && reportingEvent.analysisMethods.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">STATO Ontology Coverage</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {reportingEvent.analysisMethods
                .filter(m => m._statoMapping?.code)
                .map(m => (
                  <a
                    key={m.id}
                    href={`http://purl.obolibrary.org/obo/${m._statoMapping?.code?.replace(':', '_')}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hover:opacity-80"
                  >
                    <Badge variant="outline" className="flex items-center gap-1">
                      {m.label || m.name}: {m._statoMapping?.code}
                      <ExternalLink className="h-3 w-3" />
                    </Badge>
                  </a>
                ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// =============================================================================
// Analysis Sets Panel
// =============================================================================

function AnalysisSetsPanel({ sets }: { sets: AnalysisSet[] }) {
  if (sets.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          <Users className="h-8 w-8 mx-auto mb-2" />
          No analysis sets defined
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      {sets.map(set => (
        <Card key={set.id}>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                {set.name}
                {set._usdmLinkage?.populationType && (
                  <Badge variant="secondary">{set._usdmLinkage.populationType}</Badge>
                )}
              </CardTitle>
              <Badge variant="outline">Order: {set.order}</Badge>
            </div>
          </CardHeader>
          <CardContent>
            {set.description && <p className="text-sm mb-2">{set.description}</p>}
            {set.condition?.value && (
              <div className="bg-muted p-2 rounded text-sm font-mono">
                {set.condition.value}
              </div>
            )}
            {set._usdmLinkage?.populationId && (
              <p className="text-xs text-muted-foreground mt-2">
                USDM Population ID: {set._usdmLinkage.populationId}
              </p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// =============================================================================
// Methods Panel
// =============================================================================

function MethodsPanel({ methods }: { methods: AnalysisMethod[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);

  if (methods.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          <FlaskConical className="h-8 w-8 mx-auto mb-2" />
          No analysis methods defined
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      {methods.map(method => (
        <Card key={method.id} className="overflow-hidden">
          <div
            className="p-4 cursor-pointer hover:bg-muted/50 transition-colors"
            onClick={() => setExpanded(expanded === method.id ? null : method.id)}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {expanded === method.id ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{method.label || method.name}</span>
                    {method._statoMapping?.code && (
                      <a
                        href={`http://purl.obolibrary.org/obo/${method._statoMapping.code.replace(':', '_')}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-500 hover:text-blue-700"
                        onClick={e => e.stopPropagation()}
                      >
                        <Badge variant="outline" className="flex items-center gap-1">
                          {method._statoMapping.code}
                          <ExternalLink className="h-3 w-3" />
                        </Badge>
                      </a>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">{method.name}</p>
                </div>
              </div>
              <Badge variant="secondary">
                {method.operations?.length || 0} operations
              </Badge>
            </div>
          </div>

          {expanded === method.id && method.operations && method.operations.length > 0 && (
            <CardContent className="pt-0 border-t bg-muted/30">
              <div className="mt-4">
                <h4 className="text-sm font-medium mb-2">Operations</h4>
                <div className="space-y-2">
                  {method.operations
                    .sort((a, b) => a.order - b.order)
                    .map(op => (
                      <div
                        key={op.id}
                        className="flex items-center justify-between p-2 bg-background rounded"
                      >
                        <div>
                          <span className="font-medium">{op.label || op.name}</span>
                          <span className="text-muted-foreground ml-2 text-sm">({op.name})</span>
                        </div>
                        <Badge variant="outline">#{op.order}</Badge>
                      </div>
                    ))}
                </div>
              </div>
            </CardContent>
          )}
        </Card>
      ))}
    </div>
  );
}

// =============================================================================
// Analyses Panel
// =============================================================================

function AnalysesPanel({ 
  analyses, 
  methods, 
  sets 
}: { 
  analyses: Analysis[]; 
  methods: AnalysisMethod[];
  sets: AnalysisSet[];
}) {
  const [expanded, setExpanded] = useState<string | null>(null);

  // Build lookup maps
  const methodMap = Object.fromEntries(methods.map(m => [m.id, m]));
  const setMap = Object.fromEntries(sets.map(s => [s.id, s]));

  if (analyses.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          <FileBarChart className="h-8 w-8 mx-auto mb-2" />
          No analyses defined
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      {analyses.map(analysis => {
        const method = analysis.methodId ? methodMap[analysis.methodId] : null;
        const set = analysis.analysisSetId ? setMap[analysis.analysisSetId] : null;

        return (
          <Card key={analysis.id} className="overflow-hidden">
            <div
              className="p-4 cursor-pointer hover:bg-muted/50 transition-colors"
              onClick={() => setExpanded(expanded === analysis.id ? null : analysis.id)}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {expanded === analysis.id ? (
                    <ChevronDown className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                  <div>
                    <span className="font-medium">{analysis.name}</span>
                    {analysis._sapLinkage?.endpointName && (
                      <p className="text-sm text-muted-foreground">
                        {analysis._sapLinkage.endpointName}
                      </p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {analysis.reason && (
                    <Badge
                      variant="outline"
                      className={
                        analysis.reason.value.includes('PRIMARY')
                          ? 'bg-green-50 text-green-700 border-green-200'
                          : analysis.reason.value.includes('SENSITIVITY')
                          ? 'bg-blue-50 text-blue-700 border-blue-200'
                          : 'bg-amber-50 text-amber-700 border-amber-200'
                      }
                    >
                      {analysis.reason.value}
                    </Badge>
                  )}
                </div>
              </div>
            </div>

            {expanded === analysis.id && (
              <CardContent className="pt-0 border-t bg-muted/30">
                <dl className="grid grid-cols-2 gap-4 text-sm mt-4">
                  {analysis.description && (
                    <div className="col-span-2">
                      <dt className="font-medium text-muted-foreground">Description</dt>
                      <dd className="mt-1">{analysis.description}</dd>
                    </div>
                  )}
                  {method && (
                    <div>
                      <dt className="font-medium text-muted-foreground">Method</dt>
                      <dd className="mt-1">{method.label || method.name}</dd>
                    </div>
                  )}
                  {set && (
                    <div>
                      <dt className="font-medium text-muted-foreground">Analysis Set</dt>
                      <dd className="mt-1">{set.name}</dd>
                    </div>
                  )}
                  {analysis._sapLinkage?.hypothesisType && (
                    <div>
                      <dt className="font-medium text-muted-foreground">Hypothesis Type</dt>
                      <dd className="mt-1 capitalize">{analysis._sapLinkage.hypothesisType}</dd>
                    </div>
                  )}
                  {analysis.purpose && (
                    <div>
                      <dt className="font-medium text-muted-foreground">Purpose</dt>
                      <dd className="mt-1">{analysis.purpose.value}</dd>
                    </div>
                  )}
                </dl>
              </CardContent>
            )}
          </Card>
        );
      })}
    </div>
  );
}

// =============================================================================
// Categories Panel
// =============================================================================

function CategoriesPanel({ categorizations }: { categorizations: AnalysisCategorization[] }) {
  if (categorizations.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          <FolderTree className="h-8 w-8 mx-auto mb-2" />
          No categorizations defined
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {categorizations.map(cat => (
        <Card key={cat.id}>
          <CardHeader>
            <CardTitle className="text-base">{cat.label}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {cat.categories?.map(c => (
                <Badge key={c.id} variant="outline">
                  {c.order}. {c.label}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export default ARSDataView;
