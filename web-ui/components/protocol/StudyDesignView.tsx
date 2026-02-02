'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { GitBranch, Layers, Grid3X3, Shield, AlertTriangle, Info, CheckCircle2, Shuffle } from 'lucide-react';

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

interface Masking {
  id: string;
  text?: string;
  isMasked?: boolean;
}

interface ClassifiedIssue {
  severity: 'blocking' | 'warning' | 'info';
  category: string;
  message: string;
  suggestion?: string;
  affectedIds?: string[];
}

interface AllocationRatio {
  ratio?: string;
}

interface CrossoverDesign {
  isCrossover?: boolean;
  numPeriods?: number;
  numSequences?: number;
  periods?: string[];
  sequences?: string[];
  washoutDuration?: string;
  washoutRequired?: boolean;
}

interface ActivityGroup {
  id: string;
  name?: string;
  label?: string;
  description?: string;
  activityIds?: string[];
  childIds?: string[];
  activityNames?: string[];
}

interface TransitionRule {
  id: string;
  name?: string;
  description?: string;
  text?: string;
  condition?: string;
  fromEpochId?: string;
  toEpochId?: string;
}

interface Activity {
  id: string;
  name?: string;
  label?: string;
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
  // Handle both 'elements' and 'studyElements' keys
  const elements = (design.studyElements as StudyElement[]) ?? (design.elements as StudyElement[]) ?? [];
  const maskingRoles = (design.maskingRoles as Masking[]) ?? [];
  
  // Build lookup maps
  const armMap = new Map(arms.map(a => [a.id, a]));
  const epochMap = new Map(epochs.map(e => [e.id, e]));
  const elementMap = new Map(elements.map(e => [e.id, e]));

  // Design metadata
  const studyType = (design.studyType as { decode?: string })?.decode;
  const blindingSchema = (design.blindingSchema as { standardCode?: { decode?: string } })?.standardCode?.decode;
  const modelObj = design.model as { decode?: string; code?: string } | undefined;
  const model = modelObj?.decode;
  const modelCode = modelObj?.code;
  
  // Extended study design info
  const allocationRatio = (design.allocationRatio as AllocationRatio)?.ratio;
  
  // Extract extension attributes for reconciliation info
  const extensionAttributes = (design.extensionAttributes as { url?: string; valueJson?: unknown }[]) ?? [];
  
  // Find classified issues from reconciliation layer
  const classifiedIssuesExt = extensionAttributes.find(e => e.url === 'x-executionModel-classifiedIssues');
  const classifiedIssues = (classifiedIssuesExt?.valueJson as ClassifiedIssue[]) ?? [];
  
  // Find crossover design from extension
  const crossoverExt = extensionAttributes.find(e => e.url === 'x-executionModel-crossoverDesign');
  const crossoverDesign = crossoverExt?.valueJson as CrossoverDesign | undefined;

  // Activity groups
  const activityGroups = (design.activityGroups as ActivityGroup[]) ?? [];
  const activities = (design.activities as Activity[]) ?? [];
  const activityMap = new Map(activities.map(a => [a.id, a]));

