"""
Crossover Sequence Extractor

Detects and extracts crossover study design structure from protocol PDFs:
- Number of periods and sequences
- Treatment sequence assignments (AB, BA, etc.)
- Washout period requirements
- Carryover prevention measures

Per reviewer feedback: Crossover studies require explicit period sequencing
with washout enforcement to prevent subjects skipping periods.
"""

import re
import json
import logging
from typing import List, Dict, Any, Optional, Tuple

from .schema import (
    CrossoverDesign, TraversalConstraint,
    ExecutionModelResult, ExecutionModelData
)

logger = logging.getLogger(__name__)


# Crossover design detection patterns
CROSSOVER_PATTERNS: List[Tuple[str, float]] = [
    # Explicit crossover mentions
    (r'crossover\s+(?:study|design|trial)', 0.95),
    (r'cross[\-\s]?over\s+(?:study|design|trial)', 0.95),
    (r'(?:2|two|3|three)[\-\s]?(?:way|period|sequence)\s+crossover', 0.95),
    (r'(?:open[\-\s]?label\s+)?crossover', 0.90),
    
    # Period mentions
    (r'period\s+[12]\s+(?:and|&)\s+period\s+[12]', 0.90),
    (r'treatment\s+period\s+[12]', 0.85),
    (r'(?:first|second)\s+treatment\s+period', 0.85),
    
    # Sequence mentions
    (r'sequence\s+[AB]{2,}', 0.90),
    (r'treatment\s+sequence\s+(?:[AB]{2,}|[12]{2,})', 0.90),
    (r'randomized?\s+to\s+(?:sequence|treatment\s+order)', 0.85),
    
    # Washout mentions
    (r'washout\s+period', 0.85),
    (r'wash[\-\s]?out\s+(?:of\s+)?\d+\s*(?:days?|weeks?)', 0.90),
    (r'(?:\d+[\-\s]?(?:day|week))\s+washout', 0.90),
    (r'between[\-\s]?period\s+washout', 0.85),
]

# Period detection patterns
PERIOD_PATTERNS: List[Tuple[str, float]] = [
    (r'period\s+(\d+)', 0.85),
    (r'treatment\s+period\s+(\d+)', 0.90),
    (r'(?:first|second|third)\s+(?:treatment\s+)?period', 0.80),
]

# Sequence detection patterns  
SEQUENCE_PATTERNS: List[Tuple[str, float]] = [
    (r'sequence\s+([AB]{2,})', 0.90),
    (r'treatment\s+sequence\s+([AB]{2,})', 0.90),
    (r'sequence\s+([12]{2,})', 0.85),
    (r'(?:AB|BA|ABC|ACB|BAC|BCA|CAB|CBA)\s+sequence', 0.85),
]

# Washout duration patterns
WASHOUT_PATTERNS: List[Tuple[str, float]] = [
    (r'washout\s+(?:period\s+)?(?:of\s+)?(\d+)\s*(?:days?)', 0.90),
    (r'washout\s+(?:period\s+)?(?:of\s+)?(\d+)\s*(?:weeks?)', 0.90),
    (r'(\d+)[\-\s]?(?:day|week)\s+washout', 0.90),
    (r'(?:minimum|at\s+least)\s+(\d+)\s*(?:days?|weeks?)\s+washout', 0.85),
    (r'washout\s+(?:of\s+)?(?:at\s+least\s+)?(\d+)', 0.80),
]

# Keywords for finding crossover-relevant pages
CROSSOVER_KEYWORDS = [
    r'crossover',
    r'cross[\-\s]?over',
    r'period\s+[12]',
    r'sequence',
    r'washout',
    r'carry[\-\s]?over',
    r'treatment\s+order',
]


def find_crossover_pages(
    pdf_path: str,
    max_pages_to_scan: int = 40,
) -> List[int]:
    """Find pages likely to contain crossover design information."""
    import fitz
    
    pattern = re.compile('|'.join(CROSSOVER_KEYWORDS), re.IGNORECASE)
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
        
        if len(pages) > 15:
            pages = pages[:15]
        
        logger.info(f"Found {len(pages)} potential crossover pages")
        
    except Exception as e:
        logger.error(f"Error scanning PDF for crossover: {e}")
        pages = list(range(min(20, max_pages_to_scan)))
    
    return pages


