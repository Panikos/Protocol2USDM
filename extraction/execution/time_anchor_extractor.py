"""
Time Anchor Extractor

Identifies canonical time anchors for study timelines from protocol PDFs.

Per USDM workshop manual: "Every main timeline requires an anchor point - 
the fundamental reference from which all other timing is measured."

Common anchor patterns:
- Cycle 1, Day 1 with screening relative to it
- Week 0 of treatment as baseline  
- Days from randomization where Day 0 is reference
- First dose administration
"""

import re
import json
import logging
from typing import List, Dict, Any, Optional, Tuple

from .schema import TimeAnchor, AnchorType, ExecutionModelResult, ExecutionModelData

logger = logging.getLogger(__name__)


# Anchor detection patterns with associated types
# Organized by therapeutic area for comprehensive coverage
ANCHOR_PATTERNS: List[Tuple[str, AnchorType, float]] = [
    # ==========================================================================
    # GENERAL / CROSS-THERAPEUTIC PATTERNS (highest priority)
    # ==========================================================================
    # First dose patterns
    (r'first\s+(?:dose|administration)\s+of\s+(?:study\s+)?(?:drug|medication|treatment|investigational\s+product)',
     AnchorType.FIRST_DOSE, 0.95),
    (r'day\s+1\s+(?:of\s+)?(?:cycle\s+1|treatment|dosing)',
     AnchorType.FIRST_DOSE, 0.90),
    (r'initiation\s+of\s+(?:study\s+)?treatment',
     AnchorType.FIRST_DOSE, 0.85),
    (r'start\s+of\s+(?:study\s+)?(?:treatment|therapy|intervention)',
     AnchorType.FIRST_DOSE, 0.85),
    (r'treatment\s+(?:start|initiation|commencement)',
     AnchorType.FIRST_DOSE, 0.80),
    
    # Randomization patterns
    (r'day\s+(?:of\s+)?randomization',
     AnchorType.RANDOMIZATION, 0.90),
    (r'randomization\s+(?:visit|day|date)',
     AnchorType.RANDOMIZATION, 0.90),
    (r'days?\s+(?:from|after|since)\s+randomization',
     AnchorType.RANDOMIZATION, 0.85),
    (r'post[\-\s]?randomization',
     AnchorType.RANDOMIZATION, 0.80),
    
    # Day 1/Baseline patterns
    (r'day\s+1\s*[=:]\s*(?:baseline|first\s+visit)',
     AnchorType.DAY_1, 0.85),
    (r'baseline\s+(?:visit|day|assessment)',
     AnchorType.BASELINE, 0.80),
    (r'week\s+0\s+(?:of\s+)?treatment',
     AnchorType.BASELINE, 0.80),
    (r'pre[\-\s]?treatment\s+(?:baseline|assessment)',
     AnchorType.BASELINE, 0.80),
    
    # Screening/Enrollment
    (r'screening\s+(?:visit|period|day)',
     AnchorType.SCREENING, 0.70),
    (r'informed\s+consent',
     AnchorType.INFORMED_CONSENT, 0.75),
    (r'enrollment\s+(?:visit|day)',
     AnchorType.ENROLLMENT, 0.75),
    
    # ==========================================================================
    # ONCOLOGY PATTERNS
    # ==========================================================================
    (r'cycle\s+1[,\s]+day\s+1',
     AnchorType.CYCLE_START, 0.85),
    (r'c1d1',
     AnchorType.CYCLE_START, 0.80),
    (r'first\s+(?:infusion|injection)\s+(?:of\s+)?(?:study\s+)?(?:drug|treatment)',
     AnchorType.FIRST_DOSE, 0.90),
    (r'start\s+of\s+(?:chemotherapy|immunotherapy|targeted\s+therapy)',
     AnchorType.FIRST_DOSE, 0.85),
    (r'day\s+1\s+of\s+(?:induction|consolidation|maintenance)',
     AnchorType.FIRST_DOSE, 0.85),
    (r'first\s+(?:cycle|course)\s+of\s+(?:treatment|therapy)',
     AnchorType.CYCLE_START, 0.85),
    
    # ==========================================================================
    # VACCINES / IMMUNOLOGY PATTERNS
    # ==========================================================================
    (r'(?:first|prime)\s+(?:vaccination|immunization|dose)',
     AnchorType.FIRST_DOSE, 0.90),
    (r'day\s+(?:of\s+)?(?:prime|first)\s+vaccination',
     AnchorType.FIRST_DOSE, 0.90),
    (r'vaccination\s+day\s+(?:1|one)',
     AnchorType.FIRST_DOSE, 0.85),
    (r'post[\-\s]?vaccination\s+day\s+\d+',
     AnchorType.FIRST_DOSE, 0.80),
    (r'challenge\s+(?:day|date)',
     AnchorType.CUSTOM, 0.80),
    
    # ==========================================================================
    # CARDIOLOGY PATTERNS
    # ==========================================================================
    (r'(?:index|qualifying)\s+(?:event|mi|stroke|hospitalization)',
     AnchorType.CUSTOM, 0.85),
    (r'days?\s+(?:from|after|since)\s+(?:index|qualifying)\s+event',
     AnchorType.CUSTOM, 0.85),
    (r'post[\-\s]?(?:mi|stroke|pci|cabg)',
     AnchorType.CUSTOM, 0.80),
    (r'hospital\s+discharge',
     AnchorType.CUSTOM, 0.75),
    (r'days?\s+(?:from|after)\s+discharge',
     AnchorType.CUSTOM, 0.80),
    
    # ==========================================================================
    # NEUROLOGY / CNS PATTERNS
    # ==========================================================================
    (r'(?:first|initial)\s+(?:seizure|episode|attack)',
     AnchorType.CUSTOM, 0.80),
    (r'symptom\s+onset',
     AnchorType.CUSTOM, 0.80),
    (r'days?\s+(?:from|after|since)\s+(?:diagnosis|onset)',
     AnchorType.CUSTOM, 0.80),
    (r'titration\s+(?:start|initiation|period)',
     AnchorType.FIRST_DOSE, 0.75),
    
    # ==========================================================================
    # SURGERY / PROCEDURES / DEVICES PATTERNS
    # ==========================================================================
    (r'(?:day\s+of\s+)?(?:surgery|procedure|implantation|transplant)',
     AnchorType.CUSTOM, 0.85),
    (r'post[\-\s]?(?:operative|surgical|procedure)',
     AnchorType.CUSTOM, 0.80),
    (r'days?\s+(?:from|after|since)\s+(?:surgery|procedure|implant)',
     AnchorType.CUSTOM, 0.85),
    (r'device\s+(?:implantation|activation)',
     AnchorType.CUSTOM, 0.80),
    (r'transplant(?:ation)?\s+(?:day|date)',
     AnchorType.CUSTOM, 0.85),
    
    # ==========================================================================
    # RARE DISEASE / GENETIC PATTERNS
    # ==========================================================================
    (r'first\s+(?:infusion|injection)\s+of\s+(?:enzyme|gene\s+therapy|replacement)',
     AnchorType.FIRST_DOSE, 0.90),
    (r'start\s+of\s+(?:enzyme|gene)\s+(?:replacement\s+)?therapy',
     AnchorType.FIRST_DOSE, 0.85),
    (r'loading\s+dose',
     AnchorType.FIRST_DOSE, 0.80),
    
    # ==========================================================================
    # DIABETES / METABOLIC PATTERNS
    # ==========================================================================
    (r'(?:first|initial)\s+(?:injection|dose)\s+of\s+(?:insulin|glp[\-\s]?1|sglt)',
     AnchorType.FIRST_DOSE, 0.90),
    (r'start\s+of\s+(?:insulin|basal|bolus)\s+(?:therapy|treatment)',
     AnchorType.FIRST_DOSE, 0.85),
    (r'clamp\s+(?:procedure|study)\s+(?:day|start)',
     AnchorType.CUSTOM, 0.80),
    (r'glucose\s+(?:challenge|tolerance\s+test)',
     AnchorType.CUSTOM, 0.75),
    
    # ==========================================================================
    # INFECTIOUS DISEASE PATTERNS
    # ==========================================================================
    (r'first\s+dose\s+of\s+(?:antibiotic|antiviral|antifungal)',
     AnchorType.FIRST_DOSE, 0.90),
    (r'start\s+of\s+(?:antimicrobial|antiretroviral)\s+therapy',
     AnchorType.FIRST_DOSE, 0.85),
    (r'(?:infection|symptom)\s+(?:onset|diagnosis)',
     AnchorType.CUSTOM, 0.80),
    
    # ==========================================================================
    # OPHTHALMOLOGY PATTERNS
    # ==========================================================================
    (r'(?:first|initial)\s+(?:intravitreal\s+)?injection',
     AnchorType.FIRST_DOSE, 0.90),
    (r'day\s+of\s+(?:injection|treatment)\s+(?:in\s+)?(?:study|treated)\s+eye',
     AnchorType.FIRST_DOSE, 0.85),
    
    # ==========================================================================
    # DERMATOLOGY PATTERNS
    # ==========================================================================
    (r'first\s+(?:application|dose)\s+of\s+(?:topical|study)\s+(?:drug|treatment)',
     AnchorType.FIRST_DOSE, 0.85),
    (r'start\s+of\s+(?:topical|phototherapy)\s+treatment',
     AnchorType.FIRST_DOSE, 0.80),
]

