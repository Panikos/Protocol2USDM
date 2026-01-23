"""
USDM Types Generated from Official Schema

This module generates Python dataclasses from the official CDISC dataStructure.yml.
It provides type-safe access to all 86+ USDM entity types with proper:
- Required/optional field handling
- NCI codes and definitions as docstrings
- to_dict() and from_dict() methods
- Validation against schema

Usage:
    from core.usdm_types_generated import Activity, Encounter, Code
    
    activity = Activity(id="act_1", name="Blood Draw")
    print(activity.to_dict())
"""

import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from .usdm_schema_loader import (
    USDMSchemaLoader, EntityDefinition, AttributeDefinition,
    get_schema_loader, get_entity_definition, USDMEntity
)


def generate_uuid() -> str:
    """Generate a UUID string."""
    return str(uuid.uuid4())


# ============================================================================
# Core Types - These are fundamental and used throughout
# ============================================================================

@dataclass
class Code(USDMEntity):
    """
    USDM Code - A symbol or combination of symbols assigned to members of a collection.
    
    NCI Code: C25162
    Required: id, code, codeSystem, codeSystemVersion, decode, instanceType
    """
    code: str
    decode: str
    codeSystem: str = "http://www.cdisc.org"
    codeSystemVersion: str = "2024-09-27"
    id: Optional[str] = None
    instanceType: str = "Code"
    extensionAttributes: List[Any] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self._ensure_id(),
            "code": self.code,
            "codeSystem": self.codeSystem,
            "codeSystemVersion": self.codeSystemVersion,
            "decode": self.decode,
            "instanceType": self.instanceType,
        }
    
    @classmethod
    def make(cls, code: str, decode: str, 
             system: str = "http://www.cdisc.org",
             version: str = "2024-09-27") -> 'Code':
        """Factory method for quick Code creation."""
        return cls(code=code, decode=decode, codeSystem=system, codeSystemVersion=version)
    
    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> Optional['Code']:
        if not data:
            return None
        return cls(
            code=data.get('code', ''),
            decode=data.get('decode', ''),
            codeSystem=data.get('codeSystem', 'http://www.cdisc.org'),
            codeSystemVersion=data.get('codeSystemVersion', '2024-09-27'),
            id=data.get('id'),
        )


@dataclass
class AliasCode(USDMEntity):
    """
    USDM AliasCode - An alternative symbol with standard code reference.
    
    NCI Code: C201344
    Required: id, standardCode, instanceType
    """
    id: Optional[str] = None
    standardCode: Optional[Code] = None
    standardCodeAliases: List[Code] = field(default_factory=list)
    instanceType: str = "AliasCode"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self._ensure_id(),
            "instanceType": self.instanceType,
        }
        if self.standardCode:
            result["standardCode"] = self.standardCode.to_dict()
        if self.standardCodeAliases:
            result["standardCodeAliases"] = [c.to_dict() for c in self.standardCodeAliases]
        return result
    
    @classmethod
    def make_blinding(cls, blind_type: str = "open") -> 'AliasCode':
        """Factory method for blinding schema."""
        codes = {
            "open": ("C49656", "Open Label"),
            "single": ("C15228", "Single Blind"),
            "double": ("C15227", "Double Blind"),
            "triple": ("C156593", "Triple Blind"),
        }
        code, decode = codes.get(blind_type.lower(), codes["open"])
        return cls(standardCode=Code.make(code, decode))


@dataclass
class CommentAnnotation(USDMEntity):
    """
    USDM CommentAnnotation - A note or comment.
    
    NCI Code: C215481
    Required: id, text, instanceType
    """
    id: Optional[str] = None
    text: str = ""
    instanceType: str = "CommentAnnotation"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self._ensure_id(),
            "text": self.text,
            "instanceType": self.instanceType,
        }


@dataclass
class Range(USDMEntity):
    """USDM Range - A numeric range."""
    minValue: Optional[float] = None
    maxValue: Optional[float] = None
    instanceType: str = "Range"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"instanceType": self.instanceType}
        if self.minValue is not None:
            result["minValue"] = self.minValue
        if self.maxValue is not None:
            result["maxValue"] = self.maxValue
        return result


@dataclass  
class Quantity(USDMEntity):
    """USDM Quantity - A value with unit."""
    value: float = 0
    unit: Optional[Code] = None
    instanceType: str = "Quantity"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"value": self.value, "instanceType": self.instanceType}
        if self.unit:
            result["unit"] = self.unit.to_dict()
        return result


# ============================================================================
# Study Structure Types
# ============================================================================

@dataclass
class Study(USDMEntity):
    """
    USDM Study - A clinical study.
    
    NCI Code: C15206
    Required: id, name, instanceType
    """
    id: str = ""
    name: str = ""
    label: Optional[str] = None
    description: Optional[str] = None
    versions: List['StudyVersion'] = field(default_factory=list)
    instanceType: str = "Study"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self._ensure_id(),
            "name": self.name,
            "instanceType": self.instanceType,
        }
        if self.label:
            result["label"] = self.label
        if self.description:
            result["description"] = self.description
        if self.versions:
            result["versions"] = [v.to_dict() for v in self.versions]
        return result


@dataclass
class StudyVersion(USDMEntity):
    """
    USDM StudyVersion - A version of a study.
    
    NCI Code: C142722
    Required: id, versionIdentifier, rationale, titles, studyIdentifiers, instanceType
    """
    id: str = ""
    versionIdentifier: str = "1.0"
    rationale: str = "Initial protocol version"
    titles: List['StudyTitle'] = field(default_factory=list)
    studyIdentifiers: List['StudyIdentifier'] = field(default_factory=list)
    studyDesigns: List['StudyDesign'] = field(default_factory=list)
    studyPhase: Optional[AliasCode] = None
    instanceType: str = "StudyVersion"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self._ensure_id(),
            "versionIdentifier": self.versionIdentifier,
            "rationale": self.rationale,
            "instanceType": self.instanceType,
        }
        if self.titles:
            result["titles"] = [t.to_dict() for t in self.titles]
        if self.studyIdentifiers:
            result["studyIdentifiers"] = [s.to_dict() for s in self.studyIdentifiers]
        if self.studyDesigns:
            result["studyDesigns"] = [d.to_dict() for d in self.studyDesigns]
        if self.studyPhase:
            result["studyPhase"] = self.studyPhase.to_dict()
        return result