def _is_titration_study(text: str) -> bool:
    """
    Detect if this is a within-subject titration study.
    
    Titration studies have dose escalation within the SAME subject, not
    different treatments in different periods. They should NOT be classified
    as crossover even if they mention "periods" or "phases".
    """
    text_lower = text.lower()
    
    # Strong titration indicators
    titration_patterns = [
        r'dose\s+titration',
        r'titrat(?:e|ion|ed)\s+(?:to|from)',
        r'dose\s+escalation',
        r'escalat(?:e|ion|ed)\s+(?:to|from)',
        r'(\d+)\s*mg.*?(?:for|during).*?(\d+)\s*days?.*?(?:then|followed\s+by).*?(\d+)\s*mg',
        r'starting\s+dose.*?(?:increase|titrate|escalate)',
        r'initial\s+dose.*?(?:increase|titrate|escalate)',
        r'dose\s+adjustment',
        r'within[\-\s]?subject\s+(?:dose|titration)',
    ]
    
    titration_score = 0
    for pattern in titration_patterns:
        if re.search(pattern, text_lower):
            titration_score += 1
    
    # Single-arm indicators (further evidence against crossover)
    single_arm_patterns = [
        r'single[\-\s]?arm',
        r'open[\-\s]?label(?:\s+single)',
        r'all\s+(?:subjects?|participants?)\s+(?:will\s+)?receive',
        r'no\s+(?:control|placebo|comparator)\s+(?:arm|group)',
    ]
    
    for pattern in single_arm_patterns:
        if re.search(pattern, text_lower):
            titration_score += 1
    
    # If strong titration evidence, this is NOT a crossover
    return titration_score >= 2


def _detect_crossover_heuristic(text: str) -> Optional[CrossoverDesign]:
    """Detect crossover design using regex patterns."""
    
    # EXCLUSION: Check for titration study first
    if _is_titration_study(text):
        logger.info("Detected titration study - excluding from crossover classification")
        return None
    
    # Check if this is a crossover study
    is_crossover = False
    crossover_confidence = 0.0
    source_text = None
    
    for pattern, confidence in CROSSOVER_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            is_crossover = True
            if confidence > crossover_confidence:
                crossover_confidence = confidence
                source_text = match.group()
    
    if not is_crossover:
        return None
    
    # Extract number of periods
    num_periods = 2  # Default for crossover
    period_matches = re.findall(r'(\d+)[\-\s]?(?:period|way)\s+crossover', text, re.IGNORECASE)
    if period_matches:
        try:
            num_periods = int(period_matches[0])
        except ValueError:
            pass
    
    # Also check for explicit period mentions
    period_nums = re.findall(r'period\s+(\d+)', text, re.IGNORECASE)
    if period_nums:
        max_period = max(int(p) for p in period_nums)
        num_periods = max(num_periods, max_period)
    
    # Extract periods
    periods = []
    if num_periods == 2:
        periods = ["Period 1", "Period 2"]
    elif num_periods == 3:
        periods = ["Period 1", "Period 2", "Period 3"]
    
    # Extract sequences
    sequences = []
    for pattern, _ in SEQUENCE_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            if m.upper() not in sequences:
                sequences.append(m.upper())
    
    # If no explicit sequences found, infer from period count
    if not sequences:
        if num_periods == 2:
            sequences = ["AB", "BA"]
        elif num_periods == 3:
            sequences = ["ABC", "ACB", "BAC", "BCA", "CAB", "CBA"]
    
    # Extract washout duration
    washout_duration = None
    washout_required = False
    
    for pattern, _ in WASHOUT_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            washout_required = True
            try:
                value = int(match.group(1))
                # Determine unit from context
                if 'week' in match.group().lower():
                    washout_duration = f"P{value}W"
                else:
                    washout_duration = f"P{value}D"
            except (ValueError, IndexError):
                pass
            break
    
    # Check for carryover prevention
    carryover_prevention = None
    carryover_match = re.search(
        r'(?:prevent|minimize|avoid|reduce)\s+(?:potential\s+)?carry[\-\s]?over',
        text, re.IGNORECASE
    )
    if carryover_match:
        # Extract surrounding context
        start = max(0, carryover_match.start() - 50)
        end = min(len(text), carryover_match.end() + 100)
        carryover_prevention = text[start:end].strip()
    
    return CrossoverDesign(
        id="crossover_1",
        is_crossover=True,
        num_periods=num_periods,
        num_sequences=len(sequences),
        periods=periods,
        sequences=sequences,
        washout_duration=washout_duration,
        washout_required=washout_required,
        carryover_prevention=carryover_prevention,
        source_text=source_text,
    )


