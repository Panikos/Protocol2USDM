"""
Subject State Machine Generator

Generates a state machine describing valid subject paths through a study.
Enables validation of subject journeys and realistic disposition patterns.
"""

import re
import logging
from typing import List, Optional, Tuple, Dict, Any

from .schema import (
    SubjectStateMachine,
    StateTransition,
    StateType,
    TraversalConstraint,
    CrossoverDesign,
    ExecutionModelData,
    ExecutionModelResult,
)

logger = logging.getLogger(__name__)


# Keywords for finding disposition/state pages
STATE_KEYWORDS = [
    "disposition", "subject flow", "patient flow", "discontinuation",
    "withdrawal", "completion", "early termination", "screen failure",
    "randomization", "enrollment", "follow-up", "lost to follow-up",
    "adverse event", "death", "consent withdrawn",
]

# Common discontinuation reasons
DISCONTINUATION_REASONS = [
    "adverse event",
    "lack of efficacy",
    "withdrawal of consent",
    "lost to follow-up",
    "protocol deviation",
    "investigator decision",
    "sponsor decision",
    "death",
    "disease progression",
    "pregnancy",
]

# Standard state transitions for typical studies
STANDARD_TRANSITIONS = [
    # Screening to enrolled/screen failure
    (StateType.SCREENING, StateType.ENROLLED, "Meets eligibility criteria"),
    (StateType.SCREENING, StateType.DISCONTINUED, "Screen failure"),
    
    # Enrolled to randomized
    (StateType.ENROLLED, StateType.RANDOMIZED, "Randomization"),
    (StateType.ENROLLED, StateType.DISCONTINUED, "Early withdrawal before randomization"),
    
    # Randomized to on treatment
    (StateType.RANDOMIZED, StateType.ON_TREATMENT, "First dose administered"),
    (StateType.RANDOMIZED, StateType.DISCONTINUED, "Withdrawal before treatment"),
    
    # On treatment outcomes
    (StateType.ON_TREATMENT, StateType.COMPLETED, "Completes treatment period"),
    (StateType.ON_TREATMENT, StateType.DISCONTINUED, "Discontinues treatment"),
    (StateType.ON_TREATMENT, StateType.FOLLOW_UP, "Enters follow-up"),
    (StateType.ON_TREATMENT, StateType.DEATH, "Death on treatment"),
    
    # Follow-up outcomes
    (StateType.FOLLOW_UP, StateType.COMPLETED, "Completes follow-up"),
    (StateType.FOLLOW_UP, StateType.LOST_TO_FOLLOW_UP, "Lost to follow-up"),
    (StateType.FOLLOW_UP, StateType.WITHDRAWN, "Withdraws during follow-up"),
    (StateType.FOLLOW_UP, StateType.DEATH, "Death during follow-up"),
    
    # Discontinued to follow-up
    (StateType.DISCONTINUED, StateType.FOLLOW_UP, "Safety follow-up after discontinuation"),
    (StateType.DISCONTINUED, StateType.COMPLETED, "Completes early termination procedures"),
]


def find_disposition_pages(pdf_path: str) -> List[int]:
    """Find pages likely to contain disposition/flow information."""
    from core.pdf_utils import extract_text_from_pages, get_page_count
    
    page_count = get_page_count(pdf_path)
    relevant_pages = []
    
    for page_idx in range(min(page_count, 80)):
        text = extract_text_from_pages(pdf_path, [page_idx])
        if text:
            text_lower = text.lower()
            score = sum(1 for kw in STATE_KEYWORDS if kw in text_lower)
            if score >= 2:
                relevant_pages.append(page_idx)
    
    return relevant_pages


def _detect_states_from_text(text: str) -> List[StateType]:
    """Detect which states are present in the study."""
    text_lower = text.lower()
    states = set()
    
    # Always include screening
    states.add(StateType.SCREENING)
    
    # Check for specific states
    state_patterns = [
        (r'enroll(?:ed|ment)', StateType.ENROLLED),
        (r'random(?:ized?|ization)', StateType.RANDOMIZED),
        (r'(?:on\s+)?treatment\s+(?:period|phase)', StateType.ON_TREATMENT),
        (r'complet(?:ed?|ion)', StateType.COMPLETED),
        (r'discontinu(?:ed?|ation)', StateType.DISCONTINUED),
        (r'follow[- ]?up', StateType.FOLLOW_UP),
        (r'lost\s+to\s+follow[- ]?up', StateType.LOST_TO_FOLLOW_UP),
        (r'withdr(?:ew|awn|awal)', StateType.WITHDRAWN),
        (r'death|died|deceased', StateType.DEATH),
    ]
    
    for pattern, state in state_patterns:
        if re.search(pattern, text_lower):
            states.add(state)
    
    return list(states)


