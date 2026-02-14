// Types for execution model data — shared across all panel sub-components

export interface TimeAnchor {
  id: string;
  definition: string;
  anchorType: string;
  classification?: string;
  timelineId?: string | null;
  dayValue?: number;
  sourceText?: string;
  encounterId?: string | null;
  activityId?: string | null;
}

export interface VisitWindow {
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

export interface FootnoteCondition {
  id: string;
  conditionType: string;
  text: string;
  footnoteId?: string;
  structuredCondition?: string;
  appliesToActivityIds?: string[];
  sourceText?: string;
  originalIndex?: number;
  editable?: boolean;
}

export interface Repetition {
  id: string;
  type: string;
  interval?: string;
  count?: number;
  activityIds?: string[];
  sourceText?: string;
}

export interface DosingRegimen {
  id: string;
  treatmentName: string;
  frequency: string;
  route: string;
  startDay?: number;
  doseLevels?: { amount: number; unit: string }[];
  titrationSchedule?: string;
  doseModifications?: string[];
}

export interface StateMachine {
  id: string;
  initialState: string;
  terminalStates: string[];
  states: string[];
  transitions: { fromState: string; toState: string; trigger: string }[];
}

export interface TraversalConstraint {
  id: string;
  requiredSequence?: string[];
  allowEarlyExit?: boolean;
  exitEpochIds?: string[];
  mandatoryVisits?: string[];
  sourceText?: string;
}

export interface ExecutionType {
  activityId: string;
  executionType: string;
  rationale?: string;
}

export interface ClassifiedIssue {
  severity: 'blocking' | 'warning' | 'info';
  category: string;
  message: string;
  affectedPath?: string;
  affectedIds?: string[];
  suggestion?: string;
}

export interface StudyExit {
  id: string;
  name: string;
  exitType: string;
  description?: string;
}

export interface TimingDetail {
  id: string;
  name: string;
  type?: string;
  value?: string;
  valueLabel?: string;
  relativeToFrom?: string;
  windowLower?: string;
  windowUpper?: string;
}

export interface ScheduledInstance {
  id: string;
  name: string;
  activityIds?: string[];
  epochId?: string;
  encounterId?: string;
  timingId?: string;
}

export interface ExecutionModelData {
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

export type TabId = 'overview' | 'anchors' | 'visits' | 'conditions' | 'repetitions' | 'dosing' | 'statemachine' | 'traversal' | 'issues' | 'schedule';