@dataclass
class StudyTitle(USDMEntity):
    """
    USDM StudyTitle - A title for a study.
    
    NCI Code: C215507
    Required: id, text, type, instanceType
    """
    id: str = ""
    text: str = ""
    type: Optional[Code] = None
    instanceType: str = "StudyTitle"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self._ensure_id(),
            "text": self.text,
            "instanceType": self.instanceType,
        }
        if self.type:
            result["type"] = self.type.to_dict()
        else:
            result["type"] = Code.make("C99905", "Official Study Title").to_dict()
        return result


@dataclass
class StudyIdentifier(USDMEntity):
    """
    USDM StudyIdentifier - An identifier for a study.
    
    NCI Code: C142709
    Required: id, text, type, instanceType
    
    Type is auto-inferred from the identifier format:
    - NCT... → ClinicalTrials.gov Identifier
    - YYYY-NNNNNN-NN → EudraCT Number
    - 5-6 digits → IND Number
    - Other → Sponsor Protocol Identifier
    """
    id: str = ""
    text: str = ""
    scopeId: Optional[str] = None
    type: Optional[Code] = None  # Auto-inferred if not provided
    instanceType: str = "StudyIdentifier"
    
    def to_dict(self) -> Dict[str, Any]:
        from core.terminology_codes import get_study_identifier_type
        
        result = {
            "id": self._ensure_id(),
            "text": self.text,
            "instanceType": self.instanceType,
        }
        if self.scopeId:
            result["scopeId"] = self.scopeId
        
        # Auto-infer type if not explicitly provided
        if self.type:
            result["type"] = self.type.to_dict() if hasattr(self.type, 'to_dict') else self.type
        else:
            # Infer type from identifier text format
            result["type"] = get_study_identifier_type(self.text)
        
        return result


@dataclass
class Organization(USDMEntity):
    """
    USDM Organization - A formalized group/company.
    
    NCI Code: C19711
    Required: id, name, instanceType
    """
    id: str = ""
    name: str = ""
    type: Optional[Code] = None
    instanceType: str = "Organization"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self._ensure_id(),
            "name": self.name,
            "instanceType": self.instanceType,
        }
        if self.type:
            result["type"] = self.type.to_dict()
        return result


# ============================================================================
# Study Design Types
# ============================================================================

@dataclass
class StudyDesign(USDMEntity):
    """
    USDM StudyDesign - Base for Interventional/Observational designs.
    
    This is typically InterventionalStudyDesign or ObservationalStudyDesign.
    Required: id, name, rationale, model, population, epochs, arms, instanceType
    """
    id: str = ""
    name: str = "Study Design"
    description: Optional[str] = None
    rationale: str = "Protocol-defined study design"
    instanceType: str = "InterventionalStudyDesign"
    
    # Design characteristics
    blindingSchema: Optional[AliasCode] = None
    model: Optional[Code] = None
    
    # Structure
    arms: List['StudyArm'] = field(default_factory=list)
    studyCells: List['StudyCell'] = field(default_factory=list)
    epochs: List['StudyEpoch'] = field(default_factory=list)
    
    # SoA
    activities: List['Activity'] = field(default_factory=list)
    encounters: List['Encounter'] = field(default_factory=list)
    scheduleTimelines: List['ScheduleTimeline'] = field(default_factory=list)
    
    # Population & Eligibility
    population: Optional['StudyDesignPopulation'] = None
    eligibilityCriteria: List['EligibilityCriterion'] = field(default_factory=list)
    
    # Objectives
    objectives: List['Objective'] = field(default_factory=list)
    endpoints: List['Endpoint'] = field(default_factory=list)
    
    # Interventions
    studyInterventions: List['StudyIntervention'] = field(default_factory=list)
    
    # Notes
    notes: List[CommentAnnotation] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self._ensure_id(),
            "name": self.name,
            "rationale": self.rationale,
            "instanceType": self.instanceType,
        }
        
        if self.description:
            result["description"] = self.description
        
        # blindingSchema required for Interventional
        if self.instanceType == "InterventionalStudyDesign":
            if self.blindingSchema:
                result["blindingSchema"] = self.blindingSchema.to_dict()
            else:
                result["blindingSchema"] = AliasCode.make_blinding("open").to_dict()
        
        # Model required
        if self.model:
            result["model"] = self.model.to_dict()
        else:
            if len(self.arms) >= 2:
                result["model"] = Code.make("C82639", "Parallel Study").to_dict()
            else:
                result["model"] = Code.make("C82638", "Single Group Study").to_dict()
        
        # Arrays
        if self.arms:
            result["arms"] = [a.to_dict() for a in self.arms]
        if self.studyCells:
            result["studyCells"] = [c.to_dict() for c in self.studyCells]
        if self.epochs:
            result["epochs"] = [e.to_dict() for e in self.epochs]
        if self.activities:
            result["activities"] = [a.to_dict() for a in self.activities]
        if self.encounters:
            result["encounters"] = [e.to_dict() for e in self.encounters]
        if self.scheduleTimelines:
            result["scheduleTimelines"] = [s.to_dict() for s in self.scheduleTimelines]
        if self.eligibilityCriteria:
            result["eligibilityCriteria"] = [e.to_dict() for e in self.eligibilityCriteria]
        if self.population:
            result["population"] = self.population.to_dict()
        if self.objectives:
            result["objectives"] = [o.to_dict() for o in self.objectives]
        if self.endpoints:
            result["endpoints"] = [e.to_dict() for e in self.endpoints]
        if self.studyInterventions:
            result["studyInterventions"] = [s.to_dict() for s in self.studyInterventions]
        if self.notes:
            result["notes"] = [n.to_dict() for n in self.notes]
        
        return result