# Keywords to find anchor-relevant pages
ANCHOR_KEYWORDS = [
    r'day\s+1',
    r'baseline',
    r'randomization',
    r'first\s+dose',
    r'cycle\s+1',
    r'study\s+day',
    r'treatment\s+day',
    r'week\s+0',
    r'time\s*point',
    r'schedule\s+of\s+(?:activities|assessments|events)',
]


def find_anchor_pages(
    pdf_path: str,
    max_pages_to_scan: int = 40,
) -> List[int]:
    """
    Find pages likely to contain time anchor definitions.
    
    Args:
        pdf_path: Path to protocol PDF
        max_pages_to_scan: Maximum pages to scan
        
    Returns:
        List of 0-indexed page numbers
    """
    import fitz
    
    pattern = re.compile('|'.join(ANCHOR_KEYWORDS), re.IGNORECASE)
    anchor_pages = []
    
    try:
        doc = fitz.open(pdf_path)
        total_pages = min(len(doc), max_pages_to_scan)
        
        for page_num in range(total_pages):
            page = doc[page_num]
            text = page.get_text().lower()
            
            matches = len(pattern.findall(text))
            if matches >= 2:
                anchor_pages.append(page_num)
                logger.debug(f"Found anchor keywords on page {page_num + 1}")
        
        doc.close()
        
        if len(anchor_pages) > 15:
            anchor_pages = anchor_pages[:15]
        
        logger.info(f"Found {len(anchor_pages)} potential anchor pages")
        
    except Exception as e:
        logger.error(f"Error scanning PDF for anchors: {e}")
        anchor_pages = list(range(min(20, max_pages_to_scan)))
    
    return anchor_pages


