"""
LLM Prompts for Objectives & Endpoints Extraction.

These prompts guide the LLM to extract study objectives and endpoints
from protocol synopsis and objectives sections.

Output format follows USDM v4.0 OpenAPI schema requirements.
"""

OBJECTIVES_EXTRACTION_PROMPT = """You are an expert at extracting study objectives and endpoints from clinical trial protocols.
Your output must conform to USDM v4.0 schema specifications.

Analyze the provided protocol section and extract ALL objectives and their associated endpoints.

## Required Information

### 1. Study Objectives (by level)
- **Primary**: Main purpose of the study
- **Secondary**: Additional goals (safety, tolerability, etc.)
- **Exploratory**: Hypothesis-generating objectives

### 2. Endpoints (matched to objectives)
- **Primary**: Main outcome measures
- **Secondary**: Supporting outcome measures  
- **Exploratory**: Additional measures

### 3. Estimands (if ICH E9(R1) format described)

## USDM v4.0 Output Format (MUST follow exactly)

Every entity MUST have `id` and `instanceType` fields.
Use Code objects for level/purpose fields.

```json
{
  "objectives": [
    {
      "id": "obj_1",
      "name": "Primary Efficacy Objective",
      "text": "To evaluate the efficacy of Drug X compared to placebo in reducing disease severity",
      "level": {
        "code": "Primary",
        "codeSystem": "http://www.cdisc.org/USDM/objectiveLevel",
        "decode": "Primary Objective"
      },
      "endpointIds": ["ep_1"],
      "instanceType": "Objective"
    },
    {
      "id": "obj_2",
      "name": "Safety Objective",
      "text": "To evaluate the safety and tolerability of Drug X",
      "level": {
        "code": "Secondary",
        "codeSystem": "http://www.cdisc.org/USDM/objectiveLevel",
        "decode": "Secondary Objective"
      },
      "endpointIds": ["ep_2", "ep_3"],
      "instanceType": "Objective"
    }
  ],
  "endpoints": [
    {
      "id": "ep_1",
      "name": "Primary Efficacy Endpoint",
      "text": "Change from baseline in disease severity score at Week 12",
      "level": {
        "code": "Primary",
        "codeSystem": "http://www.cdisc.org/USDM/endpointLevel",
        "decode": "Primary Endpoint"
      },
      "purpose": "Efficacy",
      "instanceType": "Endpoint"
    },
    {
      "id": "ep_2",
      "name": "Adverse Events",
      "text": "Incidence and severity of treatment-emergent adverse events",
      "level": {
        "code": "Secondary",
        "codeSystem": "http://www.cdisc.org/USDM/endpointLevel",
        "decode": "Secondary Endpoint"
      },
      "purpose": "Safety",
      "instanceType": "Endpoint"
    }
  ],
  "estimands": [
    {
      "id": "est_1",
      "name": "Primary Estimand",
      "text": "Treatment effect on disease severity in ITT population",
      "intercurrentEvents": [
        {
          "id": "ice_1",
          "name": "Treatment discontinuation",
          "strategy": {
            "code": "TreatmentPolicy",
            "codeSystem": "http://www.cdisc.org/USDM/strategy",
            "decode": "Treatment Policy"
          },
          "instanceType": "IntercurrentEvent"
        }
      ],
      "instanceType": "Estimand"
    }
  ]
}
```

## Level Codes
- Primary = Primary (main objective/endpoint)
- Secondary = Secondary (supporting)
- Exploratory = Exploratory (hypothesis-generating)

## Purpose Values
- Efficacy, Safety, Tolerability, Pharmacokinetic, Pharmacodynamic, Biomarker, QualityOfLife

## ID Linking Pattern
- Objectives reference endpoints via `endpointIds` array
- Use matching patterns: obj_1 → ep_1, obj_2 → ep_2, ep_3

## Rules

1. **Every entity must have `id` and `instanceType`** - mandatory
2. **Use sequential IDs** - obj_1, obj_2; ep_1, ep_2; est_1, etc.
3. **Link objectives to endpoints** - endpointIds must match endpoint ids
4. **Extract exact text** - Copy verbatim from protocol
5. **Classify by level** - Primary, Secondary, Exploratory
6. **Be complete** - Extract ALL objectives and endpoints
7. **Return ONLY valid JSON** - no markdown fences, no explanations

Now analyze the protocol content and extract the objectives and endpoints:
"""


OBJECTIVES_PAGE_FINDER_PROMPT = """Analyze these PDF pages and identify which pages contain study objectives and endpoints.

Look for pages that contain:
1. **Synopsis** - Often has objectives and endpoints summary table
2. **Objectives section** - Usually Section 2 or 3
3. **Endpoints section** - May be combined with objectives or separate
4. **Statistical considerations** - May contain estimand framework

Return a JSON object:
```json
{
  "objectives_pages": [page_numbers],
  "synopsis_page": page_number,
  "endpoints_pages": [page_numbers],
  "confidence": "high/medium/low",
  "notes": "any relevant observations"
}
```

Pages are 0-indexed. Return ONLY valid JSON.
"""


def build_objectives_extraction_prompt(protocol_text: str, context_hints: str = "") -> str:
    """Build the full extraction prompt with protocol content and optional context hints."""
    prompt = OBJECTIVES_EXTRACTION_PROMPT
    if context_hints:
        prompt += f"\n\nCONTEXT FROM PRIOR EXTRACTION:{context_hints}"
    prompt += f"\n\n---\n\nPROTOCOL CONTENT:\n\n{protocol_text}"
    return prompt


def build_page_finder_prompt() -> str:
    """Build prompt for finding objectives pages."""
    return OBJECTIVES_PAGE_FINDER_PROMPT
