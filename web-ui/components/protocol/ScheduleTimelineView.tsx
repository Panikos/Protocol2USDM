'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { EditableField } from '@/components/semantic';
import { designPath } from '@/lib/semantic/schema';
import { EpochTimelineChart } from './EpochTimelineChart';
import { 
  Calendar, 
  Clock, 
  ChevronDown, 
  ChevronRight,
  Activity,
  Timer,
  ArrowRight,
} from 'lucide-react';

interface ScheduleTimelineViewProps {
  usdm: Record<string, unknown> | null;
}

interface ScheduledActivityInstance {
  id: string;
  activityId?: string;
  activityIds?: string[];
  encounterId?: string;
  epochId?: string;
  name?: string;
  scheduledAt?: string;
  scheduledAtTimingId?: string;
  instanceType?: string;
}

interface Timing {
  id: string;
  name?: string;
  label?: string;
  description?: string;
  type?: { decode?: string };
  value?: string | { value?: string; unit?: string };
  valueLabel?: string;
  valueMin?: string | { value?: string; unit?: string };
  valueMax?: string | { value?: string; unit?: string };
  relativeToFrom?: string | { decode?: string };
  relativeToFromId?: string;
  relativeFromScheduledInstanceId?: string;
  windowBefore?: string | { value?: string; unit?: string };
  windowAfter?: string | { value?: string; unit?: string };
  windowLower?: string;
  windowUpper?: string;
  instanceType?: string;
}

interface ScheduleTimeline {
  id: string;
  name?: string;
  label?: string;
  description?: string;
  mainTimeline?: boolean;
  instances?: ScheduledActivityInstance[];
  timings?: Timing[];
  exits?: { id: string; condition?: string }[];
  instanceType?: string;
}

interface Activity {
  id: string;
  name?: string;
  label?: string;
}

interface Encounter {
  id: string;
  name?: string;
  label?: string;
}

