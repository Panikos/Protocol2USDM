'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { CheckCircle2, XCircle, Users } from 'lucide-react';

interface EligibilityCriteriaViewProps {
  usdm: Record<string, unknown> | null;
}

interface EligibilityCriterion {
  id: string;
  name?: string;
  label?: string;
  description?: string;
  text?: string;
  category?: { decode?: string };
  identifier?: string;
}

export function EligibilityCriteriaView({ usdm }: EligibilityCriteriaViewProps) {
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

  // Extract eligibility criteria
  const eligibilityCriteria = (design.eligibilityCriteria as EligibilityCriterion[]) ?? [];
  
  // Also check version-level eligibilityCriterionItems
  const criterionItems = (version?.eligibilityCriterionItems as EligibilityCriterion[]) ?? [];
  
  // Combine both sources
  const allCriteria = [...eligibilityCriteria, ...criterionItems];

  // Separate inclusion vs exclusion
  const inclusionCriteria = allCriteria.filter(c => 
    c.category?.decode?.toLowerCase().includes('inclusion') ||
    c.name?.toLowerCase().includes('inclusion') ||
    c.identifier?.startsWith('I')
  );
  
  const exclusionCriteria = allCriteria.filter(c => 
    c.category?.decode?.toLowerCase().includes('exclusion') ||
    c.name?.toLowerCase().includes('exclusion') ||
    c.identifier?.startsWith('E')
  );

  // If no categorization, just show all
  const uncategorized = allCriteria.filter(c => 
    !inclusionCriteria.includes(c) && !exclusionCriteria.includes(c)
  );

  // Extract population info
  const population = design.population as Record<string, unknown> | undefined;
  const plannedAge = population?.plannedAge as { minValue?: { value?: number }; maxValue?: { value?: number } } | undefined;
  const plannedSex = (population?.plannedSex as { decode?: string }[]) ?? [];

  const renderCriterion = (criterion: EligibilityCriterion, index: number) => {
    const text = criterion.text || criterion.description || criterion.label || criterion.name || 'No text';
    const identifier = criterion.identifier || `${index + 1}`;
    
    return (
      <div key={criterion.id || index} className="flex gap-3 py-2 border-b last:border-b-0">
        <Badge variant="outline" className="h-6 min-w-[2rem] justify-center">
          {identifier}
        </Badge>
        <p className="text-sm flex-1">{text}</p>
      </div>
    );
  };

  if (allCriteria.length === 0) {
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
                  <p className="font-medium">
                    {plannedAge.minValue?.value ?? '?'} - {plannedAge.maxValue?.value ?? '?'} years
                  </p>
                </div>
              )}
              
              {plannedSex.length > 0 && (
                <div>
                  <span className="text-sm text-muted-foreground">Sex</span>
                  <p className="font-medium">{plannedSex[0]?.decode ?? 'Both'}</p>
                </div>
              )}

              {population.plannedEnrollmentNumber && (
                <div>
                  <span className="text-sm text-muted-foreground">Planned Enrollment</span>
                  <p className="font-medium">
                    {String((population.plannedEnrollmentNumber as Record<string, unknown>)?.value ?? 'N/A')}
                  </p>
                </div>
              )}

              {population.includesHealthySubjects !== undefined && (
                <div>
                  <span className="text-sm text-muted-foreground">Healthy Subjects</span>
                  <p className="font-medium">
                    {population.includesHealthySubjects ? 'Yes' : 'No'}
                  </p>
                </div>
              )}
            </div>

            {population.description && (
              <div className="mt-4 pt-4 border-t">
                <span className="text-sm text-muted-foreground">Description</span>
                <p className="mt-1">{String(population.description)}</p>
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
              {inclusionCriteria.map((c, i) => renderCriterion(c, i))}
            </div>
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
              {exclusionCriteria.map((c, i) => renderCriterion(c, i))}
            </div>
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
              {uncategorized.map((c, i) => renderCriterion(c, i))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default EligibilityCriteriaView;
