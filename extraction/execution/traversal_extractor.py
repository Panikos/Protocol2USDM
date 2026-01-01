"""
Traversal Constraint Extractor

Extracts required subject path through study design:
- Required epoch/period sequences
- Mandatory visits that cannot be skipped
- Early exit conditions and procedures
- End-of-study requirements

Per reviewer feedback: Synthetic data generators need to know the
valid paths through a study to ensure generated records represent
realistic subject journeys.
"""

import re
import json
import logging
from typing import List, Dict, Any, Optional, Tuple

from .schema import (
    TraversalConstraint,
    ExecutionModelResult, ExecutionModelData
)

logger = logging.getLogger(__name__)


# Epoch/Period detection patterns
EPOCH_PATTERNS: List[Tuple[str, float]] = [
    # Standard epochs
    (r'screening\s+(?:period|phase|epoch|visit)', 0.90),
    (r'run[\-\s]?in\s+(?:period|phase)', 0.85),
    (r'lead[\-\s]?in\s+(?:period|phase)', 0.85),
    (r'treatment\s+(?:period|phase|epoch)', 0.90),
    (r'active\s+treatment\s+(?:period|phase)', 0.90),
    (r'maintenance\s+(?:period|phase)', 0.85),
    (r'follow[\-\s]?up\s+(?:period|phase|epoch)', 0.90),
    (r'washout\s+(?:period|phase)', 0.90),
    (r'extension\s+(?:period|phase)', 0.85),
    (r'end[\-\s]?of[\-\s]?(?:study|treatment)\s+(?:visit|period)?', 0.90),
]

# Sequence requirement patterns
SEQUENCE_PATTERNS: List[Tuple[str, float]] = [
    (r'subjects?\s+(?:must|will|shall)\s+complete\s+(.+)\s+(?:before|prior\s+to)', 0.90),
    (r'following\s+(?:successful\s+)?completion\s+of\s+(.+)', 0.85),
    (r'after\s+(?:completing|completion\s+of)\s+(.+)', 0.85),
    (r'(?:proceed|advance|move)\s+(?:to|into)\s+(.+)\s+(?:phase|period)', 0.80),
]

# Mandatory visit patterns
MANDATORY_PATTERNS: List[Tuple[str, float]] = [
    (r'(?:mandatory|required)\s+(?:visit|assessment)', 0.90),
    (r'(?:must|shall)\s+(?:attend|complete)\s+(?:the\s+)?(.+)\s+visit', 0.85),
    (r'(?:cannot|may\s+not)\s+(?:skip|miss)\s+(.+)\s+visit', 0.90),
    (r'all\s+subjects?\s+(?:must|shall|will)\s+(?:complete|attend)', 0.85),
]

# Early exit patterns
EARLY_EXIT_PATTERNS: List[Tuple[str, float]] = [
    (r'early\s+(?:termination|discontinuation|withdrawal)', 0.90),
    (r'premature\s+(?:termination|discontinuation)', 0.90),
    (r'(?:discontinue|withdraw)\s+(?:from\s+)?(?:the\s+)?study', 0.85),
    (r'(?:if|when)\s+(?:the\s+)?subject\s+(?:discontinues|withdraws)', 0.85),
    (r'(?:early|premature)\s+exit', 0.85),
]

# Keywords for finding traversal-relevant pages
TRAVERSAL_KEYWORDS = [
    r'study\s+design',
    r'study\s+flow',
    r'subject\s+(?:flow|disposition)',
    r'screening',
    r'treatment\s+period',
    r'follow[\-\s]?up',
    r'early\s+termination',
    r'discontinu',
    r'mandatory',
    r'required\s+visit',
]


def find_traversal_pages(
    pdf_path: str,
    max_pages_to_scan: int = 40,
) -> List[int]:
    """Find pages likely to contain study design/flow information."""
    import fitz
    
    pattern = re.compile('|'.join(TRAVERSAL_KEYWORDS), re.IGNORECASE)
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
        
        logger.info(f"Found {len(pages)} potential traversal pages")
        
    except Exception as e:
        logger.error(f"Error scanning PDF for traversal: {e}")
        pages = list(range(min(20, max_pages_to_scan)))
    
    return pages