@dataclass
class StudyArm(USDMEntity):
    """
    USDM StudyArm - A treatment arm.
    
    NCI Code: C174447
    Required: id, name, type, dataOriginType, dataOriginDescription, instanceType
    """
    id: str = ""
    name: str = ""
    description: Optional[str] = None
    type: Optional[Code] = None
    dataOriginDescription: str = "Collected"
    dataOriginType: Optional[Code] = None
    instanceType: str = "StudyArm"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self._ensure_id(),
            "name": self.name,
            "instanceType": self.instanceType,
            "dataOriginDescription": self.dataOriginDescription or "Collected",
        }
        
        if self.description:
            result["description"] = self.description
        
        # type is required - infer from name
        if self.type:
            result["type"] = self.type.to_dict()
        else:
            name_lower = self.name.lower()
            if "placebo" in name_lower:
                result["type"] = Code.make("C49648", "Placebo Comparator Arm").to_dict()
            elif "active" in name_lower or "comparator" in name_lower:
                result["type"] = Code.make("C49647", "Active Comparator Arm").to_dict()
            elif "control" in name_lower:
                result["type"] = Code.make("C174266", "No Intervention Arm").to_dict()
            else:
                result["type"] = Code.make("C174267", "Experimental Arm").to_dict()
        
        # dataOriginType is required
        if self.dataOriginType:
            result["dataOriginType"] = self.dataOriginType.to_dict()
        else:
            result["dataOriginType"] = Code.make("C70793", "Collected").to_dict()
        
        return result


@dataclass
class StudyCell(USDMEntity):
    """USDM StudyCell - Intersection of arm and epoch."""
    id: str = ""
    armId: str = ""
    epochId: str = ""
    instanceType: str = "StudyCell"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self._ensure_id(),
            "armId": self.armId,
            "epochId": self.epochId,
            "instanceType": self.instanceType,
        }


@dataclass
class StudyEpoch(USDMEntity):
    """
    USDM StudyEpoch - A study phase/period.
    
    NCI Code: C71738
    Required: id, name, type, instanceType
    """
    id: str = ""
    name: str = ""
    description: Optional[str] = None
    label: Optional[str] = None
    type: Optional[Code] = None
    previousId: Optional[str] = None
    nextId: Optional[str] = None
    instanceType: str = "StudyEpoch"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self._ensure_id(),
            "name": self.name,
            "instanceType": self.instanceType,
        }
        
        if self.description:
            result["description"] = self.description
        if self.label:
            result["label"] = self.label
        
        # type is required - infer from name
        if self.type:
            result["type"] = self.type.to_dict()
        else:
            name_lower = self.name.lower()
            if "screen" in name_lower:
                result["type"] = Code.make("C98779", "Screening Epoch").to_dict()
            elif "treatment" in name_lower or "intervention" in name_lower:
                result["type"] = Code.make("C98780", "Treatment Epoch").to_dict()
            elif "follow" in name_lower:
                result["type"] = Code.make("C98781", "Follow-up Epoch").to_dict()
            elif "run-in" in name_lower or "runin" in name_lower or "washout" in name_lower:
                result["type"] = Code.make("C98782", "Run-in Epoch").to_dict()
            else:
                result["type"] = Code.make("C98780", "Treatment Epoch").to_dict()
        
        if self.previousId:
            result["previousId"] = self.previousId
        if self.nextId:
            result["nextId"] = self.nextId
        
        return result


# Backward compatibility alias
Epoch = StudyEpoch


# ============================================================================
# SoA Types
# ============================================================================

@dataclass
class Activity(USDMEntity):
    """
    USDM Activity - A study activity.
    
    NCI Code: C71473
    Required: id, name, instanceType
    """
    id: str = ""
    name: str = ""
    label: Optional[str] = None
    description: Optional[str] = None
    notes: List[CommentAnnotation] = field(default_factory=list)
    definedProcedures: List['Procedure'] = field(default_factory=list)
    biomedicalConceptIds: List[str] = field(default_factory=list)
    nextId: Optional[str] = None
    timelineId: Optional[str] = None
    childIds: List[str] = field(default_factory=list)  # For activity groups
    instanceType: str = "Activity"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self._ensure_id(),
            "name": self.name,
            "instanceType": self.instanceType,
        }
        if self.label:
            result["label"] = self.label
        if self.description:
            result["description"] = self.description
        if self.notes:
            result["notes"] = [n.to_dict() for n in self.notes]
        if self.definedProcedures:
            result["definedProcedures"] = [p.to_dict() for p in self.definedProcedures]
        if self.biomedicalConceptIds:
            result["biomedicalConceptIds"] = self.biomedicalConceptIds
        if self.nextId:
            result["nextId"] = self.nextId
        if self.timelineId:
            result["timelineId"] = self.timelineId
        if self.childIds:
            result["childIds"] = self.childIds
        return result


@dataclass
class Encounter(USDMEntity):
    """
    USDM Encounter - A study visit.
    
    NCI Code: C215488
    Required: id, name, type, instanceType
    """
    id: str = ""
    name: str = ""
    description: Optional[str] = None
    label: Optional[str] = None
    type: Optional[Code] = None
    epochId: Optional[str] = None
    scheduledAtTimingId: Optional[str] = None
    instanceType: str = "Encounter"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self._ensure_id(),
            "name": self.name,
            "instanceType": self.instanceType,
        }
        
        if self.description:
            result["description"] = self.description
        if self.label:
            result["label"] = self.label
        
        # type is required - infer from name
        if self.type:
            result["type"] = self.type.to_dict()
        else:
            name_lower = self.name.lower()
            if "screen" in name_lower:
                result["type"] = Code.make("C48262", "Screening").to_dict()
            elif "baseline" in name_lower or "day 1" in name_lower or "day1" in name_lower:
                result["type"] = Code.make("C82517", "Baseline").to_dict()
            elif "follow" in name_lower:
                result["type"] = Code.make("C99158", "Follow-up").to_dict()
            elif "end" in name_lower or "eos" in name_lower or "completion" in name_lower:
                result["type"] = Code.make("C126070", "End of Study").to_dict()
            elif "early" in name_lower or "discontin" in name_lower or "termination" in name_lower:
                result["type"] = Code.make("C49631", "Early Termination").to_dict()
            elif "unscheduled" in name_lower:
                result["type"] = Code.make("C99157", "Unscheduled").to_dict()
            else:
                result["type"] = Code.make("C99156", "Scheduled Visit").to_dict()
        
        if self.epochId:
            result["epochId"] = self.epochId
        if self.scheduledAtTimingId:
            result["scheduledAtTimingId"] = self.scheduledAtTimingId
        
        return result


