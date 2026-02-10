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
        
        # --- Strategy A: Full-PDF heading discovery ---
        # Scan the entire PDF for numbered section headings the LLM missed
        # from the TOC (which only covers the first ~30 pages).
        if sections:
            try:
                sections = _discover_sections_from_pdf(pdf_path, sections)
            except Exception as e:
                logger.warning(f"Full-PDF heading discovery failed (non-fatal): {e}")
        
        # --- Full-text extraction from PDF page ranges ---
        section_texts: Dict[str, str] = {}
        if sections:
            try:
                from core.pdf_utils import get_page_count
                total = get_page_count(pdf_path)
                section_pages = _find_section_pages(pdf_path, sections)
                if section_pages:
                    section_texts = _extract_section_texts(
                        pdf_path, sections, section_pages, total,
                    )
            except Exception as e:
                logger.warning(f"Full-text extraction failed (non-fatal): {e}")
        
        # --- Strategy B: Targeted LLM gap-filling ---
        # Detect which M11 sections are still empty and fill them via
        # targeted LLM calls on the later pages of the PDF.
        if sections and extract_sections:
            try:
                gaps = _detect_m11_gaps(sections, section_texts)
                if gaps:
                    logger.info(f"M11 gaps detected: {gaps}")
                    gap_sections, gap_texts = _fill_m11_gaps(
                        pdf_path, model_name, sections, section_texts, gaps,
                    )
                    if gap_sections:
                        # Merge gap-filled sections — avoid duplicating existing numbers
                        existing_nums = {s.get('number', '') for s in sections}
                        for gs in gap_sections:
                            if gs.get('number', '') not in existing_nums:
                                sections.append(gs)
                        section_texts.update(gap_texts)
                        logger.info(
                            f"After gap-fill: {len(sections)} sections, "
                            f"{len(section_texts)} with text"
                        )
            except Exception as e:
                logger.warning(f"M11 gap-filling failed (non-fatal): {e}")
        
        # Convert to structured data
        result.data = _build_narrative_data(abbreviations, sections, document, section_texts)
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


# ---------------------------------------------------------------------------
# Full-PDF heading discovery (Strategy A)
# ---------------------------------------------------------------------------

def _discover_sections_from_pdf(
    pdf_path: str,
    known_sections: List[Dict],
) -> List[Dict]:
    """
    Scan the full PDF for numbered section headings not found by the LLM.

    The LLM only sees TOC/synopsis pages (~30 pages), so it may miss sections
    that appear later in the document. This function scans every page for
    patterns like "7. Discontinuation" or "8  TRIAL ASSESSMENTS" and returns
    any newly discovered sections merged with the known ones.

    Returns the merged section list (known + discovered), sorted by number.
    """
    import fitz

    known_nums = {s.get('number', '') for s in known_sections}

    # Pattern: start-of-line, optional whitespace, section number (1-2 digits,
    # optionally with .N.N), followed by whitespace and title words (ALL CAPS
    # or Title Case, at least 2 words).
    heading_re = re.compile(
        r'(?:^|\n)\s*'
        r'(\d{1,2}(?:\.\d{1,2}){0,3})'   # section number
        r'\.?\s{1,6}'                       # separator
        r'([A-Z][A-Za-z,/\-&\' ]{4,80})',  # title (starts uppercase, 5-80 chars)
    )

    doc = fitz.open(pdf_path)
    total = len(doc)

    # Detect TOC pages (pages matching 5+ headings) to skip them
    page_heading_counts: Dict[int, int] = {}
    page_headings: Dict[int, List[tuple]] = {}
    for p in range(total):
        text = doc[p].get_text()
        matches = heading_re.findall(text)
        page_heading_counts[p] = len(matches)
        page_headings[p] = matches

    toc_pages = {p for p, count in page_heading_counts.items() if count >= 5}

    discovered: Dict[str, Dict] = {}
    for p in range(total):
        if p in toc_pages:
            continue
        for num, title in page_headings.get(p, []):
            num = num.rstrip('.')
            if num in known_nums or num in discovered:
                continue
            # Only accept sections with depth ≤ 3 (e.g. "7", "8.1", "8.1.1")
            depth = num.count('.') + 1
            if depth > 3:
                continue
            # Top-level number must be 1-14 (M11 range) to avoid false positives
            # like "24 Blood sampling" or "30 Randomization"
            top_level = num.split('.')[0]
            if top_level.isdigit() and int(top_level) > 14:
                continue
            # Clean title and require at least 2 words
            title = title.strip().rstrip('.')
            title_words = title.split()
            if len(title) < 5 or len(title_words) < 2:
                continue
            # Reject common false-positive patterns
            title_lower = title.lower()
            if any(fp in title_lower for fp in [
                'table ', 'figure ', 'page ', 'visit ', 'day ',
                'week ', 'month ', 'year ', 'dose ', 'mg ',
            ]):
                continue
            discovered[num] = {
                'number': num,
                'title': title,
                'type': _infer_section_type_from_title(title),
                'page': p + 1,  # 1-indexed for consistency with LLM output
                '_discovered_page0': p,  # 0-indexed page for direct use
            }

    doc.close()

    if discovered:
        logger.info(
            f"Discovered {len(discovered)} additional sections from full PDF scan: "
            f"{sorted(discovered.keys())}"
        )

    # Merge: known sections first, then discovered, sorted by number
    merged = list(known_sections)
    merged.extend(discovered.values())
    merged.sort(key=lambda s: [
        int(x) if x.isdigit() else 0
        for x in s.get('number', '0').split('.')
    ])
    return merged


