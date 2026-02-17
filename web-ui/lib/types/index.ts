/**
 * USDM Type Barrel — Re-exports generated schema types and provides
 * runtime-safe variants for working with extracted data.
 *
 * Generated types (strict):  import type { Activity } from '@/lib/types/usdm.generated'
 * Runtime types (loose):     import type { USDMActivity } from '@/lib/types'
 *
 * Runtime types use Partial<> so missing fields from extraction don't cause errors,
 * plus [key: string]: unknown for extensionAttributes and custom fields.
 */

// Import ExtensionAttribute for use in runtime-safe types below
import type { ExtensionAttribute as _ExtensionAttribute } from './usdm.generated';
type ExtensionAttribute = _ExtensionAttribute;

// Re-export all generated types as-is for strict usage
export type {
  // Core
  Code,
  AliasCode,
  CommentAnnotation,
  Duration,
  Quantity,
  Range,
  ExtensionAttribute,
  Abbreviation,
  GovernanceDate,
  TransitionRule,
  Condition,
  NarrativeContent,
  NarrativeContentItem,

  // Study structure
  Study,
  StudyVersion,
  StudyDesign,
  StudyTitle,
  StudyIdentifier,
  Organization,
  Indication,
  StudyAmendment,
  StudyAmendmentReason,

  // Design components
  StudyArm,
  StudyEpoch,
  StudyCell,
  StudyElement,
  StudyDesignPopulation,

  // SoA / Schedule
  Activity,
  ActivityGroup,
  Encounter,
  ScheduleTimeline,
  ScheduledActivityInstance,
  ScheduledDecisionInstance,
  ScheduleTimelineExit,
  Timing,

  // Eligibility
  EligibilityCriterion,
  EligibilityCriterionItem,

  // Objectives & Endpoints
  Objective,
  Endpoint,
  Estimand,
  IntercurrentEvent,

  // Interventions
  StudyIntervention,
  Administration,
  AdministrableProduct,
  Procedure,
  MedicalDevice,

  // Other
  Masking,
  BiospecimenRetention,
  PopulationDefinition,

  // Execution model extensions
  AnchorType,
  RepetitionType,
  ExecutionType,
  EndpointType,
  DosingFrequency,
  RouteOfAdministration,
  TimeAnchor,
  Repetition,
  VisitWindow,
  FootnoteCondition,
  DosingRegimen,
  StateTransition,
  SubjectStateMachine,
  SamplingConstraint,
  TraversalConstraint,
  ActivityBinding,
  CrossoverDesign,
  EndpointAlgorithm,
  DerivedVariable,
  RandomizationScheme,
  ClassifiedIssue,
  ExecutionModelData,
} from './usdm.generated';

// ==========================================================================
// Runtime-safe types
// ==========================================================================
// These interfaces include official USDM fields (optional for flexibility)
// plus pipeline-specific fields added during extraction. The index signature
// allows access to any extra fields without TypeScript errors.

export interface USDMStudy {
  id: string;
  instanceType?: string;
  versions: USDMStudyVersion[];
  [key: string]: unknown;
}

export interface USDMStudyVersion {
  id: string;
  instanceType?: string;
  versionIdentifier?: string;
  studyDesigns?: USDMStudyDesign[];
  [key: string]: unknown;
}

export interface USDMStudyDesign {
  id: string;
  name: string;
  instanceType: string;
  activities?: USDMActivity[];
  activityGroups?: USDMActivityGroup[];
  encounters?: USDMEncounter[];
  epochs?: USDMEpoch[];
  scheduleTimelines?: USDMScheduleTimeline[];
  timings?: USDMTiming[];
  arms?: USDMArm[];
  studyCells?: unknown[];
  elements?: unknown[];
  studyElements?: unknown[];
  eligibilityCriteria?: unknown[];
  objectives?: unknown[];
  indications?: unknown[];
  estimands?: unknown[];
  maskingRoles?: unknown[];
  population?: unknown;
  extensionAttributes?: ExtensionAttribute[];
  [key: string]: unknown;
}

export interface USDMActivity {
  id: string;
  name: string;
  label?: string;
  description?: string;
  instanceType?: string;
  childIds?: string[];
  nextId?: string;
  previousId?: string;
  timelineId?: string;
  definedProcedures?: unknown[];
  extensionAttributes?: ExtensionAttribute[];
  [key: string]: unknown;
}

