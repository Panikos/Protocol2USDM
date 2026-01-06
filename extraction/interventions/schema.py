"""
Interventions Extraction Schema - Internal types for extraction pipeline.

These types are used during extraction and convert to official USDM types
(from core.usdm_types) when generating final output.

For official USDM types, see: core/usdm_types.py
Schema source: https://github.com/cdisc-org/DDF-RA/blob/main/Deliverables/UML/dataStructure.yml
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

from core.usdm_types import generate_uuid, Code


class RouteOfAdministration(Enum):
    """USDM route of administration codes."""
    ORAL = "Oral"
    INTRAVENOUS = "Intravenous"
    SUBCUTANEOUS = "Subcutaneous"
    INTRAMUSCULAR = "Intramuscular"
    TOPICAL = "Topical"
    INHALATION = "Inhalation"
    INTRANASAL = "Intranasal"
    OPHTHALMIC = "Ophthalmic"
    TRANSDERMAL = "Transdermal"
    RECTAL = "Rectal"
    SUBLINGUAL = "Sublingual"
    OTHER = "Other"


class DoseForm(Enum):
    """USDM dose form codes."""
    TABLET = "Tablet"
    CAPSULE = "Capsule"
    SOLUTION = "Solution"
    SUSPENSION = "Suspension"
    INJECTION = "Injection"
    CREAM = "Cream"
    OINTMENT = "Ointment"
    GEL = "Gel"
    PATCH = "Patch"
    POWDER = "Powder"
    SPRAY = "Spray"
    INHALER = "Inhaler"
    OTHER = "Other"


class InterventionRole(Enum):
    """USDM intervention role codes."""
    INVESTIGATIONAL = "Investigational Product"
    COMPARATOR = "Comparator"
    PLACEBO = "Placebo"
    RESCUE = "Rescue Medication"
    CONCOMITANT = "Concomitant Medication"
    BACKGROUND = "Background Therapy"


@dataclass
class Substance:
    """
    USDM Substance entity.
    
    Active pharmaceutical ingredient.
    """
    id: str
    name: str
    description: Optional[str] = None
    codes: List[Dict[str, str]] = field(default_factory=list)  # UNII, CAS, etc.
    instance_type: str = "Substance"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "instanceType": self.instance_type,
        }
        if self.description:
            result["description"] = self.description
        if self.codes:
            result["codes"] = self.codes
        return result


@dataclass
class Administration:
    """
    USDM Administration entity.
    
    Describes how a product is administered.
    """
    id: str
    name: str
    dose: Optional[str] = None  # e.g., "15 mg", "100 mg/m2"
    dose_frequency: Optional[str] = None  # e.g., "once daily", "twice daily"
    route: Optional[RouteOfAdministration] = None
    duration: Optional[str] = None  # e.g., "24 weeks", "Until disease progression"
    description: Optional[str] = None
    instance_type: str = "Administration"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "instanceType": self.instance_type,
        }
        if self.dose:
            result["dose"] = self.dose
        if self.dose_frequency:
            result["doseFrequency"] = self.dose_frequency
        if self.route:
            result["route"] = {
                "code": self.route.value,
                "codeSystem": "USDM",
                "decode": self.route.value,
            }
        if self.duration:
            result["duration"] = self.duration
        if self.description:
            result["description"] = self.description
        return result


@dataclass
class AdministrableProduct:
    """
    USDM AdministrableProduct entity.
    
    A product that can be administered to subjects.
    """
    id: str
    name: str
    description: Optional[str] = None
    dose_form: Optional[DoseForm] = None
    strength: Optional[str] = None  # e.g., "15 mg", "100 mg/mL"
    substance_ids: List[str] = field(default_factory=list)
    manufacturer: Optional[str] = None
    instance_type: str = "AdministrableProduct"
    
    def to_dict(self) -> Dict[str, Any]:
        # Map dose forms to NCI codes
        dose_form_codes = {
            DoseForm.TABLET: ("C42998", "Tablet"),
            DoseForm.CAPSULE: ("C25158", "Capsule"),
            DoseForm.SOLUTION: ("C42986", "Solution"),
            DoseForm.SUSPENSION: ("C42993", "Suspension"),
            DoseForm.INJECTION: ("C42945", "Injection"),
            DoseForm.CREAM: ("C28944", "Cream"),
            DoseForm.OINTMENT: ("C42966", "Ointment"),
            DoseForm.GEL: ("C42906", "Gel"),
            DoseForm.PATCH: ("C42968", "Patch"),
            DoseForm.POWDER: ("C42970", "Powder"),
            DoseForm.SPRAY: ("C42989", "Spray"),
            DoseForm.INHALER: ("C42940", "Inhaler"),
            DoseForm.OTHER: ("C17998", "Unknown"),
        }
        
        if self.dose_form:
            code, decode = dose_form_codes.get(self.dose_form, ("C17998", "Unknown"))
        else:
            code, decode = "C17998", "Unknown"
        
        result = {
            "id": self.id,
            "name": self.name,
            "administrableDoseForm": {  # Required field
                "id": generate_uuid(),
                "code": code,
                "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
                "codeSystemVersion": "25.01d",
                "decode": decode,
                "standardCode": {  # Required nested Code
                    "id": generate_uuid(),
                    "code": code,
                    "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
                    "codeSystemVersion": "25.01d",
                    "decode": decode,
                    "instanceType": "Code",
                },
                "instanceType": "Code",
            },
            "productDesignation": {  # Required field
                "id": generate_uuid(),
                "code": "C54121",
                "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
                "codeSystemVersion": "25.01d",
                "decode": "Investigational Product",
                "instanceType": "Code",
            },
            "instanceType": self.instance_type,
        }
        if self.description:
            result["description"] = self.description
        if self.strength:
            result["strength"] = self.strength
        if self.substance_ids:
            result["substanceIds"] = self.substance_ids
        if self.manufacturer:
            result["manufacturer"] = self.manufacturer
        return result


@dataclass
class MedicalDevice:
    """
    USDM MedicalDevice entity.
    
    A medical device used in the study.
    """
    id: str
    name: str
    description: Optional[str] = None
    device_identifier: Optional[str] = None
    manufacturer: Optional[str] = None
    instance_type: str = "MedicalDevice"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "instanceType": self.instance_type,
        }
        if self.description:
            result["description"] = self.description
        if self.device_identifier:
            result["deviceIdentifier"] = self.device_identifier
        if self.manufacturer:
            result["manufacturer"] = self.manufacturer
        return result


@dataclass
class StudyIntervention:
    """
    USDM StudyIntervention entity.
    
    High-level description of an intervention in the study.
    """
    id: str
    name: str
    description: Optional[str] = None
    role: InterventionRole = InterventionRole.INVESTIGATIONAL
    label: Optional[str] = None
    product_ids: List[str] = field(default_factory=list)  # Links to AdministrableProduct
    administration_ids: List[str] = field(default_factory=list)  # Links to Administration
    codes: List[Dict[str, str]] = field(default_factory=list)  # ATC codes, etc.
    instance_type: str = "StudyIntervention"
    
    def to_dict(self) -> Dict[str, Any]:
        # Map intervention roles to NCI codes
        role_codes = {
            InterventionRole.INVESTIGATIONAL: ("C54121", "Investigational Product"),
            InterventionRole.COMPARATOR: ("C54129", "Comparator"),
            InterventionRole.PLACEBO: ("C41132", "Placebo"),
            InterventionRole.RESCUE: ("C54125", "Rescue Medication"),
            InterventionRole.CONCOMITANT: ("C54126", "Concomitant Medication"),
            InterventionRole.BACKGROUND: ("C54127", "Background Therapy"),
        }
        code, decode = role_codes.get(self.role, ("C54121", "Investigational Product"))
        
        result = {
            "id": self.id,
            "name": self.name,
            "type": {  # Required field
                "id": generate_uuid(),
                "code": code,
                "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
                "codeSystemVersion": "25.01d",
                "decode": decode,
                "instanceType": "Code",
            },
            "role": {
                "id": generate_uuid(),
                "code": code,
                "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
                "codeSystemVersion": "25.01d",
                "decode": decode,
                "instanceType": "Code",
            },
            "instanceType": self.instance_type,
        }
        if self.description:
            result["description"] = self.description
        if self.label:
            result["label"] = self.label
        if self.product_ids:
            result["productIds"] = self.product_ids
        if self.administration_ids:
            result["administrationIds"] = self.administration_ids
        if self.codes:
            result["codes"] = self.codes
        return result


@dataclass
class InterventionsData:
    """
    Aggregated interventions extraction result.
    
    Contains all Phase 5 entities for a protocol.
    """
    interventions: List[StudyIntervention] = field(default_factory=list)
    products: List[AdministrableProduct] = field(default_factory=list)
    administrations: List[Administration] = field(default_factory=list)
    substances: List[Substance] = field(default_factory=list)
    devices: List[MedicalDevice] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to USDM-compatible dictionary structure."""
        return {
            "studyInterventions": [i.to_dict() for i in self.interventions],
            "administrableProducts": [p.to_dict() for p in self.products],
            "administrations": [a.to_dict() for a in self.administrations],
            "substances": [s.to_dict() for s in self.substances],
            "medicalDevices": [d.to_dict() for d in self.devices],
            "summary": {
                "interventionCount": len(self.interventions),
                "productCount": len(self.products),
                "deviceCount": len(self.devices),
            }
        }