  // Transition rules (from top-level)
  const transitionRules = (usdm.transitionRules as TransitionRule[]) ?? [];

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
                <div className="flex items-center gap-2">
                  <p className="font-medium">{model}</p>
                  {modelCode && (
                    <Badge variant="outline" className="text-xs font-mono">
                      {modelCode}
                    </Badge>
                  )}
                </div>
              </div>
            )}
            {blindingSchema && (
              <div>
                <span className="text-sm text-muted-foreground">Blinding</span>
                <p className="font-medium">{blindingSchema}</p>
              </div>
            )}
            {allocationRatio && (
              <div>
                <span className="text-sm text-muted-foreground">Randomization</span>
                <p className="font-medium">{allocationRatio}</p>
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
            <div>
              <span className="text-sm text-muted-foreground">Elements</span>
              <p className="font-medium">{elements.length}</p>
            </div>
            {maskingRoles.length > 0 && (
              <div>
                <span className="text-sm text-muted-foreground">Masking</span>
                <p className="font-medium">
                  {maskingRoles.some(m => m.isMasked) ? 'Yes' : 'No'} ({maskingRoles.length})
                </p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Crossover Design (when valid) */}
      {crossoverDesign?.isCrossover && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shuffle className="h-5 w-5" />
              Crossover Design
              <Badge variant="default">Detected</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <span className="text-sm text-muted-foreground">Periods</span>
                <p className="font-medium">{crossoverDesign.numPeriods ?? 'N/A'}</p>
              </div>
              <div>
                <span className="text-sm text-muted-foreground">Sequences</span>
                <p className="font-medium">{crossoverDesign.numSequences ?? 'N/A'}</p>
              </div>
              {crossoverDesign.washoutDuration && (
                <div>
                  <span className="text-sm text-muted-foreground">Washout</span>
                  <p className="font-medium">{crossoverDesign.washoutDuration}</p>
                </div>
              )}
              {crossoverDesign.sequences && crossoverDesign.sequences.length > 0 && (
                <div>
                  <span className="text-sm text-muted-foreground">Sequence Order</span>
                  <div className="flex gap-1 flex-wrap mt-1">
                    {crossoverDesign.sequences.map((seq, i) => (
                      <Badge key={i} variant="secondary">{seq}</Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Design Classification Issues */}
      {classifiedIssues.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              Design Classification Notes
              <Badge variant="outline">{classifiedIssues.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {classifiedIssues.map((issue, i) => (
                <div 
                  key={i} 
                  className={`p-3 border rounded-lg ${
                    issue.severity === 'blocking' ? 'border-red-300 bg-red-50 dark:bg-red-950/20' :
                    issue.severity === 'warning' ? 'border-amber-300 bg-amber-50 dark:bg-amber-950/20' :
                    'border-blue-300 bg-blue-50 dark:bg-blue-950/20'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    {issue.severity === 'blocking' ? (
                      <AlertTriangle className="h-4 w-4 text-red-500" />
                    ) : issue.severity === 'warning' ? (
                      <AlertTriangle className="h-4 w-4 text-amber-500" />
                    ) : (
                      <Info className="h-4 w-4 text-blue-500" />
                    )}
                    <Badge variant={
                      issue.severity === 'blocking' ? 'destructive' :
                      issue.severity === 'warning' ? 'default' : 'secondary'
                    }>
                      {issue.category.replace(/_/g, ' ')}
                    </Badge>
                  </div>
                  <p className="text-sm">{issue.message}</p>
                  {issue.suggestion && (
                    <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                      <CheckCircle2 className="h-3 w-3" />
                      {issue.suggestion}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

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

      {/* Masking */}
      {maskingRoles.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-5 w-5" />
              Masking
              <Badge variant="secondary">{maskingRoles.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {maskingRoles.map((mask, i) => (
                <div key={mask.id || i} className="flex items-center gap-2">
                  <Badge variant={mask.isMasked ? "default" : "outline"}>
                    {mask.isMasked ? "Masked" : "Unmasked"}
                  </Badge>
                  <span className="text-sm">{mask.text || `Role ${i + 1}`}</span>
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

      {/* Activity Groups */}
      {activityGroups.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Layers className="h-5 w-5" />
              Activity Groups
              <Badge variant="secondary">{activityGroups.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {activityGroups.map((group, i) => {
                // Use childIds or activityIds to look up activities
                const idList = group.childIds ?? group.activityIds ?? [];
                const groupActivities = idList
                  .map(id => activityMap.get(id))
                  .filter(Boolean);
                // Fallback to activityNames if no activities found by ID
                const displayNames = groupActivities.length > 0
                  ? groupActivities.map(a => a?.name || a?.label || 'Activity')
                  : (group.activityNames ?? []);
                const activityCount = displayNames.length || idList.length;
                
                return (
                  <div key={group.id || i} className="p-3 border rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-medium">
                        {group.name || group.label || `Group ${i + 1}`}
                      </span>
                      <Badge variant="secondary">
                        {activityCount} activities
                      </Badge>
                    </div>
                    {group.description && (
                      <p className="text-sm text-muted-foreground mb-2">{group.description}</p>
                    )}
                    {displayNames.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {displayNames.map((name, ai) => (
                          <Badge key={ai} variant="outline" className="text-xs">
                            {name}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Transition Rules */}
      {transitionRules.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <GitBranch className="h-5 w-5" />
              Transition Rules
              <Badge variant="secondary">{transitionRules.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {transitionRules.map((rule, i) => {
                const fromEpoch = epochMap.get(rule.fromEpochId || '');
                const toEpoch = epochMap.get(rule.toEpochId || '');
                return (
                  <div key={rule.id || i} className="p-3 border rounded-lg bg-gradient-to-r from-purple-50/50 to-transparent dark:from-purple-950/20">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="font-medium">
                        {rule.name || `Rule ${i + 1}`}
                      </span>
                      {fromEpoch && toEpoch && (
                        <div className="flex items-center gap-1 text-sm text-muted-foreground">
                          <Badge variant="outline">{fromEpoch.name || fromEpoch.label}</Badge>
                          <span>→</span>
                          <Badge variant="outline">{toEpoch.name || toEpoch.label}</Badge>
                        </div>
                      )}
                    </div>
                    {(rule.description || rule.text || rule.condition) && (
                      <p className="text-sm text-muted-foreground">
                        {rule.description || rule.text || rule.condition}
                      </p>
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

export default StudyDesignView;
