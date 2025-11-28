"""
Document Structure Extraction Module - Phase 12

Extracts USDM entities:
- DocumentContentReference
- CommentAnnotation
- StudyDefinitionDocumentVersion
"""

from .schema import (
    DocumentContentReference,
    CommentAnnotation,
    StudyDefinitionDocumentVersion,
    DocumentStructureData,
    DocumentStructureResult,
    AnnotationType,
)
from .extractor import extract_document_structure

__all__ = [
    'DocumentContentReference',
    'CommentAnnotation',
    'StudyDefinitionDocumentVersion',
    'DocumentStructureData',
    'DocumentStructureResult',
    'AnnotationType',
    'extract_document_structure',
]
