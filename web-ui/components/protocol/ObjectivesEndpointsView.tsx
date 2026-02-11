'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { EditableField, EditableCodedValue, CDISC_TERMINOLOGIES } from '@/components/semantic';
import { designPath, idPath } from '@/lib/semantic/schema';
import { useSemanticStore } from '@/stores/semanticStore';
import { useEditModeStore } from '@/stores/editModeStore';
import { Target, TrendingUp, Beaker, Plus, Trash2 } from 'lucide-react';

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

  const { addPatchOp } = useSemanticStore();
  const isEditMode = useEditModeStore((s) => s.isEditMode);

  const handleAddObjective = (level: { code: string; decode: string }) => {
    const newObj = {
      id: `obj_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      text: '',
      description: '',
      level,
      endpoints: [],
      instanceType: 'Objective',
    };
    addPatchOp({ op: 'add', path: '/study/versions/0/studyDesigns/0/objectives/-', value: newObj });
  };

  const handleRemoveObjective = (objectiveId: string) => {
    addPatchOp({ op: 'remove', path: designPath('objectives', objectiveId) });
  };

  const handleAddEndpoint = (objectiveId: string) => {
    const newEp = {
      id: `ep_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      text: '',
      description: '',
      purpose: { code: '', decode: '' },
      instanceType: 'Endpoint',
    };
    // If the objective has no endpoints array yet, create it with the new item;
    // otherwise append to the existing array.
    const obj = objectives.find(o => o.id === objectiveId);
    if (!obj?.endpoints || obj.endpoints.length === 0) {
      addPatchOp({ op: 'add', path: `${designPath('objectives', objectiveId)}/endpoints`, value: [newEp] });
    } else {
      addPatchOp({ op: 'add', path: `${designPath('objectives', objectiveId)}/endpoints/-`, value: newEp });
    }
  };

  const handleRemoveEndpoint = (objectiveId: string, endpointId: string) => {
    addPatchOp({
      op: 'remove',
      path: idPath('objectives', objectiveId, undefined, {
        nested: { collection: 'endpoints', entityId: endpointId },
      }),
    });
  };

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
      <div key={objective.id || index} className="py-3 border-b last:border-b-0 group/obj">
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
                  <div key={ep.id || epIndex} className="mb-2 last:mb-0 group/ep">
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
                        showCode
                        placeholder="Purpose"
                        className="shrink-0"
                      />
                      {isEditMode && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6 shrink-0 opacity-0 group-hover/ep:opacity-100 transition-opacity text-destructive hover:text-destructive"
                          onClick={() => handleRemoveEndpoint(objective.id, ep.id)}
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
                {isEditMode && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleAddEndpoint(objective.id)}
                    className="mt-2 border-dashed text-xs"
                  >
                    <Plus className="h-3 w-3 mr-1" />
                    Add Endpoint
                  </Button>
                )}
              </div>
            )}
            {isEditMode && (!endpoints || endpoints.length === 0) && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleAddEndpoint(objective.id)}
                className="mt-2 border-dashed text-xs"
              >
                <Plus className="h-3 w-3 mr-1" />
                Add Endpoint
              </Button>
            )}
          </div>
          {isEditMode && (
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 shrink-0 opacity-0 group-hover/obj:opacity-100 transition-opacity text-destructive hover:text-destructive"
              onClick={() => handleRemoveObjective(objective.id)}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          )}
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
      {(primaryObjectives.length > 0 || isEditMode) && (
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
            {isEditMode && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleAddObjective({ code: 'C85826', decode: 'Primary' })}
                className="mt-3 w-full border-dashed"
              >
                <Plus className="h-4 w-4 mr-2" />
                Add Primary Objective
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      {/* Secondary Objectives */}
      {(secondaryObjectives.length > 0 || isEditMode) && (
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
            {isEditMode && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleAddObjective({ code: 'C85827', decode: 'Secondary' })}
                className="mt-3 w-full border-dashed"
              >
                <Plus className="h-4 w-4 mr-2" />
                Add Secondary Objective
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      {/* Exploratory Objectives */}
      {(exploratoryObjectives.length > 0 || isEditMode) && (
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
            {isEditMode && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleAddObjective({ code: 'C163559', decode: 'Exploratory' })}
                className="mt-3 w-full border-dashed"
              >
                <Plus className="h-4 w-4 mr-2" />
                Add Exploratory Objective
              </Button>
            )}
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
