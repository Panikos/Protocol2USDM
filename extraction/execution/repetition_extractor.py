"""
Repetition Extractor

Detects and encodes repetition patterns from protocol PDFs:
- Daily collections (e.g., "daily urine collection")
- Interval sampling (e.g., "every 5 minutes for 30 minutes")
- Treatment cycles (e.g., "21-day cycles until progression")
- Continuous monitoring windows (e.g., "Days -4 to -1")

Per USDM workshop manual: "Treatment cycles represent a common pattern 
in clinical trials, particularly in oncology studies."
"""

import re
import json
import logging
from typing import List, Dict, Any, Optional, Tuple

from .schema import (
    Repetition, RepetitionType, SamplingConstraint,
    ExecutionModelResult, ExecutionModelData, ActivityBinding,
    AnalysisWindow, TimeAnchor, AnchorType
)

logger = logging.getLogger(__name__)


# =============================================================================
# REPETITION DETECTION PATTERNS - Organized by therapeutic area
# =============================================================================

# Daily collection patterns
DAILY_PATTERNS: List[Tuple[str, float]] = [
    # General
    (r'daily\s+(?:urine|blood|sample|collection|measurement|assessment)', 0.90),
    (r'once\s+daily', 0.85),
    (r'every\s+day', 0.85),
    (r'each\s+day\s+(?:of|during)', 0.80),
    (r'(?:collect|measure|assess)\s+daily', 0.85),
    (r'(?:qd|q\.d\.|od)', 0.80),  # Medical abbreviations
    
    # Diabetes/Metabolic
    (r'daily\s+(?:glucose|blood\s+sugar|bg)\s+(?:monitoring|measurement)', 0.90),
    (r'(?:smbg|self[\-\s]?monitoring)\s+daily', 0.85),
    (r'daily\s+(?:diary|log)\s+(?:entry|entries)', 0.80),
    (r'daily\s+weight', 0.85),
    
    # Cardiology
    (r'daily\s+(?:blood\s+pressure|bp)\s+(?:monitoring|measurement)', 0.90),
    (r'daily\s+(?:heart\s+rate|hr|pulse)', 0.85),
    (r'daily\s+(?:ecg|ekg|holter)', 0.85),
    
    # Oncology
    (r'daily\s+(?:oral|po)\s+(?:dosing|administration)', 0.85),
    (r'daily\s+(?:symptom|toxicity)\s+(?:assessment|diary)', 0.80),
    
    # Neurology
    (r'daily\s+(?:seizure|headache|migraine)\s+(?:diary|log)', 0.85),
    (r'daily\s+(?:pain|symptom)\s+(?:score|rating)', 0.80),
    
    # Rare Disease
    (r'daily\s+(?:enzyme|substrate|biomarker)\s+(?:level|measurement)', 0.85),
    
    # Infectious Disease
    (r'daily\s+(?:temperature|fever)\s+(?:monitoring|check)', 0.85),
    (r'daily\s+(?:viral|bacterial)\s+(?:load|count)', 0.85),
]

