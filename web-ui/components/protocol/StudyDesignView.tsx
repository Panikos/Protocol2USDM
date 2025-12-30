'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { GitBranch, Layers, Grid3X3 } from 'lucide-react';

interface StudyDesignViewProps {
  usdm: Record<string, unknown> | null;
}

interface Arm {
  id: string;
  name?: string;
  label?: string;
  description?: string;
  type?: { decode?: string };
}

interface Epoch {
  id: string;
  name?: string;
  label?: string;
  description?: string;
  type?: { decode?: string };
}

interface StudyCell {
  id: string;
  armId?: string;
  epochId?: string;
  elementIds?: string[];
}

interface StudyElement {
  id: string;
  name?: string;
  label?: string;
  description?: string;
}

export function StudyDesignView({ usdm }: StudyDesignViewProps) {
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

  // Extract design components
  const arms = (design.arms as Arm[]) ?? [];
  const epochs = (design.epochs as Epoch[]) ?? [];
  const studyCells = (design.studyCells as StudyCell[]) ?? [];
  const elements = (design.elements as StudyElement[]) ?? [];
  
  // Build lookup maps
  const armMap = new Map(arms.map(a => [a.id, a]));
  const epochMap = new Map(epochs.map(e => [e.id, e]));
  const elementMap = new Map(elements.map(e => [e.id, e]));

  // Design metadata
  const studyType = (design.studyType as { decode?: string })?.decode;
  const blindingSchema = (design.blindingSchema as { standardCode?: { decode?: string } })?.standardCode?.decode;
  const model = (design.model as { decode?: string })?.decode;

  return (
    <div className="space-y-6">
      {/* Design Overview */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Grid3X3 className="h-5 w-5" />
            Design Overview
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {studyType && (
              <div>
                <span className="text-sm text-muted-foreground">Study Type</span>
                <p className="font-medium">{studyType}</p>
              </div>
            )}
            {model && (
              <div>
                <span className="text-sm text-muted-foreground">Model</span>
                <p className="font-medium">{model}</p>
              </div>
            )}
            {blindingSchema && (
              <div>
                <span className="text-sm text-muted-foreground">Blinding</span>
                <p className="font-medium">{blindingSchema}</p>
              </div>
            )}
            <div>
              <span className="text-sm text-muted-foreground">Arms</span>
              <p className="font-medium">{arms.length}</p>
            </div>
            <div>
              <span className="text-sm text-muted-foreground">Epochs</span>
              <p className="font-medium">{epochs.length}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Arms */}
      {arms.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <GitBranch className="h-5 w-5" />
              Study Arms
              <Badge variant="secondary">{arms.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {arms.map((arm, i) => (
                <div key={arm.id || i} className="p-3 border rounded-lg">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-medium">{arm.label || arm.name || `Arm ${i + 1}`}</span>
                    {arm.type?.decode && (
                      <Badge variant="outline">{arm.type.decode}</Badge>
                    )}
                  </div>
                  {arm.description && (
                    <p className="text-sm text-muted-foreground">{arm.description}</p>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Epochs */}
      {epochs.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Layers className="h-5 w-5" />
              Study Epochs
              <Badge variant="secondary">{epochs.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {epochs.map((epoch, i) => (
                <div key={epoch.id || i} className="p-3 border rounded-lg min-w-[150px]">
                  <div className="font-medium">{epoch.label || epoch.name || `Epoch ${i + 1}`}</div>
                  {epoch.type?.decode && (
                    <Badge variant="outline" className="mt-1">{epoch.type.decode}</Badge>
                  )}
                  {epoch.description && (
                    <p className="text-xs text-muted-foreground mt-1">{epoch.description}</p>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Study Cells Matrix */}
      {studyCells.length > 0 && arms.length > 0 && epochs.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Study Cells Matrix</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr>
                    <th className="border p-2 bg-muted text-left">Arm / Epoch</th>
                    {epochs.map((epoch, i) => (
                      <th key={epoch.id || i} className="border p-2 bg-muted text-center">
                        {epoch.label || epoch.name || `E${i + 1}`}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {arms.map((arm, ai) => (
                    <tr key={arm.id || ai}>
                      <td className="border p-2 font-medium bg-muted/50">
                        {arm.label || arm.name || `Arm ${ai + 1}`}
                      </td>
                      {epochs.map((epoch, ei) => {
                        const cell = studyCells.find(
                          c => c.armId === arm.id && c.epochId === epoch.id
                        );
                        const cellElements = (cell?.elementIds ?? [])
                          .map(id => elementMap.get(id))
                          .filter(Boolean);
                        
                        return (
                          <td key={epoch.id || ei} className="border p-2 text-center">
                            {cellElements.length > 0 ? (
                              <div className="flex flex-wrap gap-1 justify-center">
                                {cellElements.map((el, i) => (
                                  <Badge key={i} variant="secondary" className="text-xs">
                                    {el?.label || el?.name || 'Element'}
                                  </Badge>
                                ))}
                              </div>
                            ) : cell ? (
                              <span className="text-muted-foreground">✓</span>
                            ) : (
                              <span className="text-muted-foreground">-</span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default StudyDesignView;