def _detect_anchors_heuristic(text: str) -> List[TimeAnchor]:
    """
    Detect time anchors using regex patterns.
    
    Args:
        text: Protocol text to analyze
        
    Returns:
        List of detected TimeAnchor objects
    """
    anchors = []
    seen_types = set()
    
    for pattern, anchor_type, confidence in ANCHOR_PATTERNS:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        
        for match in matches:
            if anchor_type in seen_types:
                continue
                
            # Extract surrounding context (up to 100 chars each side)
            start = max(0, match.start() - 100)
            end = min(len(text), match.end() + 100)
            context = text[start:end].strip()
            
            anchor = TimeAnchor(
                id=f"anchor_{len(anchors)+1}",
                definition=_build_anchor_definition(anchor_type, match.group()),
                anchor_type=anchor_type,
                day_value=_extract_day_value(match.group(), context),
                source_text=match.group(),
            )
            
            anchors.append(anchor)
            seen_types.add(anchor_type)
    
    return anchors


def _build_anchor_definition(anchor_type: AnchorType, matched_text: str) -> str:
    """Build human-readable definition for an anchor type."""
    definitions = {
        AnchorType.FIRST_DOSE: "First administration of investigational product",
        AnchorType.RANDOMIZATION: "Date of subject randomization",
        AnchorType.DAY_1: "Study Day 1 (baseline)",
        AnchorType.BASELINE: "Baseline visit/assessment",
        AnchorType.SCREENING: "Screening visit",
        AnchorType.ENROLLMENT: "Subject enrollment date",
        AnchorType.INFORMED_CONSENT: "Informed consent obtained",
        AnchorType.CYCLE_START: "Day 1 of Cycle 1",
        AnchorType.CUSTOM: matched_text.strip(),
    }
    return definitions.get(anchor_type, matched_text.strip())


def _extract_day_value(matched_text: str, context: str) -> int:
    """Extract numeric day value from anchor text."""
    # Look for "Day X" pattern
    day_match = re.search(r'day\s*(\d+)', matched_text + " " + context, re.IGNORECASE)
    if day_match:
        return int(day_match.group(1))
    
    # Week 0 = Day 1
    if re.search(r'week\s*0', matched_text, re.IGNORECASE):
        return 1
    
    # Default to Day 1
    return 1


