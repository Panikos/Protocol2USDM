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
) -> ExecutionModelResult:
    """
    Extract dosing regimens from a protocol PDF.
    
    Args:
        pdf_path: Path to the protocol PDF
        model: LLM model to use for enhancement
        use_llm: Whether to use LLM for extraction
        
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
    
    logger.info(f"Extracted {len(regimens)} dosing regimens")
    
    return ExecutionModelResult(
        success=True,
        data=ExecutionModelData(dosing_regimens=regimens),
        pages_used=pages,
        model_used=model if use_llm else "heuristic",
    )


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
        # Valid: ALXN1840, Aspirin, Drug-123
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
        
        regimen = DosingRegimen(
            id=f"dosing_{regimen_id}",
            treatment_name=treatment_name,
            dose_levels=dose_levels,
            frequency=frequency,
            route=route,
            duration_description=duration,
            source_text=context[:300],
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
    
    prompt = f"""Analyze this clinical protocol text and extract ALL dosing regimens.

For each treatment/drug, identify:
1. Treatment name (drug/intervention name)
2. Dose amounts and units
3. Dosing frequency (QD, BID, weekly, etc.)
4. Route of administration (oral, IV, SC, etc.)
5. Treatment duration
6. Titration schedule (if any)
7. Dose modifications (conditions for dose changes)

Text to analyze:
{text[:8000]}

Return JSON format:
{{
    "regimens": [
        {{
            "treatmentName": "Drug Name",
            "doses": [
                {{"amount": 100, "unit": "mg", "description": "starting dose"}},
                {{"amount": 200, "unit": "mg", "description": "maintenance dose"}}
            ],
            "frequency": "QD|BID|TID|QID|QW|Q2W|Q3W|Q4W|PRN|Single",
            "route": "Oral|IV|SC|IM|Topical|Inhalation",
            "duration": "24 weeks",
            "titration": "Increase by 50mg weekly until target reached",
            "modifications": ["Reduce dose by 50% for renal impairment"]
        }}
    ]
}}

Extract all distinct treatment regimens. Return valid JSON only."""

    try:
        response = call_llm(prompt, model_name=model)
        
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
                dose_levels.append(DoseLevel(
                    amount=float(dose.get('amount', 0)),
                    unit=dose.get('unit', 'mg'),
                    description=dose.get('description'),
                ))
            
            # Parse frequency
            freq_str = item.get('frequency', 'QD').upper()
            frequency = DosingFrequency.ONCE_DAILY
            for f in DosingFrequency:
                if f.value == freq_str or f.name == freq_str:
                    frequency = f
                    break
            
            # Parse route
            route_str = item.get('route', 'Oral')
            route = RouteOfAdministration.ORAL
            for r in RouteOfAdministration:
                if r.value.lower() == route_str.lower() or r.name.lower() == route_str.lower():
                    route = r
                    break
            
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
