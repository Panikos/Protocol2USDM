"""
USDM v4.0 Type Definitions - Comprehensive dataclasses aligned with OpenAPI schema.

This module provides the canonical Python types for all USDM v4.0 entities.
Entity names, field names, and structures match the official USDM_API.json spec.

Organized by domain:
1. Core Types (Code, Range, Duration)
2. Study Structure (Study, StudyVersion, StudyDesign)
3. Metadata (StudyTitle, StudyIdentifier, Organization)
4. Schedule of Activities (Activity, Encounter, ScheduleTimeline)
5. Eligibility (EligibilityCriterion, StudyDesignPopulation)
6. Objectives & Endpoints (Objective, Endpoint, Estimand)
7. Interventions (StudyIntervention, AdministrableProduct)
8. Narrative (NarrativeContent, Abbreviation)
9. Scheduling Logic (Timing, Condition, TransitionRule)

Usage:
    from core.usdm_types_v4 import Study, Activity, ScheduleTimeline
    
    study = Study(id="study_1", name="My Protocol")
    activity = Activity(id="act_1", name="Informed Consent")
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Union
from enum import Enum
from abc import ABC
import uuid


def generate_uuid() -> str:
    """Generate a valid UUID string for USDM entity IDs."""
    return str(uuid.uuid4())


# =============================================================================
# BASE CLASSES & MIXINS
# =============================================================================

class USDMEntity(ABC):
    """Base class for all USDM entities with common methods."""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict, excluding None values."""
        result = {}
        for k, v in asdict(self).items():
            if v is not None:
                if isinstance(v, Enum):
                    result[k] = v.value
                elif isinstance(v, list):
                    result[k] = [
                        item.to_dict() if hasattr(item, 'to_dict') else item 
                        for item in v
                    ] if v else []
                elif hasattr(v, 'to_dict'):
                    result[k] = v.to_dict()
                else:
                    result[k] = v
        return result


# =============================================================================
# 1. CORE TYPES
# =============================================================================

@dataclass
class Code:
    """
    USDM Code - coded value with terminology reference.
    
    OpenAPI: Code-Input
    Required: id, code, codeSystem, codeSystemVersion, decode, instanceType
    """
    code: str
    decode: Optional[str] = None
    codeSystem: str = "http://www.cdisc.org"
    codeSystemVersion: str = "2024-09-27"
    id: Optional[str] = None
    instanceType: str = "Code"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "code": self.code,
            "codeSystem": self.codeSystem,
            "codeSystemVersion": self.codeSystemVersion,
            "instanceType": self.instanceType,
        }
        # Generate UUID if not provided
        if self.id:
            result["id"] = self.id
        else:
            result["id"] = generate_uuid()
        if self.decode:
            result["decode"] = self.decode
        return result
    
    @classmethod
    def from_dict(cls, data: Optional[Dict]) -> Optional['Code']:
        if not data:
            return None
        return cls(
            code=data.get('code', ''),
            codeSystem=data.get('codeSystem'),
            codeSystemVersion=data.get('codeSystemVersion'),
            decode=data.get('decode'),
        )
    
    @classmethod
    def make(cls, code: str, decode: str, system: str = "http://www.cdisc.org", version: str = "2024-09-27") -> 'Code':
        """Factory method for quick Code creation with all required fields."""
        return cls(code=code, decode=decode, codeSystem=system, codeSystemVersion=version)


@dataclass
class AliasCode:
    """
    USDM AliasCode - aliased code with standard code reference.
    
    OpenAPI: AliasCode-Input
    Required: id, standardCode, instanceType
    
    Used for fields like blindingSchema that require both an ID and a standard code.
    """
    id: Optional[str] = None
    standardCode: Optional[Code] = None
    standardCodeAliases: List[Code] = field(default_factory=list)
    instanceType: str = "AliasCode"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id or generate_uuid(),
            "instanceType": self.instanceType,
        }
        if self.standardCode:
            result["standardCode"] = self.standardCode.to_dict()
        else:
            # Default standard code
            result["standardCode"] = Code.make("C49656", "Open Label").to_dict()
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
class Range:
    """
    USDM Range - numeric range (for enrollment, age, etc.).
    
    OpenAPI: Range-Input
    """
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
class Duration:
    """
    USDM Duration - ISO 8601 duration.
    
    OpenAPI: Duration-Input
    """
    value: str  # ISO 8601 format, e.g., "P12W" = 12 weeks
    description: Optional[str] = None
    instanceType: str = "Duration"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"value": self.value, "instanceType": self.instanceType}
        if self.description:
            result["description"] = self.description
        return result


@dataclass
class Quantity:
    """
    USDM Quantity - value with unit.
    
    OpenAPI: Quantity-Input
    """
    value: float
    unit: Optional[Code] = None
    instanceType: str = "Quantity"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"value": self.value, "instanceType": self.instanceType}
        if self.unit:
            result["unit"] = self.unit.to_dict()
        return result


@dataclass
class CommentAnnotation:
    """
    USDM CommentAnnotation - note or comment attached to an entity.
    
    OpenAPI: CommentAnnotation-Input
    Used for: SoA footnotes in StudyDesign.notes
    """
    id: str
    text: str
    codes: List[Code] = field(default_factory=list)
    instanceType: str = "CommentAnnotation"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "text": self.text,
            "instanceType": self.instanceType
        }
        if self.codes:
            result["codes"] = [c.to_dict() for c in self.codes]
        return result
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CommentAnnotation':
        return cls(
            id=data.get('id', ''),
            text=data.get('text', ''),
            codes=[Code.from_dict(c) for c in data.get('codes', [])],
            instanceType=data.get('instanceType', 'CommentAnnotation'),
        )


# =============================================================================
# 2. STUDY STRUCTURE
# =============================================================================

@dataclass
class Study:
    """
    USDM Study - root entity.
    
    OpenAPI: Study-Input
    Required: name, instanceType
    """
    id: Optional[str] = None
    name: str = ""
    description: Optional[str] = None
    label: Optional[str] = None
    instanceType: str = "Study"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"name": self.name, "instanceType": self.instanceType}
        if self.id:
            result["id"] = self.id
        if self.description:
            result["description"] = self.description
        if self.label:
            result["label"] = self.label
        return result


