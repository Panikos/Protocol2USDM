"""
Execution Type Classifier

Classifies activities as WINDOW vs EPISODE execution types.

WINDOW: Continuous repeated data collection over a time period
  - Example: Balance collection Days -4 to -1
  - Example: Daily glucose monitoring
  - Characterized by: "Day X to Day Y", "during the period", "throughout"

EPISODE: Ordered conditional workflow with decision points
  - Example: Insulin → PG check → Glucagon sequence
  - Example: If lab > threshold, then action
  - Characterized by: "until", "once [condition]", "after [event]", "when [threshold]"

Per reviewer feedback: This distinction is critical for synthetic data 
generators to know whether to produce continuous vs. discrete records.
"""

import re
import json
import logging
from typing import List, Dict, Any, Optional, Tuple

from .schema import (
    ExecutionType, ExecutionTypeAssignment,
    ExecutionModelResult, ExecutionModelData
)

logger = logging.getLogger(__name__)


# =============================================================================
# EXECUTION TYPE PATTERNS - Organized by therapeutic area
# =============================================================================

# Patterns indicating WINDOW execution (continuous collection)
WINDOW_PATTERNS: List[Tuple[str, float]] = [
    # Day/Week ranges - General
    (r'day(?:s)?\s*[-–]?\d+\s*(?:to|through|[-–])\s*(?:day\s*)?[-–]?\d+', 0.90),
    (r'from\s+day\s*[-–]?\d+\s+to\s+day', 0.90),
    (r'week(?:s)?\s*\d+\s*(?:to|through|[-–])\s*(?:week\s*)?\d+', 0.90),
    
    # Duration-based
    (r'during\s+(?:the\s+)?(?:\d+[\s-]*day|entire|full)\s+(?:period|window|phase)', 0.85),
    (r'throughout\s+(?:the\s+)?(?:treatment|study|dosing|observation)\s+period', 0.85),
    (r'continuous(?:ly)?\s+(?:monitor|collect|measure|record)', 0.85),
    (r'over\s+(?:a\s+)?(?:\d+[\s-]*(?:day|hour|week))\s+period', 0.85),
    
    # Daily/repeated
    (r'daily\s+(?:collection|measurement|monitoring|assessment|diary)', 0.80),
    (r'once\s+daily\s+(?:for|during|throughout)', 0.80),
    (r'every\s+day\s+(?:of|during|for)', 0.80),
    
    # Interval sampling
    (r'every\s+\d+\s*(?:min(?:ute)?s?|hours?)\s+(?:for|during|over)', 0.85),
    (r'at\s+\d+(?:,\s*\d+)+\s*(?:min(?:ute)?s?|hours?)', 0.85),
    
    # Diabetes/Metabolic - Window patterns
    (r'(?:glucose|cgm|blood\s+sugar)\s+(?:monitoring|measurement)\s+(?:for|during|over)', 0.90),
    (r'clamp\s+(?:procedure|study)', 0.85),
    (r'(?:meal|glucose)\s+tolerance\s+test', 0.85),
    (r'(?:24|48|72)[\s-]*(?:hour|hr)\s+(?:urine|stool|collection|monitoring)', 0.90),
    
    # Cardiology - Continuous monitoring
    (r'(?:holter|ambulatory|continuous)\s+(?:ecg|ekg|monitoring)', 0.90),
    (r'(?:24|48)[\s-]*(?:hour|hr)\s+(?:bp|blood\s+pressure|ecg|ekg)', 0.90),
    (r'telemetry\s+monitoring', 0.85),
    
    # Rare Disease - Balance windows
    (r'(?:balance|metabolic)\s+(?:period|study|collection)', 0.90),
    (r'(?:copper|iron|zinc|substrate)\s+(?:balance|excretion)', 0.90),
    
    # Hospitalization/Confinement
    (r'(?:in[\-\s]?patient|hospitalization|confinement)\s+(?:period|stay)', 0.85),
    (r'during\s+(?:hospitalization|admission|stay)', 0.85),
    
    # Infusion - During/post monitoring
    (r'during\s+(?:the\s+)?infusion', 0.85),
    (r'(?:infusion|injection)\s+(?:period|window)', 0.85),
    
    # PK/PD - Dense sampling windows
    (r'(?:pk|pd|pharmacokinetic|pharmacodynamic)\s+(?:sampling|profile|window)', 0.90),
    (r'serial\s+(?:blood|plasma|serum)\s+(?:samples?|sampling)', 0.85),
]