def _detect_transitions_from_text(text: str, states: List[StateType]) -> List[StateTransition]:
    """Detect transitions from protocol text."""
    transitions = []
    text_lower = text.lower()
    
    # Add standard transitions that apply to detected states
    for from_state, to_state, trigger in STANDARD_TRANSITIONS:
        if from_state in states and to_state in states:
            transitions.append(StateTransition(
                from_state=from_state,
                to_state=to_state,
                trigger=trigger,
            ))
    
    # Look for specific discontinuation reasons
    for reason in DISCONTINUATION_REASONS:
        if reason in text_lower:
            # Find what state leads to discontinuation due to this reason
            if StateType.ON_TREATMENT in states:
                # Check if this is a unique transition
                existing = [t for t in transitions 
                           if t.from_state == StateType.ON_TREATMENT 
                           and t.to_state == StateType.DISCONTINUED
                           and reason in t.trigger.lower()]
                if not existing:
                    transitions.append(StateTransition(
                        from_state=StateType.ON_TREATMENT,
                        to_state=StateType.DISCONTINUED,
                        trigger=f"Discontinuation due to {reason}",
                    ))
    
    return transitions


def _detect_guard_conditions(text: str, transitions: List[StateTransition]) -> List[StateTransition]:
    """Add guard conditions to transitions based on protocol text."""
    text_lower = text.lower()
    
    enhanced = []
    for t in transitions:
        guard = None
        actions = []
        
        # Screen failure conditions
        if t.from_state == StateType.SCREENING and t.to_state == StateType.DISCONTINUED:
            # Look for screen failure criteria
            if 'eligibility' in text_lower:
                guard = "NOT meets_eligibility_criteria"
        
        # Early termination actions
        if t.to_state == StateType.DISCONTINUED:
            # Look for required procedures
            if 'early termination visit' in text_lower:
                actions.append("Complete Early Termination Visit")
            if 'safety follow-up' in text_lower or '30-day' in text_lower:
                actions.append("Schedule Safety Follow-up")
        
        enhanced.append(StateTransition(
            from_state=t.from_state,
            to_state=t.to_state,
            trigger=t.trigger,
            guard_condition=guard,
            actions=actions if actions else t.actions,
        ))
    
    return enhanced


def _sanitize_key(name: str) -> str:
    """Sanitize a string for use as a JSON object key (no spaces for CDISC engine path traversal)."""
    return name.replace(' ', '_').replace('-', '_')


