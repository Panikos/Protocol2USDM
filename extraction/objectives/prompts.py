"""
LLM Prompts for Objectives & Endpoints Extraction.

Split into two focused phases for improved reliability:
1. OBJECTIVES_ENDPOINTS_PROMPT - Extract objectives and endpoints (core, always succeeds)
2. ESTIMANDS_PROMPT - Extract estimands with endpoint context (enhancement phase)

This separation improves reliability by:
- Reducing prompt complexity and output size
- Ensuring core objectives/endpoints always extract successfully
- Allowing estimands to reference already-extracted endpoint IDs
- Making each prompt easier to tune independently

Output format follows USDM v4.0 OpenAPI schema requirements.
"""

# =============================================================================
# PHASE 1: Objectives & Endpoints (Core extraction - always runs)
# =============================================================================

OBJECTIVES_ENDPOINTS_PROMPT = """You are an expert at extracting study objectives and endpoints from clinical trial protocols.
Extract ALL objectives and their associated endpoints. Output must conform to USDM v4.0 schema.

## Study Objectives (by level)
- **Primary**: Main purpose of the study
- **Secondary**: Additional goals (safety, tolerability, etc.)
- **Exploratory**: Hypothesis-generating objectives

## Endpoints (matched to objectives)
- **Primary**: Main outcome measures for primary objectives
- **Secondary**: Supporting outcome measures
- **Exploratory**: Additional exploratory measures

## USDM v4.0 Output Format

```json
{
  "objectives": [
    {
      "id": "obj_1",
      "name": "Primary Efficacy Objective",
      "text": "To evaluate the efficacy of Drug X compared to placebo",
      "level": {"code": "Primary", "codeSystem": "http://www.cdisc.org/USDM/objectiveLevel", "decode": "Primary Objective"},
      "endpointIds": ["ep_1"],
      "instanceType": "Objective"
    }
  ],
  "endpoints": [
    {
      "id": "ep_1",
      "name": "Primary Efficacy Endpoint",
      "text": "Change from baseline in disease severity score at Week 12",
      "level": {"code": "Primary", "codeSystem": "http://www.cdisc.org/USDM/endpointLevel", "decode": "Primary Endpoint"},
      "purpose": "Efficacy",
      "instanceType": "Endpoint"
    }
  ]
}
```

## Level Codes
- Primary, Secondary, Exploratory

## Purpose Values
- Efficacy, Safety, Tolerability, Pharmacokinetic, Pharmacodynamic, Biomarker, QualityOfLife

## Rules
1. Every entity MUST have `id` and `instanceType`
2. Use sequential IDs: obj_1, obj_2; ep_1, ep_2
3. Link objectives to endpoints via `endpointIds` array
4. Extract exact text verbatim from protocol
5. Classify correctly by level
6. Be complete - extract ALL objectives and endpoints
7. Return ONLY valid JSON - no markdown, no explanations

Now extract objectives and endpoints from the protocol:
"""

# =============================================================================
# PHASE 2: Estimands (Enhancement - runs after objectives/endpoints)
# =============================================================================

