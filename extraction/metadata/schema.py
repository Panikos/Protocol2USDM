"""
Metadata Extraction Schema - Internal types for extraction pipeline.

These types are used during extraction and convert to official USDM types
(from core.usdm_types) when generating final output.

For official USDM types, see: core/usdm_types.py
Schema source: https://github.com/cdisc-org/DDF-RA/blob/main/Deliverables/UML/dataStructure.yml
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

from core.usdm_types import generate_uuid, Code


class TitleType(Enum):
    """USDM StudyTitle types."""
    BRIEF = "Brief Study Title"
    OFFICIAL = "Official Study Title"
    PUBLIC = "Public Study Title"
    SCIENTIFIC = "Scientific Study Title"
    ACRONYM = "Study Acronym"


class OrganizationType(Enum):
    """USDM Organization types."""
    REGULATORY_AGENCY = "Regulatory Agency"
    PHARMACEUTICAL_COMPANY = "Pharmaceutical Company"
    CRO = "Contract Research Organization"
    ACADEMIC = "Academic Institution"
    HEALTHCARE = "Healthcare Facility"
    GOVERNMENT = "Government Institute"
    LABORATORY = "Laboratory"
    REGISTRY = "Clinical Study Registry"
    MEDICAL_DEVICE = "Medical Device Company"


class StudyRoleCode(Enum):
    """USDM StudyRole codes."""
    SPONSOR = "Sponsor"
    CO_SPONSOR = "Co-Sponsor"
    LOCAL_SPONSOR = "Local Sponsor"
    INVESTIGATOR = "Investigator"
    PRINCIPAL_INVESTIGATOR = "Principal investigator"
    CRO = "Contract Research"
    REGULATORY = "Regulatory Agency"
    MANUFACTURER = "Manufacturer"
    STUDY_SITE = "Study Site"
    STATISTICIAN = "Statistician"
    MEDICAL_EXPERT = "Medical Expert"
    PROJECT_MANAGER = "Project Manager"


@dataclass
class StudyTitle:
    """USDM StudyTitle entity."""
    id: str
    text: str
    type: TitleType
    instance_type: str = "StudyTitle"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "type": {"code": self.type.value, "codeSystem": "USDM", "decode": self.type.value},
            "instanceType": self.instance_type,
        }


@dataclass
class StudyIdentifier:
    """USDM StudyIdentifier entity."""
    id: str
    text: str  # The actual identifier value (e.g., "NCT04573309")
    scope_id: str  # Reference to Organization that issued it
    instance_type: str = "StudyIdentifier"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "scopeId": self.scope_id,
            "instanceType": self.instance_type,
        }


@dataclass
class Organization:
    """USDM Organization entity."""
    id: str
    name: str
    type: OrganizationType
    identifier: Optional[str] = None
    identifier_scheme: Optional[str] = None
    label: Optional[str] = None
    instance_type: str = "Organization"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "type": {"code": self.type.value, "codeSystem": "USDM", "decode": self.type.value},
            "instanceType": self.instance_type,
        }
        if self.identifier:
            result["identifier"] = self.identifier
            result["identifierScheme"] = self.identifier_scheme or "Unknown"
        if self.label:
            result["label"] = self.label
        return result


@dataclass
class StudyRole:
    """USDM StudyRole entity - links organizations to their roles in the study."""
    id: str
    name: str
    code: StudyRoleCode
    organization_ids: List[str] = field(default_factory=list)
    description: Optional[str] = None
    instance_type: str = "StudyRole"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "code": {"code": self.code.value, "codeSystem": "USDM", "decode": self.code.value},
            "organizationIds": self.organization_ids,
            "instanceType": self.instance_type,
        }
        if self.description:
            result["description"] = self.description
        return result


@dataclass
class Indication:
    """USDM Indication entity - disease or condition being studied."""
    id: str
    name: str
    description: Optional[str] = None
    is_rare_disease: bool = False
    codes: List[Dict[str, str]] = field(default_factory=list)  # MedDRA, ICD codes
    instance_type: str = "Indication"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "isRareDisease": self.is_rare_disease,
            "instanceType": self.instance_type,
        }
        if self.description:
            result["description"] = self.description
        if self.codes:
            result["codes"] = self.codes
        return result


@dataclass
class StudyPhase:
    """Study phase information."""
    phase: str  # "Phase 1", "Phase 2", "Phase 3", "Phase 4", "Phase 1/2", etc.
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.phase,
            "codeSystem": "USDM",
            "decode": self.phase,
        }


@dataclass
class StudyMetadata:
    """
    Aggregated study metadata extraction result.
    
    Contains all Phase 2 entities for a protocol.
    """
    # Study identity
    study_name: str
    study_description: Optional[str] = None
    
    # Titles
    titles: List[StudyTitle] = field(default_factory=list)
    
    # Identifiers
    identifiers: List[StudyIdentifier] = field(default_factory=list)
    
    # Organizations
    organizations: List[Organization] = field(default_factory=list)
    
    # Roles
    roles: List[StudyRole] = field(default_factory=list)
    
    # Indication/Disease
    indications: List[Indication] = field(default_factory=list)
    
    # Study characteristics
    study_phase: Optional[StudyPhase] = None
    study_type: Optional[str] = None  # "Interventional" or "Observational"
    
    # Protocol version info
    protocol_version: Optional[str] = None
    protocol_date: Optional[str] = None
    amendment_number: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to USDM-compatible dictionary structure."""
        result = {
            "studyName": self.study_name,
            "titles": [t.to_dict() for t in self.titles],
            "identifiers": [i.to_dict() for i in self.identifiers],
            "organizations": [o.to_dict() for o in self.organizations],
            "roles": [r.to_dict() for r in self.roles],
            "indications": [i.to_dict() for i in self.indications],
        }
        
        if self.study_description:
            result["studyDescription"] = self.study_description
        if self.study_phase:
            result["studyPhase"] = self.study_phase.to_dict()
        if self.study_type:
            result["studyType"] = self.study_type
        if self.protocol_version:
            result["protocolVersion"] = self.protocol_version
        if self.protocol_date:
            result["protocolDate"] = self.protocol_date
        if self.amendment_number:
            result["amendmentNumber"] = self.amendment_number
            
        return result