def _extract_traversal_from_crossover(
    crossover: CrossoverDesign,
    text: str,
) -> TraversalConstraint:
    """Extract traversal constraints from crossover design."""
    
    # Build required sequence
    required_sequence = ["SCREENING"]
    
    for i, period in enumerate(crossover.periods):
        required_sequence.append(period.upper().replace(" ", "_"))
        # Add washout between periods (except after last)
        if crossover.washout_required and i < len(crossover.periods) - 1:
            required_sequence.append("WASHOUT")
    
    required_sequence.append("END_OF_STUDY")
    
    # Find mandatory visits
    mandatory_visits = ["Screening", "Day 1"]
    
    # Look for explicit mandatory visit mentions
    mandatory_match = re.search(
        r'(?:mandatory|required)\s+(?:visits?|assessments?)',
        text, re.IGNORECASE
    )
    if mandatory_match:
        # Extract context for potential visit names
        start = mandatory_match.start()
        end = min(len(text), mandatory_match.end() + 200)
        context = text[start:end]
        
        # Look for visit names in context
        visit_matches = re.findall(r'(?:Visit\s+\d+|Day\s+\d+|Week\s+\d+)', context, re.IGNORECASE)
        for v in visit_matches[:5]:
            if v not in mandatory_visits:
                mandatory_visits.append(v)
    
    # Add End of Study as mandatory
    mandatory_visits.append("End of Study")
    
    return TraversalConstraint(
        id="traversal_crossover_1",
        required_sequence=required_sequence,
        allow_early_exit=True,
        exit_epoch_ids=["EARLY_TERMINATION"],
        mandatory_visits=mandatory_visits,
        source_text=crossover.source_text,
    )


def extract_crossover_design(
    pdf_path: str,
    model: str = "gemini-2.5-pro",
    pages: Optional[List[int]] = None,
    use_llm: bool = True,
) -> ExecutionModelResult:
    """
    Extract crossover design structure from protocol PDF.
    
    Args:
        pdf_path: Path to protocol PDF
        model: LLM model to use
        pages: Specific pages to analyze
        use_llm: Whether to use LLM enhancement
        
    Returns:
        ExecutionModelResult with CrossoverDesign and TraversalConstraint
    """
    from core.pdf_utils import extract_text_from_pages, get_page_count
    
    logger.info("Starting crossover design extraction...")
    
    # Find relevant pages
    if pages is None:
        pages = find_crossover_pages(pdf_path)
    
    if not pages:
        logger.info("No crossover pages found, using first 20 pages")
        pages = list(range(min(20, get_page_count(pdf_path))))
    
    # Extract text
    text = extract_text_from_pages(pdf_path, pages)
    if not text:
        return ExecutionModelResult(
            success=False,
            error="Failed to extract text from PDF",
            pages_used=pages,
            model_used=model,
        )
    
    # EXCLUSION CHECK: Skip crossover detection entirely for titration studies
    if _is_titration_study(text):
        logger.info("Detected titration study - skipping crossover detection entirely")
        return ExecutionModelResult(
            success=False,
            data=ExecutionModelData(),
            pages_used=pages,
            model_used="heuristic",
        )
    
    # Heuristic detection
    crossover = _detect_crossover_heuristic(text)
    
    # LLM enhancement (only if not excluded by titration check above)
    if use_llm and crossover:
        try:
            llm_crossover = _extract_crossover_llm(text, model)
            if llm_crossover:
                crossover = _merge_crossover(crossover, llm_crossover)
        except Exception as e:
            logger.warning(f"LLM crossover extraction failed: {e}")
    elif use_llm and not crossover:
        # Try LLM even if heuristic found nothing
        try:
            crossover = _extract_crossover_llm(text, model)
        except Exception as e:
            logger.warning(f"LLM crossover extraction failed: {e}")
    
    # Build result
    data = ExecutionModelData()
    
    if crossover and crossover.is_crossover:
        data.crossover_design = crossover
        
        # Extract traversal constraints
        traversal = _extract_traversal_from_crossover(crossover, text)
        data.traversal_constraints = [traversal]
        
        logger.info(
            f"Detected crossover design: {crossover.num_periods} periods, "
            f"{crossover.num_sequences} sequences, washout={crossover.washout_duration}"
        )
    else:
        logger.info("No crossover design detected (parallel or other design)")
    
    return ExecutionModelResult(
        success=crossover is not None and crossover.is_crossover,
        data=data,
        pages_used=pages,
        model_used=model if use_llm else "heuristic",
    )