# ---------------------------------------------------------------------------
# M11 gap-filling via targeted LLM (Strategy B)
# ---------------------------------------------------------------------------

# M11 section definitions for gap detection
_M11_SECTION_DEFS = {
    '1': 'Protocol Summary',
    '2': 'Introduction',
    '3': 'Objectives and Estimands',
    '4': 'Trial Design',
    '5': 'Study Population',
    '6': 'Study Intervention(s)',
    '7': 'Discontinuation of Trial Intervention and Participant Discontinuation/Withdrawal',
    '8': 'Trial Assessments and Procedures',
    '9': 'Adverse Events and Other Safety',
    '10': 'Statistics',
    '11': 'Oversight, Compliance, and Integrity',
    '12': 'Appendix: Supporting Information',
    '13': 'Appendix: Glossary of Terms and Abbreviations',
    '14': 'Appendix: References',
}


def _detect_m11_gaps(
    sections: List[Dict],
    section_texts: Dict[str, str],
) -> List[str]:
    """
    Detect which M11 sections have no narrative content after initial extraction.

    Uses the M11 mapper to determine coverage, returns list of M11 section
    numbers (e.g. ['7', '8', '9']) that are empty.
    """
    try:
        from .m11_mapper import map_sections_to_m11, build_m11_narrative
        mapping = map_sections_to_m11(sections, section_texts)
        m11_narrative = build_m11_narrative(sections, section_texts, mapping)

        gaps = []
        for m11_num in sorted(_M11_SECTION_DEFS.keys(), key=int):
            entry = m11_narrative.get(m11_num, {})
            if not entry.get('hasContent', False):
                gaps.append(m11_num)
        return gaps
    except Exception as e:
        logger.warning(f"M11 gap detection failed: {e}")
        return []


_M11_GAP_FILL_PROMPT = """You are an expert at extracting clinical protocol content.

I need you to extract the content that belongs to ICH M11 Section {m11_number}: "{m11_title}" from the following protocol text.

## What to extract for this section:
{section_guidance}

## Rules:
1. Extract VERBATIM text from the protocol — do not paraphrase or summarize
2. Include all relevant paragraphs, tables, and lists
3. If the content for this section is embedded within another section, extract just the relevant parts
4. If no content matches this section, return an empty string
5. Return ONLY a JSON object with the exact format below

## Output format:
```json
{{
  "sectionNumber": "{m11_number}",
  "sectionTitle": "{m11_title}",
  "text": "<extracted verbatim text here>",
  "sourcePages": "<page numbers where content was found, e.g. '45-52'>"
}}
```

## Protocol text:
{protocol_text}
"""

