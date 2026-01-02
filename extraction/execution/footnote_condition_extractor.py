"""
Footnote Condition Extractor

Extracts structured conditions from SoA footnotes and converts them
to machine-readable USDM Condition objects.

Per USDM workshop manual: "Footnotes contain critical timing and sequencing
information. USDM aims to extract this logic and represent it explicitly
in the timeline structure."

Footnote types:
- Timing: "ECG must be collected 30 min before labs"
- Eligibility: "Only for women of childbearing potential"
- Procedure variant: "Performed in triplicate at Weeks 0 and 36"
- Frequency: "Daily during treatment period"
- Sequence: "Vital signs before ECG before labs"
"""

import re
import json
import logging
from typing import List, Dict, Any, Optional, Tuple

from .schema import (
    FootnoteCondition,
    ExecutionModelResult, ExecutionModelData
)

logger = logging.getLogger(__name__)


# Footnote condition type patterns
TIMING_PATTERNS: List[Tuple[str, str, float]] = [
    # Before/After patterns
    (r'(\d+)\s*(?:min(?:ute)?s?|hours?)\s+(?:before|prior\s+to)\s+(.+)', 
     "timing_before", 0.90),
    (r'(?:before|prior\s+to)\s+(.+)', 
     "timing_before", 0.80),
    (r'(\d+)\s*(?:min(?:ute)?s?|hours?)\s+(?:after|following)\s+(.+)', 
     "timing_after", 0.90),
    (r'(?:after|following)\s+(.+)', 
     "timing_after", 0.80),
    
    # At specific times
    (r'(?:at|on)\s+(?:day|week)\s+(\d+)', 
     "timing_at", 0.85),
    (r'(?:at|during)\s+(?:each|every)\s+(?:visit|timepoint)', 
     "timing_recurring", 0.85),
    
    # Sequence patterns
    (r'(.+)\s+(?:then|followed\s+by)\s+(.+)', 
     "sequence", 0.85),
    (r'(.+)\s+(?:before|prior\s+to)\s+(.+)\s+(?:before|prior\s+to)\s+(.+)', 
     "sequence", 0.90),
]

ELIGIBILITY_PATTERNS: List[Tuple[str, str, float]] = [
    # Population subsets
    (r'(?:only\s+)?(?:for|in)\s+(?:women|female)\s+(?:of\s+)?(?:childbearing|reproductive)\s+(?:potential|age)', 
     "eligibility_wocbp", 0.95),
    (r'(?:only\s+)?(?:for|in)\s+(?:patients?|subjects?)\s+(?:with|who\s+have)\s+(.+)', 
     "eligibility_condition", 0.85),
    (r'(?:if|when)\s+(?:applicable|indicated|required)', 
     "eligibility_conditional", 0.80),
    (r'(?:only\s+)?(?:for|in)\s+(?:patients?|subjects?)\s+(?:age[d]?\s+)?(\d+)\s*(?:years?|and\s+older)', 
     "eligibility_age", 0.85),
    (r'(?:exclude[d]?\s+)?(?:for|in)\s+(?:patients?|subjects?)\s+(?:with|taking)\s+(.+)', 
     "eligibility_exclusion", 0.85),
]

PROCEDURE_VARIANT_PATTERNS: List[Tuple[str, str, float]] = [
    # Triplicate/Duplicate
    (r'(?:performed|collected|measured)\s+(?:in\s+)?(?:triplicate|duplicate)', 
     "procedure_replicate", 0.90),
    (r'(?:triplicate|duplicate)\s+(?:measurements?|readings?|samples?)', 
     "procedure_replicate", 0.90),
    
    # At specific timepoints
    (r'(?:at|on|during)\s+(?:weeks?|days?|visits?)\s+([\d,\s]+(?:and\s+\d+)?)', 
     "procedure_timepoints", 0.85),
    
    # Conditional procedures
    (r'(?:if|when)\s+(?:clinically\s+)?(?:indicated|necessary|required)', 
     "procedure_conditional", 0.85),
    (r'(?:as\s+)?(?:clinically\s+)?indicated', 
     "procedure_conditional", 0.80),
    
    # Fasting requirements
    (r'(?:fasting|after\s+(?:\d+[\-\s]?hour)?\s*fast)', 
     "procedure_fasting", 0.90),
]

