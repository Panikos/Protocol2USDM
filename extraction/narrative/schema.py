"""
Narrative Extraction Schema - Internal types for extraction pipeline.

These types are used during extraction and convert to official USDM types
(from core.usdm_types) when generating final output.

For official USDM types, see: core/usdm_types.py
Schema source: https://github.com/cdisc-org/DDF-RA/blob/main/Deliverables/UML/dataStructure.yml
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

from core.usdm_types import generate_uuid, Code


class SectionType(Enum):
    """Common protocol section types."""
    TITLE_PAGE = "Title Page"
    SYNOPSIS = "Synopsis"
    TABLE_OF_CONTENTS = "Table of Contents"
    ABBREVIATIONS = "Abbreviations"
    INTRODUCTION = "Introduction"
    OBJECTIVES = "Objectives"
    STUDY_DESIGN = "Study Design"
    POPULATION = "Study Population"
    ELIGIBILITY = "Eligibility Criteria"
    TREATMENT = "Treatment"
    STUDY_PROCEDURES = "Study Procedures"
    ASSESSMENTS = "Assessments"
    SAFETY = "Safety"
    DISCONTINUATION = "Discontinuation"
    STATISTICS = "Statistics"
    ETHICS = "Ethics"
    REFERENCES = "References"
    APPENDIX = "Appendix"
    OTHER = "Other"


@dataclass
class Abbreviation:
    """
    USDM Abbreviation entity.
    
    Represents an abbreviation used in the protocol.
    """
    id: str
    abbreviated_text: str  # e.g., "ECG"
    expanded_text: str     # e.g., "Electrocardiogram"
    instance_type: str = "Abbreviation"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "abbreviatedText": self.abbreviated_text,
            "expandedText": self.expanded_text,
            "instanceType": self.instance_type,
        }


@dataclass
class NarrativeContentItem:
    """
    USDM NarrativeContentItem entity.
    
    A subsection or paragraph within a NarrativeContent section.
    """
    id: str
    name: str
    text: str
    section_number: Optional[str] = None  # e.g., "5.1.2"
    section_title: Optional[str] = None
    order: int = 0
    instance_type: str = "NarrativeContentItem"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "text": self.text,
            "order": self.order,
            "instanceType": self.instance_type,
        }
        if self.section_number:
            result["sectionNumber"] = self.section_number
        if self.section_title:
            result["sectionTitle"] = self.section_title
        return result


@dataclass
class NarrativeContent:
    """
    USDM NarrativeContent entity.
    
    Represents a major section of the protocol document.
    """
    id: str
    name: str
    section_number: Optional[str] = None  # e.g., "5"
    section_title: Optional[str] = None   # e.g., "Study Procedures"
    section_type: Optional[SectionType] = None
    text: Optional[str] = None            # Full section text if available
    child_ids: List[str] = field(default_factory=list)  # NarrativeContentItem IDs
    order: int = 0
    instance_type: str = "NarrativeContent"
    
    def to_dict(self) -> Dict[str, Any]:
        # USDM requires name and text fields to be non-empty strings
        effective_name = self.name if self.name else f"Section {self.order + 1}"
        effective_text = self.text if self.text else effective_name
        
        result = {
            "id": self.id,
            "name": effective_name,
            "text": effective_text,  # Required field
            "order": self.order,
            "instanceType": self.instance_type,
        }
        if self.section_number:
            result["sectionNumber"] = self.section_number
        if self.section_title:
            result["sectionTitle"] = self.section_title
        if self.section_type:
            result["sectionType"] = {
                "id": generate_uuid(),
                "code": self.section_type.value,
                "codeSystem": "USDM",
                "codeSystemVersion": "2024-09-27",
                "decode": self.section_type.value,
                "instanceType": "Code",
            }
        if self.child_ids:
            result["childIds"] = self.child_ids
        return result


@dataclass
class StudyDefinitionDocument:
    """
    USDM StudyDefinitionDocument entity.
    
    Represents the protocol document itself.
    """
    id: str
    name: str
    version: Optional[str] = None
    version_date: Optional[str] = None
    document_type: str = "Protocol"
    language: str = "en"
    content_ids: List[str] = field(default_factory=list)  # NarrativeContent IDs
    instance_type: str = "StudyDefinitionDocument"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "documentType": self.document_type,
            "language": self.language,
            "instanceType": self.instance_type,
        }
        if self.version:
            result["version"] = self.version
        if self.version_date:
            result["versionDate"] = self.version_date
        if self.content_ids:
            result["contentIds"] = self.content_ids
        return result


@dataclass
class NarrativeData:
    """
    Aggregated narrative structure extraction result.
    
    Contains all Phase 7 entities for a protocol.
    """
    document: Optional[StudyDefinitionDocument] = None
    sections: List[NarrativeContent] = field(default_factory=list)
    items: List[NarrativeContentItem] = field(default_factory=list)
    abbreviations: List[Abbreviation] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to USDM-compatible dictionary structure."""
        result = {
            "narrativeContents": [s.to_dict() for s in self.sections],
            "narrativeContentItems": [i.to_dict() for i in self.items],
            "abbreviations": [a.to_dict() for a in self.abbreviations],
            "summary": {
                "sectionCount": len(self.sections),
                "itemCount": len(self.items),
                "abbreviationCount": len(self.abbreviations),
            }
        }
        if self.document:
            result["studyDefinitionDocument"] = self.document.to_dict()
        return result