@dataclass
class StudyVersion:
    """
    USDM StudyVersion - versioned protocol content.
    
    OpenAPI: StudyVersion-Input
    Required: id, versionIdentifier, rationale, titles, studyIdentifiers, instanceType
    """
    id: str
    versionIdentifier: str
    rationale: str = ""
    titles: List['StudyTitle'] = field(default_factory=list)
    studyIdentifiers: List['StudyIdentifier'] = field(default_factory=list)
    studyDesigns: List['StudyDesign'] = field(default_factory=list)
    studyPhase: Optional[Code] = None
    instanceType: str = "StudyVersion"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "versionIdentifier": self.versionIdentifier,
            "rationale": self.rationale,
            "titles": [t.to_dict() for t in self.titles],
            "studyIdentifiers": [s.to_dict() for s in self.studyIdentifiers],
            "instanceType": self.instanceType,
        }
        if self.studyDesigns:
            result["studyDesigns"] = [sd.to_dict() for sd in self.studyDesigns]
        if self.studyPhase:
            result["studyPhase"] = self.studyPhase.to_dict()
        return result


@dataclass
class StudyDesign:
    """
    USDM StudyDesign - interventional or observational study design.
    
    OpenAPI: InterventionalStudyDesign-Input / ObservationalStudyDesign-Input
    Required: id, name, arms, studyCells, rationale, epochs, population, eligibilityCriteria, model, instanceType
    """
    id: str
    name: str = "Study Design"  # Required
    description: Optional[str] = None
    rationale: str = "Protocol-defined study design"  # Required
    instanceType: str = "InterventionalStudyDesign"  # or ObservationalStudyDesign
    
    # Design characteristics
    blindingSchema: Optional[AliasCode] = None  # Required for InterventionalStudyDesign
    model: Optional[Code] = None  # Required - study model (parallel, crossover, etc.)
    
    # Study structure - note: property name is 'arms' in schema, not 'studyArms'
    arms: List['StudyArm'] = field(default_factory=list)
    studyCells: List['StudyCell'] = field(default_factory=list)
    studyCohorts: List['StudyCohort'] = field(default_factory=list)
    
    # SoA entities
    activities: List['Activity'] = field(default_factory=list)
    encounters: List['Encounter'] = field(default_factory=list)
    epochs: List['StudyEpoch'] = field(default_factory=list)
    scheduleTimelines: List['ScheduleTimeline'] = field(default_factory=list)
    
    # Eligibility - note: property name is 'population' in schema, not 'studyDesignPopulation'
    eligibilityCriteria: List['EligibilityCriterion'] = field(default_factory=list)
    population: Optional['StudyDesignPopulation'] = None
    
    # Objectives
    objectives: List['Objective'] = field(default_factory=list)
    endpoints: List['Endpoint'] = field(default_factory=list)
    estimands: List['Estimand'] = field(default_factory=list)
    
    # Interventions
    studyInterventions: List['StudyIntervention'] = field(default_factory=list)
    
    # Notes (for SoA footnotes)
    notes: List[CommentAnnotation] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id, 
            "name": self.name,
            "rationale": self.rationale,
            "instanceType": self.instanceType,
        }
        
        if self.description:
            result["description"] = self.description
        
        # blindingSchema is required for InterventionalStudyDesign
        if self.instanceType == "InterventionalStudyDesign":
            if self.blindingSchema:
                result["blindingSchema"] = self.blindingSchema.to_dict()
            else:
                result["blindingSchema"] = AliasCode.make_blinding("open").to_dict()
        
        # Model - required, default to parallel if multiple arms
        if self.model:
            result["model"] = self.model.to_dict()
        else:
            # Default model based on arm count
            if len(self.arms) >= 2:
                result["model"] = Code(code="C82639", decode="Parallel Study").to_dict()
            else:
                result["model"] = Code(code="C82638", decode="Single Group Study").to_dict()
            
        # Arrays - use correct schema property names
        if self.arms:
            result["arms"] = [a.to_dict() for a in self.arms]  # NOT studyArms
        if self.studyCells:
            result["studyCells"] = [c.to_dict() for c in self.studyCells]
        if self.studyCohorts:
            result["studyCohorts"] = [c.to_dict() for c in self.studyCohorts]
        if self.activities:
            result["activities"] = [a.to_dict() for a in self.activities]
        if self.encounters:
            result["encounters"] = [e.to_dict() for e in self.encounters]
        if self.epochs:
            result["epochs"] = [e.to_dict() for e in self.epochs]
        if self.scheduleTimelines:
            result["scheduleTimelines"] = [s.to_dict() for s in self.scheduleTimelines]
        if self.eligibilityCriteria:
            result["eligibilityCriteria"] = [e.to_dict() for e in self.eligibilityCriteria]
        if self.population:
            result["population"] = self.population.to_dict()  # NOT studyDesignPopulation
        if self.objectives:
            result["objectives"] = [o.to_dict() for o in self.objectives]
        if self.endpoints:
            result["endpoints"] = [e.to_dict() for e in self.endpoints]
        if self.estimands:
            result["estimands"] = [e.to_dict() for e in self.estimands]
        if self.studyInterventions:
            result["studyInterventions"] = [i.to_dict() for i in self.studyInterventions]
        if self.notes:
            result["notes"] = [n.to_dict() for n in self.notes]
            
        return result


