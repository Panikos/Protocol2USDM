"""
Document Structure Extraction Schema - Internal types for extraction pipeline.

These types are used during extraction and convert to official USDM types
(from core.usdm_types) when generating final output.

For official USDM types, see: core/usdm_types.py
Schema source: https://github.com/cdisc-org/DDF-RA/blob/main/Deliverables/UML/dataStructure.yml
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

from core.usdm_types import generate_uuid, Code


class AnnotationType(Enum):
    """Types of annotations."""
    FOOTNOTE = "Footnote"
    COMMENT = "Comment"
    NOTE = "Note"
    CLARIFICATION = "Clarification"
    REFERENCE = "Reference"


@dataclass
class DocumentContentReference:
    """
    USDM DocumentContentReference entity.
    References to specific sections or content within the protocol.
    """
    id: str
    name: str
    section_number: Optional[str] = None
    section_title: Optional[str] = None
    page_number: Optional[int] = None
    target_id: Optional[str] = None  # ID of referenced entity
    description: Optional[str] = None
    instance_type: str = "DocumentContentReference"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "instanceType": self.instance_type,
        }
        if self.section_number:
            result["sectionNumber"] = self.section_number
        if self.section_title:
            result["sectionTitle"] = self.section_title
        if self.page_number:
            result["pageNumber"] = self.page_number
        if self.target_id:
            result["targetId"] = self.target_id
        if self.description:
            result["description"] = self.description
        return result


@dataclass
class CommentAnnotation:
    """
    USDM CommentAnnotation entity.
    Footnotes, comments, and annotations in the protocol.
    """
    id: str
    text: str
    annotation_type: AnnotationType = AnnotationType.FOOTNOTE
    source_section: Optional[str] = None
    page_number: Optional[int] = None
    instance_type: str = "CommentAnnotation"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "text": self.text,
            "annotationType": self.annotation_type.value,
            "instanceType": self.instance_type,
        }
        if self.source_section:
            result["sourceSection"] = self.source_section
        if self.page_number:
            result["pageNumber"] = self.page_number
        return result


@dataclass
class StudyDefinitionDocumentVersion:
    """
    USDM StudyDefinitionDocumentVersion entity.
    Version information for the protocol document.
    """
    id: str
    version_number: str
    version_date: Optional[str] = None
    status: str = "Final"  # Draft, Final, Approved
    description: Optional[str] = None
    amendment_number: Optional[str] = None
    instance_type: str = "StudyDefinitionDocumentVersion"
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "versionNumber": self.version_number,
            "status": self.status,
            "instanceType": self.instance_type,
        }
        if self.version_date:
            result["versionDate"] = self.version_date
        if self.description:
            result["description"] = self.description
        if self.amendment_number:
            result["amendmentNumber"] = self.amendment_number
        return result


@dataclass
class DocumentStructureData:
    """Container for document structure extraction results."""
    content_references: List[DocumentContentReference] = field(default_factory=list)
    annotations: List[CommentAnnotation] = field(default_factory=list)
    document_versions: List[StudyDefinitionDocumentVersion] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "documentContentReferences": [r.to_dict() for r in self.content_references],
            "commentAnnotations": [a.to_dict() for a in self.annotations],
            "studyDefinitionDocumentVersions": [v.to_dict() for v in self.document_versions],
            "summary": {
                "referenceCount": len(self.content_references),
                "annotationCount": len(self.annotations),
                "versionCount": len(self.document_versions),
            }
        }


@dataclass
class DocumentStructureResult:
    """Result container for document structure extraction."""
    success: bool
    data: Optional[DocumentStructureData] = None
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
            result["documentStructure"] = self.data.to_dict()
        if self.error:
            result["error"] = self.error
        return result