def extract_time_anchors(
    pdf_path: str,
    model: str = "gemini-2.5-pro",
    pages: Optional[List[int]] = None,
    use_llm: bool = True,
    existing_encounters: Optional[List[Dict[str, Any]]] = None,
    existing_epochs: Optional[List[Dict[str, Any]]] = None,
) -> ExecutionModelResult:
    """
    Extract time anchors from protocol PDF.
    
    Uses a combination of heuristic pattern matching and optional LLM
    extraction for higher accuracy.
    
    Args:
        pdf_path: Path to protocol PDF
        model: LLM model to use (if use_llm=True)
        pages: Specific pages to analyze (auto-detected if None)
        use_llm: Whether to use LLM for enhanced extraction
        existing_encounters: SoA encounters for context (improves anchor resolution)
        existing_epochs: SoA epochs for context (improves anchor resolution)
        
    Returns:
        ExecutionModelResult with extracted TimeAnchors
    """
    from core.pdf_utils import extract_text_from_pages, get_page_count
    
    logger.info("Starting time anchor extraction...")
    
    # Find relevant pages
    if pages is None:
        pages = find_anchor_pages(pdf_path)
    
    if not pages:
        logger.warning("No anchor pages found, using first 20 pages")
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
    
    # Heuristic extraction
    anchors = _detect_anchors_heuristic(text)
    
    # LLM enhancement if requested and heuristics found something
    if use_llm and anchors:
        try:
            llm_anchors = _extract_anchors_llm(text, model)
            if llm_anchors:
                # Merge LLM results (prefer higher confidence)
                anchors = _merge_anchors(anchors, llm_anchors)
        except Exception as e:
            logger.warning(f"LLM anchor extraction failed, using heuristics only: {e}")
    
    # Select primary anchor (highest confidence, prefer FIRST_DOSE > RANDOMIZATION > DAY_1)
    if anchors:
        anchors = _prioritize_anchors(anchors)
    
    data = ExecutionModelData(time_anchors=anchors)
    
    result = ExecutionModelResult(
        success=len(anchors) > 0,
        data=data,
        pages_used=pages,
        model_used=model if use_llm else "heuristic",
    )
    
    logger.info(f"Extracted {len(anchors)} time anchors")
    
    return result


def _extract_anchors_llm(text: str, model: str) -> List[TimeAnchor]:
    """Extract time anchors using LLM."""
    from core.llm_client import call_llm
    
    prompt = f"""Analyze this clinical protocol text and identify the TIME ANCHOR - the reference point from which all study timing is measured.

Look for patterns like:
- "Day 1" definitions (e.g., "Day 1 is defined as first dose of study drug")
- Randomization as anchor (e.g., "Days from randomization")
- Cycle 1, Day 1 (C1D1) in oncology protocols
- Week 0 or Baseline definitions

Return JSON with the PRIMARY time anchor:

```json
{{
  "timeAnchor": {{
    "definition": "First administration of investigational product",
    "anchorType": "FirstDose|Randomization|Day1|Baseline|CycleStart|Screening|Enrollment",
    "dayValue": 1,
    "sourceText": "exact quote from protocol defining the anchor"
  }}
}}
```

Protocol text:
{text[:8000]}

Return ONLY the JSON, no explanation."""

    try:
        result = call_llm(
            prompt=prompt,
            model_name=model,
            json_mode=True,
            extractor_name="time_anchor",
            temperature=0.1,
        )
        response = result.get('response', '')
        
        # Parse JSON
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response
        
        data = json.loads(json_str)
        
        anchor_data = data.get('timeAnchor', {})
        if anchor_data:
            anchor_type_str = anchor_data.get('anchorType')
            anchor_type = AnchorType.CUSTOM  # Default to CUSTOM if not extracted
            if anchor_type_str:
                try:
                    anchor_type = AnchorType(anchor_type_str)
                except ValueError:
                    anchor_type = AnchorType.CUSTOM
            
            return [TimeAnchor(
                id="anchor_llm_1",
                definition=anchor_data.get('definition', ''),
                anchor_type=anchor_type,
                day_value=anchor_data.get('dayValue', 1),
                source_text=anchor_data.get('sourceText'),
            )]
        
    except Exception as e:
        logger.error(f"LLM anchor extraction failed: {e}")
    
    return []


def _merge_anchors(heuristic: List[TimeAnchor], llm: List[TimeAnchor]) -> List[TimeAnchor]:
    """Merge heuristic and LLM-extracted anchors, preferring higher confidence."""
    merged = {}
    
    for anchor in heuristic + llm:
        key = anchor.anchor_type
        if key not in merged:
            merged[key] = anchor
    
    return list(merged.values())


def _prioritize_anchors(anchors: List[TimeAnchor]) -> List[TimeAnchor]:
    """Sort anchors by priority (FIRST_DOSE > RANDOMIZATION > DAY_1 > others)."""
    priority = {
        AnchorType.FIRST_DOSE: 1,
        AnchorType.RANDOMIZATION: 2,
        AnchorType.DAY_1: 3,
        AnchorType.BASELINE: 4,
        AnchorType.CYCLE_START: 5,
        AnchorType.ENROLLMENT: 6,
        AnchorType.SCREENING: 7,
        AnchorType.INFORMED_CONSENT: 8,
        AnchorType.CUSTOM: 9,
    }
    
    return sorted(anchors, key=lambda a: priority.get(a.anchor_type, 10))
