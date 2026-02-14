"""
LLM Prompts for Scheduling Logic extraction.
"""

SCHEDULING_SYSTEM_PROMPT = """You are an expert clinical protocol analyst specializing in study timing, 
visit windows, and protocol decision logic.

Your task is to extract:
1. Timing constraints (visit windows, intervals between visits)
2. Transition rules (criteria for moving between study phases)
3. Conditions for branching or adaptive designs
4. Early termination and discontinuation criteria

Return valid JSON only."""

SCHEDULING_USER_PROMPT = """Extract all Scheduling Logic from the following protocol text.

**Timing to extract:**
- Visit windows (e.g., "Day 1 ± 3 days")
- Intervals between visits (e.g., "4 weeks after previous visit")
- Time relative to events (e.g., "within 7 days of screening")

**Transition Rules to extract:**
- Criteria for epoch transitions (e.g., screening to treatment)
- Discontinuation criteria
- Rescue therapy rules
- Dose modification triggers

**Conditions to extract:**
- Eligibility conditions beyond inclusion/exclusion
- Response-based decisions
- Safety stopping rules
- Interim analysis conditions

**Schedule Exits to extract:**
- Early termination criteria
- Study completion criteria
- Protocol deviations leading to exit

Return JSON in this exact format:
```json
{{
  "timings": [
    {{
      "id": "timing_1",
      "name": "Screening Window",
      "timingType": "Within",
      "value": 28,
      "unit": "days",
      "relativeTo": "Randomization",
      "windowLower": -28,
      "windowUpper": -1
    }},
    {{
      "id": "timing_2",
      "name": "Week 4 Visit Window",
      "timingType": "At",
      "value": 28,
      "unit": "days",
      "relativeTo": "Randomization",
      "windowLower": -3,
      "windowUpper": 3
    }}
  ],
  "conditions": [
    {{
      "id": "cond_1",
      "name": "Response Criteria",
      "description": "Criteria for determining treatment response",
      "text": "50% reduction in primary endpoint from baseline"
    }}
  ],
  "transitionRules": [
    {{
      "id": "trans_1",
      "name": "Screen to Treatment Transition",
      "transitionType": "Epoch Transition",
      "fromElementId": "epoch_screening",
      "toElementId": "epoch_treatment",
      "text": "Subject must meet all eligibility criteria"
    }},
    {{
      "id": "trans_2",
      "name": "Discontinuation for Safety",
      "transitionType": "Discontinuation",
      "text": "ALT > 5x ULN requires treatment discontinuation"
    }}
  ],
  "scheduleExits": [
    {{
      "id": "exit_1",
      "name": "Early Termination",
      "exitType": "Early Termination",
      "description": "Subject may discontinue for any reason"
    }},
    {{
      "id": "exit_2",
      "name": "Study Completion",
      "exitType": "Completion",
      "description": "Completion of all protocol-required visits"
    }}
  ],
  "decisionInstances": [
    {{
      "id": "dec_1",
      "name": "Response Assessment Decision",
      "timepointId": "pt_week12",
      "conditionIds": ["cond_1"],
      "description": "Decision point for response-based continuation"
    }}
  ]
}}
```

Valid timingType values: Before, After, Within, At, Between
Valid relativeTo values: Study Start, Randomization, First Dose, Last Dose, Previous Visit, Screening, Baseline, End of Treatment
Valid transitionType values: Epoch Transition, Arm Transition, Discontinuation, Early Termination, Rescue Therapy, Dose Modification

PROTOCOL TEXT:
{protocol_text}

Extract all timing constraints, conditions, and transition rules. Focus on quantitative timing information."""


def get_scheduling_prompt(protocol_text: str, upstream_context: str = None) -> str:
    """Generate the full prompt for scheduling extraction.
    
    Args:
        protocol_text: Raw protocol text to extract from.
        upstream_context: Optional context from upstream phases (epochs, encounters, arms)
            to ground the LLM and prevent hallucinated entity names.
    """
    prompt = SCHEDULING_USER_PROMPT.format(protocol_text=protocol_text)
    if upstream_context:
        context_block = (
            "\n\n## Already-Extracted Study Context (use these exact names)\n"
            "The following entities have already been extracted from this protocol. "
            "When referencing epochs, visits, or arms in your timings and transition rules, "
            "use these exact names rather than inventing new ones.\n\n"
            f"{upstream_context}\n"
        )
        prompt = context_block + prompt
    return prompt


def get_system_prompt() -> str:
    """Get the system prompt for scheduling extraction."""
    return SCHEDULING_SYSTEM_PROMPT