def _extract_crossover_llm(text: str, model: str) -> Optional[CrossoverDesign]:
    """Extract crossover design using LLM."""
    from core.llm_client import call_llm
    
    prompt = f"""Analyze this clinical protocol text and determine if it describes a CROSSOVER study design.

Look for:
1. Explicit crossover mentions ("crossover study", "2-way crossover", etc.)
2. Multiple treatment periods (Period 1, Period 2)
3. Treatment sequences (AB, BA, ABC, etc.)
4. Washout periods between treatments
5. Carryover prevention measures

Return JSON:
```json
{{
  "isCrossover": true,
  "numPeriods": 2,
  "numSequences": 2,
  "periods": ["Period 1", "Period 2"],
  "sequences": ["AB", "BA"],
  "washoutDuration": "P7D",
  "washoutRequired": true,
  "carryoverPrevention": "7-day washout to prevent carryover effects",
  "sourceQuote": "exact quote mentioning crossover"
}}
```

If NOT a crossover study, return:
```json
{{
  "isCrossover": false,
  "designType": "parallel|single-arm|other"
}}
```

Protocol text:
{text[:8000]}

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
        
        if not data.get('isCrossover', False):
            return None
        
        return CrossoverDesign(
            id="crossover_llm_1",
            is_crossover=True,
            num_periods=data.get('numPeriods', 2),
            num_sequences=data.get('numSequences', 2),
            periods=data.get('periods', []),
            sequences=data.get('sequences', []),
            washout_duration=data.get('washoutDuration'),
            washout_required=data.get('washoutRequired', False),
            carryover_prevention=data.get('carryoverPrevention'),
            source_text=data.get('sourceQuote'),
        )
        
    except Exception as e:
        logger.error(f"LLM crossover extraction failed: {e}")
        return None


def _merge_crossover(
    heuristic: CrossoverDesign,
    llm: CrossoverDesign,
) -> CrossoverDesign:
    """Merge heuristic and LLM crossover results."""
    # Prefer LLM values if they're more specific
    return CrossoverDesign(
        id=heuristic.id,
        is_crossover=True,
        num_periods=llm.num_periods if llm.num_periods > 0 else heuristic.num_periods,
        num_sequences=llm.num_sequences if llm.num_sequences > 0 else heuristic.num_sequences,
        periods=llm.periods if llm.periods else heuristic.periods,
        sequences=llm.sequences if llm.sequences else heuristic.sequences,
        washout_duration=llm.washout_duration or heuristic.washout_duration,
        washout_required=llm.washout_required or heuristic.washout_required,
        carryover_prevention=llm.carryover_prevention or heuristic.carryover_prevention,
        source_text=heuristic.source_text or llm.source_text,
    )
