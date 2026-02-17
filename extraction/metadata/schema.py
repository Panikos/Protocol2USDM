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
from core.code_registry import registry as _cr


class TitleType(Enum):
    """USDM StudyTitle types."""
    UNKNOWN = ""  # Not extracted from source
    BRIEF = "Brief Study Title"
    OFFICIAL = "Official Study Title"
    PUBLIC = "Public Study Title"
    SCIENTIFIC = "Scientific Study Title"
    ACRONYM = "Study Acronym"


class OrganizationType(Enum):
    """USDM Organization types."""
    UNKNOWN = ""  # Not extracted from source
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
    UNKNOWN = ""  # Not extracted from source
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
        # USDM CT codelist C207419 via CodeRegistry
        term = _cr.match("titleType", self.type.value) if self.type.value else None
        type_code = _cr.make_code("titleType", term.code) if term else _cr.make_code("titleType", "C207616")
        return {
            "id": self.id,
            "text": self.text,
            "type": type_code,
            "instanceType": self.instance_type,
        }


class IdentifierType(Enum):
    """Types of study identifiers."""
    NCT = "NCT"  # ClinicalTrials.gov
    SPONSOR_PROTOCOL = "SponsorProtocolNumber"
    EUDRACT = "EudraCT"
    IND = "IND"
    IDE = "IDE"
    ISRCTN = "ISRCTN"
    CTIS = "CTIS"
    WHO_UTN = "WHO_UTN"
    OTHER = "Other"


@dataclass
class StudyIdentifier:
    """USDM StudyIdentifier entity."""
    id: str
    text: str  # The actual identifier value (e.g., "NCT04573309")
    scope_id: str  # Reference to Organization that issued it
    identifier_type: Optional[IdentifierType] = None
    issuing_organization: Optional[str] = None
    instance_type: str = "StudyIdentifier"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "text": self.text,
            "scopeId": self.scope_id,
            "instanceType": self.instance_type,
        }
        if self.identifier_type:
            result["identifierType"] = {
                "code": self.identifier_type.value,
                "codeSystem": "http://www.cdisc.org",
                "decode": self._get_identifier_decode()
            }
        return result
    
    def _get_identifier_decode(self) -> str:
        """Get human-readable decode for identifier type."""
        decodes = {
            IdentifierType.NCT: "ClinicalTrials.gov Identifier",
            IdentifierType.SPONSOR_PROTOCOL: "Sponsor Protocol Number",
            IdentifierType.EUDRACT: "EudraCT Number",
            IdentifierType.IND: "FDA IND Number",
            IdentifierType.IDE: "FDA IDE Number",
            IdentifierType.ISRCTN: "ISRCTN Number",
            IdentifierType.CTIS: "EU CTIS Number",
            IdentifierType.WHO_UTN: "WHO Universal Trial Number",
            IdentifierType.OTHER: "Other Identifier",
        }
        return decodes.get(self.identifier_type, "Study Identifier")


@dataclass
class Organization:
    """USDM Organization entity."""
    id: str
    name: str
    type: OrganizationType
    identifier: Optional[str] = None
    identifier_scheme: Optional[str] = None
    label: Optional[str] = None
    # H1: Sponsor legal address
    address_city: Optional[str] = None
    address_state: Optional[str] = None
    address_country: Optional[str] = None
    address_postal_code: Optional[str] = None
    instance_type: str = "Organization"
    
    def to_dict(self) -> Dict[str, Any]:
        # USDM CT codelist C188724 via CodeRegistry
        term = _cr.match("organizationType", self.type.value) if self.type.value else None
        type_code = _cr.make_code("organizationType", term.code) if term else _cr.make_code("organizationType", "C54149")
        type_code["id"] = generate_uuid()
        
        result = {
            "id": self.id,
            "name": self.name,
            "type": type_code,
            "identifier": self.identifier or self.name,  # Required field
            "identifierScheme": self.identifier_scheme or "DUNS",  # Required field
            "instanceType": self.instance_type,
        }
        if self.label:
            result["label"] = self.label
        # H1: Emit legalAddress if any address component is present
        if any([self.address_city, self.address_state, self.address_country, self.address_postal_code]):
            addr_lines = []
            if self.address_city:
                addr_lines.append(self.address_city)
            if self.address_state:
                addr_lines.append(self.address_state)
            if self.address_country:
                addr_lines.append(self.address_country)
            if self.address_postal_code:
                addr_lines.append(self.address_postal_code)
            result["legalAddress"] = {
                "id": generate_uuid(),
                "text": ", ".join(addr_lines),
                "city": self.address_city or "",
                "district": self.address_state or "",
                "country": {
                    "id": generate_uuid(),
                    "code": self.address_country or "",
                    "codeSystem": "ISO 3166-1 alpha-3",
                    "codeSystemVersion": "2024",
                    "decode": self.address_country or "",
                    "instanceType": "Code",
                },
                "postalCode": self.address_postal_code or "",
                "instanceType": "Address",
            }
        return result


