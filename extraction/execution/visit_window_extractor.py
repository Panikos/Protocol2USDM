"""
Visit Window Extractor

Extracts scheduled visits with timing windows and allowed deviations
from clinical protocol PDFs. Critical for generating realistic visit timing data.

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
    VisitWindow,
)
from .processing_warnings import _add_processing_warning

logger = logging.getLogger(__name__)


# Keywords for finding visit schedule sections
VISIT_KEYWORDS = [
    "visit", "schedule of assessments", "study schedule", "visit schedule",
    "schedule of events", "SoA", "study visits", "clinic visit",
    "screening", "baseline", "day 1", "week", "month", "follow-up",
    "end of study", "end of treatment", "early termination",
    "window", "± days", "+/- days", "allowable", "deviation",
]

# Visit name patterns
VISIT_PATTERNS = [
    # "Visit 1", "V1"
    (r'(?:Visit|V)\s*(\d+)', lambda m: f"Visit {m.group(1)}"),
    # "Screening Visit", "Baseline Visit"
    (r'(Screening|Baseline|Randomization)\s*(?:Visit)?', lambda m: m.group(1)),
    # "Week 4 Visit", "Week 12"
    (r'Week\s*(\d+)\s*(?:Visit)?', lambda m: f"Week {m.group(1)}"),
    # "Day 1", "Day 15"
    (r'Day\s*(\d+)', lambda m: f"Day {m.group(1)}"),
    # "Month 3"
    (r'Month\s*(\d+)', lambda m: f"Month {m.group(1)}"),
    # "End of Study", "End of Treatment"
    (r'(End\s+of\s+(?:Study|Treatment)|EOS|EOT)', lambda m: m.group(1)),
    # "Follow-up Visit"
    (r'(Follow[\-\s]?up)\s*(?:Visit)?', lambda m: "Follow-up"),
    # "Early Termination"
    (r'(Early\s+Termination|ET)', lambda m: "Early Termination"),
]

# Window patterns: "± 3 days", "+/- 7 days", "within 3 days"
WINDOW_PATTERNS = [
    # "± 3 days" or "+/- 3 days" or "+-3 days"
    re.compile(r'[±]\s*(\d+)\s*days?', re.IGNORECASE),
    re.compile(r'\+[\s/]*-\s*(\d+)\s*days?', re.IGNORECASE),
    # "(±3 days)" - common in tables
    re.compile(r'\(\s*[±]\s*(\d+)\s*days?\s*\)', re.IGNORECASE),
    # "within 3 days"
    re.compile(r'within\s*(\d+)\s*days?', re.IGNORECASE),
    # "-3 to +3 days" or "3 days before to 3 days after"
    re.compile(r'[\-−]\s*(\d+)\s*(?:days?)?\s*(?:to|through|and)\s*\+?\s*(\d+)\s*days?', re.IGNORECASE),
    # "window: 7 days" or "window of 7 days"
    re.compile(r'window\s*(?:of|:)?\s*(\d+)\s*days?', re.IGNORECASE),
    # "3 day window" or "7-day window"
    re.compile(r'(\d+)[\-\s]?day\s+window', re.IGNORECASE),
    # "allowable deviation: 3 days"
    re.compile(r'(?:allowable|allowed)\s+(?:deviation|variance)[:\s]+(\d+)\s*days?', re.IGNORECASE),
]

# Day/timing patterns
DAY_PATTERN = re.compile(r'Day\s*(\d+)', re.IGNORECASE)
WEEK_PATTERN = re.compile(r'Week\s*(\d+)', re.IGNORECASE)

# Default windows for visit types when not explicitly specified
DEFAULT_WINDOWS = {
    'screening': (7, 0),      # Can be up to 7 days early
    'baseline': (1, 1),       # ±1 day typically
    'day 1': (0, 0),          # Usually no window for Day 1
    'randomization': (0, 0),  # Usually no window
    'follow-up': (7, 7),      # Larger window for follow-up
    'end of study': (3, 7),   # Some flexibility
    'end of treatment': (3, 3),
    'early termination': (0, 0),  # As needed
    'default': (3, 3),        # Default ±3 days for regular visits
}


def _clean_source_text(text: str) -> str:
    """Clean source text for better readability."""
    # Replace multiple whitespace with single space
    text = re.sub(r'\s+', ' ', text)
    # Remove X marks from tables
    text = re.sub(r'\bX\b', '', text)
    # Trim
    return text.strip()[:300]


def _get_default_window(visit_name: str) -> tuple:
    """Get default window allowance based on visit type."""
    name_lower = visit_name.lower()
    for key, window in DEFAULT_WINDOWS.items():
        if key in name_lower:
            return window
    return DEFAULT_WINDOWS['default']


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


def find_visit_pages(pdf_path: str) -> List[int]:
    """Find pages likely to contain visit schedule information."""
    try:
        pages = []
        page_count = _get_page_count(pdf_path)
        
        for page_num in range(page_count):
            try:
                page_text = _extract_text_from_pages(pdf_path, pages=[page_num])
                if page_text:
                    text_lower = page_text.lower()
                    # Check for visit keywords
                    keyword_count = sum(1 for kw in VISIT_KEYWORDS if kw.lower() in text_lower)
                    # Also check for table-like patterns (SoA)
                    has_table = bool(re.search(r'visit\s*\d|week\s*\d|day\s*\d', text_lower))
                    if keyword_count >= 3 or has_table:
                        pages.append(page_num)
            except Exception:
                continue
        
        return pages[:25]  # Limit to 25 pages
        
    except Exception as e:
        logger.warning(f"Error finding visit pages: {e}")
        return []


def extract_visit_windows(
    pdf_path: str,
    model: str = "gemini-2.5-pro",
    use_llm: bool = True,
    soa_data: Optional[Dict[str, Any]] = None,
) -> ExecutionModelResult:
    """
    Extract visit windows from a protocol PDF.
    
    Args:
        pdf_path: Path to the protocol PDF
        model: LLM model to use for enhancement
        use_llm: Whether to use LLM for extraction
        soa_data: Optional SOA extraction result for enhanced context
        
    Returns:
        ExecutionModelResult with visit windows
    """
    
    logger.info("=" * 60)
    logger.info("PHASE 4B: Visit Window Extraction")
    logger.info("=" * 60)
    
    # If SOA data provided, extract visits from it first
    soa_windows = []
    if soa_data:
        soa_windows = _extract_from_soa(soa_data)
        if soa_windows:
            logger.info(f"Extracted {len(soa_windows)} visits from SOA data")
    
    # Find relevant pages
    pages = find_visit_pages(pdf_path)
    if not pages:
        pages = list(range(min(40, _get_page_count(pdf_path))))
    
    logger.info(f"Found {len(pages)} potential visit schedule pages")
    
    # Extract text
    text = _extract_text_from_pages(pdf_path, pages=pages)
    if not text:
        # If we have SOA windows but no text, return SOA windows
        if soa_windows:
            return ExecutionModelResult(
                success=True,
                data=ExecutionModelData(visit_windows=soa_windows),
                pages_used=[],
                model_used="soa_data",
            )
        return ExecutionModelResult(
            success=False,
            error="Failed to extract text from PDF",
            pages_used=pages,
            model_used=model,
        )
    
    # Heuristic extraction
    windows = _extract_windows_heuristic(text)
    logger.info(f"Heuristic extraction found {len(windows)} visit windows")
    
    # LLM enhancement
    if use_llm and len(text) > 100:
        try:
            llm_windows = _extract_windows_llm(text, model)
            if llm_windows:
                windows = _merge_windows(windows, llm_windows)
                logger.info(f"After LLM enhancement: {len(windows)} visit windows")
        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}")
            _add_processing_warning(
                category="llm_extraction_failed",
                message=f"LLM visit window extraction failed: {e}",
                context="visit_window_extraction",
                details={'error': str(e), 'fallback': 'heuristic extraction'}
            )
    
    # Merge with SOA windows (SOA data is authoritative for visit names/timing)
    if soa_windows:
        windows = _merge_windows(soa_windows, windows)
        logger.info(f"After merging with SOA: {len(windows)} visit windows")
    
    # Sort by target day (handle None values)
    windows.sort(key=lambda w: w.target_day if w.target_day is not None else 0)
    
    # Assign visit numbers if not set
    for idx, window in enumerate(windows):
        if window.visit_number is None:
            window.visit_number = idx + 1
    
    logger.info(f"Extracted {len(windows)} visit windows")
    
    return ExecutionModelResult(
        success=True,
        data=ExecutionModelData(visit_windows=windows),
        pages_used=pages,
        model_used=model if use_llm else "heuristic",
    )


def _extract_windows_heuristic(text: str) -> List[VisitWindow]:
    """Extract visit windows using pattern matching."""
    windows = []
    seen_visits = set()  # Track by normalized name
    window_id = 1
    
    # Split into lines for better context
    lines = text.split('\n')
    
    for i, line in enumerate(lines):
        # Get context (current line + next few lines)
        context = '\n'.join(lines[i:i+3])
        
        for pattern, name_func in VISIT_PATTERNS:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                visit_name = name_func(match)
                
                # Avoid duplicates using normalized name (handles EOT/EOS synonyms)
                normalized = _normalize_visit_name(visit_name)
                if normalized in seen_visits:
                    continue
                seen_visits.add(normalized)
                
                # Extract target day/week
                target_day, target_week = _extract_timing(visit_name, context)
                
                # Extract window allowance
                window_before, window_after = _extract_window_allowance(context)
                
                # Apply default windows if none found
                if window_before == 0 and window_after == 0:
                    default_before, default_after = _get_default_window(visit_name)
                    window_before = default_before
                    window_after = default_after
                
                # Determine if required
                is_required = _is_required_visit(visit_name, context)
                
                window = VisitWindow(
                    id=f"visit_{window_id}",
                    visit_name=visit_name,
                    target_day=target_day,
                    target_week=target_week,
                    window_before=window_before,
                    window_after=window_after,
                    is_required=is_required,
                    source_text=_clean_source_text(context),
                )
                windows.append(window)
                window_id += 1
    
    return windows


def _extract_timing(visit_name: str, context: str) -> Tuple[Optional[int], Optional[int]]:
    """Extract target day and week from visit name and context.
    
    Returns (target_day, target_week). target_day may be None for event-based visits.
    """
    target_day = None  # Don't default to 1 - use None for unknown
    target_week = None
    
    # Check visit name first
    day_match = DAY_PATTERN.search(visit_name)
    if day_match:
        target_day = int(day_match.group(1))
        return target_day, None
    
    week_match = WEEK_PATTERN.search(visit_name)
    if week_match:
        target_week = int(week_match.group(1))
        target_day = (target_week - 1) * 7 + 1  # Week 1 = Day 1, Week 2 = Day 8, etc.
        return target_day, target_week
    
    # Handle special visits FIRST (before context extraction)
    name_lower = visit_name.lower()
    
    # Event-based visits - these don't have fixed day values
    # Return None for target_day to indicate they're event-driven
    if any(term in name_lower for term in ['early termination', 'et visit', 'withdrawal']):
        return None, None  # Event-based, no fixed day
    if any(term in name_lower for term in ['end of treatment', 'eot', 'end-of-treatment']):
        return None, None  # Event-based, no fixed day
    if any(term in name_lower for term in ['end of study', 'eos', 'end-of-study']):
        return None, None  # Event-based, no fixed day
    if 'unscheduled' in name_lower:
        return None, None  # Event-based, no fixed day
    
    # Fixed special visits with known timing
    if 'screening' in name_lower:
        return -14, None  # Typically 2 weeks before Day 1
    if 'baseline' in name_lower:
        return 0, None  # Day before treatment
    if 'randomization' in name_lower:
        return 1, None  # Usually Day 1
    if 'follow' in name_lower:
        return 365, None  # Placeholder for follow-up (end of study + buffer)
    
    # Check context for day/week only for visits without special handling
    day_match = DAY_PATTERN.search(context)
    if day_match:
        target_day = int(day_match.group(1))
    
    week_match = WEEK_PATTERN.search(context)
    if week_match:
        target_week = int(week_match.group(1))
        if target_day is None:  # Only override if not already set
            target_day = (target_week - 1) * 7 + 1
    
    return target_day, target_week


def _extract_window_allowance(context: str) -> Tuple[int, int]:
    """Extract window allowance (days before/after target)."""
    window_before = 0
    window_after = 0
    
    for pattern in WINDOW_PATTERNS:
        match = pattern.search(context)
        if match:
            groups = match.groups()
            if len(groups) == 1:
                # Symmetric window (± X days)
                window = int(groups[0])
                window_before = window
                window_after = window
            elif len(groups) == 2:
                # Asymmetric window (-X to +Y days)
                window_before = int(groups[0])
                window_after = int(groups[1])
            break
    
    return window_before, window_after


def _is_required_visit(visit_name: str, context: str) -> bool:
    """Determine if a visit is required or optional."""
    context_lower = context.lower()
    
    # Optional indicators
    optional_keywords = ['optional', 'if applicable', 'as needed', 'prn', 'unscheduled']
    for keyword in optional_keywords:
        if keyword in context_lower:
            return False
    
    # Required indicators
    required_keywords = ['required', 'mandatory', 'must']
    for keyword in required_keywords:
        if keyword in context_lower:
            return True
    
    # Default: most visits are required
    return True


def _extract_windows_llm(text: str, model: str) -> List[VisitWindow]:
    """Extract visit windows using LLM."""
    from core.llm_client import call_llm
    import json
    
    prompt = f"""Analyze this clinical protocol text and extract ALL study visits with their timing windows.