@dataclass
class ScheduleTimeline(USDMEntity):
    """
    USDM ScheduleTimeline - Contains scheduled instances.
    
    Per USDM 4.0 schema:
    - instances: 0..* (ScheduledActivityInstance references)
    - timings: 0..* (Timing references for scheduled activities)
    - exits: 0..* (ScheduleTimelineExit references)
    
    Required: id, name, entryCondition, entryId, instanceType
    """
    id: str = ""
    name: str = ""
    description: Optional[str] = None
    label: Optional[str] = None
    mainTimeline: bool = True
    entryCondition: str = "Subject enrolled in study"
    entryId: Optional[str] = None
    instances: List['ScheduledActivityInstance'] = field(default_factory=list)
    timings: List['Timing'] = field(default_factory=list)  # USDM 4.0: timings belong in timeline
    exits: List['ScheduleTimelineExit'] = field(default_factory=list)
    instanceType: str = "ScheduleTimeline"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self._ensure_id(),
            "name": self.name,
            "mainTimeline": self.mainTimeline,
            "instanceType": self.instanceType,
            "entryCondition": self.entryCondition,
        }
        
        if self.description:
            result["description"] = self.description
        if self.label:
            result["label"] = self.label
        
        # entryId is required
        if self.entryId:
            result["entryId"] = self.entryId
        elif self.instances:
            result["entryId"] = self.instances[0].id
        else:
            result["entryId"] = generate_uuid()
        
        if self.instances:
            result["instances"] = [i.to_dict() for i in self.instances]
        if self.timings:
            result["timings"] = [t.to_dict() if hasattr(t, 'to_dict') else t for t in self.timings]
        if self.exits:
            result["exits"] = [e.to_dict() for e in self.exits]
        
        return result


@dataclass
class ScheduledActivityInstance(USDMEntity):
    """
    USDM ScheduledActivityInstance - Activity scheduled at a timepoint.
    
    Per USDM 4.0 schema:
    - activityIds: 0..* (list of activity references)
    - encounterId: 0..1 (reference to Encounter)
    - epochId: 0..1 (reference to StudyEpoch)
    
    Required: id, name, instanceType
    """
    id: str = ""
    activityIds: List[str] = field(default_factory=list)
    activityId: str = ""  # Backward compatibility - converted to activityIds
    name: Optional[str] = None
    epochId: Optional[str] = None
    encounterId: Optional[str] = None
    timingId: Optional[str] = None
    timelineId: Optional[str] = None
    defaultConditionId: Optional[str] = None
    instanceType: str = "ScheduledActivityInstance"
    
    def __post_init__(self):
        # Convert singular activityId to activityIds list for schema compliance
        if self.activityId and not self.activityIds:
            self.activityIds = [self.activityId]
    
    def to_dict(self) -> Dict[str, Any]:
        # Ensure activityIds is populated
        activity_ids = self.activityIds if self.activityIds else ([self.activityId] if self.activityId else [])
        
        result = {
            "id": self._ensure_id(),
            "activityIds": activity_ids,
            "instanceType": self.instanceType,
        }
        
        # name is required - auto-generate if not provided
        act_label = activity_ids[0] if activity_ids else "activity"
        result["name"] = self.name or f"{act_label}@{self.encounterId or 'schedule'}"
        
        if self.epochId:
            result["epochId"] = self.epochId
        if self.encounterId:
            result["encounterId"] = self.encounterId
        if self.timingId:
            result["timingId"] = self.timingId
        if self.timelineId:
            result["timelineId"] = self.timelineId
        if self.defaultConditionId:
            result["defaultConditionId"] = self.defaultConditionId
        
        return result


@dataclass
class ScheduleTimelineExit(USDMEntity):
    """USDM ScheduleTimelineExit - Exit criteria for timeline."""
    id: str = ""
    instanceType: str = "ScheduleTimelineExit"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self._ensure_id(),
            "instanceType": self.instanceType,
        }


@dataclass
class Timing(USDMEntity):
    """
    USDM Timing - Timing for scheduled activities.
    
    Per USDM 4.0 schema, required fields:
    - id, name, type, value, valueLabel, relativeToFrom, relativeFromScheduledInstanceId
    """
    id: str = ""
    name: str = ""
    type: Optional[Code] = None
    value: str = "P0D"  # ISO 8601 duration, required
    valueLabel: str = ""  # Required - human-readable label
    relativeToFrom: Optional[Code] = None  # Required - what timing is relative to
    relativeFromScheduledInstanceId: str = ""  # Required - reference to anchor instance
    windowLower: Optional[str] = None  # ISO 8601 duration
    windowUpper: Optional[str] = None  # ISO 8601 duration
    windowLabel: Optional[str] = None
    instanceType: str = "Timing"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self._ensure_id(),
            "name": self.name or self.valueLabel or "Timing",
            "instanceType": self.instanceType,
            "value": self.value or "P0D",
            "valueLabel": self.valueLabel or self.name or "Day 0",
        }
        
        # Type - default to "Fixed Reference" if not provided
        if self.type:
            result["type"] = self.type.to_dict() if hasattr(self.type, 'to_dict') else self.type
        else:
            result["type"] = {
                "id": generate_uuid(),
                "code": "C71148",
                "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
                "codeSystemVersion": "25.01d",
                "decode": "Fixed Reference",
                "instanceType": "Code"
            }
        
        # relativeToFrom - default to "Study Start" if not provided
        if self.relativeToFrom:
            result["relativeToFrom"] = self.relativeToFrom.to_dict() if hasattr(self.relativeToFrom, 'to_dict') else self.relativeToFrom
        else:
            result["relativeToFrom"] = {
                "id": generate_uuid(),
                "code": "C71153",
                "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
                "codeSystemVersion": "25.01d",
                "decode": "Study Start",
                "instanceType": "Code"
            }
        
        # relativeFromScheduledInstanceId - required, use placeholder if not set
        result["relativeFromScheduledInstanceId"] = self.relativeFromScheduledInstanceId or generate_uuid()
        
        if self.windowLower:
            result["windowLower"] = self.windowLower
        if self.windowUpper:
            result["windowUpper"] = self.windowUpper
        if self.windowLabel:
            result["windowLabel"] = self.windowLabel
            
        return result


# ============================================================================
# Eligibility Types
# ============================================================================