# Interval sampling patterns
INTERVAL_PATTERNS: List[Tuple[str, float]] = [
    # Minutes - General
    (r'every\s+(\d+)\s*(?:min(?:ute)?s?)', 0.90),
    (r'at\s+(?:time\s+)?(\d+(?:,\s*\d+)+)\s*(?:min(?:ute)?s?)', 0.90),
    (r'(\d+)\s*(?:min(?:ute)?s?)\s+intervals?', 0.85),
    (r'q(\d+)min', 0.85),
    
    # Hours - General
    (r'every\s+(\d+)\s*(?:hour|hr)s?', 0.90),
    (r'(\d+)\s*(?:hour|hr)s?\s+intervals?', 0.85),
    (r'q(\d+)h', 0.85),  # Medical notation: q4h, q6h, etc.
    (r'(?:bid|b\.i\.d\.)', 0.80),  # Twice daily
    (r'(?:tid|t\.i\.d\.)', 0.80),  # Three times daily
    (r'(?:qid|q\.i\.d\.)', 0.80),  # Four times daily
    
    # PK/PD Sampling - Dense timepoints
    (r'(?:pk|pharmacokinetic)\s+(?:samples?|sampling)\s+(?:at|:)\s*([\d,\s\.]+)', 0.95),
    (r'(?:pd|pharmacodynamic)\s+(?:samples?|sampling)\s+(?:at|:)\s*([\d,\s\.]+)', 0.95),
    (r'(?:0|pre[\-\s]?dose)[,\s]+(\d+(?:[,\s]+\d+)*)\s*(?:min|hour|hr)', 0.90),
    (r'time\s+(?:0|zero)[,\s]+(\d+(?:[,\s]+\d+)*)', 0.85),
    
    # Diabetes - Glucose monitoring
    (r'glucose\s+(?:every|q)\s*(\d+)\s*(?:min|hour|hr)', 0.90),
    (r'(?:cgm|continuous\s+glucose)', 0.85),
    (r'glucose\s+at\s+(\d+(?:,\s*\d+)+)\s*(?:min|hour)', 0.90),
    
    # Cardiology - ECG/BP intervals
    (r'(?:ecg|ekg|bp)\s+(?:every|q)\s*(\d+)\s*(?:min|hour|hr)', 0.90),
    (r'(?:holter|ambulatory)\s+(?:monitoring|ecg)', 0.85),
    
    # Vaccines - Post-vaccination monitoring
    (r'post[\-\s]?(?:vaccination|injection)\s+(?:at|every)\s*(\d+)\s*(?:min|hour)', 0.90),
    (r'observation\s+(?:period|every)\s*(\d+)\s*(?:min|hour)', 0.85),
    
    # Infusion monitoring
    (r'(?:during|post)\s+infusion\s+(?:at|every)\s*(\d+)\s*(?:min|hour)', 0.90),
    (r'infusion[\-\s]?related\s+(?:monitoring|assessment)', 0.80),
]

# Treatment cycle patterns
CYCLE_PATTERNS: List[Tuple[str, float]] = [
    # General cycle lengths
    (r'(\d+)[\s-]*day\s+cycle', 0.90),
    (r'cycle\s+(?:length|duration)\s*(?:is|of|:)?\s*(\d+)\s*days?', 0.90),
    (r'repeat(?:ed)?\s+every\s+(\d+)\s*(?:days?|weeks?)', 0.85),
    (r'(\d+)[\s-]*week\s+cycle', 0.90),
    
    # Oncology - Common cycle lengths
    (r'(?:21|28|35|42)[\s-]*day\s+(?:treatment\s+)?cycle', 0.90),
    (r'(?:3|4|6)[\s-]*week\s+(?:treatment\s+)?cycle', 0.90),
    (r'cycle\s+\d+\s+day\s+\d+', 0.85),  # Cycle X Day Y notation
    (r'c\d+d\d+', 0.80),  # C1D1 notation
    
    # Oncology - Exit conditions
    (r'until\s+(?:disease\s+)?progression', 0.80),
    (r'until\s+(?:unacceptable\s+)?toxicity', 0.80),
    (r'until\s+(?:death|withdrawal|discontinuation)', 0.75),
    (r'(?:maximum|up\s+to)\s+(\d+)\s+cycles?', 0.85),
    
    # Maintenance/Continuation
    (r'maintenance\s+(?:phase|therapy)\s+(?:every|q)\s*(\d+)\s*(?:days?|weeks?)', 0.85),
    (r'(?:continue|continued)\s+(?:until|for)\s+(\d+)\s*(?:cycles?|weeks?|months?)', 0.80),
    
    # Vaccines - Dosing schedules
    (r'(?:prime|boost(?:er)?)\s+(?:at|on)\s+(?:day|week)\s+(\d+)', 0.85),
    (r'(?:second|third|booster)\s+(?:dose|vaccination)\s+(?:at|on)', 0.85),
    (r'vaccination\s+(?:at|on)\s+(?:day|week)s?\s+(\d+(?:,\s*\d+)*)', 0.90),
    
    # Dialysis
    (r'(?:dialysis|hemodialysis)\s+(?:sessions?|days?)', 0.85),
    (r'(?:3|three)\s+times?\s+(?:per|a)\s+week', 0.85),
]

