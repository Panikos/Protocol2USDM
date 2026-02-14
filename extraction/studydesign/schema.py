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


# ---------------------------------------------------------------------------
# Therapeutic Area controlled vocabulary (MeSH-backed)
# Keys = canonical TA labels; values = MeSH Descriptor Unique IDs.
# Used by LLM prompt (constrained list) and deterministic fallback.
# ---------------------------------------------------------------------------
THERAPEUTIC_AREA_CODES: Dict[str, str] = {
    "Oncology": "D009369",
    "Cardiovascular": "D002318",
    "Endocrinology & Metabolism": "D008659",
    "Neurology": "D009422",
    "Psychiatry": "D001523",
    "Infectious Disease": "D003141",
    "Immunology & Inflammation": "D007154",
    "Respiratory": "D012140",
    "Gastroenterology": "D004066",
    "Nephrology": "D007674",
    "Dermatology": "D012871",
    "Hematology": "D006425",
    "Ophthalmology": "D005128",
    "Musculoskeletal": "D009140",
    "Hepatology": "D008107",
    "Urology": "D014570",
    "Rheumatology": "D012216",
    "Rare Diseases": "D035583",
    "Vaccines": "D014612",
    "Pain": "D010146",
    "Gynecology & Obstetrics": "D005261",
}

# Keyword → canonical TA name for deterministic indication-based fallback
_INDICATION_TA_KEYWORDS: Dict[str, str] = {
    # Oncology
    "cancer": "Oncology", "tumor": "Oncology", "tumour": "Oncology",
    "carcinoma": "Oncology", "lymphoma": "Oncology", "leukemia": "Oncology",
    "leukaemia": "Oncology", "melanoma": "Oncology", "sarcoma": "Oncology",
    "myeloma": "Oncology", "glioblastoma": "Oncology", "neoplasm": "Oncology",
    "nsclc": "Oncology", "sclc": "Oncology", "malignant": "Oncology",
    # Cardiovascular
    "heart failure": "Cardiovascular", "cardiac": "Cardiovascular",
    "cardiovascular": "Cardiovascular", "hypertension": "Cardiovascular",
    "atherosclerosis": "Cardiovascular", "atrial fibrillation": "Cardiovascular",
    "myocardial": "Cardiovascular", "coronary": "Cardiovascular",
    "cardiomyopathy": "Cardiovascular", "stroke": "Cardiovascular",
    # Endocrinology & Metabolism
    "diabetes": "Endocrinology & Metabolism", "diabetic": "Endocrinology & Metabolism",
    "glycemic": "Endocrinology & Metabolism", "insulin": "Endocrinology & Metabolism",
    "obesity": "Endocrinology & Metabolism", "metabolic": "Endocrinology & Metabolism",
    "thyroid": "Endocrinology & Metabolism", "hba1c": "Endocrinology & Metabolism",
    # Neurology
    "alzheimer": "Neurology", "parkinson": "Neurology", "multiple sclerosis": "Neurology",
    "epilepsy": "Neurology", "migraine": "Neurology", "neuropathy": "Neurology",
    "neurodegenerat": "Neurology", "amyotrophic": "Neurology", "huntington": "Neurology",
    # Psychiatry
    "depression": "Psychiatry", "schizophrenia": "Psychiatry", "bipolar": "Psychiatry",
    "anxiety": "Psychiatry", "adhd": "Psychiatry", "psychosis": "Psychiatry",
    # Infectious Disease
    "hiv": "Infectious Disease", "hepatitis": "Infectious Disease",
    "covid": "Infectious Disease", "sars": "Infectious Disease",
    "tuberculosis": "Infectious Disease", "malaria": "Infectious Disease",
    "influenza": "Infectious Disease", "infection": "Infectious Disease",
    "pneumonia": "Infectious Disease", "sepsis": "Infectious Disease",
    # Immunology & Inflammation
    "autoimmune": "Immunology & Inflammation", "lupus": "Immunology & Inflammation",
    "crohn": "Immunology & Inflammation", "colitis": "Immunology & Inflammation",
    "inflammatory bowel": "Immunology & Inflammation", "ibd": "Immunology & Inflammation",
    # Respiratory
    "asthma": "Respiratory", "copd": "Respiratory", "pulmonary": "Respiratory",
    "respiratory": "Respiratory", "lung": "Respiratory", "cystic fibrosis": "Respiratory",
    # Gastroenterology
    "gastric": "Gastroenterology", "gastrointestinal": "Gastroenterology",
    "celiac": "Gastroenterology", "gerd": "Gastroenterology",
    # Nephrology
    "kidney": "Nephrology", "renal": "Nephrology", "nephritis": "Nephrology",
    "dialysis": "Nephrology", "ckd": "Nephrology",
    # Dermatology
    "psoriasis": "Dermatology", "dermatitis": "Dermatology", "eczema": "Dermatology",
    "atopic": "Dermatology", "skin": "Dermatology", "acne": "Dermatology",
    # Hematology
    "anemia": "Hematology", "anaemia": "Hematology", "hemophilia": "Hematology",
    "thrombocytopenia": "Hematology", "sickle cell": "Hematology",
    "thalassemia": "Hematology", "wilson disease": "Hematology",
    "wilson's disease": "Hematology", "copper": "Hematology",
    # Ophthalmology
    "macular": "Ophthalmology", "retinal": "Ophthalmology", "glaucoma": "Ophthalmology",
    "optic": "Ophthalmology", "ocular": "Ophthalmology",
    # Musculoskeletal
    "osteoporosis": "Musculoskeletal", "arthritis": "Musculoskeletal",
    "osteoarthritis": "Musculoskeletal", "fracture": "Musculoskeletal",
    # Hepatology
    "liver": "Hepatology", "hepatic": "Hepatology", "cirrhosis": "Hepatology",
    "nash": "Hepatology", "nafld": "Hepatology",
    # Rheumatology
    "rheumatoid": "Rheumatology", "ankylosing": "Rheumatology",
    "psoriatic arthritis": "Rheumatology", "gout": "Rheumatology",
    # Rare Diseases
    "rare": "Rare Diseases", "orphan": "Rare Diseases",
    # Vaccines
    "vaccine": "Vaccines", "immunization": "Vaccines",
    # Pain
    "pain": "Pain", "fibromyalgia": "Pain", "analges": "Pain",
    # Urology
    "bladder": "Urology", "prostate": "Urology", "urinary": "Urology",
    # Gynecology & Obstetrics
    "endometriosis": "Gynecology & Obstetrics", "ovarian": "Gynecology & Obstetrics",
    "uterine": "Gynecology & Obstetrics", "pregnancy": "Gynecology & Obstetrics",
}


