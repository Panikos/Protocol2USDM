"""
Document Structure & Narrative Extraction Module - Phase 7 of USDM Expansion

Extracts document structure elements from protocol:
- NarrativeContent (section text)
- NarrativeContentItem (subsections)
- Abbreviation
- StudyDefinitionDocument
- M11 section mapping
"""

from .extractor import (
    extract_narrative_structure,
    NarrativeExtractionResult,
)
from .schema import (
    NarrativeData,
    NarrativeContent,
    NarrativeContentItem,
    Abbreviation,
    StudyDefinitionDocument,
)
from .m11_mapper import (
    map_sections_to_m11,
    build_m11_narrative,
    M11MappingResult,
    M11_TEMPLATE,
)

__all__ = [
    # Main extraction function
    "extract_narrative_structure",
    "NarrativeExtractionResult",
    # Schema classes
    "NarrativeData",
    "NarrativeContent",
    "NarrativeContentItem",
    "Abbreviation",
    "StudyDefinitionDocument",
    # M11 mapping
    "map_sections_to_m11",
    "build_m11_narrative",
    "M11MappingResult",
    "M11_TEMPLATE",
]