# Continuous window patterns
WINDOW_PATTERNS: List[Tuple[str, float]] = [
    # Day range patterns - capture sign with number using ([-–−]?\d+)
    (r'day(?:s)?\s*([-–−]?\d+)\s*(?:to|through|[-–−])\s*(?:day\s*)?([-–−]?\d+)', 0.90),
    (r'from\s+day\s*([-–−]?\d+)\s+to\s+day\s*([-–−]?\d+)', 0.90),
    (r'during\s+(?:the\s+)?(\d+)[\s-]*day\s+(?:period|window)', 0.85),
    (r'throughout\s+(?:the\s+)?(?:treatment|study)\s+period', 0.75),
    
    # Week range patterns
    (r'week(?:s)?\s*(\d+)\s*(?:to|through|[-–])\s*(?:week\s*)?(\d+)', 0.90),
    (r'from\s+week\s*(\d+)\s+to\s+week\s*(\d+)', 0.90),
    
    # Specific windows
    (r'(?:screening|washout|run[\-\s]?in)\s+(?:period|window|phase)', 0.85),
    (r'(?:treatment|active|dosing)\s+(?:period|window|phase)', 0.85),
    (r'(?:follow[\-\s]?up|observation|safety)\s+(?:period|window|phase)', 0.85),
    
    # Pre/Post patterns
    (r'(?:pre|post)[\-\s]?(?:dose|treatment|surgery|procedure)\s+(?:period|window)', 0.85),
    (r'(\d+)\s+(?:days?|hours?)\s+(?:before|after|pre|post)', 0.80),
    
    # Hospitalization/Confinement
    (r'(?:in[\-\s]?patient|hospitalization|confinement)\s+(?:period|days?)', 0.85),
    (r'(?:days?\s+)?[-–]?\s*(\d+)\s+to\s+(?:day\s+)?(\d+)\s+(?:in[\-\s]?patient|hospitalized)', 0.85),
    
    # Balance/Metabolic windows
    (r'(?:balance|metabolic)\s+(?:period|collection|study)', 0.90),
    (r'(?:24|48|72)[\-\s]?(?:hour|hr)\s+(?:urine|stool|collection)', 0.90),
    
    # Crossover washout
    (r'washout\s+(?:period|phase)\s+(?:of\s+)?(\d+)\s*(?:days?|weeks?)', 0.90),
    (r'(?:minimum|at\s+least)\s+(\d+)\s*(?:days?|weeks?)\s+washout', 0.85),
]

# Keywords for finding repetition-relevant pages
REPETITION_KEYWORDS = [
    r'daily',
    r'every\s+\d+',
    r'cycle',
    r'repeat',
    r'interval',
    r'continuous',
    r'throughout',
    r'sampling',
    r'collection\s+schedule',
    r'pk\s+(?:sampling|profile)',
    r'pd\s+(?:sampling|profile)',
    r'pharmacokinetic',
    r'pharmacodynamic',
    r'glucose\s+monitoring',
    r'blood\s+pressure',
    r'holter',
    r'cgm',
    r'infusion',
    r'vaccination',
    r'dialysis',
    r'balance',
    r'washout',
]


def find_repetition_pages(
    pdf_path: str,
    max_pages_to_scan: int = 50,
) -> List[int]:
    """
    Find pages likely to contain repetition/cycle definitions.
    
    Args:
        pdf_path: Path to protocol PDF
        max_pages_to_scan: Maximum pages to scan
        
    Returns:
        List of 0-indexed page numbers
    """
    import fitz
    
    pattern = re.compile('|'.join(REPETITION_KEYWORDS), re.IGNORECASE)
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
        
        logger.info(f"Found {len(pages)} potential repetition pages")
        
    except Exception as e:
        logger.error(f"Error scanning PDF for repetitions: {e}")
        pages = list(range(min(25, max_pages_to_scan)))
    
    return pages


def _detect_daily_patterns(text: str) -> List[Repetition]:
    """Detect daily collection patterns."""
    repetitions = []
    
    for pattern, confidence in DAILY_PATTERNS:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        
        for match in matches:
            # Extract context
            start = max(0, match.start() - 150)
            end = min(len(text), match.end() + 150)
            context = text[start:end]
            
            # Try to find associated activity
            activity_match = re.search(
                r'(urine|blood|sample|glucose|vital|weight|diary)',
                context, re.IGNORECASE
            )
            activity_hint = activity_match.group(1) if activity_match else None
            
            # Try to find duration
            duration = _extract_duration_from_context(context)
            
            repetitions.append(Repetition(
                id=f"rep_daily_{len(repetitions)+1}",
                type=RepetitionType.DAILY,
                interval="P1D",
                start_offset=duration.get('start') if duration else None,
                end_offset=duration.get('end') if duration else None,
                source_text=match.group(),
            ))
    
    return repetitions


