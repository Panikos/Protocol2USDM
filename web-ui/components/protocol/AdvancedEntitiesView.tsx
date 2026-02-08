'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { EditableField, EditableCodedValue, CDISC_TERMINOLOGIES } from '@/components/semantic';
import { 
  Microscope, 
  Pill,
  Target,
  Beaker,
  FileText,
  Users,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';

interface AdvancedEntitiesViewProps {
  usdm: Record<string, unknown> | null;
}

interface Indication {
  id: string;
  name?: string;
  description?: string;
  codes?: { code: string; decode?: string }[];
  instanceType?: string;
}

interface BiomedicalConcept {
  id: string;
  name?: string;
  synonyms?: string[];
  reference?: string;
  instanceType?: string;
}

interface IntercurrentEvent {
  id: string;
  name: string;
  text?: string;  // USDM 4.0 required
  description?: string;
  strategy?: string;  // USDM 4.0: string, not Code object
}

interface Estimand {
  id: string;
  name?: string;
  label?: string;
  description?: string;
  // ICH E9(R1) Five Attributes
  treatment?: string;
  population?: string;
  populationSummary?: string;
  analysisPopulation?: string;
  variableOfInterest?: string;
  summaryMeasure?: string;
  intercurrentEvents?: IntercurrentEvent[];
  // Linkage
  endpointId?: string;
  instanceType?: string;
}

interface AnalysisPopulation {
  id: string;
  name?: string;
  label?: string;
  description?: string;
  text?: string;
  level?: { decode?: string };
  includesHealthySubjects?: boolean;
}

export function AdvancedEntitiesView({ usdm }: AdvancedEntitiesViewProps) {
  if (!usdm) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Microscope className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
          <p className="text-muted-foreground">No USDM data available</p>
        </CardContent>
      </Card>
    );
  }

  // Extract data from USDM structure
  const study = usdm.study as Record<string, unknown> | undefined;
  const versions = (study?.versions as unknown[]) ?? [];
  const version = versions[0] as Record<string, unknown> | undefined;
  const studyDesigns = (version?.studyDesigns as Record<string, unknown>[]) ?? [];
  const studyDesign = studyDesigns[0] ?? {};

  // USDM-compliant locations per dataStructure.yml:
  // - indications: studyDesign.indications
  // - biomedicalConcepts: studyVersion.biomedicalConcepts
  // - estimands: studyDesign.estimands  
  // - therapeuticAreas: studyDesign.therapeuticAreas
  const indications = (studyDesign.indications as Indication[]) ?? [];
  const biomedicalConcepts = (version?.biomedicalConcepts as BiomedicalConcept[]) ?? 
    (studyDesign.biomedicalConcepts as BiomedicalConcept[]) ?? [];
  const estimands = (studyDesign.estimands as Estimand[]) ?? [];
  const therapeuticAreas = (studyDesign.therapeuticAreas as { term?: string; decode?: string }[]) ?? [];
  const analysisPopulations = (studyDesign.analysisPopulations as AnalysisPopulation[]) ?? [];

  // State for collapsible sections
  const [showAllEstimands, setShowAllEstimands] = useState(false);

  const hasData = indications.length > 0 || biomedicalConcepts.length > 0 || 
    estimands.length > 0 || therapeuticAreas.length > 0 || analysisPopulations.length > 0;

  if (!hasData) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Microscope className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
          <p className="text-muted-foreground">No advanced entities found</p>
          <p className="text-sm text-muted-foreground mt-2">
            Biomedical concepts, estimands, and indications will appear here when available
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Target className="h-5 w-5 text-blue-600" />
              <div>
                <div className="text-2xl font-bold">{indications.length}</div>
                <div className="text-xs text-muted-foreground">Indications</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Beaker className="h-5 w-5 text-purple-600" />
              <div>
                <div className="text-2xl font-bold">{biomedicalConcepts.length}</div>
                <div className="text-xs text-muted-foreground">Biomedical Concepts</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-green-600" />
              <div>
                <div className="text-2xl font-bold">{estimands.length}</div>
                <div className="text-xs text-muted-foreground">Estimands</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Pill className="h-5 w-5 text-orange-600" />
              <div>
                <div className="text-2xl font-bold">{therapeuticAreas.length}</div>
                <div className="text-xs text-muted-foreground">Therapeutic Areas</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Users className="h-5 w-5 text-cyan-600" />
              <div>
                <div className="text-2xl font-bold">{analysisPopulations.length}</div>
                <div className="text-xs text-muted-foreground">Analysis Populations</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Therapeutic Areas */}
      {therapeuticAreas.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Pill className="h-5 w-5" />
              Therapeutic Areas
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {therapeuticAreas.map((area, i) => (
                <Badge key={i} variant="secondary" className="text-sm">
                  {area.decode || area.term || 'Unknown'}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Indications */}
      {indications.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Target className="h-5 w-5" />
              Indications
              <Badge variant="secondary">{indications.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {indications.map((indication, i) => (
                <div key={i} className="p-3 bg-muted rounded-lg">
                  <EditableField
                    path={`/study/versions/0/studyDesigns/0/indications/${i}/name`}
                    value={indication.name || indication.description || `Indication ${i + 1}`}
                    className="font-medium"
                    placeholder="Indication name"
                  />
                  {indication.description && indication.name && (
                    <EditableField
                      path={`/study/versions/0/studyDesigns/0/indications/${i}/description`}
                      value={indication.description}
                      type="textarea"
                      className="text-sm text-muted-foreground mt-1"
                      placeholder="Description"
                    />
                  )}
                  {indication.codes && indication.codes.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {indication.codes.map((code, j) => (
                        <Badge key={j} variant="outline" className="text-xs">
                          {code.code}: {code.decode || 'N/A'}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Biomedical Concepts */}
      {biomedicalConcepts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Beaker className="h-5 w-5" />
              Biomedical Concepts
              <Badge variant="secondary">{biomedicalConcepts.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {biomedicalConcepts.map((concept, i) => (
                <div key={i} className="p-3 bg-muted rounded-lg">
                  <EditableField
                    path={`/study/versions/0/biomedicalConcepts/${i}/name`}
                    value={concept.name || `Concept ${i + 1}`}
                    className="font-medium"
                    placeholder="Concept name"
                  />
                  {concept.synonyms && concept.synonyms.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {concept.synonyms.slice(0, 5).map((syn, j) => (
                        <Badge key={j} variant="outline" className="text-xs">
                          {syn}
                        </Badge>
                      ))}
                      {concept.synonyms.length > 5 && (
                        <Badge variant="outline" className="text-xs">
                          +{concept.synonyms.length - 5} more
                        </Badge>
                      )}
                    </div>
                  )}
                  {concept.reference && (
                    <p className="text-xs text-muted-foreground mt-1">
                      Ref: {concept.reference}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Estimands - ICH E9(R1) Framework */}
      {estimands.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Estimands (ICH E9 R1)
              <Badge variant="secondary">{estimands.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-6">
              {estimands.map((estimand, i) => {
                const population = estimand.population || estimand.populationSummary || estimand.analysisPopulation;
                const getStrategyText = (strategy: IntercurrentEvent['strategy']) => {
                  if (!strategy) return 'Not specified';
                  return strategy;  // USDM 4.0: strategy is a string
                };
                
                return (
                  <div key={i} className="p-4 border rounded-lg bg-gradient-to-r from-green-50/50 to-transparent dark:from-green-950/20">
                    {/* Header */}
                    <div className="flex items-start justify-between mb-4">
                      <div>
                        <div className="font-semibold text-lg">
                          {estimand.name || `Estimand ${i + 1}`}
                        </div>
                        {estimand.label && (
                          <div className="text-sm text-muted-foreground">{estimand.label}</div>
                        )}
                      </div>
                      {estimand.endpointId && (
                        <Badge variant="outline" className="text-xs">
                          → {estimand.endpointId}
                        </Badge>
                      )}
                    </div>
                    
                    {estimand.description && (
                      <p className="text-sm text-muted-foreground mb-4 italic">
                        {estimand.description}
                      </p>
                    )}
                    
                    {/* ICH E9(R1) Five Attributes Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                      {/* 1. Treatment */}
                      <div className="p-3 bg-muted/50 rounded-md">
                        <div className="font-medium text-blue-700 dark:text-blue-400 mb-1 flex items-center gap-1">
                          <span className="text-xs bg-blue-100 dark:bg-blue-900 px-1.5 py-0.5 rounded">1</span>
                          Treatment
                        </div>
                        <div>{estimand.treatment || 'Not specified'}</div>
                      </div>
                      
                      {/* 2. Population */}
                      <div className="p-3 bg-muted/50 rounded-md">
                        <div className="font-medium text-purple-700 dark:text-purple-400 mb-1 flex items-center gap-1">
                          <span className="text-xs bg-purple-100 dark:bg-purple-900 px-1.5 py-0.5 rounded">2</span>
                          Population
                        </div>
                        <div>{population || 'Not specified'}</div>
                      </div>
                      
                      {/* 3. Variable (Endpoint) */}
                      <div className="p-3 bg-muted/50 rounded-md">
                        <div className="font-medium text-green-700 dark:text-green-400 mb-1 flex items-center gap-1">
                          <span className="text-xs bg-green-100 dark:bg-green-900 px-1.5 py-0.5 rounded">3</span>
                          Variable (Endpoint)
                        </div>
                        <div>{estimand.variableOfInterest || 'Not specified'}</div>
                      </div>
                      
                      {/* 5. Population-Level Summary */}
                      <div className="p-3 bg-muted/50 rounded-md">
                        <div className="font-medium text-orange-700 dark:text-orange-400 mb-1 flex items-center gap-1">
                          <span className="text-xs bg-orange-100 dark:bg-orange-900 px-1.5 py-0.5 rounded">5</span>
                          Summary Measure
                        </div>
                        <div>{estimand.summaryMeasure || 'Not specified'}</div>
                      </div>
                    </div>
                    
                    {/* 4. Intercurrent Events */}
                    <div className="mt-4 p-3 bg-muted/50 rounded-md">
                      <div className="font-medium text-red-700 dark:text-red-400 mb-2 flex items-center gap-1">
                        <span className="text-xs bg-red-100 dark:bg-red-900 px-1.5 py-0.5 rounded">4</span>
                        Intercurrent Events & Strategies
                      </div>
                      {estimand.intercurrentEvents && estimand.intercurrentEvents.length > 0 ? (
                        <div className="space-y-2">
                          {estimand.intercurrentEvents.map((event, j) => (
                            <div key={j} className="flex items-start justify-between p-2 bg-background rounded border">
                              <div className="flex-1 min-w-0">
                                <div className="font-medium text-sm">{event.name}</div>
                                {/* USDM 4.0: text is the primary field, description is optional */}
                                {(event.text || event.description) && (
                                  <div className="text-xs text-muted-foreground mt-0.5">
                                    {event.text || event.description}
                                  </div>
                                )}
                              </div>
                              <Badge variant="secondary" className="text-xs shrink-0 ml-2">
                                {getStrategyText(event.strategy)}
                              </Badge>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="text-muted-foreground text-sm">No intercurrent events specified</div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Analysis Populations (SAP) */}
      {analysisPopulations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="h-5 w-5" />
              Analysis Populations
              <Badge variant="secondary">{analysisPopulations.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {analysisPopulations.map((pop, i) => (
                <div key={pop.id || i} className="p-4 border rounded-lg bg-gradient-to-r from-cyan-50/50 to-transparent dark:from-cyan-950/20">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="font-semibold text-lg">
                        {pop.name || pop.label || `Population ${i + 1}`}
                      </div>
                      <EditableCodedValue
                        path={`/study/versions/0/studyDesigns/0/analysisPopulations/${i}/level`}
                        value={pop.level}
                        options={CDISC_TERMINOLOGIES.populationLevel}
                        placeholder="Level"
                      />
                    </div>
                    {pop.includesHealthySubjects !== undefined && (
                      <Badge variant={pop.includesHealthySubjects ? 'default' : 'secondary'}>
                        {pop.includesHealthySubjects ? 'Includes Healthy' : 'Patients Only'}
                      </Badge>
                    )}
                  </div>
                  {(pop.description || pop.text) && (
                    <p className="text-sm text-muted-foreground mt-2">
                      {pop.description || pop.text}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default AdvancedEntitiesView;