@dataclass
class StudyArm:
    """
    USDM StudyArm - treatment arm.
    
    OpenAPI: StudyArm-Input
    Required: id, name, type, dataOriginDescription, dataOriginType, instanceType
    """
    id: str
    name: str
    description: Optional[str] = None
    type: Optional[Code] = None
    dataOriginDescription: Optional[str] = None
    dataOriginType: Optional[Code] = None
    instanceType: str = "StudyArm"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"id": self.id, "name": self.name, "instanceType": self.instanceType}
        if self.description:
            result["description"] = self.description
        # Type is required - provide default based on arm name
        if self.type:
            result["type"] = self.type.to_dict()
        else:
            name_lower = self.name.lower()
            if 'placebo' in name_lower:
                result["type"] = Code.make("C49648", "Placebo Comparator Arm").to_dict()
            elif 'active' in name_lower or 'comparator' in name_lower:
                result["type"] = Code.make("C49647", "Active Comparator Arm").to_dict()
            elif 'control' in name_lower:
                result["type"] = Code.make("C174266", "No Intervention Arm").to_dict()
            else:
                result["type"] = Code.make("C174267", "Experimental Arm").to_dict()
        # dataOriginDescription is required
        result["dataOriginDescription"] = self.dataOriginDescription or "Collected"
        # dataOriginType is required
        if self.dataOriginType:
            result["dataOriginType"] = self.dataOriginType.to_dict()
        else:
            result["dataOriginType"] = Code.make("C70793", "Collected").to_dict()
        return result


@dataclass
class StudyCell:
    """
    USDM StudyCell - intersection of arm and epoch.
    
    OpenAPI: StudyCell-Input
    """
    id: str
    armId: str
    epochId: str
    instanceType: str = "StudyCell"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "armId": self.armId,
            "epochId": self.epochId,
            "instanceType": self.instanceType,
        }


@dataclass
class StudyCohort:
    """
    USDM StudyCohort - patient cohort.
    
    OpenAPI: StudyCohort-Input
    """
    id: str
    name: str
    description: Optional[str] = None
    instanceType: str = "StudyCohort"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"id": self.id, "name": self.name, "instanceType": self.instanceType}
        if self.description:
            result["description"] = self.description
        return result


# =============================================================================
# 3. METADATA ENTITIES
# =============================================================================

@dataclass
class StudyTitle:
    """
    USDM StudyTitle - study title with type.
    
    OpenAPI: StudyTitle-Input
    Required: id, text, type, instanceType
    """
    id: str
    text: str
    type: Code
    instanceType: str = "StudyTitle"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "type": self.type.to_dict(),
            "instanceType": self.instanceType,
        }


@dataclass
class StudyIdentifier:
    """
    USDM StudyIdentifier - registry/sponsor ID.
    
    OpenAPI: StudyIdentifier-Input
    Required: id, text, instanceType
    """
    id: str
    text: str
    scopeId: Optional[str] = None  # Reference to Organization
    instanceType: str = "StudyIdentifier"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"id": self.id, "text": self.text, "instanceType": self.instanceType}
        if self.scopeId:
            result["scopeId"] = self.scopeId
        return result


@dataclass
class Organization:
    """
    USDM Organization - company/institution.
    
    OpenAPI: Organization-Input
    Required: id, name, instanceType
    """
    id: str
    name: str
    type: Optional[Code] = None
    identifier: Optional[str] = None
    identifierScheme: Optional[str] = None
    instanceType: str = "Organization"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"id": self.id, "name": self.name, "instanceType": self.instanceType}
        if self.type:
            result["type"] = self.type.to_dict()
        if self.identifier:
            result["identifier"] = self.identifier
            if self.identifierScheme:
                result["identifierScheme"] = self.identifierScheme
        return result


@dataclass
class Indication:
    """
    USDM Indication - disease/condition.
    
    OpenAPI: Indication-Input
    """
    id: str
    name: str
    description: Optional[str] = None
    codes: List[Code] = field(default_factory=list)
    instanceType: str = "Indication"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"id": self.id, "name": self.name, "instanceType": self.instanceType}
        if self.description:
            result["description"] = self.description
        if self.codes:
            result["codes"] = [c.to_dict() for c in self.codes]
        return result


# =============================================================================
# 4. SCHEDULE OF ACTIVITIES ENTITIES
# =============================================================================

@dataclass
class Activity:
    """
    USDM Activity - a procedure or assessment.
    
    OpenAPI: Activity-Input
    Required: id, name, instanceType
    
    Note: activityGroupId is an internal field used during extraction to link
    activities to their parent groups. It gets converted to childIds on the
    parent Activity in the final output.
    """
    id: str
    name: str
    description: Optional[str] = None
    label: Optional[str] = None
    previousId: Optional[str] = None
    nextId: Optional[str] = None
    childIds: List[str] = field(default_factory=list)
    biomedicalConceptIds: List[str] = field(default_factory=list)
    definedProcedures: List['Procedure'] = field(default_factory=list)
    timelineId: Optional[str] = None
    activityGroupId: Optional[str] = None  # Internal: links to parent group during extraction
    instanceType: str = "Activity"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"id": self.id, "name": self.name, "instanceType": self.instanceType}
        if self.description:
            result["description"] = self.description
        if self.label:
            result["label"] = self.label
        if self.previousId:
            result["previousId"] = self.previousId
        if self.nextId:
            result["nextId"] = self.nextId
        if self.childIds:
            result["childIds"] = self.childIds
        if self.biomedicalConceptIds:
            result["biomedicalConceptIds"] = self.biomedicalConceptIds
        if self.definedProcedures:
            result["definedProcedures"] = [p.to_dict() for p in self.definedProcedures]
        if self.timelineId:
            result["timelineId"] = self.timelineId
        if self.activityGroupId:
            result["activityGroupId"] = self.activityGroupId  # Keep for viewer compatibility
        return result
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Activity':
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            description=data.get('description'),
            label=data.get('label'),
            previousId=data.get('previousId'),
            nextId=data.get('nextId'),
            childIds=data.get('childIds', []),
            biomedicalConceptIds=data.get('biomedicalConceptIds', []),
            timelineId=data.get('timelineId'),
            activityGroupId=data.get('activityGroupId'),
            instanceType=data.get('instanceType', 'Activity'),
        )