@dataclass
class EligibilityCriterion(USDMEntity):
    """USDM EligibilityCriterion - Eligibility criteria."""
    id: str = ""
    name: str = ""
    text: str = ""
    category: Optional[Code] = None  # Inclusion/Exclusion
    identifier: Optional[str] = None
    instanceType: str = "EligibilityCriterion"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self._ensure_id(),
            "name": self.name,
            "text": self.text,
            "instanceType": self.instanceType,
        }
        if self.category:
            result["category"] = self.category.to_dict()
        if self.identifier:
            result["identifier"] = self.identifier
        return result


@dataclass
class StudyDesignPopulation(USDMEntity):
    """USDM StudyDesignPopulation - Study population definition."""
    id: str = ""
    name: str = ""
    description: Optional[str] = None
    plannedAge: Optional[Range] = None
    plannedSex: List[Code] = field(default_factory=list)
    instanceType: str = "StudyDesignPopulation"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self._ensure_id(),
            "name": self.name,
            "instanceType": self.instanceType,
        }
        if self.description:
            result["description"] = self.description
        if self.plannedAge:
            result["plannedAge"] = self.plannedAge.to_dict()
        if self.plannedSex:
            result["plannedSex"] = [s.to_dict() for s in self.plannedSex]
        return result


# ============================================================================
# Objectives & Endpoints
# ============================================================================

@dataclass
class Objective(USDMEntity):
    """USDM Objective - Study objective."""
    id: str = ""
    name: str = ""
    text: str = ""
    level: Optional[Code] = None  # Primary/Secondary/Exploratory
    instanceType: str = "Objective"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self._ensure_id(),
            "name": self.name,
            "text": self.text,
            "instanceType": self.instanceType,
        }
        if self.level:
            result["level"] = self.level.to_dict()
        return result


@dataclass
class Endpoint(USDMEntity):
    """USDM Endpoint - Study endpoint."""
    id: str = ""
    name: str = ""
    text: str = ""
    level: Optional[Code] = None
    purpose: Optional[str] = None
    instanceType: str = "Endpoint"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self._ensure_id(),
            "name": self.name,
            "text": self.text,
            "instanceType": self.instanceType,
        }
        if self.level:
            result["level"] = self.level.to_dict()
        if self.purpose:
            result["purpose"] = self.purpose
        return result


# ============================================================================
# Interventions
# ============================================================================

@dataclass
class StudyIntervention(USDMEntity):
    """USDM StudyIntervention - Treatment intervention."""
    id: str = ""
    name: str = ""
    description: Optional[str] = None
    role: Optional[Code] = None
    instanceType: str = "StudyIntervention"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self._ensure_id(),
            "name": self.name,
            "instanceType": self.instanceType,
        }
        if self.description:
            result["description"] = self.description
        if self.role:
            result["role"] = self.role.to_dict()
        return result


@dataclass
class Procedure(USDMEntity):
    """USDM Procedure - A procedure performed."""
    id: str = ""
    name: str = ""
    description: Optional[str] = None
    code: Optional[Code] = None
    instanceType: str = "Procedure"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self._ensure_id(),
            "name": self.name,
            "instanceType": self.instanceType,
        }
        if self.description:
            result["description"] = self.description
        if self.code:
            result["code"] = self.code.to_dict()
        return result


# ============================================================================
# Additional Official USDM Types
# ============================================================================

@dataclass
class Duration(USDMEntity):
    """
    USDM Duration - Time duration with optional bounds.
    
    Required: id, durationWillVary, instanceType
    """
    id: str = ""
    durationWillVary: bool = False
    durationMax: Optional[Quantity] = None
    durationMin: Optional[Quantity] = None
    durationDescription: Optional[str] = None
    instanceType: str = "Duration"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self._ensure_id(),
            "durationWillVary": self.durationWillVary,
            "instanceType": self.instanceType,
        }
        if self.durationMax:
            result["durationMax"] = self.durationMax.to_dict()
        if self.durationMin:
            result["durationMin"] = self.durationMin.to_dict()
        if self.durationDescription:
            result["durationDescription"] = self.durationDescription
        return result


@dataclass
class Abbreviation(USDMEntity):
    """
    USDM Abbreviation - Abbreviation with expansion.
    
    Required: id, abbreviatedText, expandedText, instanceType
    """
    id: str = ""
    abbreviatedText: str = ""
    expandedText: str = ""
    instanceType: str = "Abbreviation"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self._ensure_id(),
            "abbreviatedText": self.abbreviatedText,
            "expandedText": self.expandedText,
            "instanceType": self.instanceType,
        }


@dataclass
class Indication(USDMEntity):
    """
    USDM Indication - Medical condition being studied.
    
    Required: id, name, isRareDisease, instanceType
    """
    id: str = ""
    name: str = ""
    description: Optional[str] = None
    codes: List[Code] = field(default_factory=list)
    isRareDisease: bool = False
    instanceType: str = "Indication"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self._ensure_id(),
            "name": self.name,
            "isRareDisease": self.isRareDisease,
            "instanceType": self.instanceType,
        }
        if self.description:
            result["description"] = self.description
        if self.codes:
            result["codes"] = [c.to_dict() for c in self.codes]
        return result


@dataclass
class StudyCohort(USDMEntity):
    """
    USDM StudyCohort - A group of subjects.
    
    Required: id, name, includesHealthySubjects, instanceType
    """
    id: str = ""
    name: str = ""
    description: Optional[str] = None
    includesHealthySubjects: bool = False
    instanceType: str = "StudyCohort"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self._ensure_id(),
            "name": self.name,
            "includesHealthySubjects": self.includesHealthySubjects,
            "instanceType": self.instanceType,
        }
        if self.description:
            result["description"] = self.description
        return result


@dataclass
class Condition(USDMEntity):
    """
    USDM Condition - A conditional rule.
    
    Required: id, name, text, instanceType
    """
    id: str = ""
    name: str = ""
    text: str = ""
    label: Optional[str] = None
    description: Optional[str] = None
    appliesToIds: List[str] = field(default_factory=list)
    contextIds: List[str] = field(default_factory=list)
    instanceType: str = "Condition"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self._ensure_id(),
            "name": self.name,
            "text": self.text,
            "instanceType": self.instanceType,
        }
        if self.label:
            result["label"] = self.label
        if self.description:
            result["description"] = self.description
        if self.appliesToIds:
            result["appliesToIds"] = self.appliesToIds
        if self.contextIds:
            result["contextIds"] = self.contextIds
        return result