def _detect_interval_patterns(text: str) -> List[Repetition]:
    """Detect interval sampling patterns (e.g., every 5 minutes)."""
    repetitions = []
    
    for pattern, confidence in INTERVAL_PATTERNS:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        
        for match in matches:
            groups = match.groups()
            
            # Parse interval value
            if groups:
                interval_val = groups[0]
                # Check if it's a list of timepoints (e.g., "0, 5, 10, 15")
                if ',' in str(interval_val):
                    timepoints = [t.strip() for t in interval_val.split(',')]
                    min_obs = len(timepoints)
                    # Calculate interval from timepoints
                    try:
                        nums = [int(t) for t in timepoints]
                        if len(nums) >= 2:
                            interval_min = nums[1] - nums[0]
                            interval_iso = f"PT{interval_min}M"
                        else:
                            interval_iso = None
                    except ValueError:
                        interval_iso = None
                        min_obs = None
                else:
                    # Single interval value
                    try:
                        interval_num = int(interval_val)
                        # Determine unit from pattern
                        if 'hour' in pattern or 'hr' in pattern or pattern.endswith('h'):
                            interval_iso = f"PT{interval_num}H"
                        else:
                            interval_iso = f"PT{interval_num}M"
                        min_obs = None
                    except ValueError:
                        interval_iso = None
                        min_obs = None
            else:
                interval_iso = None
                min_obs = None
            
            repetitions.append(Repetition(
                id=f"rep_interval_{len(repetitions)+1}",
                type=RepetitionType.INTERVAL,
                interval=interval_iso,
                min_observations=min_obs,
                source_text=match.group(),
            ))
    
    return repetitions


def _detect_cycle_patterns(text: str) -> List[Repetition]:
    """Detect treatment cycle patterns."""
    repetitions = []
    
    for pattern, confidence in CYCLE_PATTERNS:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        
        for match in matches:
            groups = match.groups()
            
            # Extract cycle length
            cycle_days = None
            if groups:
                try:
                    cycle_days = int(groups[0])
                except (ValueError, IndexError):
                    pass
            
            # Look for exit condition in context
            start = max(0, match.start() - 200)
            end = min(len(text), match.end() + 200)
            context = text[start:end]
            
            exit_condition = None
            if 'progression' in context.lower():
                exit_condition = "Disease progression"
            elif 'toxicity' in context.lower():
                exit_condition = "Unacceptable toxicity"
            
            cycle_length_iso = f"P{cycle_days}D" if cycle_days else None
            
            repetitions.append(Repetition(
                id=f"rep_cycle_{len(repetitions)+1}",
                type=RepetitionType.CYCLE,
                cycle_length=cycle_length_iso,
                exit_condition=exit_condition,
                source_text=match.group(),
            ))
    
    return repetitions


def _detect_window_patterns(text: str) -> List[Repetition]:
    """Detect continuous collection windows (e.g., Days -4 to -1)."""
    repetitions = []
    
    for pattern, confidence in WINDOW_PATTERNS:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        
        for match in matches:
            groups = match.groups()
            
            start_day = None
            end_day = None
            
            if len(groups) >= 2:
                try:
                    # Use robust day parsing to handle negative signs
                    start_str = groups[0]
                    end_str = groups[1]
                    
                    start_day = _parse_day_with_sign(start_str)
                    end_day = _parse_day_with_sign(end_str)
                        
                except (ValueError, IndexError):
                    pass
            
            start_iso = f"P{abs(start_day)}D" if start_day else None
            if start_day and start_day < 0:
                start_iso = f"-P{abs(start_day)}D"
            
            end_iso = f"P{abs(end_day)}D" if end_day else None
            if end_day and end_day < 0:
                end_iso = f"-P{abs(end_day)}D"
            
            repetitions.append(Repetition(
                id=f"rep_window_{len(repetitions)+1}",
                type=RepetitionType.CONTINUOUS,
                start_offset=start_iso,
                end_offset=end_iso,
                source_text=match.group(),
            ))
    
    return repetitions


def _extract_duration_from_context(context: str) -> Optional[Dict[str, str]]:
    """Extract start/end duration from surrounding context."""
    # Look for day ranges
    day_range = re.search(
        r'day(?:s)?\s*[-–]?\s*(\d+)\s*(?:to|through|[-–])\s*(?:day\s*)?[-–]?\s*(\d+)',
        context, re.IGNORECASE
    )
    
    if day_range:
        start = int(day_range.group(1))
        end = int(day_range.group(2))
        return {
            'start': f"P{start}D",
            'end': f"P{end}D",
        }
    
    return None


# =============================================================================
# FIX 2: DAILY REPETITION BINDING WITH EXPECTED COUNTS
# =============================================================================