@dataclass
class Encounter:
    """
    USDM Encounter - a study visit.
    
    OpenAPI: Encounter-Input
    Required: id, name, instanceType
    """
    id: str
    name: str
    description: Optional[str] = None
    label: Optional[str] = None
    type: Optional[Code] = None
    epochId: Optional[str] = None
    scheduledAtTimingId: Optional[str] = None
    instanceType: str = "Encounter"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"id": self.id, "name": self.name, "instanceType": self.instanceType}
        if self.description:
            result["description"] = self.description
        if self.label:
            result["label"] = self.label
        # Type is required - provide default if not set
        if self.type:
            result["type"] = self.type.to_dict()
        else:
            # Infer type from encounter name - use Code.make() for all required fields
            name_lower = self.name.lower()
            if 'screen' in name_lower:
                result["type"] = Code.make("C48262", "Screening").to_dict()
            elif 'baseline' in name_lower or 'day 1' in name_lower or 'day1' in name_lower:
                result["type"] = Code.make("C82517", "Baseline").to_dict()
            elif 'follow' in name_lower:
                result["type"] = Code.make("C99158", "Follow-up").to_dict()
            elif 'end' in name_lower or 'eos' in name_lower or 'completion' in name_lower:
                result["type"] = Code.make("C126070", "End of Study").to_dict()
            elif 'early' in name_lower or 'discontin' in name_lower or 'termination' in name_lower:
                result["type"] = Code.make("C49631", "Early Termination").to_dict()
            elif 'unscheduled' in name_lower:
                result["type"] = Code.make("C99157", "Unscheduled").to_dict()
            else:
                result["type"] = Code.make("C99156", "Scheduled Visit").to_dict()
        if self.epochId:
            result["epochId"] = self.epochId
        if self.scheduledAtTimingId:
            result["scheduledAtTimingId"] = self.scheduledAtTimingId
        return result
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Encounter':
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            description=data.get('description'),
            label=data.get('label'),
            type=Code.from_dict(data.get('type')),
            epochId=data.get('epochId'),
            scheduledAtTimingId=data.get('scheduledAtTimingId'),
            instanceType=data.get('instanceType', 'Encounter'),
        )


@dataclass
class StudyEpoch:
    """
    USDM StudyEpoch - a study phase/period.
    
    OpenAPI: StudyEpoch-Input
    Required: id, name, instanceType
    
    Note: This replaces the old "Epoch" class to match USDM naming.
    """
    id: str
    name: str
    description: Optional[str] = None
    label: Optional[str] = None
    type: Optional[Code] = None
    previousId: Optional[str] = None
    nextId: Optional[str] = None
    instanceType: str = "StudyEpoch"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"id": self.id, "name": self.name, "instanceType": self.instanceType}
        if self.description:
            result["description"] = self.description
        if self.label:
            result["label"] = self.label
        # Type is required - provide default based on epoch name
        if self.type:
            result["type"] = self.type.to_dict()
        else:
            name_lower = self.name.lower()
            if 'screen' in name_lower:
                result["type"] = Code.make("C98779", "Screening Epoch").to_dict()
            elif 'treatment' in name_lower or 'intervention' in name_lower:
                result["type"] = Code.make("C98780", "Treatment Epoch").to_dict()
            elif 'follow' in name_lower:
                result["type"] = Code.make("C98781", "Follow-up Epoch").to_dict()
            elif 'run-in' in name_lower or 'runin' in name_lower or 'washout' in name_lower:
                result["type"] = Code.make("C98782", "Run-in Epoch").to_dict()
            else:
                result["type"] = Code.make("C98780", "Treatment Epoch").to_dict()
        if self.previousId:
            result["previousId"] = self.previousId
        if self.nextId:
            result["nextId"] = self.nextId
        return result
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'StudyEpoch':
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            description=data.get('description'),
            label=data.get('label'),
            type=Code.from_dict(data.get('type')),
            previousId=data.get('previousId'),
            nextId=data.get('nextId'),
            instanceType=data.get('instanceType', 'StudyEpoch'),
        )


# Backward compatibility alias
Epoch = StudyEpoch


@dataclass
class ScheduleTimeline:
    """
    USDM ScheduleTimeline - contains scheduled instances.
    
    OpenAPI: ScheduleTimeline-Input
    Required: id, name, entryCondition, entryId, instanceType
    """
    id: str
    name: str
    description: Optional[str] = None
    label: Optional[str] = None
    mainTimeline: bool = True
    entryCondition: Optional[str] = None  # Required - entry condition text
    entryId: Optional[str] = None  # Required - reference to entry point
    instances: List['ScheduledActivityInstance'] = field(default_factory=list)
    exits: List['ScheduleTimelineExit'] = field(default_factory=list)
    instanceType: str = "ScheduleTimeline"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "mainTimeline": self.mainTimeline,
            "instanceType": self.instanceType,
        }
        if self.description:
            result["description"] = self.description
        if self.label:
            result["label"] = self.label
        # entryCondition is required - provide default
        result["entryCondition"] = self.entryCondition or "Subject enrolled in study"
        # entryId is required - reference to first instance or generate UUID
        if self.entryId:
            result["entryId"] = self.entryId
        elif self.instances:
            result["entryId"] = self.instances[0].id
        else:
            result["entryId"] = generate_uuid()
        if self.instances:
            result["instances"] = [i.to_dict() for i in self.instances]
        if self.exits:
            result["exits"] = [e.to_dict() for e in self.exits]
        return result


@dataclass
class ScheduledActivityInstance:
    """
    USDM ScheduledActivityInstance - activity scheduled at a timepoint.
    
    OpenAPI: ScheduledActivityInstance-Input
    Required: id, name, instanceType
    
    Note: This replaces the old "ActivityTimepoint" concept.
    """
    id: str
    activityId: str
    name: Optional[str] = None  # Required - will auto-generate if not provided
    epochId: Optional[str] = None
    encounterId: Optional[str] = None
    timingId: Optional[str] = None
    timelineId: Optional[str] = None
    defaultConditionId: Optional[str] = None
    instanceType: str = "ScheduledActivityInstance"
    
    def to_dict(self) -> Dict[str, Any]:
        # Generate name if not provided
        instance_name = self.name
        if not instance_name:
            instance_name = f"{self.activityId}@{self.encounterId or 'schedule'}"
        
        result = {
            "id": self.id,
            "name": instance_name,  # Required field
            "activityId": self.activityId,
            "instanceType": self.instanceType,
        }
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
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ScheduledActivityInstance':
        return cls(
            id=data.get('id', ''),
            activityId=data.get('activityId', ''),
            epochId=data.get('epochId'),
            encounterId=data.get('encounterId'),
            timingId=data.get('timingId'),
            timelineId=data.get('timelineId'),
            defaultConditionId=data.get('defaultConditionId'),
            instanceType=data.get('instanceType', 'ScheduledActivityInstance'),
        )