# Patterns indicating EPISODE execution (conditional workflow)
EPISODE_PATTERNS: List[Tuple[str, float]] = [
    # Conditional triggers - General
    (r'if\s+(?:the\s+)?(?:patient|subject|value|level|result)', 0.90),
    (r'when\s+(?:the\s+)?(?:value|level|result)\s*(?:is|exceeds?|falls?|drops?)', 0.90),
    (r'once\s+(?:the\s+)?(?:target|threshold|level)\s+(?:is\s+)?(?:reached|achieved|met)', 0.90),
    (r'in\s+(?:the\s+)?(?:event|case)\s+(?:of|that)', 0.85),
    
    # Sequential actions
    (r'(?:then|followed\s+by|subsequently)\s+(?:administer|give|perform|collect)', 0.85),
    (r'after\s+(?:the\s+)?(?:first|initial|previous)\s+(?:dose|measurement|assessment)', 0.85),
    (r'prior\s+to\s+(?:the\s+)?(?:next|subsequent|following)', 0.80),
    (r'before\s+(?:and\s+after|proceeding)', 0.80),
    
    # Until conditions
    (r'until\s+(?:the\s+)?(?:value|level|glucose|response)\s*(?:is|reaches?|exceeds?)', 0.90),
    (r'until\s+(?:stable|normal|baseline|target|resolved)', 0.85),
    (r'continue\s+(?:until|unless|while)', 0.85),
    
    # Threshold-based - General
    (r'(?:if|when)\s+(?:pg|glucose|lab|value|result)\s*[<>≤≥=]\s*\d+', 0.90),
    (r'threshold\s+(?:of\s+)?\d+', 0.80),
    (r'(?:above|below|exceeds?|falls?\s+below)\s+\d+', 0.85),
    
    # Rescue/intervention triggers
    (r'rescue\s+(?:medication|therapy|treatment|intervention)', 0.85),
    (r'(?:administer|give)\s+(?:rescue|emergency|additional)', 0.85),
    (r'(?:breakthrough|escape)\s+(?:medication|therapy|treatment)', 0.85),
    
    # Diabetes - Hypoglycemia episodes
    (r'(?:if|when)\s+(?:glucose|blood\s+sugar|bg)\s*[<≤]\s*\d+', 0.95),
    (r'hypoglycemi(?:a|c)\s+(?:event|episode|rescue)', 0.90),
    (r'(?:glucagon|dextrose|glucose)\s+(?:rescue|administration)', 0.90),
    
    # Oncology - Dose modifications
    (r'(?:dose|treatment)\s+(?:modification|reduction|interruption|delay)', 0.85),
    (r'(?:if|when)\s+(?:toxicity|adverse\s+event|ae)\s+(?:occurs?|is\s+observed)', 0.90),
    (r'(?:grade\s+)?[≥>]\s*[234]\s+(?:toxicity|adverse\s+event)', 0.90),
    (r'(?:hold|withhold|discontinue)\s+(?:treatment|dosing)\s+(?:if|until)', 0.85),
    
    # Cardiology - Event-driven
    (r'(?:if|when)\s+(?:bp|blood\s+pressure|hr|heart\s+rate)\s*[<>]\s*\d+', 0.90),
    (r'(?:chest\s+pain|angina|arrhythmia)\s+(?:occurs?|is\s+reported)', 0.85),
    
    # Neurology - Event-driven
    (r'(?:if|when)\s+(?:seizure|attack|episode)\s+occurs?', 0.90),
    (r'(?:rescue|abortive)\s+(?:medication|treatment)', 0.85),
    
    # Vaccines - Adverse reaction
    (r'(?:if|when)\s+(?:reaction|adverse\s+event)\s+occurs?', 0.85),
    (r'(?:anaphylaxis|anaphylactic)\s+(?:protocol|management)', 0.90),
    
    # Infusion - Reaction management
    (r'(?:infusion|injection)[\s-]*(?:related\s+)?reaction', 0.85),
    (r'(?:slow|stop|pause)\s+(?:infusion|injection)\s+(?:if|when)', 0.90),
]

