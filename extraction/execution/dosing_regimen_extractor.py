"""
Dosing Regimen Extractor

Extracts dosing schedules, frequencies, titration rules, and dose modifications
from clinical protocol PDFs. Critical for generating realistic treatment data.

Phase 4 Component.
"""

import re
import logging
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path

import fitz  # PyMuPDF

from .schema import (
    ExecutionModelResult,
    ExecutionModelData,
    DosingRegimen,
    DoseLevel,
    DosingFrequency,
    RouteOfAdministration,
)
from .processing_warnings import _add_processing_warning

logger = logging.getLogger(__name__)


# Keywords for finding dosing sections
DOSING_KEYWORDS = [
    "dosing", "dose", "dosage", "administration", "treatment regimen",
    "investigational product", "study drug", "study medication",
    "titration", "dose escalation", "dose reduction", "dose modification",
    "mg", "mcg", "mL", "IU", "units",
    "once daily", "twice daily", "QD", "BID", "TID", "QID",
    "weekly", "every week", "q2w", "q3w", "q4w",
    "oral", "intravenous", "subcutaneous", "IV", "SC", "IM",
]

# Frequency pattern mappings
FREQUENCY_PATTERNS = {
    r'\b(once\s+daily|QD|q\.?d\.?|od)\b': DosingFrequency.ONCE_DAILY,
    r'\b(twice\s+daily|BID|b\.?i\.?d\.?)\b': DosingFrequency.TWICE_DAILY,
    r'\b(three\s+times\s+daily|TID|t\.?i\.?d\.?)\b': DosingFrequency.THREE_TIMES_DAILY,
    r'\b(four\s+times\s+daily|QID|q\.?i\.?d\.?)\b': DosingFrequency.FOUR_TIMES_DAILY,
    r'\b(every\s+other\s+day|QOD|q\.?o\.?d\.?)\b': DosingFrequency.EVERY_OTHER_DAY,
    r'\b(once\s+weekly|weekly|QW|q\.?w\.?|every\s+week)\b': DosingFrequency.WEEKLY,
    r'\b(every\s+2\s+weeks?|Q2W|q2w|biweekly)\b': DosingFrequency.EVERY_TWO_WEEKS,
    r'\b(every\s+3\s+weeks?|Q3W|q3w)\b': DosingFrequency.EVERY_THREE_WEEKS,
    r'\b(every\s+4\s+weeks?|Q4W|q4w|monthly)\b': DosingFrequency.EVERY_FOUR_WEEKS,
    r'\b(as\s+needed|PRN|p\.?r\.?n\.?)\b': DosingFrequency.AS_NEEDED,
    r'\b(single\s+dose|one\s+time|one-time)\b': DosingFrequency.SINGLE_DOSE,
    r'\b(continuous|continuously)\b': DosingFrequency.CONTINUOUS,
}

# Route pattern mappings
ROUTE_PATTERNS = {
    r'\b(oral|orally|by\s+mouth|PO|p\.?o\.?)\b': RouteOfAdministration.ORAL,
    r'\b(intravenous|IV|i\.?v\.?)\b': RouteOfAdministration.INTRAVENOUS,
    r'\b(subcutaneous|SC|s\.?c\.?|subcut)\b': RouteOfAdministration.SUBCUTANEOUS,
    r'\b(intramuscular|IM|i\.?m\.?)\b': RouteOfAdministration.INTRAMUSCULAR,
    r'\b(topical|topically)\b': RouteOfAdministration.TOPICAL,
    r'\b(inhalation|inhaled|nebulized)\b': RouteOfAdministration.INHALATION,
    r'\b(intranasal|nasal)\b': RouteOfAdministration.INTRANASAL,
    r'\b(transdermal|patch)\b': RouteOfAdministration.TRANSDERMAL,
    r'\b(sublingual)\b': RouteOfAdministration.SUBLINGUAL,
    r'\b(rectal|rectally)\b': RouteOfAdministration.RECTAL,
    r'\b(ophthalmic|eye\s+drops?)\b': RouteOfAdministration.OPHTHALMIC,
}

# Dose amount patterns
DOSE_PATTERN = re.compile(
    r'(\d+(?:\.\d+)?)\s*(mg|mcg|µg|g|mL|ml|IU|units?|U)\b',
    re.IGNORECASE
)

