'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Pill, Syringe, Clock } from 'lucide-react';

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

  // Get interventions from multiple possible locations
  const studyInterventions = (design?.studyInterventions as StudyIntervention[]) ?? 
                             (version?.studyInterventions as StudyIntervention[]) ?? [];
  
  const administrableProducts = (version?.administrableProducts as AdministrableProduct[]) ?? [];

  if (studyInterventions.length === 0 && administrableProducts.length === 0) {
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
                    <div>
                      <h4 className="font-medium">
                        {intervention.label || intervention.name || `Intervention ${i + 1}`}
                      </h4>
                      {intervention.description && (
                        <p className="text-sm text-muted-foreground mt-1">
                          {intervention.description}
                        </p>
                      )}
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
                  <h4 className="font-medium">
                    {product.label || product.name || `Product ${i + 1}`}
                  </h4>
                  
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3 text-sm">
                    {product.formulation && (
                      <div>
                        <span className="text-muted-foreground">Formulation</span>
                        <p>{product.formulation}</p>
                      </div>
                    )}
                    {product.route?.decode && (
                      <div>
                        <span className="text-muted-foreground">Route</span>
                        <p>{product.route.decode}</p>
                      </div>
                    )}
                    {product.dosage && (
                      <div>
                        <span className="text-muted-foreground">Dosage</span>
                        <p>{product.dosage}</p>
                      </div>
                    )}
                    {product.strength && (
                      <div>
                        <span className="text-muted-foreground">Strength</span>
                        <p>{product.strength}</p>
                      </div>
                    )}
                  </div>
                  
                  {product.description && (
                    <p className="text-sm text-muted-foreground mt-2">
                      {product.description}
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

export default InterventionsView;