# Patterns for activities that need daily binding
DAILY_COLLECTION_ACTIVITIES = [
    (r'(?:24[\-\s]?hour|daily)\s+urine\s+(?:collection|sample)', 'urine_collection'),
    (r'(?:feces|stool|fecal)\s+(?:collection|sample)', 'feces_collection'),
    (r'(?:controlled|standardized)\s+(?:meal|diet)', 'controlled_meal'),
    (r'daily\s+(?:meal|food)\s+(?:intake|consumption)', 'meal_intake'),
    (r'(?:copper|cu|molybdenum|mo)\s+balance', 'balance_collection'),
    (r'daily\s+weight', 'daily_weight'),
    (r'daily\s+diary', 'daily_diary'),
]


def _detect_daily_activity_bindings(text: str) -> Tuple[List[ActivityBinding], List[Repetition]]:
    """
    FIX 2: Detect daily collection activities and create explicit bindings.
    
    This addresses the feedback: "daily repetition is not machine-enforced"
    by encoding "every day" semantics with expected occurrence counts.
    """
    bindings = []
    daily_repetitions = []
    
    # Pattern to find day ranges like "Days -4 through -1", "Day 2-3", "Days 30-35"
    day_range_pattern = re.compile(
        r'(?:days?\s*)?([-–]?\d+)\s*(?:to|through|[-–])\s*(?:days?\s*)?([-–]?\d+)',
        re.IGNORECASE
    )
    
    for activity_pattern, activity_type in DAILY_COLLECTION_ACTIVITIES:
        matches = re.finditer(activity_pattern, text, re.IGNORECASE)
        
        for match in matches:
            # Get context around match to find day range
            start_ctx = max(0, match.start() - 200)
            end_ctx = min(len(text), match.end() + 200)
            context = text[start_ctx:end_ctx]
            
            # Find day ranges in context
            range_matches = day_range_pattern.finditer(context)
            
            for range_match in range_matches:
                try:
                    # FIX 4: Use robust day parsing to preserve negative signs
                    start_day = _parse_day_with_sign(range_match.group(1))
                    end_day = _parse_day_with_sign(range_match.group(2))
                    
                    # Calculate expected daily occurrences
                    expected_count = abs(end_day - start_day) + 1
                    
                    # Create repetition with count
                    # FIX 4: Proper ISO8601 duration with negative sign
                    rep_id = f"rep_daily_bound_{len(daily_repetitions)+1}"
                    daily_repetitions.append(Repetition(
                        id=rep_id,
                        type=RepetitionType.DAILY,
                        interval="P1D",
                        count=expected_count,
                        start_offset=f"P{start_day}D" if start_day >= 0 else f"-P{abs(start_day)}D",
                        end_offset=f"P{end_day}D" if end_day >= 0 else f"-P{abs(end_day)}D",
                        source_text=f"{match.group()} ({range_match.group()})",
                    ))
                    
                    # Create binding
                    bindings.append(ActivityBinding(
                        id=f"binding_{len(bindings)+1}",
                        activity_id=activity_type,
                        activity_name=match.group(),
                        repetition_id=rep_id,
                        expected_occurrences=expected_count,
                        source_text=f"Daily {activity_type} from Day {start_day} to Day {end_day}",
                    ))
                    
                except (ValueError, AttributeError):
                    continue
    
    return bindings, daily_repetitions


# =============================================================================
# FIX 3: ANALYSIS WINDOW EXTRACTION
# =============================================================================

# Patterns for analysis window types
ANALYSIS_WINDOW_PATTERNS = [
    # Baseline windows
    (r'(?:pre[\-\s]?treatment\s+)?baseline\s+(?:period|window|phase)?\s*(?:days?\s*)?([-–]?\d+)\s*(?:to|through|[-–])\s*(?:days?\s*)?([-–]?\d+)', 'baseline'),
    (r'days?\s*([-–]\d+)\s*(?:to|through|[-–])\s*([-–]?\d+)\s*(?:as\s+)?baseline', 'baseline'),
    
    # Accumulation windows
    (r'accumulation\s+(?:period|window|phase)', 'accumulation'),
    (r'(?:initial|early)\s+(?:treatment\s+)?(?:period|phase)', 'accumulation'),
    
    # Steady-state windows
    (r'steady[\-\s]?state\s+(?:period|window|phase)', 'steady_state'),
    (r'(?:maintenance|stable)\s+(?:treatment\s+)?(?:period|phase)', 'steady_state'),
    
    # Treatment windows
    (r'treatment\s+(?:period|window|phase)\s*(?:\d+)?', 'treatment'),
    (r'(?:active|dosing)\s+(?:period|phase)', 'treatment'),
]