FREQUENCY_PATTERNS: List[Tuple[str, str, float]] = [
    # Daily/Weekly patterns
    (r'(?:daily|once\s+daily|every\s+day)', 
     "frequency_daily", 0.90),
    (r'(?:weekly|once\s+(?:a|per)\s+week)', 
     "frequency_weekly", 0.90),
    (r'(?:twice|two\s+times?)\s+(?:daily|per\s+day)', 
     "frequency_bid", 0.90),
    
    # During period
    (r'(?:during|throughout)\s+(?:the\s+)?(?:treatment|study|dosing)\s+(?:period|phase)', 
     "frequency_continuous", 0.85),
]

# Footnote marker patterns
FOOTNOTE_MARKERS = [
    r'\[([a-z])\]',  # [a], [b], [c]
    r'\(([a-z])\)',  # (a), (b), (c)
    r'([a-z])\.',    # a., b., c.
    r'\[(\d+)\]',    # [1], [2], [3]
    r'\((\d+)\)',    # (1), (2), (3)
    r'(\d+)\.',      # 1., 2., 3.
    r'[*†‡§¶]+',     # *, †, ‡
    r'\^([a-z])',    # ^a, ^b
]


def find_footnote_pages(
    pdf_path: str,
    max_pages_to_scan: int = 50,
) -> List[int]:
    """Find pages likely to contain SoA footnotes."""
    import fitz
    
    footnote_keywords = [
        r'schedule\s+of\s+(?:activities|assessments|events)',
        r'soa',
        r'footnote',
        r'\[a\]|\[b\]|\[1\]|\[2\]',
        r'note\s*:',
        r'abbreviation',
    ]
    
    pattern = re.compile('|'.join(footnote_keywords), re.IGNORECASE)
    pages = []
    
    try:
        doc = fitz.open(pdf_path)
        total_pages = min(len(doc), max_pages_to_scan)
        
        for page_num in range(total_pages):
            page = doc[page_num]
            text = page.get_text().lower()
            
            matches = len(pattern.findall(text))
            if matches >= 2:
                pages.append(page_num)
        
        doc.close()
        
        if len(pages) > 20:
            pages = pages[:20]
        
        logger.info(f"Found {len(pages)} potential footnote pages")
        
    except Exception as e:
        logger.error(f"Error scanning PDF for footnotes: {e}")
        pages = list(range(min(25, max_pages_to_scan)))
    
    return pages


def _extract_footnote_text(text: str) -> List[Tuple[str, str]]:
    """Extract individual footnotes with their markers."""
    footnotes = []
    
    # Try different footnote patterns
    for marker_pattern in FOOTNOTE_MARKERS:
        # Look for footnote definitions (marker followed by text)
        pattern = rf'({marker_pattern})\s*[:=]?\s*([^\n\[(\d\.]+(?:\n(?![a-z]\.|\[\d|\(\d)[^\n\[(\d\.]+)*)'
        matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
        
        for match in matches:
            if len(match) >= 2:
                marker = match[0] if isinstance(match[0], str) else str(match[0])
                content = match[-1].strip() if isinstance(match[-1], str) else str(match[-1])
                
                # Filter out too short or too long
                if 10 < len(content) < 500:
                    footnotes.append((marker, content))
    
    # Also look for footnote sections
    footnote_section = re.search(
        r'(?:footnotes?|notes?)\s*[:\-]?\s*\n(.+?)(?=\n\n|\Z)',
        text, re.IGNORECASE | re.DOTALL
    )
    if footnote_section:
        section_text = footnote_section.group(1)
        # Split by common delimiters
        parts = re.split(r'\n(?=[a-z]\.|\[\d|\(\d|[*†‡])', section_text)
        for i, part in enumerate(parts):
            if 10 < len(part.strip()) < 500:
                footnotes.append((f"fn_{i+1}", part.strip()))
    
    return footnotes


