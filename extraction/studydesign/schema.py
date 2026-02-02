"""
Study Design Extraction Schema - Internal types for extraction pipeline.

These types are used during extraction and convert to official USDM types
(from core.usdm_types) when generating final output.

For official USDM types, see: core/usdm_types.py
Schema source: https://github.com/cdisc-org/DDF-RA/blob/main/Deliverables/UML/dataStructure.yml
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

from core.usdm_types import generate_uuid, Code


class ArmType(Enum):
    """USDM StudyArm type codes."""
    UNKNOWN = ""  # Not extracted from source
    EXPERIMENTAL = "Experimental Arm"
    ACTIVE_COMPARATOR = "Active Comparator Arm"
    PLACEBO_COMPARATOR = "Placebo Comparator Arm"
    SHAM_COMPARATOR = "Sham Comparator Arm"
    NO_INTERVENTION = "No Intervention Arm"
    OTHER = "Other Arm"


class BlindingSchema(Enum):
    """USDM blinding schema codes."""
    UNKNOWN = ""  # Not extracted from source
    OPEN_LABEL = "Open Label"
    SINGLE_BLIND = "Single Blind"
    DOUBLE_BLIND = "Double Blind"
    TRIPLE_BLIND = "Triple Blind"
    QUADRUPLE_BLIND = "Quadruple Blind"


class RandomizationType(Enum):
    """USDM randomization type codes."""
    UNKNOWN = ""  # Not extracted from source
    RANDOMIZED = "Randomized"
    NON_RANDOMIZED = "Non-Randomized"


class ControlType(Enum):
    """USDM control type codes."""
    PLACEBO = "Placebo Control"
    ACTIVE = "Active Control"
    DOSE_COMPARISON = "Dose Comparison"
    NO_TREATMENT = "No Treatment"
    HISTORICAL = "Historical Control"


@dataclass
class AllocationRatio:
    """Allocation ratio for randomization."""
    ratio: str  # e.g., "1:1", "2:1", "1:1:1"
    description: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"ratio": self.ratio}
        if self.description:
            result["description"] = self.description
        return result


@dataclass
class DoseEpoch:
    """
    Represents a dose-level epoch for titration studies.
    
    Used when a single arm has sequential dose levels (within-subject titration).
    """
    dose: str  # e.g., "15 mg/day"
    start_day: Optional[int] = None
    end_day: Optional[int] = None
    description: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"dose": self.dose}
        if self.start_day is not None:
            result["startDay"] = self.start_day
        if self.end_day is not None:
            result["endDay"] = self.end_day
        if self.description:
            result["description"] = self.description
        return result


@dataclass
class StudyArm:
    """
    USDM StudyArm entity.
    
    Represents a treatment arm in the study.
    """
    id: str
    name: str
    description: Optional[str] = None
    arm_type: ArmType = ArmType.EXPERIMENTAL
    label: Optional[str] = None
    population_ids: List[str] = field(default_factory=list)  # Links to StudyCohort
    # Titration support
    is_titration: bool = False  # True if within-subject dose escalation
    dose_epochs: List[DoseEpoch] = field(default_factory=list)  # Sequential dose levels
    instance_type: str = "StudyArm"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "type": {
                "code": self.arm_type.value,
                "codeSystem": "USDM",
                "decode": self.arm_type.value,
            },
            "instanceType": self.instance_type,
        }
        if self.description:
            result["description"] = self.description
        if self.label:
            result["label"] = self.label
        if self.population_ids:
            result["populationIds"] = self.population_ids
        # Titration extension
        if self.is_titration:
            result["extensionAttributes"] = [{
                "url": "x-titration",
                "valueString": "true"
            }]
            if self.dose_epochs:
                result["extensionAttributes"].append({
                    "url": "x-doseEpochs",
                    "valueString": str([de.to_dict() for de in self.dose_epochs])
                })
        return result


@dataclass
class StudyElement:
    """
    USDM StudyElement entity.
    
    A basic building block for time within a clinical study comprising
    a description of what happens to the subject during the element.
    """
    id: str
    name: str
    description: Optional[str] = None
    label: Optional[str] = None
    instance_type: str = "StudyElement"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "instanceType": self.instance_type,
        }
        if self.description:
            result["description"] = self.description
        if self.label:
            result["label"] = self.label
        return result


@dataclass
class StudyCell:
    """
    USDM StudyCell entity.
    
    Represents the intersection of a StudyArm and StudyEpoch.
    Defines what happens for a particular arm during a particular epoch.
    """
    id: str
    arm_id: str  # Reference to StudyArm
    epoch_id: str  # Reference to StudyEpoch
    element_ids: List[str] = field(default_factory=list)  # StudyElement references
    instance_type: str = "StudyCell"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "armId": self.arm_id,
            "epochId": self.epoch_id,
            "elementIds": self.element_ids,
            "instanceType": self.instance_type,
        }


@dataclass
class StudyCohort:
    """
    USDM StudyCohort entity.
    
    Represents a sub-population within the study.
    """
    id: str
    name: str
    description: Optional[str] = None
    label: Optional[str] = None
    characteristic: Optional[str] = None  # Defining characteristic of the cohort
    instance_type: str = "StudyCohort"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "instanceType": self.instance_type,
        }
        if self.description:
            result["description"] = self.description
        if self.label:
            result["label"] = self.label
        if self.characteristic:
            result["characteristic"] = self.characteristic
        return result


@dataclass
class InterventionalStudyDesign:
    """
    USDM InterventionalStudyDesign entity.
    
    Describes the overall design of an interventional clinical trial.
    """
    id: str
    name: str
    description: Optional[str] = None
    
    # Design characteristics
    trial_intent_types: List[str] = field(default_factory=list)  # Treatment, Prevention, Diagnostic, etc.
    trial_type: Optional[str] = None  # e.g., "Interventional"
    
    # Blinding
    blinding_schema: Optional[BlindingSchema] = None
    masked_roles: List[str] = field(default_factory=list)  # Subject, Investigator, Outcome Assessor
    
    # Randomization
    randomization_type: Optional[RandomizationType] = None
    allocation_ratio: Optional[AllocationRatio] = None
    stratification_factors: List[str] = field(default_factory=list)
    
    # Control
    control_type: Optional[ControlType] = None
    
    # Structure references
    arm_ids: List[str] = field(default_factory=list)
    epoch_ids: List[str] = field(default_factory=list)
    cell_ids: List[str] = field(default_factory=list)
    cohort_ids: List[str] = field(default_factory=list)
    
    # Additional design info
    therapeutic_areas: List[str] = field(default_factory=list)
    
    instance_type: str = "InterventionalStudyDesign"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "instanceType": self.instance_type,
        }
        
        if self.description:
            result["description"] = self.description
        if self.trial_intent_types:
            result["trialIntentTypes"] = [
                {"code": t, "codeSystem": "USDM", "decode": t} for t in self.trial_intent_types
            ]
        if self.trial_type:
            result["trialType"] = {
                "code": self.trial_type,
                "codeSystem": "USDM", 
                "decode": self.trial_type,
            }
        if self.blinding_schema:
            result["blindingSchema"] = {
                "code": self.blinding_schema.value,
                "codeSystem": "USDM",
                "decode": self.blinding_schema.value,
            }
        if self.masked_roles:
            result["maskedRoles"] = self.masked_roles
        if self.randomization_type:
            result["randomizationType"] = {
                "code": self.randomization_type.value,
                "codeSystem": "USDM",
                "decode": self.randomization_type.value,
            }
        if self.allocation_ratio:
            result["allocationRatio"] = self.allocation_ratio.to_dict()
        if self.stratification_factors:
            result["stratificationFactors"] = self.stratification_factors
        if self.control_type:
            result["controlType"] = {
                "code": self.control_type.value,
                "codeSystem": "USDM",
                "decode": self.control_type.value,
            }
        if self.arm_ids:
            result["armIds"] = self.arm_ids
        if self.epoch_ids:
            result["epochIds"] = self.epoch_ids
        if self.cell_ids:
            result["cellIds"] = self.cell_ids
        if self.cohort_ids:
            result["cohortIds"] = self.cohort_ids
        if self.therapeutic_areas:
            result["therapeuticAreas"] = self.therapeutic_areas
            
        return result


@dataclass
class StudyDesignData:
    """
    Aggregated study design extraction result.
    
    Contains all Phase 4 entities for a protocol.
    """
    # Main design object
    study_design: Optional[InterventionalStudyDesign] = None
    
    # Arms
    arms: List[StudyArm] = field(default_factory=list)
    
    # Cells (arm × epoch)
    cells: List[StudyCell] = field(default_factory=list)
    
    # Cohorts
    cohorts: List[StudyCohort] = field(default_factory=list)
    
    # Elements (treatment periods within cells)
    elements: List[StudyElement] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to USDM-compatible dictionary structure."""
        result = {
            "studyArms": [a.to_dict() for a in self.arms],
            "studyCells": [c.to_dict() for c in self.cells],
            "studyCohorts": [c.to_dict() for c in self.cohorts],
            "studyElements": [e.to_dict() for e in self.elements],
            "summary": {
                "armCount": len(self.arms),
                "cellCount": len(self.cells),
                "cohortCount": len(self.cohorts),
                "elementCount": len(self.elements),
            }
        }
        if self.study_design:
            result["studyDesign"] = self.study_design.to_dict()
        return result