# Patterns indicating SINGLE execution (one-time)
SINGLE_PATTERNS: List[Tuple[str, float]] = [
    # General one-time
    (r'(?:at\s+)?(?:screening|baseline|randomization)\s+(?:only|visit)', 0.85),
    (r'(?:one|single)\s+time\s+(?:only|at)', 0.80),
    (r'(?:performed|collected|assessed)\s+once', 0.80),
    (r'(?:one[\s-]*time|single)\s+(?:assessment|measurement|collection)', 0.85),
    
    # Specific single events
    (r'(?:at\s+)?(?:enrollment|entry|day\s+1)\s+only', 0.85),
    (r'(?:at\s+)?end[\s-]*of[\s-]*(?:study|treatment)\s+(?:only|visit)', 0.85),
    (r'(?:at\s+)?(?:final|termination|discontinuation)\s+visit', 0.85),
    
    # Procedures - typically one-time
    (r'(?:biopsy|surgery|procedure|implantation)', 0.75),
    (r'(?:genetic|genomic)\s+(?:testing|analysis|sampling)', 0.80),
    (r'(?:informed\s+consent|icf)', 0.90),
    (r'(?:randomization|stratification)', 0.85),
    
    # Device/Vaccine - Initial
    (r'(?:device|implant)\s+(?:insertion|implantation|placement)', 0.85),
]

# Patterns indicating RECURRING execution (scheduled repeats)
RECURRING_PATTERNS: List[Tuple[str, float]] = [
    # At each visit - General
    (r'at\s+(?:each|every|all)\s+(?:\w+\s+)?(?:visit|encounter|timepoint)', 0.85),
    (r'(?:at\s+)?each\s+(?:\w+\s+)?visit', 0.85),
    (r'(?:recorded|measured|assessed|performed)\s+at\s+(?:each|every|all)', 0.80),
    
    # Scheduled frequency
    (r'(?:weekly|monthly|quarterly|biweekly)\s+(?:assessment|visit|evaluation|monitoring)', 0.85),
    (r'every\s+(?:\d+\s+)?(?:week|month|visit)', 0.80),
    (r'(?:q\d+w|q\d+m)', 0.80),  # q4w, q3m notation
    
    # Standard assessments at visits
    (r'(?:vital\s+signs?|vitals)\s+(?:at\s+)?(?:each|every)\s+visit', 0.90),
    (r'(?:physical\s+exam(?:ination)?|pe)\s+(?:at\s+)?(?:each|every)\s+visit', 0.85),
    (r'(?:adverse\s+events?|ae)\s+(?:assessment|review|collection)', 0.80),
    (r'(?:concomitant\s+medications?|con\s*meds?)\s+(?:review|assessment)', 0.80),
    
    # Labs at scheduled visits
    (r'(?:laboratory|lab)\s+(?:tests?|assessments?)\s+(?:at\s+)?(?:each|every|scheduled)', 0.85),
    (r'(?:chemistry|hematology|urinalysis)\s+(?:at\s+)?(?:each|every)\s+visit', 0.85),
    
    # Oncology - Per cycle
    (r'(?:at|on)\s+(?:day\s+1\s+of\s+)?each\s+cycle', 0.90),
    (r'(?:every|each)\s+cycle', 0.85),
    (r'(?:tumor|disease)\s+(?:assessment|evaluation)\s+every\s+\d+\s+(?:weeks?|cycles?)', 0.85),
    
    # PRO/ePRO - At visits
    (r'(?:questionnaire|pro|epro|diary)\s+(?:at\s+)?(?:each|every)\s+visit', 0.85),
    (r'(?:patient|subject)\s+(?:reported|diary)\s+(?:at\s+)?(?:each|scheduled)', 0.80),
]


def _score_text_for_type(
    text: str,
    patterns: List[Tuple[str, float]]
) -> Tuple[int, float]:
    """
    Score text against patterns for an execution type.
    
    Returns:
        Tuple of (match_count, max_confidence)
    """
    match_count = 0
    max_confidence = 0.0
    
    for pattern, confidence in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            match_count += len(matches)
            max_confidence = max(max_confidence, confidence)
    
    return match_count, max_confidence