def _is_valid_footnote(text: str) -> bool:
    """Filter out noise - text that is unlikely to be a real footnote condition."""
    text_lower = text.lower().strip()
    
    # Too short to be meaningful
    if len(text_lower) < 15:
        return False
    
    # All caps (likely a header)
    if text.isupper() and len(text) > 20:
        return False
    
    # Starts with common non-footnote patterns
    noise_starts = [
        'page ', 'table ', 'figure ', 'section ', 'chapter ',
        'version ', 'protocol ', 'confidential', 'proprietary',
        'amendment', 'revision', 'date:', 'sponsor:',
    ]
    for noise in noise_starts:
        if text_lower.startswith(noise):
            return False
    
    # Contains mostly numbers or dates (likely a table cell)
    num_count = sum(1 for c in text if c.isdigit())
    if num_count > len(text) * 0.5:
        return False
    
    # Looks like a reference or citation only
    if re.match(r'^[\[\(]?\d+[\]\)]?\.?\s*$', text_lower):
        return False
    
    # Contains footnote-relevant keywords
    relevant_keywords = [
        'visit', 'day', 'week', 'hour', 'minute', 'before', 'after',
        'if', 'when', 'only', 'must', 'should', 'may', 'can',
        'patient', 'subject', 'sample', 'blood', 'urine', 'fasting',
        'female', 'male', 'women', 'men', 'childbearing',
        'triplicate', 'duplicate', 'repeat', 'collect',
        'assess', 'perform', 'measure', 'record', 'document',
        'applicable', 'indicated', 'required', 'optional',
    ]
    
    has_relevant = any(kw in text_lower for kw in relevant_keywords)
    
    # If no relevant keywords and classified as general, it's likely noise
    return has_relevant or len(text) > 50