ESTIMANDS_PROMPT = """You are an expert at extracting estimands from clinical trial protocols using the ICH E9(R1) framework.

## Previously Extracted Endpoints
{endpoints_context}

## ICH E9(R1) Estimand Framework

An estimand precisely describes the treatment effect. Extract these five attributes:

1. **Treatment** - Intervention AND comparator (e.g., "Drug X 100mg vs Placebo")
2. **Population** - Target patients (e.g., "Adults with moderate-to-severe disease")
3. **Variable** - The endpoint being measured (reference endpoint ID from above)
4. **Intercurrent Events** - Events affecting interpretation:
   - Treatment discontinuation
   - Rescue medication use
   - Death
   - Treatment switching
5. **Summary Measure** - How effect is summarized (difference in means, hazard ratio, odds ratio, etc.)

## Intercurrent Event Strategies
- **Treatment Policy** - Include all data regardless of event
- **Composite** - Event becomes part of outcome
- **Hypothetical** - Estimate as if event hadn't occurred
- **Principal Stratum** - Subset who wouldn't experience event
- **While on Treatment** - Only data while on treatment

## Output Format

```json
{{
  "estimands": [
    {{
      "id": "est_1",
      "name": "Primary Efficacy Estimand",
      "population": "Adult patients meeting eligibility criteria (ITT population)",
      "treatment": "Drug X 100mg daily vs Placebo",
      "variableOfInterest": "Change from baseline in severity score",
      "endpointId": "ep_1",
      "summaryMeasure": "Difference in least squares means",
      "intercurrentEvents": [
        {{
          "id": "ice_1",
          "name": "Treatment discontinuation",
          "text": "Subject discontinues treatment before Week 12",
          "strategy": "Treatment Policy",
          "instanceType": "IntercurrentEvent"
        }}
      ],
      "instanceType": "Estimand"
    }}
  ]
}}
```

## Rules
1. Link to existing endpoint IDs from Phase 1
2. Extract at least one estimand for each primary endpoint
3. Include common intercurrent events even if not explicit
4. Return ONLY valid JSON

Now extract estimands from the protocol:
"""

# =============================================================================
# Legacy prompt (kept for backward compatibility)
# =============================================================================

OBJECTIVES_EXTRACTION_PROMPT = OBJECTIVES_ENDPOINTS_PROMPT

# =============================================================================
# Page finder prompt
# =============================================================================

OBJECTIVES_PAGE_FINDER_PROMPT = """Identify pages containing study objectives and endpoints.

Look for:
1. **Synopsis** - Objectives/endpoints summary table
2. **Objectives section** - Usually Section 2 or 3
3. **Endpoints section** - May be combined or separate
4. **Statistical considerations** - May contain estimand framework

Return JSON:
```json
{
  "objectives_pages": [page_numbers],
  "synopsis_page": page_number,
  "endpoints_pages": [page_numbers],
  "confidence": "high/medium/low"
}
```

Pages are 0-indexed. Return ONLY valid JSON.
"""


# =============================================================================
# Prompt builders
# =============================================================================

def build_objectives_extraction_prompt(protocol_text: str, context_hints: str = "") -> str:
    """Build prompt for Phase 1: objectives and endpoints extraction."""
    prompt = OBJECTIVES_ENDPOINTS_PROMPT
    if context_hints:
        prompt += f"\n\nCONTEXT FROM PRIOR EXTRACTION:{context_hints}"
    prompt += f"\n\n---\n\nPROTOCOL CONTENT:\n\n{protocol_text}"
    return prompt


def build_estimands_prompt(protocol_text: str, endpoints: list, context_hints: str = "") -> str:
    """Build prompt for Phase 2: estimands extraction with endpoint context."""
    # Format endpoints for context
    if endpoints:
        endpoints_lines = []
        for ep in endpoints:
            ep_id = ep.get('id', 'unknown')
            ep_name = ep.get('name', '')
            ep_text = ep.get('text', '')[:100]  # Truncate for brevity
            level = ep.get('level', {})
            level_code = level.get('code', '') if isinstance(level, dict) else str(level)
            endpoints_lines.append(f"- {ep_id}: [{level_code}] {ep_name} - {ep_text}")
        endpoints_context = "\n".join(endpoints_lines)
    else:
        endpoints_context = "No endpoints extracted yet."
    
    prompt = ESTIMANDS_PROMPT.format(endpoints_context=endpoints_context)
    if context_hints:
        prompt += f"\n\nADDITIONAL CONTEXT:{context_hints}"
    prompt += f"\n\n---\n\nPROTOCOL CONTENT:\n\n{protocol_text}"
    return prompt


def build_page_finder_prompt() -> str:
    """Build prompt for finding objectives pages."""
    return OBJECTIVES_PAGE_FINDER_PROMPT
