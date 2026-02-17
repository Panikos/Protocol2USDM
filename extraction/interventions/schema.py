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
from core.code_registry import registry as _cr


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


class InterventionType(Enum):
    """ICH M11 intervention type codes (NCI EVS, no USDM CT codelist)."""
    DRUG = "Drug"
    BIOLOGICAL = "Biological"
    DEVICE = "Device"
    DIETARY_SUPPLEMENT = "Dietary Supplement"
    PROCEDURE = "Procedure"
    RADIATION = "Radiation"
    OTHER = "Other"


class InterventionRole(Enum):
    """USDM intervention role codes per USDM CT codelist C207417."""
    UNKNOWN = ""  # Not extracted from source
    INVESTIGATIONAL = "Experimental Intervention"
    COMPARATOR = "Active Comparator"
    PLACEBO = "Placebo"
    RESCUE = "Rescue Medicine"
    CONCOMITANT = "Additional Required Treatment"
    BACKGROUND = "Background Treatment"
    CHALLENGE_AGENT = "Challenge Agent"
    DIAGNOSTIC = "Diagnostic"


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
            "strengths": [{
                "id": generate_uuid(),
                "name": "Not specified",
                "numerator": {
                    "id": generate_uuid(),
                    "value": 0,
                    "instanceType": "Quantity",
                },
                "instanceType": "Strength",
            }],
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
    
    @staticmethod
    def _parse_dose_string(dose_str: str) -> tuple:
        """Parse a dose string like '100 mg' into (value, unit). Returns (None, dose_str) if unparseable."""
        import re
        m = re.match(r'^([\d.,]+)\s*(.+)$', dose_str.strip())
        if m:
            try:
                value = float(m.group(1).replace(',', ''))
                return (value, m.group(2).strip())
            except ValueError:
                pass
        return (None, dose_str)
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "instanceType": self.instance_type,
        }
        # H6: Emit dose as USDM Quantity object
        if self.dose:
            value, unit = self._parse_dose_string(self.dose)
            if value is not None:
                result["dose"] = {
                    "id": generate_uuid(),
                    "value": value,
                    "unit": {
                        "id": generate_uuid(),
                        "code": "",
                        "codeSystem": "http://unitsofmeasure.org",
                        "decode": unit,
                        "instanceType": "Code",
                    },
                    "instanceType": "Quantity",
                }
            else:
                result["dose"] = {
                    "id": generate_uuid(),
                    "value": 0,
                    "unit": {
                        "id": generate_uuid(),
                        "code": "",
                        "codeSystem": "http://unitsofmeasure.org",
                        "decode": self.dose,
                        "instanceType": "Code",
                    },
                    "instanceType": "Quantity",
                }
        # H7: Emit frequency as USDM Code object
        if self.dose_frequency:
            result["frequency"] = {
                "id": generate_uuid(),
                "code": "",
                "codeSystem": "http://www.cdisc.org",
                "decode": self.dose_frequency,
                "instanceType": "Code",
            }
        if self.route:
            route_term = _cr.match("routeOfAdministration", self.route.value)
            if route_term:
                route_code = _cr.make_code("routeOfAdministration", route_term.code)
                route_code["id"] = generate_uuid()
                result["route"] = route_code
            else:
                result["route"] = {
                    "id": generate_uuid(),
                    "code": self.route.value,
                    "codeSystem": "http://www.cdisc.org",
                    "decode": self.route.value,
                    "instanceType": "Code",
                }
        if self.duration:
            result["duration"] = self.duration
        if self.description:
            result["description"] = self.description
        return result


class ProductDesignation(Enum):
    """USDM CT codelist C207418 — IMP vs NIMP."""
    IMP = "IMP"
    NIMP = "NIMP"


class ProductSourcing(Enum):
    """USDM CT codelist C215483 — central vs local sourcing."""
    CENTRALLY_SOURCED = "Centrally Sourced"
    LOCALLY_SOURCED = "Locally Sourced"


