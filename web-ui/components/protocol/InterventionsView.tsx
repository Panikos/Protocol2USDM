'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { EditableField } from '@/components/semantic';
import { Pill, Syringe, Clock, Beaker, FlaskConical, ChevronDown, ChevronRight } from 'lucide-react';

interface InterventionsViewProps {
  usdm: Record<string, unknown> | null;
}

interface StudyIntervention {
  id: string;
  name?: string;
  label?: string;
  description?: string;
  role?: { decode?: string };
  type?: { decode?: string };
  codes?: { decode?: string }[];
  administrableProducts?: AdministrableProduct[];
  administrableProductIds?: string[];
}

interface AdministrableProduct {
  id: string;
  name?: string;
  label?: string;
  description?: string;
  formulation?: string;
  route?: { decode?: string };
  dosage?: string;
  strength?: string;
}

interface Administration {
  id: string;
  name?: string;
  description?: string;
  duration?: string;
  durationDescription?: string;
  route?: { decode?: string };
  frequency?: { decode?: string };
  dose?: string;
  doseDescription?: string;
}

interface Substance {
  id: string;
  name?: string;
  substanceName?: string;
  description?: string;
  substanceType?: { decode?: string };
  codes?: { code?: string; decode?: string }[];
}

interface Ingredient {
  id: string;
  name?: string;
  role?: { decode?: string };
  substanceId?: string;
  strengthId?: string;
}

interface Strength {
  id: string;
  value?: string;
  unit?: string;
  presentationText?: string;
}

