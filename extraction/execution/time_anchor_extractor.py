"""
Time Anchor Extractor

Identifies canonical time anchors for study timelines from protocol PDFs.

Per USDM workshop manual: "Every main timeline requires an anchor point - 
the fundamental reference from which all other timing is measured."

Uses LLM-primary extraction to produce 1-3 protocol-specific anchors
with actual protocol quotes as definitions, not canned boilerplate.
"""

import re
import json
import logging
from typing import List, Dict, Any, Optional

from .schema import TimeAnchor, AnchorType, ExecutionModelResult, ExecutionModelData

logger = logging.getLogger(__name__)


# ── Anchor-type mapping ──────────────────────────────────────────────────────
_ANCHOR_TYPE_MAP: Dict[str, AnchorType] = {
    "firstdose": AnchorType.FIRST_DOSE,
    "treatmentstart": AnchorType.TREATMENT_START,
    "randomization": AnchorType.RANDOMIZATION,
    "screening": AnchorType.SCREENING,
    "day1": AnchorType.DAY_1,
    "baseline": AnchorType.BASELINE,
    "enrollment": AnchorType.ENROLLMENT,
    "informedconsent": AnchorType.INFORMED_CONSENT,
    "cyclestart": AnchorType.CYCLE_START,
    "collectionday": AnchorType.COLLECTION_DAY,
    "custom": AnchorType.CUSTOM,
}


def _resolve_anchor_type(raw: str) -> AnchorType:
    """Fuzzy-match an LLM-returned anchor type string to AnchorType enum."""
    if not raw:
        return AnchorType.CUSTOM
    # Try exact enum value first
    try:
        return AnchorType(raw)
    except ValueError:
        pass
    # Normalize and look up
    key = re.sub(r'[\s_\-]', '', raw).lower()
    return _ANCHOR_TYPE_MAP.get(key, AnchorType.CUSTOM)


# ── Page-finding heuristics ──────────────────────────────────────────────────
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


# ── LLM prompt ───────────────────────────────────────────────────────────────

_TIME_ANCHOR_PROMPT = """You are a clinical protocol analyst. Identify the **time anchors** — the reference points from which all study timing is measured.

A time anchor is a specific event or day that other visits, assessments, and endpoints are timed relative to. Examples:
- "Day 1 is defined as the day of first dose of ALXN1840"
- "Day 0 = date of randomisation. All subsequent visits are relative to Day 0."
- "Cycle 1 Day 1 (C1D1) — first infusion of pembrolizumab"

## Instructions
1. Read the protocol text carefully.
2. Identify **1 to 3** time anchors that the protocol actually defines or uses as reference points.
3. For each anchor, provide:
   - `definition`: A protocol-specific definition using the actual drug name, visit, or event (NOT generic text).
   - `anchorType`: One of: FirstDose, TreatmentStart, Randomization, Screening, Day1, Baseline, Enrollment, CycleStart, Custom
   - `dayValue`: The numeric day value (e.g., 1 for Day 1, 0 for Day 0)
   - `sourceText`: An **exact quote** from the protocol (1-2 sentences) that defines or references this anchor.
4. The FIRST anchor in the list must be the **primary** anchor — the one that most other timing references are relative to.

## Important
- DO NOT include generic anchors like "informed consent" or "screening visit" unless the protocol explicitly uses them as the primary timing reference.
- DO NOT invent definitions. Use the protocol's own language.
- Keep `sourceText` as a verbatim quote, not a paraphrase.

{context_block}

## Protocol Text
{text}

Return ONLY valid JSON:
```json
{{
  "timeAnchors": [
    {{
      "definition": "...",
      "anchorType": "...",
      "dayValue": 1,
      "sourceText": "exact quote..."
    }}
  ]
}}
```"""


