#!/usr/bin/env python3
"""
TypeScript Type Generator — Generates web-ui TypeScript interfaces from the
same USDM schema sources used by the Python pipeline.

Sources:
  1. core/schema_cache/dataStructure.yml  (USDM v4.0 entities)
  2. extraction/execution/schema.py       (execution model extensions)

Output:
  web-ui/lib/types/usdm.generated.ts

Usage:
  python scripts/generate_ts_types.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Any, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.usdm_schema_loader import USDMSchemaLoader, EntityDefinition, AttributeDefinition

# Which entities to generate — covers everything the frontend needs.
# Grouped by usage domain (mirrors schema_prompt_generator.ENTITY_GROUPS).
ENTITIES_TO_GENERATE: Dict[str, Set[str]] = {
    "Core Types": {
        "Code",
        "AliasCode",
        "CommentAnnotation",
        "Duration",
        "Quantity",
        "Range",
        "ExtensionAttribute",
        "Abbreviation",
        "GovernanceDate",
        "TransitionRule",
        "Condition",
        "NarrativeContent",
        "NarrativeContentItem",
    },
    "Study Structure": {
        "Study",
        "StudyVersion",
        "StudyDesign",
        "InterventionalStudyDesign",
        "ObservationalStudyDesign",
        "StudyTitle",
        "StudyIdentifier",
        "Organization",
        "Indication",
        "StudyAmendment",
        "StudyAmendmentReason",
    },
    "Design Components": {
        "StudyArm",
        "StudyEpoch",
        "StudyCell",
        "StudyElement",
        "StudyDesignPopulation",
    },
    "SoA / Schedule": {
        "Activity",
        "ActivityGroup",
        "Encounter",
        "ScheduleTimeline",
        "ScheduledActivityInstance",
        "ScheduledDecisionInstance",
        "ScheduleTimelineExit",
        "Timing",
    },
    "Eligibility": {
        "EligibilityCriterion",
        "EligibilityCriterionItem",
    },
    "Objectives & Endpoints": {
        "Objective",
        "Endpoint",
        "Estimand",
        "IntercurrentEvent",
    },
    "Interventions": {
        "StudyIntervention",
        "Administration",
        "AdministrableProduct",
        "Procedure",
        "MedicalDevice",
    },
    "Masking": {
        "Masking",
    },
    "Biospecimen": {
        "BiospecimenRetention",
    },
    "Population": {
        "PopulationDefinition",
    },
    "Syntax": {
        "SyntaxTemplateDictionary",
        "ParameterMap",
    },
    "Referenced Support Types": {
        "QuantityRange",
        "ExtensionClass",
        "GeographicScope",
        "ConditionAssignment",
        "StudyCohort",
        "AnalysisPopulation",
        "ReferenceIdentifier",
        "StudyRole",
        "ProductOrganizationRole",
        "BiomedicalConcept",
        "BiomedicalConceptCategory",
        "BiomedicalConceptSurrogate",
        "AdministrableProductIdentifier",
        "AdministrableProductProperty",
        "Ingredient",
        "MedicalDeviceIdentifier",
    },
}

# Flatten to a single set for lookup
ALL_ENTITIES = set()
for group_entities in ENTITIES_TO_GENERATE.values():
    ALL_ENTITIES.update(group_entities)

# YAML type ref → TypeScript type
TS_TYPE_MAP = {
    "#/string": "string",
    "#/integer": "number",
    "#/boolean": "boolean",
    "#/number": "number",
}


def ts_type_for_attr(attr: AttributeDefinition, all_entity_names: Set[str]) -> str:
    """Convert a schema attribute to its TypeScript type string."""
    base_ref = attr.type_ref.replace("#/", "")

    # Primitive types
    if attr.type_ref in TS_TYPE_MAP:
        base_ts = TS_TYPE_MAP[attr.type_ref]
    elif base_ref in all_entity_names:
        # Reference to another entity we're generating
        base_ts = base_ref
    else:
        # Unknown entity — use generic Record
        base_ts = "Record<string, unknown>"

    # If it's a Ref relationship, the JSON representation is an ID string
    if attr.is_reference:
        base_ts = "string"

    # Cardinality
    if attr.is_list:
        return f"{base_ts}[]"
    elif not attr.is_required:
        return f"{base_ts} | null"
    else:
        return base_ts


def generate_interface(entity: EntityDefinition, all_entity_names: Set[str]) -> str:
    """Generate a TypeScript interface for a single USDM entity."""
    lines: List[str] = []

    # JSDoc comment
    lines.append("/**")
    if entity.definition:
        # Wrap definition to ~80 chars
        defn = entity.definition.replace("\n", " ").strip()
        while len(defn) > 76:
            idx = defn.rfind(" ", 0, 76)
            if idx == -1:
                idx = 76
            lines.append(f" * {defn[:idx]}")
            defn = defn[idx:].strip()
        if defn:
            lines.append(f" * {defn}")
    if entity.nci_code:
        lines.append(f" * @nciCode {entity.nci_code}")
    if entity.preferred_term:
        lines.append(f" * @preferredTerm {entity.preferred_term}")
    lines.append(" */")

    # Interface declaration
    lines.append(f"export interface {entity.name} {{")

    for attr_name, attr_def in entity.attributes.items():
        ts_type = ts_type_for_attr(attr_def, all_entity_names)
        optional = "?" if not attr_def.is_required else ""
        # Add inline comment for NCI code
        comment = ""
        if attr_def.nci_code:
            comment = f"  // {attr_def.nci_code}"
        lines.append(f"  {attr_name}{optional}: {ts_type};{comment}")

    lines.append("}")
    return "\n".join(lines)


def generate_execution_model_types() -> str:
    """
    Generate TypeScript types for the execution model extensions.
    These are read from extraction/execution/schema.py enums and key dataclasses.
    Rather than parsing Python AST, we define them from the known schema.
    """
    return '''
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

export interface FactorLevel {
  id: string;
  label: string;
  definition?: string | null;
  criterionId?: string | null;
  code?: Record<string, unknown> | null;
}

export interface StratificationFactor {
  id: string;
  name: string;
  categories: string[];
  factorLevels?: FactorLevel[];
  isBlocking: boolean;
  isNesting?: boolean;
  parentFactorId?: string | null;
  dataSource?: string | null;
  sourceText?: string | null;
}

export interface AllocationCell {
  id: string;
  factorLevels: Record<string, string>;
  armId?: string | null;
  ratioWeight: number;
  isValid: boolean;
  plannedEnrollment?: number | null;
}

export interface RandomizationScheme {
  id: string;
  ratio: string;
  method: string;
  algorithmType: string;
  blockSize?: number | null;
  blockSizes?: number[];
  stratificationFactors?: StratificationFactor[];
  allocationCells?: AllocationCell[];
  centralRandomization: boolean;
  iwrsSystem?: string | null;
  concealmentMethod?: string | null;
  seedMethod?: string | null;
  isAdaptive?: boolean;
  adaptiveRules?: string | null;
  blindingSchemaId?: string | null;
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
}'''


def main():
    output_path = PROJECT_ROOT / "web-ui" / "lib" / "types" / "usdm.generated.ts"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load schema
    loader = USDMSchemaLoader()
    entities = loader.load()
    all_entity_names = set(entities.keys())

    # Collect entities to generate, preserving group order
    ordered_entities: List[tuple] = []  # (group_name, entity_name, EntityDefinition)
    missing: List[str] = []

    for group_name, entity_names in ENTITIES_TO_GENERATE.items():
        for name in sorted(entity_names):
            if name in entities:
                ordered_entities.append((group_name, name, entities[name]))
            else:
                missing.append(name)

    if missing:
        print(f"Warning: {len(missing)} entities not found in schema: {missing}")

    # Build output
    lines: List[str] = []

    # Header
    version_info = loader.get_schema_version_info() or {}
    schema_tag = version_info.get("schema_tag", "unknown")
    lines.append("// ==========================================================================")
    lines.append("// AUTO-GENERATED — DO NOT EDIT MANUALLY")
    lines.append(f"// Generated from USDM dataStructure.yml (tag: {schema_tag})")
    lines.append(f"// Generated at: {datetime.now().isoformat()}")
    lines.append(f"// Generator: scripts/generate_ts_types.py")
    lines.append(f"// Entities: {len(ordered_entities)} from schema + execution model extensions")
    lines.append("//")
    lines.append("// To regenerate: python scripts/generate_ts_types.py")
    lines.append("// ==========================================================================")
    lines.append("")

    # Generate grouped interfaces
    current_group = None
    for group_name, entity_name, entity_def in ordered_entities:
        if group_name != current_group:
            current_group = group_name
            lines.append("")
            lines.append(f"// {'=' * 74}")
            lines.append(f"// {group_name}")
            lines.append(f"// {'=' * 74}")
            lines.append("")

        lines.append(generate_interface(entity_def, all_entity_names))
        lines.append("")

    # Add custom types not in official schema but used by the codebase
    lines.append("")
    lines.append("// ==========================================================================")
    lines.append("// Custom Types (not in official USDM schema, used by Protocol2USDM)")
    lines.append("// ==========================================================================")
    lines.append("")
    lines.append("/**")
    lines.append(" * Grouping of activities — used by Protocol2USDM for SoA row grouping.")
    lines.append(" * Not an official USDM entity; stored via extensionAttributes or activityGroups.")
    lines.append(" */")
    lines.append("export interface ActivityGroup {")
    lines.append("  id: string;")
    lines.append("  name: string;")
    lines.append("  label?: string | null;")
    lines.append("  description?: string | null;")
    lines.append("  activityIds?: string[];")
    lines.append("  childIds?: string[];")
    lines.append("  instanceType?: string;")
    lines.append("  extensionAttributes?: ExtensionAttribute[];")
    lines.append("}")
    lines.append("")

    # Emit stub types for any entities referenced but not generated
    generated_names = {e[1] for e in ordered_entities}
    generated_names.add("ActivityGroup")  # custom
    referenced_but_missing: Set[str] = set()
    for _, _, entity_def in ordered_entities:
        for attr_name, attr_def in entity_def.attributes.items():
            ref = attr_def.type_ref.replace("#/", "")
            if ref not in TS_TYPE_MAP.values() and ref not in {k.replace('#/', '') for k in TS_TYPE_MAP} and ref not in generated_names and not attr_def.is_reference:
                referenced_but_missing.add(ref)

    if referenced_but_missing:
        lines.append("// Stub types for entities referenced but not fully generated")
        for stub_name in sorted(referenced_but_missing):
            lines.append(f"export type {stub_name} = Record<string, unknown>;")
        lines.append("")

    # Add execution model extension types
    lines.append(generate_execution_model_types())
    lines.append("")

    # Write output
    content = "\n".join(lines)
    output_path.write_text(content, encoding="utf-8")

    print(f"Generated {output_path}")
    print(f"  USDM entities: {len(ordered_entities)}")
    print(f"  Schema tag: {schema_tag}")
    print(f"  File size: {len(content):,} bytes")


if __name__ == "__main__":
    main()