@dataclass
class ScheduleTimelineExit:
    """
    USDM ScheduleTimelineExit - exit criteria for timeline.
    
    OpenAPI: ScheduleTimelineExit-Input
    """
    id: str
    name: str
    description: Optional[str] = None
    conditionId: Optional[str] = None
    instanceType: str = "ScheduleTimelineExit"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"id": self.id, "name": self.name, "instanceType": self.instanceType}
        if self.description:
            result["description"] = self.description
        if self.conditionId:
            result["conditionId"] = self.conditionId
        return result


@dataclass
class Timing:
    """
    USDM Timing - timing constraint.
    
    OpenAPI: Timing-Input
    """
    id: str
    name: str
    description: Optional[str] = None
    label: Optional[str] = None
    type: Optional[Code] = None
    value: Optional[str] = None  # ISO 8601 duration
    valueLabel: Optional[str] = None
    relativeToFrom: Optional[Code] = None
    relativeFromScheduledInstanceId: Optional[str] = None
    windowLower: Optional[str] = None
    windowUpper: Optional[str] = None
    instanceType: str = "Timing"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"id": self.id, "name": self.name, "instanceType": self.instanceType}
        if self.description:
            result["description"] = self.description
        if self.label:
            result["label"] = self.label
        if self.type:
            result["type"] = self.type.to_dict()
        if self.value:
            result["value"] = self.value
        if self.valueLabel:
            result["valueLabel"] = self.valueLabel
        if self.relativeToFrom:
            result["relativeToFrom"] = self.relativeToFrom.to_dict()
        if self.relativeFromScheduledInstanceId:
            result["relativeFromScheduledInstanceId"] = self.relativeFromScheduledInstanceId
        if self.windowLower:
            result["windowLower"] = self.windowLower
        if self.windowUpper:
            result["windowUpper"] = self.windowUpper
        return result


# =============================================================================
# 5. ELIGIBILITY ENTITIES
# =============================================================================

@dataclass
class EligibilityCriterion:
    """
    USDM EligibilityCriterion - inclusion/exclusion criterion.
    
    OpenAPI: EligibilityCriterion-Input
    Required: id, name, category, identifier, criterionItemId, instanceType
    """
    id: str
    name: str
    category: Code  # Inclusion/Exclusion
    identifier: str  # I1, E1, etc.
    criterionItemId: str
    description: Optional[str] = None
    label: Optional[str] = None
    previousId: Optional[str] = None
    nextId: Optional[str] = None
    instanceType: str = "EligibilityCriterion"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "category": self.category.to_dict(),
            "identifier": self.identifier,
            "criterionItemId": self.criterionItemId,
            "instanceType": self.instanceType,
        }
        if self.description:
            result["description"] = self.description
        if self.label:
            result["label"] = self.label
        if self.previousId:
            result["previousId"] = self.previousId
        if self.nextId:
            result["nextId"] = self.nextId
        return result


@dataclass
class EligibilityCriterionItem:
    """
    USDM EligibilityCriterionItem - the actual criterion text.
    
    OpenAPI: EligibilityCriterionItem-Input  
    Required: id, name, text, instanceType
    """
    id: str
    name: str
    text: str
    description: Optional[str] = None
    dictionaryId: Optional[str] = None
    instanceType: str = "EligibilityCriterionItem"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "text": self.text,
            "instanceType": self.instanceType,
        }
        if self.description:
            result["description"] = self.description
        if self.dictionaryId:
            result["dictionaryId"] = self.dictionaryId
        return result


@dataclass
class StudyDesignPopulation:
    """
    USDM StudyDesignPopulation - target population.
    
    OpenAPI: StudyDesignPopulation-Input
    """
    id: str
    name: str
    description: Optional[str] = None
    includesHealthySubjects: bool = False
    plannedEnrollmentNumber: Optional[Range] = None
    plannedMinimumAge: Optional[str] = None  # ISO 8601: P18Y
    plannedMaximumAge: Optional[str] = None
    plannedSex: List[Code] = field(default_factory=list)
    criterionIds: List[str] = field(default_factory=list)
    instanceType: str = "StudyDesignPopulation"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "includesHealthySubjects": self.includesHealthySubjects,
            "instanceType": self.instanceType,
        }
        if self.description:
            result["description"] = self.description
        if self.plannedEnrollmentNumber:
            result["plannedEnrollmentNumber"] = self.plannedEnrollmentNumber.to_dict()
        if self.plannedMinimumAge:
            result["plannedMinimumAge"] = self.plannedMinimumAge
        if self.plannedMaximumAge:
            result["plannedMaximumAge"] = self.plannedMaximumAge
        if self.plannedSex:
            result["plannedSex"] = [s.to_dict() for s in self.plannedSex]
        if self.criterionIds:
            result["criterionIds"] = self.criterionIds
        return result


# =============================================================================
# 6. OBJECTIVES & ENDPOINTS
# =============================================================================

@dataclass
class Objective:
    """
    USDM Objective - study objective.
    
    OpenAPI: Objective-Input
    Required: id, text, level, instanceType
    """
    id: str
    text: str
    level: Code  # Primary/Secondary/Exploratory
    name: Optional[str] = None
    description: Optional[str] = None
    endpointIds: List[str] = field(default_factory=list)
    instanceType: str = "Objective"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "text": self.text,
            "level": self.level.to_dict(),
            "instanceType": self.instanceType,
        }
        if self.name:
            result["name"] = self.name
        if self.description:
            result["description"] = self.description
        if self.endpointIds:
            result["endpointIds"] = self.endpointIds
        return result


