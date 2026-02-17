'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { 
  BarChart3, 
  CheckCircle2, 
  Link2, 
  FileCheck,
  Activity,
  Calendar,
  Layers,
  GitBranch,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface QualityMetricsDashboardProps {
  usdm: Record<string, unknown> | null;
}

interface EntityCounts {
  activities: number;
  activityGroups: number;
  encounters: number;
  epochs: number;
  arms: number;
  objectives: number;
  eligibilityCriteria: number;
  interventions: number;
  timings: number;
}

export function QualityMetricsDashboard({ usdm }: QualityMetricsDashboardProps) {
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

  // Calculate entity counts
  // USDM-compliant: timings are in scheduleTimeline.timings (per dataStructure.yml)
  const scheduleTimelines = (design?.scheduleTimelines as { timings?: unknown[] }[]) ?? [];
  const timingsCount = scheduleTimelines.reduce((sum, tl) => sum + (tl.timings?.length ?? 0), 0);
  
  const allActivities = (design?.activities as { childIds?: string[] }[]) ?? [];
  const leafActivityCount = allActivities.filter(a => !a.childIds || a.childIds.length === 0).length;
  const parentActivityCount = allActivities.filter(a => a.childIds && a.childIds.length > 0).length;

  const counts: EntityCounts = {
    activities: leafActivityCount,
    activityGroups: parentActivityCount,
    encounters: (design?.encounters as unknown[])?.length ?? 0,
    epochs: (design?.epochs as unknown[])?.length ?? 0,
    arms: (design?.arms as unknown[])?.length ?? 0,
    objectives: (design?.objectives as unknown[])?.length ?? 0,
    eligibilityCriteria: ((design?.eligibilityCriteria as unknown[])?.length ?? 0) +
                         ((version?.eligibilityCriterionItems as unknown[])?.length ?? 0),
    interventions: ((version?.studyInterventions as unknown[])?.length ?? 0) +
                   ((version?.administrableProducts as unknown[])?.length ?? 0),
    timings: timingsCount,
  };

  // Calculate field population metrics
  const fieldMetrics = calculateFieldPopulation(design, version);
  
  // Calculate linkage metrics
  const linkageMetrics = calculateLinkageAccuracy(design);

  return (
    <div className="space-y-6">
      {/* Entity Counts */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            Entity Counts
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MetricCard icon={<Activity className="h-4 w-4" />} label="Activities" value={counts.activities} />
            <MetricCard icon={<Activity className="h-4 w-4" />} label="Activity Groups" value={counts.activityGroups} />
            <MetricCard icon={<Calendar className="h-4 w-4" />} label="Encounters" value={counts.encounters} />
            <MetricCard icon={<Layers className="h-4 w-4" />} label="Epochs" value={counts.epochs} />
            <MetricCard icon={<GitBranch className="h-4 w-4" />} label="Arms" value={counts.arms} />
            <MetricCard icon={<CheckCircle2 className="h-4 w-4" />} label="Objectives" value={counts.objectives} />
            <MetricCard icon={<FileCheck className="h-4 w-4" />} label="Eligibility Criteria" value={counts.eligibilityCriteria} />
            <MetricCard icon={<Activity className="h-4 w-4" />} label="Interventions" value={counts.interventions} />
            <MetricCard icon={<Link2 className="h-4 w-4" />} label="Timings" value={counts.timings} />
          </div>
        </CardContent>
      </Card>

      {/* Field Population */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileCheck className="h-5 w-5" />
            Field Population Rate
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {fieldMetrics.map((metric, i) => (
              <div key={i}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="font-medium">{metric.entity}</span>
                  <span className={cn(
                    metric.rate >= 80 ? 'text-green-600' :
                    metric.rate >= 50 ? 'text-amber-600' :
                    'text-red-600'
                  )}>
                    {metric.filled}/{metric.total} ({metric.rate.toFixed(0)}%)
                  </span>
                </div>
                <Progress value={metric.rate} className="h-2" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Linkage Accuracy */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Link2 className="h-5 w-5" />
            Linkage Accuracy
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="text-center p-4 bg-muted rounded-lg">
              <div className={cn(
                'text-3xl font-bold',
                linkageMetrics.encounterEpoch >= 80 ? 'text-green-600' :
                linkageMetrics.encounterEpoch >= 50 ? 'text-amber-600' :
                'text-red-600'
              )}>
                {linkageMetrics.encounterEpoch.toFixed(0)}%
              </div>
              <div className="text-sm text-muted-foreground">Encounter → Epoch</div>
            </div>
            <div className="text-center p-4 bg-muted rounded-lg">
              <div className={cn(
                'text-3xl font-bold',
                linkageMetrics.activitySchedule >= 80 ? 'text-green-600' :
                linkageMetrics.activitySchedule >= 50 ? 'text-amber-600' :
                'text-red-600'
              )}>
                {linkageMetrics.activitySchedule.toFixed(0)}%
              </div>
              <div className="text-sm text-muted-foreground">Activity → Schedule</div>
            </div>
            <div className="text-center p-4 bg-muted rounded-lg">
              <div className={cn(
                'text-3xl font-bold',
                linkageMetrics.overall >= 80 ? 'text-green-600' :
                linkageMetrics.overall >= 50 ? 'text-amber-600' :
                'text-red-600'
              )}>
                {linkageMetrics.overall.toFixed(0)}%
              </div>
              <div className="text-sm text-muted-foreground">Overall Linkage</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* USDM Version Info */}
      <Card>
        <CardHeader>
          <CardTitle>USDM Information</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">USDM Version</span>
              <p className="font-medium">{String(usdm.usdmVersion ?? 'N/A')}</p>
            </div>
            <div>
              <span className="text-muted-foreground">Generator</span>
              <p className="font-medium">{String(usdm.generator ?? usdm.systemName ?? 'N/A')}</p>
            </div>
            <div>
              <span className="text-muted-foreground">Generated At</span>
              <p className="font-medium">
                {usdm.generatedAt ? new Date(String(usdm.generatedAt)).toLocaleDateString() : 'N/A'}
              </p>
            </div>
            <div>
              <span className="text-muted-foreground">Study Versions</span>
              <p className="font-medium">{versions.length}</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function MetricCard({ 
  icon, 
  label, 
  value 
}: { 
  icon: React.ReactNode; 
  label: string; 
  value: number;
}) {
  return (
    <div className="p-3 bg-muted rounded-lg">
      <div className="flex items-center gap-2 text-muted-foreground mb-1">
        {icon}
        <span className="text-xs">{label}</span>
      </div>
      <div className="text-2xl font-bold">{value}</div>
    </div>
  );
}

function calculateFieldPopulation(
  design: Record<string, unknown> | undefined,
  version: Record<string, unknown> | undefined
): { entity: string; filled: number; total: number; rate: number }[] {
  const metrics: { entity: string; filled: number; total: number; rate: number }[] = [];
  
  const checkFields = (items: unknown[], fields: string[], entityName: string) => {
    if (!items || items.length === 0) return;
    
    let filled = 0;
    const total = items.length * fields.length;
    
    for (const item of items as Record<string, unknown>[]) {
      for (const field of fields) {
        if (item[field] !== undefined && item[field] !== null && item[field] !== '') {
          filled++;
        }
      }
    }
    
    metrics.push({
      entity: entityName,
      filled,
      total,
      rate: total > 0 ? (filled / total) * 100 : 100,
    });
  };
  
  if (design) {
    // Only check required/meaningful fields, not optional ones like 'description'
    // Activities: name is required — only check leaf activities (exclude parent groups)
    const leafActs = (design.activities as { childIds?: string[] }[])?.filter(a => !a.childIds || a.childIds.length === 0) ?? [];
    checkFields(leafActs, ['name'], 'Activities');
    // Encounters: name is essential (epochId is resolved via schedule instances, not stored directly)
    checkFields(design.encounters as unknown[], ['name'], 'Encounters');
    // Epochs: name is the essential field (epochType often not populated from extraction)
    checkFields(design.epochs as unknown[], ['name'], 'Epochs');
    // Arms: name and type are essential
    checkFields(design.arms as unknown[], ['name', 'type'], 'Arms');
    // Objectives: text and level are essential
    checkFields(design.objectives as unknown[], ['text', 'level'], 'Objectives');
  }
  
  return metrics;
}

function calculateLinkageAccuracy(
  design: Record<string, unknown> | undefined
): { encounterEpoch: number; activitySchedule: number; overall: number } {
  if (!design) {
    return { encounterEpoch: 0, activitySchedule: 0, overall: 0 };
  }
  
  const encounters = (design.encounters as { id: string }[]) ?? [];
  const epochs = (design.epochs as { id: string }[]) ?? [];
  const epochIds = new Set(epochs.map(e => e.id));
  
  // Encounter → Epoch linkage via ScheduledActivityInstance bridge
  // USDM v4.0: encounters don't have epochId directly — the link is through
  // instances which carry both encounterId and epochId.
  const scheduleTimelines = (design.scheduleTimelines as {
    instances?: { activityIds?: string[]; encounterId?: string; epochId?: string }[];
  }[]) ?? [];
  const allInstances = scheduleTimelines.flatMap(tl => tl.instances ?? []);
  
  const encounterIdsWithEpoch = new Set<string>();
  for (const inst of allInstances) {
    if (inst.encounterId && inst.epochId && epochIds.has(inst.epochId)) {
      encounterIdsWithEpoch.add(inst.encounterId);
    }
  }
  const encounterEpoch = encounters.length > 0
    ? (encounters.filter(e => encounterIdsWithEpoch.has(e.id)).length / encounters.length) * 100
    : 100;
  
  // Activity → Schedule linkage
  // Exclude parent activities (groups with childIds) — they are never directly scheduled.
  // Also exclude procedure_enrichment activities.
  const allActivities = (design.activities as {
    id: string;
    childIds?: string[];
    extensionAttributes?: { url?: string; valueString?: string }[];
  }[]) ?? [];
  
  const scheduledActivityIds = new Set<string>();
  for (const inst of allInstances) {
    for (const actId of inst.activityIds ?? []) {
      scheduledActivityIds.add(actId);
    }
  }
  
  // Filter: exclude parent activities (groups) and procedure_enrichment
  const schedulableActivities = allActivities.filter(act => {
    // Exclude parent activities (they group children, not scheduled themselves)
    if (act.childIds && act.childIds.length > 0) return false;
    // Exclude procedure enrichment activities
    const sourceExt = act.extensionAttributes?.find(ext => ext.url?.endsWith('activitySource'));
    const source = sourceExt?.valueString;
    return source !== 'procedure_enrichment';
  });
  
  let activityLinked = 0;
  for (const act of schedulableActivities) {
    if (scheduledActivityIds.has(act.id)) {
      activityLinked++;
    }
  }
  const activitySchedule = schedulableActivities.length > 0
    ? (activityLinked / schedulableActivities.length) * 100
    : 100;
  
  // Overall
  const overall = (encounterEpoch + activitySchedule) / 2;
  
  return { encounterEpoch, activitySchedule, overall };
}

export default QualityMetricsDashboard;
