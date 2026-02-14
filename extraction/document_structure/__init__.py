"""
Document Structure Extraction Module - Phase 12

Extracts USDM entities:
- DocumentContentReference
- CommentAnnotation
- StudyDefinitionDocumentVersion
- InlineCrossReference (cross-references in narrative text)
- ProtocolFigure (figures, tables, diagrams from PDF)
"""

from .schema import (
    DocumentContentReference,
    CommentAnnotation,
    StudyDefinitionDocumentVersion,
    DocumentStructureData,
    DocumentStructureResult,
    AnnotationType,
    ReferenceType,
    FigureContentType,
    InlineCrossReference,
    ProtocolFigure,
)
from .extractor import extract_document_structure
from .reference_scanner import (
    scan_inline_references,
    scan_pdf_for_figures,
    render_figure_images,
    link_references_to_narratives,
    assign_figures_to_sections,
)

__all__ = [
    'DocumentContentReference',
    'CommentAnnotation',
    'StudyDefinitionDocumentVersion',
    'DocumentStructureData',
    'DocumentStructureResult',
    'AnnotationType',
    'ReferenceType',
    'FigureContentType',
    'InlineCrossReference',
    'ProtocolFigure',
    'extract_document_structure',
    'scan_inline_references',
    'scan_pdf_for_figures',
    'render_figure_images',
    'link_references_to_narratives',
    'assign_figures_to_sections',
]