_M11_SECTION_GUIDANCE = {
    '7': (
        "Discontinuation/withdrawal content including:\n"
        "- Criteria for discontinuing trial intervention\n"
        "- Criteria for participant withdrawal from the trial\n"
        "- Lost to follow-up procedures\n"
        "- Stopping rules\n"
        "Look in sections about study population, study intervention, or study procedures."
    ),
    '8': (
        "Trial assessments and procedures including:\n"
        "- Efficacy assessments and procedures\n"
        "- Safety assessments and procedures\n"
        "- Laboratory tests and procedures\n"
        "- Imaging, ECG, vital signs\n"
        "- Pharmacokinetic/pharmacodynamic assessments\n"
        "Look in sections about study procedures, assessments, or clinical laboratory tests."
    ),
    '9': (
        "Adverse events and safety content including:\n"
        "- Definition of adverse events (AE) and serious adverse events (SAE)\n"
        "- AE recording and reporting procedures\n"
        "- Adverse events of special interest (AESI)\n"
        "- Pregnancy reporting\n"
        "- Safety reporting timelines\n"
        "- Follow-up of AEs and SAEs\n"
        "Look in sections about adverse events, safety, or pharmacovigilance."
    ),
    '11': (
        "Oversight, compliance, and integrity including:\n"
        "- Regulatory and ethical considerations\n"
        "- Informed consent process\n"
        "- Data protection and privacy\n"
        "- Committees (DMC, steering committee)\n"
        "- Quality management\n"
        "- Protocol deviations\n"
        "Look in sections about ethics, regulatory, oversight, or compliance."
    ),
    '12': (
        "Supporting appendix content including:\n"
        "- Country-specific requirements\n"
        "- Contraceptive guidance\n"
        "- Liver safety monitoring\n"
        "- COVID-19 considerations\n"
        "- Amendment history\n"
        "Look in appendices or supplementary sections."
    ),
}


def _fill_m11_gaps(
    pdf_path: str,
    model_name: str,
    sections: List[Dict],
    section_texts: Dict[str, str],
    gaps: List[str],
) -> tuple:
    """
    Fill M11 narrative gaps using targeted LLM calls.

    For each gap, sends relevant PDF pages to the LLM with a focused prompt
    asking it to extract content for that specific M11 section.

    Returns (new_sections, new_section_texts) to merge into the main data.
    """
    if not gaps:
        return [], {}

    # Only fill gaps where we have guidance (skip §1-§6 which should come from
    # structured extraction, and §13-§14 which are glossary/references)
    fillable = [g for g in gaps if g in _M11_SECTION_GUIDANCE or int(g) >= 7]

    if not fillable:
        return [], {}

    logger.info(f"Filling M11 narrative gaps via LLM: {fillable}")

    # Extract full PDF text for the LLM (pages after the first 30, where
    # most missing content lives). Cap at 60k chars to stay within context.
    from core.pdf_utils import get_page_count
    total_pages = get_page_count(pdf_path)
    # Use pages 20+ to capture content beyond TOC/synopsis
    late_pages = list(range(min(20, total_pages), total_pages))
    late_text = extract_text_from_pages(pdf_path, late_pages)
    if not late_text:
        logger.warning("Could not extract late-page text for gap filling")
        return [], {}

    # Cap text length for LLM context
    if len(late_text) > 60000:
        late_text = late_text[:60000] + "\n\n[...text truncated...]"

    new_sections = []
    new_texts: Dict[str, str] = {}

    for m11_num in fillable:
        m11_title = _M11_SECTION_DEFS.get(m11_num, f'Section {m11_num}')
        guidance = _M11_SECTION_GUIDANCE.get(
            m11_num,
            f"Extract all content relevant to {m11_title}."
        )

        prompt = _M11_GAP_FILL_PROMPT.format(
            m11_number=m11_num,
            m11_title=m11_title,
            section_guidance=guidance,
            protocol_text=late_text,
        )

        try:
            response = call_llm(
                prompt=prompt,
                model_name=model_name,
                json_mode=True,
                extractor_name="narrative_gap_fill",
            )

            if 'error' in response:
                logger.warning(f"Gap fill for M11 §{m11_num} failed: {response['error']}")
                continue

            result = _parse_json_response(response.get('response', ''))
            if not result:
                continue

            text = result.get('text', '').strip()
            if not text or len(text) < 20:
                logger.info(f"  M11 §{m11_num}: no content found in protocol")
                continue

            # Create a synthetic section for this M11 gap
            sec_id = f"m11_{m11_num}"
            new_sections.append({
                'number': m11_num,
                'title': m11_title,
                'type': _infer_section_type(m11_num),
                'page': None,
                '_synthetic': True,  # Flag: created by gap-fill, not from TOC
            })
            new_texts[m11_num] = text

            logger.info(
                f"  M11 §{m11_num} ({m11_title}): filled with {len(text)} chars"
            )

        except Exception as e:
            logger.warning(f"Gap fill for M11 §{m11_num} error: {e}")
            continue

    return new_sections, new_texts


