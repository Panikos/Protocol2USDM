"""
Document Structure & Narrative Extractor - Phase 7 of USDM Expansion

Extracts document structure and abbreviations from protocol.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

from core.llm_client import call_llm
from core.pdf_utils import extract_text_from_pages, get_page_count
from .schema import (
    NarrativeData,
    NarrativeContent,
    NarrativeContentItem,
    Abbreviation,
    StudyDefinitionDocument,
    SectionType,
)
from .prompts import build_abbreviations_extraction_prompt, build_structure_extraction_prompt

logger = logging.getLogger(__name__)


@dataclass
class NarrativeExtractionResult:
    """Result of narrative structure extraction."""
    success: bool
    data: Optional[NarrativeData] = None
    raw_response: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    pages_used: List[int] = field(default_factory=list)
    model_used: Optional[str] = None


def find_structure_pages(
    pdf_path: str,
    max_pages: int = 30,
) -> List[int]:
    """
    Find pages containing document structure (TOC, abbreviations).
    Usually in the first 10-20 pages, but SoA abbreviations may be on page 16+.
    """
    import fitz
    
    structure_keywords = [
        r'table\s+of\s+contents',
        r'list\s+of\s+abbreviations',
        r'abbreviations?\s+and\s+definitions?',
        r'abbreviations\s*:',  # SoA table abbreviations format
        r'glossary',
        r'synopsis',
        r'protocol\s+summary',
        r'schedule\s+of\s+activities',  # Include SoA pages for abbreviations
    ]
    
    pattern = re.compile('|'.join(structure_keywords), re.IGNORECASE)
    
    structure_pages = []
    
    try:
        doc = fitz.open(pdf_path)
        total_pages = min(len(doc), max_pages)
        
        for page_num in range(total_pages):
            page = doc[page_num]
            text = page.get_text().lower()
            
            if pattern.search(text):
                structure_pages.append(page_num)
        
        doc.close()
        
        # If nothing found, use first 10 pages
        if not structure_pages:
            structure_pages = list(range(min(10, get_page_count(pdf_path))))
        
        logger.info(f"Found {len(structure_pages)} structure pages")
        
    except Exception as e:
        logger.error(f"Error scanning PDF: {e}")
        structure_pages = list(range(min(10, max_pages)))
        
    return structure_pages


def extract_narrative_structure(
    pdf_path: str,
    model_name: str = "gemini-2.5-pro",
    pages: Optional[List[int]] = None,
    protocol_text: Optional[str] = None,
    extract_abbreviations: bool = True,
    extract_sections: bool = True,
) -> NarrativeExtractionResult:
    """
    Extract document structure and abbreviations from a protocol PDF.
    """
    result = NarrativeExtractionResult(success=False, model_used=model_name)
    
    try:
        # Auto-detect structure pages if not specified
        if pages is None:
            pages = find_structure_pages(pdf_path)
        
        result.pages_used = pages
        
        # Extract text from pages
        if protocol_text is None:
            logger.info(f"Extracting text from pages {pages}...")
            protocol_text = extract_text_from_pages(pdf_path, pages)
        
        if not protocol_text:
            result.error = "Failed to extract text from PDF"
            return result
        
        abbreviations = []
        sections = []
        document = None
        raw_responses = {}
        
        # Extract abbreviations
        if extract_abbreviations:
            logger.info("Extracting abbreviations...")
            abbrev_result = _extract_abbreviations(protocol_text, model_name)
            if abbrev_result:
                abbreviations = abbrev_result.get("abbreviations", [])
                raw_responses["abbreviations"] = abbrev_result
        
        # Extract document structure
        if extract_sections:
            logger.info("Extracting document structure...")
            struct_result = _extract_structure(protocol_text, model_name)
            if struct_result:
                sections = struct_result.get("sections", [])
                document = struct_result.get("document")
                raw_responses["structure"] = struct_result
        
        result.raw_response = raw_responses
        
        # Convert to structured data
        result.data = _build_narrative_data(abbreviations, sections, document)
        result.success = result.data is not None
        
        if result.success:
            logger.info(
                f"Extracted {len(result.data.abbreviations)} abbreviations, "
                f"{len(result.data.sections)} sections"
            )
        
    except Exception as e:
        logger.error(f"Narrative extraction failed: {e}")
        result.error = str(e)
        
    return result


def _extract_abbreviations(protocol_text: str, model_name: str) -> Optional[Dict]:
    """Extract abbreviations using LLM."""
    prompt = build_abbreviations_extraction_prompt(protocol_text)
    
    response = call_llm(prompt=prompt, model_name=model_name, json_mode=True)
    
    if 'error' in response:
        logger.warning(f"Abbreviation extraction failed: {response['error']}")
        return None
    
    return _parse_json_response(response.get('response', ''))


def _extract_structure(protocol_text: str, model_name: str) -> Optional[Dict]:
    """Extract document structure using LLM."""
    prompt = build_structure_extraction_prompt(protocol_text)
    
    response = call_llm(prompt=prompt, model_name=model_name, json_mode=True)
    
    if 'error' in response:
        logger.warning(f"Structure extraction failed: {response['error']}")
        return None
    
    return _parse_json_response(response.get('response', ''))


def _parse_json_response(response_text: str) -> Optional[Dict[str, Any]]:
    """Parse JSON from LLM response, handling markdown code blocks."""
    if not response_text:
        return None
        
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
    if json_match:
        response_text = json_match.group(1)
    
    response_text = response_text.strip()
    
    try:
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON response: {e}")
        return None


def _build_narrative_data(
    abbreviations_raw: List[Dict],
    sections_raw: List[Dict],
    document_raw: Optional[Dict],
) -> NarrativeData:
    """Build NarrativeData from raw extraction results.
    
    Handles both legacy format and new USDM-compliant format.
    """
    
    # Process abbreviations - accept multiple key names
    abbreviations = []
    for i, abbr in enumerate(abbreviations_raw):
        if isinstance(abbr, dict):
            # Accept multiple key variations
            abbrev_text = abbr.get('abbreviation') or abbr.get('abbreviatedText') or abbr.get('text')
            expand_text = abbr.get('expansion') or abbr.get('expandedText') or abbr.get('definition')
            
            if abbrev_text and expand_text:
                abbreviations.append(Abbreviation(
                    id=abbr.get('id', f"abbr_{i+1}"),
                    abbreviated_text=abbrev_text,
                    expanded_text=expand_text,
                ))
    
    # Process sections - accept multiple key names
    sections = []
    items = []
    section_ids = []
    
    for i, sec in enumerate(sections_raw):
        if not isinstance(sec, dict):
            continue
        
        # Use provided ID or generate one
        section_id = sec.get('id', f"nc_{i+1}")
        section_ids.append(section_id)
        
        # Process subsections
        child_ids = []
        for j, sub in enumerate(sec.get('subsections', [])):
            if isinstance(sub, dict):
                item_id = f"nci_{i+1}_{j+1}"
                child_ids.append(item_id)
                items.append(NarrativeContentItem(
                    id=item_id,
                    name=sub.get('title', f'Section {sub.get("number", "")}'),
                    text="",  # Text not extracted in this phase
                    section_number=sub.get('number'),
                    section_title=sub.get('title'),
                    order=j,
                ))
        
        section_type = _map_section_type(sec.get('type', 'Other'))
        
        sections.append(NarrativeContent(
            id=section_id,
            name=sec.get('title', f'Section {sec.get("number", "")}'),
            section_number=sec.get('number'),
            section_title=sec.get('title'),
            section_type=section_type,
            child_ids=child_ids,
            order=i,
        ))
    
    # Process document
    document = None
    if document_raw and isinstance(document_raw, dict):
        document = StudyDefinitionDocument(
            id="sdd_1",
            name=document_raw.get('title', 'Clinical Protocol'),
            version=document_raw.get('version'),
            version_date=document_raw.get('versionDate'),
            content_ids=section_ids,
        )
    
    return NarrativeData(
        document=document,
        sections=sections,
        items=items,
        abbreviations=abbreviations,
    )


def _map_section_type(type_str: str) -> SectionType:
    """Map string to SectionType enum."""
    type_lower = type_str.lower()
    
    mappings = {
        'synopsis': SectionType.SYNOPSIS,
        'introduction': SectionType.INTRODUCTION,
        'objective': SectionType.OBJECTIVES,
        'design': SectionType.STUDY_DESIGN,
        'population': SectionType.POPULATION,
        'eligibility': SectionType.ELIGIBILITY,
        'treatment': SectionType.TREATMENT,
        'procedure': SectionType.STUDY_PROCEDURES,
        'assessment': SectionType.ASSESSMENTS,
        'safety': SectionType.SAFETY,
        'statistic': SectionType.STATISTICS,
        'ethic': SectionType.ETHICS,
        'reference': SectionType.REFERENCES,
        'appendix': SectionType.APPENDIX,
        'abbreviation': SectionType.ABBREVIATIONS,
        'title': SectionType.TITLE_PAGE,
        'content': SectionType.TABLE_OF_CONTENTS,
    }
    
    for key, value in mappings.items():
        if key in type_lower:
            return value
    
    return SectionType.OTHER


def save_narrative_result(
    result: NarrativeExtractionResult,
    output_path: str,
) -> None:
    """Save narrative extraction result to JSON file."""
    output = {
        "success": result.success,
        "pagesUsed": result.pages_used,
        "modelUsed": result.model_used,
    }
    
    if result.data:
        output["narrative"] = result.data.to_dict()
    if result.error:
        output["error"] = result.error
    if result.raw_response:
        output["rawResponse"] = result.raw_response
        
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Saved narrative structure to {output_path}")