def _parse_day_with_sign(day_str: str) -> int:
    """
    Parse day string preserving negative sign.
    
    Handles formats like: "-4", "−4", "–4", "Day -4", "Day−4"
    """
    if not day_str:
        return 0
    
    # Normalize various dash/minus characters to standard minus
    normalized = day_str.replace('–', '-').replace('−', '-').replace('—', '-')
    
    # Remove any non-numeric characters except minus at start
    cleaned = re.sub(r'[^\d\-]', '', normalized)
    
    # Handle cases where minus is separated: "- 4" -> "-4"
    if cleaned.startswith('-'):
        return int(cleaned)
    
    # Check if original had a negative indicator before digits
    if re.search(r'[-–−—]\s*\d', day_str):
        # Extract just the number and make it negative
        num_match = re.search(r'(\d+)', day_str)
        if num_match:
            return -int(num_match.group(1))
    
    return int(cleaned) if cleaned else 0


def _detect_analysis_windows(text: str) -> List[AnalysisWindow]:
    """
    FIX 3: Detect analysis windows (baseline, accumulation, steady-state).
    
    This addresses the feedback: "Baseline vs accumulation vs steady-state 
    windows are not explicit as computable phases"
    """
    windows = []
    
    # First, find explicit day ranges for baseline
    # Pattern handles "Day -4 through Day -1", "Days -4 to -1", etc.
    baseline_pattern = re.compile(
        r'(?:baseline|pre[\-\s]?treatment)\s+(?:period|window|phase|days?)?\s*[:]?\s*'
        r'(?:days?\s*)?([-–−]?\s*\d+)\s*(?:to|through|[-–−])\s*(?:days?\s*)?([-–−]?\s*\d+)',
        re.IGNORECASE
    )
    
    for match in baseline_pattern.finditer(text):
        try:
            start_day = _parse_day_with_sign(match.group(1))
            end_day = _parse_day_with_sign(match.group(2))
            
            windows.append(AnalysisWindow(
                id=f"window_baseline_{len(windows)+1}",
                window_type="baseline",
                name="Baseline Period",
                start_day=start_day,
                end_day=end_day,
                description=f"Pre-treatment baseline from Day {start_day} to Day {end_day}",
                source_text=match.group(),
            ))
        except (ValueError, AttributeError):
            continue
    
    # Find treatment windows with day ranges
    treatment_pattern = re.compile(
        r'(?:treatment|dosing|active)\s+(?:period|window|phase)?\s*[:\-]?\s*'
        r'(?:days?\s*)?(\d+)\s*(?:to|through|[-–])\s*(?:days?\s*)?(\d+)',
        re.IGNORECASE
    )
    
    for match in treatment_pattern.finditer(text):
        try:
            start_day = int(match.group(1))
            end_day = int(match.group(2))
            
            windows.append(AnalysisWindow(
                id=f"window_treatment_{len(windows)+1}",
                window_type="treatment",
                name="Treatment Period",
                start_day=start_day,
                end_day=end_day,
                description=f"Active treatment from Day {start_day} to Day {end_day}",
                source_text=match.group(),
            ))
        except (ValueError, AttributeError):
            continue
    
    # Find steady-state references
    steady_state_pattern = re.compile(
        r'steady[\-\s]?state\s+(?:period|window|phase|days?)?\s*[:\-]?\s*'
        r'(?:days?\s*)?(\d+)\s*(?:to|through|[-–])\s*(?:days?\s*)?(\d+)',
        re.IGNORECASE
    )
    
    for match in steady_state_pattern.finditer(text):
        try:
            start_day = int(match.group(1))
            end_day = int(match.group(2))
            
            windows.append(AnalysisWindow(
                id=f"window_steady_state_{len(windows)+1}",
                window_type="steady_state",
                name="Steady-State Period",
                start_day=start_day,
                end_day=end_day,
                description=f"Steady-state from Day {start_day} to Day {end_day}",
                source_text=match.group(),
            ))
        except (ValueError, AttributeError):
            continue
    
    return windows


# =============================================================================
# FIX 4: COLLECTION DAY ANCHOR DETECTION
# =============================================================================