def _build_context_block(
    existing_encounters: Optional[List[Dict[str, Any]]],
    existing_epochs: Optional[List[Dict[str, Any]]],
    pipeline_context: Optional[Any] = None,
) -> str:
    """Build rich context section from all available upstream data."""
    parts = []
    
    # Study metadata
    if pipeline_context:
        meta_parts = []
        if getattr(pipeline_context, 'study_title', ''):
            meta_parts.append(f"Study: {pipeline_context.study_title}")
        if getattr(pipeline_context, 'indication', ''):
            meta_parts.append(f"Indication: {pipeline_context.indication}")
        if getattr(pipeline_context, 'phase', ''):
            meta_parts.append(f"Phase: {pipeline_context.phase}")
        if getattr(pipeline_context, 'study_type', ''):
            meta_parts.append(f"Type: {pipeline_context.study_type}")
        if meta_parts:
            parts.append("Study metadata: " + "; ".join(meta_parts))
    
    # Study arms
    if pipeline_context and getattr(pipeline_context, 'arms', []):
        arm_names = [a.get('name', '?') for a in pipeline_context.arms[:6]]
        parts.append(f"Study arms: {', '.join(arm_names)}")
    
    # Interventions (drug names, doses — critical for anchor definitions)
    if pipeline_context and getattr(pipeline_context, 'interventions', []):
        intv_descs = []
        for intv in pipeline_context.interventions[:6]:
            name = intv.get('name') or intv.get('description') or '?'
            intv_descs.append(name)
        parts.append(f"Interventions: {'; '.join(intv_descs)}")
    
    # Administrable products (drug formulations)
    if pipeline_context and getattr(pipeline_context, 'products', []):
        prod_names = [p.get('name', '?') for p in pipeline_context.products[:6]]
        parts.append(f"Products: {', '.join(prod_names)}")
    
    # Epochs
    if existing_epochs:
        names = [e.get("name", "?") for e in existing_epochs[:10]]
        parts.append(f"Study epochs: {', '.join(names)}")
    
    # Encounters/visits
    if existing_encounters:
        visit_names = [e.get("name", "?") for e in existing_encounters[:20]]
        parts.append(f"Study visits: {', '.join(visit_names)}")
    
    # Activities (assessment/procedure names)
    if pipeline_context and getattr(pipeline_context, 'activities', []):
        act_names = list(dict.fromkeys(  # dedupe preserving order
            a.get('name', '') for a in pipeline_context.activities if a.get('name')
        ))[:15]
        if act_names:
            parts.append(f"Activities: {', '.join(act_names)}")
    
    # Timings / scheduling rules
    if pipeline_context and getattr(pipeline_context, 'timings', []):
        timing_descs = []
        for t in pipeline_context.timings[:8]:
            desc = t.get('description') or t.get('label') or t.get('name') or ''
            if desc:
                timing_descs.append(desc)
        if timing_descs:
            parts.append(f"Timing rules: {'; '.join(timing_descs)}")
    
    if parts:
        return "## Available Context (from prior extraction phases)\n" + "\n".join(parts)
    return ""


# ── Main extractor ───────────────────────────────────────────────────────────

def extract_time_anchors(
    pdf_path: str,
    model: str = "gemini-2.5-pro",
    pages: Optional[List[int]] = None,
    use_llm: bool = True,
    existing_encounters: Optional[List[Dict[str, Any]]] = None,
    existing_epochs: Optional[List[Dict[str, Any]]] = None,
    pipeline_context: Optional[Any] = None,
) -> ExecutionModelResult:
    """
    Extract time anchors from protocol PDF using LLM-primary approach.
    
    Args:
        pdf_path: Path to protocol PDF
        model: LLM model to use
        pages: Specific pages to analyze (auto-detected if None)
        use_llm: Whether to use LLM (strongly recommended; fallback is minimal)
        existing_encounters: SoA encounters for context
        existing_epochs: SoA epochs for context
        pipeline_context: Full pipeline context with upstream extraction results
        
    Returns:
        ExecutionModelResult with extracted TimeAnchors
    """
    from core.pdf_utils import extract_text_from_pages, get_page_count
    
    logger.info("Starting time anchor extraction (LLM-primary)...")
    
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
    
    anchors: List[TimeAnchor] = []
    
    if use_llm:
        try:
            anchors = _extract_anchors_llm(
                text, model, existing_encounters, existing_epochs,
                pipeline_context=pipeline_context,
            )
        except Exception as e:
            logger.warning(f"LLM anchor extraction failed: {e}")
    
    # Minimal fallback: if LLM failed or was disabled, try a simple heuristic
    if not anchors:
        logger.info("Using minimal heuristic fallback for time anchors")
        anchors = _detect_anchors_fallback(text)
    
    # Ensure primary anchor is first
    if anchors:
        anchors = _prioritize_anchors(anchors)
    
    data = ExecutionModelData(time_anchors=anchors)
    
    result = ExecutionModelResult(
        success=len(anchors) > 0,
        data=data,
        pages_used=pages,
        model_used=model if use_llm else "heuristic_fallback",
    )
    
    logger.info(f"Extracted {len(anchors)} time anchors")
    for a in anchors:
        logger.info(f"  [{a.anchor_type.value}] {a.definition}")
    
    return result