def _build_therapeutic_area_code(ta_name: str) -> Dict[str, Any]:
    """Build a USDM Code object for a therapeutic area, using MeSH descriptors."""
    mesh_id = THERAPEUTIC_AREA_CODES.get(ta_name, "")
    return {
        "id": generate_uuid(),
        "code": mesh_id,
        "codeSystem": "http://www.nlm.nih.gov/mesh",
        "codeSystemVersion": "2024",
        "decode": ta_name,
        "instanceType": "Code",
    }


def _match_therapeutic_area(raw: str) -> Optional[str]:
    """Fuzzy-match a raw TA string from the LLM to a canonical TA name."""
    raw_lower = raw.lower().strip()
    # Exact match (case-insensitive)
    for canonical in THERAPEUTIC_AREA_CODES:
        if canonical.lower() == raw_lower:
            return canonical
    # Substring / prefix match
    for canonical in THERAPEUTIC_AREA_CODES:
        if raw_lower in canonical.lower() or canonical.lower() in raw_lower:
            return canonical
    return None


def infer_therapeutic_areas_from_indications(indication_names: List[str]) -> List[str]:
    """
    Deterministic fallback: infer therapeutic areas from indication names
    using keyword matching.  Returns deduplicated canonical TA names.
    """
    matched: Dict[str, bool] = {}
    for name in indication_names:
        name_lower = name.lower()
        for keyword, ta in _INDICATION_TA_KEYWORDS.items():
            if keyword in name_lower and ta not in matched:
                matched[ta] = True
    return list(matched.keys())


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
    # L3: Arm notes/comments
    notes: List[str] = field(default_factory=list)
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
        # L3: Arm notes
        if self.notes:
            result["notes"] = [
                {"id": generate_uuid(), "text": n, "instanceType": "CommentAnnotation"}
                for n in self.notes
            ]
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
    
    # Additional design info — values should be keys from THERAPEUTIC_AREA_CODES
    therapeutic_areas: List[str] = field(default_factory=list)
    
    # C3: Design rationale (USDM InterventionalStudyDesign.rationale — required)
    rationale: Optional[str] = None
    
    # H4: Study design characteristics (e.g., "Parallel", "Crossover", "Adaptive")
    characteristics: List[str] = field(default_factory=list)
    
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
            result["therapeuticAreas"] = [
                _build_therapeutic_area_code(ta) for ta in self.therapeutic_areas
            ]
        # C3: Design rationale
        if self.rationale:
            result["rationale"] = self.rationale
        # H4: Characteristics as coded values
        if self.characteristics:
            result["characteristics"] = [
                {
                    "id": generate_uuid(),
                    "code": c,
                    "codeSystem": "http://www.cdisc.org",
                    "decode": c,
                    "instanceType": "Code",
                } for c in self.characteristics
            ]
            
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