# Duration patterns
DURATION_PATTERN = re.compile(
    r'(?:for\s+)?(\d+)\s*(weeks?|days?|months?|years?)',
    re.IGNORECASE
)

# Dose range pattern (e.g., "750-1500", "100 to 200")
DOSE_RANGE_PATTERN = re.compile(
    r'^(\d+(?:\.\d+)?)\s*[-–—to]+\s*(\d+(?:\.\d+)?)$',
    re.IGNORECASE
)


def _parse_dose_amount(value: Any) -> Tuple[float, Optional[float]]:
    """
    Parse a dose amount that may be a number, string, or range.
    
    Args:
        value: The dose amount (int, float, or string like '750-1500')
        
    Returns:
        Tuple of (amount, max_amount) where max_amount is None for single values
    """
    if value is None:
        return 0.0, None
    
    # Already a number
    if isinstance(value, (int, float)):
        return float(value), None
    
    # String - check for range
    value_str = str(value).strip()
    
    # Try range pattern first
    range_match = DOSE_RANGE_PATTERN.match(value_str)
    if range_match:
        min_val = float(range_match.group(1))
        max_val = float(range_match.group(2))
        return min_val, max_val
    
    # Try simple float conversion
    try:
        return float(value_str), None
    except ValueError:
        # Extract first number from string
        num_match = re.search(r'(\d+(?:\.\d+)?)', value_str)
        if num_match:
            return float(num_match.group(1)), None
        return 0.0, None


def _get_page_count(pdf_path: str) -> int:
    """Get total page count of PDF."""
    try:
        doc = fitz.open(pdf_path)
        count = len(doc)
        doc.close()
        return count
    except Exception:
        return 0


def _extract_text_from_pages(pdf_path: str, pages: List[int] = None) -> str:
    """Extract text from specified pages or all pages."""
    try:
        doc = fitz.open(pdf_path)
        text_parts = []
        
        if pages is None:
            pages = range(len(doc))
        
        for page_num in pages:
            if 0 <= page_num < len(doc):
                page = doc[page_num]
                text_parts.append(page.get_text())
        
        doc.close()
        return "\n\n".join(text_parts)
    except Exception as e:
        logger.warning(f"Error extracting text: {e}")
        return ""


def find_dosing_pages(pdf_path: str) -> List[int]:
    """Find pages likely to contain dosing information."""
    try:
        pages = []
        page_count = _get_page_count(pdf_path)
        
        for page_num in range(page_count):
            try:
                page_text = _extract_text_from_pages(pdf_path, pages=[page_num])
                if page_text:
                    text_lower = page_text.lower()
                    # Check for dosing keywords
                    keyword_count = sum(1 for kw in DOSING_KEYWORDS if kw.lower() in text_lower)
                    if keyword_count >= 3:
                        pages.append(page_num)
            except Exception:
                continue
        
        return pages[:30]  # Limit to 30 pages
        
    except Exception as e:
        logger.warning(f"Error finding dosing pages: {e}")
        return []


def extract_dosing_regimens(
    pdf_path: str,
    model: str = "gemini-2.5-pro",
    use_llm: bool = True,
    existing_interventions: Optional[List[Dict[str, Any]]] = None,
    existing_arms: Optional[List[Dict[str, Any]]] = None,
) -> ExecutionModelResult:
    """
    Extract dosing regimens from a protocol PDF.
    
    Args:
        pdf_path: Path to the protocol PDF
        model: LLM model to use for enhancement
        use_llm: Whether to use LLM for extraction
        existing_interventions: SoA interventions to bind dosing to actual treatments
        existing_arms: SoA arms for arm-specific dosing context
        
    Returns:
        ExecutionModelResult with dosing regimens
    """
    
    logger.info("=" * 60)
    logger.info("PHASE 4A: Dosing Regimen Extraction")
    logger.info("=" * 60)
    
    # Find relevant pages
    pages = find_dosing_pages(pdf_path)
    if not pages:
        pages = list(range(min(40, _get_page_count(pdf_path))))
    
    logger.info(f"Found {len(pages)} potential dosing pages")
    
    # Extract text
    text = _extract_text_from_pages(pdf_path, pages=pages)
    if not text:
        return ExecutionModelResult(
            success=False,
            error="Failed to extract text from PDF",
            pages_used=pages,
            model_used=model,
        )
    
    # Heuristic extraction
    regimens = _extract_regimens_heuristic(text)
    logger.info(f"Heuristic extraction found {len(regimens)} dosing regimens")
    
    # LLM enhancement
    if use_llm and len(text) > 100:
        try:
            llm_regimens = _extract_regimens_llm(text, model)
            if llm_regimens:
                regimens = _merge_regimens(regimens, llm_regimens)
                logger.info(f"After LLM enhancement: {len(regimens)} dosing regimens")
        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}")
            _add_processing_warning(
                category="llm_extraction_failed",
                message=f"LLM dosing extraction failed: {e}",
                context="dosing_regimen_extraction",
                details={'error': str(e), 'fallback': 'heuristic extraction'}
            )
    
    logger.info(f"Extracted {len(regimens)} dosing regimens")
    
    return ExecutionModelResult(
        success=True,
        data=ExecutionModelData(dosing_regimens=regimens),
        pages_used=pages,
        model_used=model if use_llm else "heuristic",
    )