def _extract_anchors_llm(
    text: str,
    model: str,
    existing_encounters: Optional[List[Dict[str, Any]]] = None,
    existing_epochs: Optional[List[Dict[str, Any]]] = None,
    pipeline_context: Optional[Any] = None,
) -> List[TimeAnchor]:
    """Extract time anchors using LLM with protocol-specific prompt."""
    from core.llm_client import call_llm
    
    context_block = _build_context_block(existing_encounters, existing_epochs, pipeline_context)
    
    # Trim text to a reasonable size for the prompt (keep most relevant pages)
    max_chars = 12000
    trimmed_text = text[:max_chars] if len(text) > max_chars else text
    
    prompt = _TIME_ANCHOR_PROMPT.format(
        context_block=context_block,
        text=trimmed_text,
    )
    
    result = call_llm(
        prompt=prompt,
        model_name=model,
        json_mode=True,
        extractor_name="time_anchor",
        temperature=0.1,
    )
    response = result.get('response', '')
    
    # Parse JSON (handle optional ```json``` wrapper)
    json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
    json_str = json_match.group(1) if json_match else response
    
    data = json.loads(json_str)
    
    # Handle various response shapes: dict with key, bare list, or single object
    if isinstance(data, list):
        raw_anchors = data
    elif isinstance(data, dict):
        raw_anchors = data.get('timeAnchors', [])
        if not raw_anchors:
            single = data.get('timeAnchor')
            if single:
                raw_anchors = [single]
            elif 'definition' in data:
                # Single anchor returned as top-level dict
                raw_anchors = [data]
    else:
        raw_anchors = []
    
    anchors: List[TimeAnchor] = []
    seen_types: set = set()
    
    for i, item in enumerate(raw_anchors[:5]):  # cap at 5
        anchor_type = _resolve_anchor_type(item.get('anchorType', ''))
        
        # Skip duplicates by type
        if anchor_type in seen_types and anchor_type != AnchorType.CUSTOM:
            continue
        seen_types.add(anchor_type)
        
        definition = (item.get('definition') or '').strip()
        source_text = (item.get('sourceText') or '').strip()
        
        # Skip empty or clearly generic entries
        if not definition or definition.lower() in (
            'informed consent obtained',
            'informed consent',
            'screening visit',
            'procedure',
        ):
            continue
        
        anchors.append(TimeAnchor(
            id=f"anchor_{i+1}",
            definition=definition,
            anchor_type=anchor_type,
            day_value=item.get('dayValue', 1),
            source_text=source_text or None,
        ))
    
    logger.info(f"LLM extracted {len(anchors)} time anchors")
    return anchors


# ── Minimal fallback (no LLM) ───────────────────────────────────────────────

# Only the most meaningful anchor patterns — no junk like "informed consent"
_FALLBACK_PATTERNS = [
    (r'day\s+1\s+(?:is\s+)?(?:defined\s+as\s+)?.*?(?:first\s+dose|treatment|administration)',
     AnchorType.FIRST_DOSE),
    (r'first\s+(?:dose|administration)\s+of\s+\S+',
     AnchorType.FIRST_DOSE),
    (r'day\s+(?:of\s+)?randomiz?ation',
     AnchorType.RANDOMIZATION),
    (r'days?\s+(?:from|after|since)\s+randomiz?ation',
     AnchorType.RANDOMIZATION),
    (r'cycle\s+1[,\s]+day\s+1',
     AnchorType.CYCLE_START),
    (r'c1d1',
     AnchorType.CYCLE_START),
]


def _detect_anchors_fallback(text: str) -> List[TimeAnchor]:
    """
    Minimal heuristic fallback — only high-value anchor patterns.
    Used when LLM is disabled or fails.
    """
    anchors = []
    seen_types: set = set()
    
    for pattern, anchor_type in _FALLBACK_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match and anchor_type not in seen_types:
            # Extract surrounding sentence for a meaningful sourceText
            start = max(0, match.start() - 80)
            end = min(len(text), match.end() + 80)
            context = text[start:end].strip()
            # Try to trim to sentence boundaries
            sent_start = context.rfind('.', 0, 80)
            if sent_start > 0:
                context = context[sent_start + 1:].strip()
            sent_end = context.find('.', len(context) // 2)
            if sent_end > 0:
                context = context[:sent_end + 1].strip()
            
            anchors.append(TimeAnchor(
                id=f"anchor_{len(anchors)+1}",
                definition=context[:120],  # Use actual context, not canned text
                anchor_type=anchor_type,
                day_value=_extract_day_value(match.group(), context),
                source_text=context[:200],
            ))
            seen_types.add(anchor_type)
    
    return anchors


def _extract_day_value(matched_text: str, context: str) -> int:
    """Extract numeric day value from anchor text."""
    day_match = re.search(r'day\s*(\d+)', matched_text + " " + context, re.IGNORECASE)
    if day_match:
        return int(day_match.group(1))
    if re.search(r'week\s*0', matched_text, re.IGNORECASE):
        return 1
    return 1


def _prioritize_anchors(anchors: List[TimeAnchor]) -> List[TimeAnchor]:
    """Sort anchors by priority (FIRST_DOSE > RANDOMIZATION > DAY_1 > others)."""
    priority = {
        AnchorType.FIRST_DOSE: 1,
        AnchorType.TREATMENT_START: 2,
        AnchorType.RANDOMIZATION: 3,
        AnchorType.DAY_1: 4,
        AnchorType.BASELINE: 5,
        AnchorType.CYCLE_START: 6,
        AnchorType.ENROLLMENT: 7,
        AnchorType.SCREENING: 8,
        AnchorType.CUSTOM: 9,
    }
    return sorted(anchors, key=lambda a: priority.get(a.anchor_type, 10))
