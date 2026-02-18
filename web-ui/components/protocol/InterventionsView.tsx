'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { EditableField, EditableCodedValue, CDISC_TERMINOLOGIES, CodeLink } from '@/components/semantic';
import { versionPath, entityPath } from '@/lib/semantic/schema';
import { useSemanticStore } from '@/stores/semanticStore';
import { useEditModeStore } from '@/stores/editModeStore';
import { Pill, Syringe, Clock, Beaker, FlaskConical, ChevronDown, ChevronRight, Plus, Trash2, ExternalLink, AlertTriangle, Info, Loader2 } from 'lucide-react';
import { ProvenanceBadge } from '@/components/provenance';
import { useDrugInfo } from '@/hooks/useDrugInfo';

interface InterventionsViewProps {
  usdm: Record<string, unknown> | null;
}

// ---------------------------------------------------------------------------
// DrugInfoPanel — collapsible FDA enrichment for a single drug
// ---------------------------------------------------------------------------
function DrugInfoPanel({ drugName }: { drugName: string }) {
  const { data, loading, error } = useDrugInfo(drugName);
  const [expanded, setExpanded] = useState(false);

  if (loading) {
    return (
      <div className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" />
        Looking up FDA label…
      </div>
    );
  }

  if (error || !data) return null;

  const summary = [
    data.generic_name && data.generic_name.toLowerCase() !== drugName.toLowerCase()
      ? `Generic: ${data.generic_name}`
      : null,
    data.brand_name && data.brand_name.toLowerCase() !== drugName.toLowerCase()
      ? `Brand: ${data.brand_name}`
      : null,
    data.manufacturer ? `Mfr: ${data.manufacturer}` : null,
    data.route.length > 0 ? `Route: ${data.route.join(', ')}` : null,
    data.pharmacologic_class.length > 0
      ? `Class: ${data.pharmacologic_class[0]}`
      : null,
  ].filter(Boolean);

  return (
    <div className="mt-2 rounded-md border border-blue-200 bg-blue-50/50 dark:border-blue-900 dark:bg-blue-950/30 text-xs">
      {/* Collapsed summary row */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-1.5 px-3 py-1.5 text-left hover:bg-blue-100/50 dark:hover:bg-blue-900/30 transition-colors"
      >
        <Info className="h-3 w-3 text-blue-600 shrink-0" />
        <span className="font-medium text-blue-700 dark:text-blue-400">FDA Label</span>
        <span className="text-muted-foreground truncate flex-1">
          {summary.length > 0 ? `— ${summary.join(' · ')}` : ''}
        </span>
        {expanded ? (
          <ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground" />
        )}
      </button>

      {/* Expanded details */}
      {expanded && (
        <div className="px-3 pb-3 space-y-2 border-t border-blue-200 dark:border-blue-900 pt-2">
          {data.indications && (
            <FdaSection title="Indications & Usage" text={data.indications} />
          )}
          {data.clinical_pharmacology && (
            <FdaSection title="Clinical Pharmacology" text={data.clinical_pharmacology} />
          )}
          {data.dosage_and_administration && (
            <FdaSection title="Dosage & Administration" text={data.dosage_and_administration} />
          )}
          {data.boxed_warning && (
            <div className="rounded border border-red-300 bg-red-50 dark:bg-red-950/30 dark:border-red-800 px-2 py-1.5">
              <div className="flex items-center gap-1 font-semibold text-red-700 dark:text-red-400 mb-0.5">
                <AlertTriangle className="h-3 w-3" /> Boxed Warning
              </div>
              <p className="text-red-800 dark:text-red-300 whitespace-pre-wrap">{data.boxed_warning}</p>
            </div>
          )}
          {data.contraindications && (
            <FdaSection title="Contraindications" text={data.contraindications} />
          )}
          {data.adverse_reactions && (
            <FdaSection title="Adverse Reactions" text={data.adverse_reactions} />
          )}
          {data.drug_interactions && (
            <FdaSection title="Drug Interactions" text={data.drug_interactions} />
          )}
          {data.mechanism_of_action.length > 0 && (
            <FdaSection title="Mechanism of Action" text={data.mechanism_of_action.join('; ')} />
          )}
          <p className="text-[10px] text-muted-foreground flex items-center gap-1 pt-1">
            <ExternalLink className="h-2.5 w-2.5" />
            Source: openFDA Drug Label API · api.fda.gov
          </p>
        </div>
      )}
    </div>
  );
}

function FdaSection({ title, text }: { title: string; text: string }) {
  return (
    <div>
      <div className="font-semibold text-blue-800 dark:text-blue-300 mb-0.5">{title}</div>
      <p className="text-muted-foreground whitespace-pre-wrap leading-relaxed">{text}</p>
    </div>
  );
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
  administrations?: Administration[];
}

interface AdministrableProduct {
  id: string;
  name?: string;
  label?: string;
  description?: string;
  administrableDoseForm?: { code?: string; decode?: string; standardCode?: { code?: string; decode?: string } };
  routeOfAdministration?: { code?: string; decode?: string };
  productDesignation?: { code?: string; decode?: string };
  sourcing?: { code?: string; decode?: string };
  pharmacologicClass?: { code?: string; decode?: string };
  strength?: string;
  manufacturer?: string;
}

interface Administration {
  id: string;
  name?: string;
  description?: string;
  duration?: string;
  durationDescription?: string;
  route?: { decode?: string };
  frequency?: { decode?: string };
  dose?: string | { value?: number; unit?: { decode?: string } };
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

  // USDM v4.0: administrations are nested inside each StudyIntervention
  // Collect all nested administrations, falling back to root-level for legacy data
  const nestedAdmins = studyInterventions.flatMap(si => si.administrations ?? []);
  const administrations = nestedAdmins.length > 0
    ? nestedAdmins
    : (usdm.administrations as Administration[]) ?? [];
  const substances = (usdm.substances as Substance[]) ?? [];
  const ingredients = (usdm.ingredients as Ingredient[]) ?? [];
  const strengths = (usdm.strengths as Strength[]) ?? [];

  // Build lookup maps
  const substanceMap = new Map(substances.map(s => [s.id, s]));
  const strengthMap = new Map(strengths.map(s => [s.id, s]));

  const { addPatchOp } = useSemanticStore();
  const isEditMode = useEditModeStore((s) => s.isEditMode);

  const handleAddIntervention = () => {
    const newIntervention = {
      id: `int_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      name: '',
      description: '',
      role: { code: '', decode: '' },
      type: { code: '', decode: '' },
      instanceType: 'StudyIntervention',
    };
    addPatchOp({ op: 'add', path: '/study/versions/0/studyInterventions/-', value: newIntervention });
  };

  const handleRemoveIntervention = (interventionId: string) => {
    addPatchOp({ op: 'remove', path: versionPath('studyInterventions', interventionId) });
  };

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
                <div key={intervention.id || i} className="p-4 border rounded-lg group/int">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <EditableField
                          path={versionPath('studyInterventions', intervention.id, 'name')}
                          value={intervention.label || intervention.name || `Intervention ${i + 1}`}
                          label=""
                          className="font-medium"
                          placeholder="Intervention name"
                        />
                        <ProvenanceBadge entityId={intervention.id} />
                      </div>
                      <EditableField
                        path={versionPath('studyInterventions', intervention.id, 'description')}
                        value={intervention.description || ''}
                        label=""
                        type="textarea"
                        className="text-sm text-muted-foreground mt-1"
                        placeholder="No description"
                      />
                    </div>
                    <div className="flex gap-2 items-start shrink-0">
                      <EditableCodedValue
                        path={versionPath('studyInterventions', intervention.id, 'role')}
                        value={intervention.role}
                        options={CDISC_TERMINOLOGIES.interventionRole}
                        showCode
                        placeholder="Role"
                      />
                      <EditableCodedValue
                        path={versionPath('studyInterventions', intervention.id, 'type')}
                        value={intervention.type}
                        options={CDISC_TERMINOLOGIES.interventionType}
                        showCode
                        placeholder="Type"
                      />
                      {isEditMode && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 shrink-0 opacity-0 group-hover/int:opacity-100 transition-opacity text-destructive hover:text-destructive"
                          onClick={() => handleRemoveIntervention(intervention.id)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      )}
                    </div>
                  </div>
                  
                  {intervention.codes && intervention.codes.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {intervention.codes.map((code: { code?: string; decode?: string; codeSystem?: string }, ci: number) => (
                        <CodeLink key={ci} code={code.code} decode={code.decode} codeSystem={code.codeSystem} variant="secondary" className="text-xs" />
                      ))}
                    </div>
                  )}

                  {/* OpenFDA drug label enrichment */}
                  {(intervention.name || intervention.label) && (
                    <DrugInfoPanel drugName={(intervention.name || intervention.label)!} />
                  )}
                </div>
              ))}
            </div>
            {isEditMode && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleAddIntervention}
                className="mt-3 w-full border-dashed"
              >
                <Plus className="h-4 w-4 mr-2" />
                Add Intervention
              </Button>
            )}
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
                    path={versionPath('administrableProducts', product.id, 'name')}
                    value={product.label || product.name || `Product ${i + 1}`}
                    label=""
                    className="font-medium"
                    placeholder="Product name"
                  />
                  
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3 text-sm">
                    <EditableField
                      path={versionPath('administrableProducts', product.id, 'administrableDoseForm/decode')}
                      value={product.administrableDoseForm?.decode || product.administrableDoseForm?.standardCode?.decode || ''}
                      label="Dose Form"
                      placeholder="Not specified"
                    />
                    <EditableCodedValue
                      path={versionPath('administrableProducts', product.id, 'routeOfAdministration')}
                      value={product.routeOfAdministration}
                      label="Route"
                      options={CDISC_TERMINOLOGIES.routeOfAdministration}
                      showCode
                      placeholder="Not specified"
                    />
                    <EditableField
                      path={versionPath('administrableProducts', product.id, 'strength')}
                      value={product.strength || ''}
                      label="Strength"
                      placeholder="Not specified"
                    />
                    <EditableCodedValue
                      path={versionPath('administrableProducts', product.id, 'productDesignation')}
                      value={product.productDesignation}
                      label="Designation"
                      options={CDISC_TERMINOLOGIES.productDesignation ?? []}
                      showCode
                      placeholder="Not specified"
                    />
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-2 text-sm">
                    <EditableCodedValue
                      path={versionPath('administrableProducts', product.id, 'sourcing')}
                      value={product.sourcing}
                      label="Sourcing"
                      options={CDISC_TERMINOLOGIES.productSourcing ?? []}
                      showCode
                      placeholder="Not specified"
                    />
                    <EditableField
                      path={versionPath('administrableProducts', product.id, 'pharmacologicClass/decode')}
                      value={product.pharmacologicClass?.decode || ''}
                      label="Pharmacologic Class"
                      placeholder="Not specified"
                    />
                    <EditableField
                      path={versionPath('administrableProducts', product.id, 'manufacturer')}
                      value={product.manufacturer || ''}
                      label="Manufacturer"
                      placeholder="Not specified"
                    />
                  </div>
                  
                  <EditableField
                    path={versionPath('administrableProducts', product.id, 'description')}
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
                    path={entityPath('/administrations', admin.id, 'name')}
                    value={admin.name || `Administration ${i + 1}`}
                    className="font-medium"
                    placeholder="Administration name"
                  />
                  
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3 text-sm">
                    <EditableCodedValue
                      path={entityPath('/administrations', admin.id, 'route')}
                      value={admin.route}
                      label="Route"
                      options={CDISC_TERMINOLOGIES.routeOfAdministration}
                      showCode
                      placeholder="Route"
                    />
                    {admin.frequency?.decode && (
                      <div>
                        <span className="text-muted-foreground">Frequency</span>
                        <EditableField
                          path={entityPath('/administrations', admin.id, 'frequency/decode')}
                          value={admin.frequency.decode}
                          placeholder="Frequency"
                        />
                      </div>
                    )}
                    {(admin.dose || admin.doseDescription) && (
                      <div>
                        <span className="text-muted-foreground">Dose</span>
                        <EditableField
                          path={entityPath('/administrations', admin.id, 'dose')}
                          value={
                            typeof admin.dose === 'object' && admin.dose
                              ? `${admin.dose.value ?? ''} ${admin.dose.unit?.decode ?? ''}`.trim()
                              : (admin.dose as string) || admin.doseDescription || ''
                          }
                          placeholder="Dose"
                        />
                      </div>
                    )}
                    {(admin.duration || admin.durationDescription) && (
                      <div>
                        <span className="text-muted-foreground">Duration</span>
                        <EditableField
                          path={entityPath('/administrations', admin.id, 'duration')}
                          value={admin.duration || admin.durationDescription || ''}
                          placeholder="Duration"
                        />
                      </div>
                    )}
                  </div>
                  
                  {admin.description && (
                    <EditableField
                      path={entityPath('/administrations', admin.id, 'description')}
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
                        path={entityPath('/substances', substance.id, 'substanceName')}
                        value={substance.substanceName || substance.name || `Substance ${i + 1}`}
                        label=""
                        className="font-medium"
                        placeholder="Substance name"
                      />
                      <EditableField
                        path={entityPath('/substances', substance.id, 'description')}
                        value={substance.description || ''}
                        label=""
                        type="textarea"
                        className="text-sm text-muted-foreground mt-1"
                        placeholder="No description"
                      />
                    </div>
                    <EditableCodedValue
                      path={entityPath('/substances', substance.id, 'substanceType')}
                      value={substance.substanceType}
                      options={CDISC_TERMINOLOGIES.substanceType}
                      showCode
                      placeholder="Type"
                      className="shrink-0"
                    />
                  </div>
                  {substance.codes && substance.codes.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {substance.codes.map((code: { code?: string; decode?: string; codeSystem?: string }, ci: number) => (
                        <CodeLink key={ci} code={code.code} decode={`${code.code}: ${code.decode || 'N/A'}`} codeSystem={code.codeSystem} variant="secondary" className="text-xs font-mono" />
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
                      <EditableCodedValue
                        path={entityPath('/ingredients', ingredient.id, 'role')}
                        value={ingredient.role}
                        options={CDISC_TERMINOLOGIES.ingredientRole}
                        showCode
                        placeholder="Role"
                        className="shrink-0"
                      />
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