def _build_from_traversal(
    traversal: TraversalConstraint,
    crossover: Optional[CrossoverDesign] = None,
    existing_epochs: Optional[List[Dict[str, Any]]] = None,
) -> SubjectStateMachine:
    """
    Build state machine from traversal constraints using actual protocol epoch names.
    
    Args:
        traversal: Traversal constraint with required sequence
        crossover: Optional crossover design info
        existing_epochs: List of actual epoch dicts from USDM with 'id' and 'name'
    """
    states = []
    transitions = []
    epoch_ids = {}
    
    # Build epoch ID to name mapping from existing epochs
    epoch_id_to_name = {}
    if existing_epochs:
        for ep in existing_epochs:
            ep_id = ep.get('id', '')
            ep_name = ep.get('name', ep_id)
            epoch_id_to_name[ep_id] = ep_name
            # Also map normalized versions
            epoch_id_to_name[ep_id.lower()] = ep_name
            epoch_id_to_name[ep_id.replace('_', ' ')] = ep_name
    
    # Determine initial state (first in sequence)
    initial_state = "Screening"  # Default
    
    # Build states from required sequence using actual epoch names
    prev_state = None
    for epoch_ref in traversal.required_sequence:
        # Try to resolve to actual epoch name
        state_name = epoch_id_to_name.get(epoch_ref)
        if not state_name:
            # Try case-insensitive lookup
            state_name = epoch_id_to_name.get(epoch_ref.lower())
        if not state_name:
            # Use the epoch ref itself, cleaned up
            state_name = epoch_ref.replace('_', ' ').replace('epoch ', '').title()
        
        # Track epoch ID mapping (sanitize key to avoid spaces breaking CDISC engine path traversal)
        epoch_ids[_sanitize_key(state_name)] = epoch_ref
        
        if state_name not in states:
            states.append(state_name)
        
        # Set initial state from first epoch
        if prev_state is None:
            initial_state = state_name
        
        # Add transition from previous state
        if prev_state and prev_state != state_name:
            transitions.append(StateTransition(
                from_state=prev_state,
                to_state=state_name,
                trigger=f"Progress to {state_name}",
            ))
        prev_state = state_name
    
    # Add exit epochs as terminal states
    terminal_states = []
    for exit_id in (traversal.exit_epoch_ids or []):
        exit_name = epoch_id_to_name.get(exit_id)
        if not exit_name:
            exit_name = exit_id.replace('_', ' ').replace('epoch ', '').title()
        terminal_states.append(exit_name)
        epoch_ids[_sanitize_key(exit_name)] = exit_id
        if exit_name not in states:
            states.append(exit_name)
    
    # Add standard terminal outcomes if not already present
    if "Completed" not in terminal_states and prev_state:
        terminal_states.append("Completed")
    if "Early Termination" not in terminal_states and "Discontinued" not in terminal_states:
        terminal_states.append("Early Termination")
    
    # Add early exit transitions from treatment states
    treatment_states = [s for s in states if any(kw in s.lower() for kw in 
                       ['treatment', 'period', 'dose', 'titration'])]
    for treatment_state in treatment_states:
        for term in terminal_states:
            if term != "Completed":
                transitions.append(StateTransition(
                    from_state=treatment_state,
                    to_state=term,
                    trigger=f"Subject exits to {term}",
                ))
    
    # Handle crossover-specific transitions
    if crossover and crossover.is_crossover:
        # Find washout state if present
        washout_states = [s for s in states if 'washout' in s.lower() or 'wash' in s.lower()]
        period_states = [s for s in states if 'period' in s.lower()]
        
        if washout_states and len(period_states) >= 2:
            # Add crossover transition through washout
            for i, period in enumerate(period_states[:-1]):
                if i < len(washout_states):
                    transitions.append(StateTransition(
                        from_state=period,
                        to_state=washout_states[min(i, len(washout_states)-1)],
                        trigger="Complete period, enter washout",
                    ))
    
    return SubjectStateMachine(
        id="sm_1",
        initial_state=initial_state,
        terminal_states=terminal_states if terminal_states else ["Completed", "Early Termination"],
        states=states,
        transitions=transitions,
        epoch_ids=epoch_ids,
    )


def generate_state_machine(
    pdf_path: str,
    model: str = "gemini-2.5-pro",
    pages: Optional[List[int]] = None,
    traversal: Optional[TraversalConstraint] = None,
    crossover: Optional[CrossoverDesign] = None,
    use_llm: bool = True,
    existing_epochs: Optional[List[Dict[str, Any]]] = None,
) -> ExecutionModelResult:
    """
    Generate subject state machine from protocol PDF.
    
    Args:
        pdf_path: Path to protocol PDF
        model: LLM model to use
        pages: Specific pages to analyze
        traversal: Pre-extracted traversal constraint
        crossover: Pre-extracted crossover design
        use_llm: Whether to use LLM enhancement
        existing_epochs: List of actual epoch dicts from USDM for name resolution
        
    Returns:
        ExecutionModelResult with state machine
    """
    from core.pdf_utils import extract_text_from_pages, get_page_count
    
    logger.info("Starting state machine generation...")
    
    # If we have traversal constraints, build from those
    if traversal:
        sm = _build_from_traversal(traversal, crossover, existing_epochs)
        logger.info(f"Built state machine from traversal: {len(sm.states)} states, {len(sm.transitions)} transitions")
        return ExecutionModelResult(
            success=True,
            data=ExecutionModelData(state_machine=sm),
            pages_used=[],
            model_used=model,
        )
    
    # Otherwise, extract from PDF
    if pages is None:
        pages = find_disposition_pages(pdf_path)
    
    if not pages:
        pages = list(range(min(40, get_page_count(pdf_path))))
    
    logger.info(f"Found {len(pages)} potential disposition pages")
    
    # Extract text
    text = extract_text_from_pages(pdf_path, pages)
    if not text:
        return ExecutionModelResult(
            success=False,
            error="Failed to extract text from PDF",
            pages_used=pages,
            model_used=model,
        )
    
    # Detect states and transitions
    states = _detect_states_from_text(text)
    transitions = _detect_transitions_from_text(text, states)
    transitions = _detect_guard_conditions(text, transitions)
    
    # Create state machine
    sm = SubjectStateMachine(
        id="sm_1",
        initial_state=StateType.SCREENING,
        terminal_states=[s for s in states if s in [
            StateType.COMPLETED, StateType.DISCONTINUED,
            StateType.WITHDRAWN, StateType.DEATH, StateType.LOST_TO_FOLLOW_UP
        ]],
        states=states,
        transitions=transitions,
        source_text=text[:500],
    )
    
    # LLM enhancement
    if use_llm:
        try:
            enhanced = _enhance_with_llm(text, sm, model)
            if enhanced:
                sm = enhanced
        except Exception as e:
            logger.warning(f"LLM enhancement failed: {e}")
    
    logger.info(f"Generated state machine: {len(sm.states)} states, {len(sm.transitions)} transitions")
    
    return ExecutionModelResult(
        success=True,
        data=ExecutionModelData(state_machine=sm),
        pages_used=pages,
        model_used=model,
    )


