"""
Procedures Extraction Schema - Internal types for extraction pipeline.

These types are used during extraction and convert to official USDM types
(from core.usdm_types) when generating final output.

For official USDM types, see: core/usdm_types.py
Schema source: https://github.com/cdisc-org/DDF-RA/blob/main/Deliverables/UML/dataStructure.yml
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

from core.usdm_types import generate_uuid, Code


class ProcedureType(Enum):
    """Types of clinical procedures."""
    UNKNOWN = ""  # Not extracted from source
    DIAGNOSTIC = "Diagnostic"
    THERAPEUTIC = "Therapeutic"
    SURGICAL = "Surgical"
    SAMPLING = "Sample Collection"
    IMAGING = "Imaging"
    MONITORING = "Monitoring"
    ASSESSMENT = "Assessment"


class DeviceType(Enum):
    """Types of medical devices."""
    UNKNOWN = ""  # Not extracted from source
    DRUG_DELIVERY = "Drug Delivery Device"
    DIAGNOSTIC = "Diagnostic Device"
    MONITORING = "Monitoring Device"
    IMPLANTABLE = "Implantable Device"
    WEARABLE = "Wearable Device"
    IMAGING = "Imaging Equipment"
    LABORATORY = "Laboratory Equipment"


@dataclass
class Procedure:
    """
    USDM Procedure entity.
    Represents a clinical procedure performed during the study.
    """
    id: str
    name: str
    label: Optional[str] = None
    description: Optional[str] = None
    procedure_type: Optional[ProcedureType] = None
    code: Optional[Dict[str, str]] = None  # CPT, SNOMED, etc.
    instance_type: str = "Procedure"
    
    def to_dict(self) -> Dict[str, Any]:
        # Map procedure types to NCI codes where available
        procedure_type_codes = {
            ProcedureType.DIAGNOSTIC: ("C25391", "Diagnostic Procedure"),
            ProcedureType.THERAPEUTIC: ("C49236", "Therapeutic Procedure"),
            ProcedureType.SURGICAL: ("C17173", "Surgical Procedure"),
            ProcedureType.SAMPLING: ("C70793", "Biospecimen Collection"),
            ProcedureType.IMAGING: ("C17369", "Imaging Technique"),
            ProcedureType.MONITORING: ("C25548", "Monitoring"),
            ProcedureType.ASSESSMENT: ("C25218", "Assessment"),
        }
        
        # Build procedureType as proper Code object (required as string per schema)
        if self.procedure_type:
            code, decode = procedure_type_codes.get(self.procedure_type, (self.procedure_type.value, self.procedure_type.value))
            proc_type_str = decode  # USDM expects string, not Code object
        else:
            proc_type_str = "Clinical Procedure"
        
        # Check if code dict has valid values (not all null)
        has_valid_code = (
            self.code 
            and isinstance(self.code, dict) 
            and self.code.get('code')  # code value must be non-null
        )
        
        # Build code object - use existing if valid, otherwise create default
        if has_valid_code:
            # Ensure all required fields are strings (not null)
            code_obj = {
                "id": self.code.get('id') or generate_uuid(),
                "code": self.code.get('code') or "",
                "codeSystem": self.code.get('codeSystem') or "",
                "codeSystemVersion": self.code.get('codeSystemVersion') or "",
                "decode": self.code.get('decode') or self.name,
                "instanceType": "Code",
            }
        else:
            # Default code based on procedure type
            default_code, default_decode = procedure_type_codes.get(
                self.procedure_type, ("C25218", "Clinical Procedure")
            )
            code_obj = {
                "id": generate_uuid(),
                "code": default_code,
                "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
                "codeSystemVersion": "25.01d",
                "decode": default_decode,
                "instanceType": "Code",
            }
        
        result = {
            "id": self.id,
            "name": self.name,
            "procedureType": proc_type_str,  # Required field - string type
            "code": code_obj,
            "instanceType": self.instance_type,
        }
        if self.label:
            result["label"] = self.label
        if self.description:
            result["description"] = self.description
        return result


@dataclass
class MedicalDeviceIdentifier:
    """
    USDM MedicalDeviceIdentifier entity.
    Identifier for a medical device (UDI, catalog number, etc.)
    """
    id: str
    text: str
    scope_id: Optional[str] = None
    instance_type: str = "MedicalDeviceIdentifier"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "text": self.text,
            "instanceType": self.instance_type,
        }
        if self.scope_id:
            result["scopeId"] = self.scope_id
        return result


@dataclass
class MedicalDevice:
    """
    USDM MedicalDevice entity.
    Represents a medical device used in the study.
    """
    id: str
    name: str
    label: Optional[str] = None
    description: Optional[str] = None
    device_type: Optional[DeviceType] = None
    manufacturer: Optional[str] = None
    model_number: Optional[str] = None
    identifier_ids: List[str] = field(default_factory=list)
    instance_type: str = "MedicalDevice"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "instanceType": self.instance_type,
        }
        if self.label:
            result["label"] = self.label
        if self.description:
            result["description"] = self.description
        if self.device_type:
            result["deviceType"] = {
                "code": self.device_type.value,
                "codeSystem": "USDM",
                "decode": self.device_type.value
            }
        if self.manufacturer:
            result["manufacturer"] = self.manufacturer
        if self.model_number:
            result["modelNumber"] = self.model_number
        if self.identifier_ids:
            result["identifierIds"] = self.identifier_ids
        return result


@dataclass
class Ingredient:
    """
    USDM Ingredient entity.
    Represents an ingredient of an administrable product.
    """
    id: str
    name: str
    role: str  # "Active", "Inactive", "Adjuvant"
    substance_id: Optional[str] = None
    instance_type: str = "Ingredient"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "instanceType": self.instance_type,
        }
        if self.substance_id:
            result["substanceId"] = self.substance_id
        return result


@dataclass
class Strength:
    """
    USDM Strength entity.
    Represents the strength/concentration of an ingredient.
    """
    id: str
    value: float
    unit: str
    numerator_value: Optional[float] = None
    numerator_unit: Optional[str] = None
    denominator_value: Optional[float] = None
    denominator_unit: Optional[str] = None
    instance_type: str = "Strength"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "instanceType": self.instance_type,
        }
        # Simple strength
        if self.value and self.unit:
            result["value"] = self.value
            result["unit"] = self.unit
        # Ratio strength (e.g., mg/mL)
        if self.numerator_value:
            result["numerator"] = {
                "value": self.numerator_value,
                "unit": self.numerator_unit or ""
            }
        if self.denominator_value:
            result["denominator"] = {
                "value": self.denominator_value,
                "unit": self.denominator_unit or ""
            }
        return result


@dataclass
class ProceduresDevicesData:
    """Container for procedures and devices extraction results."""
    procedures: List[Procedure] = field(default_factory=list)
    devices: List[MedicalDevice] = field(default_factory=list)
    device_identifiers: List[MedicalDeviceIdentifier] = field(default_factory=list)
    ingredients: List[Ingredient] = field(default_factory=list)
    strengths: List[Strength] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "procedures": [p.to_dict() for p in self.procedures],
            "medicalDevices": [d.to_dict() for d in self.devices],
            "medicalDeviceIdentifiers": [i.to_dict() for i in self.device_identifiers],
            "ingredients": [i.to_dict() for i in self.ingredients],
            "strengths": [s.to_dict() for s in self.strengths],
            "summary": {
                "procedureCount": len(self.procedures),
                "deviceCount": len(self.devices),
                "ingredientCount": len(self.ingredients),
            }
        }


@dataclass
class ProceduresDevicesResult:
    """Result container for procedures and devices extraction."""
    success: bool
    data: Optional[ProceduresDevicesData] = None
    error: Optional[str] = None
    pages_used: List[int] = field(default_factory=list)
    model_used: Optional[str] = None
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "success": self.success,
            "pagesUsed": self.pages_used,
            "modelUsed": self.model_used,
            "confidence": self.confidence,
        }
        if self.data:
            result["proceduresDevices"] = self.data.to_dict()
        if self.error:
            result["error"] = self.error
        return result
