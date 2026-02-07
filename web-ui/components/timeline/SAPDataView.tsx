'use client';

import { useState, useMemo } from 'react';
import { 
  Users, 
  Calculator, 
  ClipboardList,
  BarChart3,
  Layers,
  FlaskConical,
  GitBranch,
  Clock,
  Hash,
  Activity,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Info,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { usePatchedStudyDesign } from '@/hooks/usePatchedUsdm';
import { EditableField } from '@/components/semantic';

// Types for SAP data
interface AnalysisPopulation {
  id: string;
  name: string;
  label?: string;
  text?: string;
  populationType?: string;
  populationDescription?: string;
  criteria?: string;
}

interface StatisticalMethod {
  id: string;
  name: string;
  description?: string;
  endpointName?: string;
  statoCode?: string;
  statoLabel?: string;
  hypothesisType?: string;
  testType?: string;
  alphaLevel?: number;
  covariates?: string[];
  software?: string;
  // CDISC ARS linkage
  arsMethodId?: string;
  arsOperationId?: string;
  arsReason?: string;
}

interface MultiplicityAdjustment {
  id: string;
  name: string;
  description?: string;
  methodType?: string;
  statoCode?: string;
  overallAlpha?: number;
  endpointsCovered?: string[];
  hierarchy?: string;
}

interface SensitivityAnalysis {
  id: string;
  name: string;
  description?: string;
  primaryEndpoint?: string;
  analysisType?: string;
  methodVariation?: string;
  population?: string;
  // CDISC ARS linkage
  arsReason?: string;
  arsAnalysisId?: string;
}

interface SubgroupAnalysis {
  id: string;
  name: string;
  description?: string;
  subgroupVariable?: string;
  categories?: string[];
  endpoints?: string[];
  interactionTest?: boolean;
}

interface InterimAnalysis {
  id: string;
  name: string;
  description?: string;
  timing?: string;
  informationFraction?: number;
  stoppingRuleEfficacy?: string;
  stoppingRuleFutility?: string;
  // CDISC ARS linkage
  arsReportingEventType?: string;
  alphaSpent?: number;
  spendingFunction?: string;
}

interface SampleSizeCalculation {
  id: string;
  name: string;
  description?: string;
  targetSampleSize?: number;
  power?: number;
  alpha?: number;
  effectSize?: string;
  dropoutRate?: number;
  assumptions?: string;
}

interface DerivedVariable {
  id: string;
  name: string;
  formula?: string;
  unit?: string;
  notes?: string;
}

interface DataHandlingRule {
  id: string;
  name: string;
  rule?: string;
}

interface SAPData {
  analysisPopulations?: AnalysisPopulation[];
  statisticalMethods?: StatisticalMethod[];
  multiplicityAdjustments?: MultiplicityAdjustment[];
  sensitivityAnalyses?: SensitivityAnalysis[];
  subgroupAnalyses?: SubgroupAnalysis[];
  interimAnalyses?: InterimAnalysis[];
  sampleSizeCalculations?: SampleSizeCalculation[];
  derivedVariables?: DerivedVariable[];
  dataHandlingRules?: DataHandlingRule[];
}

type TabId = 'overview' | 'populations' | 'methods' | 'multiplicity' | 'sensitivity' | 'subgroups' | 'interim' | 'samplesize' | 'derived' | 'handling';

export function SAPDataView() {
  const [activeTab, setActiveTab] = useState<TabId>('overview');

  // Use patched study design to show draft changes
  const studyDesign = usePatchedStudyDesign();
  
  // Extract SAP data from USDM
  const sapData = useMemo(() => {
    const data: SAPData = {};
    
    // Get analysis populations from core USDM
    const populations = studyDesign?.analysisPopulations as AnalysisPopulation[] | undefined;
    if (populations && populations.length > 0) {
      data.analysisPopulations = populations;
    }
    
    // Get SAP extensions
    const extensions = (studyDesign?.extensionAttributes ?? []) as Array<{
      url?: string;
      valueString?: string;
    }>;
    
    for (const ext of extensions) {
      const url = ext?.url ?? '';
      
      if (url.includes('x-sap-statistical-methods') && ext?.valueString) {
        try { data.statisticalMethods = JSON.parse(ext.valueString); } catch { /* ignore */ }
      }
      if (url.includes('x-sap-multiplicity-adjustments') && ext?.valueString) {
        try { data.multiplicityAdjustments = JSON.parse(ext.valueString); } catch { /* ignore */ }
      }
      if (url.includes('x-sap-sensitivity-analyses') && ext?.valueString) {
        try { data.sensitivityAnalyses = JSON.parse(ext.valueString); } catch { /* ignore */ }
      }
      if (url.includes('x-sap-subgroup-analyses') && ext?.valueString) {
        try { data.subgroupAnalyses = JSON.parse(ext.valueString); } catch { /* ignore */ }
      }
      if (url.includes('x-sap-interim-analyses') && ext?.valueString) {
        try { data.interimAnalyses = JSON.parse(ext.valueString); } catch { /* ignore */ }
      }
      if (url.includes('x-sap-sample-size-calculations') && ext?.valueString) {
        try { data.sampleSizeCalculations = JSON.parse(ext.valueString); } catch { /* ignore */ }
      }
      if (url.includes('x-sap-derived-variables') && ext?.valueString) {
        try { data.derivedVariables = JSON.parse(ext.valueString); } catch { /* ignore */ }
      }
      if (url.includes('x-sap-data-handling-rules') && ext?.valueString) {
        try { data.dataHandlingRules = JSON.parse(ext.valueString); } catch { /* ignore */ }
      }
    }
    
    return data;
  }, [studyDesign]);

  const tabs = [
    { id: 'overview' as TabId, label: 'Overview', icon: <Activity className="h-4 w-4" /> },
    { id: 'populations' as TabId, label: 'Populations', icon: <Users className="h-4 w-4" />, count: sapData.analysisPopulations?.length },
    { id: 'methods' as TabId, label: 'Statistical Methods', icon: <BarChart3 className="h-4 w-4" />, count: sapData.statisticalMethods?.length },
    { id: 'multiplicity' as TabId, label: 'Multiplicity', icon: <Layers className="h-4 w-4" />, count: sapData.multiplicityAdjustments?.length },
    { id: 'sensitivity' as TabId, label: 'Sensitivity', icon: <FlaskConical className="h-4 w-4" />, count: sapData.sensitivityAnalyses?.length },
    { id: 'subgroups' as TabId, label: 'Subgroups', icon: <GitBranch className="h-4 w-4" />, count: sapData.subgroupAnalyses?.length },
    { id: 'interim' as TabId, label: 'Interim', icon: <Clock className="h-4 w-4" />, count: sapData.interimAnalyses?.length },
    { id: 'samplesize' as TabId, label: 'Sample Size', icon: <Hash className="h-4 w-4" />, count: sapData.sampleSizeCalculations?.length },
    { id: 'derived' as TabId, label: 'Derived Vars', icon: <Calculator className="h-4 w-4" />, count: sapData.derivedVariables?.length },
    { id: 'handling' as TabId, label: 'Data Handling', icon: <ClipboardList className="h-4 w-4" />, count: sapData.dataHandlingRules?.length },
  ];

  // Check if any SAP data exists
  const hasSAPData = Object.values(sapData).some(arr => arr && arr.length > 0);

  if (!hasSAPData) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <BarChart3 className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
          <h3 className="text-lg font-semibold mb-2">No SAP Data Available</h3>
          <p className="text-muted-foreground">
            Statistical Analysis Plan data has not been extracted for this protocol.
          </p>
          <p className="text-sm text-muted-foreground mt-2">
            Run extraction with --sap flag to include SAP analysis.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Tab Navigation */}
      <div className="flex flex-wrap gap-2 p-1 bg-muted rounded-lg">
        {tabs.map(tab => (
          <Button
            key={tab.id}
            variant={activeTab === tab.id ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setActiveTab(tab.id)}
            className="flex items-center gap-2"
            disabled={tab.count === undefined && tab.id !== 'overview' ? true : (tab.count === 0 && tab.id !== 'overview')}
          >
            {tab.icon}
            <span className="hidden sm:inline">{tab.label}</span>
            {tab.count !== undefined && tab.count > 0 && (
              <Badge variant="secondary" className="ml-1 h-5 px-1.5 text-xs">
                {tab.count}
              </Badge>
            )}
          </Button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="min-h-[400px]">
        {activeTab === 'overview' && <OverviewPanel data={sapData} />}
        {activeTab === 'populations' && <PopulationsPanel populations={sapData.analysisPopulations ?? []} />}
        {activeTab === 'methods' && <StatisticalMethodsPanel methods={sapData.statisticalMethods ?? []} />}
        {activeTab === 'multiplicity' && <MultiplicityPanel adjustments={sapData.multiplicityAdjustments ?? []} />}
        {activeTab === 'sensitivity' && <SensitivityPanel analyses={sapData.sensitivityAnalyses ?? []} />}
        {activeTab === 'subgroups' && <SubgroupsPanel analyses={sapData.subgroupAnalyses ?? []} />}
        {activeTab === 'interim' && <InterimPanel analyses={sapData.interimAnalyses ?? []} />}
        {activeTab === 'samplesize' && <SampleSizePanel calculations={sapData.sampleSizeCalculations ?? []} />}
        {activeTab === 'derived' && <DerivedVariablesPanel variables={sapData.derivedVariables ?? []} />}
        {activeTab === 'handling' && <DataHandlingPanel rules={sapData.dataHandlingRules ?? []} />}
      </div>
    </div>
  );
}

// ============================================================================
// Overview Panel
// ============================================================================

function OverviewPanel({ data }: { data: SAPData }) {
  const stats = [
    { label: 'Analysis Populations', value: data.analysisPopulations?.length ?? 0, icon: <Users className="h-5 w-5" />, color: 'bg-blue-500' },
    { label: 'Statistical Methods', value: data.statisticalMethods?.length ?? 0, icon: <BarChart3 className="h-5 w-5" />, color: 'bg-green-500' },
    { label: 'Sensitivity Analyses', value: data.sensitivityAnalyses?.length ?? 0, icon: <FlaskConical className="h-5 w-5" />, color: 'bg-amber-500' },
    { label: 'Subgroup Analyses', value: data.subgroupAnalyses?.length ?? 0, icon: <GitBranch className="h-5 w-5" />, color: 'bg-purple-500' },
    { label: 'Interim Analyses', value: data.interimAnalyses?.length ?? 0, icon: <Clock className="h-5 w-5" />, color: 'bg-pink-500' },
    { label: 'Derived Variables', value: data.derivedVariables?.length ?? 0, icon: <Calculator className="h-5 w-5" />, color: 'bg-cyan-500' },
  ];

  // Count STATO-mapped methods
  const statoMappedCount = data.statisticalMethods?.filter(m => m.statoCode)?.length ?? 0;

  return (
    <div className="space-y-6">
      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {stats.map(stat => (
          <Card key={stat.label}>
            <CardContent className="pt-6">
              <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center text-white mb-3', stat.color)}>
                {stat.icon}
              </div>
              <p className="text-2xl font-bold">{stat.value}</p>
              <p className="text-sm text-muted-foreground">{stat.label}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* STATO Mapping Summary */}
      {data.statisticalMethods && data.statisticalMethods.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5" />
              STATO Ontology Mapping
            </CardTitle>
            <CardDescription>
              Statistical methods mapped to STATO codes for interoperability
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4 mb-4">
              <div className="flex-1 bg-muted rounded-full h-3 overflow-hidden">
                <div 
                  className="bg-green-500 h-full transition-all"
                  style={{ width: `${(statoMappedCount / data.statisticalMethods.length) * 100}%` }}
                />
              </div>
              <span className="text-sm font-medium">
                {statoMappedCount}/{data.statisticalMethods.length} mapped
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {data.statisticalMethods.filter(m => m.statoCode).map(method => (
                <Badge key={method.id} variant="outline" className="flex items-center gap-1">
                  <span>{method.name}</span>
                  <a 
                    href={`http://purl.obolibrary.org/obo/${method.statoCode?.replace(':', '_')}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-500 hover:text-blue-700"
                  >
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Population Types Summary */}
      {data.analysisPopulations && data.analysisPopulations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="h-5 w-5" />
              Analysis Populations
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {data.analysisPopulations.map(pop => (
                <div key={pop.id} className="p-3 bg-muted rounded-lg">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant="outline" className="text-xs">{pop.label || pop.populationType}</Badge>
                  </div>
                  <p className="font-medium text-sm">{pop.name}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ============================================================================
// Populations Panel
// ============================================================================

function PopulationsPanel({ populations }: { populations: AnalysisPopulation[] }) {
  const basePath = '/study/versions/0/studyDesigns/0/analysisPopulations';
  const [expanded, setExpanded] = useState<string | null>(null);

  const populationTypeColors: Record<string, string> = {
    'Screened': 'bg-gray-100 text-gray-800',
    'Enrolled': 'bg-blue-100 text-blue-800',
    'FullAnalysis': 'bg-green-100 text-green-800',
    'PerProtocol': 'bg-purple-100 text-purple-800',
    'Safety': 'bg-red-100 text-red-800',
    'Pharmacokinetic': 'bg-amber-100 text-amber-800',
    'Pharmacodynamic': 'bg-cyan-100 text-cyan-800',
  };

  return (
    <div className="space-y-3">
      {populations.map(pop => (
        <Card key={pop.id} className="overflow-hidden">
          <div 
            className="p-4 cursor-pointer hover:bg-muted/50 transition-colors"
            onClick={() => setExpanded(expanded === pop.id ? null : pop.id)}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {expanded === pop.id ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <EditableField
                      path={`${basePath}/${populations.indexOf(pop)}/name`}
                      value={pop.name}
                      label=""
                    />
                    {pop.label && <Badge variant="secondary">{pop.label}</Badge>}
                  </div>
                  <p className="text-sm text-muted-foreground">{pop.criteria || pop.populationType}</p>
                </div>
              </div>
              {pop.populationType && (
                <Badge className={populationTypeColors[pop.populationType] || 'bg-gray-100'}>
                  {pop.populationType}
                </Badge>
              )}
            </div>
          </div>
          {expanded === pop.id && (
            <CardContent className="pt-0 border-t bg-muted/30">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm mt-4">
                <div className="md:col-span-2">
                  <EditableField
                    path={`${basePath}/${populations.indexOf(pop)}/populationDescription`}
                    value={pop.populationDescription || ''}
                    label="Definition"
                    type="textarea"
                    placeholder="No definition specified"
                  />
                </div>
                <div className="md:col-span-2">
                  <EditableField
                    path={`${basePath}/${populations.indexOf(pop)}/text`}
                    value={pop.text || ''}
                    label="Description"
                    type="textarea"
                    placeholder="No description specified"
                  />
                </div>
                <div>
                  <EditableField
                    path={`${basePath}/${populations.indexOf(pop)}/criteria`}
                    value={pop.criteria || ''}
                    label="Criteria"
                    placeholder="No criteria specified"
                  />
                </div>
                <div>
                  <EditableField
                    path={`${basePath}/${populations.indexOf(pop)}/label`}
                    value={pop.label || ''}
                    label="Label"
                    placeholder="No label specified"
                  />
                </div>
              </div>
            </CardContent>
          )}
        </Card>
      ))}
    </div>
  );
}

// ============================================================================
// Statistical Methods Panel
// ============================================================================

function StatisticalMethodsPanel({ methods }: { methods: StatisticalMethod[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);

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
                {expanded === method.id ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{method.name}</span>
                    {method.statoCode && (
                      <a 
                        href={`http://purl.obolibrary.org/obo/${method.statoCode.replace(':', '_')}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-500 hover:text-blue-700"
                        onClick={e => e.stopPropagation()}
                      >
                        <Badge variant="outline" className="flex items-center gap-1">
                          {method.statoCode}
                          <ExternalLink className="h-3 w-3" />
                        </Badge>
                      </a>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">{method.endpointName || method.description?.substring(0, 80)}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {method.hypothesisType && <Badge variant="secondary">{method.hypothesisType}</Badge>}
                {method.testType && <Badge variant="outline">{method.testType}</Badge>}
              </div>
            </div>
          </div>
          {expanded === method.id && (
            <CardContent className="pt-0 border-t bg-muted/30">
              <dl className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm mt-4">
                {method.description && (
                  <div className="md:col-span-2">
                    <dt className="font-medium text-muted-foreground">Description</dt>
                    <dd className="mt-1">{method.description}</dd>
                  </div>
                )}
                {method.alphaLevel !== undefined && (
                  <div>
                    <dt className="font-medium text-muted-foreground">Alpha Level</dt>
                    <dd className="mt-1">{method.alphaLevel}</dd>
                  </div>
                )}
                {method.covariates && method.covariates.length > 0 && (
                  <div>
                    <dt className="font-medium text-muted-foreground">Covariates</dt>
                    <dd className="mt-1 flex flex-wrap gap-1">
                      {method.covariates.map((c, i) => (
                        <Badge key={i} variant="secondary">{c}</Badge>
                      ))}
                    </dd>
                  </div>
                )}
                {method.software && (
                  <div>
                    <dt className="font-medium text-muted-foreground">Software</dt>
                    <dd className="mt-1">{method.software}</dd>
                  </div>
                )}
                {method.statoLabel && (
                  <div>
                    <dt className="font-medium text-muted-foreground">STATO Label</dt>
                    <dd className="mt-1">{method.statoLabel}</dd>
                  </div>
                )}
                {/* CDISC ARS Linkage */}
                {(method.arsOperationId || method.arsReason) && (
                  <div className="md:col-span-2 mt-2 pt-2 border-t">
                    <dt className="font-medium text-muted-foreground flex items-center gap-2">
                      <span className="text-purple-600">CDISC ARS</span>
                    </dt>
                    <dd className="mt-1 flex flex-wrap gap-2">
                      {method.arsOperationId && (
                        <Badge variant="outline" className="bg-purple-50 text-purple-700 border-purple-200">
                          Operation: {method.arsOperationId}
                        </Badge>
                      )}
                      {method.arsReason && (
                        <Badge variant="outline" className="bg-purple-50 text-purple-700 border-purple-200">
                          Reason: {method.arsReason}
                        </Badge>
                      )}
                    </dd>
                  </div>
                )}
              </dl>
            </CardContent>
          )}
        </Card>
      ))}
    </div>
  );
}

// ============================================================================
// Multiplicity Panel
// ============================================================================

function MultiplicityPanel({ adjustments }: { adjustments: MultiplicityAdjustment[] }) {
  if (adjustments.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          <Layers className="h-8 w-8 mx-auto mb-2" />
          No multiplicity adjustments specified in SAP
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      {adjustments.map(adj => (
        <Card key={adj.id}>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              {adj.name}
              {adj.methodType && <Badge variant="outline">{adj.methodType}</Badge>}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm mb-3">{adj.description}</p>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              {adj.overallAlpha !== undefined && (
                <div>
                  <dt className="text-muted-foreground">Overall Alpha</dt>
                  <dd className="font-medium">{adj.overallAlpha}</dd>
                </div>
              )}
              {adj.hierarchy && (
                <div className="col-span-2">
                  <dt className="text-muted-foreground">Testing Hierarchy</dt>
                  <dd>{adj.hierarchy}</dd>
                </div>
              )}
              {adj.endpointsCovered && adj.endpointsCovered.length > 0 && (
                <div className="col-span-2">
                  <dt className="text-muted-foreground">Endpoints Covered</dt>
                  <dd className="flex flex-wrap gap-1 mt-1">
                    {adj.endpointsCovered.map((e, i) => (
                      <Badge key={i} variant="secondary">{e}</Badge>
                    ))}
                  </dd>
                </div>
              )}
            </dl>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// ============================================================================
// Sensitivity Panel
// ============================================================================

function SensitivityPanel({ analyses }: { analyses: SensitivityAnalysis[] }) {
  if (analyses.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          <FlaskConical className="h-8 w-8 mx-auto mb-2" />
          No sensitivity analyses specified in SAP
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      {analyses.map(analysis => (
        <Card key={analysis.id}>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              {analysis.name}
              {analysis.analysisType && <Badge variant="outline">{analysis.analysisType}</Badge>}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm mb-3">{analysis.description}</p>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              {analysis.primaryEndpoint && (
                <div>
                  <dt className="text-muted-foreground">Primary Endpoint</dt>
                  <dd className="font-medium">{analysis.primaryEndpoint}</dd>
                </div>
              )}
              {analysis.population && (
                <div>
                  <dt className="text-muted-foreground">Population</dt>
                  <dd>{analysis.population}</dd>
                </div>
              )}
              {analysis.methodVariation && (
                <div className="col-span-2">
                  <dt className="text-muted-foreground">Method Variation</dt>
                  <dd>{analysis.methodVariation}</dd>
                </div>
              )}
              {/* CDISC ARS Linkage */}
              {analysis.arsReason && (
                <div className="col-span-2 mt-2 pt-2 border-t">
                  <dt className="text-muted-foreground">CDISC ARS</dt>
                  <dd className="mt-1">
                    <Badge variant="outline" className="bg-purple-50 text-purple-700 border-purple-200">
                      Reason: {analysis.arsReason}
                    </Badge>
                  </dd>
                </div>
              )}
            </dl>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// ============================================================================
// Subgroups Panel
// ============================================================================

function SubgroupsPanel({ analyses }: { analyses: SubgroupAnalysis[] }) {
  if (analyses.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          <GitBranch className="h-8 w-8 mx-auto mb-2" />
          No subgroup analyses specified in SAP
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      {analyses.map(analysis => (
        <Card key={analysis.id}>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              {analysis.name}
              {analysis.interactionTest && <Badge variant="secondary">Interaction Test</Badge>}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm mb-3">{analysis.description}</p>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              {analysis.subgroupVariable && (
                <div>
                  <dt className="text-muted-foreground">Subgroup Variable</dt>
                  <dd className="font-medium">{analysis.subgroupVariable}</dd>
                </div>
              )}
              {analysis.categories && analysis.categories.length > 0 && (
                <div className="col-span-2">
                  <dt className="text-muted-foreground">Categories</dt>
                  <dd className="flex flex-wrap gap-1 mt-1">
                    {analysis.categories.map((c, i) => (
                      <Badge key={i} variant="outline">{c}</Badge>
                    ))}
                  </dd>
                </div>
              )}
              {analysis.endpoints && analysis.endpoints.length > 0 && (
                <div className="col-span-2">
                  <dt className="text-muted-foreground">Endpoints</dt>
                  <dd className="flex flex-wrap gap-1 mt-1">
                    {analysis.endpoints.map((e, i) => (
                      <Badge key={i} variant="secondary">{e}</Badge>
                    ))}
                  </dd>
                </div>
              )}
            </dl>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// ============================================================================
// Interim Panel
// ============================================================================

function InterimPanel({ analyses }: { analyses: InterimAnalysis[] }) {
  if (analyses.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          <Clock className="h-8 w-8 mx-auto mb-2" />
          No interim analyses specified in SAP
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      {analyses.map(analysis => (
        <Card key={analysis.id}>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              {analysis.name}
              {analysis.timing && <Badge variant="outline">{analysis.timing}</Badge>}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm mb-3">{analysis.description}</p>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              {analysis.informationFraction !== undefined && (
                <div>
                  <dt className="text-muted-foreground">Information Fraction</dt>
                  <dd className="font-medium">{(analysis.informationFraction * 100).toFixed(0)}%</dd>
                </div>
              )}
              {analysis.alphaSpent !== undefined && (
                <div>
                  <dt className="text-muted-foreground">Alpha Spent</dt>
                  <dd className="font-medium">{analysis.alphaSpent}</dd>
                </div>
              )}
              {analysis.spendingFunction && (
                <div>
                  <dt className="text-muted-foreground">Spending Function</dt>
                  <dd>{analysis.spendingFunction}</dd>
                </div>
              )}
              {analysis.stoppingRuleEfficacy && (
                <div className="col-span-2">
                  <dt className="text-muted-foreground">Efficacy Stopping Rule</dt>
                  <dd className="bg-green-50 p-2 rounded text-green-800">{analysis.stoppingRuleEfficacy}</dd>
                </div>
              )}
              {analysis.stoppingRuleFutility && (
                <div className="col-span-2">
                  <dt className="text-muted-foreground">Futility Stopping Rule</dt>
                  <dd className="bg-amber-50 p-2 rounded text-amber-800">{analysis.stoppingRuleFutility}</dd>
                </div>
              )}
              {/* CDISC ARS Linkage */}
              {analysis.arsReportingEventType && (
                <div className="col-span-2 mt-2 pt-2 border-t">
                  <dt className="text-muted-foreground">CDISC ARS</dt>
                  <dd className="mt-1">
                    <Badge variant="outline" className="bg-purple-50 text-purple-700 border-purple-200">
                      ReportingEvent: {analysis.arsReportingEventType}
                    </Badge>
                  </dd>
                </div>
              )}
            </dl>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// ============================================================================
// Sample Size Panel
// ============================================================================

function SampleSizePanel({ calculations }: { calculations: SampleSizeCalculation[] }) {
  if (calculations.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          <Hash className="h-8 w-8 mx-auto mb-2" />
          No sample size calculations specified in SAP
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      {calculations.map(calc => (
        <Card key={calc.id}>
          <CardHeader>
            <CardTitle className="text-base">{calc.name}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm mb-3">{calc.description}</p>
            <dl className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              {calc.targetSampleSize !== undefined && (
                <div>
                  <dt className="text-muted-foreground">Target N</dt>
                  <dd className="text-2xl font-bold">{calc.targetSampleSize}</dd>
                </div>
              )}
              {calc.power !== undefined && (
                <div>
                  <dt className="text-muted-foreground">Power</dt>
                  <dd className="text-2xl font-bold">{(calc.power * 100).toFixed(0)}%</dd>
                </div>
              )}
              {calc.alpha !== undefined && (
                <div>
                  <dt className="text-muted-foreground">Alpha</dt>
                  <dd className="text-2xl font-bold">{calc.alpha}</dd>
                </div>
              )}
              {calc.dropoutRate !== undefined && (
                <div>
                  <dt className="text-muted-foreground">Dropout Rate</dt>
                  <dd className="text-2xl font-bold">{(calc.dropoutRate * 100).toFixed(0)}%</dd>
                </div>
              )}
            </dl>
            {(calc.effectSize || calc.assumptions) && (
              <div className="mt-4 pt-4 border-t text-sm">
                {calc.effectSize && (
                  <div className="mb-2">
                    <span className="text-muted-foreground">Effect Size: </span>
                    <span>{calc.effectSize}</span>
                  </div>
                )}
                {calc.assumptions && (
                  <div>
                    <span className="text-muted-foreground">Assumptions: </span>
                    <span>{calc.assumptions}</span>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// ============================================================================
// Derived Variables Panel
// ============================================================================

function DerivedVariablesPanel({ variables }: { variables: DerivedVariable[] }) {
  if (variables.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          <Calculator className="h-8 w-8 mx-auto mb-2" />
          No derived variables specified in SAP
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      {variables.map(variable => (
        <Card key={variable.id}>
          <CardContent className="pt-6">
            <div className="flex items-start justify-between mb-2">
              <h4 className="font-medium">{variable.name}</h4>
              {variable.unit && <Badge variant="outline">{variable.unit}</Badge>}
            </div>
            {variable.formula && (
              <div className="bg-muted p-3 rounded-lg font-mono text-sm">
                {variable.formula}
              </div>
            )}
            {variable.notes && (
              <p className="text-sm text-muted-foreground mt-2 flex items-start gap-1">
                <Info className="h-4 w-4 mt-0.5 flex-shrink-0" />
                {variable.notes}
              </p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// ============================================================================
// Data Handling Panel
// ============================================================================

function DataHandlingPanel({ rules }: { rules: DataHandlingRule[] }) {
  if (rules.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          <ClipboardList className="h-8 w-8 mx-auto mb-2" />
          No data handling rules specified in SAP
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      {rules.map(rule => (
        <Card key={rule.id}>
          <CardContent className="pt-6">
            <h4 className="font-medium mb-2">{rule.name}</h4>
            <p className="text-sm text-muted-foreground">{rule.rule}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