@dataclass
class Endpoint:
    """
    USDM Endpoint - study endpoint.
    
    OpenAPI: Endpoint-Input
    Required: id, text, level, instanceType
    """
    id: str
    text: str
    level: Code  # Primary/Secondary/Exploratory
    name: Optional[str] = None
    description: Optional[str] = None
    purpose: Optional[str] = None
    instanceType: str = "Endpoint"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "text": self.text,
            "level": self.level.to_dict(),
            "instanceType": self.instanceType,
        }
        if self.name:
            result["name"] = self.name
        if self.description:
            result["description"] = self.description
        if self.purpose:
            result["purpose"] = self.purpose
        return result


@dataclass
class Estimand:
    """
    USDM Estimand - ICH E9(R1) estimand.
    
    OpenAPI: Estimand-Input
    """
    id: str
    name: str
    text: Optional[str] = None
    description: Optional[str] = None
    intercurrentEvents: List['IntercurrentEvent'] = field(default_factory=list)
    instanceType: str = "Estimand"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"id": self.id, "name": self.name, "instanceType": self.instanceType}
        if self.text:
            result["text"] = self.text
        if self.description:
            result["description"] = self.description
        if self.intercurrentEvents:
            result["intercurrentEvents"] = [e.to_dict() for e in self.intercurrentEvents]
        return result


@dataclass
class IntercurrentEvent:
    """
    USDM IntercurrentEvent - event affecting estimand.
    
    OpenAPI: IntercurrentEvent-Input
    """
    id: str
    name: str
    description: Optional[str] = None
    strategy: Optional[Code] = None
    instanceType: str = "IntercurrentEvent"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"id": self.id, "name": self.name, "instanceType": self.instanceType}
        if self.description:
            result["description"] = self.description
        if self.strategy:
            result["strategy"] = self.strategy.to_dict()
        return result


# =============================================================================
# 7. INTERVENTION ENTITIES
# =============================================================================

@dataclass
class StudyIntervention:
    """
    USDM StudyIntervention - treatment/comparator.
    
    OpenAPI: StudyIntervention-Input
    Required: id, name, instanceType
    """
    id: str
    name: str
    description: Optional[str] = None
    type: Optional[Code] = None
    productIds: List[str] = field(default_factory=list)
    instanceType: str = "StudyIntervention"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"id": self.id, "name": self.name, "instanceType": self.instanceType}
        if self.description:
            result["description"] = self.description
        if self.type:
            result["type"] = self.type.to_dict()
        if self.productIds:
            result["productIds"] = self.productIds
        return result


@dataclass
class AdministrableProduct:
    """
    USDM AdministrableProduct - drug product.
    
    OpenAPI: AdministrableProduct-Input
    """
    id: str
    name: str
    description: Optional[str] = None
    instanceType: str = "AdministrableProduct"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"id": self.id, "name": self.name, "instanceType": self.instanceType}
        if self.description:
            result["description"] = self.description
        return result


@dataclass
class Administration:
    """
    USDM Administration - dosing administration.
    
    OpenAPI: Administration-Input
    """
    id: str
    name: str
    description: Optional[str] = None
    route: Optional[Code] = None
    frequency: Optional[Code] = None
    duration: Optional[Duration] = None
    instanceType: str = "Administration"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"id": self.id, "name": self.name, "instanceType": self.instanceType}
        if self.description:
            result["description"] = self.description
        if self.route:
            result["route"] = self.route.to_dict()
        if self.frequency:
            result["frequency"] = self.frequency.to_dict()
        if self.duration:
            result["duration"] = self.duration.to_dict()
        return result


@dataclass
class Procedure:
    """
    USDM Procedure - medical procedure.
    
    OpenAPI: Procedure-Input
    """
    id: str
    name: str
    description: Optional[str] = None
    code: Optional[Code] = None
    instanceType: str = "Procedure"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"id": self.id, "name": self.name, "instanceType": self.instanceType}
        if self.description:
            result["description"] = self.description
        if self.code:
            result["code"] = self.code.to_dict()
        return result


# =============================================================================
# 8. NARRATIVE ENTITIES
# =============================================================================

@dataclass
class NarrativeContent:
    """
    USDM NarrativeContent - protocol text section.
    
    OpenAPI: NarrativeContent-Input
    """
    id: str
    name: str
    text: Optional[str] = None
    sectionNumber: Optional[str] = None
    sectionTitle: Optional[str] = None
    instanceType: str = "NarrativeContent"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"id": self.id, "name": self.name, "instanceType": self.instanceType}
        if self.text:
            result["text"] = self.text
        if self.sectionNumber:
            result["sectionNumber"] = self.sectionNumber
        if self.sectionTitle:
            result["sectionTitle"] = self.sectionTitle
        return result


@dataclass
class Abbreviation:
    """
    USDM Abbreviation - abbreviation definition.
    
    OpenAPI: Abbreviation-Input
    Required: id, abbreviatedText, expandedText, instanceType
    """
    id: str
    abbreviatedText: str
    expandedText: str
    instanceType: str = "Abbreviation"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "abbreviatedText": self.abbreviatedText,
            "expandedText": self.expandedText,
            "instanceType": self.instanceType,
        }


@dataclass
class StudyAmendment:
    """
    USDM StudyAmendment - protocol amendment.
    
    OpenAPI: StudyAmendment-Input
    """
    id: str
    number: str
    summary: Optional[str] = None
    description: Optional[str] = None
    instanceType: str = "StudyAmendment"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "number": self.number,
            "instanceType": self.instanceType,
        }
        if self.summary:
            result["summary"] = self.summary
        if self.description:
            result["description"] = self.description
        return result


# =============================================================================
# 9. SCHEDULING LOGIC ENTITIES
# =============================================================================