export interface USDMActivityGroup {
  id: string;
  name: string;
  label?: string;
  description?: string;
  instanceType?: string;
  activityIds?: string[];
  childIds?: string[];
  extensionAttributes?: ExtensionAttribute[];
  [key: string]: unknown;
}

export interface USDMEncounter {
  id: string;
  name: string;
  label?: string;
  description?: string;
  instanceType?: string;
  // Pipeline-specific: encounter's epoch association
  epochId?: string;
  // Pipeline-specific: convenience timing object
  timing?: {
    windowLabel?: string;
    [key: string]: unknown;
  };
  type?: unknown;
  transitionStartRule?: unknown;
  transitionEndRule?: unknown;
  scheduledAtId?: string;
  nextId?: string;
  previousId?: string;
  environmentalSettings?: unknown[];
  contactModes?: unknown[];
  extensionAttributes?: ExtensionAttribute[];
  [key: string]: unknown;
}

export interface USDMEpoch {
  id: string;
  name: string;
  label?: string;
  description?: string;
  instanceType?: string;
  type?: unknown;
  nextId?: string;
  previousId?: string;
  extensionAttributes?: ExtensionAttribute[];
  [key: string]: unknown;
}

export interface USDMArm {
  id: string;
  name: string;
  label?: string;
  description?: string;
  instanceType?: string;
  type?: unknown;
  extensionAttributes?: ExtensionAttribute[];
  [key: string]: unknown;
}

export interface USDMScheduleTimeline {
  id: string;
  name?: string;
  label?: string;
  description?: string;
  instanceType: string;
  mainTimeline?: boolean;
  entryCondition?: string;
  entryId?: string;
  instances?: USDMScheduledInstance[];
  timings?: USDMTiming[];
  exits?: { id: string; instanceType?: string; [key: string]: unknown }[];
  extensionAttributes?: ExtensionAttribute[];
  [key: string]: unknown;
}

export interface USDMScheduledInstance {
  id: string;
  name?: string;
  label?: string;
  description?: string;
  instanceType?: string;
  activityId?: string;
  activityIds?: string[];
  encounterId?: string;
  epochId?: string;
  defaultConditionId?: string;
  conditionAssignments?: {
    id: string;
    condition: string;
    conditionTargetId: string;
    instanceType?: string;
    [key: string]: unknown;
  }[];
  timelineExitId?: string;
  timelineId?: string;
  scheduledAtId?: string;
  extensionAttributes?: ExtensionAttribute[];
  [key: string]: unknown;
}

export interface USDMTiming {
  id: string;
  name?: string;
  label?: string;
  description?: string;
  instanceType?: string;
  type?: string | { code?: string; decode?: string; [key: string]: unknown };
  value?: string | number;
  valueLabel?: string;
  unit?: string;
  windowLower?: string | number;
  windowUpper?: string | number;
  windowLabel?: string;
  relativeTo?: string;
  relativeFromScheduledInstanceId?: string;
  relativeToScheduledInstanceId?: string;
  relativeToFrom?: string | { code?: string; decode?: string; [key: string]: unknown };
  extensionAttributes?: ExtensionAttribute[];
  [key: string]: unknown;
}

// ==========================================================================
// Cross-references & Figures (from document_structure extraction)
// ==========================================================================

export type ReferenceType = 'Section' | 'Table' | 'Figure' | 'Appendix' | 'Listing' | 'Other';
export type FigureContentType = 'Figure' | 'Table' | 'Diagram' | 'Chart' | 'Flowchart' | 'Image';

export interface InlineCrossReference {
  id: string;
  sourceSection: string;
  targetLabel: string;
  targetSection?: string;
  targetId?: string;
  referenceType: ReferenceType;
  contextText?: string;
  instanceType?: string;
}

export interface ProtocolFigure {
  id: string;
  label: string;
  title?: string;
  pageNumber?: number;
  sectionNumber?: string;
  contentType: FigureContentType;
  imagePath?: string;
  instanceType?: string;
}

/** Full USDM document wrapper */
export interface USDMDocument {
  usdmVersion: string;
  generatedAt: string;
  generator: string;
  study: USDMStudy;
  inlineCrossReferences?: InlineCrossReference[];
  protocolFigures?: ProtocolFigure[];
  [key: string]: unknown;
}