def _clean_source_text(text: str) -> str:
    """Clean source text for better readability."""
    # Replace multiple whitespace with single space
    text = re.sub(r'\s+', ' ', text)
    # Remove X marks from tables
    text = re.sub(r'\bX\b', '', text)
    # Trim
    return text.strip()[:300]


def _extract_titration_schedule(text: str) -> Optional[str]:
    """Extract titration/escalation schedule from text."""
    text_lower = text.lower()
    
    # Titration patterns
    patterns = [
        r'(titrat\w+[^.]{10,100}\.)',  # "Titration... ."
        r'(dose\s+escalat\w+[^.]{10,100}\.)',  # "Dose escalation... ."
        r'(increas\w+\s+(?:by|to)\s+\d+\s*(?:mg|mcg)[^.]{5,80}\.)',  # "Increase by/to X mg..."
        r'(start\w*\s+(?:at|with)\s+\d+\s*(?:mg|mcg)[^.]{5,80}\.)',  # "Start at/with X mg..."
        r'(adjust\w*\s+(?:to|by)\s+\d+\s*(?:mg|mcg)[^.]{5,80}\.)',  # "Adjust to/by X mg..."
        r'(target\s+dose[^.]{5,80}\.)',  # "Target dose..."
        r'(maintenance\s+dose[^.]{5,80}\.)',  # "Maintenance dose..."
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            return match.group(1).strip().capitalize()
    
    return None


def _extract_dose_modifications(text: str) -> List[str]:
    """Extract dose modification rules from text."""
    modifications = []
    text_lower = text.lower()
    
    # Modification patterns
    patterns = [
        r'(reduce\s+(?:dose|by)[^.]{10,100}\.)',  # "Reduce dose/by..."
        r'(discontinue[^.]{10,100}\.)',  # "Discontinue..."
        r'(hold\s+(?:dose|treatment)[^.]{10,100}\.)',  # "Hold dose..."
        r'(if\s+(?:adverse|toxicity|intoleran)[^.]{10,100}\.)',  # Conditional modifications
        r'(dose\s+reduction[^.]{10,100}\.)',  # "Dose reduction..."
        r'(renal\s+(?:impairment|insufficiency)[^.]{10,100}\.)',  # Renal-based
        r'(hepatic\s+(?:impairment|insufficiency)[^.]{10,100}\.)',  # Hepatic-based
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            mod = match.group(1).strip().capitalize()
            if mod not in modifications:
                modifications.append(mod)
    
    return modifications[:5]  # Limit to 5


def _extract_regimens_heuristic(text: str) -> List[DosingRegimen]:
    """Extract dosing regimens using pattern matching."""
    regimens = []
    
    # Find drug/treatment names with doses
    # Pattern: "Drug Name 100 mg once daily"
    drug_dose_pattern = re.compile(
        r'([A-Z][a-zA-Z0-9\-]+(?:\s+[A-Z][a-zA-Z0-9\-]+)?)\s+'
        r'(\d+(?:\.\d+)?)\s*(mg|mcg|µg|g|mL|IU|units?)',
        re.IGNORECASE
    )
    
    seen_treatments = set()
    regimen_id = 1
    
    for match in drug_dose_pattern.finditer(text):
        treatment_name = match.group(1).strip()
        dose_amount = float(match.group(2))
        dose_unit = match.group(3).lower()
        
        # Skip common false positives - expanded list
        false_positives = {
            'the', 'and', 'for', 'with', 'from', 'study', 'day', 'week', 'to',
            'of', 'in', 'at', 'on', 'by', 'or', 'be', 'is', 'was', 'were', 'are',
            'than', 'each', 'per', 'every', 'total', 'maximum', 'minimum',
            'approximately', 'about', 'up', 'least', 'most', 'after', 'before',
            'during', 'between', 'within', 'dose', 'doses', 'dosing', 'mg',
            'initial', 'state', 'treatment', 'titration', 'end', 'start',
            'daily', 'weekly', 'monthly', 'hours', 'minutes', 'given', 'taken',
        }
        name_lower = treatment_name.lower()
        
        # Skip single false positive words
        if name_lower in false_positives:
            continue
        
        # Skip if name is too short (< 4 chars for single words)
        if len(treatment_name) < 4:
            continue
        
        # Skip if ALL words are common/false positives
        words = name_lower.split()
        if all(w in false_positives or len(w) < 3 for w in words):
            continue
        
        # Skip patterns like "X at", "X of", "to X", "end of", "state at"
        if re.match(r'^(to|of|at|in|on|by|end|state|initial|treatment|titration)\s+\w+$', name_lower):
            continue
        if re.match(r'^\w+\s+(at|of|to|in|on|by)$', name_lower):
            continue
        
        # Skip if name doesn't start with a letter
        if not treatment_name[0].isalpha():
            continue
        
        # Skip names with excessive whitespace or weird characters
        if '\n' in treatment_name or '\t' in treatment_name or '  ' in treatment_name:
            continue
        
        # Drug names typically have specific patterns - require alphanumeric with possible hyphen/numbers
        # Valid: ABC-1234, Aspirin, Drug-123
        # Invalid: "state at", "end of", "Interventionm"
        if not re.match(r'^[A-Z][A-Za-z0-9\-]+$', treatment_name):
            # Multi-word: at least one word should look like a drug name
            has_drug_like_word = any(
                re.match(r'^[A-Z][A-Za-z0-9\-]+$', w) and len(w) >= 4 and w.lower() not in false_positives
                for w in treatment_name.split()
            )
            if not has_drug_like_word:
                continue
        
        # Avoid duplicates
        key = treatment_name.lower()
        if key in seen_treatments:
            continue
        seen_treatments.add(key)
        
        # Get surrounding context for more details
        start = max(0, match.start() - 200)
        end = min(len(text), match.end() + 200)
        context = text[start:end]
        
        # Detect frequency
        frequency = _detect_frequency(context)
        
        # Detect route
        route = _detect_route(context)
        
        # Detect duration
        duration = _detect_duration(context)
        
        # Detect titration schedule
        titration = _extract_titration_schedule(context)
        
        # Detect dose modifications
        modifications = _extract_dose_modifications(context)
        
        # Create dose level
        dose_levels = [DoseLevel(
            amount=dose_amount,
            unit=dose_unit,
        )]
        
        # Look for additional dose levels
        additional_doses = _find_additional_doses(context, dose_unit)
        for amt in additional_doses:
            if amt != dose_amount:
                dose_levels.append(DoseLevel(amount=amt, unit=dose_unit))
        
        # Find max/min doses if present
        max_dose = None
        min_dose = None
        max_match = re.search(r'max(?:imum)?\s+(?:dose\s+)?(?:of\s+)?(\d+(?:\.\d+)?)\s*' + re.escape(dose_unit), context, re.IGNORECASE)
        min_match = re.search(r'min(?:imum)?\s+(?:dose\s+)?(?:of\s+)?(\d+(?:\.\d+)?)\s*' + re.escape(dose_unit), context, re.IGNORECASE)
        if max_match:
            max_dose = float(max_match.group(1))
        if min_match:
            min_dose = float(min_match.group(1))
        
        regimen = DosingRegimen(
            id=f"dosing_{regimen_id}",
            treatment_name=treatment_name,
            dose_levels=dose_levels,
            frequency=frequency,
            route=route,
            duration_description=duration,
            titration_schedule=titration,
            dose_modifications=modifications,
            max_dose=max_dose,
            min_dose=min_dose,
            source_text=_clean_source_text(context),
        )
        regimens.append(regimen)
        regimen_id += 1
    
    return regimens


def _detect_frequency(text: str) -> DosingFrequency:
    """Detect dosing frequency from text."""
    text_lower = text.lower()
    
    for pattern, frequency in FREQUENCY_PATTERNS.items():
        if re.search(pattern, text_lower):
            return frequency
    
    return DosingFrequency.ONCE_DAILY  # Default


def _detect_route(text: str) -> RouteOfAdministration:
    """Detect route of administration from text."""
    text_lower = text.lower()
    
    for pattern, route in ROUTE_PATTERNS.items():
        if re.search(pattern, text_lower):
            return route
    
    return RouteOfAdministration.ORAL  # Default


def _detect_duration(text: str) -> Optional[str]:
    """Detect treatment duration from text."""
    match = DURATION_PATTERN.search(text)
    if match:
        return f"{match.group(1)} {match.group(2)}"
    return None


def _parse_frequency_flexible(freq_raw: Optional[str]) -> DosingFrequency:
    """Parse frequency with flexible matching for LLM output variations."""
    if not freq_raw:
        return DosingFrequency.UNKNOWN
    
    freq_str = str(freq_raw).upper().strip()
    
    # Direct enum value/name match
    for f in DosingFrequency:
        if f.value.upper() == freq_str or f.name == freq_str:
            return f
    
    # Flexible pattern matching for common variations
    freq_lower = freq_str.lower()
    
    # Once daily variations
    if any(x in freq_lower for x in ['once daily', 'once a day', 'daily', 'od', 'qd', 'q.d.']):
        return DosingFrequency.ONCE_DAILY
    
    # Twice daily variations
    if any(x in freq_lower for x in ['twice daily', 'twice a day', 'bid', 'b.i.d.']):
        return DosingFrequency.TWICE_DAILY
    
    # Three times daily
    if any(x in freq_lower for x in ['three times', 'tid', 't.i.d.', '3 times']):
        return DosingFrequency.THREE_TIMES_DAILY
    
    # Four times daily
    if any(x in freq_lower for x in ['four times', 'qid', 'q.i.d.', '4 times']):
        return DosingFrequency.FOUR_TIMES_DAILY
    
    # Weekly variations
    if 'q3w' in freq_lower or 'every 3 week' in freq_lower or 'every three week' in freq_lower:
        return DosingFrequency.EVERY_THREE_WEEKS
    if 'q2w' in freq_lower or 'every 2 week' in freq_lower or 'every two week' in freq_lower or 'biweekly' in freq_lower:
        return DosingFrequency.EVERY_TWO_WEEKS
    if 'q4w' in freq_lower or 'every 4 week' in freq_lower or 'monthly' in freq_lower:
        return DosingFrequency.EVERY_FOUR_WEEKS
    if any(x in freq_lower for x in ['weekly', 'once weekly', 'qw', 'q.w.', 'every week', 'once a week']):
        return DosingFrequency.WEEKLY
    
    # Other patterns
    if any(x in freq_lower for x in ['every other day', 'qod', 'alternate day']):
        return DosingFrequency.EVERY_OTHER_DAY
    if any(x in freq_lower for x in ['as needed', 'prn', 'p.r.n.']):
        return DosingFrequency.AS_NEEDED
    if any(x in freq_lower for x in ['single', 'one time', 'one-time', 'once']):
        return DosingFrequency.SINGLE_DOSE
    if any(x in freq_lower for x in ['continuous', 'continuously']):
        return DosingFrequency.CONTINUOUS
    
    return DosingFrequency.UNKNOWN


def _parse_route_flexible(route_raw: Optional[str]) -> RouteOfAdministration:
    """Parse route with flexible matching for LLM output variations."""
    if not route_raw:
        return RouteOfAdministration.UNKNOWN
    
    route_str = str(route_raw).strip()
    
    # Direct enum value/name match
    for r in RouteOfAdministration:
        if r.value.lower() == route_str.lower() or r.name.lower() == route_str.lower():
            return r
    
    # Flexible pattern matching
    route_lower = route_str.lower()
    
    # Oral variations
    if any(x in route_lower for x in ['oral', 'po', 'by mouth', 'tablet', 'capsule', 'orally']):
        return RouteOfAdministration.ORAL
    
    # IV variations
    if any(x in route_lower for x in ['intravenous', 'iv', 'i.v.', 'infusion', 'iv push', 'iv infusion']):
        return RouteOfAdministration.INTRAVENOUS
    
    # Subcutaneous variations
    if any(x in route_lower for x in ['subcutaneous', 'sc', 's.c.', 'subq', 'sub-q', 'subcut']):
        return RouteOfAdministration.SUBCUTANEOUS
    
    # Intramuscular variations
    if any(x in route_lower for x in ['intramuscular', 'im', 'i.m.']):
        return RouteOfAdministration.INTRAMUSCULAR
    
    # Inhalation variations
    if any(x in route_lower for x in ['inhalation', 'inhaled', 'nebulized', 'aerosol']):
        return RouteOfAdministration.INHALATION
    
    # Topical variations
    if any(x in route_lower for x in ['topical', 'cream', 'ointment', 'gel', 'patch']):
        return RouteOfAdministration.TOPICAL
    
    # Transdermal
    if any(x in route_lower for x in ['transdermal', 'patch']):
        return RouteOfAdministration.TRANSDERMAL
    
    # Other specific routes
    if 'intranasal' in route_lower or 'nasal' in route_lower:
        return RouteOfAdministration.INTRANASAL
    if 'sublingual' in route_lower:
        return RouteOfAdministration.SUBLINGUAL
    if 'rectal' in route_lower:
        return RouteOfAdministration.RECTAL
    if 'ophthalmic' in route_lower or 'eye' in route_lower:
        return RouteOfAdministration.OPHTHALMIC
    
    # Injection could be SC, IM, or IV - default to SC as most common for drugs
    if 'injection' in route_lower:
        return RouteOfAdministration.SUBCUTANEOUS
    
    return RouteOfAdministration.UNKNOWN


def _find_additional_doses(text: str, unit: str) -> List[float]:
    """Find additional dose amounts in context."""
    doses = []
    pattern = re.compile(rf'(\d+(?:\.\d+)?)\s*{re.escape(unit)}', re.IGNORECASE)
    for match in pattern.finditer(text):
        try:
            doses.append(float(match.group(1)))
        except ValueError:
            continue
    return list(set(doses))


def _extract_regimens_llm(text: str, model: str) -> List[DosingRegimen]:
    """Extract dosing regimens using LLM."""
    from core.llm_client import call_llm
    import json
    
    prompt = f"""Analyze this clinical protocol text and extract ALL dosing regimens for investigational products and comparators.

CRITICAL: For EVERY treatment, you MUST extract:
- frequency: How often is the drug administered? Look for patterns like "once daily", "twice daily", "every 3 weeks", "weekly", "as needed", etc. Convert to standard abbreviations.
- route: How is the drug given? Look for "oral", "orally", "intravenous", "IV", "subcutaneous", "SC", "injection", "infusion", "tablet", "capsule", etc.

Common frequency abbreviations:
- QD = once daily, OD = once daily
- BID = twice daily  
- TID = three times daily
- QW = once weekly, weekly
- Q2W = every 2 weeks, biweekly
- Q3W = every 3 weeks
- Q4W = every 4 weeks, monthly
- PRN = as needed
- Single = one-time dose

Common route indicators:
- Oral: tablet, capsule, oral, PO, by mouth
- IV: intravenous, infusion, IV push
- SC: subcutaneous, injection (under skin)
- IM: intramuscular
- Inhalation: inhaled, nebulized

For placebo/comparator: Infer route and frequency from the active drug it matches (e.g., if active is "oral tablet once daily", placebo is also "Oral" and "QD").

Text to analyze:
{text[:8000]}

Return JSON format:
{{
    "regimens": [
        {{
            "treatmentName": "Drug Name",
            "doses": [
                {{"amount": 100, "unit": "mg", "description": "starting dose"}}
            ],
            "frequency": "QD",
            "frequencyRationale": "Text states 'administered once daily'",
            "route": "Oral",
            "routeRationale": "Text states 'oral tablet'",
            "duration": "24 weeks",
            "titration": "Increase by 50mg weekly until target reached",
            "modifications": ["Reduce dose by 50% for renal impairment"]
        }}
    ]
}}

IMPORTANT: 
- frequency and route are REQUIRED for every regimen
- Include frequencyRationale and routeRationale to show where you found this information
- If a drug is given as matching placebo, copy route/frequency from the active comparator
- Return valid JSON only."""

    try:
        result = call_llm(prompt, model_name=model, extractor_name="dosing_regimen")
        
        # Extract response text from dict
        if isinstance(result, dict):
            if 'error' in result:
                logger.warning(f"LLM call error: {result['error']}")
                return []
            response = result.get('response', '')
        else:
            response = str(result)
        
        if not response:
            return []
        
        # Parse JSON from response
        json_match = re.search(r'\{[\s\S]*\}', response)
        if not json_match:
            return []
        
        data = json.loads(json_match.group())
        regimens = []
        
        for idx, item in enumerate(data.get('regimens', [])):
            # Parse doses
            dose_levels = []
            for dose in item.get('doses', []):
                # Handle dose ranges like '750-1500'
                amount, max_amount = _parse_dose_amount(dose.get('amount', 0))
                description = dose.get('description')
                unit = dose.get('unit') or ''  # Empty string if not extracted
                if not unit:
                    _add_processing_warning(
                        category="missing_unit",
                        message=f"Dose unit not extracted for '{item.get('treatmentName', 'Unknown')}'",
                        context="dosing_regimen_extraction",
                        details={'treatment': item.get('treatmentName'), 'dose_amount': amount}
                    )
                if max_amount is not None:
                    # Add range info to description
                    range_desc = f"{amount}-{max_amount} {unit}" if unit else f"{amount}-{max_amount}"
                    description = f"{range_desc}" if not description else f"{range_desc}: {description}"
                dose_levels.append(DoseLevel(
                    amount=amount,
                    unit=unit,
                    description=description,
                ))
            
            # Parse frequency (use UNKNOWN if not in source)
            freq_raw = item.get('frequency')
            frequency = _parse_frequency_flexible(freq_raw)
            if frequency == DosingFrequency.UNKNOWN:
                _add_processing_warning(
                    category="missing_frequency",
                    message=f"Dosing frequency not extracted for '{item.get('treatmentName', 'Unknown')}'",
                    context="dosing_regimen_extraction",
                    details={'treatment': item.get('treatmentName'), 'raw_value': freq_raw}
                )
            
            # Parse route (use UNKNOWN if not in source)
            route_raw = item.get('route')
            route = _parse_route_flexible(route_raw)
            if route == RouteOfAdministration.UNKNOWN:
                _add_processing_warning(
                    category="missing_route",
                    message=f"Route of administration not extracted for '{item.get('treatmentName', 'Unknown')}'",
                    context="dosing_regimen_extraction",
                    details={'treatment': item.get('treatmentName'), 'raw_value': route_raw}
                )
            
            regimen = DosingRegimen(
                id=f"dosing_llm_{idx+1}",
                treatment_name=item.get('treatmentName', 'Unknown'),
                dose_levels=dose_levels,
                frequency=frequency,
                route=route,
                duration_description=item.get('duration'),
                titration_schedule=item.get('titration'),
                dose_modifications=item.get('modifications', []),
            )
            regimens.append(regimen)
        
        return regimens
        
    except Exception as e:
        logger.error(f"LLM dosing extraction failed: {e}")
        return []


def _merge_regimens(
    heuristic: List[DosingRegimen],
    llm: List[DosingRegimen]
) -> List[DosingRegimen]:
    """Merge heuristic and LLM-extracted regimens."""
    merged = {}
    
    # Add heuristic results
    for regimen in heuristic:
        key = regimen.treatment_name.lower()
        merged[key] = regimen
    
    # Merge/update with LLM results
    for regimen in llm:
        key = regimen.treatment_name.lower()
        if key in merged:
            # Enhance existing with LLM details
            existing = merged[key]
            if regimen.titration_schedule and not existing.titration_schedule:
                existing.titration_schedule = regimen.titration_schedule
            if regimen.dose_modifications and not existing.dose_modifications:
                existing.dose_modifications = regimen.dose_modifications
            if regimen.duration_description and not existing.duration_description:
                existing.duration_description = regimen.duration_description
            # Merge dose levels
            existing_amounts = {d.amount for d in existing.dose_levels}
            for dose in regimen.dose_levels:
                if dose.amount not in existing_amounts:
                    existing.dose_levels.append(dose)
        else:
            merged[key] = regimen
    
    return list(merged.values())
