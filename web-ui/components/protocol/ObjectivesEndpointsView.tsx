'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { EditableField, EditableCodedValue, CDISC_TERMINOLOGIES } from '@/components/semantic';
import { designPath, idPath } from '@/lib/semantic/schema';
import { Target, TrendingUp, Beaker } from 'lucide-react';

interface ObjectivesEndpointsViewProps {
  usdm: Record<string, unknown> | null;
}

interface Endpoint {
  id: string;
  name?: string;
  label?: string;
  description?: string;
  text?: string;
  purpose?: { decode?: string };
  level?: { decode?: string };
}

interface Objective {
  id: string;
  name?: string;
  label?: string;
  description?: string;
  text?: string;
  level?: { decode?: string };
  endpoints?: Endpoint[];
  endpointIds?: string[];
}

export function ObjectivesEndpointsView({ usdm }: ObjectivesEndpointsViewProps) {
  if (!usdm) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-muted-foreground">No USDM data available</p>
        </CardContent>
      </Card>
    );
  }

  // Extract study design
  const study = usdm.study as Record<string, unknown> | undefined;
  const versions = (study?.versions as unknown[]) ?? [];
  const version = versions[0] as Record<string, unknown> | undefined;
  const studyDesigns = (version?.studyDesigns as Record<string, unknown>[]) ?? [];
  const design = studyDesigns[0];

  if (!design) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-muted-foreground">No study design found</p>
        </CardContent>
      </Card>
    );
  }

  // Extract objectives
  const objectives = (design.objectives as Objective[]) ?? [];

  // Categorize objectives by level
  const primaryObjectives = objectives.filter(o => 
    o.level?.decode?.toLowerCase().includes('primary')
  );
  const secondaryObjectives = objectives.filter(o => 
    o.level?.decode?.toLowerCase().includes('secondary')
  );
  const exploratoryObjectives = objectives.filter(o => 
    o.level?.decode?.toLowerCase().includes('exploratory') ||
    o.level?.decode?.toLowerCase().includes('tertiary')
  );
  const otherObjectives = objectives.filter(o => 
    !primaryObjectives.includes(o) && 
    !secondaryObjectives.includes(o) && 
    !exploratoryObjectives.includes(o)
  );

  const renderObjective = (objective: Objective, index: number) => {
    const text = objective.text || objective.description || objective.label || objective.name || 'No description';
    const endpoints = objective.endpoints ?? [];

    return (
      <div key={objective.id || index} className="py-3 border-b last:border-b-0">
        <div className="flex items-start gap-3">
          <Badge variant="outline" className="mt-0.5">{index + 1}</Badge>
          <div className="flex-1">
            <EditableField
              path={designPath('objectives', objective.id, 'text')}
              value={text}
              label="Objective Text"
              type="textarea"
              className="text-sm"
            />
            
            {endpoints.length > 0 && (
              <div className="mt-3 pl-4 border-l-2 border-blue-200">
                <p className="text-xs font-medium text-muted-foreground mb-2">Endpoints:</p>
                {endpoints.map((ep, epIndex) => (
                  <div key={ep.id || epIndex} className="mb-2 last:mb-0">
                    <div className="flex items-center gap-2">
                      <TrendingUp className="h-3 w-3 text-blue-500" />
                      <EditableField
                        path={idPath('objectives', objective.id, undefined, {
                          nested: { collection: 'endpoints', entityId: ep.id, property: 'text' }
                        })}
                        value={ep.text || ep.description || ep.label || ep.name || 'Endpoint'}
                        label="Endpoint Text"
                        className="text-sm"
                      />
                      <EditableCodedValue
                        path={idPath('objectives', objective.id, undefined, {
                          nested: { collection: 'endpoints', entityId: ep.id, property: 'purpose' }
                        })}
                        value={ep.purpose}
                        options={CDISC_TERMINOLOGIES.endpointPurpose}
                        placeholder="Purpose"
                        className="shrink-0"
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  if (objectives.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-muted-foreground">No objectives found in USDM data</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Primary Objectives */}
      {primaryObjectives.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Target className="h-5 w-5 text-red-600" />
              Primary Objectives
              <Badge>{primaryObjectives.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {primaryObjectives.map((o, i) => renderObjective(o, i))}
          </CardContent>
        </Card>
      )}

      {/* Secondary Objectives */}
      {secondaryObjectives.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Target className="h-5 w-5 text-orange-500" />
              Secondary Objectives
              <Badge variant="secondary">{secondaryObjectives.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {secondaryObjectives.map((o, i) => renderObjective(o, i))}
          </CardContent>
        </Card>
      )}

      {/* Exploratory Objectives */}
      {exploratoryObjectives.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Beaker className="h-5 w-5 text-purple-500" />
              Exploratory Objectives
              <Badge variant="outline">{exploratoryObjectives.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {exploratoryObjectives.map((o, i) => renderObjective(o, i))}
          </CardContent>
        </Card>
      )}

      {/* Other/Uncategorized Objectives */}
      {otherObjectives.length > 0 && primaryObjectives.length === 0 && secondaryObjectives.length === 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Target className="h-5 w-5" />
              Objectives
              <Badge>{otherObjectives.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {otherObjectives.map((o, i) => renderObjective(o, i))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default ObjectivesEndpointsView;