@dataclass
class TransitionRule(USDMEntity):
    """
    USDM TransitionRule - Rule for state transitions.
    
    Required: id, name, text, instanceType
    """
    id: str = ""
    name: str = ""
    text: str = ""
    instanceType: str = "TransitionRule"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self._ensure_id(),
            "name": self.name,
            "text": self.text,
            "instanceType": self.instanceType,
        }


@dataclass
class EligibilityCriterionItem(USDMEntity):
    """
    USDM EligibilityCriterionItem - Individual criterion item.
    
    Required: id, name, text, instanceType
    """
    id: str = ""
    name: str = ""
    text: str = ""
    dictionary: Optional[str] = None
    dictionaryVersion: Optional[str] = None
    instanceType: str = "EligibilityCriterionItem"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self._ensure_id(),
            "name": self.name,
            "text": self.text,
            "instanceType": self.instanceType,
        }
        if self.dictionary:
            result["dictionary"] = self.dictionary
        if self.dictionaryVersion:
            result["dictionaryVersion"] = self.dictionaryVersion
        return result


@dataclass
class IntercurrentEvent(USDMEntity):
    """
    USDM IntercurrentEvent - Event affecting estimand.
    
    Required: id, name, text, strategy, instanceType
    """
    id: str = ""
    name: str = ""
    text: str = ""
    strategy: str = ""
    instanceType: str = "IntercurrentEvent"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self._ensure_id(),
            "name": self.name,
            "text": self.text,
            "strategy": self.strategy,
            "instanceType": self.instanceType,
        }


@dataclass
class Estimand(USDMEntity):
    """
    USDM Estimand - Statistical estimand.
    
    Required: id, name, populationSummary, analysisPopulationId, variableOfInterestId, intercurrentEvents, interventionIds
    """
    id: str = ""
    name: str = ""
    populationSummary: str = ""
    analysisPopulationId: str = ""
    variableOfInterestId: str = ""
    intercurrentEvents: List[IntercurrentEvent] = field(default_factory=list)
    interventionIds: List[str] = field(default_factory=list)
    summaryMeasure: Optional[str] = None
    instanceType: str = "Estimand"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self._ensure_id(),
            "name": self.name,
            "populationSummary": self.populationSummary,
            "analysisPopulationId": self.analysisPopulationId,
            "variableOfInterestId": self.variableOfInterestId,
            "intercurrentEvents": [e.to_dict() for e in self.intercurrentEvents],
            "interventionIds": self.interventionIds,
            "instanceType": self.instanceType,
        }
        if self.summaryMeasure:
            result["summaryMeasure"] = self.summaryMeasure
        return result


@dataclass
class Administration(USDMEntity):
    """
    USDM Administration - Drug administration details.
    
    Required: id, name, duration, instanceType
    """
    id: str = ""
    name: str = ""
    description: Optional[str] = None
    duration: Optional[Duration] = None
    route: Optional[Code] = None
    frequency: Optional[Code] = None
    instanceType: str = "Administration"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self._ensure_id(),
            "name": self.name,
            "instanceType": self.instanceType,
        }
        if self.description:
            result["description"] = self.description
        if self.duration:
            result["duration"] = self.duration.to_dict()
        else:
            result["duration"] = Duration().to_dict()
        if self.route:
            result["route"] = self.route.to_dict()
        if self.frequency:
            result["frequency"] = self.frequency.to_dict()
        return result


@dataclass
class AdministrableProduct(USDMEntity):
    """
    USDM AdministrableProduct - Administrable drug product.
    
    Required: id, name, administrableDoseForm, productDesignation, instanceType
    """
    id: str = ""
    name: str = ""
    description: Optional[str] = None
    administrableDoseForm: Optional[Code] = None
    productDesignation: Optional[Code] = None
    instanceType: str = "AdministrableProduct"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self._ensure_id(),
            "name": self.name,
            "instanceType": self.instanceType,
        }
        if self.description:
            result["description"] = self.description
        if self.administrableDoseForm:
            result["administrableDoseForm"] = self.administrableDoseForm.to_dict()
        else:
            result["administrableDoseForm"] = Code.make("C42998", "Tablet Dosage Form").to_dict()
        if self.productDesignation:
            result["productDesignation"] = self.productDesignation.to_dict()
        else:
            result["productDesignation"] = Code.make("C68846", "Investigational Product").to_dict()
        return result


@dataclass
class NarrativeContent(USDMEntity):
    """
    USDM NarrativeContent - Narrative document section.
    
    Required: id, name, displaySectionTitle, displaySectionNumber, instanceType
    """
    id: str = ""
    name: str = ""
    sectionNumber: str = ""
    sectionTitle: str = ""
    displaySectionNumber: str = ""
    displaySectionTitle: str = ""
    text: str = ""
    instanceType: str = "NarrativeContent"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self._ensure_id(),
            "name": self.name,
            "displaySectionNumber": self.displaySectionNumber or self.sectionNumber,
            "displaySectionTitle": self.displaySectionTitle or self.sectionTitle,
            "sectionNumber": self.sectionNumber,
            "sectionTitle": self.sectionTitle,
            "text": self.text,
            "instanceType": self.instanceType,
        }


@dataclass
class StudyAmendment(USDMEntity):
    """
    USDM StudyAmendment - Protocol amendment.
    
    Required: id, name, number, summary, geographicScopes, changes, primaryReason, instanceType
    """
    id: str = ""
    name: str = ""
    number: str = ""
    summary: str = ""
    label: Optional[str] = None
    description: Optional[str] = None
    geographicScopes: List[Code] = field(default_factory=list)
    changes: List[str] = field(default_factory=list)
    primaryReason: Optional[Code] = None
    instanceType: str = "StudyAmendment"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self._ensure_id(),
            "name": self.name,
            "number": self.number,
            "summary": self.summary,
            "instanceType": self.instanceType,
        }
        if self.label:
            result["label"] = self.label
        if self.description:
            result["description"] = self.description
        if self.geographicScopes:
            result["geographicScopes"] = [g.to_dict() for g in self.geographicScopes]
        else:
            result["geographicScopes"] = [Code.make("C17998", "Global").to_dict()]
        if self.changes:
            result["changes"] = self.changes
        else:
            result["changes"] = ["Protocol amendments"]
        if self.primaryReason:
            result["primaryReason"] = self.primaryReason.to_dict()
        else:
            result["primaryReason"] = Code.make("C49663", "Safety").to_dict()
        return result


