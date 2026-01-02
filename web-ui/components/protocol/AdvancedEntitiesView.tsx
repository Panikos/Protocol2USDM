'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  Microscope, 
  Pill,
  Target,
  Beaker,
  FileText,
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

interface Estimand {
  id: string;
  treatment?: string;
  summaryMeasure?: string;
  population?: string;
  variableOfInterest?: string;
  intercurrentEvents?: { name: string; strategy: string }[];
  instanceType?: string;
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
  // Per USDM spec: indications, biomedicalConcepts, estimands, therapeuticAreas are at studyDesign level
  const study = usdm.study as Record<string, unknown> | undefined;
  const versions = (study?.versions as unknown[]) ?? [];
  const version = versions[0] as Record<string, unknown> | undefined;
  const studyDesigns = (version?.studyDesigns as Record<string, unknown>[]) ?? [];
  const studyDesign = studyDesigns[0] ?? {};

  // Get indications - at studyDesign level per USDM spec
  const indications = (studyDesign.indications as Indication[]) ?? [];

  // Get biomedical concepts - at studyDesign level
  const biomedicalConcepts = (studyDesign.biomedicalConcepts as BiomedicalConcept[]) ?? [];

  // Get estimands - at studyDesign level
  const estimands = (studyDesign.estimands as Estimand[]) ?? [];

  // Get therapeutic areas - at studyDesign level
  const therapeuticAreas = (studyDesign.therapeuticAreas as { term?: string; decode?: string }[]) ?? [];

  const hasData = indications.length > 0 || biomedicalConcepts.length > 0 || 
    estimands.length > 0 || therapeuticAreas.length > 0;

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
                  <div className="font-medium">
                    {indication.name || indication.description || `Indication ${i + 1}`}
                  </div>
                  {indication.description && indication.name && (
                    <p className="text-sm text-muted-foreground mt-1">
                      {indication.description}
                    </p>
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
                  <div className="font-medium">{concept.name || `Concept ${i + 1}`}</div>
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

      {/* Estimands */}
      {estimands.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Estimands
              <Badge variant="secondary">{estimands.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {estimands.map((estimand, i) => (
                <div key={i} className="p-4 border rounded-lg">
                  <div className="font-medium mb-2">Estimand {i + 1}</div>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    {estimand.treatment && (
                      <div>
                        <span className="text-muted-foreground">Treatment:</span>{' '}
                        {estimand.treatment}
                      </div>
                    )}
                    {estimand.population && (
                      <div>
                        <span className="text-muted-foreground">Population:</span>{' '}
                        {estimand.population}
                      </div>
                    )}
                    {estimand.variableOfInterest && (
                      <div>
                        <span className="text-muted-foreground">Variable:</span>{' '}
                        {estimand.variableOfInterest}
                      </div>
                    )}
                    {estimand.summaryMeasure && (
                      <div>
                        <span className="text-muted-foreground">Summary:</span>{' '}
                        {estimand.summaryMeasure}
                      </div>
                    )}
                  </div>
                  {estimand.intercurrentEvents && estimand.intercurrentEvents.length > 0 && (
                    <div className="mt-3">
                      <div className="text-sm text-muted-foreground mb-1">
                        Intercurrent Events:
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {estimand.intercurrentEvents.map((event, j) => (
                          <Badge key={j} variant="outline">
                            {event.name} ({event.strategy})
                          </Badge>
                        ))}
                      </div>
                    </div>
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
