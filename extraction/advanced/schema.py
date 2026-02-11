"""
Advanced Extraction Schema - Internal types for extraction pipeline.

These types are used during extraction and convert to official USDM types
(from core.usdm_types) when generating final output.

For official USDM types, see: core/usdm_types.py
Schema source: https://github.com/cdisc-org/DDF-RA/blob/main/Deliverables/UML/dataStructure.yml
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

from core.usdm_types import generate_uuid, Code


class AmendmentScope(Enum):
    """Scope of a protocol amendment."""
    GLOBAL = "Global"
    COUNTRY_SPECIFIC = "Country Specific"
    SITE_SPECIFIC = "Site Specific"


@dataclass
class AmendmentReason:
    """
    USDM AmendmentReason entity.
    
    Describes why an amendment was made.
    """
    id: str
    code: str  # e.g., "SAFETY", "EFFICACY", "REGULATORY"
    description: str
    instance_type: str = "AmendmentReason"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "code": self.code,
            "description": self.description,
            "instanceType": self.instance_type,
        }


@dataclass
class StudyAmendment:
    """
    USDM StudyAmendment entity.
    
    Represents a protocol amendment.
    """
    id: str
    number: str  # Amendment number (e.g., "1", "2")
    summary: Optional[str] = None
    effective_date: Optional[str] = None
    scope: AmendmentScope = AmendmentScope.GLOBAL
    reason_ids: List[str] = field(default_factory=list)
    previous_version: Optional[str] = None
    new_version: Optional[str] = None
    instance_type: str = "StudyAmendment"
    
    def to_dict(self) -> Dict[str, Any]:
        # USDM requires: name, primaryReason, geographicScopes
        result = {
            "id": self.id,
            "number": self.number,
            "name": f"Amendment {self.number}",  # Required field
            "scope": {
                "id": generate_uuid(),
                "code": self.scope.value,
                "codeSystem": "USDM",
                "codeSystemVersion": "2024-09-27",
                "decode": self.scope.value,
                "instanceType": "Code",
            },
            "primaryReason": {  # Required field - Code object with nested standardCode
                "id": generate_uuid(),
                "code": {  # Nested Code object
                    "id": generate_uuid(),
                    "code": "C132347",
                    "codeSystem": "http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl",
                    "codeSystemVersion": "25.01d",
                    "decode": "Protocol Amendment",
                    "instanceType": "Code",
                },
                "otherReason": "Protocol Amendment",
                "instanceType": "StudyAmendmentReason",
            },
            "geographicScopes": [{  # Required field - at least one
                "id": generate_uuid(),
                "type": {
                    "id": generate_uuid(),
                    "code": self.scope.value,
                    "codeSystem": "USDM",
                    "codeSystemVersion": "2024-09-27",
                    "decode": self.scope.value,
                    "instanceType": "Code",
                },
                "instanceType": "GeographicScope",
            }],
            "instanceType": self.instance_type,
        }
        # summary is required in USDM 4.0
        result["summary"] = self.summary if self.summary else f"Amendment {self.number} to the protocol"
        if self.effective_date:
            result["effectiveDate"] = self.effective_date
        if self.reason_ids:
            result["reasonIds"] = self.reason_ids
        if self.previous_version:
            result["previousVersion"] = self.previous_version
        if self.new_version:
            result["newVersion"] = self.new_version
        return result


@dataclass
class Country:
    """
    USDM Country entity.
    
    Represents a country where the study is conducted.
    """
    id: str
    name: str
    code: Optional[str] = None  # ISO 3166-1 alpha-2 or alpha-3
    region: Optional[str] = None  # e.g., "Europe", "North America"
    instance_type: str = "Country"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "instanceType": self.instance_type,
        }
        if self.code:
            result["code"] = self.code
        if self.region:
            result["region"] = self.region
        return result


@dataclass
class StudySite:
    """
    USDM StudySite entity.
    
    Represents a clinical study site.
    """
    id: str
    name: str
    site_number: Optional[str] = None
    country_id: Optional[str] = None
    city: Optional[str] = None
    instance_type: str = "StudySite"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "instanceType": self.instance_type,
        }
        if self.site_number:
            result["siteNumber"] = self.site_number
        if self.country_id:
            result["countryId"] = self.country_id
        if self.city:
            result["city"] = self.city
        return result


@dataclass
class GeographicScope:
    """
    USDM GeographicScope entity.
    
    Defines the geographic scope of the study.
    """
    id: str
    name: str
    scope_type: str = "Global"  # Global, Regional, Country
    country_ids: List[str] = field(default_factory=list)
    site_ids: List[str] = field(default_factory=list)
    regions: List[str] = field(default_factory=list)
    instance_type: str = "GeographicScope"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "scopeType": self.scope_type,
            "instanceType": self.instance_type,
        }
        if self.country_ids:
            result["countryIds"] = self.country_ids
        if self.site_ids:
            result["siteIds"] = self.site_ids
        if self.regions:
            result["regions"] = self.regions
        return result


@dataclass
class AdvancedData:
    """
    Aggregated advanced entities extraction result.
    
    Contains all Phase 8 entities for a protocol.
    """
    amendments: List[StudyAmendment] = field(default_factory=list)
    amendment_reasons: List[AmendmentReason] = field(default_factory=list)
    geographic_scope: Optional[GeographicScope] = None
    countries: List[Country] = field(default_factory=list)
    sites: List[StudySite] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to USDM-compatible dictionary structure."""
        result = {
            "studyAmendments": [a.to_dict() for a in self.amendments],
            "amendmentReasons": [r.to_dict() for r in self.amendment_reasons],
            "countries": [c.to_dict() for c in self.countries],
            "studySites": [s.to_dict() for s in self.sites],
            "summary": {
                "amendmentCount": len(self.amendments),
                "countryCount": len(self.countries),
                "siteCount": len(self.sites),
            }
        }
        if self.geographic_scope:
            result["geographicScope"] = self.geographic_scope.to_dict()
        return result