For each visit, identify:
1. Visit name (e.g., "Screening", "Day 1", "Week 4", "End of Study")
2. Visit number (sequential)
3. Target study day (relative to Day 1)
4. Target week (if applicable)
5. Window allowance: days before and after target that are acceptable
6. Whether the visit is required or optional
7. Study epoch/phase this visit belongs to

Text to analyze:
{text[:8000]}

Return JSON format:
{{
    "visits": [
        {{
            "visitName": "Screening",
            "visitNumber": 1,
            "targetDay": -14,
            "targetWeek": null,
            "windowBefore": 7,
            "windowAfter": 0,
            "isRequired": true,
            "epoch": "Screening"
        }},
        {{
            "visitName": "Day 1",
            "visitNumber": 2,
            "targetDay": 1,
            "targetWeek": 1,
            "windowBefore": 0,
            "windowAfter": 0,
            "isRequired": true,
            "epoch": "Treatment"
        }},
        {{
            "visitName": "Week 4",
            "visitNumber": 3,
            "targetDay": 29,
            "targetWeek": 4,
            "windowBefore": 3,
            "windowAfter": 3,
            "isRequired": true,
            "epoch": "Treatment"
        }}
    ]
}}

Extract all visits from the schedule. Return valid JSON only."""

    try:
        result = call_llm(prompt, model_name=model, extractor_name="visit_window")
        
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
        windows = []
        
        for item in data.get('visits', []):
            window = VisitWindow(
                id=f"visit_llm_{item.get('visitNumber', len(windows)+1)}",
                visit_name=item.get('visitName', 'Unknown'),
                visit_number=item.get('visitNumber'),
                target_day=item.get('targetDay', 1),
                target_week=item.get('targetWeek'),
                window_before=item.get('windowBefore', 0),
                window_after=item.get('windowAfter', 0),
                is_required=item.get('isRequired', True),
                epoch=item.get('epoch'),
            )
            windows.append(window)
        
        return windows
        
    except Exception as e:
        logger.error(f"LLM visit extraction failed: {e}")
        return []


def _extract_from_soa(soa_data: Dict[str, Any]) -> List[VisitWindow]:
    """
    Extract visit windows from SOA extraction data.
    
    SOA data contains encounters and timepoints which map directly to visits.
    This provides authoritative visit names and timing from the actual SoA table.
    """
    windows = []
    
    try:
        # Navigate to timeline data
        study = soa_data.get("study", {})
        versions = study.get("versions", [])
        if not versions:
            return []
        
        timeline = versions[0].get("timeline", {})
        
        # Get encounters (visits)
        encounters = timeline.get("encounters", [])
        # Also try plannedTimepoints for legacy format
        timepoints = timeline.get("plannedTimepoints", [])
        # Get epochs for context
        epochs = {e.get("id"): e for e in timeline.get("epochs", [])}
        
        # Build timepoint lookup for window info
        timepoint_map = {t.get("encounterId"): t for t in timepoints}
        
        for idx, encounter in enumerate(encounters):
            enc_id = encounter.get("id", f"enc_{idx+1}")
            enc_name = encounter.get("name", encounter.get("label", f"Visit {idx+1}"))
            
            # Get epoch for this encounter
            epoch_id = encounter.get("epochId")
            epoch_name = epochs.get(epoch_id, {}).get("name") if epoch_id else None
            
            # Get timepoint for timing info
            timepoint = timepoint_map.get(enc_id, {})
            value_label = timepoint.get("valueLabel", "")
            
            # Parse target day from value label or name
            target_day, target_week = _extract_timing(enc_name, value_label)
            
            # Extract window from encounter or timepoint
            window_before = encounter.get("windowBefore", 0)
            window_after = encounter.get("windowAfter", 0)
            
            # Check for window in scheduledAt timing
            scheduled_at = encounter.get("scheduledAt", {})
            if scheduled_at:
                window_lower = scheduled_at.get("windowLower", 0)
                window_upper = scheduled_at.get("windowUpper", 0)
                if window_lower or window_upper:
                    window_before = abs(window_lower) if window_lower else 0
                    window_after = window_upper if window_upper else 0
            
            window = VisitWindow(
                id=f"visit_soa_{idx+1}",
                visit_name=enc_name,
                visit_number=idx + 1,
                target_day=target_day,
                target_week=target_week,
                window_before=window_before,
                window_after=window_after,
                is_required=True,
                epoch=epoch_name,
                source_text=f"From SOA: {enc_name}",
            )
            windows.append(window)
        
        return windows
        
    except Exception as e:
        logger.warning(f"Error extracting visits from SOA: {e}")
        return []


def _normalize_visit_name(name: str) -> str:
    """Normalize visit name for comparison - extract core identifier."""
    name_lower = name.lower().strip()
    # Remove parenthetical suffixes like "(CRU Discharge)", "(Treatment Start)"
    name_lower = re.sub(r'\s*\([^)]+\)\s*$', '', name_lower)
    # Remove common suffixes
    name_lower = re.sub(r'\s*[-/]\s*(discharge|start|return|end|visit).*$', '', name_lower)
    
    # Normalize synonymous visit names to canonical form
    # EOT variants -> "end of treatment"
    if name_lower in ['eot', 'end of treatment', 'end-of-treatment', 'treatment end']:
        return 'end of treatment'
    # EOS variants -> "end of study"
    if name_lower in ['eos', 'end of study', 'end-of-study', 'study end', 'study completion']:
        return 'end of study'
    # ET variants -> "early termination"
    if name_lower in ['et', 'early termination', 'early withdrawal', 'discontinuation']:
        return 'early termination'
    
    return name_lower.strip()


def _merge_windows(
    primary: List[VisitWindow],
    secondary: List[VisitWindow]
) -> List[VisitWindow]:
    """
    Merge visit windows from two sources, deduplicating by target_day and normalized name.
    
    Primary source (typically SOA) takes precedence. Secondary visits (LLM/heuristic)
    are only added if they don't duplicate an existing visit.
    
    Event-based visits (target_day=None) are deduplicated by normalized name only.
    Scheduled visits are deduplicated by target_day primarily, with name as fallback.
    """
    result: List[VisitWindow] = []
    by_target_day: Dict[int, VisitWindow] = {}  # Only for actual day values
    by_normalized_name: Dict[str, VisitWindow] = {}
    
    for window in primary:
        norm_name = _normalize_visit_name(window.visit_name)
        
        # Check for duplicate by normalized name first
        if norm_name and norm_name in by_normalized_name:
            continue
        
        # For scheduled visits (has target_day), also check by day
        if window.target_day is not None:
            if window.target_day in by_target_day:
                existing = by_target_day[window.target_day]
                # Keep the one with longer (more descriptive) name
                if len(window.visit_name) > len(existing.visit_name):
                    # Replace existing
                    result.remove(existing)
                    result.append(window)
                    by_target_day[window.target_day] = window
                    if norm_name:
                        by_normalized_name[norm_name] = window
                continue
            by_target_day[window.target_day] = window
        
        # Add to result
        result.append(window)
        if norm_name:
            by_normalized_name[norm_name] = window
    
    # Now merge secondary, avoiding duplicates
    for window in secondary:
        norm_name = _normalize_visit_name(window.visit_name)
        
        # Skip if we have a visit with similar normalized name
        if norm_name and norm_name in by_normalized_name:
            existing = by_normalized_name[norm_name]
            # Enhance existing with secondary's details if useful
            if (window.window_before or 0) > 0 and (existing.window_before or 0) == 0:
                existing.window_before = window.window_before
            if (window.window_after or 0) > 0 and (existing.window_after or 0) == 0:
                existing.window_after = window.window_after
            if window.epoch and not existing.epoch:
                existing.epoch = window.epoch
            continue
        
        # For scheduled visits, also check by target_day
        if window.target_day is not None and window.target_day in by_target_day:
            existing = by_target_day[window.target_day]
            # Enhance existing
            if (window.window_before or 0) > 0 and (existing.window_before or 0) == 0:
                existing.window_before = window.window_before
            if (window.window_after or 0) > 0 and (existing.window_after or 0) == 0:
                existing.window_after = window.window_after
            if window.epoch and not existing.epoch:
                existing.epoch = window.epoch
            continue
        
        # This is a genuinely new visit, add it
        result.append(window)
        if window.target_day is not None:
            by_target_day[window.target_day] = window
        if norm_name:
            by_normalized_name[norm_name] = window
    
    return result
