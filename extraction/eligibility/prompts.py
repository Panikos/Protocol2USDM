"""
LLM Prompts for Eligibility Criteria Extraction.

These prompts guide the LLM to extract inclusion and exclusion criteria
from protocol Section 4-5.

Output format follows USDM v4.0 OpenAPI schema requirements.
"""

ELIGIBILITY_EXTRACTION_PROMPT = """You are an expert at extracting eligibility criteria from clinical trial protocols.
Your output must conform to USDM v4.0 schema specifications.

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

## USDM v4.0 Output Format (MUST follow exactly)

USDM separates criteria into two linked entities:
1. **EligibilityCriterion** - The criterion with category (Inclusion/Exclusion)
2. **EligibilityCriterionItem** - The reusable text content

Every entity MUST have `id` and `instanceType` fields.

```json
{
  "eligibilityCriteria": [
    {
      "id": "ec_1",
      "name": "Age requirement",
      "identifier": "I1",
      "category": {
        "code": "Inclusion",
        "codeSystem": "http://www.cdisc.org/USDM/criterionCategory",
        "decode": "Inclusion Criterion"
      },
      "criterionItemId": "eci_1",
      "instanceType": "EligibilityCriterion"
    },
    {
      "id": "ec_2",
      "name": "Prior therapy exclusion",
      "identifier": "E1",
      "category": {
        "code": "Exclusion",
        "codeSystem": "http://www.cdisc.org/USDM/criterionCategory",
        "decode": "Exclusion Criterion"
      },
      "criterionItemId": "eci_2",
      "instanceType": "EligibilityCriterion"
    }
  ],
  "eligibilityCriterionItems": [
    {
      "id": "eci_1",
      "name": "Age requirement",
      "text": "Age ≥ 18 years at the time of signing informed consent",
      "instanceType": "EligibilityCriterionItem"
    },
    {
      "id": "eci_2",
      "name": "Prior therapy exclusion",
      "text": "Prior treatment with any investigational agent within 30 days",
      "instanceType": "EligibilityCriterionItem"
    }
  ],
  "population": {
    "id": "pop_1",
    "name": "Study Population",
    "includesHealthySubjects": false,
    "plannedEnrollmentNumber": {
      "maxValue": 200,
      "instanceType": "Range"
    },
    "plannedMinimumAge": "P18Y",
    "plannedMaximumAge": "P75Y",
    "plannedSex": [
      {"code": "Male", "codeSystem": "http://www.cdisc.org/USDM/sex", "decode": "Male"},
      {"code": "Female", "codeSystem": "http://www.cdisc.org/USDM/sex", "decode": "Female"}
    ],
    "criterionIds": ["ec_1", "ec_2"],
    "instanceType": "StudyDesignPopulation"
  }
}
```

## Category Codes
- Inclusion = Inclusion Criterion (who CAN participate)
- Exclusion = Exclusion Criterion (who CANNOT participate)

## ID Linking Pattern
- Each EligibilityCriterion has a `criterionItemId` pointing to its EligibilityCriterionItem
- Use matching IDs: ec_1 → eci_1, ec_2 → eci_2, etc.

## Age Format
- Use ISO 8601 duration: P18Y = 18 years, P6M = 6 months

## Rules

1. **Every entity must have `id` and `instanceType`** - mandatory
2. **Use sequential IDs** - ec_1, ec_2 for criteria; eci_1, eci_2 for items
3. **Link criteria to items** - criterionItemId must match an item's id
4. **Extract exact text** - Copy criterion text verbatim in the item
5. **Use identifier** - Preserve original numbering (I1, E1, 1, 2, etc.)
6. **Maintain order** - Keep criteria in protocol order
7. **Be complete** - Include sub-criteria in the text
8. **Return ONLY valid JSON** - no markdown fences, no explanations

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