def _enhance_with_llm(
    text: str,
    state_machine: SubjectStateMachine,
    model: str,
) -> Optional[SubjectStateMachine]:
    """Enhance state machine using LLM."""
    from core.llm_client import call_llm
    
    prompt = f"""Analyze this clinical protocol text and generate a SUBJECT STATE MACHINE.

Identify all possible states a subject can be in during the study:
- SCREENING, ENROLLED, RANDOMIZED, ON_TREATMENT
- COMPLETED, DISCONTINUED, FOLLOW_UP
- WITHDRAWN, LOST_TO_FOLLOW_UP, DEATH

For each transition, identify:
1. From state and to state
2. Trigger event (what causes the transition)
3. Guard condition (if any additional conditions required)
4. Actions to perform during transition

Return JSON:
```json
{{
  "initialState": "Screening",
  "terminalStates": ["Completed", "Discontinued", "Withdrawn", "Death"],
  "states": ["Screening", "Enrolled", "OnTreatment", "Completed", "Discontinued"],
  "transitions": [
    {{
      "fromState": "Screening",
      "toState": "Enrolled",
      "trigger": "Meets all eligibility criteria",
      "guardCondition": null,
      "actions": ["Obtain informed consent", "Assign subject ID"]
    }},
    {{
      "fromState": "OnTreatment",
      "toState": "Discontinued",
      "trigger": "Adverse event",
      "guardCondition": "AE meets discontinuation criteria",
      "actions": ["Complete Early Termination Visit", "Schedule Safety Follow-up"]
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
            extractor_name="state_machine",
        )
        
        # Extract response text from dict
        if isinstance(result, dict):
            if 'error' in result:
                logger.warning(f"LLM call error: {result['error']}")
                return None
            response = result.get('response', '')
        else:
            response = str(result)
        
        if not response:
            return None
        
        # Parse JSON response
        import json
        
        json_match = re.search(r'\{[\s\S]*\}', response)
        if not json_match:
            return None
        
        data = json.loads(json_match.group())
        
        # Convert to StateType enums
        def to_state_type(s: str) -> StateType:
            s_normalized = s.upper().replace(' ', '_').replace('-', '_')
            for st in StateType:
                if st.name == s_normalized or st.value.upper() == s.upper():
                    return st
            return StateType.ON_TREATMENT
        
        # Build state machine
        states = [to_state_type(s) for s in data.get('states', [])]
        terminal = [to_state_type(s) for s in data.get('terminalStates', [])]
        
        transitions = []
        for t_data in data.get('transitions', []):
            transitions.append(StateTransition(
                from_state=to_state_type(t_data.get('fromState', 'Screening')),
                to_state=to_state_type(t_data.get('toState', 'Completed')),
                trigger=t_data.get('trigger', 'Unknown'),
                guard_condition=t_data.get('guardCondition'),
                actions=t_data.get('actions', []),
            ))
        
        return SubjectStateMachine(
            id="sm_1",
            initial_state=to_state_type(data.get('initialState', 'Screening')),
            terminal_states=terminal if terminal else state_machine.terminal_states,
            states=states if states else state_machine.states,
            transitions=transitions if transitions else state_machine.transitions,
        )
        
    except Exception as e:
        logger.warning(f"LLM state machine enhancement failed: {e}")
        return None