@dataclass
class AdministrableProduct:
    """
    USDM AdministrableProduct entity (C215492).
    
    A product that can be administered to subjects.
    """
    id: str
    name: str
    label: Optional[str] = None  # Short descriptive designation (trade name)
    description: Optional[str] = None
    dose_form: Optional[DoseForm] = None
    strength: Optional[str] = None  # e.g., "15 mg", "100 mg/mL"
    route: Optional[RouteOfAdministration] = None  # Convenience; also on Administration
    product_designation: ProductDesignation = ProductDesignation.IMP
    sourcing: Optional[ProductSourcing] = None
    pharmacologic_class: Optional[str] = None  # e.g., "Copper Chelator", "Monoclonal Antibody"
    substance_ids: List[str] = field(default_factory=list)
    manufacturer: Optional[str] = None
    # M5: Product identifiers (NDC, manufacturer codes)
    identifiers: List[Dict[str, str]] = field(default_factory=list)
    # L5: Product properties
    properties: List[Dict[str, str]] = field(default_factory=list)
    instance_type: str = "AdministrableProduct"
    
    # Dose form NCI codes (no USDM CT codelist; NCI EVS verified)
    _DOSE_FORM_CODES = {
        DoseForm.TABLET: "C42998", DoseForm.CAPSULE: "C25158",
        DoseForm.SOLUTION: "C42986", DoseForm.SUSPENSION: "C42993",
        DoseForm.INJECTION: "C42945", DoseForm.CREAM: "C28944",
        DoseForm.OINTMENT: "C42966", DoseForm.GEL: "C42906",
        DoseForm.PATCH: "C42968", DoseForm.POWDER: "C42970",
        DoseForm.SPRAY: "C42989", DoseForm.INHALER: "C42940",
        DoseForm.OTHER: "C17998",
    }

    def to_dict(self) -> Dict[str, Any]:
        if self.dose_form:
            code = self._DOSE_FORM_CODES.get(self.dose_form, "C17998")
            decode = self.dose_form.value
        else:
            code, decode = "C17998", "Unknown"
        
        # productDesignation from USDM CT C207418 via CodeRegistry
        desig_term = _cr.match("productDesignation", self.product_designation.value)
        desig_code = _cr.make_code("productDesignation", desig_term.code) if desig_term else {
            "code": "C202579", "codeSystem": "http://www.cdisc.org",
            "codeSystemVersion": "2024-09-27", "decode": "IMP", "instanceType": "Code",
        }
        desig_code["id"] = generate_uuid()
        
        result = {
            "id": self.id,
            "name": self.name,
            "administrableDoseForm": {  # Required AliasCode per USDM v4.0
                "id": generate_uuid(),
                "standardCode": {
                    "id": generate_uuid(),
                    "code": code,
                    "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
                    "codeSystemVersion": "25.01d",
                    "decode": decode,
                    "instanceType": "Code",
                },
                "instanceType": "AliasCode",
            },
            "productDesignation": desig_code,
            "instanceType": self.instance_type,
        }
        if self.label:
            result["label"] = self.label
        if self.description:
            result["description"] = self.description
        if self.strength:
            result["strength"] = self.strength
        if self.route:
            route_term = _cr.match("routeOfAdministration", self.route.value)
            if route_term:
                route_code = _cr.make_code("routeOfAdministration", route_term.code)
                route_code["id"] = generate_uuid()
                result["routeOfAdministration"] = route_code
        if self.sourcing:
            src_term = _cr.match("productSourcing", self.sourcing.value)
            if src_term:
                src_code = _cr.make_code("productSourcing", src_term.code)
                src_code["id"] = generate_uuid()
                result["sourcing"] = src_code
        if self.pharmacologic_class:
            result["pharmacologicClass"] = {
                "id": generate_uuid(),
                "code": "",
                "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
                "decode": self.pharmacologic_class,
                "instanceType": "Code",
            }
        if self.substance_ids:
            result["substanceIds"] = self.substance_ids
        if self.manufacturer:
            result["manufacturer"] = self.manufacturer
        # M5: Product identifiers
        if self.identifiers:
            result["identifiers"] = [
                {"id": generate_uuid(), "text": pid.get("text", ""), "instanceType": "Code"}
                for pid in self.identifiers
            ]
        # L5: Product properties
        if self.properties:
            result["properties"] = [
                {"id": generate_uuid(), "name": p.get("name", ""), "value": p.get("value", ""), "instanceType": "AdministrableProductProperty"}
                for p in self.properties
            ]
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
    intervention_type: InterventionType = InterventionType.DRUG
    label: Optional[str] = None
    product_ids: List[str] = field(default_factory=list)  # Links to AdministrableProduct
    administration_ids: List[str] = field(default_factory=list)  # Links to Administration
    codes: List[Dict[str, str]] = field(default_factory=list)  # ATC codes, etc.
    # M4: Minimum response duration (e.g., "12 weeks")
    minimum_response_duration: Optional[str] = None
    # L4: Notes/comments about the intervention
    notes: List[str] = field(default_factory=list)
    instance_type: str = "StudyIntervention"
    
    def to_dict(self) -> Dict[str, Any]:
        # Role from USDM CT codelist C207417 via CodeRegistry
        role_term = _cr.match("interventionRole", self.role.value) if self.role.value else None
        role_code_obj = _cr.make_code("interventionRole", role_term.code) if role_term else _cr.make_code("interventionRole", "C41161")
        role_code_obj["id"] = generate_uuid()
        
        # Type from ICH M11 intervention type via CodeRegistry
        type_term = _cr.match("interventionType", self.intervention_type.value) if self.intervention_type else None
        type_code_obj = _cr.make_code("interventionType", type_term.code) if type_term else _cr.make_code("interventionType", "C1909")
        type_code_obj["id"] = generate_uuid()
        type_code_obj["codeSystem"] = "http://www.cdisc.org"
        type_code_obj["codeSystemVersion"] = "2024-09-27"
        
        result = {
            "id": self.id,
            "name": self.name,
            "type": type_code_obj,
            "role": role_code_obj,
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
        # M4: Minimum response duration
        if self.minimum_response_duration:
            result["minimumResponseDuration"] = {
                "id": generate_uuid(),
                "value": self.minimum_response_duration,
                "instanceType": "Duration",
            }
        # L4: Notes
        if self.notes:
            result["notes"] = [{"id": generate_uuid(), "text": n, "instanceType": "CommentAnnotation"} for n in self.notes]
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
