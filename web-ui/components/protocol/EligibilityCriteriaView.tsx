'use client';

import { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { EditableField, EditableCodedValue, CDISC_TERMINOLOGIES } from '@/components/semantic';
import { designPath } from '@/lib/semantic/schema';
import { useSemanticStore } from '@/stores/semanticStore';
import { useEditModeStore } from '@/stores/editModeStore';
import { CheckCircle2, XCircle, Users, AlertTriangle, Plus, Trash2 } from 'lucide-react';
import { ProvenanceBadge } from '@/components/provenance';

interface EligibilityCriteriaViewProps {
  usdm: Record<string, unknown> | null;
}

interface EligibilityCriterion {
  id: string;
  name?: string;
  label?: string;
  description?: string;
  text?: string;
  category?: { decode?: string; code?: string };
  identifier?: string;
  criterionItemId?: string;
}

interface EligibilityCriterionItem {
  id: string;
  name?: string;
  text?: string;
  instanceType?: string;
}

export function EligibilityCriteriaView({ usdm }: EligibilityCriteriaViewProps) {
  // Build criterion items map from USDM eligibilityCriterionItems
  const criterionItemsMap = useMemo(() => {
    const map = new Map<string, EligibilityCriterionItem>();
    
    // Look for eligibilityCriterionItems in the USDM
    const study = usdm?.study as Record<string, unknown> | undefined;
    const versions = (study?.versions as unknown[]) ?? [];
    const version = versions[0] as Record<string, unknown> | undefined;
    
    // USDM-compliant: eligibilityCriterionItems are at studyVersion level (per dataStructure.yml)
    const criterionItems = (version?.eligibilityCriterionItems as EligibilityCriterionItem[]) ?? [];
    
    for (const item of criterionItems) {
      if (item.id) {
        map.set(item.id, item);
      }
    }
    return map;
  }, [usdm]);

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

  // Extract eligibility criteria from USDM
  const eligibilityCriteria = (design.eligibilityCriteria as EligibilityCriterion[]) ?? [];
  
  // Resolve criterion text from USDM eligibilityCriterionItems using criterionItemId
  const resolvedCriteria = eligibilityCriteria.map(criterion => {
    if (criterion.criterionItemId && criterionItemsMap.has(criterion.criterionItemId)) {
      const item = criterionItemsMap.get(criterion.criterionItemId)!;
      return {
        ...criterion,
        text: item.text || criterion.text,
      };
    }
    return criterion;
  });
  
  // Check if we have missing criterion item references (pipeline gap)
  const hasMissingItems = eligibilityCriteria.some(c => 
    c.criterionItemId && !criterionItemsMap.has(c.criterionItemId) && !c.text
  );

  const { addPatchOp } = useSemanticStore();
  const isEditMode = useEditModeStore((s) => s.isEditMode);

  const handleAddCriterion = (category: { code: string; decode: string }) => {
    const newCriterion = {
      id: `ec_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      text: '',
      description: '',
      category,
      instanceType: 'EligibilityCriterion',
    };
    addPatchOp({ op: 'add', path: '/study/versions/0/studyDesigns/0/eligibilityCriteria/-', value: newCriterion });
  };

  const handleRemoveCriterion = (criterionId: string) => {
    addPatchOp({ op: 'remove', path: designPath('eligibilityCriteria', criterionId) });
  };

  // Separate inclusion vs exclusion
  const inclusionCriteria = resolvedCriteria.filter(c => 
    c.category?.decode?.toLowerCase().includes('inclusion') ||
    c.category?.code === 'C25532' ||
    c.name?.toLowerCase().includes('inclusion') ||
    c.identifier?.startsWith('I')
  );
  
  const exclusionCriteria = resolvedCriteria.filter(c => 
    c.category?.decode?.toLowerCase().includes('exclusion') ||
    c.category?.code === 'C25370' ||
    c.name?.toLowerCase().includes('exclusion') ||
    c.identifier?.startsWith('E')
  );

  // If no categorization, just show all
  const uncategorized = resolvedCriteria.filter(c => 
    !inclusionCriteria.includes(c) && !exclusionCriteria.includes(c)
  );

  // Extract population info
  const population = design.population as Record<string, unknown> | undefined;
  const rawPlannedAge = population?.plannedAge as Record<string, unknown> | undefined;
  // Support both USDM v4.0 Quantity objects and legacy flat ints
  const extractAgeValue = (v: unknown): string => {
    if (v == null) return '';
    if (typeof v === 'object' && v !== null && 'value' in v) return String((v as Record<string, unknown>).value ?? '');
    if (typeof v === 'number') return String(v);
    return String(v);
  };
  const plannedAge = rawPlannedAge ? {
    minValue: { value: extractAgeValue(rawPlannedAge.minValue) ? Number(extractAgeValue(rawPlannedAge.minValue)) : undefined },
    maxValue: { value: extractAgeValue(rawPlannedAge.maxValue) ? Number(extractAgeValue(rawPlannedAge.maxValue)) : undefined },
  } : undefined;
  const plannedSex = (population?.plannedSex as { decode?: string }[]) ?? [];

  const renderCriterion = (criterion: EligibilityCriterion, index: number, criteriaType: 'inclusion' | 'exclusion' | 'uncategorized', typeIndex: number) => {
    const text = criterion.text || criterion.description || criterion.label || criterion.name || 'No text';
    
    return (
      <div key={criterion.id || index} className="flex gap-3 py-2 border-b last:border-b-0 group/crit">
        <Badge variant="outline" className="h-6 min-w-[2rem] justify-center">
          {typeIndex + 1}
        </Badge>
        <ProvenanceBadge entityId={criterion.id} />
        <EditableField
          path={designPath('eligibilityCriteria', criterion.id, 'text')}
          value={text}
          label="Criterion Text"
          type="textarea"
          className="text-sm flex-1"
        />
        {isEditMode && (
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 shrink-0 opacity-0 group-hover/crit:opacity-100 transition-opacity text-destructive hover:text-destructive"
            onClick={() => handleRemoveCriterion(criterion.id)}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        )}
      </div>
    );
  };

  if (resolvedCriteria.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-muted-foreground">No eligibility criteria found in USDM data</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Pipeline Gap Warning */}
      {hasMissingItems && (
        <Card className="border-amber-200 bg-amber-50 dark:bg-amber-950/20">
          <CardContent className="py-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5" />
              <div>
                <p className="font-medium text-amber-800 dark:text-amber-200">Pipeline Gap: Missing EligibilityCriterionItem entities</p>
                <p className="text-sm text-amber-700 dark:text-amber-300 mt-1">
                  The USDM contains EligibilityCriterion references but the linked EligibilityCriterionItem entities (with actual text) are not included.
                  This needs to be fixed in the extraction pipeline.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
      {/* Population Summary */}
      {population && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="h-5 w-5" />
              Population Summary
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {plannedAge && (
                <div>
                  <span className="text-sm text-muted-foreground">Age Range</span>
                  <div className="flex items-center gap-1 font-medium">
                    <EditableField
                      path="/study/versions/0/studyDesigns/0/population/plannedAge/minValue/value"
                      value={String(plannedAge.minValue?.value ?? '')}
                      type="number"
                      className="w-12"
                      placeholder="?"
                    />
                    <span>-</span>
                    <EditableField
                      path="/study/versions/0/studyDesigns/0/population/plannedAge/maxValue/value"
                      value={String(plannedAge.maxValue?.value ?? '')}
                      type="number"
                      className="w-12"
                      placeholder="?"
                    />
                    <span>years</span>
                  </div>
                </div>
              )}
              
              <div>
                <span className="text-sm text-muted-foreground">Sex</span>
                <div className="font-medium">
                  {plannedSex.length === 0 ? (
                    <span className="text-muted-foreground italic text-sm">Not specified</span>
                  ) : plannedSex.length >= 2 ? (
                    <span className="text-sm">Both (Male & Female)</span>
                  ) : (
                    <EditableCodedValue
                      path="/study/versions/0/studyDesigns/0/population/plannedSex/0"
                      value={plannedSex[0]}
                      options={CDISC_TERMINOLOGIES.sex}
                      placeholder="Not specified"
                    />
                  )}
                </div>
              </div>

              {!!population.plannedEnrollmentNumber && (
                <div>
                  <span className="text-sm text-muted-foreground">Planned Enrollment</span>
                  <EditableField
                    path="/study/versions/0/studyDesigns/0/population/plannedEnrollmentNumber/value"
                    value={String((population.plannedEnrollmentNumber as Record<string, unknown>)?.value ?? '')}
                    type="number"
                    className="font-medium"
                    placeholder="N/A"
                  />
                </div>
              )}

              {population.includesHealthySubjects !== undefined && (
                <div>
                  <span className="text-sm text-muted-foreground">Healthy Subjects</span>
                  <EditableField
                    path="/study/versions/0/studyDesigns/0/population/includesHealthySubjects"
                    value={population.includesHealthySubjects ? 'true' : 'false'}
                    type="boolean"
                    className="font-medium"
                  />
                </div>
              )}
            </div>

            {!!population.description && (
              <div className="mt-4 pt-4 border-t">
                <span className="text-sm text-muted-foreground">Description</span>
                <EditableField
                  path="/study/versions/0/studyDesigns/0/population/description"
                  value={String(population.description)}
                  type="textarea"
                  className="mt-1"
                  placeholder="No description"
                />
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Inclusion Criteria */}
      {inclusionCriteria.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-green-600" />
              Inclusion Criteria
              <Badge variant="secondary">{inclusionCriteria.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="divide-y">
              {inclusionCriteria.map((c, i) => renderCriterion(c, i, 'inclusion', i))}
            </div>
            {isEditMode && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleAddCriterion({ code: 'C25532', decode: 'Inclusion' })}
                className="mt-3 w-full border-dashed"
              >
                <Plus className="h-4 w-4 mr-2" />
                Add Inclusion Criterion
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      {/* Exclusion Criteria */}
      {exclusionCriteria.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <XCircle className="h-5 w-5 text-red-600" />
              Exclusion Criteria
              <Badge variant="secondary">{exclusionCriteria.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="divide-y">
              {exclusionCriteria.map((c, i) => renderCriterion(c, i, 'exclusion', i))}
            </div>
            {isEditMode && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleAddCriterion({ code: 'C25370', decode: 'Exclusion' })}
                className="mt-3 w-full border-dashed"
              >
                <Plus className="h-4 w-4 mr-2" />
                Add Exclusion Criterion
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      {/* Uncategorized Criteria */}
      {uncategorized.length > 0 && inclusionCriteria.length === 0 && exclusionCriteria.length === 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Eligibility Criteria</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="divide-y">
              {uncategorized.map((c, i) => renderCriterion(c, i, 'uncategorized', i))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default EligibilityCriteriaView;
