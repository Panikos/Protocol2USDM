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


class ReferenceType(Enum):
    """Types of inline cross-references found in protocol text."""
    SECTION = "Section"
    TABLE = "Table"
    FIGURE = "Figure"
    APPENDIX = "Appendix"
    LISTING = "Listing"
    OTHER = "Other"


class FigureContentType(Enum):
    """Types of visual content in the protocol PDF."""
    FIGURE = "Figure"
    TABLE = "Table"
    DIAGRAM = "Diagram"
    CHART = "Chart"
    FLOWCHART = "Flowchart"
    IMAGE = "Image"


@dataclass
class InlineCrossReference:
    """
    An inline cross-reference found in narrative text.
    e.g. "see Section 5.2", "refer to Table 3-1", "Figure 1".
    """
    id: str
    source_section: str           # Section number where the reference appears
    target_label: str             # Raw text of the target (e.g. "Section 5.2", "Table 3-1")
    target_section: Optional[str] = None   # Resolved section number (e.g. "5.2")
    target_id: Optional[str] = None        # Resolved NarrativeContent entity ID
    reference_type: ReferenceType = ReferenceType.SECTION
    context_text: Optional[str] = None     # Surrounding sentence fragment
    instance_type: str = "InlineCrossReference"

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "sourceSection": self.source_section,
            "targetLabel": self.target_label,
            "referenceType": self.reference_type.value,
            "instanceType": self.instance_type,
        }
        if self.target_section:
            result["targetSection"] = self.target_section
        if self.target_id:
            result["targetId"] = self.target_id
        if self.context_text:
            result["contextText"] = self.context_text
        return result


@dataclass
class ProtocolFigure:
    """
    A figure, table, diagram, or image detected in the protocol PDF.
    Stores metadata and a path to the rendered page image.
    """
    id: str
    label: str                    # e.g. "Figure 1", "Table 3-1"
    title: Optional[str] = None   # e.g. "Study Schema"
    page_number: Optional[int] = None  # 0-indexed PDF page
    section_number: Optional[str] = None
    content_type: FigureContentType = FigureContentType.FIGURE
    image_path: Optional[str] = None   # Relative path to rendered PNG
    instance_type: str = "ProtocolFigure"

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "label": self.label,
            "contentType": self.content_type.value,
            "instanceType": self.instance_type,
        }
        if self.title:
            result["title"] = self.title
        if self.page_number is not None:
            result["pageNumber"] = self.page_number
        if self.section_number:
            result["sectionNumber"] = self.section_number
        if self.image_path:
            result["imagePath"] = self.image_path
        return result


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
    inline_references: List[InlineCrossReference] = field(default_factory=list)
    figures: List[ProtocolFigure] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "documentContentReferences": [r.to_dict() for r in self.content_references],
            "commentAnnotations": [a.to_dict() for a in self.annotations],
            "studyDefinitionDocumentVersions": [v.to_dict() for v in self.document_versions],
            "inlineCrossReferences": [r.to_dict() for r in self.inline_references],
            "protocolFigures": [f.to_dict() for f in self.figures],
            "summary": {
                "referenceCount": len(self.content_references),
                "annotationCount": len(self.annotations),
                "versionCount": len(self.document_versions),
                "inlineReferenceCount": len(self.inline_references),
                "figureCount": len(self.figures),
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