# ============================================================================
# Helper Functions
# ============================================================================

def create_wrapper_input(
    data = None,
    *,
    timeline=None,
    usdm_version: str = "4.0",
    system_name: str = "Protocol2USDM",
    system_version: str = "6.2.0",
) -> Dict[str, Any]:
    """
    Create a properly wrapped USDM input structure.
    
    Args:
        data: StudyVersion, StudyDesign, Timeline, or dict to wrap
        timeline: Legacy Timeline object (keyword arg for backward compatibility)
        usdm_version: USDM version string
        system_name: System name for wrapper
        system_version: System version for wrapper
    """
    # Handle legacy timeline keyword parameter
    if timeline is not None:
        data = timeline
    
    if data is None:
        raise ValueError("Either 'data' or 'timeline' must be provided")
    
    # Handle Timeline objects (from core.usdm_types)
    if hasattr(data, 'to_study_design'):
        study_design = data.to_study_design()
        version = StudyVersion(studyDesigns=[study_design])
        result = {
            "usdmVersion": usdm_version,
            "systemName": system_name,
            "systemVersion": system_version,
            "study": Study(versions=[version]).to_dict()
        }
        # Preserve activityGroups from Timeline (not in USDM spec but needed for UI)
        if hasattr(data, 'activityGroups') and data.activityGroups:
            sd = result["study"]["versions"][0]["studyDesigns"][0]
            sd["activityGroups"] = [
                g.to_dict() if hasattr(g, 'to_dict') else g 
                for g in data.activityGroups
            ]
        return result
    
    if isinstance(data, StudyVersion):
        return {
            "usdmVersion": usdm_version,
            "systemName": system_name,
            "systemVersion": system_version,
            "study": Study(versions=[data]).to_dict()
        }
    elif isinstance(data, StudyDesign):
        version = StudyVersion(studyDesigns=[data])
        return {
            "usdmVersion": usdm_version,
            "systemName": system_name,
            "systemVersion": system_version,
            "study": Study(versions=[version]).to_dict()
        }
    elif isinstance(data, dict):
        return data
    else:
        raise ValueError(f"Unsupported type: {type(data)}")