@dataclass
class StudyRole:
    """USDM StudyRole entity - links organizations to their roles in the study."""
    id: str
    name: str
    code: StudyRoleCode
    organization_ids: List[str] = field(default_factory=list)
    description: Optional[str] = None
    # M2: Assigned persons (e.g., PI name, medical monitor)
    assigned_persons: List[str] = field(default_factory=list)
    instance_type: str = "StudyRole"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "code": {"code": self.code.value, "codeSystem": "http://www.cdisc.org", "decode": self.code.value},
            "organizationIds": self.organization_ids,
            "instanceType": self.instance_type,
        }
        if self.description:
            result["description"] = self.description
        # M2: Emit assignedPersons
        if self.assigned_persons:
            result["assignedPersons"] = [
                {"id": generate_uuid(), "name": name, "instanceType": "AssignedPerson"}
                for name in self.assigned_persons
            ]
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
    
    # Phase string → NCI C-code mapping
    _PHASE_CODES: Dict[str, tuple] = field(default=None, init=False, repr=False)
    
    @staticmethod
    def _resolve_phase_code(phase_str: str) -> tuple:
        """Resolve a phase string to (C-code, decode)."""
        _map = {
            "phase 1": ("C15600", "Phase I Trial"),
            "phase i": ("C15600", "Phase I Trial"),
            "phase1": ("C15600", "Phase I Trial"),
            "phase 1/2": ("C15693", "Phase I/II Trial"),
            "phase i/ii": ("C15693", "Phase I/II Trial"),
            "phase 2": ("C15601", "Phase II Trial"),
            "phase ii": ("C15601", "Phase II Trial"),
            "phase2": ("C15601", "Phase II Trial"),
            "phase 2/3": ("C15694", "Phase II/III Trial"),
            "phase ii/iii": ("C15694", "Phase II/III Trial"),
            "phase 3": ("C15602", "Phase III Trial"),
            "phase iii": ("C15602", "Phase III Trial"),
            "phase3": ("C15602", "Phase III Trial"),
            "phase 4": ("C15603", "Phase IV Trial"),
            "phase iv": ("C15603", "Phase IV Trial"),
            "phase4": ("C15603", "Phase IV Trial"),
        }
        return _map.get(phase_str.lower().strip(), ("C48660", "Not Applicable"))
    
    def to_dict(self) -> Dict[str, Any]:
        c_code, decode = self._resolve_phase_code(self.phase)
        return {
            "id": generate_uuid(),
            "standardCode": {
                "id": generate_uuid(),
                "code": c_code,
                "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
                "codeSystemVersion": "25.01d",
                "decode": decode,
                "instanceType": "Code",
            },
            "standardCodeAliases": [],
            "instanceType": "AliasCode",
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
    
    # C2: Study rationale (USDM StudyVersion.rationale — required)
    study_rationale: Optional[str] = None
    
    # H2: Governance dates
    sponsor_approval_date: Optional[str] = None
    original_protocol_date: Optional[str] = None
    
    # G1: Planned enrollment number from synopsis
    planned_enrollment_number: Optional[int] = None
    
    # L1: Cross-reference identifiers
    reference_identifiers: List[Dict[str, str]] = field(default_factory=list)
    
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
        if self.study_rationale:
            result["studyRationale"] = self.study_rationale
        if self.sponsor_approval_date:
            result["sponsorApprovalDate"] = self.sponsor_approval_date
        if self.original_protocol_date:
            result["originalProtocolDate"] = self.original_protocol_date
        # G1: Planned enrollment number
        if self.planned_enrollment_number:
            result["plannedEnrollmentNumber"] = self.planned_enrollment_number
        # L1: Reference identifiers
        if self.reference_identifiers:
            result["referenceIdentifiers"] = self.reference_identifiers
            
        return result