def _infer_section_type_from_title(title: str) -> str:
    """Infer a section type string from the section title text."""
    title_lower = title.lower()
    mappings = {
        'synopsis': 'Synopsis', 'protocol summary': 'Synopsis',
        'introduction': 'Introduction', 'background': 'Introduction',
        'rationale': 'Introduction',
        'objective': 'Objectives', 'endpoint': 'Objectives',
        'estimand': 'Objectives',
        'study design': 'Study Design', 'overall design': 'Study Design',
        'trial design': 'Study Design',
        'population': 'Study Population', 'eligibility': 'Eligibility Criteria',
        'screen fail': 'Study Population',
        'intervention': 'Treatment', 'dosing': 'Treatment',
        'dose modif': 'Treatment', 'concomitant': 'Treatment',
        'discontinu': 'Discontinuation', 'withdraw': 'Discontinuation',
        'lost to follow': 'Discontinuation',
        'assessment': 'Assessments', 'procedure': 'Study Procedures',
        'efficacy': 'Assessments', 'laboratory': 'Assessments',
        'electrocardiogram': 'Assessments', 'ecg': 'Assessments',
        'pharmacokinetic': 'Assessments',
        'adverse event': 'Safety', 'safety': 'Safety',
        'serious adverse': 'Safety', 'sae': 'Safety',
        'statistic': 'Statistics', 'interim analys': 'Statistics',
        'sample size': 'Statistics', 'data monitoring': 'Statistics',
        'ethic': 'Ethics', 'regulatory': 'Ethics',
        'informed consent': 'Ethics', 'oversight': 'Ethics',
        'data protection': 'Ethics', 'quality assurance': 'Ethics',
        'financial disclosure': 'Ethics', 'publication': 'Ethics',
        'reference': 'References',
        'abbreviation': 'Abbreviations', 'glossary': 'Abbreviations',
        'appendix': 'Appendix', 'amendment': 'Appendix',
        'contracepti': 'Ethics', 'pregnancy': 'Ethics',
        'covid': 'Appendix',
    }
    for key, value in mappings.items():
        if key in title_lower:
            return value
    return 'Other'


def _infer_section_type(m11_num: str) -> str:
    """Infer a SectionType string from M11 section number."""
    type_map = {
        '1': 'Synopsis', '2': 'Introduction', '3': 'Objectives',
        '4': 'Study Design', '5': 'Study Population', '6': 'Treatment',
        '7': 'Discontinuation', '8': 'Assessments', '9': 'Safety',
        '10': 'Statistics', '11': 'Ethics', '12': 'Appendix',
        '13': 'Abbreviations', '14': 'References',
    }
    return type_map.get(m11_num, 'Other')


# ---------------------------------------------------------------------------
# Full-text extraction helpers
# ---------------------------------------------------------------------------