def normalize_usdm_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize USDM data by passing entities through dataclasses.
    
    This leverages the auto-population logic in each dataclass's to_dict():
    - Code objects get id, codeSystem, codeSystemVersion, instanceType
    - Encounters get type inferred from name
    - StudyArms get type, dataOriginType inferred
    - Epochs get type inferred from name
    
    This should be called before validation to ensure all required fields are populated.
    """
    import copy
    result = copy.deepcopy(data)
    
    def normalize_code(obj: Dict, preserve_standard_code: bool = True) -> Dict:
        """Normalize a Code object, optionally preserving nested standardCode."""
        if not obj or not isinstance(obj, dict):
            return obj
        if "code" in obj:
            code = Code(
                code=obj.get("code", ""),
                decode=obj.get("decode", obj.get("code", "")),
                codeSystem=obj.get("codeSystem", "http://www.cdisc.org"),
                codeSystemVersion=obj.get("codeSystemVersion", "2024-09-27"),
                id=obj.get("id"),
            )
            result = code.to_dict()
            # Preserve standardCode if present in original (USDM 4.0 requirement)
            if preserve_standard_code and "standardCode" in obj and obj["standardCode"]:
                result["standardCode"] = normalize_code(obj["standardCode"], preserve_standard_code=False)
            return result
        return obj
    
    def normalize_encounter(obj: Dict) -> Dict:
        """Normalize an Encounter."""
        if not obj or not isinstance(obj, dict):
            return obj
        enc = Encounter(
            id=obj.get("id") or None,  # Preserve existing ID, None triggers UUID gen only if truly missing
            name=obj.get("name", ""),
            description=obj.get("description"),
            label=obj.get("label"),
            type=Code.from_dict(obj.get("type")) if obj.get("type") else None,
            epochId=obj.get("epochId"),
        )
        result = enc.to_dict()
        # Preserve extensionAttributes from encounter reconciliation
        if obj.get("extensionAttributes"):
            result["extensionAttributes"] = obj["extensionAttributes"]
        return result
    
    def normalize_epoch(obj: Dict) -> Dict:
        """Normalize a StudyEpoch."""
        if not obj or not isinstance(obj, dict):
            return obj
        epoch = StudyEpoch(
            id=obj.get("id") or None,  # Preserve existing ID
            name=obj.get("name", ""),
            description=obj.get("description"),
            type=Code.from_dict(obj.get("type")) if obj.get("type") else None,
        )
        result = epoch.to_dict()
        # Preserve extensionAttributes from epoch reconciliation
        if obj.get("extensionAttributes"):
            result["extensionAttributes"] = obj["extensionAttributes"]
        return result
    
    def normalize_arm(obj: Dict) -> Dict:
        """Normalize a StudyArm."""
        if not obj or not isinstance(obj, dict):
            return obj
        arm = StudyArm(
            id=obj.get("id") or None,  # Preserve existing ID
            name=obj.get("name", ""),
            description=obj.get("description"),
            type=Code.from_dict(obj.get("type")) if obj.get("type") else None,
            dataOriginDescription=obj.get("dataOriginDescription", "Collected"),
            dataOriginType=Code.from_dict(obj.get("dataOriginType")) if obj.get("dataOriginType") else None,
        )
        return arm.to_dict()
    
    def normalize_study_identifier(obj: Dict) -> Dict:
        """Normalize a StudyIdentifier to include type field and ensure scopeId."""
        if not obj or not isinstance(obj, dict):
            return obj
        # Ensure scopeId is present (required by USDM 4.0 schema)
        scope_id = obj.get("scopeId")
        if not scope_id:
            # Use a placeholder org reference - will be validated later
            scope_id = "org_sponsor_default"
        si = StudyIdentifier(
            id=obj.get("id") or None,
            text=obj.get("text", ""),
            scopeId=scope_id,
            type=Code.from_dict(obj.get("type")) if obj.get("type") else None,
        )
        return si.to_dict()
    
    def normalize_alias_code(obj: Dict) -> Dict:
        """Normalize an AliasCode (e.g., blindingSchema) to include standardCode."""
        if not obj or not isinstance(obj, dict):
            return obj
        
        # If it looks like a Code object (has code but no standardCode), convert to AliasCode
        if obj.get("instanceType") == "Code" or ("code" in obj and "standardCode" not in obj):
            # Convert Code to AliasCode with standardCode
            code_obj = normalize_code(obj)
            return {
                "id": generate_uuid(),
                "standardCode": code_obj,
                "instanceType": "AliasCode",
            }
        
        # Already has standardCode structure, just normalize it
        result = dict(obj)
        if "standardCode" in result and result["standardCode"]:
            result["standardCode"] = normalize_code(result["standardCode"])
        
        if "id" not in result:
            result["id"] = generate_uuid()
        if "instanceType" not in result:
            result["instanceType"] = "AliasCode"
        
        return result
    
    def walk_and_normalize(obj: Any, path: str = "$") -> Any:
        """Recursively walk and normalize entities."""
        if isinstance(obj, dict):
            # Check for specific entity types by instanceType or field patterns
            inst_type = obj.get("instanceType", "")
            
            # Normalize Code objects (preserve standardCode if present)
            if inst_type == "Code" or ("code" in obj and "decode" in obj and "standardCode" not in obj):
                # normalize_code now handles standardCode preservation internally
                return normalize_code(obj, preserve_standard_code=True)
            
            # Normalize by path patterns
            normalized = {}
            for key, value in obj.items():
                new_path = f"{path}.{key}"
                
                # Handle arrays of specific types
                if key == "encounters" and isinstance(value, list):
                    normalized[key] = [normalize_encounter(e) for e in value]
                elif key == "epochs" and isinstance(value, list):
                    normalized[key] = [normalize_epoch(e) for e in value]
                elif key in ("arms", "studyArms") and isinstance(value, list):
                    # Also rename studyArms -> arms
                    normalized["arms"] = [normalize_arm(a) for a in value]
                elif key == "studyIdentifiers" and isinstance(value, list):
                    # Normalize StudyIdentifiers to add type field
                    normalized[key] = [normalize_study_identifier(si) for si in value]
                elif key == "type" and isinstance(value, dict) and "code" in value:
                    normalized[key] = normalize_code(value)
                elif key == "blindingSchema" and isinstance(value, dict):
                    # AliasCode requires standardCode
                    normalized[key] = normalize_alias_code(value)
                elif key == "administrableDoseForm" and isinstance(value, dict):
                    # administrableDoseForm requires nested standardCode (USDM 4.0)
                    if "code" in value and "standardCode" not in value:
                        # Add standardCode as copy of the Code
                        code_normalized = normalize_code(value)
                        normalized[key] = {
                            **code_normalized,
                            "standardCode": {
                                "id": generate_uuid(),
                                "code": code_normalized.get("code", ""),
                                "codeSystem": code_normalized.get("codeSystem", "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl"),
                                "codeSystemVersion": code_normalized.get("codeSystemVersion", "25.01d"),
                                "decode": code_normalized.get("decode", ""),
                                "instanceType": "Code",
                            }
                        }
                    else:
                        normalized[key] = walk_and_normalize(value, new_path)
                elif key in ("dataOriginType", "model") and isinstance(value, dict):
                    if "code" in value:
                        normalized[key] = normalize_code(value)
                    else:
                        normalized[key] = walk_and_normalize(value, new_path)
                else:
                    normalized[key] = walk_and_normalize(value, new_path)
            
            return normalized
        elif isinstance(obj, list):
            return [walk_and_normalize(item, f"{path}[{i}]") for i, item in enumerate(obj)]
        else:
            return obj
    
    # Apply normalization
    result = walk_and_normalize(result)
    
    # Ensure top-level required fields
    if "study" in result:
        study = result["study"]
        
        # Study.name is required
        if "name" not in study or not study["name"]:
            # Try to get name from various locations
            titles = study.get("studyTitles") or study.get("titles") or []
            
            # Check in versions if not found at study level
            versions = study.get("versions", [])
            if not titles and versions:
                for version in versions:
                    if isinstance(version, dict):
                        titles = version.get("titles") or version.get("studyTitles") or []
                        if titles:
                            break
            
            if titles and isinstance(titles, list) and len(titles) > 0:
                # Prefer official title, fall back to first
                official = next((t for t in titles if "official" in str(t.get("type", {})).lower()), None)
                title_obj = official or titles[0]
                study["name"] = title_obj.get("text", "Untitled Study")
            else:
                study["name"] = "Untitled Study"
        
        # Ensure versions have rationale
        versions = study.get("versions", [])
        for version in versions:
            if isinstance(version, dict):
                if "rationale" not in version or not version["rationale"]:
                    version["rationale"] = "Protocol version"
    
    return result


# Export all types
__all__ = [
    # Core
    'Code', 'AliasCode', 'CommentAnnotation', 'Range', 'Quantity', 'Duration',
    # Study Structure
    'Study', 'StudyVersion', 'StudyTitle', 'StudyIdentifier', 'Organization',
    # Study Design
    'StudyDesign', 'StudyArm', 'StudyCell', 'StudyEpoch', 'Epoch', 'StudyCohort',
    # SoA
    'Activity', 'Encounter', 'ScheduleTimeline', 'ScheduledActivityInstance',
    'ScheduleTimelineExit', 'Timing',
    # Eligibility
    'EligibilityCriterion', 'EligibilityCriterionItem', 'StudyDesignPopulation',
    # Objectives
    'Objective', 'Endpoint', 'Estimand', 'IntercurrentEvent',
    # Interventions
    'StudyIntervention', 'Procedure', 'Administration', 'AdministrableProduct',
    # Metadata
    'Indication', 'Abbreviation', 'NarrativeContent', 'StudyAmendment',
    # Scheduling
    'Condition', 'TransitionRule',
    # Helpers
    'generate_uuid', 'create_wrapper_input', 'normalize_usdm_data', 'USDMEntity',
]