def _detect_epochs(text: str, existing_epochs: Optional[List[Dict[str, Any]]] = None) -> List[str]:
    """
    Detect study epochs/periods from text.
    
    If existing_epochs from SoA are provided, match against those actual epoch
    names/IDs instead of outputting arbitrary abstract labels.
    """
    text_lower = text.lower()
    
    # If we have existing epochs from SoA, use those as the source of truth
    if existing_epochs:
        return _match_epochs_to_soa(text_lower, existing_epochs)
    
    # Fallback: detect abstract epoch labels (legacy behavior)
    epochs = []
    standard_epochs = [
        ("SCREENING", r'screening\s+(?:period|phase|epoch|visit)?'),
        ("RUN_IN", r'run[\-\s]?in\s+(?:period|phase)?'),
        ("LEAD_IN", r'lead[\-\s]?in\s+(?:period|phase)?'),
        ("BASELINE", r'baseline\s+(?:period|phase|visit)?'),
        ("TREATMENT", r'(?:active\s+)?treatment\s+(?:period|phase|epoch)?'),
        ("MAINTENANCE", r'maintenance\s+(?:period|phase)?'),
        ("WASHOUT", r'washout\s+(?:period|phase)?'),
        ("FOLLOW_UP", r'follow[\-\s]?up\s+(?:period|phase|epoch)?'),
        ("EXTENSION", r'(?:open[\-\s]?label\s+)?extension\s+(?:period|phase)?'),
        ("END_OF_STUDY", r'end[\-\s]?of[\-\s]?(?:study|treatment)'),
    ]
    
    for epoch_name, pattern in standard_epochs:
        if re.search(pattern, text_lower):
            if epoch_name not in epochs:
                epochs.append(epoch_name)
    
    if not epochs:
        epochs = ["SCREENING", "TREATMENT", "FOLLOW_UP", "END_OF_STUDY"]
    
    if "END_OF_STUDY" in epochs:
        epochs.remove("END_OF_STUDY")
    epochs.append("END_OF_STUDY")
    
    return epochs


def _match_epochs_to_soa(text_lower: str, existing_epochs: List[Dict[str, Any]]) -> List[str]:
    """
    Match traversal references to actual SoA epoch IDs.
    
    This ensures traversal constraints reference real epoch IDs from the start,
    avoiding the need for downstream resolution.
    """
    matched_epochs = []
    
    # Build a mapping of epoch patterns to actual epoch IDs
    epoch_patterns = []
    for epoch in existing_epochs:
        epoch_id = epoch.get('id', '')
        epoch_name = epoch.get('name', '')
        name_lower = epoch_name.lower()
        
        # Create patterns to match this epoch in text
        patterns = [
            re.escape(epoch_name.lower()),  # Exact name match
            re.escape(name_lower.replace(' ', r'\s*')),  # Flexible spacing
        ]
        
        # Add semantic patterns based on epoch name content
        if 'screen' in name_lower:
            patterns.append(r'screening\s+(?:period|phase|epoch|visit)?')
        if 'baseline' in name_lower or 'day 1' in name_lower or 'day-1' in name_lower:
            patterns.append(r'baseline\s+(?:period|phase|visit)?')
        if 'treatment' in name_lower or 'active' in name_lower:
            patterns.append(r'(?:active\s+)?treatment\s+(?:period|phase|epoch)?')
        if 'inpatient' in name_lower:
            patterns.append(r'inpatient\s+(?:period|phase)?\s*\d*')
        if 'outpatient' in name_lower or name_lower == 'op':
            patterns.append(r'outpatient\s+(?:period|phase)?')
        if 'follow' in name_lower:
            patterns.append(r'follow[\-\s]?up\s+(?:period|phase|epoch)?')
        if 'maintenance' in name_lower:
            patterns.append(r'maintenance\s+(?:period|phase)?')
        if 'washout' in name_lower:
            patterns.append(r'washout\s+(?:period|phase)?')
        if 'end' in name_lower or 'eos' in name_lower or 'et' in name_lower:
            patterns.append(r'end[\-\s]?of[\-\s]?(?:study|treatment)')
        
        epoch_patterns.append((epoch_id, epoch_name, patterns))
    
    # Check which epochs are mentioned in the traversal text
    for epoch_id, epoch_name, patterns in epoch_patterns:
        for pattern in patterns:
            try:
                if re.search(pattern, text_lower):
                    if epoch_id not in matched_epochs:
                        matched_epochs.append(epoch_id)
                        logger.debug(f"Matched traversal epoch: {epoch_name} ({epoch_id})")
                    break
            except re.error:
                continue
    
    # If no matches, return all epochs in sequence order (sorted by sequenceNumber if available)
    if not matched_epochs:
        sorted_epochs = sorted(existing_epochs, key=lambda e: e.get('sequenceNumber', 999))
        matched_epochs = [e.get('id', '') for e in sorted_epochs if e.get('id')]
        logger.info(f"No specific traversal matches - using all {len(matched_epochs)} SoA epochs in sequence")
    
    return matched_epochs