def classify_activity_text(
    activity_name: str,
    context_text: str,
) -> ExecutionTypeAssignment:
    """
    Classify a single activity based on its name and context.
    
    Args:
        activity_name: Name of the activity
        context_text: Surrounding protocol text mentioning this activity
        
    Returns:
        ExecutionTypeAssignment with classified type
    """
    combined_text = f"{activity_name} {context_text}".lower()
    
    # Score against each type
    window_count, window_conf = _score_text_for_type(combined_text, WINDOW_PATTERNS)
    episode_count, episode_conf = _score_text_for_type(combined_text, EPISODE_PATTERNS)
    single_count, single_conf = _score_text_for_type(combined_text, SINGLE_PATTERNS)
    recurring_count, recurring_conf = _score_text_for_type(combined_text, RECURRING_PATTERNS)
    
    # Determine winner
    scores = [
        (ExecutionType.WINDOW, window_count, window_conf),
        (ExecutionType.EPISODE, episode_count, episode_conf),
        (ExecutionType.SINGLE, single_count, single_conf),
        (ExecutionType.RECURRING, recurring_count, recurring_conf),
    ]
    
    # Sort by match count, then confidence
    scores.sort(key=lambda x: (x[1], x[2]), reverse=True)
    
    winner_type, winner_count, winner_conf = scores[0]
    
    # Default to SINGLE if no strong signals
    if winner_count == 0:
        winner_type = ExecutionType.SINGLE
        winner_conf = 0.5
    
    # Build rationale
    rationale_parts = []
    if window_count > 0:
        rationale_parts.append(f"WINDOW signals: {window_count}")
    if episode_count > 0:
        rationale_parts.append(f"EPISODE signals: {episode_count}")
    if single_count > 0:
        rationale_parts.append(f"SINGLE signals: {single_count}")
    if recurring_count > 0:
        rationale_parts.append(f"RECURRING signals: {recurring_count}")
    
    rationale = "; ".join(rationale_parts) if rationale_parts else "No strong signals detected"
    
    return ExecutionTypeAssignment(
        activity_id=activity_name,
        execution_type=winner_type,
        rationale=rationale,
    )


def classify_execution_types(
    pdf_path: str,
    activities: Optional[List[Dict[str, Any]]] = None,
    model: str = "gemini-2.5-pro",
    use_llm: bool = False,
) -> ExecutionModelResult:
    """
    Classify execution types for activities in a protocol.
    
    Args:
        pdf_path: Path to protocol PDF
        activities: List of activity dicts with 'id' and 'name' keys
                   If None, will scan PDF for activity mentions
        model: LLM model to use (if use_llm=True)
        use_llm: Whether to use LLM for enhanced classification
        
    Returns:
        ExecutionModelResult with ExecutionTypeAssignments
    """
    from core.pdf_utils import extract_text_from_pages, get_page_count
    
    logger.info("Starting execution type classification...")
    
    # Get full text for context
    pages = list(range(min(40, get_page_count(pdf_path))))
    text = extract_text_from_pages(pdf_path, pages)
    
    if not text:
        return ExecutionModelResult(
            success=False,
            error="Failed to extract text from PDF",
            pages_used=pages,
            model_used=model,
        )
    
    assignments = []
    
    if activities:
        # Classify provided activities
        for activity in activities:
            activity_name = activity.get('name', activity.get('id', ''))
            
            # Find context around activity mentions
            context = _find_activity_context(activity_name, text)
            
            assignment = classify_activity_text(activity_name, context)
            assignment.activity_id = activity.get('id', activity_name)
            
            assignments.append(assignment)
    else:
        # Scan for common activity types and classify
        common_activities = _detect_common_activities(text)
        
        for activity_name in common_activities:
            context = _find_activity_context(activity_name, text)
            assignment = classify_activity_text(activity_name, context)
            assignments.append(assignment)
    
    # LLM enhancement
    if use_llm and len(text) > 100:
        try:
            llm_assignments = _classify_with_llm(text, model)
            assignments = _merge_assignments(assignments, llm_assignments)
        except Exception as e:
            logger.warning(f"LLM classification failed: {e}")
    
    data = ExecutionModelData(execution_types=assignments)
    
    result = ExecutionModelResult(
        success=len(assignments) > 0,
        data=data,
        pages_used=pages,
        model_used=model if use_llm else "heuristic",
    )
    
    # Log summary
    type_counts = {}
    for a in assignments:
        type_counts[a.execution_type.value] = type_counts.get(a.execution_type.value, 0) + 1
    
    logger.info(f"Classified {len(assignments)} activities: {type_counts}")
    
    return result


