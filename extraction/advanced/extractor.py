"""
Advanced Entities Extractor - Phase 8 of USDM Expansion

Extracts amendments, geographic scope, and sites from protocol.
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
    AdvancedData,
    StudyAmendment,
    AmendmentReason,
    GeographicScope,
    Country,
    StudySite,
    AmendmentScope,
)
from .prompts import build_advanced_extraction_prompt

logger = logging.getLogger(__name__)


@dataclass
class AdvancedExtractionResult:
    """Result of advanced entities extraction."""
    success: bool
    data: Optional[AdvancedData] = None
    raw_response: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    pages_used: List[int] = field(default_factory=list)
    model_used: Optional[str] = None


def find_advanced_pages(
    pdf_path: str,
    max_pages: int = 100,  # Increased to search more of the document
) -> List[int]:
    """
    Find pages containing amendment history, geographic scope, or sites.
    
    Amendment history is often near the END of protocols, so we search
    the entire document, not just the first 30 pages.
    """
    import fitz
    
    # Keywords to find amendment-related pages
    amendment_keywords = [
        r'amendment\s+history',
        r'protocol\s+amendment\s+history',
        r'overall\s+rationale\s+for\s+the\s+amendment',
        r'changes\s+to\s+the\s+protocol',
        r'summary\s+of\s+changes',
        r'document\s+history',
    ]
    
    other_keywords = [
        r'protocol\s+amendment',
        r'version\s+history',
        r'participating\s+countries',
        r'geographic\s+scope',
        r'study\s+sites?',
        r'investigator\s+sites?',
    ]
    
    amendment_pattern = re.compile('|'.join(amendment_keywords), re.IGNORECASE)
    other_pattern = re.compile('|'.join(other_keywords), re.IGNORECASE)
    
    found_pages = []
    amendment_pages = []
    
    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        
        # Always include first few pages (title, current amendment summary often there)
        found_pages = [0, 1, 2, 3]
        
        # Search ENTIRE document for amendment history (often at end)
        for page_num in range(total_pages):
            page = doc[page_num]
            text = page.get_text().lower()
            
            # Priority: amendment history pages
            if amendment_pattern.search(text):
                amendment_pages.append(page_num)
            # Also include other relevant pages (limited)
            elif other_pattern.search(text) and page_num < 30:
                if page_num not in found_pages:
                    found_pages.append(page_num)
        
        # Add all amendment history pages (these contain the detailed summaries)
        found_pages.extend(amendment_pages)
        
        doc.close()
        found_pages = sorted(set(found_pages))
        
        logger.info(f"Found {len(found_pages)} advanced entity pages "
                   f"(including {len(amendment_pages)} amendment history pages)")
        
    except Exception as e:
        logger.error(f"Error scanning PDF: {e}")
        found_pages = list(range(min(10, 30)))
        
    return found_pages


def extract_advanced_entities(
    pdf_path: str,
    model_name: str = "gemini-2.5-pro",
    pages: Optional[List[int]] = None,
    protocol_text: Optional[str] = None,
    upstream_context: Optional[str] = None,
) -> AdvancedExtractionResult:
    """
    Extract advanced entities from a protocol PDF.
    """
    result = AdvancedExtractionResult(success=False, model_used=model_name)
    
    try:
        # Auto-detect pages if not specified
        if pages is None:
            pages = find_advanced_pages(pdf_path)
        
        result.pages_used = pages
        
        # Extract text from pages
        if protocol_text is None:
            logger.info(f"Extracting text from pages {pages}...")
            protocol_text = extract_text_from_pages(pdf_path, pages)
        
        if not protocol_text:
            result.error = "Failed to extract text from PDF"
            return result
        
        # Call LLM for extraction
        logger.info("Extracting advanced entities with LLM...")
        prompt = build_advanced_extraction_prompt(protocol_text)
        if upstream_context:
            prompt = (
                "## Already-Extracted Study Context\n"
                "The following entities have already been extracted from this protocol. "
                "Use this context to ensure consistency with previously extracted data.\n\n"
                f"{upstream_context}\n\n{prompt}"
            )
        
        response = call_llm(prompt=prompt, model_name=model_name, json_mode=True, extractor_name="advanced")
        
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
        result.data = _build_advanced_data(raw_response)
        result.success = result.data is not None
        
        if result.success:
            logger.info(
                f"Extracted {len(result.data.amendments)} amendments, "
                f"{len(result.data.countries)} countries"
            )
        
    except Exception as e:
        logger.error(f"Advanced extraction failed: {e}")
        result.error = str(e)
        
    return result


def _parse_json_response(response_text: str) -> Optional[Dict[str, Any]]:
    """Parse JSON from LLM response, handling markdown code blocks."""
    if not response_text:
        return None
        
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
    if json_match:
        response_text = json_match.group(1)
    
    response_text = response_text.strip()
    
    try:
        result = json.loads(response_text)
        # Handle case where LLM returns a list instead of a dict
        if isinstance(result, list):
            if len(result) == 1 and isinstance(result[0], dict):
                return result[0]
            # Wrap list in expected structure
            return {'amendments': result}
        return result
    except json.JSONDecodeError as e:
        # Try to extract just the first JSON object if there's extra data
        if 'Extra data' in str(e):
            try:
                # Find the first complete JSON object
                decoder = json.JSONDecoder()
                result, _ = decoder.raw_decode(response_text)
                if isinstance(result, list) and len(result) == 1:
                    return result[0]
                return result if isinstance(result, dict) else {'amendments': result}
            except Exception:
                pass
        logger.warning(f"Failed to parse JSON response: {e}")
        return None


def _build_advanced_data(raw: Dict[str, Any]) -> AdvancedData:
    """Build AdvancedData from raw extraction results.
    
    Handles both legacy format and new USDM-compliant format with ids.
    """
    
    if raw is None:
        return AdvancedData()
    
    amendments = []
    amendment_reasons = []
    countries = []
    sites = []
    geo_scope = None
    
    # Process amendments - accept both 'amendments' and 'studyAmendments' keys
    amendments_raw = raw.get('amendments') or raw.get('studyAmendments') or []
    amend_idx = 0
    for amend in amendments_raw:
        if not isinstance(amend, dict):
            continue
        
        amend_number = str(amend.get('number', ''))
        
        # Skip "Original Protocol" - it's not an amendment
        if 'original' in amend_number.lower():
            continue
        
        amend_idx += 1
        
        # Process reasons
        reason_ids = []
        reasons_raw = amend.get('reasons') or amend.get('reasonIds') or []
        for j, reason in enumerate(reasons_raw):
            reason_id = f"ar_{amend_idx}_{j+1}"
            reason_ids.append(reason_id)
            amendment_reasons.append(AmendmentReason(
                id=reason_id,
                code=reason.upper() if isinstance(reason, str) else "OTHER",
                description=reason if isinstance(reason, str) else str(reason),
            ))
        
        amendments.append(StudyAmendment(
            id=amend.get('id', f"amend_{amend_idx}"),
            number=amend_number,
            summary=amend.get('summary'),
            effective_date=amend.get('effectiveDate'),
            previous_version=amend.get('previousVersion'),
            new_version=amend.get('newVersion'),
            reason_ids=reason_ids,
        ))
    
    # Process geographic scope - also check for top-level 'countries' key
    geo_data = raw.get('geographicScope') or {}
    countries_raw = []
    
    if isinstance(geo_data, dict) and geo_data:
        countries_raw = geo_data.get('countries') or []
    
    # Also check for top-level countries array (USDM format)
    if not countries_raw:
        countries_raw = raw.get('countries') or []
    
    country_ids = []
    for i, country in enumerate(countries_raw):
        if isinstance(country, dict):
            country_id = country.get('id', f"country_{i+1}")
            country_ids.append(country_id)
            countries.append(Country(
                id=country_id,
                name=country.get('name', f'Country {i+1}'),
                code=country.get('code'),
            ))
        elif isinstance(country, str):
            country_id = f"country_{i+1}"
            country_ids.append(country_id)
            countries.append(Country(
                id=country_id,
                name=country,
            ))
    
    if isinstance(geo_data, dict) and geo_data:
        
        geo_scope = GeographicScope(
            id="geo_1",
            name="Study Geographic Scope",
            scope_type=geo_data.get('type') or 'Global',
            country_ids=country_ids,
            regions=geo_data.get('regions') or [],
        )
    
    # Process sites
    sites_raw = raw.get('sites') or []
    for i, site in enumerate(sites_raw):
        if not isinstance(site, dict):
            continue
        
        # Find country name/code for Code object
        site_country = site.get('country', '')
        country_code = None
        country_name = site_country
        for c in countries:
            if c.name.lower() == site_country.lower():
                country_code = c.code
                country_name = c.name
                break
        
        sites.append(StudySite(
            id=f"site_{i+1}",
            name=site.get('name', f'Site {i+1}'),
            site_number=site.get('number'),
            country_code=country_code,
            country_name=country_name if country_name else None,
            city=site.get('city'),
        ))
    
    return AdvancedData(
        amendments=amendments,
        amendment_reasons=amendment_reasons,
        geographic_scope=geo_scope,
        countries=countries,
        sites=sites,
    )


def save_advanced_result(
    result: AdvancedExtractionResult,
    output_path: str,
) -> None:
    """Save advanced extraction result to JSON file."""
    output = {
        "success": result.success,
        "pagesUsed": result.pages_used,
        "modelUsed": result.model_used,
    }
    
    if result.data:
        output["advanced"] = result.data.to_dict()
    if result.error:
        output["error"] = result.error
    if result.raw_response:
        output["rawResponse"] = result.raw_response
        
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Saved advanced entities to {output_path}")