def _detect_collection_day_anchors(text: str) -> List[TimeAnchor]:
    """
    FIX 4: Detect 24-hour collection day boundaries.
    
    This addresses the feedback: "need a stable anchor for 24-hour collection 
    boundaries"
    """
    anchors = []
    
    # Patterns for 24-hour collection definitions
    collection_patterns = [
        (r'24[\-\s]?hour\s+(?:urine|collection)\s+(?:period|window|from)\s*'
         r'(\d{1,2})[:\.]?(\d{2})?\s*(?:am|pm|hours?)?', 'urine'),
        (r'collection\s+(?:day|period)\s+(?:begins?|starts?|from)\s*'
         r'(\d{1,2})[:\.]?(\d{2})?\s*(?:am|pm|hours?)?', 'general'),
        (r'(?:morning|am)\s+(?:of\s+)?day\s+\d+\s+to\s+(?:morning|am)\s+(?:of\s+)?day\s+\d+', 'morning_anchor'),
    ]
    
    # Collect all source texts for CollectionDay anchor
    collection_sources = []
    
    for pattern, anchor_type in collection_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            collection_sources.append(match.group())
    
    # Also detect generic 24-hour collection mentions
    generic_24h = re.finditer(
        r'(?:complete\s+)?24[\-\s]?hour\s+(?:urine|stool|feces|collection)',
        text, re.IGNORECASE
    )
    for match in generic_24h:
        if match.group() not in collection_sources:
            collection_sources.append(match.group())
    
    # Create only ONE CollectionDay anchor (they're all the same concept)
    if collection_sources:
        anchors.append(TimeAnchor(
            id="anchor_collection_1",
            definition="24-hour collection period",
            anchor_type=AnchorType.COLLECTION_DAY,
            source_text=collection_sources[0],  # Use first match as source
        ))
    
    return anchors


def _detect_sampling_constraints(text: str) -> List[SamplingConstraint]:
    """Detect minimum sampling requirements from PK/PD tables."""
    constraints = []
    
    # Look for PK sampling timepoints
    pk_pattern = r'(?:pk|pharmacokinetic)\s+(?:sampling|sample|timepoint)s?\s*[:\-]?\s*([\d,\s\.]+(?:min|hour|hr|h)?)'
    matches = re.finditer(pk_pattern, text, re.IGNORECASE)
    
    for match in matches:
        timepoints_str = match.group(1)
        # Parse timepoints
        timepoints = re.findall(r'(\d+(?:\.\d+)?)', timepoints_str)
        
        if len(timepoints) >= 3:
            constraints.append(SamplingConstraint(
                id=f"sampling_{len(constraints)+1}",
                activity_id="pk_sampling",  # Placeholder
                min_per_window=len(timepoints),
                timepoints=timepoints,
                source_text=match.group(),
            ))
    
    return constraints


