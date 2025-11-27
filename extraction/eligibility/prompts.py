"""
LLM Prompts for Eligibility Criteria Extraction.

These prompts guide the LLM to extract inclusion and exclusion criteria
from protocol Section 4-5.
"""

ELIGIBILITY_EXTRACTION_PROMPT = """You are an expert at extracting eligibility criteria from clinical trial protocols.

Analyze the provided protocol section and extract ALL inclusion and exclusion criteria.

## Required Information

### 1. Inclusion Criteria
Extract every inclusion criterion. These typically:
- Start with "Participants must..." or "Eligible participants..."
- Are numbered (1, 2, 3... or I1, I2, I3...)
- Define who CAN participate in the study

### 2. Exclusion Criteria
Extract every exclusion criterion. These typically:
- Start with "Participants must not..." or "Excluded if..."
- Are numbered (1, 2, 3... or E1, E2, E3...)
- Define who CANNOT participate in the study

### 3. Population Information (if available)
- Target enrollment number
- Age range (minimum/maximum)
- Sex/Gender requirements
- Whether healthy volunteers are included

## Output Format

Return a JSON object with this exact structure:

```json
{
  "inclusionCriteria": [
    {
      "identifier": "I1",
      "text": "Full text of the criterion exactly as written",
      "name": "Short descriptive name (optional)"
    },
    {
      "identifier": "I2",
      "text": "..."
    }
  ],
  "exclusionCriteria": [
    {
      "identifier": "E1",
      "text": "Full text of the criterion exactly as written",
      "name": "Short descriptive name (optional)"
    }
  ],
  "population": {
    "plannedEnrollment": 100,
    "minimumAge": "18 years",
    "maximumAge": "75 years",
    "sex": ["Male", "Female"],
    "includesHealthySubjects": false
  }
}
```

## Rules

1. **Extract exact text** - Copy criterion text verbatim, preserving numbering and formatting
2. **Maintain order** - Keep criteria in the order they appear in the protocol
3. **Be complete** - Extract ALL criteria, including sub-criteria (e.g., 1a, 1b)
4. **Use identifiers** - Use "I1", "I2" for inclusion; "E1", "E2" for exclusion
5. **Preserve sub-items** - If a criterion has sub-parts, include them all in the text
6. **Handle notes** - Include any notes or clarifications that are part of a criterion
7. **Age format** - Use natural language like "18 years", "6 months", etc.
8. **Return ONLY valid JSON** - no markdown, no explanations

Now analyze the protocol content and extract the eligibility criteria:
"""


ELIGIBILITY_PAGE_FINDER_PROMPT = """Analyze these PDF pages and identify which pages contain eligibility criteria.

Look for pages that contain:
1. **Inclusion Criteria section** - Usually labeled "Inclusion Criteria" or "Eligibility - Inclusion"
2. **Exclusion Criteria section** - Usually labeled "Exclusion Criteria" or "Eligibility - Exclusion"
3. **Study Population section** - May contain eligibility information

These are typically found in:
- Section 4: Study Population
- Section 5: Eligibility Criteria
- Synopsis section (summary of I/E criteria)

Return a JSON object:
```json
{
  "eligibility_pages": [page_numbers],
  "inclusion_start_page": page_number,
  "exclusion_start_page": page_number,
  "confidence": "high/medium/low",
  "notes": "any relevant observations"
}
```

Pages are 0-indexed. Return ONLY valid JSON.
"""


def build_eligibility_extraction_prompt(protocol_text: str) -> str:
    """Build the full extraction prompt with protocol content."""
    return f"{ELIGIBILITY_EXTRACTION_PROMPT}\n\n---\n\nPROTOCOL CONTENT:\n\n{protocol_text}"


def build_page_finder_prompt() -> str:
    """Build prompt for finding eligibility pages."""
    return ELIGIBILITY_PAGE_FINDER_PROMPT