@dataclass
class Condition:
    """
    USDM Condition - conditional logic.
    
    OpenAPI: Condition-Input
    """
    id: str
    name: str
    description: Optional[str] = None
    text: Optional[str] = None
    contextIds: List[str] = field(default_factory=list)
    appliesToIds: List[str] = field(default_factory=list)
    instanceType: str = "Condition"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"id": self.id, "name": self.name, "instanceType": self.instanceType}
        if self.description:
            result["description"] = self.description
        if self.text:
            result["text"] = self.text
        if self.contextIds:
            result["contextIds"] = self.contextIds
        if self.appliesToIds:
            result["appliesToIds"] = self.appliesToIds
        return result


@dataclass
class TransitionRule:
    """
    USDM TransitionRule - state transition rule.
    
    OpenAPI: TransitionRule-Input
    """
    id: str
    name: str
    description: Optional[str] = None
    text: Optional[str] = None
    instanceType: str = "TransitionRule"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"id": self.id, "name": self.name, "instanceType": self.instanceType}
        if self.description:
            result["description"] = self.description
        if self.text:
            result["text"] = self.text
        return result


# =============================================================================
# 10. BACKWARD COMPATIBILITY - Legacy aliases and containers
# =============================================================================

# These provide backward compatibility with existing code that uses old names

@dataclass
class ActivityTimepoint:
    """
    DEPRECATED: Use ScheduledActivityInstance instead.
    
    This is kept for backward compatibility with existing SoA extraction code.
    Maps to the simplified tick-matrix concept.
    """
    id: str
    activityId: str
    plannedTimepointId: str
    instanceType: str = "ScheduledActivityInstance"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "activityId": self.activityId,
            "encounterId": self.plannedTimepointId,  # Map to encounter for USDM compliance
            "instanceType": self.instanceType,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ActivityTimepoint':
        return cls(
            id=data.get('id', ''),
            activityId=data.get('activityId', ''),
            plannedTimepointId=data.get('plannedTimepointId') or data.get('encounterId', ''),
            instanceType=data.get('instanceType', 'ScheduledActivityInstance'),
        )
    
    def to_scheduled_instance(self) -> ScheduledActivityInstance:
        """Convert to proper USDM ScheduledActivityInstance."""
        return ScheduledActivityInstance(
            id=self.id,
            activityId=self.activityId,
            encounterId=self.plannedTimepointId,
        )


@dataclass
class PlannedTimepoint:
    """
    DEPRECATED: Represents a planned moment in the study schedule.
    
    In USDM v4.0, this concept is handled by Timing + Encounter.
    Kept for backward compatibility with existing SoA extraction code.
    """
    id: str
    name: str
    description: Optional[str] = None
    encounterId: Optional[str] = None
    value: Optional[str] = None
    valueLabel: Optional[str] = None
    instanceType: str = "Timing"  # Maps to Timing in USDM v4.0
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"id": self.id, "name": self.name, "instanceType": self.instanceType}
        if self.description:
            result["description"] = self.description
        if self.encounterId:
            result["encounterId"] = self.encounterId
        if self.value:
            result["value"] = self.value
        if self.valueLabel:
            result["valueLabel"] = self.valueLabel
        return result
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'PlannedTimepoint':
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            description=data.get('description'),
            encounterId=data.get('encounterId'),
            value=data.get('value'),
            valueLabel=data.get('valueLabel'),
            instanceType=data.get('instanceType', 'Timing'),
        )


@dataclass
class ActivityGroup:
    """
    Activity group/category extracted from SoA table row headers.
    
    Gets converted to parent Activity with childIds in the final USDM output.
    Visual properties help verify extraction accuracy.
    """
    id: str
    name: str
    description: Optional[str] = None
    activities: List[str] = field(default_factory=list)
    instanceType: str = "Activity"  # Groups are parent Activities in USDM v4.0
    
    # Visual properties for verification
    isBold: bool = False
    hasMergedCells: bool = False
    spansFullWidth: bool = False
    visualConfidence: float = 1.0  # 0-1 confidence this is truly a group header
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"id": self.id, "name": self.name, "instanceType": self.instanceType}
        if self.description:
            result["description"] = self.description
        if self.activities:
            result["childIds"] = self.activities  # Map to childIds
        # Include visual properties for debugging/verification
        result["_visual"] = {
            "isBold": self.isBold,
            "hasMergedCells": self.hasMergedCells,
            "spansFullWidth": self.spansFullWidth,
            "confidence": self.visualConfidence,
        }
        return result
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ActivityGroup':
        visual = data.get('_visual', data.get('visual', {}))
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            description=data.get('description'),
            activities=data.get('activities', data.get('childIds', [])),
            instanceType=data.get('instanceType', 'Activity'),
            isBold=visual.get('isBold', data.get('isBold', False)),
            hasMergedCells=visual.get('hasMergedCells', data.get('hasMergedCells', False)),
            spansFullWidth=visual.get('spansFullWidth', data.get('spansFullWidth', False)),
            visualConfidence=visual.get('confidence', data.get('visualConfidence', 1.0)),
        )


# =============================================================================
# 11. CONTAINER CLASSES
# =============================================================================

@dataclass
class HeaderStructure:
    """
    Container for SoA header structure extracted by vision analysis.
    
    This is an internal type (not in USDM) used during extraction.
    """
    epochs: List[StudyEpoch] = field(default_factory=list)
    encounters: List[Encounter] = field(default_factory=list)
    plannedTimepoints: List[PlannedTimepoint] = field(default_factory=list)
    activityGroups: List[ActivityGroup] = field(default_factory=list)
    footnotes: List[str] = field(default_factory=list)  # SoA table footnotes
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'columnHierarchy': {
                'epochs': [e.to_dict() for e in self.epochs],
                'encounters': [e.to_dict() for e in self.encounters],
                'plannedTimepoints': [pt.to_dict() for pt in self.plannedTimepoints],
            },
            'rowGroups': [g.to_dict() for g in self.activityGroups],
            'footnotes': self.footnotes,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'HeaderStructure':
        col_h = data.get('columnHierarchy', {})
        return cls(
            epochs=[StudyEpoch.from_dict(e) for e in col_h.get('epochs', [])],
            encounters=[Encounter.from_dict(e) for e in col_h.get('encounters', [])],
            plannedTimepoints=[PlannedTimepoint.from_dict(pt) for pt in col_h.get('plannedTimepoints', [])],
            activityGroups=[ActivityGroup.from_dict(g) for g in data.get('rowGroups', [])],
            footnotes=data.get('footnotes', []),
        )
    
    def get_timepoint_ids(self) -> List[str]:
        return [pt.id for pt in self.plannedTimepoints]
    
    def get_encounter_ids(self) -> List[str]:
        return [enc.id for enc in self.encounters]
    
    def get_group_ids(self) -> List[str]:
        return [g.id for g in self.activityGroups]


