"""
USDM Schema definitions for Amendment Detail entities.

Based on USDM v4.0 specification.
Phase 13: StudyAmendmentImpact, StudyAmendmentReason, StudyChange
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class ImpactLevel(Enum):
    """Level of amendment impact."""
    MAJOR = "Major"
    MINOR = "Minor"
    ADMINISTRATIVE = "Administrative"


class ChangeType(Enum):
    """Type of protocol change."""
    ADDITION = "Addition"
    DELETION = "Deletion"
    MODIFICATION = "Modification"
    CLARIFICATION = "Clarification"


class ReasonCategory(Enum):
    """Category of amendment reason."""
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
        result = {
            "id": self.id,
            "amendmentId": self.amendment_id,
            "affectedSection": self.affected_section,
            "impactLevel": self.impact_level.value,
            "instanceType": self.instance_type,
        }
        if self.description:
            result["description"] = self.description
        if self.affected_entity_ids:
            result["affectedEntityIds"] = self.affected_entity_ids
        return result


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
            "amendmentId": self.amendment_id,
            "reasonText": self.reason_text,
            "category": self.category.value,
            "isPrimary": self.is_primary,
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
        result = {
            "id": self.id,
            "amendmentId": self.amendment_id,
            "changeType": self.change_type.value,
            "instanceType": self.instance_type,
        }
        if self.section_number:
            result["sectionNumber"] = self.section_number
        if self.before_text:
            result["beforeText"] = self.before_text
        if self.after_text:
            result["afterText"] = self.after_text
        if self.summary:
            result["summary"] = self.summary
        return result


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