def extract_repetitions(
    pdf_path: str,
    model: str = "gemini-2.5-pro",
    pages: Optional[List[int]] = None,
    use_llm: bool = False,
    existing_activities: Optional[List[Dict[str, Any]]] = None,
    existing_encounters: Optional[List[Dict[str, Any]]] = None,
) -> ExecutionModelResult:
    """
    Extract repetition patterns from protocol PDF.
    
    Args:
        pdf_path: Path to protocol PDF
        model: LLM model to use (if use_llm=True)
        pages: Specific pages to analyze (auto-detected if None)
        use_llm: Whether to use LLM for enhanced extraction
        existing_activities: SoA activities for binding repetitions to actual activities
        existing_encounters: SoA encounters for binding repetitions to visits
        
    Returns:
        ExecutionModelResult with extracted Repetitions
    """
    from core.pdf_utils import extract_text_from_pages, get_page_count
    
    logger.info("Starting repetition extraction...")
    
    # Find relevant pages
    if pages is None:
        pages = find_repetition_pages(pdf_path)
    
    if not pages:
        logger.warning("No repetition pages found, using first 25 pages")
        pages = list(range(min(25, get_page_count(pdf_path))))
    
    # Extract text
    text = extract_text_from_pages(pdf_path, pages)
    if not text:
        return ExecutionModelResult(
            success=False,
            error="Failed to extract text from PDF",
            pages_used=pages,
            model_used=model,
        )
    
    # Run all detection patterns
    all_repetitions = []
    all_repetitions.extend(_detect_daily_patterns(text))
    all_repetitions.extend(_detect_interval_patterns(text))
    all_repetitions.extend(_detect_cycle_patterns(text))
    all_repetitions.extend(_detect_window_patterns(text))
    
    # Detect sampling constraints
    sampling_constraints = _detect_sampling_constraints(text)
    
    # FIX 2: Daily activity bindings with expected counts
    activity_bindings, bound_repetitions = _detect_daily_activity_bindings(text)
    all_repetitions.extend(bound_repetitions)
    
    # FIX 3: Analysis windows (baseline, accumulation, steady-state)
    analysis_windows = _detect_analysis_windows(text)
    
    # FIX 4: Collection day anchors (24-hour boundaries)
    collection_anchors = _detect_collection_day_anchors(text)
    
    # LLM enhancement if requested
    if use_llm and (all_repetitions or sampling_constraints):
        try:
            llm_result = _extract_repetitions_llm(text, model)
            if llm_result:
                all_repetitions.extend(llm_result)
        except Exception as e:
            logger.warning(f"LLM repetition extraction failed: {e}")
    
    # Deduplicate by source text
    seen = set()
    unique_repetitions = []
    for rep in all_repetitions:
        key = (rep.type, rep.source_text)
        if key not in seen:
            seen.add(key)
            unique_repetitions.append(rep)
    
    data = ExecutionModelData(
        repetitions=unique_repetitions,
        sampling_constraints=sampling_constraints,
        activity_bindings=activity_bindings,
        analysis_windows=analysis_windows,
        time_anchors=collection_anchors,
    )
    
    result = ExecutionModelResult(
        success=len(unique_repetitions) > 0 or len(sampling_constraints) > 0,
        data=data,
        pages_used=pages,
        model_used=model if use_llm else "heuristic",
    )
    
    logger.info(
        f"Extracted {len(unique_repetitions)} repetitions, "
        f"{len(sampling_constraints)} sampling constraints"
    )
    
    # Log Fix 2, 3, 4 results
    if activity_bindings:
        logger.info(f"  FIX 2: {len(activity_bindings)} daily activity bindings with expected counts")
    if analysis_windows:
        logger.info(f"  FIX 3: {len(analysis_windows)} analysis windows (baseline/treatment/steady-state)")
    if collection_anchors:
        logger.info(f"  FIX 4: {len(collection_anchors)} collection day anchors")
    
    return result


def _extract_repetitions_llm(text: str, model: str) -> List[Repetition]:
    """Extract repetitions using LLM for complex patterns."""
    from core.llm_client import call_llm
    
    prompt = f"""Analyze this clinical protocol text and identify REPETITION PATTERNS for data collection.

Look for:
1. DAILY collections (daily urine, daily glucose, etc.)
2. INTERVAL sampling (every 5 minutes, every 2 hours, etc.)
3. TREATMENT CYCLES (21-day cycles, repeat every 28 days, etc.)
4. CONTINUOUS WINDOWS (Days -4 to -1, throughout treatment, etc.)

Return JSON:

```json
{{
  "repetitions": [
    {{
      "type": "Daily|Interval|Cycle|Continuous",
      "interval": "ISO 8601 duration (e.g., PT5M, P1D, P21D)",
      "startOffset": "ISO 8601 duration from anchor",
      "endOffset": "ISO 8601 duration from anchor", 
      "minObservations": 4,
      "exitCondition": "condition to exit cycle (if applicable)",
      "sourceText": "exact quote"
    }}
  ]
}}
```

Protocol text:
{text[:6000]}

Return ONLY the JSON."""

    try:
        result = call_llm(
            prompt=prompt,
            model_name=model,
            json_mode=True,
            extractor_name="repetition",
            temperature=0.1,
        )
        response = result.get('response', '')
        
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response
        
        data = json.loads(json_str)
        
        repetitions = []
        for i, rep_data in enumerate(data.get('repetitions', [])):
            rep_type_str = rep_data.get('type')
            rep_type = RepetitionType.UNKNOWN  # Default to UNKNOWN if not extracted
            if rep_type_str:
                try:
                    rep_type = RepetitionType(rep_type_str)
                except ValueError:
                    rep_type = RepetitionType.UNKNOWN
            
            repetitions.append(Repetition(
                id=f"rep_llm_{i+1}",
                type=rep_type,
                interval=rep_data.get('interval'),
                start_offset=rep_data.get('startOffset'),
                end_offset=rep_data.get('endOffset'),
                min_observations=rep_data.get('minObservations'),
                exit_condition=rep_data.get('exitCondition'),
                source_text=rep_data.get('sourceText'),
            ))
        
        return repetitions
        
    except Exception as e:
        logger.error(f"LLM repetition extraction failed: {e}")
        return []
