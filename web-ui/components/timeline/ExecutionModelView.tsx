'use client';

import { useState, useMemo } from 'react';
import { 
  Anchor, 
  Calendar, 
  FileText, 
  Repeat, 
  Activity,
  Clock,
  Pill,
  GitBranch,
  Search,
  ChevronDown,
  ChevronUp,
  ChevronRight,
  AlertTriangle,
  Filter,
  AlertCircle,
  XCircle,
  Info,
  LogOut,
  ListTree,
  BarChart3,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useProtocolStore, type USDMStudyDesign } from '@/stores/protocolStore';

// Types for execution model data
interface TimeAnchor {
  id: string;
  definition: string;
  anchorType: string;
  timelineId?: string | null;
  dayValue?: number;
  sourceText?: string;
}

interface VisitWindow {
  id: string;
  visitName: string;
  targetDay: number;
  targetWeek?: number;
  windowBefore: number;
  windowAfter: number;
  isRequired: boolean;
  visitNumber?: number;
  epoch?: string;
  sourceText?: string;
}

interface FootnoteCondition {
  id: string;
  conditionType: string;
  text: string;
  footnoteId?: string;
  structuredCondition?: string;
  appliesToActivityIds?: string[];
  sourceText?: string;
}

interface Repetition {
  id: string;
  type: string;
  interval?: string;
  count?: number;
  activityIds?: string[];
  sourceText?: string;
}

interface DosingRegimen {
  id: string;
  treatmentName: string;
  frequency: string;
  route: string;
  startDay?: number;
  doseLevels?: { amount: number; unit: string }[];
  titrationSchedule?: string;
  doseModifications?: string[];
}

interface StateMachine {
  id: string;
  initialState: string;
  terminalStates: string[];
  states: string[];
  transitions: { fromState: string; toState: string; trigger: string }[];
}

interface TraversalConstraint {
  id: string;
  requiredSequence?: string[];
  allowEarlyExit?: boolean;
  exitEpochIds?: string[];
  mandatoryVisits?: string[];
  sourceText?: string;
}

interface ExecutionType {
  activityId: string;
  executionType: string;
  rationale?: string;
}

interface ClassifiedIssue {
  severity: 'blocking' | 'warning' | 'info';
  category: string;
  message: string;
  affectedPath?: string;
  affectedIds?: string[];
  suggestion?: string;
}

interface StudyExit {
  id: string;
  name: string;
  exitType: string;
  description?: string;
}

interface TimingDetail {
  id: string;
  name: string;
  type?: string;
  value?: string;
  valueLabel?: string;
  relativeToFrom?: string;
  windowLower?: string;
  windowUpper?: string;
}

interface ScheduledInstance {
  id: string;
  name: string;
  activityIds?: string[];
  epochId?: string;
  encounterId?: string;
  timingId?: string;
}

interface ExecutionModelData {
  timeAnchors?: TimeAnchor[];
  visitWindows?: VisitWindow[];
  footnoteConditions?: FootnoteCondition[];
  repetitions?: Repetition[];
  dosingRegimens?: DosingRegimen[];
  stateMachine?: StateMachine;
  traversalConstraints?: TraversalConstraint[];
  executionTypes?: ExecutionType[];
  classifiedIssues?: ClassifiedIssue[];
  studyExits?: StudyExit[];
  timings?: TimingDetail[];
  scheduledInstances?: ScheduledInstance[];
}

type TabId = 'overview' | 'anchors' | 'visits' | 'conditions' | 'repetitions' | 'dosing' | 'statemachine' | 'traversal' | 'issues' | 'schedule';

interface ExecutionModelViewProps {
  executionModel?: ExecutionModelData;
}