def _detect_mandatory_visits(text: str) -> List[str]:
    """Detect mandatory visits from text."""
    mandatory = []
    text_lower = text.lower()
    
    # Always mandatory
    mandatory.append("Screening")
    
    # Look for explicit mandatory mentions
    for pattern, _ in MANDATORY_PATTERNS:
        matches = re.findall(pattern, text_lower)
        for match in matches:
            if isinstance(match, str):
                # Clean up the match
                visit_name = match.strip().title()
                if visit_name and visit_name not in mandatory:
                    mandatory.append(visit_name)
    
    # Common mandatory visits
    common_mandatory = [
        (r'day\s+1', "Day 1"),
        (r'baseline\s+visit', "Baseline"),
        (r'randomization\s+visit', "Randomization"),
        (r'end[\-\s]?of[\-\s]?(?:study|treatment)\s+visit', "End of Study"),
        (r'(?:final|termination)\s+visit', "End of Study"),
        (r'(?:30|28)[\-\s]?day\s+(?:safety\s+)?follow[\-\s]?up', "Safety Follow-up"),
    ]
    
    for pattern, visit_name in common_mandatory:
        if re.search(pattern, text_lower):
            if visit_name not in mandatory:
                mandatory.append(visit_name)
    
    # Ensure End of Study is included
    if "End of Study" not in mandatory:
        mandatory.append("End of Study")
    
    return mandatory


def _detect_early_exit_conditions(text: str) -> Tuple[bool, List[str]]:
    """Detect early exit allowance and required procedures."""
    text_lower = text.lower()
    
    allows_early_exit = False
    exit_procedures = []
    
    # Check for early termination mentions
    for pattern, _ in EARLY_EXIT_PATTERNS:
        if re.search(pattern, text_lower):
            allows_early_exit = True
            break
    
    # Look for required exit procedures
    exit_procedure_patterns = [
        (r'early\s+termination\s+visit', "Early Termination Visit"),
        (r'(?:30|28)[\-\s]?day\s+(?:safety\s+)?follow[\-\s]?up', "30-Day Follow-up"),
        (r'end[\-\s]?of[\-\s]?treatment\s+(?:visit|assessment)', "End of Treatment"),
        (r'safety\s+follow[\-\s]?up', "Safety Follow-up"),
    ]
    
    for pattern, proc_name in exit_procedure_patterns:
        if re.search(pattern, text_lower):
            if proc_name not in exit_procedures:
                exit_procedures.append(proc_name)
    
    return allows_early_exit, exit_procedures