export function ScheduleTimelineView({ usdm }: ScheduleTimelineViewProps) {
  const [expandedTimelines, setExpandedTimelines] = useState<Set<string>>(new Set(['main']));
  const [showAllInstances, setShowAllInstances] = useState(false);

  if (!usdm) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Calendar className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
          <p className="text-muted-foreground">No USDM data available</p>
        </CardContent>
      </Card>
    );
  }

  // Extract data from USDM structure
  const study = usdm.study as Record<string, unknown> | undefined;
  const versions = (study?.versions as unknown[]) ?? [];
  const version = versions[0] as Record<string, unknown> | undefined;
  const studyDesigns = (version?.studyDesigns as Record<string, unknown>[]) ?? [];
  const studyDesign = studyDesigns[0] ?? {};

  // Get schedule timelines
  const scheduleTimelines = (studyDesign.scheduleTimelines as ScheduleTimeline[]) ?? [];
  
  // Get activities and encounters for reference
  const activities = (studyDesign.activities as Activity[]) ?? [];
  const encounters = (studyDesign.encounters as Encounter[]) ?? [];
  
  // Build lookup maps
  const activityMap = new Map(activities.map(a => [a.id, a]));
  const encounterMap = new Map(encounters.map(e => [e.id, e]));

  const hasData = scheduleTimelines.length > 0;

  if (!hasData) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Calendar className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
          <p className="text-muted-foreground">No schedule timeline data found</p>
          <p className="text-sm text-muted-foreground mt-2">
            Schedule timelines with activity instances will appear here when available
          </p>
        </CardContent>
      </Card>
    );
  }

  const toggleTimeline = (id: string) => {
    const newExpanded = new Set(expandedTimelines);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedTimelines(newExpanded);
  };

  // Calculate totals
  const totalInstances = scheduleTimelines.reduce((sum, tl) => sum + (tl.instances?.length || 0), 0);
  const totalTimings = scheduleTimelines.reduce((sum, tl) => sum + (tl.timings?.length || 0), 0);

  return (
    <div className="space-y-6">
      {/* Visual Epoch Timeline */}
      <EpochTimelineChart usdm={usdm} />

      {/* Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Calendar className="h-5 w-5 text-blue-600" />
              <div>
                <div className="text-2xl font-bold">{scheduleTimelines.length}</div>
                <div className="text-xs text-muted-foreground">Timelines</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-purple-600" />
              <div>
                <div className="text-2xl font-bold">{totalInstances}</div>
                <div className="text-xs text-muted-foreground">Scheduled Instances</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Timer className="h-5 w-5 text-green-600" />
              <div>
                <div className="text-2xl font-bold">{totalTimings}</div>
                <div className="text-xs text-muted-foreground">Timing Definitions</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Clock className="h-5 w-5 text-orange-600" />
              <div>
                <div className="text-2xl font-bold">{encounters.length}</div>
                <div className="text-xs text-muted-foreground">Encounters</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Timelines */}
      {scheduleTimelines.map((timeline, i) => {
        const isExpanded = expandedTimelines.has(timeline.id) || expandedTimelines.has('main');
        const instances = timeline.instances ?? [];
        const timings = timeline.timings ?? [];
        const displayedInstances = showAllInstances ? instances : instances.slice(0, 20);

        return (
          <Card key={timeline.id || i}>
            <CardHeader 
              className="cursor-pointer hover:bg-muted/50 transition-colors"
              onClick={() => toggleTimeline(timeline.id)}
            >
              <CardTitle className="flex items-center gap-2">
                {isExpanded ? (
                  <ChevronDown className="h-5 w-5" />
                ) : (
                  <ChevronRight className="h-5 w-5" />
                )}
                <Calendar className="h-5 w-5" />
                <EditableField
                  path={timeline.id ? designPath('scheduleTimelines', timeline.id, 'name') : `/study/versions/0/studyDesigns/0/scheduleTimelines/${i}/name`}
                  value={timeline.name || timeline.label || `Timeline ${i + 1}`}
                  label=""
                  className="font-semibold"
                  placeholder="Timeline name"
                />
                {timeline.mainTimeline && (
                  <Badge variant="default">Main</Badge>
                )}
                <Badge variant="secondary">{instances.length} instances</Badge>
                <Badge variant="outline">{timings.length} timings</Badge>
              </CardTitle>
            </CardHeader>
            
            {isExpanded && (
              <CardContent className="space-y-6">
                <EditableField
                  path={timeline.id ? designPath('scheduleTimelines', timeline.id, 'description') : `/study/versions/0/studyDesigns/0/scheduleTimelines/${i}/description`}
                  value={timeline.description || ''}
                  label=""
                  type="textarea"
                  className="text-sm text-muted-foreground"
                  placeholder="No description"
                />

                {/* Timing Definitions */}
                {timings.length > 0 && (
                  <div>
                    <h4 className="font-medium mb-3 flex items-center gap-2">
                      <Timer className="h-4 w-4" />
                      Timing Definitions
                    </h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {timings.map((timing, ti) => (
                        <div key={timing.id || ti} className="p-3 bg-muted rounded-lg">
                          <EditableField
                            path={timing.id && timeline.id
                              ? `/study/versions/0/studyDesigns/0/scheduleTimelines/@id:${timeline.id}/timings/@id:${timing.id}/name`
                              : `/study/versions/0/studyDesigns/0/scheduleTimelines/${i}/timings/${ti}/name`}
                            value={timing.name || timing.label || `Timing ${ti + 1}`}
                            label=""
                            className="font-medium text-sm"
                            placeholder="Timing name"
                          />
                          <div className="text-xs text-muted-foreground mt-1 space-y-1">
                            {timing.type?.decode && (
                              <div>Type: <Badge variant="outline" className="text-xs">{timing.type.decode}</Badge></div>
                            )}
                            {(timing.value || timing.valueLabel) && (
                              <div>Value: {timing.valueLabel || (typeof timing.value === 'object' ? `${timing.value.value || ''} ${timing.value.unit || ''}`.trim() : timing.value)}</div>
                            )}
                            {(timing.windowBefore || timing.windowAfter || timing.windowLower || timing.windowUpper) && (
                              <div>
                                Window: {timing.windowLower || (typeof timing.windowBefore === 'object' ? `${timing.windowBefore.value || '0'} ${timing.windowBefore.unit || ''}`.trim() : (timing.windowBefore || '0'))} / {timing.windowUpper || (typeof timing.windowAfter === 'object' ? `${timing.windowAfter.value || '0'} ${timing.windowAfter.unit || ''}`.trim() : (timing.windowAfter || '0'))}
                              </div>
                            )}
                            {timing.relativeToFrom && (
                              <div className="flex items-center gap-1">
                                <ArrowRight className="h-3 w-3" />
                                Relative to: {typeof timing.relativeToFrom === 'object' ? timing.relativeToFrom.decode : timing.relativeToFrom}
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Scheduled Activity Instances */}
                {instances.length > 0 && (
                  <div>
                    <h4 className="font-medium mb-3 flex items-center gap-2">
                      <Activity className="h-4 w-4" />
                      Scheduled Activity Instances
                      <Badge variant="secondary">{instances.length}</Badge>
                    </h4>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm border-collapse">
                        <thead>
                          <tr className="bg-muted">
                            <th className="p-2 text-left border">Activity</th>
                            <th className="p-2 text-left border">Encounter</th>
                            <th className="p-2 text-left border">Scheduled At</th>
                          </tr>
                        </thead>
                        <tbody>
                          {displayedInstances.map((instance, ii) => {
                            // Handle both activityId (singular) and activityIds (array)
                            const activityIdList = instance.activityIds ?? (instance.activityId ? [instance.activityId] : []);
                            const activityNames = activityIdList
                              .map(id => activityMap.get(id))
                              .filter(Boolean)
                              .map(a => a?.name || a?.label)
                              .join(', ');
                            const encounter = encounterMap.get(instance.encounterId || '');
                            // Look up timing by ID for human-readable description
                            const timing = timings.find(t => t.id === instance.scheduledAtTimingId);
                            const timingDescription = timing 
                              ? (timing.name || timing.label || timing.description || instance.scheduledAtTimingId)
                              : (instance.scheduledAt || instance.scheduledAtTimingId || '-');
                            return (
                              <tr key={instance.id || ii} className="hover:bg-muted/50">
                                <td className="p-2 border">
                                  {activityNames || instance.name || '-'}
                                </td>
                                <td className="p-2 border">
                                  {encounter?.name || encounter?.label || instance.encounterId || '-'}
                                </td>
                                <td className="p-2 border text-sm">
                                  {timingDescription}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                    {instances.length > 20 && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setShowAllInstances(!showAllInstances);
                        }}
                        className="mt-3 flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400"
                      >
                        {showAllInstances ? (
                          <>
                            <ChevronDown className="h-4 w-4" />
                            Show less
                          </>
                        ) : (
                          <>
                            <ChevronRight className="h-4 w-4" />
                            Show all {instances.length} instances
                          </>
                        )}
                      </button>
                    )}
                  </div>
                )}

                {/* Timeline Exits */}
                {timeline.exits && timeline.exits.length > 0 && (
                  <div>
                    <h4 className="font-medium mb-2">Exit Conditions</h4>
                    <div className="space-y-2">
                      {timeline.exits.map((exit, ei) => (
                        <div key={exit.id || ei} className="p-2 bg-amber-50 dark:bg-amber-950/20 rounded border border-amber-200 dark:border-amber-800">
                          <span className="text-sm">{exit.condition || 'Exit condition'}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            )}
          </Card>
        );
      })}
    </div>
  );
}

export default ScheduleTimelineView;