def _find_activity_context(activity_name: str, text: str, context_size: int = 500) -> str:
    """Find text surrounding mentions of an activity."""
    contexts = []
    
    # Escape special regex chars in activity name
    escaped_name = re.escape(activity_name)
    
    # Find all mentions
    for match in re.finditer(escaped_name, text, re.IGNORECASE):
        start = max(0, match.start() - context_size)
        end = min(len(text), match.end() + context_size)
        contexts.append(text[start:end])
    
    return " ".join(contexts[:3])  # Limit to first 3 mentions


def _detect_common_activities(text: str) -> List[str]:
    """Detect common clinical trial activity types from text."""
    activity_patterns = [
        r'(?:blood|urine|serum|plasma)\s+(?:sample|collection|draw)',
        r'(?:vital\s+signs?|vitals)',
        r'(?:ECG|electrocardiogram|EKG)',
        r'(?:physical\s+exam(?:ination)?|PE)',
        r'(?:adverse\s+events?|AE)',
        r'(?:concomitant\s+medications?)',
        r'(?:laboratory\s+(?:tests?|assessments?))',
        r'(?:PK\s+sampling|pharmacokinetic)',
        r'(?:PD\s+(?:sampling|assessment)|pharmacodynamic)',
        r'(?:glucose\s+(?:monitoring|measurement))',
        r'(?:insulin\s+(?:administration|infusion))',
        r'(?:drug\s+administration|dosing)',
        r'(?:imaging|MRI|CT\s+scan|X-ray)',
        r'(?:biopsy|tissue\s+sample)',
        r'(?:questionnaire|diary|ePRO)',
    ]
    
    detected = []
    for pattern in activity_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # Normalize to most common form
            normalized = matches[0].strip().title()
            if normalized not in detected:
                detected.append(normalized)
    
    return detected


def _classify_with_llm(text: str, model: str) -> List[ExecutionTypeAssignment]:
    """Use LLM for execution type classification."""
    from core.llm_client import call_llm
    
    prompt = f"""Analyze this clinical protocol and classify the DATA COLLECTION ACTIVITIES by execution type:

EXECUTION TYPES:
- WINDOW: Continuous repeated collection over time period (e.g., "daily urine Days -4 to -1", "glucose every 5 min for 30 min")
- EPISODE: Ordered conditional workflow with decision points (e.g., "if glucose < 70, administer glucagon", "until target reached")
- SINGLE: One-time assessment (e.g., "at screening only")
- RECURRING: Scheduled repeats at visits (e.g., "at each study visit")

Return JSON:
```json
{{
  "classifications": [
    {{
      "activityName": "Balance Collection",
      "executionType": "Window",
      "rationale": "Days -4 to -1 indicates continuous collection window"
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
            extractor_name="execution_type",
            temperature=0.1,
        )
        response = result.get('response', '')
        
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response
        
        data = json.loads(json_str)
        
        assignments = []
        for item in data.get('classifications', []):
            try:
                exec_type = ExecutionType(item.get('executionType', 'Single'))
            except ValueError:
                exec_type = ExecutionType.SINGLE
            
            assignments.append(ExecutionTypeAssignment(
                activity_id=item.get('activityName', ''),
                execution_type=exec_type,
                rationale=item.get('rationale'),
            ))
        
        return assignments
        
    except Exception as e:
        logger.error(f"LLM classification failed: {e}")
        return []


def _merge_assignments(
    heuristic: List[ExecutionTypeAssignment],
    llm: List[ExecutionTypeAssignment]
) -> List[ExecutionTypeAssignment]:
    """Merge heuristic and LLM assignments, preferring higher confidence."""
    merged = {}
    
    for assignment in heuristic + llm:
        key = assignment.activity_id.lower()
        if key not in merged:
            merged[key] = assignment
    
    return list(merged.values())