def extract_traversal_constraints(
    pdf_path: str,
    model: str = "gemini-2.5-pro",
    pages: Optional[List[int]] = None,
    use_llm: bool = True,
    existing_epochs: Optional[List[Dict[str, Any]]] = None,
) -> ExecutionModelResult:
    """
    Extract traversal constraints from protocol PDF.
    
    Args:
        pdf_path: Path to protocol PDF
        model: LLM model to use
        pages: Specific pages to analyze
        use_llm: Whether to use LLM enhancement
        existing_epochs: Epochs from SoA extraction to use as reference
                        (avoids outputting abstract labels that need resolution)
        
    Returns:
        ExecutionModelResult with TraversalConstraints
    """
    from core.pdf_utils import extract_text_from_pages, get_page_count
    
    logger.info("Starting traversal constraint extraction...")
    
    # Find relevant pages
    if pages is None:
        pages = find_traversal_pages(pdf_path)
    
    if not pages:
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
    
    # Heuristic extraction - pass existing epochs to match against SoA
    epochs = _detect_epochs(text, existing_epochs)
    mandatory_visits = _detect_mandatory_visits(text)
    allows_early_exit, exit_procedures = _detect_early_exit_conditions(text)
    
    # Log whether we used SoA epochs or abstract labels
    if existing_epochs:
        logger.info(f"Matched traversal to {len(epochs)} existing SoA epoch IDs")
    else:
        logger.info(f"No SoA epochs provided - using abstract labels: {epochs}")
    
    # Build constraint
    constraint = TraversalConstraint(
        id="traversal_1",
        required_sequence=epochs,
        allow_early_exit=allows_early_exit,
        exit_epoch_ids=["EARLY_TERMINATION"] if allows_early_exit else [],
        mandatory_visits=mandatory_visits,
    )
    
    # LLM enhancement
    if use_llm:
        try:
            llm_constraint = _extract_traversal_llm(text, model)
            if llm_constraint:
                constraint = _merge_traversal(constraint, llm_constraint)
        except Exception as e:
            logger.warning(f"LLM traversal extraction failed: {e}")
    
    data = ExecutionModelData(traversal_constraints=[constraint])
    
    logger.info(
        f"Extracted traversal: {len(epochs)} epochs, "
        f"{len(mandatory_visits)} mandatory visits, "
        f"early_exit={allows_early_exit}"
    )
    
    return ExecutionModelResult(
        success=True,
        data=data,
        pages_used=pages,
        model_used=model if use_llm else "heuristic",
    )


def _extract_traversal_llm(text: str, model: str) -> Optional[TraversalConstraint]:
    """Extract traversal constraints using LLM."""
    from core.llm_client import call_llm
    
    prompt = f"""Analyze this clinical protocol and extract the REQUIRED SUBJECT PATH through the study.

Identify:
1. Study epochs/periods in order (e.g., Screening → Treatment → Follow-up)
2. Mandatory visits that cannot be skipped
3. Early termination conditions and required procedures
4. Any branching or conditional paths

Return JSON:
```json
{{
  "requiredSequence": ["SCREENING", "BASELINE", "TREATMENT", "FOLLOW_UP", "END_OF_STUDY"],
  "mandatoryVisits": ["Screening", "Day 1", "Week 12", "End of Study"],
  "allowEarlyExit": true,
  "earlyExitProcedures": ["Early Termination Visit", "30-Day Follow-up"],
  "conditionalPaths": [
    {{
      "condition": "If subject experiences AE requiring discontinuation",
      "path": ["EARLY_TERMINATION", "SAFETY_FOLLOW_UP"]
    }}
  ],
  "confidence": 0.85
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
        
        return TraversalConstraint(
            id="traversal_llm_1",
            required_sequence=data.get('requiredSequence', []),
            allow_early_exit=data.get('allowEarlyExit', True),
            exit_epoch_ids=["EARLY_TERMINATION"] if data.get('allowEarlyExit', True) else [],
            mandatory_visits=data.get('mandatoryVisits', []),
            source_text=str(data.get('conditionalPaths', [])),
        )
        
    except Exception as e:
        logger.error(f"LLM traversal extraction failed: {e}")
        return None


def _merge_traversal(
    heuristic: TraversalConstraint,
    llm: TraversalConstraint,
) -> TraversalConstraint:
    """Merge heuristic and LLM traversal constraints."""
    # Prefer LLM sequence if it has more detail
    sequence = llm.required_sequence if len(llm.required_sequence) > len(heuristic.required_sequence) else heuristic.required_sequence
    
    # Merge mandatory visits
    mandatory = list(set(heuristic.mandatory_visits + llm.mandatory_visits))
    
    return TraversalConstraint(
        id=heuristic.id,
        required_sequence=sequence,
        allow_early_exit=heuristic.allow_early_exit or llm.allow_early_exit,
        exit_epoch_ids=list(set(heuristic.exit_epoch_ids + llm.exit_epoch_ids)),
        mandatory_visits=mandatory,
        source_text=llm.source_text or heuristic.source_text,
    )