export function InterventionsView({ usdm }: InterventionsViewProps) {
  if (!usdm) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-muted-foreground">No USDM data available</p>
        </CardContent>
      </Card>
    );
  }

  // Extract study design and version
  const study = usdm.study as Record<string, unknown> | undefined;
  const versions = (study?.versions as unknown[]) ?? [];
  const version = versions[0] as Record<string, unknown> | undefined;
  const studyDesigns = (version?.studyDesigns as Record<string, unknown>[]) ?? [];
  const design = studyDesigns[0];

  // USDM-compliant: studyInterventions and administrableProducts are at studyVersion level
  const studyInterventions = (version?.studyInterventions as StudyIntervention[]) ?? 
                             (design?.studyInterventions as StudyIntervention[]) ?? [];
  
  const administrableProducts = (version?.administrableProducts as AdministrableProduct[]) ?? 
                                (usdm.administrableProducts as AdministrableProduct[]) ?? [];

  // Top-level USDM data for administrations, substances, ingredients
  const administrations = (usdm.administrations as Administration[]) ?? [];
  const substances = (usdm.substances as Substance[]) ?? [];
  const ingredients = (usdm.ingredients as Ingredient[]) ?? [];
  const strengths = (usdm.strengths as Strength[]) ?? [];

  // Build lookup maps
  const substanceMap = new Map(substances.map(s => [s.id, s]));
  const strengthMap = new Map(strengths.map(s => [s.id, s]));

  // State for collapsible sections
  const [showAllAdministrations, setShowAllAdministrations] = useState(false);

  const hasData = studyInterventions.length > 0 || administrableProducts.length > 0 || 
    administrations.length > 0 || substances.length > 0;

  if (!hasData) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-muted-foreground">No interventions found in USDM data</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Study Interventions */}
      {studyInterventions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Pill className="h-5 w-5" />
              Study Interventions
              <Badge variant="secondary">{studyInterventions.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {studyInterventions.map((intervention, i) => (
                <div key={intervention.id || i} className="p-4 border rounded-lg">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <EditableField
                        path={`/study/versions/0/studyInterventions/${i}/name`}
                        value={intervention.label || intervention.name || `Intervention ${i + 1}`}
                        label=""
                        className="font-medium"
                        placeholder="Intervention name"
                      />
                      <EditableField
                        path={`/study/versions/0/studyInterventions/${i}/description`}
                        value={intervention.description || ''}
                        label=""
                        type="textarea"
                        className="text-sm text-muted-foreground mt-1"
                        placeholder="No description"
                      />
                    </div>
                    <div className="flex gap-2">
                      {intervention.role?.decode && (
                        <Badge variant="outline">{intervention.role.decode}</Badge>
                      )}
                      {intervention.type?.decode && (
                        <Badge>{intervention.type.decode}</Badge>
                      )}
                    </div>
                  </div>
                  
                  {intervention.codes && intervention.codes.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {intervention.codes.map((code, ci) => (
                        <Badge key={ci} variant="secondary" className="text-xs">
                          {code.decode}
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

      {/* Administrable Products */}
      {administrableProducts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Syringe className="h-5 w-5" />
              Administrable Products
              <Badge variant="secondary">{administrableProducts.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {administrableProducts.map((product, i) => (
                <div key={product.id || i} className="p-4 border rounded-lg">
                  <EditableField
                    path={`/study/versions/0/administrableProducts/${i}/name`}
                    value={product.label || product.name || `Product ${i + 1}`}
                    label=""
                    className="font-medium"
                    placeholder="Product name"
                  />
                  
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3 text-sm">
                    <EditableField
                      path={`/study/versions/0/administrableProducts/${i}/formulation`}
                      value={product.formulation || ''}
                      label="Formulation"
                      placeholder="Not specified"
                    />
                    {product.route?.decode && (
                      <div>
                        <span className="text-muted-foreground">Route</span>
                        <p>{product.route.decode}</p>
                      </div>
                    )}
                    <EditableField
                      path={`/study/versions/0/administrableProducts/${i}/dosage`}
                      value={product.dosage || ''}
                      label="Dosage"
                      placeholder="Not specified"
                    />
                    <EditableField
                      path={`/study/versions/0/administrableProducts/${i}/strength`}
                      value={product.strength || ''}
                      label="Strength"
                      placeholder="Not specified"
                    />
                  </div>
                  
                  <EditableField
                    path={`/study/versions/0/administrableProducts/${i}/description`}
                    value={product.description || ''}
                    label=""
                    type="textarea"
                    className="text-sm text-muted-foreground mt-2"
                    placeholder="No description"
                  />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Administrations (Dosing Details) */}
      {administrations.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-5 w-5" />
              Administration Details
              <Badge variant="secondary">{administrations.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {(showAllAdministrations ? administrations : administrations.slice(0, 5)).map((admin, i) => (
                <div key={admin.id || i} className="p-4 border rounded-lg bg-gradient-to-r from-blue-50/50 to-transparent dark:from-blue-950/20">
                  <EditableField
                    path={`/administrations/${i}/name`}
                    value={admin.name || `Administration ${i + 1}`}
                    className="font-medium"
                    placeholder="Administration name"
                  />
                  
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3 text-sm">
                    {admin.route?.decode && (
                      <div>
                        <span className="text-muted-foreground">Route</span>
                        <EditableField
                          path={`/administrations/${i}/route/decode`}
                          value={admin.route.decode}
                          placeholder="Route"
                        />
                      </div>
                    )}
                    {admin.frequency?.decode && (
                      <div>
                        <span className="text-muted-foreground">Frequency</span>
                        <EditableField
                          path={`/administrations/${i}/frequency/decode`}
                          value={admin.frequency.decode}
                          placeholder="Frequency"
                        />
                      </div>
                    )}
                    {(admin.dose || admin.doseDescription) && (
                      <div>
                        <span className="text-muted-foreground">Dose</span>
                        <EditableField
                          path={`/administrations/${i}/dose`}
                          value={admin.dose || admin.doseDescription || ''}
                          placeholder="Dose"
                        />
                      </div>
                    )}
                    {(admin.duration || admin.durationDescription) && (
                      <div>
                        <span className="text-muted-foreground">Duration</span>
                        <EditableField
                          path={`/administrations/${i}/duration`}
                          value={admin.duration || admin.durationDescription || ''}
                          placeholder="Duration"
                        />
                      </div>
                    )}
                  </div>
                  
                  {admin.description && (
                    <EditableField
                      path={`/administrations/${i}/description`}
                      value={admin.description}
                      type="textarea"
                      className="text-sm text-muted-foreground mt-2"
                      placeholder="No description"
                    />
                  )}
                </div>
              ))}
            </div>
            {administrations.length > 5 && (
              <button
                onClick={() => setShowAllAdministrations(!showAllAdministrations)}
                className="mt-4 flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400"
              >
                {showAllAdministrations ? (
                  <>
                    <ChevronDown className="h-4 w-4" />
                    Show less
                  </>
                ) : (
                  <>
                    <ChevronRight className="h-4 w-4" />
                    Show all {administrations.length} administrations
                  </>
                )}
              </button>
            )}
          </CardContent>
        </Card>
      )}

      {/* Substances */}
      {substances.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FlaskConical className="h-5 w-5" />
              Drug Substances
              <Badge variant="secondary">{substances.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {substances.map((substance, i) => (
                <div key={substance.id || i} className="p-3 border rounded-lg">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <EditableField
                        path={`/substances/${i}/substanceName`}
                        value={substance.substanceName || substance.name || `Substance ${i + 1}`}
                        label=""
                        className="font-medium"
                        placeholder="Substance name"
                      />
                      <EditableField
                        path={`/substances/${i}/description`}
                        value={substance.description || ''}
                        label=""
                        type="textarea"
                        className="text-sm text-muted-foreground mt-1"
                        placeholder="No description"
                      />
                    </div>
                    {substance.substanceType?.decode && (
                      <Badge variant="outline">{substance.substanceType.decode}</Badge>
                    )}
                  </div>
                  {substance.codes && substance.codes.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {substance.codes.map((code, ci) => (
                        <Badge key={ci} variant="secondary" className="text-xs font-mono">
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

      {/* Ingredients with Strengths */}
      {ingredients.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Beaker className="h-5 w-5" />
              Ingredients
              <Badge variant="secondary">{ingredients.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {ingredients.map((ingredient, i) => {
                const substance = substanceMap.get(ingredient.substanceId || '');
                const strength = strengthMap.get(ingredient.strengthId || '');
                return (
                  <div key={ingredient.id || i} className="p-3 bg-muted rounded-lg">
                    <div className="flex items-center justify-between">
                      <span className="font-medium">
                        {ingredient.name || substance?.substanceName || substance?.name || `Ingredient ${i + 1}`}
                      </span>
                      {ingredient.role?.decode && (
                        <Badge variant="outline" className="text-xs">{ingredient.role.decode}</Badge>
                      )}
                    </div>
                    {strength && (
                      <div className="text-sm text-muted-foreground mt-1">
                        Strength: {strength.presentationText || `${strength.value || ''} ${strength.unit || ''}`}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default InterventionsView;
