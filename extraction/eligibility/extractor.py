"""
Eligibility Criteria Extractor - Phase 1 of USDM Expansion

Extracts inclusion and exclusion criteria from protocol Section 4-5.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from core.llm_client import call_llm
from core.pdf_utils import extract_text_from_pages, get_page_count
from .schema import (
    EligibilityData,
    EligibilityCriterion,
    EligibilityCriterionItem,
    StudyDesignPopulation,
    CriterionCategory,
)
from .prompts import build_eligibility_extraction_prompt

logger = logging.getLogger(__name__)


@dataclass
class EligibilityExtractionResult:
    """Result of eligibility criteria extraction."""
    success: bool
    data: Optional[EligibilityData] = None
    raw_response: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    pages_used: List[int] = field(default_factory=list)
    model_used: Optional[str] = None


def find_eligibility_pages(
    pdf_path: str,
    max_pages_to_scan: int = 50,
) -> List[int]:
    """
    Find pages containing eligibility criteria using heuristics.
    
    Looks for pages that contain actual criteria content (numbered items
    after section headers), not just TOC references.
    
    Args:
        pdf_path: Path to the protocol PDF
        max_pages_to_scan: Maximum pages to scan from start
        
    Returns:
        List of 0-indexed page numbers likely containing eligibility criteria
    """
    import fitz
    
    # Patterns for section headers followed by numbered criteria
    content_patterns = [
        # Section header followed by numbered items
        r'inclusion\s+criteria\s*\n.*?(?:1\.|i1|a\))',
        r'exclusion\s+criteria\s*\n.*?(?:1\.|e1|a\))',
        # Criteria with typical formatting
        r'(?:participants?|subjects?)\s+(?:must|aged|with)\s+',
        r'(?:diagnosis|history)\s+of\s+',
        r'(?:≥|>=|≤|<=)\s*\d+\s*(?:years?|months?|kg|mg)',
    ]
    
    # Keywords that indicate TOC or reference pages (exclude these)
    toc_indicators = [
        r'table\s+of\s+contents',
        r'\.{5,}',  # Dotted lines typical in TOC
        r'page\s+\d+\s+of\s+\d+.*page\s+\d+\s+of\s+\d+',  # Multiple page numbers
    ]
    
    content_pattern = re.compile('|'.join(content_patterns), re.IGNORECASE | re.DOTALL)
    toc_pattern = re.compile('|'.join(toc_indicators), re.IGNORECASE)
    
    eligibility_pages = []
    
    try:
        doc = fitz.open(pdf_path)
        total_pages = min(len(doc), max_pages_to_scan)
        
        for page_num in range(total_pages):
            page = doc[page_num]
            text = page.get_text()
            text_lower = text.lower()
            
            # Skip TOC pages
            if toc_pattern.search(text):
                continue
            
            # Look for actual eligibility content
            has_header = ('inclusion criteria' in text_lower or 
                         'exclusion criteria' in text_lower or
                         'eligibility criteria' in text_lower)
            has_content = content_pattern.search(text_lower)
            
            if has_header and has_content:
                eligibility_pages.append(page_num)
                logger.debug(f"Found eligibility content on page {page_num + 1}")
        
        doc.close()
        
        # If we found pages, also include adjacent pages for context
        if eligibility_pages:
            expanded = set()
            for p in eligibility_pages:
                expanded.add(p)
                if p > 0:
                    expanded.add(p - 1)
                if p < total_pages - 1:
                    expanded.add(p + 1)
            eligibility_pages = sorted(expanded)
        
        logger.info(f"Found {len(eligibility_pages)} potential eligibility pages")
        
    except Exception as e:
        logger.error(f"Error scanning PDF: {e}")
        
    return eligibility_pages


def extract_eligibility_criteria(
    pdf_path: str,
    model_name: str = "gemini-2.5-pro",
    pages: Optional[List[int]] = None,
    protocol_text: Optional[str] = None,
    study_indication: Optional[str] = None,
    study_phase: Optional[str] = None,
) -> EligibilityExtractionResult:
    """
    Extract eligibility criteria from a protocol PDF.
    
    Args:
        pdf_path: Path to the protocol PDF
        model_name: LLM model to use
        pages: Specific pages to use (0-indexed), auto-detected if None
        protocol_text: Optional pre-extracted text
        study_indication: Indication from metadata for context
        study_phase: Study phase from metadata for context
        
    Returns:
        EligibilityExtractionResult with extracted criteria
    """
    result = EligibilityExtractionResult(success=False, model_used=model_name)
    
    try:
        # Auto-detect eligibility pages if not specified
        if pages is None:
            pages = find_eligibility_pages(pdf_path)
            if not pages:
                # Fallback to first 20 pages if no eligibility keywords found
                logger.warning("No eligibility pages detected, scanning first 20 pages")
                pages = list(range(min(20, get_page_count(pdf_path))))
        
        result.pages_used = pages
        
        # Extract text from pages
        if protocol_text is None:
            logger.info(f"Extracting text from pages {pages}...")
            protocol_text = extract_text_from_pages(pdf_path, pages)
        
        if not protocol_text:
            result.error = "Failed to extract text from PDF"
            return result
        
        # Call LLM for extraction
        logger.info("Extracting eligibility criteria with LLM...")
        
        # Build context hints from prior extractions
        context_hints = ""
        if study_indication:
            context_hints += f"\nStudy indication: {study_indication}"
        if study_phase:
            context_hints += f"\nStudy phase: {study_phase}"
        
        prompt = build_eligibility_extraction_prompt(protocol_text, context_hints=context_hints)
        
        response = call_llm(
            prompt=prompt,
            model_name=model_name,
            json_mode=True,
        )
        
        if 'error' in response:
            result.error = response['error']
            return result
        
        # Parse response
        raw_response = _parse_json_response(response.get('response', ''))
        if not raw_response:
            result.error = "Failed to parse LLM response as JSON"
            return result
        
        result.raw_response = raw_response
        
        # Convert to structured data
        result.data = _parse_eligibility_response(raw_response)
        result.success = result.data is not None
        
        if result.success:
            logger.info(
                f"Extracted {result.data.inclusion_count} inclusion and "
                f"{result.data.exclusion_count} exclusion criteria"
            )
        
    except Exception as e:
        logger.error(f"Eligibility extraction failed: {e}")
        result.error = str(e)
        
    return result


def _parse_json_response(response_text: str) -> Optional[Dict[str, Any]]:
    """Parse JSON from LLM response, handling markdown code blocks."""
    if not response_text:
        return None
        
    # Try to extract JSON from markdown code blocks
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
    if json_match:
        response_text = json_match.group(1)
    
    response_text = response_text.strip()
    
    try:
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON response: {e}")
        return None


def _parse_usdm_eligibility_format(raw: Dict[str, Any]) -> Optional[EligibilityData]:
    """Parse new USDM-compliant format with flat criteria list."""
    try:
        criterion_items = []
        criteria = []
        
        inclusion_count = 0
        exclusion_count = 0
        inc_prev_id = None
        exc_prev_id = None
        
        # Build item lookup from eligibilityCriterionItems if present
        item_lookup = {}
        for item in raw.get('eligibilityCriterionItems', []):
            if isinstance(item, dict) and item.get('id'):
                item_lookup[item['id']] = item
        
        for crit_data in raw.get('criteria', []):
            if not isinstance(crit_data, dict):
                continue
            
            # Get category from code object
            category_data = crit_data.get('category', {})
            category_code = category_data.get('code', 'Inclusion') if isinstance(category_data, dict) else str(category_data)
            
            is_inclusion = 'Inclusion' in category_code
            category = CriterionCategory.INCLUSION if is_inclusion else CriterionCategory.EXCLUSION
            
            # Use provided ID or generate one
            crit_id = crit_data.get('id', f"ec_{len(criteria)+1}")
            identifier = crit_data.get('identifier', f"[{len(criteria)+1}]")
            name = crit_data.get('name', f"Criterion {len(criteria)+1}")
            
            # Get text - either from criterion directly or from linked criterionItem
            text = crit_data.get('text', '')
            item_id = crit_data.get('criterionItemId')
            
            if not text and item_id and item_id in item_lookup:
                # Get text from the linked criterion item
                item_data = item_lookup[item_id]
                text = item_data.get('text', '')
                name = item_data.get('name', name)
            
            if not text:
                continue
            
            # Create criterion item
            if not item_id:
                item_id = f"eci_{crit_id}"
            
            criterion_items.append(EligibilityCriterionItem(
                id=item_id,
                name=name,
                text=text,
            ))
            
            # Create criterion with linked list
            prev_id = inc_prev_id if is_inclusion else exc_prev_id
            
            criterion = EligibilityCriterion(
                id=crit_id,
                identifier=identifier,
                category=category,
                criterion_item_id=item_id,
                name=name,
                previous_id=prev_id,
            )
            
            # Link previous criterion to this one
            if prev_id:
                for c in criteria:
                    if c.id == prev_id:
                        c.next_id = crit_id
                        break
            
            criteria.append(criterion)
            
            # Update counters and prev_id
            if is_inclusion:
                inclusion_count += 1
                inc_prev_id = crit_id
            else:
                exclusion_count += 1
                exc_prev_id = crit_id
        
        # Parse population if present, linking to all criteria
        population = None
        pop_data = raw.get('population')
        if isinstance(pop_data, dict) and pop_data.get('description'):
            population = StudyDesignPopulation(
                id=pop_data.get('id', 'pop_1'),
                name=pop_data.get('name', 'Study Population'),
                description=pop_data['description'],
                criterion_ids=[c.id for c in criteria],  # Link to all criteria
            )
        elif criteria:
            # Create default population with criterion IDs even if no population data
            population = StudyDesignPopulation(
                id='pop_1',
                name='Study Population',
                description='Target population defined by eligibility criteria',
                criterion_ids=[c.id for c in criteria],
            )
        
        logger.info(f"Parsed USDM format: {inclusion_count} inclusion, {exclusion_count} exclusion criteria")
        
        return EligibilityData(
            criteria=criteria,
            criterion_items=criterion_items,
            population=population,
            inclusion_count=inclusion_count,
            exclusion_count=exclusion_count,
        )
        
    except Exception as e:
        logger.error(f"Failed to parse USDM eligibility format: {e}")
        return None


def _parse_eligibility_response(raw: Dict[str, Any]) -> Optional[EligibilityData]:
    """Parse raw LLM response into EligibilityData object.
    
    Handles two formats:
    1. New USDM format: flat 'criteria' list with 'category' code objects
    2. Legacy format: separate 'inclusionCriteria' and 'exclusionCriteria' arrays
    """
    try:
        # Check for new USDM-compliant format (flat criteria list with category codes)
        # Accept both 'criteria' and 'eligibilityCriteria' keys
        criteria_list = raw.get('criteria') or raw.get('eligibilityCriteria') or []
        if criteria_list and isinstance(criteria_list, list) and len(criteria_list) > 0:
            first_crit = criteria_list[0]
            if isinstance(first_crit, dict) and 'category' in first_crit and isinstance(first_crit.get('category'), dict):
                # Use a modified raw dict with 'criteria' key for the parser
                modified_raw = dict(raw)
                modified_raw['criteria'] = criteria_list
                return _parse_usdm_eligibility_format(modified_raw)
        
        criterion_items = []
        criteria = []
        
        # Legacy format: Process inclusion criteria
        inclusion_list = raw.get('inclusionCriteria', [])
        prev_id = None
        
        for i, crit in enumerate(inclusion_list):
            if not isinstance(crit, dict):
                continue
                
            text = crit.get('text', '').strip()
            if not text:
                continue
            
            identifier = crit.get('identifier', f'I{i+1}')
            name = crit.get('name', f'Inclusion Criterion {i+1}')
            
            # Create criterion item
            item_id = f"eci_{identifier.lower()}"
            criterion_items.append(EligibilityCriterionItem(
                id=item_id,
                name=name,
                text=text,
            ))
            
            # Create criterion
            crit_id = f"ec_{identifier.lower()}"
            criterion = EligibilityCriterion(
                id=crit_id,
                identifier=identifier,
                category=CriterionCategory.INCLUSION,
                criterion_item_id=item_id,
                name=name,
                previous_id=prev_id,
            )
            
            # Link previous criterion to this one
            if criteria and criteria[-1].category == CriterionCategory.INCLUSION:
                criteria[-1].next_id = crit_id
            
            criteria.append(criterion)
            prev_id = crit_id
        
        inclusion_count = len([c for c in criteria if c.category == CriterionCategory.INCLUSION])
        
        # Process exclusion criteria
        exclusion_list = raw.get('exclusionCriteria', [])
        prev_id = None
        
        for i, crit in enumerate(exclusion_list):
            if not isinstance(crit, dict):
                continue
                
            text = crit.get('text', '').strip()
            if not text:
                continue
            
            identifier = crit.get('identifier', f'E{i+1}')
            name = crit.get('name', f'Exclusion Criterion {i+1}')
            
            # Create criterion item
            item_id = f"eci_{identifier.lower()}"
            criterion_items.append(EligibilityCriterionItem(
                id=item_id,
                name=name,
                text=text,
            ))
            
            # Create criterion
            crit_id = f"ec_{identifier.lower()}"
            criterion = EligibilityCriterion(
                id=crit_id,
                identifier=identifier,
                category=CriterionCategory.EXCLUSION,
                criterion_item_id=item_id,
                name=name,
                previous_id=prev_id,
            )
            
            # Link previous exclusion criterion to this one
            if prev_id:
                for c in criteria:
                    if c.id == prev_id:
                        c.next_id = crit_id
                        break
            
            criteria.append(criterion)
            prev_id = crit_id
        
        exclusion_count = len([c for c in criteria if c.category == CriterionCategory.EXCLUSION])
        
        # Process population info
        population = None
        pop_data = raw.get('population', {})
        if pop_data:
            criterion_ids = [c.id for c in criteria]
            
            # Parse sex
            sex_list = pop_data.get('sex', [])
            if isinstance(sex_list, str):
                sex_list = [sex_list]
            
            population = StudyDesignPopulation(
                id="pop_1",
                name="Study Population",
                includes_healthy_subjects=pop_data.get('includesHealthySubjects', False),
                planned_enrollment_number=pop_data.get('plannedEnrollment'),
                planned_minimum_age=pop_data.get('minimumAge'),
                planned_maximum_age=pop_data.get('maximumAge'),
                planned_sex=sex_list if sex_list else None,
                criterion_ids=criterion_ids,
            )
        
        return EligibilityData(
            criterion_items=criterion_items,
            criteria=criteria,
            population=population,
            inclusion_count=inclusion_count,
            exclusion_count=exclusion_count,
        )
        
    except Exception as e:
        logger.error(f"Failed to parse eligibility response: {e}")
        return None


def save_eligibility_result(
    result: EligibilityExtractionResult,
    output_path: str,
) -> None:
    """Save eligibility extraction result to JSON file."""
    output = {
        "success": result.success,
        "pagesUsed": result.pages_used,
        "modelUsed": result.model_used,
    }
    
    if result.data:
        output["eligibility"] = result.data.to_dict()
    if result.error:
        output["error"] = result.error
    if result.raw_response:
        output["rawResponse"] = result.raw_response
        
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Saved eligibility criteria to {output_path}")