export function ExecutionModelView({ executionModel }: ExecutionModelViewProps) {
  const [activeTab, setActiveTab] = useState<TabId>('overview');

  // Get execution model from extension attributes if not passed directly
  const studyDesign = useProtocolStore(state => 
    state.usdm?.study?.versions?.[0]?.studyDesigns?.[0]
  );
  
  const execModel = useMemo(() => {
    if (executionModel) return executionModel;
    
    // Try to get from extension attributes
    const extensions = (studyDesign?.extensionAttributes ?? []) as Array<{
      name?: string;
      url?: string;
      value?: unknown;
      valueString?: string;
    }>;
    
    let baseModel: ExecutionModelData | null = null;
    
    // Look for x-executionModel by name or URL pattern
    for (const ext of extensions) {
      if ((ext?.name === 'x-executionModel' || ext?.url?.includes('x-executionModel')) && ext?.value) {
        baseModel = ext.value as ExecutionModelData;
        break;
      }
    }
    
    // If no base model, create empty one
    if (!baseModel) {
      baseModel = {};
    }
    
    // Enrich with data from other extension attributes (classified issues, etc.)
    for (const ext of extensions) {
      const url = ext?.url ?? '';
      
      // Classified Issues
      if (url.includes('classifiedIssues') && ext?.valueString) {
        try {
          baseModel.classifiedIssues = JSON.parse(ext.valueString) as ClassifiedIssue[];
        } catch { /* ignore parse errors */ }
      }
      
      // Time Anchors
      if (url.includes('timeAnchors') && ext?.valueString && !baseModel.timeAnchors) {
        try {
          baseModel.timeAnchors = JSON.parse(ext.valueString) as TimeAnchor[];
        } catch { /* ignore parse errors */ }
      }
      
      // Visit Windows  
      if (url.includes('visitWindows') && ext?.valueString && !baseModel.visitWindows) {
        try {
          baseModel.visitWindows = JSON.parse(ext.valueString) as VisitWindow[];
        } catch { /* ignore parse errors */ }
      }
      
      // Footnote Conditions
      if (url.includes('footnoteConditions') && ext?.valueString && !baseModel.footnoteConditions) {
        try {
          baseModel.footnoteConditions = JSON.parse(ext.valueString) as FootnoteCondition[];
        } catch { /* ignore parse errors */ }
      }
      
      // Repetitions
      if (url.includes('repetitions') && ext?.valueString && !baseModel.repetitions) {
        try {
          baseModel.repetitions = JSON.parse(ext.valueString) as Repetition[];
        } catch { /* ignore parse errors */ }
      }
      
      // Dosing Regimens
      if (url.includes('dosingRegimens') && ext?.valueString && !baseModel.dosingRegimens) {
        try {
          baseModel.dosingRegimens = JSON.parse(ext.valueString) as DosingRegimen[];
        } catch { /* ignore parse errors */ }
      }
      
      // Traversal Constraints
      if (url.includes('traversalConstraints') && ext?.valueString && !baseModel.traversalConstraints) {
        try {
          baseModel.traversalConstraints = JSON.parse(ext.valueString) as TraversalConstraint[];
        } catch { /* ignore parse errors */ }
      }
      
      // Execution Types
      if (url.includes('executionTypes') && ext?.valueString && !baseModel.executionTypes) {
        try {
          baseModel.executionTypes = JSON.parse(ext.valueString) as ExecutionType[];
        } catch { /* ignore parse errors */ }
      }
      
      // State Machine
      if (url.includes('stateMachine') && ext?.valueString && !baseModel.stateMachine) {
        try {
          baseModel.stateMachine = JSON.parse(ext.valueString) as StateMachine;
        } catch { /* ignore parse errors */ }
      }
    }
    
    // Get scheduled instances, timings, and exits from scheduleTimelines
    // Use the typed interface from protocolStore
    const scheduleTimelines = studyDesign?.scheduleTimelines;
    
    if (scheduleTimelines && scheduleTimelines.length > 0) {
      const timeline = scheduleTimelines[0];
      
      // Scheduled instances
      if (timeline.instances && timeline.instances.length > 0 && !baseModel.scheduledInstances) {
        baseModel.scheduledInstances = timeline.instances.map(inst => ({
          id: inst.id,
          name: inst.name ?? inst.label ?? 'Unknown',
          activityIds: inst.activityIds ?? (inst.activityId ? [inst.activityId] : undefined),
          epochId: inst.epochId,
          encounterId: inst.encounterId,
          timingId: (inst as Record<string, unknown>).timingId as string | undefined,
        }));
      }
      
      // Timings - transform from USDM format
      if (timeline.timings && timeline.timings.length > 0 && !baseModel.timings) {
        baseModel.timings = timeline.timings.map(t => ({
          id: t.id,
          name: t.name ?? t.label ?? 'Unknown',
          type: typeof t.type === 'object' ? t.type?.decode : t.type,
          value: typeof t.value === 'number' ? `P${t.value}D` : t.value,
          valueLabel: t.valueLabel,
          relativeToFrom: typeof t.relativeToFrom === 'object' ? t.relativeToFrom?.decode : t.relativeTo,
          windowLower: typeof t.windowLower === 'number' ? `P${t.windowLower}D` : t.windowLower,
          windowUpper: typeof t.windowUpper === 'number' ? `P${t.windowUpper}D` : t.windowUpper,
        }));
      }
      
      // Study exits
      if (timeline.exits && timeline.exits.length > 0 && !baseModel.studyExits) {
        baseModel.studyExits = timeline.exits.map(exit => ({
          id: exit.id,
          name: (exit as Record<string, unknown>).name as string ?? 'Unknown Exit',
          exitType: (exit as Record<string, unknown>).exitType as string ?? 'Unknown',
          description: (exit as Record<string, unknown>).description as string | undefined,
        }));
      }
    }
    
    return baseModel;
  }, [executionModel, studyDesign]);

  // Build epoch ID to name map from USDM epochs
  const epochNameMap = useMemo(() => {
    const map: Record<string, string> = {};
    const epochs = (studyDesign?.epochs ?? []) as Array<{ id?: string; name?: string }>;
    for (const epoch of epochs) {
      if (epoch.id && epoch.name) {
        map[epoch.id] = epoch.name;
      }
    }
    return map;
  }, [studyDesign]);

  // Count blocking issues for badge
  const blockingIssueCount = execModel?.classifiedIssues?.filter(i => i.severity === 'blocking').length ?? 0;
  const totalIssueCount = execModel?.classifiedIssues?.length ?? 0;

  const tabs = [
    { id: 'overview' as TabId, label: 'Overview', icon: <Activity className="h-4 w-4" /> },
    { id: 'anchors' as TabId, label: 'Time Anchors', icon: <Anchor className="h-4 w-4" />, count: execModel?.timeAnchors?.length },
    { id: 'visits' as TabId, label: 'Visit Windows', icon: <Calendar className="h-4 w-4" />, count: execModel?.visitWindows?.length },
    { id: 'conditions' as TabId, label: 'Conditions', icon: <FileText className="h-4 w-4" />, count: execModel?.footnoteConditions?.length },
    { id: 'repetitions' as TabId, label: 'Repetitions', icon: <Repeat className="h-4 w-4" />, count: execModel?.repetitions?.length },
    { id: 'dosing' as TabId, label: 'Dosing', icon: <Pill className="h-4 w-4" />, count: execModel?.dosingRegimens?.length },
    { id: 'statemachine' as TabId, label: 'State Machine', icon: <GitBranch className="h-4 w-4" />, count: execModel?.studyExits?.length },
    { id: 'traversal' as TabId, label: 'Traversal', icon: <Clock className="h-4 w-4" />, count: execModel?.traversalConstraints?.length },
    { id: 'schedule' as TabId, label: 'Activity Schedule', icon: <ListTree className="h-4 w-4" />, count: execModel?.scheduledInstances?.length },
    { id: 'issues' as TabId, label: 'Data Quality', icon: blockingIssueCount > 0 ? <XCircle className="h-4 w-4 text-red-500" /> : <AlertCircle className="h-4 w-4" />, count: totalIssueCount, highlight: blockingIssueCount > 0 },
  ];

  if (!execModel) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Activity className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
          <h3 className="text-lg font-semibold mb-2">No Execution Model Available</h3>
          <p className="text-muted-foreground">
            The execution model has not been extracted for this protocol.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Tab Navigation */}
      <div className="flex flex-wrap gap-2 p-1 bg-muted rounded-lg">
        {tabs.map(tab => (
          <Button
            key={tab.id}
            variant={activeTab === tab.id ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setActiveTab(tab.id)}
            className="flex items-center gap-2"
          >
            {tab.icon}
            <span>{tab.label}</span>
            {tab.count !== undefined && tab.count > 0 && (
              <Badge variant="secondary" className="ml-1 h-5 px-1.5 text-xs">
                {tab.count}
              </Badge>
            )}
          </Button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="min-h-[500px]">
        {activeTab === 'overview' && <OverviewPanel data={execModel} />}
        {activeTab === 'anchors' && <TimeAnchorsPanel anchors={execModel.timeAnchors ?? []} />}
        {activeTab === 'visits' && <VisitWindowsPanel visits={execModel.visitWindows ?? []} anchors={execModel.timeAnchors ?? []} epochNameMap={epochNameMap} studyDesign={studyDesign} />}
        {activeTab === 'conditions' && <ConditionsPanel conditions={execModel.footnoteConditions ?? []} studyDesign={studyDesign} />}
        {activeTab === 'repetitions' && <RepetitionsPanel repetitions={execModel.repetitions ?? []} />}
        {activeTab === 'dosing' && <DosingPanel regimens={execModel.dosingRegimens ?? []} />}
        {activeTab === 'statemachine' && <StateMachinePanel stateMachine={execModel.stateMachine} studyExits={execModel.studyExits ?? []} />}
        {activeTab === 'traversal' && <TraversalPanel constraints={execModel.traversalConstraints ?? []} executionTypes={execModel.executionTypes ?? []} epochNameMap={epochNameMap} studyDesign={studyDesign} />}
        {activeTab === 'schedule' && <ActivitySchedulePanel instances={execModel.scheduledInstances ?? []} timings={execModel.timings ?? []} epochNameMap={epochNameMap} studyDesign={studyDesign} />}
        {activeTab === 'issues' && <DataQualityPanel issues={execModel.classifiedIssues ?? []} />}
      </div>
    </div>
  );
}

// ============================================================================
// Overview Panel
// ============================================================================

function OverviewPanel({ data }: { data: ExecutionModelData }) {
  const stats = [
    { label: 'Time Anchors', value: data.timeAnchors?.length ?? 0, icon: <Anchor className="h-5 w-5" />, color: 'bg-blue-500' },
    { label: 'Visit Windows', value: data.visitWindows?.length ?? 0, icon: <Calendar className="h-5 w-5" />, color: 'bg-green-500' },
    { label: 'Conditions', value: data.footnoteConditions?.length ?? 0, icon: <FileText className="h-5 w-5" />, color: 'bg-amber-500' },
    { label: 'Repetitions', value: data.repetitions?.length ?? 0, icon: <Repeat className="h-5 w-5" />, color: 'bg-purple-500' },
    { label: 'Dosing Regimens', value: data.dosingRegimens?.length ?? 0, icon: <Pill className="h-5 w-5" />, color: 'bg-pink-500' },
    { label: 'States', value: data.stateMachine?.states?.length ?? 0, icon: <GitBranch className="h-5 w-5" />, color: 'bg-cyan-500' },
  ];

  return (
    <div className="space-y-6">
      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {stats.map(stat => (
          <Card key={stat.label}>
            <CardContent className="pt-6">
              <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center text-white mb-3', stat.color)}>
                {stat.icon}
              </div>
              <p className="text-2xl font-bold">{stat.value}</p>
              <p className="text-sm text-muted-foreground">{stat.label}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Timeline Visualization */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Study Timeline
          </CardTitle>
          <CardDescription>
            Visual representation of the study schedule with visit windows
          </CardDescription>
        </CardHeader>
        <CardContent>
          <TimelineVisualization visits={data.visitWindows ?? []} anchors={data.timeAnchors ?? []} />
        </CardContent>
      </Card>

      {/* Quick Summary */}
      <div className="grid md:grid-cols-2 gap-4">
        {/* Anchor Summary */}
        {data.timeAnchors && data.timeAnchors.length > 0 && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Anchor className="h-4 w-4" />
                Primary Time Anchor
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                <p className="font-medium text-blue-900">{data.timeAnchors[0].anchorType}</p>
                <p className="text-sm text-blue-700 mt-1">{data.timeAnchors[0].definition}</p>
                {data.timeAnchors[0].dayValue !== undefined && (
                  <Badge className="mt-2 bg-blue-600">Day {data.timeAnchors[0].dayValue}</Badge>
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {/* State Machine Summary */}
        {data.stateMachine && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <GitBranch className="h-4 w-4" />
                Subject Flow
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="p-3 bg-cyan-50 border border-cyan-200 rounded-lg">
                <p className="text-sm text-cyan-700">
                  <span className="font-medium">Initial:</span> {data.stateMachine.initialState}
                </p>
                <p className="text-sm text-cyan-700 mt-1">
                  <span className="font-medium">States:</span> {data.stateMachine.states.length}
                </p>
                <p className="text-sm text-cyan-700 mt-1">
                  <span className="font-medium">Transitions:</span> {data.stateMachine.transitions.length}
                </p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Timeline Visualization
// ============================================================================

function TimelineVisualization({ visits, anchors }: { visits: VisitWindow[]; anchors: TimeAnchor[] }) {
  const [hoveredVisit, setHoveredVisit] = useState<string | null>(null);
  
  const sortedVisits = useMemo(() => {
    return [...visits].sort((a, b) => a.targetDay - b.targetDay);
  }, [visits]);

  if (sortedVisits.length === 0) {
    return (
      <div className="h-40 flex items-center justify-center text-muted-foreground">
        No visit windows available
      </div>
    );
  }

  // Calculate day range with padding
  const minDay = Math.min(...sortedVisits.map(v => v.targetDay - v.windowBefore)) - 5;
  const maxDay = Math.max(...sortedVisits.map(v => v.targetDay + v.windowAfter)) + 5;
  const range = maxDay - minDay || 1;

  // Calculate minimum width - ensure at least 120px per visit for readability
  const minWidthPx = Math.max(1000, sortedVisits.length * 120);

  // Generate tick marks for the axis
  const tickInterval = range > 200 ? 50 : range > 100 ? 20 : range > 50 ? 10 : 5;
  const ticks: number[] = [];
  const firstTick = Math.ceil(minDay / tickInterval) * tickInterval;
  for (let d = firstTick; d <= maxDay; d += tickInterval) {
    ticks.push(d);
  }
  // Always include Day 0 and Day 1 if in range
  if (minDay <= 0 && maxDay >= 0 && !ticks.includes(0)) ticks.push(0);
  if (minDay <= 1 && maxDay >= 1 && !ticks.includes(1)) ticks.push(1);
  ticks.sort((a, b) => a - b);

  // Find Day 1 anchor
  const day1Anchor = anchors.find(a => a.dayValue === 1 || a.anchorType === 'Day1' || a.anchorType === 'FirstDose');

  // Calculate positions with minimum spacing enforcement
  // First pass: calculate raw positions based on days
  const rawPositions = sortedVisits.map(v => ((v.targetDay - minDay) / range) * 100);
  
  // Second pass: enforce minimum spacing (at least 8% between visits)
  const minSpacing = 100 / Math.max(sortedVisits.length + 1, 12); // At least ~8% spacing
  const adjustedPositions: number[] = [];
  
  for (let i = 0; i < rawPositions.length; i++) {
    if (i === 0) {
      // First visit: use raw position but ensure it's at least 5% from left
      adjustedPositions.push(Math.max(5, rawPositions[i]));
    } else {
      // Subsequent visits: ensure minimum spacing from previous
      const minPos = adjustedPositions[i - 1] + minSpacing;
      adjustedPositions.push(Math.max(minPos, rawPositions[i]));
    }
  }
  
  // Normalize if we exceeded 95% (leave 5% margin on right)
  const maxPos = Math.max(...adjustedPositions);
  const scaleFactor = maxPos > 95 ? 90 / maxPos : 1;
  const finalPositions = adjustedPositions.map(p => p * scaleFactor + 5);

  // Position helper for day markers (still use raw day-based positioning)
  const getPosition = (day: number) => ((day - minDay) / range) * 100;
  
  // Position helper for visits (use adjusted positions)
  const getVisitPosition = (index: number) => finalPositions[index];

  return (
    <div className="relative select-none">
      {/* Scrollable timeline container */}
      <div className="overflow-x-auto pb-4">
        <div className="relative h-80 mt-16 mx-8" style={{ minWidth: `${minWidthPx}px` }}>
        
        {/* Axis baseline with gradient */}
        <div className="absolute top-1/2 left-0 right-0 h-1 bg-gradient-to-r from-gray-200 via-gray-400 to-gray-200 rounded-full" />
        
        {/* Day 1 anchor marker */}
        {day1Anchor && minDay <= 1 && maxDay >= 1 && (
          <div 
            className="absolute top-1/2 flex flex-col items-center z-20"
            style={{ left: `${getPosition(1)}%` }}
          >
            <div className="w-5 h-5 rounded-full bg-blue-600 border-2 border-white shadow-lg -translate-x-1/2 -translate-y-1/2 flex items-center justify-center">
              <Anchor className="w-3 h-3 text-white" />
            </div>
            <div className="absolute -top-8 -translate-x-1/2 px-2 py-1 bg-blue-600 text-white text-xs font-medium rounded shadow whitespace-nowrap">
              Day 1 - {day1Anchor.anchorType}
            </div>
          </div>
        )}

        {/* Visit windows and markers */}
        {sortedVisits.map((visit, index) => {
          // Use adjusted position to ensure spacing
          const leftPercent = getVisitPosition(index);
          const hasWindow = visit.windowBefore > 0 || visit.windowAfter > 0;
          const isHovered = hoveredVisit === visit.id;
          
          // Stagger labels: top for even, bottom for odd
          const isTop = index % 2 === 0;
          
          return (
            <div 
              key={visit.id} 
              className="absolute z-10"
              style={{ left: `${leftPercent}%`, top: '50%' }}
              onMouseEnter={() => setHoveredVisit(visit.id)}
              onMouseLeave={() => setHoveredVisit(null)}
            >
              {/* Window range indicator - fixed width visual showing window exists */}
              {hasWindow && (
                <div 
                  className={cn(
                    "absolute h-6 -translate-y-1/2 -translate-x-1/2 rounded-full transition-all duration-200",
                    visit.isRequired 
                      ? "bg-gradient-to-r from-green-200 via-green-100 to-green-200 border border-green-400"
                      : "bg-gradient-to-r from-gray-200 via-gray-100 to-gray-200 border border-gray-400",
                    isHovered && "ring-2 ring-offset-1 ring-green-500"
                  )}
                  style={{ 
                    width: `${Math.max(40, (visit.windowBefore + visit.windowAfter) * 2)}px`,
                  }}
                />
              )}
              
              {/* Visit marker dot */}
              <div 
                className={cn(
                  "w-4 h-4 rounded-full -translate-x-1/2 -translate-y-1/2 border-2 border-white shadow-md cursor-pointer transition-all duration-200",
                  visit.isRequired ? "bg-green-600" : "bg-gray-500",
                  isHovered && "scale-150 shadow-lg"
                )}
              />
              
              {/* Visit label - positioned well above/below the window visual */}
              <div 
                className={cn(
                  "absolute -translate-x-1/2 flex flex-col items-center transition-opacity duration-200",
                  isTop ? "-top-24" : "top-12",
                  isHovered ? "opacity-100" : "opacity-90"
                )}
              >
                <div className={cn(
                  "px-2 py-1 rounded text-center max-w-32 transition-all duration-200",
                  isHovered ? "bg-white shadow-lg border" : "bg-white/80"
                )}>
                  <span className="font-medium text-xs capitalize block truncate">
                    {visit.visitName}
                  </span>
                  <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                    Day {visit.targetDay}
                    {hasWindow && (
                      <span className="text-green-600 ml-1">
                        (±{Math.max(visit.windowBefore, visit.windowAfter)}d)
                      </span>
                    )}
                  </span>
                </div>
                {/* Connector line - longer to connect label to marker */}
                <div className={cn(
                  "w-px bg-gray-400",
                  isTop ? "h-8" : "h-6 order-first"
                )} />
              </div>

              {/* Hover tooltip with details */}
              {isHovered && (
                <div className={cn(
                  "absolute z-30 bg-white rounded-lg shadow-xl border p-3 min-w-48 text-sm",
                  isTop ? "top-10 -translate-x-1/2" : "-top-32 -translate-x-1/2"
                )}>
                  <div className="font-semibold capitalize mb-2">{visit.visitName}</div>
                  <div className="space-y-1 text-xs">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Target Day:</span>
                      <span className="font-medium">Day {visit.targetDay}</span>
                    </div>
                    {hasWindow && (
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Window:</span>
                        <span className="font-mono text-green-600">
                          -{visit.windowBefore} / +{visit.windowAfter} days
                        </span>
                      </div>
                    )}
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Required:</span>
                      <span className={visit.isRequired ? "text-green-600" : "text-gray-500"}>
                        {visit.isRequired ? "Yes" : "No"}
                      </span>
                    </div>
                    {visit.epoch && (
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Epoch:</span>
                        <span>{visit.epoch}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center justify-center gap-8 mt-6 text-xs">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded-full bg-green-600 border-2 border-white shadow" />
          <span>Required Visit</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded-full bg-gray-500 border-2 border-white shadow" />
          <span>Optional Visit</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-8 h-4 bg-gradient-to-r from-green-200 to-green-100 border border-green-400 rounded-full" />
          <span>Visit Window</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded-full bg-blue-600 flex items-center justify-center">
            <Anchor className="w-2.5 h-2.5 text-white" />
          </div>
          <span>Time Anchor</span>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Time Anchors Panel - Enhanced with duplicate detection
// ============================================================================

function TimeAnchorsPanel({ anchors }: { anchors: TimeAnchor[] }) {
  const [showFullSource, setShowFullSource] = useState<Set<string>>(new Set());

  const anchorTypeColors: Record<string, string> = {
    'FirstDose': 'bg-blue-100 text-blue-800 border-blue-300',
    'Day1': 'bg-blue-100 text-blue-800 border-blue-300',
    'Baseline': 'bg-purple-100 text-purple-800 border-purple-300',
    'Randomization': 'bg-green-100 text-green-800 border-green-300',
    'Screening': 'bg-amber-100 text-amber-800 border-amber-300',
    'InformedConsent': 'bg-cyan-100 text-cyan-800 border-cyan-300',
    'CollectionDay': 'bg-pink-100 text-pink-800 border-pink-300',
  };

  // Detect duplicates by anchorType
  const duplicates = useMemo(() => {
    const typeCount: Record<string, number> = {};
    for (const anchor of anchors) {
      const type = anchor.anchorType;
      typeCount[type] = (typeCount[type] ?? 0) + 1;
    }
    return new Set(Object.keys(typeCount).filter(type => typeCount[type] > 1));
  }, [anchors]);

  const hasDuplicates = duplicates.size > 0;

  const toggleSourceView = (id: string) => {
    const newSet = new Set(showFullSource);
    if (newSet.has(id)) {
      newSet.delete(id);
    } else {
      newSet.add(id);
    }
    setShowFullSource(newSet);
  };

  if (anchors.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Anchor className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
          <p className="text-muted-foreground">No time anchors defined</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Duplicate Warning */}
      {hasDuplicates && (
        <Card className="border-amber-300 bg-amber-50">
          <CardContent className="py-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <h4 className="font-medium text-amber-800">Duplicate Anchors Detected</h4>
                <p className="text-sm text-amber-700 mt-1">
                  The following anchor types appear multiple times: {Array.from(duplicates).join(', ')}.
                  This may indicate extraction errors or require manual review.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Anchor className="h-5 w-5" />
            Time Anchors ({anchors.length})
            {hasDuplicates && (
              <Badge variant="outline" className="ml-2 text-amber-600 border-amber-400">
                {duplicates.size} duplicates
              </Badge>
            )}
          </CardTitle>
          <CardDescription>
            Reference points from which all other timing is measured
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4">
            {anchors.map((anchor, index) => {
              const isDuplicate = duplicates.has(anchor.anchorType);
              const isSourceExpanded = showFullSource.has(anchor.id);
              
              return (
                <div 
                  key={anchor.id}
                  className={cn(
                    "p-4 rounded-lg border-2",
                    isDuplicate && 'ring-2 ring-amber-400 ring-offset-1',
                    anchorTypeColors[anchor.anchorType] ?? 'bg-gray-100 text-gray-800 border-gray-300'
                  )}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className={cn(
                        "w-10 h-10 rounded-full flex items-center justify-center text-white font-bold",
                        index === 0 ? 'bg-blue-600' : 'bg-gray-500'
                      )}>
                        {anchor.dayValue ?? '?'}
                      </div>
                      <div>
                        <h4 className="font-semibold flex items-center gap-2">
                          {anchor.anchorType}
                          {isDuplicate && (
                            <AlertTriangle className="h-4 w-4 text-amber-600" />
                          )}
                        </h4>
                        <p className="text-sm opacity-80">{anchor.definition}</p>
                        {anchor.timelineId && (
                          <p className="text-xs opacity-60 mt-1">Timeline: {anchor.timelineId}</p>
                        )}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      {isDuplicate && (
                        <Badge variant="outline" className="text-amber-600 border-amber-400">
                          Duplicate
                        </Badge>
                      )}
                      {index === 0 && (
                        <Badge className="bg-blue-600">Primary</Badge>
                      )}
                    </div>
                  </div>
                  {anchor.sourceText && (
                    <div className="mt-3">
                      <button 
                        onClick={() => toggleSourceView(anchor.id)}
                        className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
                      >
                        {isSourceExpanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                        {isSourceExpanded ? 'Hide' : 'Show'} source text
                      </button>
                      {isSourceExpanded && (
                        <div className="mt-2 p-2 bg-white/50 rounded text-xs whitespace-pre-wrap">
                          {anchor.sourceText}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ============================================================================
// Visit Windows Panel - Enhanced with search, filter, and sorting
// ============================================================================

function VisitWindowsPanel({ 
  visits, 
  anchors = [], 
  epochNameMap = {},
  studyDesign 
}: { 
  visits: VisitWindow[]; 
  anchors?: TimeAnchor[];
  epochNameMap?: Record<string, string>;
  studyDesign?: Record<string, unknown>;
}) {
  const [searchQuery, setSearchQuery] = useState('');
  const [filterRequired, setFilterRequired] = useState<'all' | 'required' | 'optional'>('all');
  const [sortBy, setSortBy] = useState<'day' | 'name' | 'number'>('day');
  const [sortAsc, setSortAsc] = useState(true);

  // Build encounter name to epoch name map from USDM
  const encounterEpochMap = useMemo(() => {
    const map: Record<string, string> = {};
    const encounters = (studyDesign?.encounters ?? []) as Array<{ name?: string; epochId?: string }>;
    for (const enc of encounters) {
      if (enc.name && enc.epochId) {
        const epochName = epochNameMap[enc.epochId];
        if (epochName) {
          // Normalize visit name for matching (lowercase, trim)
          map[enc.name.toLowerCase().trim()] = epochName;
        }
      }
    }
    return map;
  }, [studyDesign, epochNameMap]);

  // Resolve epoch name for a visit - try USDM first, fallback to generic
  const resolveEpochName = (visit: VisitWindow): string | undefined => {
    // Try to match visit name to USDM encounter
    const normalizedName = visit.visitName.toLowerCase().trim();
    if (encounterEpochMap[normalizedName]) {
      return encounterEpochMap[normalizedName];
    }
    // Fallback to generic epoch from execution model
    return visit.epoch;
  };

  // Get unique epochs for stats (using resolved names)
  const epochs = useMemo(() => {
    const set = new Set(visits.map(v => resolveEpochName(v)).filter(Boolean));
    return Array.from(set);
  }, [visits, encounterEpochMap]);

  // Filter and sort visits
  const filteredVisits = useMemo(() => {
    let result = [...visits];

    // Search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      result = result.filter(v => 
        v.visitName.toLowerCase().includes(query) ||
        resolveEpochName(v)?.toLowerCase().includes(query)
      );
    }

    // Required filter
    if (filterRequired === 'required') {
      result = result.filter(v => v.isRequired);
    } else if (filterRequired === 'optional') {
      result = result.filter(v => !v.isRequired);
    }

    // Sort
    result.sort((a, b) => {
      let cmp = 0;
      switch (sortBy) {
        case 'day':
          cmp = a.targetDay - b.targetDay;
          break;
        case 'name':
          cmp = a.visitName.localeCompare(b.visitName);
          break;
        case 'number':
          cmp = (a.visitNumber ?? 0) - (b.visitNumber ?? 0);
          break;
      }
      return sortAsc ? cmp : -cmp;
    });

    return result;
  }, [visits, searchQuery, filterRequired, sortBy, sortAsc]);

  const toggleSort = (column: 'day' | 'name' | 'number') => {
    if (sortBy === column) {
      setSortAsc(!sortAsc);
    } else {
      setSortBy(column);
      setSortAsc(true);
    }
  };

  const requiredCount = visits.filter(v => v.isRequired).length;
  const optionalCount = visits.length - requiredCount;

  if (visits.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Calendar className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
          <p className="text-muted-foreground">No visit windows defined</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Timeline Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            Visit Schedule ({visits.length} visits)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <TimelineVisualization visits={visits} anchors={anchors} />
        </CardContent>
      </Card>

      {/* Table View with Filters */}
      <Card>
        <CardHeader>
          <CardTitle>Visit Details</CardTitle>
          <CardDescription>
            {requiredCount} required, {optionalCount} optional visits
            {epochs.length > 0 && ` across ${epochs.length} epochs`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Search and Filter Controls */}
          <div className="mb-4 flex flex-wrap gap-3">
            {/* Search */}
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search visits..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Required Filter */}
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <select
                value={filterRequired}
                onChange={(e) => setFilterRequired(e.target.value as 'all' | 'required' | 'optional')}
                className="px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="all">All Visits ({visits.length})</option>
                <option value="required">Required ({requiredCount})</option>
                <option value="optional">Optional ({optionalCount})</option>
              </select>
            </div>
          </div>

          {/* Results Count */}
          {(searchQuery || filterRequired !== 'all') && (
            <p className="mb-3 text-sm text-muted-foreground">
              Showing {filteredVisits.length} of {visits.length} visits
            </p>
          )}

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th 
                    className="text-left py-3 px-4 font-medium cursor-pointer hover:bg-muted/50"
                    onClick={() => toggleSort('number')}
                  >
                    # {sortBy === 'number' && (sortAsc ? '↑' : '↓')}
                  </th>
                  <th 
                    className="text-left py-3 px-4 font-medium cursor-pointer hover:bg-muted/50"
                    onClick={() => toggleSort('name')}
                  >
                    Visit Name {sortBy === 'name' && (sortAsc ? '↑' : '↓')}
                  </th>
                  <th 
                    className="text-left py-3 px-4 font-medium cursor-pointer hover:bg-muted/50"
                    onClick={() => toggleSort('day')}
                  >
                    Target Day {sortBy === 'day' && (sortAsc ? '↑' : '↓')}
                  </th>
                  <th className="text-left py-3 px-4 font-medium">Week</th>
                  <th className="text-left py-3 px-4 font-medium">Window</th>
                  <th className="text-left py-3 px-4 font-medium">Required</th>
                  <th className="text-left py-3 px-4 font-medium">Epoch</th>
                </tr>
              </thead>
              <tbody>
                {filteredVisits.map((visit, index) => (
                  <tr key={visit.id} className="border-b hover:bg-muted/50">
                    <td className="py-3 px-4 text-muted-foreground">{visit.visitNumber ?? index + 1}</td>
                    <td className="py-3 px-4 font-medium capitalize">{visit.visitName}</td>
                    <td className="py-3 px-4">
                      <Badge variant="outline">Day {visit.targetDay}</Badge>
                    </td>
                    <td className="py-3 px-4 text-muted-foreground">
                      {visit.targetWeek ? `Week ${visit.targetWeek}` : '-'}
                    </td>
                    <td className="py-3 px-4">
                      {visit.windowBefore > 0 || visit.windowAfter > 0 ? (
                        <span className="text-green-600 font-mono text-xs">
                          ±{Math.max(visit.windowBefore, visit.windowAfter)} days
                        </span>
                      ) : (
                        <span className="text-muted-foreground text-xs">Fixed</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      {visit.isRequired ? (
                        <Badge className="bg-green-600">Required</Badge>
                      ) : (
                        <Badge variant="secondary">Optional</Badge>
                      )}
                    </td>
                    <td className="py-3 px-4 text-muted-foreground">{resolveEpochName(visit) ?? '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* No Results */}
          {filteredVisits.length === 0 && (
            <div className="py-8 text-center text-muted-foreground">
              <Search className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p>No visits match your search criteria</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ============================================================================
// Conditions Panel - Enhanced with search, filter, expand/collapse
// ============================================================================

function ConditionsPanel({ conditions, studyDesign }: { conditions: FootnoteCondition[]; studyDesign?: USDMStudyDesign }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  const [showAll, setShowAll] = useState(false);

  // Build entity name maps for ID resolution
  const entityNameMap = useMemo(() => {
    const map: Record<string, string> = {};
    
    // Activities
    const activities = studyDesign?.activities ?? [];
    for (const act of activities) {
      if (act.id) {
        map[act.id] = act.name || act.label || 'Unknown Activity';
      }
    }
    // Also handle act_N format
    activities.forEach((act, idx) => {
      map[`act_${idx + 1}`] = act.name || act.label || `Activity ${idx + 1}`;
    });
    
    // Activity Groups
    const groups = studyDesign?.activityGroups ?? [];
    for (const grp of groups) {
      if (grp.id) {
        map[grp.id] = grp.name || 'Unknown Group';
      }
    }
    // Also handle grp_N format
    groups.forEach((grp, idx) => {
      map[`grp_${idx + 1}`] = grp.name || `Group ${idx + 1}`;
    });
    
    // Encounters
    const encounters = studyDesign?.encounters ?? [];
    for (const enc of encounters) {
      if (enc.id) {
        map[enc.id] = enc.name || 'Unknown Visit';
      }
    }
    encounters.forEach((enc, idx) => {
      map[`enc_${idx + 1}`] = enc.name || `Visit ${idx + 1}`;
    });
    
    return map;
  }, [studyDesign]);

  // Helper to resolve ID to name
  const resolveEntityName = (id: string): string => {
    return entityNameMap[id] || id;
  };

  // Group conditions by type
  const groupedByType = useMemo(() => {
    const groups: Record<string, FootnoteCondition[]> = {};
    for (const cond of conditions) {
      const type = cond.conditionType ?? 'general';
      if (!groups[type]) groups[type] = [];
      groups[type].push(cond);
    }
    return groups;
  }, [conditions]);

  // Filter conditions based on search and type
  const filteredConditions = useMemo(() => {
    let filtered = conditions;
    
    if (selectedType) {
      filtered = filtered.filter(c => (c.conditionType ?? 'general') === selectedType);
    }
    
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(c => 
        c.text?.toLowerCase().includes(query) ||
        c.footnoteId?.toLowerCase().includes(query) ||
        c.sourceText?.toLowerCase().includes(query)
      );
    }
    
    return filtered;
  }, [conditions, searchQuery, selectedType]);

  // Group filtered conditions
  const filteredGrouped = useMemo(() => {
    const groups: Record<string, FootnoteCondition[]> = {};
    for (const cond of filteredConditions) {
      const type = cond.conditionType ?? 'general';
      if (!groups[type]) groups[type] = [];
      groups[type].push(cond);
    }
    return groups;
  }, [filteredConditions]);

  const typeCount = Object.keys(groupedByType).length;
  const conditionTypes = Object.keys(groupedByType);

  const toggleSection = (type: string) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(type)) {
      newExpanded.delete(type);
    } else {
      newExpanded.add(type);
    }
    setExpandedSections(newExpanded);
  };

  const expandAll = () => {
    setExpandedSections(new Set(conditionTypes));
    setShowAll(true);
  };

  const collapseAll = () => {
    setExpandedSections(new Set());
    setShowAll(false);
  };

  if (conditions.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <FileText className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
          <p className="text-muted-foreground">No conditions defined</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Conditions & Footnotes ({conditions.length})
          </CardTitle>
          <CardDescription>
            {typeCount} condition types extracted from protocol footnotes
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Search and Filter Controls */}
          <div className="mb-6 space-y-3">
            <div className="flex flex-wrap gap-3">
              {/* Search Input */}
              <div className="relative flex-1 min-w-[200px]">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search conditions..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              
              {/* Type Filter */}
              <div className="flex items-center gap-2">
                <Filter className="h-4 w-4 text-muted-foreground" />
                <select
                  value={selectedType ?? ''}
                  onChange={(e) => setSelectedType(e.target.value || null)}
                  className="px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">All Types</option>
                  {conditionTypes.map(type => (
                    <option key={type} value={type}>
                      {type} ({groupedByType[type].length})
                    </option>
                  ))}
                </select>
              </div>

              {/* Expand/Collapse All */}
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={expandAll}>
                  <ChevronDown className="h-4 w-4 mr-1" />
                  Expand All
                </Button>
                <Button variant="outline" size="sm" onClick={collapseAll}>
                  <ChevronUp className="h-4 w-4 mr-1" />
                  Collapse All
                </Button>
              </div>
            </div>

            {/* Results Count */}
            {(searchQuery || selectedType) && (
              <p className="text-sm text-muted-foreground">
                Showing {filteredConditions.length} of {conditions.length} conditions
                {selectedType && <Badge variant="secondary" className="ml-2">{selectedType}</Badge>}
              </p>
            )}
          </div>

          {/* Conditions List */}
          <div className="space-y-4">
            {Object.entries(filteredGrouped).map(([type, conds]) => {
              const isExpanded = expandedSections.has(type) || showAll;
              const displayCount = isExpanded ? conds.length : Math.min(5, conds.length);
              
              return (
                <div key={type} className="border rounded-lg overflow-hidden">
                  {/* Section Header */}
                  <button
                    onClick={() => toggleSection(type)}
                    className="w-full flex items-center justify-between p-3 bg-muted/50 hover:bg-muted transition-colors"
                  >
                    <div className="flex items-center gap-2">
                      {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                      <span className="font-medium text-sm uppercase tracking-wide">{type}</span>
                      <Badge variant="secondary">{conds.length}</Badge>
                    </div>
                  </button>

                  {/* Section Content */}
                  <div className="divide-y">
                    {conds.slice(0, displayCount).map(cond => (
                      <div key={cond.id} className="p-4 bg-white hover:bg-gray-50">
                        <div className="flex items-start gap-3">
                          {cond.footnoteId && (
                            <Badge variant="outline" className="shrink-0 font-mono">
                              {cond.footnoteId}
                            </Badge>
                          )}
                          <div className="flex-1 min-w-0">
                            {/* Full text - no truncation */}
                            <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">
                              {cond.text}
                            </p>
                            
                            {/* Structured Condition */}
                            {cond.structuredCondition && (
                              <div className="mt-2 p-2 bg-blue-50 rounded border border-blue-200">
                                <p className="text-xs font-mono text-blue-800">
                                  {cond.structuredCondition}
                                </p>
                              </div>
                            )}

                            {/* Applied to Activities */}
                            {cond.appliesToActivityIds && cond.appliesToActivityIds.length > 0 && (
                              <div className="mt-2 flex flex-wrap gap-1">
                                <span className="text-xs text-muted-foreground">Applies to:</span>
                                {cond.appliesToActivityIds.map(actId => (
                                  <Badge key={actId} variant="secondary" className="text-xs">
                                    {resolveEntityName(actId)}
                                  </Badge>
                                ))}
                              </div>
                            )}

                            {/* Source Text (expandable) */}
                            {cond.sourceText && cond.sourceText !== cond.text && (
                              <details className="mt-2">
                                <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">
                                  View source text
                                </summary>
                                <p className="mt-1 text-xs text-muted-foreground bg-gray-50 p-2 rounded whitespace-pre-wrap">
                                  {cond.sourceText}
                                </p>
                              </details>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}

                    {/* Show More Button */}
                    {conds.length > displayCount && (
                      <button
                        onClick={() => toggleSection(type)}
                        className="w-full p-3 text-sm text-blue-600 hover:bg-blue-50 transition-colors"
                      >
                        Show {conds.length - displayCount} more {type} conditions
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* No Results */}
          {filteredConditions.length === 0 && (
            <div className="py-8 text-center text-muted-foreground">
              <Search className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p>No conditions match your search criteria</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ============================================================================
// Repetitions Panel - Enhanced with expandable sections and ISO 8601 translation
// ============================================================================

// Helper function to translate ISO 8601 duration to human-readable text
function translateDuration(iso: string | undefined): string {
  if (!iso) return '';
  
  // Match ISO 8601 duration pattern: P[n]Y[n]M[n]DT[n]H[n]M[n]S
  const match = iso.match(/^-?P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$/);
  if (!match) return iso;
  
  const days = match[1] ? parseInt(match[1]) : 0;
  const hours = match[2] ? parseInt(match[2]) : 0;
  const minutes = match[3] ? parseInt(match[3]) : 0;
  
  const parts: string[] = [];
  if (days === 1) parts.push('1 day');
  else if (days > 1) parts.push(`${days} days`);
  if (hours === 1) parts.push('1 hour');
  else if (hours > 1) parts.push(`${hours} hours`);
  if (minutes > 0) parts.push(`${minutes} min`);
  
  const isNegative = iso.startsWith('-');
  const result = parts.join(' ') || iso;
  return isNegative ? `-${result}` : result;
}

function RepetitionsPanel({ repetitions }: { repetitions: Repetition[] }) {
  const [expandedTypes, setExpandedTypes] = useState<Set<string>>(new Set());

  const groupedByType = useMemo(() => {
    const groups: Record<string, Repetition[]> = {};
    for (const rep of repetitions) {
      const type = rep.type ?? 'Other';
      if (!groups[type]) groups[type] = [];
      groups[type].push(rep);
    }
    return groups;
  }, [repetitions]);

  const toggleType = (type: string) => {
    const newSet = new Set(expandedTypes);
    if (newSet.has(type)) {
      newSet.delete(type);
    } else {
      newSet.add(type);
    }
    setExpandedTypes(newSet);
  };

  const expandAll = () => setExpandedTypes(new Set(Object.keys(groupedByType)));
  const collapseAll = () => setExpandedTypes(new Set());

  if (repetitions.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Repeat className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
          <p className="text-muted-foreground">No repetition patterns defined</p>
        </CardContent>
      </Card>
    );
  }

  const typeColors: Record<string, string> = {
    'Daily': 'bg-blue-50 border-blue-200',
    'Interval': 'bg-green-50 border-green-200',
    'Cycle': 'bg-purple-50 border-purple-200',
    'Continuous': 'bg-amber-50 border-amber-200',
    'OnDemand': 'bg-pink-50 border-pink-200',
  };

  const typeBadgeColors: Record<string, string> = {
    'Daily': 'bg-blue-100 text-blue-800',
    'Interval': 'bg-green-100 text-green-800',
    'Cycle': 'bg-purple-100 text-purple-800',
    'Continuous': 'bg-amber-100 text-amber-800',
    'OnDemand': 'bg-pink-100 text-pink-800',
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Repeat className="h-5 w-5" />
                Repetition Patterns ({repetitions.length})
              </CardTitle>
              <CardDescription>
                Activity scheduling and repeat patterns
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={expandAll}>
                <ChevronDown className="h-4 w-4 mr-1" />
                Expand All
              </Button>
              <Button variant="outline" size="sm" onClick={collapseAll}>
                <ChevronUp className="h-4 w-4 mr-1" />
                Collapse All
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {/* Type Summary Cards */}
          <div className="grid md:grid-cols-3 gap-3 mb-6">
            {Object.entries(groupedByType).map(([type, reps]) => (
              <div 
                key={type}
                className={cn("p-3 rounded-lg border text-center", typeColors[type] ?? 'bg-gray-50 border-gray-200')}
              >
                <Badge className={typeBadgeColors[type] ?? 'bg-gray-100 text-gray-800'}>
                  {type}
                </Badge>
                <p className="text-2xl font-bold mt-2">{reps.length}</p>
                <p className="text-xs text-muted-foreground">patterns</p>
              </div>
            ))}
          </div>

          {/* Expandable Sections */}
          <div className="space-y-3">
            {Object.entries(groupedByType).map(([type, reps]) => {
              const isExpanded = expandedTypes.has(type);
              
              return (
                <div key={type} className={cn("border rounded-lg overflow-hidden", typeColors[type])}>
                  {/* Section Header */}
                  <button
                    onClick={() => toggleType(type)}
                    className="w-full flex items-center justify-between p-3 hover:bg-white/50 transition-colors"
                  >
                    <div className="flex items-center gap-2">
                      {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                      <Badge className={typeBadgeColors[type] ?? 'bg-gray-100 text-gray-800'}>
                        {type}
                      </Badge>
                      <span className="text-sm text-muted-foreground">({reps.length} patterns)</span>
                    </div>
                  </button>

                  {/* Expanded Content */}
                  {isExpanded && (
                    <div className="border-t bg-white divide-y">
                      {reps.map(rep => (
                        <div key={rep.id} className="p-3">
                          <div className="flex items-start justify-between gap-4">
                            <div className="flex-1">
                              {/* Source Text */}
                              <p className="text-sm font-medium">
                                {rep.sourceText || rep.id}
                              </p>
                              
                              {/* Details Row */}
                              <div className="flex flex-wrap gap-3 mt-2 text-xs text-muted-foreground">
                                {rep.interval && (
                                  <span className="flex items-center gap-1">
                                    <Clock className="h-3 w-3" />
                                    <span className="font-mono">{rep.interval}</span>
                                    <span className="text-blue-600">({translateDuration(rep.interval)})</span>
                                  </span>
                                )}
                                {rep.count && (
                                  <span>Count: {rep.count}</span>
                                )}
                                {rep.activityIds && rep.activityIds.length > 0 && (
                                  <span>Activities: {rep.activityIds.length}</span>
                                )}
                              </div>

                              {/* Activity IDs */}
                              {rep.activityIds && rep.activityIds.length > 0 && (
                                <div className="flex flex-wrap gap-1 mt-2">
                                  {rep.activityIds.map(actId => (
                                    <Badge key={actId} variant="secondary" className="text-xs">
                                      {actId}
                                    </Badge>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Duration Legend */}
          <div className="mt-6 p-4 bg-muted/50 rounded-lg">
            <h4 className="text-sm font-medium mb-3">ISO 8601 Duration Examples</h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              <div><code className="text-xs bg-white px-1 rounded">P1D</code> = 1 day</div>
              <div><code className="text-xs bg-white px-1 rounded">P7D</code> = 7 days (1 week)</div>
              <div><code className="text-xs bg-white px-1 rounded">PT8H</code> = 8 hours</div>
              <div><code className="text-xs bg-white px-1 rounded">-P4D</code> = 4 days before</div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ============================================================================
// Dosing Panel
// ============================================================================

function DosingPanel({ regimens }: { regimens: DosingRegimen[] }) {
  if (regimens.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Pill className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
          <p className="text-muted-foreground">No dosing regimens defined</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Pill className="h-5 w-5" />
            Dosing Regimens ({regimens.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4">
            {regimens.map(regimen => (
              <div key={regimen.id} className="p-4 border rounded-lg bg-gradient-to-r from-pink-50 to-purple-50">
                <div className="flex items-start justify-between">
                  <div>
                    <h4 className="font-semibold text-lg">{regimen.treatmentName}</h4>
                    <div className="flex items-center gap-3 mt-2 text-sm">
                      <Badge variant="outline">{regimen.frequency}</Badge>
                      <Badge variant="outline">{regimen.route}</Badge>
                      {regimen.startDay && <Badge>Start Day {regimen.startDay}</Badge>}
                    </div>
                  </div>
                </div>
                
                {regimen.doseLevels && regimen.doseLevels.length > 0 && (
                  <div className="mt-4">
                    <p className="text-sm font-medium text-muted-foreground mb-2">Dose Levels</p>
                    <div className="flex flex-wrap gap-2">
                      {regimen.doseLevels.map((dose, i) => (
                        <Badge key={i} className="bg-purple-600">
                          {dose.amount} {dose.unit}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                {regimen.titrationSchedule && (
                  <div className="mt-3 p-2 bg-white/60 rounded text-sm">
                    <span className="font-medium">Titration: </span>
                    {regimen.titrationSchedule}
                  </div>
                )}

                {regimen.doseModifications && regimen.doseModifications.length > 0 && (
                  <div className="mt-3">
                    <p className="text-sm font-medium text-muted-foreground mb-1">Dose Modifications</p>
                    <ul className="text-sm space-y-1">
                      {regimen.doseModifications.map((mod, i) => (
                        <li key={i} className="text-amber-700">• {mod}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ============================================================================
// State Machine Panel - Enhanced with Study Exits
// ============================================================================

function StateMachinePanel({ stateMachine, studyExits = [] }: { stateMachine?: StateMachine; studyExits?: StudyExit[] }) {
  if (!stateMachine && studyExits.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <GitBranch className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
          <p className="text-muted-foreground">No state machine or study exits defined</p>
        </CardContent>
      </Card>
    );
  }

  // Dynamic color assignment based on state type keywords
  const getStateColor = (state: string): string => {
    const s = state.toLowerCase();
    
    // Terminal/exit states
    if (s.includes('terminat') || s.includes('discontinu') || s.includes('withdraw')) {
      return 'bg-red-100 border-red-400 text-red-800';
    }
    if (s.includes('death') || s.includes('died')) {
      return 'bg-gray-200 border-gray-500 text-gray-800';
    }
    if (s.includes('lost') || s.includes('ltfu')) {
      return 'bg-purple-100 border-purple-400 text-purple-800';
    }
    
    // Completion states
    if (s.includes('complet') || s.includes('end of study') || s.includes('eos')) {
      return 'bg-emerald-100 border-emerald-400 text-emerald-800';
    }
    
    // Screening/enrollment
    if (s.includes('screen')) {
      return 'bg-amber-100 border-amber-400 text-amber-800';
    }
    if (s.includes('enroll') || s.includes('baseline')) {
      return 'bg-blue-100 border-blue-400 text-blue-800';
    }
    if (s.includes('random')) {
      return 'bg-indigo-100 border-indigo-400 text-indigo-800';
    }
    
    // Treatment periods
    if (s.includes('treatment') || s.includes('period') || s.includes('dose') || s.includes('titrat')) {
      return 'bg-green-100 border-green-400 text-green-800';
    }
    
    // Washout
    if (s.includes('wash') || s.includes('washout')) {
      return 'bg-orange-100 border-orange-400 text-orange-800';
    }
    
    // Follow-up
    if (s.includes('follow')) {
      return 'bg-cyan-100 border-cyan-400 text-cyan-800';
    }
    
    // Default
    return 'bg-slate-100 border-slate-400 text-slate-800';
  };

  return (
    <div className="space-y-4">
      {/* State Machine Card - only show if stateMachine exists */}
      {stateMachine && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <GitBranch className="h-5 w-5" />
              Subject State Machine
            </CardTitle>
            <CardDescription>
              Subject flow through the study with possible state transitions
            </CardDescription>
          </CardHeader>
          <CardContent>
            {/* Visual State Diagram */}
            <div className="p-6 bg-gradient-to-br from-slate-50 to-slate-100 rounded-lg border">
              {/* Subject Flow Diagram - shows actual protocol epoch sequence */}
              <div className="flex items-center justify-center mb-6">
                <div className="flex items-center gap-3">
                  <div className="w-4 h-4 rounded-full bg-blue-600" title="Start" />
                  <div className={cn(
                    "px-6 py-3 rounded-lg border-2 font-medium shadow-sm",
                    getStateColor(stateMachine.initialState)
                  )}>
                    {stateMachine.initialState}
                  </div>
                  <span className="text-sm text-muted-foreground font-medium">(Start)</span>
                </div>
              </div>

              {/* Main Study Flow - Active States in sequence */}
              <div className="relative mb-6">
                <div className="flex flex-wrap justify-center items-center gap-2">
                  {stateMachine.states
                    .filter(s => s !== stateMachine.initialState && !stateMachine.terminalStates.includes(s))
                    .map((state, idx, arr) => (
                      <div key={state} className="flex items-center">
                        <div className={cn(
                          "px-4 py-2 rounded-lg border-2 font-medium shadow-sm",
                          getStateColor(state)
                        )}>
                          {state}
                        </div>
                        {idx < arr.length - 1 && (
                          <svg className="w-6 h-6 text-gray-400 mx-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                          </svg>
                        )}
                      </div>
                    ))
                  }
                </div>
              </div>

              {/* Arrow to terminal states */}
              <div className="flex justify-center mb-4">
                <svg className="w-6 h-8 text-gray-400" fill="none" viewBox="0 0 24 32" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v20m0 0l-6-6m6 6l6-6" />
                </svg>
              </div>

              {/* Terminal/Exit States */}
              <div className="flex flex-wrap justify-center gap-3">
                {stateMachine.terminalStates.map(state => (
                  <div
                    key={state}
                    className={cn(
                      "px-4 py-2 rounded-lg border-2 font-medium border-dashed shadow-sm",
                      getStateColor(state)
                    )}
                  >
                    {state}
                    <span className="text-xs ml-2 opacity-60">(Exit)</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Transitions Table */}
            {stateMachine.transitions.length > 0 && (
            <div className="mt-6">
              <h4 className="font-medium mb-3">State Transitions</h4>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-2 px-3 font-medium">From</th>
                      <th className="text-left py-2 px-3 font-medium">To</th>
                      <th className="text-left py-2 px-3 font-medium">Trigger</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stateMachine.transitions.map((trans, i) => (
                      <tr key={i} className="border-b">
                        <td className="py-2 px-3">
                          <Badge variant="outline">{trans.fromState}</Badge>
                        </td>
                        <td className="py-2 px-3">
                          <Badge variant="outline">{trans.toState}</Badge>
                        </td>
                        <td className="py-2 px-3 text-muted-foreground">{trans.trigger}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Study Exits Card */}
      {studyExits.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <LogOut className="h-5 w-5" />
              Study Exit Paths ({studyExits.length})
            </CardTitle>
            <CardDescription>
              Ways subjects can exit or complete the study
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {studyExits.map(exit => {
                const isCompletion = exit.exitType === 'Completion';
                return (
                  <div 
                    key={exit.id}
                    className={cn(
                      "p-4 rounded-lg border-2",
                      isCompletion 
                        ? "bg-green-50 border-green-300" 
                        : "bg-amber-50 border-amber-300"
                    )}
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <h4 className="font-medium flex items-center gap-2">
                          {exit.name}
                          <Badge className={isCompletion ? "bg-green-600" : "bg-amber-600"}>
                            {exit.exitType}
                          </Badge>
                        </h4>
                        {exit.description && (
                          <p className="text-sm text-muted-foreground mt-2">
                            {exit.description}
                          </p>
                        )}
                      </div>
                    </div>
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

// ============================================================================
// Traversal Panel
// ============================================================================

function TraversalPanel({ 
  constraints, 
  executionTypes,
  epochNameMap = {},
  studyDesign
}: { 
  constraints: TraversalConstraint[]; 
  executionTypes: ExecutionType[];
  epochNameMap?: Record<string, string>;
  studyDesign?: USDMStudyDesign;
}) {
  // Build epoch index map (epoch_1 -> actual name) for sequential IDs used in constraints
  const epochIndexMap = useMemo(() => {
    const map: Record<string, string> = {};
    const epochs = studyDesign?.epochs ?? [];
    epochs.forEach((epoch, index) => {
      // Map both UUID and sequential ID formats
      if (epoch.id) {
        map[epoch.id] = epoch.name || `Epoch ${index + 1}`;
      }
      // Also map sequential format (epoch_1, epoch_2, etc.)
      map[`epoch_${index + 1}`] = epoch.name || `Epoch ${index + 1}`;
    });
    return map;
  }, [studyDesign]);

  // Build encounter index map (enc_1 -> actual name) for sequential IDs
  const encounterIndexMap = useMemo(() => {
    const map: Record<string, string> = {};
    const encounters = studyDesign?.encounters ?? [];
    encounters.forEach((enc, index) => {
      // Map both UUID and sequential ID formats
      if (enc.id) {
        map[enc.id] = enc.name || `Visit ${index + 1}`;
      }
      // Also map sequential format (enc_1, enc_2, etc.)
      map[`enc_${index + 1}`] = enc.name || `Visit ${index + 1}`;
    });
    return map;
  }, [studyDesign]);

  // Helper to resolve epoch ID to name (handles both UUID and epoch_X formats)
  const resolveEpochName = (epochId: string): string => {
    // First check our index map
    if (epochIndexMap[epochId]) return epochIndexMap[epochId];
    // Then check the passed epochNameMap
    if (epochNameMap[epochId]) return epochNameMap[epochId];
    // Fallback: try to extract number and look up
    const match = epochId.match(/epoch_(\d+)/);
    if (match) {
      const idx = parseInt(match[1], 10) - 1;
      const epochs = studyDesign?.epochs ?? [];
      if (epochs[idx]) return epochs[idx].name || `Epoch ${idx + 1}`;
    }
    return epochId;
  };

  // Helper to resolve encounter/visit ID to name (handles both UUID and enc_X formats)
  const resolveEncounterName = (encounterId: string): string => {
    // First check our index map
    if (encounterIndexMap[encounterId]) return encounterIndexMap[encounterId];
    // Fallback: try to extract number and look up
    const match = encounterId.match(/enc_(\d+)/);
    if (match) {
      const idx = parseInt(match[1], 10) - 1;
      const encounters = studyDesign?.encounters ?? [];
      if (encounters[idx]) return encounters[idx].name || `Visit ${idx + 1}`;
    }
    return encounterId;
  };

  if (constraints.length === 0 && executionTypes.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Clock className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
          <p className="text-muted-foreground">No traversal constraints or execution types defined</p>
        </CardContent>
      </Card>
    );
  }

  const executionTypeColors: Record<string, string> = {
    'Single': 'bg-blue-100 text-blue-800',
    'Window': 'bg-green-100 text-green-800',
    'Episode': 'bg-purple-100 text-purple-800',
    'Recurring': 'bg-amber-100 text-amber-800',
  };

  return (
    <div className="space-y-6">
      {/* Traversal Constraints */}
      {constraints.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <GitBranch className="h-5 w-5" />
              Traversal Constraints ({constraints.length})
            </CardTitle>
            <CardDescription>
              Rules governing how subjects move through the study
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {constraints.map(constraint => (
                <div key={constraint.id} className="p-4 border rounded-lg bg-gradient-to-r from-slate-50 to-slate-100">
                  {/* Required Sequence */}
                  {constraint.requiredSequence && constraint.requiredSequence.length > 0 && (
                    <div className="mb-4">
                      <h4 className="text-sm font-medium text-muted-foreground mb-2">Required Epoch Sequence</h4>
                      <div className="flex items-center flex-wrap gap-2">
                        {constraint.requiredSequence.map((epochId, idx) => (
                          <div key={epochId} className="flex items-center">
                            <Badge variant="outline" className="bg-white">
                              {resolveEpochName(epochId)}
                            </Badge>
                            {idx < constraint.requiredSequence!.length - 1 && (
                              <span className="mx-2 text-gray-400">→</span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Early Exit */}
                  {constraint.allowEarlyExit && (
                    <div className="mb-3">
                      <Badge className="bg-amber-600">Early Exit Allowed</Badge>
                      {constraint.exitEpochIds && constraint.exitEpochIds.length > 0 && (
                        <span className="ml-2 text-sm text-muted-foreground">
                          via: {constraint.exitEpochIds.join(', ')}
                        </span>
                      )}
                    </div>
                  )}

                  {/* Mandatory Visits */}
                  {constraint.mandatoryVisits && constraint.mandatoryVisits.length > 0 && (
                    <div>
                      <h4 className="text-sm font-medium text-muted-foreground mb-2">Mandatory Visits</h4>
                      <div className="flex flex-wrap gap-2">
                        {constraint.mandatoryVisits.map(visit => (
                          <Badge key={visit} className="bg-green-600">
                            {resolveEncounterName(visit)}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Execution Types */}
      {executionTypes.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Activity Execution Types ({executionTypes.length})
            </CardTitle>
            <CardDescription>
              How activities are expected to be performed during the study
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {executionTypes.map((et, idx) => (
                <div key={idx} className="p-3 border rounded-lg hover:bg-muted/50">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <span className="font-medium">{et.activityId}</span>
                        <Badge className={executionTypeColors[et.executionType] ?? 'bg-gray-100 text-gray-800'}>
                          {et.executionType}
                        </Badge>
                      </div>
                      {et.rationale && (
                        <p className="text-sm text-muted-foreground leading-relaxed">
                          {et.rationale}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Execution Type Legend */}
            <div className="mt-6 p-4 bg-muted/50 rounded-lg">
              <h4 className="text-sm font-medium mb-3">Execution Type Definitions</h4>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="flex items-center gap-2">
                  <Badge className="bg-blue-100 text-blue-800">Single</Badge>
                  <span className="text-muted-foreground">One-time occurrence</span>
                </div>
                <div className="flex items-center gap-2">
                  <Badge className="bg-green-100 text-green-800">Window</Badge>
                  <span className="text-muted-foreground">Within time window</span>
                </div>
                <div className="flex items-center gap-2">
                  <Badge className="bg-purple-100 text-purple-800">Episode</Badge>
                  <span className="text-muted-foreground">Triggered by event</span>
                </div>
                <div className="flex items-center gap-2">
                  <Badge className="bg-amber-100 text-amber-800">Recurring</Badge>
                  <span className="text-muted-foreground">Repeated pattern</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ============================================================================
// Data Quality Panel - Shows classified issues from extraction
// ============================================================================

function DataQualityPanel({ issues }: { issues: ClassifiedIssue[] }) {
  const blockingIssues = issues.filter(i => i.severity === 'blocking');
  const warningIssues = issues.filter(i => i.severity === 'warning');
  const infoIssues = issues.filter(i => i.severity === 'info');

  if (issues.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <AlertCircle className="h-12 w-12 mx-auto mb-4 text-green-500" />
          <h3 className="text-lg font-semibold mb-2 text-green-700">No Issues Found</h3>
          <p className="text-muted-foreground">
            The extraction completed without any data quality issues.
          </p>
        </CardContent>
      </Card>
    );
  }

  const severityConfig = {
    blocking: { icon: <XCircle className="h-5 w-5" />, color: 'bg-red-50 border-red-300', badge: 'bg-red-600', text: 'text-red-800' },
    warning: { icon: <AlertTriangle className="h-5 w-5" />, color: 'bg-amber-50 border-amber-300', badge: 'bg-amber-600', text: 'text-amber-800' },
    info: { icon: <Info className="h-5 w-5" />, color: 'bg-blue-50 border-blue-300', badge: 'bg-blue-600', text: 'text-blue-800' },
  };

  return (
    <div className="space-y-4">
      {/* Summary Cards */}
      <div className="grid grid-cols-3 gap-4">
        <Card className={cn("border-2", blockingIssues.length > 0 ? "border-red-400 bg-red-50" : "")}>
          <CardContent className="py-4 text-center">
            <XCircle className={cn("h-8 w-8 mx-auto mb-2", blockingIssues.length > 0 ? "text-red-600" : "text-gray-300")} />
            <p className="text-2xl font-bold">{blockingIssues.length}</p>
            <p className="text-sm text-muted-foreground">Blocking</p>
          </CardContent>
        </Card>
        <Card className={cn("border-2", warningIssues.length > 0 ? "border-amber-400 bg-amber-50" : "")}>
          <CardContent className="py-4 text-center">
            <AlertTriangle className={cn("h-8 w-8 mx-auto mb-2", warningIssues.length > 0 ? "text-amber-600" : "text-gray-300")} />
            <p className="text-2xl font-bold">{warningIssues.length}</p>
            <p className="text-sm text-muted-foreground">Warnings</p>
          </CardContent>
        </Card>
        <Card className={cn("border-2", infoIssues.length > 0 ? "border-blue-400 bg-blue-50" : "")}>
          <CardContent className="py-4 text-center">
            <Info className={cn("h-8 w-8 mx-auto mb-2", infoIssues.length > 0 ? "text-blue-600" : "text-gray-300")} />
            <p className="text-2xl font-bold">{infoIssues.length}</p>
            <p className="text-sm text-muted-foreground">Info</p>
          </CardContent>
        </Card>
      </div>

      {/* Issues List */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5" />
            Data Quality Issues ({issues.length})
          </CardTitle>
          <CardDescription>
            Issues identified during extraction that may require review
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {issues.map((issue, idx) => {
              const config = severityConfig[issue.severity];
              return (
                <div 
                  key={idx}
                  className={cn("p-4 rounded-lg border-2", config.color)}
                >
                  <div className="flex items-start gap-3">
                    <div className={config.text}>{config.icon}</div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge className={config.badge}>
                          {issue.severity.toUpperCase()}
                        </Badge>
                        <Badge variant="outline" className="font-mono text-xs">
                          {issue.category}
                        </Badge>
                      </div>
                      <p className={cn("font-medium", config.text)}>{issue.message}</p>
                      
                      {issue.affectedPath && (
                        <p className="text-xs font-mono text-muted-foreground mt-2">
                          Path: {issue.affectedPath}
                        </p>
                      )}
                      
                      {issue.affectedIds && issue.affectedIds.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          <span className="text-xs text-muted-foreground">Affected:</span>
                          {issue.affectedIds.map(id => (
                            <Badge key={id} variant="secondary" className="text-xs font-mono">
                              {id}
                            </Badge>
                          ))}
                        </div>
                      )}
                      
                      {issue.suggestion && (
                        <div className="mt-3 p-2 bg-white/50 rounded border">
                          <p className="text-sm">
                            <strong>Suggestion:</strong> {issue.suggestion}
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ============================================================================
// Activity Schedule Panel - Shows scheduled activity instances
// ============================================================================

// Color palette for epochs
const EPOCH_COLORS = [
  { bg: 'bg-blue-100', border: 'border-blue-300', text: 'text-blue-700', fill: 'bg-blue-500' },
  { bg: 'bg-green-100', border: 'border-green-300', text: 'text-green-700', fill: 'bg-green-500' },
  { bg: 'bg-amber-100', border: 'border-amber-300', text: 'text-amber-700', fill: 'bg-amber-500' },
  { bg: 'bg-purple-100', border: 'border-purple-300', text: 'text-purple-700', fill: 'bg-purple-500' },
  { bg: 'bg-rose-100', border: 'border-rose-300', text: 'text-rose-700', fill: 'bg-rose-500' },
  { bg: 'bg-cyan-100', border: 'border-cyan-300', text: 'text-cyan-700', fill: 'bg-cyan-500' },
  { bg: 'bg-orange-100', border: 'border-orange-300', text: 'text-orange-700', fill: 'bg-orange-500' },
  { bg: 'bg-indigo-100', border: 'border-indigo-300', text: 'text-indigo-700', fill: 'bg-indigo-500' },
];

function ActivitySchedulePanel({ 
  instances, 
  timings,
  epochNameMap = {},
  studyDesign
}: { 
  instances: ScheduledInstance[];
  timings: TimingDetail[];
  epochNameMap?: Record<string, string>;
  studyDesign?: USDMStudyDesign;
}) {
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedTimings, setExpandedTimings] = useState(false);
  const [expandedEpochs, setExpandedEpochs] = useState<Set<string>>(new Set());
  const [selectedEpoch, setSelectedEpoch] = useState<string>('all');
  const [viewMode, setViewMode] = useState<'list' | 'visual'>('list');

  // Build activity ID to name map
  const activityNameMap = useMemo(() => {
    const map: Record<string, string> = {};
    const activities = studyDesign?.activities ?? [];
    for (const act of activities) {
      if (act.id) {
        map[act.id] = act.name || act.label || 'Unknown Activity';
      }
    }
    return map;
  }, [studyDesign]);

  // Build encounter ID to name map
  const encounterNameMap = useMemo(() => {
    const map: Record<string, string> = {};
    const encounters = studyDesign?.encounters ?? [];
    for (const enc of encounters) {
      if (enc.id) {
        map[enc.id] = enc.name || 'Unknown Encounter';
      }
    }
    return map;
  }, [studyDesign]);

  const resolveEpochName = (epochId: string): string => {
    return epochNameMap[epochId] || epochId.replace('epoch_', 'Epoch ');
  };

  const resolveActivityName = (activityId: string): string => {
    return activityNameMap[activityId] || activityId.slice(0, 8) + '...';
  };

  const resolveEncounterName = (encounterId: string): string => {
    return encounterNameMap[encounterId] || encounterId.slice(0, 8) + '...';
  };

  // Get ordered epoch list
  const orderedEpochs = useMemo(() => {
    const epochIds = new Set<string>();
    for (const inst of instances) {
      epochIds.add(inst.epochId || 'Unassigned');
    }
    return Array.from(epochIds);
  }, [instances]);

  // Assign colors to epochs
  const epochColorMap = useMemo(() => {
    const map: Record<string, typeof EPOCH_COLORS[0]> = {};
    orderedEpochs.forEach((epochId, index) => {
      map[epochId] = EPOCH_COLORS[index % EPOCH_COLORS.length];
    });
    return map;
  }, [orderedEpochs]);

  const filteredInstances = useMemo(() => {
    let result = instances;
    
    // Filter by epoch
    if (selectedEpoch !== 'all') {
      result = result.filter(inst => (inst.epochId || 'Unassigned') === selectedEpoch);
    }
    
    // Filter by search
    if (searchTerm) {
      const lower = searchTerm.toLowerCase();
      result = result.filter(inst => 
        inst.name.toLowerCase().includes(lower) ||
        inst.epochId?.toLowerCase().includes(lower) ||
        inst.activityIds?.some(aid => resolveActivityName(aid).toLowerCase().includes(lower))
      );
    }
    
    return result;
  }, [instances, searchTerm, selectedEpoch, resolveActivityName]);

  // Group by epoch
  const groupedByEpoch = useMemo(() => {
    const groups: Record<string, ScheduledInstance[]> = {};
    for (const inst of filteredInstances) {
      const epochKey = inst.epochId || 'Unassigned';
      if (!groups[epochKey]) groups[epochKey] = [];
      groups[epochKey].push(inst);
    }
    return groups;
  }, [filteredInstances]);

  // Statistics
  const stats = useMemo(() => {
    const byEpoch: Record<string, number> = {};
    const uniqueActivities = new Set<string>();
    const uniqueEncounters = new Set<string>();
    
    for (const inst of instances) {
      const epochKey = inst.epochId || 'Unassigned';
      byEpoch[epochKey] = (byEpoch[epochKey] || 0) + 1;
      inst.activityIds?.forEach(aid => uniqueActivities.add(aid));
      if (inst.encounterId) uniqueEncounters.add(inst.encounterId);
    }
    
    return {
      total: instances.length,
      byEpoch,
      uniqueActivities: uniqueActivities.size,
      uniqueEncounters: uniqueEncounters.size,
    };
  }, [instances]);

  const toggleEpoch = (epochId: string) => {
    setExpandedEpochs(prev => {
      const next = new Set(prev);
      if (next.has(epochId)) {
        next.delete(epochId);
      } else {
        next.add(epochId);
      }
      return next;
    });
  };

  const expandAll = () => setExpandedEpochs(new Set(orderedEpochs));
  const collapseAll = () => setExpandedEpochs(new Set());

  if (instances.length === 0 && timings.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <ListTree className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
          <p className="text-muted-foreground">No scheduled activity instances defined</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary Statistics Card */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-lg">
            <BarChart3 className="h-5 w-5" />
            Schedule Overview
          </CardTitle>
        </CardHeader>
        <CardContent>
          {/* Stats Row */}
          <div className="grid grid-cols-4 gap-4 mb-4">
            <div className="text-center p-3 bg-muted/30 rounded-lg">
              <div className="text-2xl font-bold text-blue-600">{stats.total}</div>
              <div className="text-xs text-muted-foreground">Total Instances</div>
            </div>
            <div className="text-center p-3 bg-muted/30 rounded-lg">
              <div className="text-2xl font-bold text-green-600">{orderedEpochs.length}</div>
              <div className="text-xs text-muted-foreground">Epochs</div>
            </div>
            <div className="text-center p-3 bg-muted/30 rounded-lg">
              <div className="text-2xl font-bold text-purple-600">{stats.uniqueActivities}</div>
              <div className="text-xs text-muted-foreground">Unique Activities</div>
            </div>
            <div className="text-center p-3 bg-muted/30 rounded-lg">
              <div className="text-2xl font-bold text-amber-600">{stats.uniqueEncounters}</div>
              <div className="text-xs text-muted-foreground">Encounters</div>
            </div>
          </div>

          {/* Visual Distribution Bar */}
          <div className="space-y-2">
            <div className="text-sm font-medium text-muted-foreground">Distribution by Epoch</div>
            <div className="flex h-8 rounded-lg overflow-hidden border">
              {orderedEpochs.map(epochId => {
                const count = stats.byEpoch[epochId] || 0;
                const percent = (count / stats.total) * 100;
                const colors = epochColorMap[epochId];
                return (
                  <div
                    key={epochId}
                    className={cn("h-full flex items-center justify-center text-xs font-medium transition-all hover:opacity-80 cursor-pointer", colors.fill, "text-white")}
                    style={{ width: `${percent}%`, minWidth: percent > 5 ? '40px' : '0' }}
                    title={`${resolveEpochName(epochId)}: ${count} (${percent.toFixed(1)}%)`}
                    onClick={() => setSelectedEpoch(selectedEpoch === epochId ? 'all' : epochId)}
                  >
                    {percent > 8 && count}
                  </div>
                );
              })}
            </div>
            {/* Legend */}
            <div className="flex flex-wrap gap-2 mt-2">
              {orderedEpochs.map(epochId => {
                const colors = epochColorMap[epochId];
                const isSelected = selectedEpoch === epochId;
                return (
                  <button
                    key={epochId}
                    onClick={() => setSelectedEpoch(selectedEpoch === epochId ? 'all' : epochId)}
                    className={cn(
                      "flex items-center gap-1.5 px-2 py-1 rounded text-xs transition-all",
                      isSelected ? cn(colors.bg, colors.border, "border-2") : "hover:bg-muted"
                    )}
                  >
                    <div className={cn("w-3 h-3 rounded-sm", colors.fill)} />
                    <span className={isSelected ? colors.text : ""}>{resolveEpochName(epochId)}</span>
                    <span className="text-muted-foreground">({stats.byEpoch[epochId]})</span>
                  </button>
                );
              })}
              {selectedEpoch !== 'all' && (
                <button
                  onClick={() => setSelectedEpoch('all')}
                  className="px-2 py-1 rounded text-xs bg-gray-200 hover:bg-gray-300"
                >
                  Clear filter
                </button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Timing Details Card */}
      {timings.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Clock className="h-5 w-5" />
                  Timing Definitions ({timings.length})
                </CardTitle>
                <CardDescription>
                  Timing rules governing activity scheduling
                </CardDescription>
              </div>
              <Button 
                variant="outline" 
                size="sm"
                onClick={() => setExpandedTimings(!expandedTimings)}
              >
                {expandedTimings ? <ChevronUp className="h-4 w-4 mr-1" /> : <ChevronDown className="h-4 w-4 mr-1" />}
                {expandedTimings ? 'Collapse' : 'Expand'}
              </Button>
            </div>
          </CardHeader>
          {expandedTimings && (
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {timings.map(timing => (
                  <div key={timing.id} className="p-3 border rounded-lg bg-muted/30">
                    <h4 className="font-medium text-sm">{timing.name}</h4>
                    <div className="flex flex-wrap gap-2 mt-2 text-xs">
                      {timing.type && (
                        <Badge variant="outline" className="text-xs">{timing.type}</Badge>
                      )}
                      {timing.value && (
                        <span className="font-mono text-muted-foreground">
                          {timing.value}
                        </span>
                      )}
                      {timing.relativeToFrom && (
                        <span className="text-muted-foreground">
                          from: <strong>{timing.relativeToFrom}</strong>
                        </span>
                      )}
                    </div>
                    {(timing.windowLower || timing.windowUpper) && (
                      <p className="text-xs text-muted-foreground mt-1">
                        Window: [{timing.windowLower || '0'}, {timing.windowUpper || '0'}]
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          )}
        </Card>
      )}

      {/* Activity Instances */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <ListTree className="h-5 w-5" />
                Scheduled Activity Instances 
                {selectedEpoch !== 'all' && <Badge variant="secondary">{filteredInstances.length} of {instances.length}</Badge>}
                {selectedEpoch === 'all' && <Badge variant="secondary">{instances.length}</Badge>}
              </CardTitle>
              <CardDescription>
                Activities bound to specific encounters and epochs
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={expandAll}>
                Expand All
              </Button>
              <Button variant="outline" size="sm" onClick={collapseAll}>
                Collapse All
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {/* Search */}
          <div className="relative mb-4">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search activities by name..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Grouped by Epoch */}
          <div className="space-y-3">
            {Object.entries(groupedByEpoch).map(([epochId, epochInstances]) => {
              const colors = epochColorMap[epochId];
              const isExpanded = expandedEpochs.has(epochId);
              const displayInstances = isExpanded ? epochInstances : epochInstances.slice(0, 5);
              
              return (
                <div key={epochId} className={cn("border-2 rounded-lg overflow-hidden", colors.border)}>
                  {/* Epoch Header */}
                  <button
                    onClick={() => toggleEpoch(epochId)}
                    className={cn("w-full px-4 py-3 font-medium flex items-center justify-between", colors.bg, "hover:opacity-90 transition-opacity")}
                  >
                    <div className="flex items-center gap-2">
                      {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                      <span className={colors.text}>{resolveEpochName(epochId)}</span>
                    </div>
                    <Badge className={cn(colors.fill, "text-white")}>{epochInstances.length} activities</Badge>
                  </button>
                  
                  {/* Activity List */}
                  <div className="divide-y bg-white">
                    {displayInstances.map(inst => (
                      <div key={inst.id} className="px-4 py-3 hover:bg-muted/30 transition-colors">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <p className="font-medium text-sm">{inst.name}</p>
                            <div className="flex flex-wrap gap-2 mt-1.5">
                              {inst.encounterId && (
                                <Badge variant="outline" className="text-xs">
                                  <Calendar className="h-3 w-3 mr-1" />
                                  {resolveEncounterName(inst.encounterId)}
                                </Badge>
                              )}
                              {inst.activityIds && inst.activityIds.length > 0 && (
                                <div className="flex flex-wrap gap-1">
                                  {inst.activityIds.map(actId => (
                                    <Badge key={actId} variant="secondary" className="text-xs">
                                      <Activity className="h-3 w-3 mr-1" />
                                      {resolveActivityName(actId)}
                                    </Badge>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                    
                    {!isExpanded && epochInstances.length > 5 && (
                      <button
                        onClick={() => toggleEpoch(epochId)}
                        className="w-full px-4 py-2 text-sm text-center hover:bg-muted/50 transition-colors"
                      >
                        <span className={colors.text}>Show {epochInstances.length - 5} more activities</span>
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {filteredInstances.length === 0 && (
            <div className="py-8 text-center text-muted-foreground">
              <Search className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p>No activities match your search</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default ExecutionModelView;