@dataclass
class Timeline:
    """
    DEPRECATED: Container for SoA data during extraction.
    
    This is an internal type used during extraction. 
    For USDM compliance, convert to StudyDesign structure.
    """
    activities: List[Activity] = field(default_factory=list)
    plannedTimepoints: List[PlannedTimepoint] = field(default_factory=list)
    encounters: List[Encounter] = field(default_factory=list)
    epochs: List[StudyEpoch] = field(default_factory=list)
    activityGroups: List[ActivityGroup] = field(default_factory=list)
    activityTimepoints: List[ActivityTimepoint] = field(default_factory=list)
    footnotes: List[str] = field(default_factory=list)  # SoA table footnotes
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'activities': [a.to_dict() for a in self.activities],
            'plannedTimepoints': [pt.to_dict() for pt in self.plannedTimepoints],
            'encounters': [e.to_dict() for e in self.encounters],
            'epochs': [e.to_dict() for e in self.epochs],
            'activityGroups': [g.to_dict() for g in self.activityGroups],
            'activityTimepoints': [at.to_dict() for at in self.activityTimepoints],
            'footnotes': self.footnotes,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Timeline':
        return cls(
            activities=[Activity.from_dict(a) for a in data.get('activities', [])],
            plannedTimepoints=[PlannedTimepoint.from_dict(pt) for pt in data.get('plannedTimepoints', [])],
            encounters=[Encounter.from_dict(e) for e in data.get('encounters', [])],
            epochs=[StudyEpoch.from_dict(e) for e in data.get('epochs', [])],
            activityGroups=[ActivityGroup.from_dict(g) for g in data.get('activityGroups', [])],
            activityTimepoints=[ActivityTimepoint.from_dict(at) for at in data.get('activityTimepoints', [])],
            footnotes=data.get('footnotes', []),
        )
    
    def to_study_design(self, design_id: str = "sd_1") -> StudyDesign:
        """
        Convert Timeline to proper USDM StudyDesign.
        
        Activity groups are converted to parent Activities with childIds,
        following USDM v4.0 hierarchy pattern.
        """
        # Build combined activities list with proper hierarchy
        all_activities = []
        
        # Convert activity groups to parent Activities with childIds
        if self.activityGroups:
            # Build mapping of group_id -> child activity ids
            group_children = {g.id: [] for g in self.activityGroups}
            
            for act in self.activities:
                # Check if activity has activityGroupId reference
                act_dict = act.to_dict() if hasattr(act, 'to_dict') else act
                group_id = act_dict.get('activityGroupId')
                if group_id and group_id in group_children:
                    group_children[group_id].append(act.id)
            
            # Create parent Activities from groups
            for group in self.activityGroups:
                child_ids = group_children.get(group.id, [])
                parent_activity = Activity(
                    id=group.id,
                    name=group.name,
                    description=group.description,
                    childIds=child_ids,
                    instanceType="Activity",
                )
                all_activities.append(parent_activity)
        
        # Add all regular activities (they already have activityGroupId for linking)
        all_activities.extend(self.activities)
        
        # Convert footnotes to CommentAnnotation objects for USDM v4.0 compliance
        soa_notes = [
            CommentAnnotation(
                id=f"soa_fn_{i+1}",
                text=fn,
            )
            for i, fn in enumerate(self.footnotes)
        ]
        
        return StudyDesign(
            id=design_id,
            activities=all_activities,
            encounters=self.encounters,
            epochs=self.epochs,
            scheduleTimelines=[
                ScheduleTimeline(
                    id="timeline_1",
                    name="Main Schedule Timeline",
                    mainTimeline=True,
                    instances=[at.to_scheduled_instance() for at in self.activityTimepoints],
                )
            ],
            notes=soa_notes,
        )


# =============================================================================
# 12. WRAPPER FUNCTIONS
# =============================================================================

def create_wrapper_input(
    timeline: Timeline = None,
    study_design: StudyDesign = None,
    study_version: StudyVersion = None,
    usdm_version: str = "4.0",
    system_name: str = "Protocol2USDM",
    system_version: str = "0.1.0",
) -> Dict[str, Any]:
    """
    Create a complete USDM Wrapper-Input structure.
    
    Args:
        timeline: Legacy Timeline (will be converted)
        study_design: Proper StudyDesign
        study_version: Proper StudyVersion
        usdm_version: USDM schema version
        system_name: Name of the generating system
        system_version: Version of the generating system
    
    Returns:
        Complete Wrapper-Input dict ready for JSON serialization
    """
    result = {
        'usdmVersion': usdm_version,
        'systemName': system_name,
        'systemVersion': system_version,
        'study': {
            'name': 'Protocol Study',
            'instanceType': 'Study',
            'versions': []
        }
    }
    
    if study_version:
        result['study']['versions'] = [study_version.to_dict()]
    elif study_design:
        result['study']['versions'] = [{
            'id': 'sv_1',
            'versionIdentifier': '1.0',
            'rationale': 'Initial version',
            'titles': [],
            'studyIdentifiers': [],
            'studyDesigns': [study_design.to_dict()],
            'instanceType': 'StudyVersion',
        }]
    elif timeline:
        # Legacy support: convert Timeline to StudyDesign
        sd = timeline.to_study_design()
        result['study']['versions'] = [{
            'id': 'sv_1',
            'versionIdentifier': '1.0',
            'rationale': 'Initial version',
            'titles': [],
            'studyIdentifiers': [],
            'studyDesigns': [sd.to_dict()],
            'instanceType': 'StudyVersion',
        }]
    
    return result
