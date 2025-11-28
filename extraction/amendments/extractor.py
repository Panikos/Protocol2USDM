"""
Amendment Details Extractor - Phase 13 of USDM Expansion

Extracts StudyAmendmentImpact, StudyAmendmentReason, StudyChange.
"""

import json
import logging
import re
from pathlib import Path
from typing import List, Optional, Dict, Any

from core.llm_client import call_llm
from core.pdf_utils import extract_text_from_pages, get_page_count
from .schema import (
    AmendmentDetailsData,
    AmendmentDetailsResult,
    StudyAmendmentImpact,
    StudyAmendmentReason,
    StudyChange,
    ImpactLevel,
    ChangeType,
    ReasonCategory,
)
from .prompts import get_amendments_prompt, get_system_prompt

logger = logging.getLogger(__name__)


def find_amendment_pages(
    pdf_path: str,
    max_pages_to_scan: int = 60,
) -> List[int]:
    """
    Find pages containing amendment information.
    """
    import fitz
    
    amendment_keywords = [
        r'amendment',
        r'revision',
        r'change\s+log',
        r'change\s+history',
        r'document\s+history',
        r'modification',
        r'protocol\s+change',
        r'summary\s+of\s+changes',
        r'rationale',
        r'reason\s+for\s+change',
    ]
    
    pattern = re.compile('|'.join(amendment_keywords), re.IGNORECASE)
    
    amendment_pages = []
    
    try:
        doc = fitz.open(pdf_path)
        total_pages = min(len(doc), max_pages_to_scan)
        
        # Include first few pages (often have amendment summary)
        amendment_pages = [0, 1, 2]
        
        for page_num in range(total_pages):
            page = doc[page_num]
            text = page.get_text().lower()
            
            matches = len(pattern.findall(text))
            if matches >= 2 and page_num not in amendment_pages:
                amendment_pages.append(page_num)
        
        doc.close()
        
        amendment_pages = sorted(set(amendment_pages))
        if len(amendment_pages) > 15:
            amendment_pages = amendment_pages[:15]
        
        logger.info(f"Found {len(amendment_pages)} amendment pages")
        
    except Exception as e:
        logger.error(f"Error scanning PDF: {e}")
        amendment_pages = list(range(min(10, get_page_count(pdf_path))))
    
    return amendment_pages


def parse_impact_level(level_str: str) -> ImpactLevel:
    """Parse impact level string to enum."""
    level_map = {
        'major': ImpactLevel.MAJOR,
        'minor': ImpactLevel.MINOR,
        'administrative': ImpactLevel.ADMINISTRATIVE,
    }
    return level_map.get(level_str.lower(), ImpactLevel.MINOR)


def parse_change_type(type_str: str) -> ChangeType:
    """Parse change type string to enum."""
    type_map = {
        'addition': ChangeType.ADDITION,
        'deletion': ChangeType.DELETION,
        'modification': ChangeType.MODIFICATION,
        'clarification': ChangeType.CLARIFICATION,
    }
    return type_map.get(type_str.lower(), ChangeType.MODIFICATION)


def parse_reason_category(cat_str: str) -> ReasonCategory:
    """Parse reason category string to enum."""
    cat_map = {
        'safety': ReasonCategory.SAFETY,
        'efficacy': ReasonCategory.EFFICACY,
        'regulatory': ReasonCategory.REGULATORY,
        'operational': ReasonCategory.OPERATIONAL,
        'scientific': ReasonCategory.SCIENTIFIC,
        'administrative': ReasonCategory.ADMINISTRATIVE,
    }
    return cat_map.get(cat_str.lower(), ReasonCategory.OPERATIONAL)


def extract_amendment_details(
    pdf_path: str,
    model: str = "gemini-2.5-pro",
    output_dir: Optional[str] = None,
) -> AmendmentDetailsResult:
    """
    Extract amendment details from protocol PDF.
    """
    logger.info("Starting amendment details extraction...")
    
    pages = find_amendment_pages(pdf_path)
    
    text = extract_text_from_pages(pdf_path, pages)
    if not text:
        return AmendmentDetailsResult(
            success=False,
            error="Failed to extract text from PDF",
            pages_used=pages,
            model_used=model,
        )
    
    prompt = get_amendments_prompt(text)
    system_prompt = get_system_prompt()
    
    try:
        full_prompt = f"{system_prompt}\n\n{prompt}"
        result = call_llm(
            prompt=full_prompt,
            model_name=model,
            json_mode=True,
            temperature=0.1,
        )
        response = result.get('response', '')
        
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response
        
        raw_data = json.loads(json_str)
        
        # Parse impacts
        impacts = []
        for i in raw_data.get('impacts', []):
            impact = StudyAmendmentImpact(
                id=i.get('id', f"impact_{len(impacts)+1}"),
                amendment_id=i.get('amendmentId', 'amend_1'),
                affected_section=i.get('affectedSection', ''),
                impact_level=parse_impact_level(i.get('impactLevel', 'Minor')),
                description=i.get('description'),
                affected_entity_ids=i.get('affectedEntityIds', []),
            )
            impacts.append(impact)
        
        # Parse reasons
        reasons = []
        for r in raw_data.get('reasons', []):
            reason = StudyAmendmentReason(
                id=r.get('id', f"reason_{len(reasons)+1}"),
                amendment_id=r.get('amendmentId', 'amend_1'),
                reason_text=r.get('reasonText', ''),
                category=parse_reason_category(r.get('category', 'Operational')),
                is_primary=r.get('isPrimary', False),
            )
            reasons.append(reason)
        
        # Parse changes
        changes = []
        for c in raw_data.get('changes', []):
            change = StudyChange(
                id=c.get('id', f"change_{len(changes)+1}"),
                amendment_id=c.get('amendmentId', 'amend_1'),
                change_type=parse_change_type(c.get('changeType', 'Modification')),
                section_number=c.get('sectionNumber'),
                before_text=c.get('beforeText'),
                after_text=c.get('afterText'),
                summary=c.get('summary'),
            )
            changes.append(change)
        
        data = AmendmentDetailsData(
            impacts=impacts,
            reasons=reasons,
            changes=changes,
        )
        
        confidence = min(1.0, (len(impacts) + len(reasons) + len(changes)) / 10)
        
        result = AmendmentDetailsResult(
            success=True,
            data=data,
            pages_used=pages,
            model_used=model,
            confidence=confidence,
        )
        
        if output_dir:
            output_path = Path(output_dir) / "14_amendment_details.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
            logger.info(f"Saved amendment details to {output_path}")
        
        logger.info(f"Extracted {len(impacts)} impacts, {len(reasons)} reasons, {len(changes)} changes")
        
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response: {e}")
        return AmendmentDetailsResult(
            success=False,
            error=f"JSON parse error: {e}",
            pages_used=pages,
            model_used=model,
        )
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return AmendmentDetailsResult(
            success=False,
            error=str(e),
            pages_used=pages,
            model_used=model,
        )
