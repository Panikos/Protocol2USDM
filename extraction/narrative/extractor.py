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
    """Extract abbreviations using LLM with retry logic for truncation."""
    prompt = build_abbreviations_extraction_prompt(protocol_text)
    
    # Retry logic for truncated responses
    max_retries = 3
    accumulated_response = ""
    
    for attempt in range(max_retries + 1):
        if attempt == 0:
            current_prompt = prompt
        else:
            logger.info(f"Abbreviations retry {attempt}/{max_retries}: Requesting continuation...")
            # Find a good merge point - last complete line ending with comma or bracket
            merge_point = accumulated_response.rfind(',\n')
            if merge_point == -1:
                merge_point = accumulated_response.rfind('[\n')
            if merge_point == -1:
                merge_point = max(0, len(accumulated_response) - 500)
            
            context = accumulated_response[merge_point:] if merge_point > 0 else accumulated_response[-500:]
            current_prompt = (
                f"Your previous response was truncated. Here is the end:\n\n"
                f"```json\n{context}\n```\n\n"
                f"Continue EXACTLY from where you left off. Output ONLY the remaining JSON to complete the array/object. "
                f"Do NOT repeat any content. Start your response with the next item or closing bracket."
            )
        
        response = call_llm(prompt=current_prompt, model_name=model_name, json_mode=True, extractor_name="narrative")
        
        if 'error' in response:
            logger.warning(f"Abbreviation extraction failed: {response['error']}")
            return None
        
        response_text = response.get('response', '')
        
        if attempt > 0 and response_text:
            # Smart merge: find overlap and concatenate
            merged = _smart_merge_json(accumulated_response, response_text)
            accumulated_response = merged
            result = _parse_json_response(accumulated_response)
            if result:
                logger.info(f"Successfully parsed abbreviations after {attempt} continuation(s)")
                return result
        else:
            accumulated_response = response_text
            result = _parse_json_response(response_text)
            if result:
                return result
            # Check if truncated
            if response_text and not response_text.rstrip().endswith('}'):
                continue
            break
    
    return None


def _smart_merge_json(base: str, continuation: str) -> str:
    """Merge truncated JSON with continuation, handling overlaps."""
    base = base.rstrip()
    continuation = continuation.lstrip()
    
    # Remove markdown code blocks from continuation
    if continuation.startswith('```'):
        lines = continuation.split('\n')
        continuation = '\n'.join(lines[1:])
        if continuation.rstrip().endswith('```'):
            continuation = continuation.rstrip()[:-3].rstrip()
    
    # If continuation starts with closing brackets, append directly
    if continuation and continuation[0] in '}]':
        return base + continuation
    
    # If base ends mid-string or mid-value, try to find merge point
    # Look for overlap (continuation might repeat some content)
    for overlap_len in range(min(100, len(base), len(continuation)), 10, -10):
        if base.endswith(continuation[:overlap_len]):
            return base + continuation[overlap_len:]
    
    # No overlap found - check if we need a comma
    if base and continuation:
        # If base ends with value and continuation starts with new item
        if base[-1] in '"}0123456789' and continuation[0] == '{':
            return base + ',\n' + continuation
        if base[-1] == ',' or continuation[0] == ',':
            return base + continuation
    
    return base + continuation


def _extract_structure(protocol_text: str, model_name: str) -> Optional[Dict]:
    """Extract document structure using LLM with retry logic for truncation."""
    prompt = build_structure_extraction_prompt(protocol_text)
    
    # Retry logic for truncated responses
    max_retries = 3
    accumulated_response = ""
    
    for attempt in range(max_retries + 1):
        if attempt == 0:
            current_prompt = prompt
        else:
            logger.info(f"Structure retry {attempt}/{max_retries}: Requesting continuation...")
            # Find a good merge point - last complete line ending with comma or bracket
            merge_point = accumulated_response.rfind(',\n')
            if merge_point == -1:
                merge_point = accumulated_response.rfind('[\n')
            if merge_point == -1:
                merge_point = max(0, len(accumulated_response) - 500)
            
            context = accumulated_response[merge_point:] if merge_point > 0 else accumulated_response[-500:]
            current_prompt = (
                f"Your previous response was truncated. Here is the end:\n\n"
                f"```json\n{context}\n```\n\n"
                f"Continue EXACTLY from where you left off. Output ONLY the remaining JSON to complete the array/object. "
                f"Do NOT repeat any content. Start your response with the next item or closing bracket."
            )
        
        response = call_llm(prompt=current_prompt, model_name=model_name, json_mode=True, extractor_name="narrative")
        
        if 'error' in response:
            logger.warning(f"Structure extraction failed: {response['error']}")
            return None
        
        response_text = response.get('response', '')
        
        if attempt > 0 and response_text:
            # Smart merge: find overlap and concatenate
            merged = _smart_merge_json(accumulated_response, response_text)
            accumulated_response = merged
            result = _parse_json_response(accumulated_response)
            if result:
                logger.info(f"Successfully parsed structure after {attempt} continuation(s)")
                return result
        else:
            accumulated_response = response_text
            result = _parse_json_response(response_text)
            if result:
                return result
            # Check if truncated
            if response_text and not response_text.rstrip().endswith('}'):
                continue
            break
    
    return None


def _parse_json_response(response_text: str) -> Optional[Dict[str, Any]]:
    """Parse JSON from LLM response, handling markdown code blocks and repairing common errors."""
    if not response_text:
        return None
        
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
    if json_match:
        response_text = json_match.group(1)
    
    response_text = response_text.strip()
    
    try:
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        # Try to repair common JSON errors
        repaired = _repair_json(response_text)
        if repaired:
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass
        logger.warning(f"Failed to parse JSON response: {e}")
        return None


def _repair_json(text: str) -> Optional[str]:
    """Attempt to repair common JSON syntax errors."""
    if not text:
        return None
    
    # Fix missing commas between array elements: }{ -> },{
    text = re.sub(r'\}\s*\{', '},{', text)
    
    # Fix missing commas between array elements: "]["  -> ],[ 
    text = re.sub(r'\]\s*\[', '],[', text)
    
    # Fix missing commas after strings followed by quotes: ""\s*" -> "", "
    text = re.sub(r'"\s*\n\s*"', '",\n"', text)
    
    # Fix trailing commas before closing brackets: ,] -> ]
    text = re.sub(r',\s*\]', ']', text)
    text = re.sub(r',\s*\}', '}', text)
    
    # Try to close unclosed arrays/objects
    open_braces = text.count('{') - text.count('}')
    open_brackets = text.count('[') - text.count(']')
    
    if open_braces > 0:
        text = text.rstrip() + '}' * open_braces
    if open_brackets > 0:
        text = text.rstrip() + ']' * open_brackets
    
    return text


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