def _deduplicate_footnotes(footnotes: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """Remove duplicate or near-duplicate footnotes."""
    seen_texts = set()
    unique = []
    
    for marker, text in footnotes:
        # Normalize text for comparison
        normalized = re.sub(r'\s+', ' ', text.lower().strip())
        normalized = re.sub(r'[^\w\s]', '', normalized)
        
        # Check for exact or near-duplicate
        is_dup = False
        for seen in seen_texts:
            # Check similarity (simple substring check)
            if normalized in seen or seen in normalized:
                is_dup = True
                break
            # Check if >80% similar (Jaccard on words)
            words1 = set(normalized.split())
            words2 = set(seen.split())
            if words1 and words2:
                intersection = len(words1 & words2)
                union = len(words1 | words2)
                if union > 0 and intersection / union > 0.8:
                    is_dup = True
                    break
        
        if not is_dup:
            seen_texts.add(normalized)
            unique.append((marker, text))
    
    return unique


def _classify_footnote(text: str) -> Tuple[str, Optional[str], float]:
    """Classify a footnote by its condition type."""
    text_lower = text.lower()
    
    # Check timing patterns
    for pattern, cond_type, confidence in TIMING_PATTERNS:
        if re.search(pattern, text_lower):
            # Extract timing constraint if present
            time_match = re.search(r'(\d+)\s*(?:min(?:ute)?s?|hours?)', text_lower)
            timing_constraint = None
            if time_match:
                value = time_match.group(1)
                if 'hour' in text_lower:
                    timing_constraint = f"PT{value}H"
                else:
                    timing_constraint = f"PT{value}M"
            return cond_type, timing_constraint, confidence
    
    # Check eligibility patterns
    for pattern, cond_type, confidence in ELIGIBILITY_PATTERNS:
        if re.search(pattern, text_lower):
            return cond_type, None, confidence
    
    # Check procedure variant patterns
    for pattern, cond_type, confidence in PROCEDURE_VARIANT_PATTERNS:
        if re.search(pattern, text_lower):
            return cond_type, None, confidence
    
    # Check frequency patterns
    for pattern, cond_type, confidence in FREQUENCY_PATTERNS:
        if re.search(pattern, text_lower):
            return cond_type, None, confidence
    
    return "general", None, 0.5


def _extract_structured_condition(text: str, cond_type: str) -> Optional[str]:
    """Extract a structured condition expression from footnote text."""
    text_lower = text.lower()
    
    # Timing conditions
    if cond_type.startswith("timing"):
        # Before pattern
        before_match = re.search(
            r'(\d+)\s*(?:min(?:ute)?s?|hours?)\s+(?:before|prior\s+to)\s+(.+)',
            text_lower
        )
        if before_match:
            return f"timing.before({before_match.group(2).strip()}, PT{before_match.group(1)}M)"
        
        # After pattern
        after_match = re.search(
            r'(\d+)\s*(?:min(?:ute)?s?|hours?)\s+(?:after|following)\s+(.+)',
            text_lower
        )
        if after_match:
            return f"timing.after({after_match.group(2).strip()}, PT{after_match.group(1)}M)"
    
    # Eligibility conditions
    if cond_type.startswith("eligibility"):
        if "childbearing" in text_lower or "reproductive" in text_lower:
            return "subject.sex == 'Female' AND subject.isOfChildbearingPotential == true"
        
        age_match = re.search(r'(?:age[d]?\s+)?(\d+)\s*(?:years?|and\s+older)', text_lower)
        if age_match:
            return f"subject.age >= {age_match.group(1)}"
    
    # Procedure variants
    if cond_type == "procedure_replicate":
        if "triplicate" in text_lower:
            return "procedure.replicates = 3"
        elif "duplicate" in text_lower:
            return "procedure.replicates = 2"
    
    if cond_type == "procedure_fasting":
        fast_match = re.search(r'(\d+)[\-\s]?hour\s*fast', text_lower)
        if fast_match:
            return f"subject.fastingHours >= {fast_match.group(1)}"
        return "subject.isFasting == true"
    
    return None


def extract_footnote_conditions(
    pdf_path: str,
    model: str = "gemini-2.5-pro",
    pages: Optional[List[int]] = None,
    footnotes: Optional[List[str]] = None,
    use_llm: bool = True,
    existing_activities: Optional[List[Dict[str, Any]]] = None,
) -> ExecutionModelResult:
    """
    Extract structured conditions from SoA footnotes.
    
    Args:
        pdf_path: Path to protocol PDF
        model: LLM model to use
        pages: Specific pages to analyze
        footnotes: Pre-extracted footnote texts (if available)
        use_llm: Whether to use LLM enhancement
        existing_activities: Activities from SoA to match footnotes against
        
    Returns:
        ExecutionModelResult with FootnoteConditions
    """
    from core.pdf_utils import extract_text_from_pages, get_page_count
    
    logger.info("Starting footnote condition extraction...")
    
    # Get footnotes
    if footnotes is None:
        if pages is None:
            pages = find_footnote_pages(pdf_path)
        
        if not pages:
            pages = list(range(min(25, get_page_count(pdf_path))))
        
        text = extract_text_from_pages(pdf_path, pages)
        if not text:
            return ExecutionModelResult(
                success=False,
                error="Failed to extract text from PDF",
                pages_used=pages,
                model_used=model,
            )
        
        # Extract footnotes from text
        raw_footnotes = _extract_footnote_text(text)
    else:
        pages = []
        raw_footnotes = [(f"fn_{i+1}", fn) for i, fn in enumerate(footnotes)]
    
    # Filter and deduplicate footnotes
    filtered_footnotes = [(m, t) for m, t in raw_footnotes if _is_valid_footnote(t)]
    unique_footnotes = _deduplicate_footnotes(filtered_footnotes)
    
    logger.info(f"Filtered {len(raw_footnotes)} -> {len(filtered_footnotes)} -> {len(unique_footnotes)} footnotes")
    
    # Process each footnote
    conditions = []
    
    for marker, fn_text in unique_footnotes:
        cond_type, timing_constraint, confidence = _classify_footnote(fn_text)
        structured = _extract_structured_condition(fn_text, cond_type)
        
        condition = FootnoteCondition(
            id=f"fn_cond_{len(conditions)+1}",
            footnote_id=marker,
            condition_type=cond_type,
            text=fn_text,
            structured_condition=structured,
            timing_constraint=timing_constraint,
            source_text=fn_text[:100],
        )
        conditions.append(condition)
    
    # LLM enhancement
    if use_llm and conditions:
        try:
            llm_conditions = _extract_conditions_llm(
                [c.text for c in conditions], model
            )
            conditions = _merge_conditions(conditions, llm_conditions)
        except Exception as e:
            logger.warning(f"LLM footnote extraction failed: {e}")
    
    data = ExecutionModelData(footnote_conditions=conditions)
    
    result = ExecutionModelResult(
        success=len(conditions) > 0,
        data=data,
        pages_used=pages,
        model_used=model if use_llm else "heuristic",
    )
    
    logger.info(f"Extracted {len(conditions)} footnote conditions")
    
    return result


def _extract_conditions_llm(
    footnotes: List[str],
    model: str,
) -> List[FootnoteCondition]:
    """Extract structured conditions using LLM."""
    from core.llm_client import call_llm
    
    footnotes_text = "\n".join([f"{i+1}. {fn}" for i, fn in enumerate(footnotes[:10])])
    
    prompt = f"""Analyze these clinical trial SoA footnotes and extract structured conditions.

For each footnote, identify:
1. Condition type: timing, eligibility, procedure_variant, frequency, sequence, general
2. Structured condition expression (machine-readable)
3. Any timing constraints (ISO 8601 duration)
4. Which activities/timepoints it applies to

Return JSON:
```json
{{
  "conditions": [
    {{
      "footnoteIndex": 1,
      "conditionType": "timing",
      "structuredCondition": "timing.before(labs, PT30M)",
      "timingConstraint": "PT30M",
      "appliesToActivities": ["ECG", "Vital Signs"],
      "confidence": 0.9
    }}
  ]
}}
```

Footnotes:
{footnotes_text}

Return ONLY the JSON."""

    try:
        result = call_llm(
            prompt=prompt,
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
        
        data = json.loads(json_str)
        
        conditions = []
        for item in data.get('conditions', []):
            idx = item.get('footnoteIndex', 0) - 1
            if 0 <= idx < len(footnotes):
                conditions.append(FootnoteCondition(
                    id=f"fn_cond_llm_{idx+1}",
                    footnote_id=f"fn_{idx+1}",
                    condition_type=item.get('conditionType', 'general'),
                    text=footnotes[idx],
                    structured_condition=item.get('structuredCondition'),
                    applies_to_activity_ids=item.get('appliesToActivities', []),
                    timing_constraint=item.get('timingConstraint'),
                ))
        
        return conditions
        
    except Exception as e:
        logger.error(f"LLM condition extraction failed: {e}")
        return []


def _merge_conditions(
    heuristic: List[FootnoteCondition],
    llm: List[FootnoteCondition],
) -> List[FootnoteCondition]:
    """Merge heuristic and LLM conditions."""
    merged = {}
    
    # Index by footnote text
    for c in heuristic:
        merged[c.text[:50]] = c
    
    # Update with LLM results
    for c in llm:
        key = c.text[:50]
        if key in merged:
            # Merge: prefer LLM structured condition if available
            existing = merged[key]
            if c.structured_condition and not existing.structured_condition:
                existing.structured_condition = c.structured_condition
            if c.applies_to_activity_ids:
                existing.applies_to_activity_ids = c.applies_to_activity_ids
        else:
            merged[key] = c
    
    return list(merged.values())
