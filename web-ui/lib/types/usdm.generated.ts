// ==========================================================================
// AUTO-GENERATED — DO NOT EDIT MANUALLY
// Generated from USDM dataStructure.yml (tag: unknown)
// Generated at: 2026-02-08T09:52:04.896660
// Generator: scripts/generate_ts_types.py
// Entities: 68 from schema + execution model extensions
//
// To regenerate: python scripts/generate_ts_types.py
// ==========================================================================


// ==========================================================================
// Core Types
// ==========================================================================

/**
 * A set of letters that are drawn from a word or from a sequence of words and
 * that are used for brevity in place of the full word or phrase. (CDISC
 * Glossary)
 * @nciCode C42610
 * @preferredTerm Abbreviation
 */
export interface Abbreviation {
  id: string;
  abbreviatedText: string;  // C215487
  expandedText: string;  // C215569
  notes?: CommentAnnotation[];  // C215570
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * An alternative symbol or combination of symbols which is assigned to the
 * members of a collection.
 * @nciCode C201344
 * @preferredTerm Alias Code
 */
export interface AliasCode {
  id: string;
  standardCode: Code;  // C215528
  standardCodeAliases?: Code[];  // C215529
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * A symbol or combination of symbols which is assigned to the members of a
 * collection.
 * @nciCode C25162
 * @preferredTerm Code
 */
export interface Code {
  id: string;
  code: string;  // C188858
  codeSystem: string;  // C188859
  codeSystemVersion: string;  // C188868
  decode: string;  // C188861
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * An explanatory or critical comment, or other in-context information (e.g.,
 * pattern, motif, link), that has been associated with data or other types of
 * information.
 * @nciCode C44272
 * @preferredTerm Comment Annotation
 */
export interface CommentAnnotation {
  id: string;
  text: string;  // C215555
  codes?: Code[];  // C215556
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * A state of being.
 * @nciCode C25457
 * @preferredTerm Condition
 */
export interface Condition {
  id: string;
  name: string;  // C207483
  label?: string | null;  // C207482
  description?: string | null;  // C207481
  text: string;  // C207484
  notes?: CommentAnnotation[];  // C215552
  dictionaryId?: string | null;
  contextIds?: string[];
  appliesToIds?: string[];
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * The length of time during which something continues.
 * @nciCode C25330
 * @preferredTerm Duration
 */
export interface Duration {
  id: string;
  text?: string | null;  // C217008
  quantity?: QuantityRange | null;  // C217011
  durationWillVary: boolean;  // C217009
  reasonDurationWillVary?: string | null;  // C217010
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 */
export interface ExtensionAttribute {
  id: string;
  url: string;
  valueString?: string | null;
  valueBoolean?: boolean | null;
  valueInteger?: number | null;
  valueId?: string | null;
  valueQuantity?: Quantity | null;
  valueRange?: Range | null;
  valueCode?: Code | null;
  valueAliasCode?: AliasCode | null;
  valueExtensionClass?: ExtensionClass | null;
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * Any of the dates associated with event milestones within a clinical study's
 * oversight and management framework.
 * @nciCode C207595
 * @preferredTerm Study Governance Date
 */
export interface GovernanceDate {
  id: string;
  name: string;  // C207499
  label?: string | null;  // C207498
  description?: string | null;  // C207497
  type: Code;  // C207496
  dateValue: Record<string, unknown>;  // C207500
  geographicScopes: GeographicScope[];
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * The container that holds an instance of unstructured text and which may
 * include objects such as tables, figures, and images.
 * @nciCode C207592
 * @preferredTerm Narrative Content
 */
export interface NarrativeContent {
  id: string;
  name: string;  // C207507
  sectionNumber?: string | null;  // C207509
  sectionTitle?: string | null;  // C207510
  displaySectionTitle: boolean;  // C215534
  displaySectionNumber: boolean;  // C215535
  contentItemId?: string | null;
  previousId?: string | null;
  nextId?: string | null;
  childIds?: string[];
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * An individual item within the container that holds an instance of
 * unstructured text and which may include objects such as tables, figures,
 * and images.
 * @nciCode C215489
 * @preferredTerm Narrative Content Item
 */
export interface NarrativeContentItem {
  id: string;
  name: string;  // C215557
  text: string;  // C215558
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * How much there is of something that can be measured; the total amount or
 * number.
 * @nciCode C25256
 * @preferredTerm Quantity
 */
export interface Quantity {
  id: string;
  value: Record<string, unknown>;  // C25712
  unit?: AliasCode | null;  // C44258
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * An expression that defines the lower and upper limits of a variation.
 * @nciCode C38013
 * @preferredTerm Range
 */
export interface Range {
  id: string;
  minValue: Quantity;  // C25570
  maxValue: Quantity;  // C25564
  isApproximate: boolean;  // C207525
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * A guide that governs the allocation of subjects to operational options at a
 * discrete decision point or branch (e.g., assignment to a particular arm,
 * discontinuation) within a clinical trial plan.
 * @nciCode C82567
 * @preferredTerm Transition Rule
 */
export interface TransitionRule {
  id: string;
  name: string;  // C207588
  label?: string | null;  // C207587
  description?: string | null;  // C188835
  text: string;  // C207589
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}


// ==========================================================================
// Study Structure
// ==========================================================================

/**
 * The disease or condition the intervention will diagnose, treat, prevent,
 * cure, or mitigate.
 * @nciCode C41184
 * @preferredTerm Disease/Condition Indication
 */
export interface Indication {
  id: string;
  name: string;  // C207503
  label?: string | null;  // C207502
  description?: string | null;  // C112038
  isRareDisease: boolean;  // C207501
  codes?: Code[];  // C188822
  notes?: CommentAnnotation[];  // C215509
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * The strategy that specifies the structure of an interventional trial in
 * terms of the planned activities (including timing) and statistical analysis
 * approach intended to meet the objectives of the study.
 * @nciCode C215503
 * @preferredTerm Interventional Study Design
 */
export interface InterventionalStudyDesign {
  id: string;
  name: string;  // C215626
  label?: string | null;  // C215628
  description?: string | null;  // C215627
  rationale: string;  // C215629
  therapeuticAreas?: Code[];  // C215633
  studyType?: Code | null;  // C215631
  characteristics?: Code[];  // C215632
  studyPhase?: AliasCode | null;  // C215630
  notes?: CommentAnnotation[];  // C215634
  activities?: Activity[];
  biospecimenRetentions?: BiospecimenRetention[];
  eligibilityCriteria: EligibilityCriterion[];
  encounters?: Encounter[];
  estimands?: Estimand[];
  indications?: Indication[];
  objectives?: Objective[];
  scheduleTimelines?: ScheduleTimeline[];
  arms: StudyArm[];
  studyCells: StudyCell[];
  documentVersionIds?: string[];
  elements?: StudyElement[];
  studyInterventionIds?: string[];
  epochs: StudyEpoch[];
  population: StudyDesignPopulation;
  model: Code;  // C98746
  subTypes?: Code[];  // C49660
  blindingSchema?: AliasCode | null;  // C49658
  intentTypes?: Code[];  // C49652
  extensionAttributes?: ExtensionAttribute[];
  analysisPopulations?: AnalysisPopulation[];
  instanceType: string;
}

/**
 * The strategy that specifies the structure of an observational study in
 * terms of the planned activities (including timing) and statistical analysis
 * approach intended to meet the objectives of the study.
 * @nciCode C215504
 * @preferredTerm Observational Study Design
 */
export interface ObservationalStudyDesign {
  id: string;
  name: string;  // C215636
  label?: string | null;  // C215638
  description?: string | null;  // C215637
  rationale: string;  // C215639
  therapeuticAreas?: Code[];  // C215643
  studyType?: Code | null;  // C215641
  characteristics?: Code[];  // C215642
  studyPhase?: AliasCode | null;  // C215640
  notes?: CommentAnnotation[];  // C215644
  activities?: Activity[];
  biospecimenRetentions?: BiospecimenRetention[];
  eligibilityCriteria: EligibilityCriterion[];
  encounters?: Encounter[];
  estimands?: Estimand[];
  indications?: Indication[];
  objectives?: Objective[];
  scheduleTimelines?: ScheduleTimeline[];
  arms: StudyArm[];
  studyCells: StudyCell[];
  documentVersionIds?: string[];
  elements?: StudyElement[];
  studyInterventionIds?: string[];
  epochs: StudyEpoch[];
  population: StudyDesignPopulation;
  model: Code;  // C147138
  subTypes?: Code[];  // C215635
  timePerspective: Code;  // C126065
  samplingMethod?: Code | null;  // C126067
  extensionAttributes?: ExtensionAttribute[];
  analysisPopulations?: AnalysisPopulation[];
  instanceType: string;
}

/**
 * A formalized group of persons or other organizations collected together for
 * a common purpose (such as administrative, legal, political) and the
 * infrastructure to carry out that purpose. (BRIDG)
 * @nciCode C19711
 * @preferredTerm Organization
 */
export interface Organization {
  id: string;
  name: string;  // C93874
  label?: string | null;  // C207514
  identifier: string;  // C93401
  identifierScheme: string;  // C188819
  type: Code;  // C188820
  legalAddress?: Address | null;
  managedSites?: StudySite[];
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * A clinical study involves research using human volunteers (also called
 * participants) that is intended to add to medical knowledge. There are two
 * main types of clinical studies: clinical trials (also called interventional
 * studies) and observational studies. (CDISC Glossary)
 * @nciCode C15206
 * @preferredTerm Clinical Study
 */
export interface Study {
  id: string;
  name: string;  // C68631
  label?: string | null;  // C207479
  description?: string | null;  // C142704
  versions?: StudyVersion[];
  documentedBy?: StudyDefinitionDocument[];
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * A written description of a change(s) to, or formal clarification of, a
 * study.
 * @nciCode C207594
 * @preferredTerm Study Amendment
 */
export interface StudyAmendment {
  id: string;
  name: string;  // C216995
  label?: string | null;  // C216997
  description?: string | null;  // C216996
  number: string;  // C207537
  notes?: CommentAnnotation[];  // C215538
  summary: string;  // C115627
  geographicScopes: GeographicScope[];
  dateValues?: GovernanceDate[];
  impacts?: StudyAmendmentImpact[];
  enrollments?: SubjectEnrollment[];
  secondaryReasons?: StudyAmendmentReason[];
  changes: StudyChange[];
  previousId?: string | null;
  primaryReason: StudyAmendmentReason;
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * The rationale for the change(s) to, or formal clarification of, a protocol.
 * @nciCode C207457
 * @preferredTerm Study Amendment Reason
 */
export interface StudyAmendmentReason {
  id: string;
  otherReason?: string | null;  // C207539
  code: Code;  // C207540
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * A plan detailing how a study will be performed in order to represent the
 * phenomenon under examination, to answer the research questions that have
 * been asked, and informing the statistical approach.
 * @nciCode C15320
 * @preferredTerm Study Design
 */
export interface StudyDesign {
  id: string;
  name: string;  // C215626
  label?: string | null;  // C215628
  description?: string | null;  // C215627
  rationale: string;  // C215629
  therapeuticAreas?: Code[];  // C215633
  studyType?: Code | null;  // C215631
  characteristics?: Code[];  // C215632
  studyPhase?: AliasCode | null;  // C215630
  notes?: CommentAnnotation[];  // C215634
  activities?: Activity[];
  biospecimenRetentions?: BiospecimenRetention[];
  eligibilityCriteria: EligibilityCriterion[];
  encounters?: Encounter[];
  estimands?: Estimand[];
  indications?: Indication[];
  objectives?: Objective[];
  scheduleTimelines?: ScheduleTimeline[];
  arms: StudyArm[];
  studyCells: StudyCell[];
  documentVersionIds?: string[];
  elements?: StudyElement[];
  studyInterventionIds?: string[];
  epochs: StudyEpoch[];
  population: StudyDesignPopulation;
  analysisPopulations?: AnalysisPopulation[];
}

/**
 * A sequence of characters used to identify, name, or characterize the study.
 * @nciCode C83082
 * @preferredTerm Study Identifier
 */
export interface StudyIdentifier {
  id: string;
  text: string;  // C215507
  scopeId: string;
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * The sponsor-defined name of the clinical study.
 * @nciCode C49802
 * @preferredTerm Study Title
 */
export interface StudyTitle {
  id: string;
  type: Code;  // C207568
  text: string;  // C207567
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * A plan at a particular point in time for a study.
 * @nciCode C188816
 * @preferredTerm Study Version
 */
export interface StudyVersion {
  id: string;
  versionIdentifier: string;  // C207570
  businessTherapeuticAreas?: Code[];  // C201322
  rationale: string;  // C94122
  notes?: CommentAnnotation[];  // C215539
  abbreviations?: Abbreviation[];
  dateValues?: GovernanceDate[];
  referenceIdentifiers?: ReferenceIdentifier[];
  amendments?: StudyAmendment[];
  documentVersionIds?: string[];
  studyDesigns?: StudyDesign[];
  studyIdentifiers: StudyIdentifier[];
  titles: StudyTitle[];
  extensionAttributes?: ExtensionAttribute[];
  eligibilityCriterionItems?: EligibilityCriterionItem[];
  narrativeContentItems?: NarrativeContentItem[];
  roles?: StudyRole[];
  organizations?: Organization[];
  studyInterventions?: StudyIntervention[];
  administrableProducts?: AdministrableProduct[];
  medicalDevices?: MedicalDevice[];
  productOrganizationRoles?: ProductOrganizationRole[];
  biomedicalConcepts?: BiomedicalConcept[];
  bcCategories?: BiomedicalConceptCategory[];
  bcSurrogates?: BiomedicalConceptSurrogate[];
  dictionaries?: SyntaxTemplateDictionary[];
  conditions?: Condition[];
  instanceType: string;
}


// ==========================================================================
// Design Components
// ==========================================================================

/**
 * A planned pathway assigned to the subject as they progress through the
 * study, usually referred to by a name that reflects one or more treatments,
 * exposures, and/or controls included in the path.
 * @nciCode C174447
 * @preferredTerm Study Arm
 */
export interface StudyArm {
  id: string;
  name: string;  // C170984
  label?: string | null;  // C172456
  description?: string | null;  // C93728
  type: Code;  // C172457
  dataOriginType: Code;  // C188829
  dataOriginDescription: string;  // C188828
  notes?: CommentAnnotation[];  // C215515
  populationIds?: string[];
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * A partitioning of a study arm into individual pieces, which are associated
 * with an epoch and any number of sequential elements within that epoch.
 * @nciCode C188810
 * @preferredTerm Study Design Cell
 */
export interface StudyCell {
  id: string;
  armId: string;
  epochId: string;
  elementIds: string[];
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * The population within the general population to which the study results can
 * be generalized.
 * @nciCode C142728
 * @preferredTerm Study Design Population
 */
export interface StudyDesignPopulation {
  id: string;
  name: string;  // C207553
  label?: string | null;  // C207550
  description?: string | null;  // C70834
  plannedSex?: Code | null;  // C207551
  includesHealthySubjects: boolean;  // C207549
  plannedAge?: Range | null;  // C207450
  plannedCompletionNumber?: QuantityRange | null;  // C207451
  plannedEnrollmentNumber?: QuantityRange | null;  // C207452
  notes?: CommentAnnotation[];  // C215512
  criterionIds?: string[];
  cohorts?: StudyCohort[];
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * A basic building block for time within a clinical study comprising the
 * following characteristics: a description of what happens to the subject
 * during the element; a definition of the start of the element; a rule for
 * ending the element.
 * @nciCode C142735
 * @preferredTerm Study Design Element
 */
export interface StudyElement {
  id: string;
  name: string;  // C188833
  label?: string | null;  // C207554
  description?: string | null;  // C188834
  notes?: CommentAnnotation[];  // C215517
  transitionEndRule?: TransitionRule | null;
  studyInterventionIds?: string[];
  transitionStartRule?: TransitionRule | null;
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * A named time period defined in the protocol, wherein a study activity is
 * specified and unchanging throughout the interval, to support a
 * study-specific purpose.
 * @nciCode C71738
 * @preferredTerm Study Epoch
 */
export interface StudyEpoch {
  id: string;
  name: string;  // C93825
  label?: string | null;  // C207555
  description?: string | null;  // C93824
  type: Code;  // C188830
  notes?: CommentAnnotation[];  // C215516
  previousId?: string | null;
  nextId?: string | null;
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}


// ==========================================================================
// SoA / Schedule
// ==========================================================================

/**
 * An action, undertaking, or event, which is anticipated to be performed or
 * observed, or was performed or observed, according to the study protocol
 * during the execution of the study.
 * @nciCode C71473
 * @preferredTerm Study Activity
 */
export interface Activity {
  id: string;
  name: string;  // C188842
  label?: string | null;  // C207458
  description?: string | null;  // C70960
  notes?: CommentAnnotation[];  // C215519
  definedProcedures?: Procedure[];
  biomedicalConceptIds?: string[];
  nextId?: string | null;
  timelineId?: string | null;
  childIds?: string[];
  previousId?: string | null;
  bcSurrogateIds?: string[];
  bcCategoryIds?: string[];
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * Any physical or virtual contact between two or more parties involved in a
 * study, at which an assessment or activity takes place.
 * @nciCode C215488
 * @preferredTerm Study Encounter
 */
export interface Encounter {
  id: string;
  name: string;  // C171010
  label?: string | null;  // C207490
  description?: string | null;  // C188836
  type: Code;  // C188839
  environmentalSettings?: Code[];  // C188840
  contactModes?: Code[];  // C188841
  notes?: CommentAnnotation[];  // C215518
  transitionEndRule?: TransitionRule | null;
  nextId?: string | null;
  transitionStartRule?: TransitionRule | null;
  scheduledAtId?: string | null;
  previousId?: string | null;
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * A chronological schedule of planned temporal events.
 * @nciCode C201348
 * @preferredTerm Schedule Timeline
 */
export interface ScheduleTimeline {
  id: string;
  name: string;  // C201334
  label?: string | null;  // C207530
  description?: string | null;  // C201332
  entryCondition: string;  // C201333
  mainTimeline: boolean;  // C201331
  plannedDuration?: Duration | null;  // C217012
  instances?: ScheduledInstance[];
  entryId: string;
  exits?: ScheduleTimelineExit[];
  timings?: Timing[];
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * To go out of or leave the schedule timeline.
 * @nciCode C201349
 * @preferredTerm Schedule Timeline Exit
 */
export interface ScheduleTimelineExit {
  id: string;
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * A scheduled occurrence of an activity event.
 * @nciCode C201350
 * @preferredTerm Scheduled Activity Instance
 */
export interface ScheduledActivityInstance {
  id: string;
  name: string;  // C207533
  label?: string | null;  // C207532
  description?: string | null;  // C207531
  defaultConditionId?: string | null;
  epochId?: string | null;
  activityIds?: string[];
  encounterId?: string | null;
  timelineId?: string | null;
  timelineExitId?: string | null;
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * A scheduled occurrence of a decision event.
 * @nciCode C201351
 * @preferredTerm Scheduled Decision Instance
 */
export interface ScheduledDecisionInstance {
  id: string;
  name: string;  // C207536
  label?: string | null;  // C207535
  description?: string | null;  // C207534
  defaultConditionId?: string | null;
  epochId?: string | null;
  conditionAssignments: ConditionAssignment[];
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * The chronological relationship between temporal events.
 * @nciCode C80484
 * @preferredTerm Timing
 */
export interface Timing {
  id: string;
  name: string;  // C207584
  label?: string | null;  // C207583
  description?: string | null;  // C164648
  type: Code;  // C201298
  relativeToFrom: Code;  // C201297
  value: string;  // C201341
  valueLabel: string;  // C207585
  windowLabel?: string | null;  // C207586
  windowLower?: string | null;  // C201342
  windowUpper?: string | null;  // C201343
  relativeToScheduledInstanceId?: string | null;
  relativeFromScheduledInstanceId: string;
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}


// ==========================================================================
// Eligibility
// ==========================================================================

/**
 * Characteristics which are necessary to allow a subject to participate in a
 * clinical study, as outlined in the study protocol. The concept covers
 * inclusion and exclusion criteria.
 * @nciCode C16112
 * @preferredTerm Study Eligibility Criterion
 */
export interface EligibilityCriterion {
  id: string;
  name: string;  // C207488
  label?: string | null;  // C207487
  description?: string | null;  // C207486
  identifier: string;  // C207489
  category: Code;  // C83016
  notes?: CommentAnnotation[];  // C215537
  criterionItemId: string;
  nextId?: string | null;
  previousId?: string | null;
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * An individual item within the container that holds an instance of an
 * eligibility criterion.
 * @nciCode C215506
 * @preferredTerm Eligibility Criterion Item
 */
export interface EligibilityCriterionItem {
  id: string;
  name: string;  // C215647
  label?: string | null;  // C215650
  description?: string | null;  // C215649
  text: string;  // C215648
  notes?: CommentAnnotation[];  // C215651
  dictionaryId?: string | null;
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}


// ==========================================================================
// Objectives & Endpoints
// ==========================================================================

/**
 * A defined variable intended to reflect an outcome of interest that is
 * statistically analyzed to address a particular research question. NOTE: A
 * precise definition of an endpoint typically specifies the type of
 * assessments made, the timing of those assessments, the assessment tools
 * used, and possibly other details, as applicable, such as how multiple
 * assessments within an individual are to be combined. [After BEST Resource]
 * (CDISC Glossary)
 * @nciCode C25212
 * @preferredTerm Study Endpoint
 */
export interface Endpoint {
  id: string;
  name: string;  // C207492
  label?: string | null;  // C207491
  description?: string | null;  // C188824
  text: string;  // C207493
  notes?: CommentAnnotation[];  // C215514
  dictionaryId?: string | null;
  level: Code;  // C188826
  purpose: string;  // C188825
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * A precise description of the treatment effect reflecting the clinical
 * question posed by a given clinical trial objective. It summarises at a
 * population level what the outcomes would be in the same patients under
 * different treatment conditions being compared. (ICH E9 R1 Addendum)
 * @nciCode C188813
 * @preferredTerm Estimand
 */
export interface Estimand {
  id: string;
  populationSummary: string;  // C188853
  name: string;  // C215522
  label?: string | null;  // C215524
  description?: string | null;  // C215523
  notes?: CommentAnnotation[];  // C215521
  analysisPopulationId: string;
  variableOfInterestId: string;
  intercurrentEvents: IntercurrentEvent[];
  interventionIds: string[];
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * An event(s) occurring after treatment initiation that affects either the
 * interpretation or the existence of the measurements associated with the
 * clinical question of interest. (ICH E9 Addendum on Estimands)
 * @nciCode C188815
 * @preferredTerm Intercurrent Event
 */
export interface IntercurrentEvent {
  id: string;
  name: string;  // C188855
  label?: string | null;  // C207504
  description?: string | null;  // C188856
  text: string;  // C215526
  notes?: CommentAnnotation[];  // C215527
  dictionaryId?: string | null;
  strategy: string;  // C188857
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * The reason for performing a study in terms of the scientific questions to
 * be answered by the analysis of data collected during the study.
 * @nciCode C142450
 * @preferredTerm Study Objective
 */
export interface Objective {
  id: string;
  name: string;  // C207512
  label?: string | null;  // C207511
  description?: string | null;  // C94090
  text: string;  // C207513
  notes?: CommentAnnotation[];  // C215513
  dictionaryId?: string | null;
  level: Code;  // C188823
  endpoints?: Endpoint[];
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}


// ==========================================================================
// Interventions
// ==========================================================================

/**
 * Any study product that is formulated and presented in the form that is
 * suitable for administration to a study participant.
 * @nciCode C215492
 * @preferredTerm Administrable Product
 */
export interface AdministrableProduct {
  id: string;
  name: string;  // C215573
  label?: string | null;  // C215575
  description?: string | null;  // C215574
  administrableDoseForm: AliasCode;  // C215576
  sourcing?: Code | null;  // C215578
  productDesignation: Code;  // C215579
  pharmacologicClass?: Code | null;  // C215577
  notes?: CommentAnnotation[];  // C215580
  identifiers?: AdministrableProductIdentifier[];
  properties?: AdministrableProductProperty[];
  ingredients?: Ingredient[];
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * The act of dispensing, applying, or tendering a product, agent, or therapy.
 * @nciCode C25409
 * @preferredTerm Administration
 */
export interface Administration {
  id: string;
  name: string;  // C207465
  label?: string | null;  // C207464
  description?: string | null;  // C207463
  dose?: Quantity | null;  // C167190
  frequency?: AliasCode | null;  // C89081
  route?: AliasCode | null;  // C38114
  duration: Duration;  // C69282
  notes?: CommentAnnotation[];  // C215544
  administrableProductId?: string | null;
  medicalDeviceId?: string | null;
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * Any instrument, apparatus, implement, machine, appliance, implant, reagent
 * for in vitro use, software, material or other similar or related article,
 * intended by the manufacturer to be used, alone or in combination for, one
 * or more specific medical purpose(s). [After REGULATION (EU) 2017/745 OF THE
 * EUROPEAN PARLIAMENT AND OF THE COUNCIL of 5 April 2017 on medical devices]
 * @nciCode C16830
 * @preferredTerm Medical Device
 */
export interface MedicalDevice {
  id: string;
  name: string;  // C215614
  label?: string | null;  // C215616
  description?: string | null;  // C215615
  hardwareVersion?: string | null;  // C215617
  softwareVersion?: string | null;  // C111093
  sourcing?: Code | null;  // C215619
  notes?: CommentAnnotation[];  // C215618
  embeddedProductId?: string | null;
  identifiers?: MedicalDeviceIdentifier[];
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * Any activity performed by manual and/or instrumental means for the purpose
 * of diagnosis, assessment, therapy, prevention, or palliative care.
 * @nciCode C98769
 * @preferredTerm Procedure
 */
export interface Procedure {
  id: string;
  name: string;  // C201325
  label?: string | null;  // C207524
  description?: string | null;  // C201324
  procedureType: string;  // C188848
  code: Code;  // C154626
  notes?: CommentAnnotation[];  // C215520
  studyInterventionId?: string | null;
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * Any agent, device, or procedure being tested or used as a reference or
 * comparator in the conduct of a clinical trial.
 * @nciCode C207649
 * @preferredTerm Study Intervention
 */
export interface StudyIntervention {
  id: string;
  name: string;  // C207558
  label?: string | null;  // C207556
  description?: string | null;  // C207647
  role: Code;  // C207560
  type: Code;  // C98747
  codes?: Code[];  // C207648
  minimumResponseDuration?: Quantity | null;  // C207557
  notes?: CommentAnnotation[];  // C215543
  administrations?: Administration[];
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}


// ==========================================================================
// Masking
// ==========================================================================

/**
 * The mechanism used to obscure the distinctive characteristics of the study
 * intervention or procedure to make it indistinguishable from a comparator.
 * (CDISC Glossary)
 * @nciCode C191278
 * @preferredTerm Masking
 */
export interface Masking {
  id: string;
  text: string;  // C215553
  isMasked: boolean;  // C215554
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}


// ==========================================================================
// Biospecimen
// ==========================================================================

/**
 * The continued possession, cataloging, and storage of collected biological
 * specimens beyond their initial use.
 * @nciCode C215505
 * @preferredTerm Biospecimen Retention
 */
export interface BiospecimenRetention {
  id: string;
  name: string;  // C215645
  label?: string | null;  // C215646
  description?: string | null;  // C181231
  isRetained: boolean;  // C164620
  includesDNA?: boolean | null;  // C127777
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}


// ==========================================================================
// Population
// ==========================================================================

/**
 * A concise explanation of the meaning of a population.
 * @nciCode C207593
 * @preferredTerm Population Definition
 */
export interface PopulationDefinition {
  id: string;
  name: string;  // C207544
  label?: string | null;  // C207543
  description?: string | null;  // C207542
  plannedSex?: Code | null;  // C207541
  includesHealthySubjects: boolean;  // C207480
  plannedAge?: Range | null;  // C207545
  plannedCompletionNumber?: QuantityRange | null;  // C207546
  plannedEnrollmentNumber?: QuantityRange | null;  // C207702
  notes?: CommentAnnotation[];  // C215547
  criterionIds?: string[];
}


// ==========================================================================
// Syntax
// ==========================================================================

/**
 * The paired name and value for a given parameter.
 * @nciCode C207456
 * @preferredTerm Parameter Map
 */
export interface ParameterMap {
  id: string;
  tag: string;  // C207515
  reference: string;  // C207516
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * A reference source that provides a listing of valid parameter names and
 * values used in syntax template text strings.
 * @nciCode C207597
 * @preferredTerm Syntax Template Dictionary
 */
export interface SyntaxTemplateDictionary {
  id: string;
  name: string;  // C207581
  label?: string | null;  // C207580
  description?: string | null;  // C207579
  parameterMaps: ParameterMap[];
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}


// ==========================================================================
// Referenced Support Types
// ==========================================================================

/**
 * A sequence of characters used to identify, name, or characterize the
 * administrable product.
 * @nciCode C215493
 * @preferredTerm Administrable Product Identifier
 */
export interface AdministrableProductIdentifier {
  id: string;
  text: string;  // C215581
  scopeId: string;
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * A characteristic from a set of characteristics used to define an
 * administrable product.
 * @nciCode C215494
 * @preferredTerm Administrable Product Property
 */
export interface AdministrableProductProperty {
  id: string;
  name: string;  // C215582
  type: Code;  // C215585
  text: string;  // C215583
  quantity?: Quantity | null;  // C215584
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * A target study population on which an analysis is performed. These may be
 * represented by the entire study population, a subgroup defined by a
 * particular characteristic measured at baseline, or a principal stratum
 * defined by the occurrence (or non-occurrence, depending on context) of a
 * specific intercurrent event. (ICH E9 R1 Addendum)
 * @nciCode C188814
 * @preferredTerm Analysis Population
 */
export interface AnalysisPopulation {
  id: string;
  text: string;  // C207468
  name: string;  // C207467
  label?: string | null;  // C207466
  description?: string | null;  // C188854
  notes?: CommentAnnotation[];  // C215525
  subsetOfIds?: string[];
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * A unit of biomedical knowledge created from a unique combination of
 * characteristics that include implementation details like variables and
 * terminologies, used as building blocks for standardized, hierarchically
 * structured clinical research information.
 * @nciCode C201345
 * @preferredTerm Biomedical Concept
 */
export interface BiomedicalConcept {
  id: string;
  name: string;  // C201312
  label?: string | null;  // C207470
  synonyms?: string[];  // C201314
  reference: string;  // C201313
  code: AliasCode;  // C207469
  notes?: CommentAnnotation[];  // C215530
  properties?: BiomedicalConceptProperty[];
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * A grouping of biomedical concepts based on some commonality or by user
 * defined characteristics.
 * @nciCode C201346
 * @preferredTerm Biomedical Concept Category
 */
export interface BiomedicalConceptCategory {
  id: string;
  name: string;  // C201317
  label?: string | null;  // C207471
  description?: string | null;  // C201316
  code?: AliasCode | null;  // C201315
  notes?: CommentAnnotation[];  // C215533
  memberIds?: string[];
  childIds?: string[];
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * A concept that substitutes for a standard biomedical concept from the
 * designated source.
 * @nciCode C207590
 * @preferredTerm Biomedical Concept Surrogate
 */
export interface BiomedicalConceptSurrogate {
  id: string;
  name: string;  // C207474
  label?: string | null;  // C207473
  description?: string | null;  // C201320
  reference?: string | null;  // C201321
  notes?: CommentAnnotation[];  // C215532
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * An allotting or appointment to a condition or set of conditions that are to
 * be met in order to make a logical decision.
 * @nciCode C201335
 * @preferredTerm Condition Assignment
 */
export interface ConditionAssignment {
  id: string;
  condition: string;  // C47953
  conditionTargetId: string;
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 */
export interface ExtensionClass {
  id: string;
  url: string;
  extensionAttributes: ExtensionAttribute[];
  instanceType: string;
}

/**
 * The extent or range related to the physical location of an entity.
 * @nciCode C207591
 * @preferredTerm Geographic Scope
 */
export interface GeographicScope {
  id: string;
  type: Code;  // C207495
  code?: AliasCode | null;  // C207494
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * Any component that constitutes a part of a compounded substance or mixture.
 * @nciCode C51981
 * @preferredTerm Ingredient
 */
export interface Ingredient {
  id: string;
  role: Code;  // C215595
  substance: Substance;
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * A sequence of characters used to identify, name, or characterize the
 * medical device.
 * @nciCode C215501
 * @preferredTerm Medical Device Identifier
 */
export interface MedicalDeviceIdentifier {
  id: string;
  text: string;  // C215620
  scopeId: string;
  type: Code;  // C215621
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * A designation that identifies the function of an organization within the
 * context of the product.
 * @nciCode C215502
 * @preferredTerm Product Organization Role
 */
export interface ProductOrganizationRole {
  id: string;
  name: string;  // C215622
  label?: string | null;  // C215624
  description?: string | null;  // C215623
  code: Code;  // C215625
  appliesToIds?: string[];
  organizationId: string;
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * The total amount (number), or the limits (minimum and maximum) of a
 * variation.
 * @nciCode C217000
 * @preferredTerm Quantity or Range
 */
export interface QuantityRange {
  id: string;
}

/**
 * A sequence of characters used to identify, name, or characterize the
 * reference.
 * @nciCode C82531
 * @preferredTerm Reference Identifier
 */
export interface ReferenceIdentifier {
  id: string;
  text: string;  // C215572
  scopeId: string;
  type: Code;  // C215571
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * A group of individuals who share a set of characteristics (e.g., exposures,
 * experiences, attributes), which logically defines a population under study.
 * @nciCode C61512
 * @preferredTerm Study Cohort
 */
export interface StudyCohort {
  id: string;
  name: string;  // C207544
  label?: string | null;  // C207543
  description?: string | null;  // C207542
  plannedSex?: Code | null;  // C207541
  includesHealthySubjects: boolean;  // C207480
  plannedAge?: Range | null;  // C207545
  plannedCompletionNumber?: QuantityRange | null;  // C207546
  plannedEnrollmentNumber?: QuantityRange | null;  // C207702
  notes?: CommentAnnotation[];  // C215547
  criterionIds?: string[];
  characteristics?: Characteristic[];
  indicationIds?: string[];
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}

/**
 * A designation that identifies the function of study personnel or an
 * organization within the context of the study.
 * @nciCode C215497
 * @preferredTerm Study Role
 */
export interface StudyRole {
  id: string;
  name: string;  // C215600
  label?: string | null;  // C215602
  description?: string | null;  // C215601
  code: Code;  // C215603
  notes?: CommentAnnotation[];  // C216994
  assignedPersons?: AssignedPerson[];
  masking?: Masking | null;
  organizationIds?: string[];
  appliesToIds?: string[];
  extensionAttributes?: ExtensionAttribute[];
  instanceType: string;
}


// ==========================================================================
// Custom Types (not in official USDM schema, used by Protocol2USDM)
// ==========================================================================

/**
 * Grouping of activities — used by Protocol2USDM for SoA row grouping.
 * Not an official USDM entity; stored via extensionAttributes or activityGroups.
 */
export interface ActivityGroup {
  id: string;
  name: string;
  label?: string | null;
  description?: string | null;
  activityIds?: string[];
  childIds?: string[];
  instanceType?: string;
  extensionAttributes?: ExtensionAttribute[];
}

// Stub types for entities referenced but not fully generated
export type Address = Record<string, unknown>;
export type AssignedPerson = Record<string, unknown>;
export type BiomedicalConceptProperty = Record<string, unknown>;
export type Characteristic = Record<string, unknown>;
export type ScheduledInstance = Record<string, unknown>;
export type StudyAmendmentImpact = Record<string, unknown>;
export type StudyChange = Record<string, unknown>;
export type StudyDefinitionDocument = Record<string, unknown>;
export type StudySite = Record<string, unknown>;
export type SubjectEnrollment = Record<string, unknown>;
export type Substance = Record<string, unknown>;
export type date = Record<string, unknown>;
export type float = Record<string, unknown>;


// ============================================================================
// Execution Model Extension Types
// ============================================================================
// These types complement core USDM entities and are stored in extensionAttributes.
// Source: extraction/execution/schema.py

export type AnchorType =
  | "FirstDose"
  | "TreatmentStart"
  | "Randomization"
  | "Screening"
  | "Day1"
  | "Baseline"
  | "Enrollment"
  | "InformedConsent"
  | "CycleStart"
  | "CollectionDay"
  | "Custom";

export type RepetitionType =
  | ""
  | "Daily"
  | "Interval"
  | "Cycle"
  | "Continuous"
  | "OnDemand";

export type ExecutionType =
  | "Window"
  | "Episode"
  | "Single"
  | "Recurring";

export type EndpointType =
  | "Primary"
  | "Secondary"
  | "Exploratory"
  | "Safety";

export type DosingFrequency =
  | "QD"
  | "BID"
  | "TID"
  | "QID"
  | "QW"
  | "Q2W"
  | "Q4W"
  | "QM"
  | "PRN"
  | "ONCE"
  | "CONTINUOUS"
  | "CUSTOM";

export type RouteOfAdministration =
  | "ORAL"
  | "IV"
  | "SC"
  | "IM"
  | "TOPICAL"
  | "INHALATION"
  | "OPHTHALMIC"
  | "OTIC"
  | "NASAL"
  | "RECTAL"
  | "VAGINAL"
  | "TRANSDERMAL"
  | "OTHER";

export interface TimeAnchor {
  id: string;
  definition: string;
  anchorType: AnchorType;
  timelineId?: string | null;
  dayValue?: number | null;
  sourceText?: string | null;
}

export interface Repetition {
  id: string;
  type: RepetitionType;
  interval?: string | null;
  count?: number | null;
  startOffset?: string | null;
  endOffset?: string | null;
  activityId?: string | null;
  activityIds?: string[];
  sourceText?: string | null;
}

export interface VisitWindow {
  id: string;
  visitName: string;
  targetDay: number;
  targetWeek?: number | null;
  windowBefore: number;
  windowAfter: number;
  isRequired: boolean;
  visitNumber?: number | null;
  epoch?: string | null;
  sourceText?: string | null;
}

export interface FootnoteCondition {
  id: string;
  conditionType: string;
  text: string;
  footnoteId?: string | null;
  structuredCondition?: string | null;
  appliesToActivityIds?: string[];
  sourceText?: string | null;
  originalIndex?: number | null;
  editable?: boolean;
}

export interface DosingRegimen {
  id: string;
  treatmentName: string;
  frequency: DosingFrequency;
  route: RouteOfAdministration;
  startDay?: number | null;
  endDay?: number | null;
  doseLevels?: { amount: number; unit: string }[];
  titrationSchedule?: string | null;
  doseModifications?: string[];
  sourceText?: string | null;
}

export interface StateTransition {
  fromState: string;
  toState: string;
  trigger: string;
  guardCondition?: string | null;
  probability?: number | null;
}

export interface SubjectStateMachine {
  id: string;
  initialState: string;
  terminalStates: string[];
  states: string[];
  transitions: StateTransition[];
  sourceText?: string | null;
  epochIds?: Record<string, string>;
}

export interface SamplingConstraint {
  id: string;
  constraintId: string;
  activityId: string;
  domain: string;
  anchorId?: string | null;
  timepoints?: number[];
  windowStart?: number | null;
  windowEnd?: number | null;
  sourceText?: string | null;
}

export interface TraversalConstraint {
  id: string;
  requiredSequence?: string[];
  allowEarlyExit?: boolean;
  exitEpochIds?: string[];
  mandatoryVisits?: string[];
  sourceText?: string | null;
}

export interface ActivityBinding {
  activityId: string;
  activityName: string;
  repetitionIds: string[];
}

export interface CrossoverDesign {
  isCrossover: boolean;
  numPeriods?: number | null;
  numSequences?: number | null;
  periods?: string[];
  sequences?: string[];
  washoutDuration?: string | null;
  washoutRequired?: boolean;
}

export interface EndpointAlgorithm {
  id: string;
  endpointType: EndpointType;
  endpointName: string;
  formula?: string | null;
  baselineDefinition?: string | null;
  analysisWindow?: string | null;
  sourceText?: string | null;
}

export interface DerivedVariable {
  id: string;
  variableName: string;
  variableType: string;
  derivationRule?: string | null;
  inputVariables?: string[];
  sourceText?: string | null;
}

export interface RandomizationScheme {
  id: string;
  method: string;
  stratificationFactors?: string[];
  blockSize?: number | null;
  ratio?: string | null;
  sourceText?: string | null;
}

export interface ClassifiedIssue {
  severity: "blocking" | "warning" | "info";
  category: string;
  message: string;
  affectedPath?: string | null;
  affectedIds?: string[];
  suggestion?: string | null;
}

/**
 * Aggregated execution model data — the full extraction output
 * stored in extensionAttributes on StudyDesign.
 */
export interface ExecutionModelData {
  timeAnchors?: TimeAnchor[];
  repetitions?: Repetition[];
  samplingConstraints?: SamplingConstraint[];
  traversalConstraints?: TraversalConstraint[];
  executionTypes?: { activityId: string; executionType: ExecutionType; rationale?: string }[];
  crossoverDesign?: CrossoverDesign | null;
  footnoteConditions?: FootnoteCondition[];
  endpointAlgorithms?: EndpointAlgorithm[];
  derivedVariables?: DerivedVariable[];
  stateMachine?: SubjectStateMachine | null;
  dosingRegimens?: DosingRegimen[];
  visitWindows?: VisitWindow[];
  activityBindings?: ActivityBinding[];
  randomizationScheme?: RandomizationScheme | null;
  classifiedIssues?: ClassifiedIssue[];
}