def _find_section_pages(
    pdf_path: str,
    sections_raw: List[Dict],
) -> Dict[str, int]:
    """
    Find the actual 0-indexed PDF page where each section heading appears.
    
    Searches the full PDF for heading patterns like "3. Study Design" or
    "3  STUDY DESIGN" to locate each section, avoiding reliance on TOC
    page numbers and eliminating page-offset calibration.
    
    TOC pages (pages matching 3+ section headings) are detected and
    excluded so that only body-text headings are returned.
    """
    import fitz
    
    doc = fitz.open(pdf_path)
    total = len(doc)
    
    # Pre-extract all page texts once
    page_texts = [doc[p].get_text() for p in range(total)]
    doc.close()
    
    # Build patterns for all sections
    sec_patterns: List[tuple] = []  # (number, [patterns], hint_page)
    for sec in sections_raw:
        number = sec.get('number', '')
        title = sec.get('title', '')
        if not number or not title:
            continue
        
        escaped_num = re.escape(number)
        title_words = title.strip().split()[:4]
        title_prefix = r'\s+'.join(re.escape(w) for w in title_words)
        
        # Primary: number + title on same line
        # Fallback 1: number + title separated by newline (multi-line headings)
        # Fallback 2: number alone at line start followed by newline + uppercase text
        patterns = [
            rf'(?:^|\n)\s*{escaped_num}\.?\s+{title_prefix}',
            rf'(?:^|\n)\s*Section\s+{escaped_num}[.:]?\s+{title_prefix}',
            rf'(?:^|\n)\s*{escaped_num}\.?\s*\n\s*{title_prefix}',
            rf'(?:^|\n)\s*{escaped_num}\.?\s*\n\s*[A-Z]{{2,}}',
        ]
        sec_patterns.append((number, patterns, sec.get('page')))
    
    # --- Pass 1: Detect TOC pages ---
    # A TOC page matches many section headings; a body page matches 1-2.
    page_match_counts: Dict[int, int] = {}
    for p in range(total):
        count = 0
        for number, patterns, _ in sec_patterns:
            for pat in patterns:
                if re.search(pat, page_texts[p], re.IGNORECASE):
                    count += 1
                    break
        if count > 0:
            page_match_counts[p] = count
    
    # Pages matching 3+ distinct sections are TOC/index pages
    toc_pages = {p for p, count in page_match_counts.items() if count >= 3}
    if toc_pages:
        logger.debug(f"Detected TOC pages: {sorted(toc_pages)} (matching 3+ headings each)")
    
    # --- Pass 2: Find first non-TOC page for each section ---
    section_pages: Dict[str, int] = {}
    
    for number, patterns, hint_page in sec_patterns:
        # Use TOC page hint to narrow search, but skip TOC pages
        if hint_page and isinstance(hint_page, (int, float)):
            hint_idx = int(hint_page) - 1
            search_ranges = [
                range(max(0, hint_idx - 10), min(total, hint_idx + 10)),
                range(total),
            ]
        else:
            search_ranges = [range(total)]
        
        found = False
        for search_range in search_ranges:
            if found:
                break
            for p in search_range:
                if p in toc_pages:
                    continue  # skip TOC pages
                for pat in patterns:
                    if re.search(pat, page_texts[p], re.IGNORECASE):
                        section_pages[number] = p
                        found = True
                        break
                if found:
                    break
    
    # --- Pass 3: Use discovery page hints for sections not found by regex ---
    # Sections discovered by _discover_sections_from_pdf have a known page
    # (stored as _discovered_page0). Use it directly when regex fails, which
    # commonly happens with multi-line headings like "7.\nDISCONTINUATION...".
    # Note: bypass TOC filtering here because _discover_sections_from_pdf
    # already has its own TOC detection (threshold 5 headings per page).
    for sec in sections_raw:
        number = sec.get('number', '')
        if not number or number in section_pages:
            continue
        disc_page = sec.get('_discovered_page0')
        if disc_page is not None:
            section_pages[number] = disc_page

    logger.info(f"Located {len(section_pages)}/{len(sections_raw)} sections in PDF (skipped {len(toc_pages)} TOC pages)")
    return section_pages


def _compute_section_page_ranges(
    sections_raw: List[Dict],
    section_pages: Dict[str, int],
    total_pages: int,
) -> Dict[str, tuple]:
    """
    Compute (start_page, end_page) for each section.
    
    A section's text runs from its start page to the page before the next
    section starts.  Returns 0-indexed inclusive page ranges.
    """
    # Build ordered list of (page, section_number) sorted by page
    located = [(page, num) for num, page in section_pages.items()]
    located.sort(key=lambda x: x[0])
    
    ranges: Dict[str, tuple] = {}
    for idx, (start, num) in enumerate(located):
        if idx + 1 < len(located):
            end = located[idx + 1][0] - 1
        else:
            end = total_pages - 1
        # Ensure end >= start (multiple sections can share a page)
        end = max(end, start)
        # Clamp to reasonable size (max 30 pages per section)
        end = min(end, start + 29)
        ranges[num] = (start, end)
    
    return ranges


def _strip_header_footer(text: str) -> str:
    """
    Remove repeated header/footer lines from extracted PDF text.
    
    Protocol PDFs typically repeat the protocol number, page number,
    and confidentiality notice on every page.
    """
    lines = text.split('\n')
    if len(lines) < 20:
        return text
    
    # Count line occurrences (normalized) — repeated lines are headers/footers
    from collections import Counter
    normalized = [l.strip().lower() for l in lines]
    counts = Counter(normalized)
    
    # Lines appearing on >30% of pages are likely headers/footers
    page_markers = sum(1 for l in lines if l.strip().startswith('--- Page'))
    threshold = max(3, page_markers * 0.3)
    
    repeated = {line for line, cnt in counts.items() if cnt >= threshold and len(line) > 3}
    
    cleaned = []
    for line in lines:
        norm = line.strip().lower()
        if norm in repeated:
            continue
        # Skip page markers from extract_text_from_pages
        if line.strip().startswith('--- Page'):
            continue
        cleaned.append(line)
    
    return '\n'.join(cleaned).strip()


