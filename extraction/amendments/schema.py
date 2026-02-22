"""
Amendments Extraction Schema - Internal types for extraction pipeline.

These types are used during extraction and convert to official USDM types
(from core.usdm_types) when generating final output.

For official USDM types, see: core/usdm_types.py
Schema source: https://github.com/cdisc-org/DDF-RA/blob/main/Deliverables/UML/dataStructure.yml
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

from core.usdm_types import generate_uuid, Code


class ImpactLevel(Enum):
    """Level of amendment impact."""
    UNKNOWN = ""  # Not extracted from source
    MAJOR = "Major"
    MINOR = "Minor"
    ADMINISTRATIVE = "Administrative"


class ChangeType(Enum):
    """Type of protocol change."""
    UNKNOWN = ""  # Not extracted from source
    ADDITION = "Addition"
    DELETION = "Deletion"
    MODIFICATION = "Modification"
    CLARIFICATION = "Clarification"


class ReasonCategory(Enum):
    """Category of amendment reason."""
    UNKNOWN = ""  # Not extracted from source
    SAFETY = "Safety"
    EFFICACY = "Efficacy"
    REGULATORY = "Regulatory"
    OPERATIONAL = "Operational"
    SCIENTIFIC = "Scientific"
    ADMINISTRATIVE = "Administrative"


@dataclass
class StudyAmendmentImpact:
    """
    USDM StudyAmendmentImpact entity.
    Describes which sections/entities are affected by an amendment.
    """
    id: str
    amendment_id: str
    affected_section: str
    impact_level: ImpactLevel = ImpactLevel.MINOR
    description: Optional[str] = None
    affected_entity_ids: List[str] = field(default_factory=list)
    instance_type: str = "StudyAmendmentImpact"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": {
                "id": generate_uuid(),
                "code": "C17649",
                "codeSystem": "http://www.cdisc.org",
                "codeSystemVersion": "2024-09-27",
                "decode": self.impact_level.value or "Other",
                "instanceType": "Code",
            },
            "text": self.description or self.affected_section or "Amendment impact",
            "isSubstantial": self.impact_level in (ImpactLevel.MAJOR,),
            "instanceType": self.instance_type,
        }


@dataclass
class StudyAmendmentReason:
    """
    USDM StudyAmendmentReason entity.
    Rationale for making a protocol amendment.
    """
    id: str
    amendment_id: str
    reason_text: str
    category: ReasonCategory = ReasonCategory.OPERATIONAL
    is_primary: bool = False
    instance_type: str = "StudyAmendmentReason"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "code": {
                "id": generate_uuid(),
                "code": "C17649",
                "codeSystem": "http://www.cdisc.org",
                "codeSystemVersion": "2024-09-27",
                "decode": self.category.value or "Other",
                "instanceType": "Code",
            },
            "otherReason": self.reason_text,
            "instanceType": self.instance_type,
        }


@dataclass
class StudyChange:
    """
    USDM StudyChange entity.
    Specific before/after change in an amendment.
    """
    id: str
    amendment_id: str
    change_type: ChangeType = ChangeType.MODIFICATION
    section_number: Optional[str] = None
    before_text: Optional[str] = None
    after_text: Optional[str] = None
    summary: Optional[str] = None
    instance_type: str = "StudyChange"
    
    def to_dict(self) -> Dict[str, Any]:
        from core.usdm_types_generated import generate_uuid
        name = self.summary or f"{self.change_type.value} in {self.section_number or 'protocol'}"
        rationale = self.after_text or self.before_text or name
        summary = self.summary or name
        sec_num = self.section_number or "N/A"
        sec_title = f"Section {sec_num}" if sec_num != "N/A" else "Protocol"
        changed_sections = [{
            "id": generate_uuid(),
            "sectionNumber": sec_num,
            "sectionTitle": sec_title,
            "appliesToId": self.amendment_id,
            "instanceType": "DocumentContentReference",
        }]
        return {
            "id": self.id,
            "name": name,
            "label": name,
            "description": rationale,
            "summary": summary,
            "rationale": rationale,
            "changedSections": changed_sections,
            "instanceType": self.instance_type,
        }


@dataclass
class AmendmentDetailsData:
    """Container for amendment details extraction results."""
    impacts: List[StudyAmendmentImpact] = field(default_factory=list)
    reasons: List[StudyAmendmentReason] = field(default_factory=list)
    changes: List[StudyChange] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "studyAmendmentImpacts": [i.to_dict() for i in self.impacts],
            "studyAmendmentReasons": [r.to_dict() for r in self.reasons],
            "studyChanges": [c.to_dict() for c in self.changes],
            "summary": {
                "impactCount": len(self.impacts),
                "reasonCount": len(self.reasons),
                "changeCount": len(self.changes),
            }
        }


@dataclass
class AmendmentDetailsResult:
    """Result container for amendment details extraction."""
    success: bool
    data: Optional[AmendmentDetailsData] = None
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
            result["amendmentDetails"] = self.data.to_dict()
        if self.error:
            result["error"] = self.error
        return result