def _extract_section_texts(
    pdf_path: str,
    sections_raw: List[Dict],
    section_pages: Dict[str, int],
    total_pages: int,
) -> Dict[str, str]:
    """
    Extract cleaned body text for each section from its page range.
    
    Returns a dict mapping section number → extracted text.
    """
    ranges = _compute_section_page_ranges(sections_raw, section_pages, total_pages)
    
    if not ranges:
        return {}
    
    import fitz
    doc = fitz.open(pdf_path)
    
    texts: Dict[str, str] = {}
    for sec_num, (start, end) in ranges.items():
        page_texts = []
        for p in range(start, min(end + 1, len(doc))):
            page_texts.append(doc[p].get_text())
        
        raw = '\n'.join(page_texts)
        cleaned = _strip_header_footer(raw)
        
        # Remove the section heading itself from the start of the text
        # (it's already captured in the section title)
        sec_data = next((s for s in sections_raw if s.get('number') == sec_num), None)
        if sec_data:
            title = sec_data.get('title', '')
            # Try to remove "3. Study Design\n" or similar from start
            heading_pat = rf'^\s*{re.escape(sec_num)}\.?\s+{re.escape(title)}\s*\n?'
            cleaned = re.sub(heading_pat, '', cleaned, count=1, flags=re.IGNORECASE).strip()
        
        if cleaned:
            texts[sec_num] = cleaned
    
    doc.close()
    logger.info(f"Extracted text for {len(texts)} sections ({sum(len(t) for t in texts.values())} chars total)")
    return texts


def _split_subsection_texts(
    parent_text: str,
    subsections: List[Dict],
) -> Dict[str, str]:
    """
    Split a parent section's text into subsection texts.
    
    Uses subsection headings to find boundaries within the parent text.
    """
    if not subsections or not parent_text:
        return {}
    
    # Build list of (position, subsection_number) for each subsection heading found
    boundaries = []
    for sub in subsections:
        num = sub.get('number', '')
        title = sub.get('title', '')
        if not num:
            continue
        
        pat = rf'{re.escape(num)}\.?\s+{re.escape(title[:30])}'
        m = re.search(pat, parent_text, re.IGNORECASE)
        if m:
            boundaries.append((m.start(), m.end(), num))
    
    if not boundaries:
        return {}
    
    boundaries.sort(key=lambda x: x[0])
    
    texts: Dict[str, str] = {}
    for idx, (start, heading_end, num) in enumerate(boundaries):
        if idx + 1 < len(boundaries):
            end = boundaries[idx + 1][0]
        else:
            end = len(parent_text)
        
        # Text after the heading, before the next subsection
        sub_text = parent_text[heading_end:end].strip()
        if sub_text:
            texts[num] = sub_text
    
    return texts


# ---------------------------------------------------------------------------
# Data builders
# ---------------------------------------------------------------------------

def _build_narrative_data(
    abbreviations_raw: List[Dict],
    sections_raw: List[Dict],
    document_raw: Optional[Dict],
    section_texts: Optional[Dict[str, str]] = None,
) -> NarrativeData:
    """Build NarrativeData from raw extraction results.
    
    Handles both legacy format and new USDM-compliant format.
    If section_texts is provided, populates text fields from extracted content.
    """
    if section_texts is None:
        section_texts = {}
    
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
        
        # Split parent text into subsection texts if available
        parent_text = section_texts.get(sec.get('number', ''), '')
        subsections = sec.get('subsections', [])
        sub_texts = _split_subsection_texts(parent_text, subsections) if parent_text else {}
        
        # Process subsections
        child_ids = []
        for j, sub in enumerate(subsections):
            if isinstance(sub, dict):
                item_id = f"nci_{i+1}_{j+1}"
                child_ids.append(item_id)
                sub_num = sub.get('number', '')
                sub_text = sub_texts.get(sub_num, '')
                items.append(NarrativeContentItem(
                    id=item_id,
                    name=sub.get('title', f'Section {sub_num}'),
                    text=sub_text,
                    section_number=sub_num,
                    section_title=sub.get('title'),
                    order=j,
                ))
        
        section_type = _map_section_type(sec.get('type', 'Other'))
        
        sec_num = sec.get('number', '')
        sec_text = section_texts.get(sec_num, '')
        
        sections.append(NarrativeContent(
            id=section_id,
            name=sec.get('title', f'Section {sec_num}'),
            section_number=sec_num,
            section_title=sec.get('title'),
            section_type=section_type,
            text=sec_text if sec_text else None,
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
        'discontinu': SectionType.DISCONTINUATION,
        'withdraw': SectionType.DISCONTINUATION,
        'dropout': SectionType.DISCONTINUATION,
        'drop-out': SectionType.DISCONTINUATION,
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
