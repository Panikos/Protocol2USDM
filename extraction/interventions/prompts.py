"""
LLM Prompts for Interventions & Products Extraction.

These prompts guide the LLM to extract study interventions and products
from protocol investigational product sections.
"""

INTERVENTIONS_EXTRACTION_PROMPT = """You are an expert at extracting study intervention information from clinical trial protocols.

Analyze the provided protocol section and extract ALL study interventions, products, and administration details.

## Required Information

### 1. Study Interventions
- Investigational product(s)
- Comparator(s) (active, placebo)
- Rescue medications (if specified)
- Background therapy (if specified)
- Concomitant medications (permitted/prohibited/required)
- Prior medications that must be washed out

### 2. Products (AdministrableProduct)
For each product extract:
- Product name (generic and/or trade name)
- Dose form (tablet, capsule, injection, etc.)
- Strength (e.g., "15 mg", "100 mg/mL")
- Manufacturer (if mentioned)

### 3. Active Substances
- Generic name of active ingredient
- Substance codes if available (UNII, CAS)

### 4. Administration Details
- Dose (e.g., "15 mg", "100 mg/m2")
- Frequency (e.g., "once daily", "every 2 weeks")
- Route (oral, IV, SC, IM, etc.)
- Duration of treatment

### 5. Medical Devices (if applicable)
- Device name
- Manufacturer
- Purpose

## Output Format

Return a JSON object with this exact structure:

```json
{
  "interventions": [
    {
      "name": "ALXN1840",
      "role": "Investigational Product",
      "description": "Investigational product for Wilson disease"
    },
    {
      "name": "Placebo",
      "role": "Placebo",
      "description": "Matching placebo tablets"
    },
    {
      "name": "Paracetamol/acetaminophen",
      "role": "Concomitant Medication",
      "description": "Permitted for mild pain relief"
    }
  ],
  "products": [
    {
      "name": "ALXN1840 tablets",
      "doseForm": "Tablet",
      "strength": "15 mg",
      "manufacturer": "Alexion Pharmaceuticals"
    }
  ],
  "substances": [
    {
      "name": "bis-choline tetrathiomolybdate",
      "description": "Active pharmaceutical ingredient"
    }
  ],
  "administrations": [
    {
      "name": "ALXN1840 15 mg daily",
      "dose": "15 mg",
      "frequency": "once daily",
      "route": "Oral",
      "duration": "24 weeks"
    },
    {
      "name": "ALXN1840 30 mg daily",
      "dose": "30 mg",
      "frequency": "once daily",
      "route": "Oral",
      "duration": "After Day 29"
    }
  ],
  "devices": []
}
```

## Rules

1. **Extract from IP section** - Usually Section 5 or 6 (Investigational Product)
2. **Include all dosing regimens** - Different doses, titration steps, dose escalation
3. **Extract concomitant medications** - Look in "Concomitant Medications" or "Prior and Concomitant Therapy" sections for permitted/prohibited medications
4. **Use standard terminology**:
   - Roles: "Investigational Product", "Comparator", "Placebo", "Rescue Medication", "Concomitant Medication", "Background Therapy"
   - Routes: "Oral", "Intravenous", "Subcutaneous", "Intramuscular", "Topical", "Inhalation"
   - Forms: "Tablet", "Capsule", "Solution", "Injection", "Cream", "Patch"
5. **Be precise with doses** - Include units (mg, mg/kg, mg/m2, etc.)
6. **Return ONLY valid JSON** - no markdown, no explanations

Now analyze the protocol content and extract the interventions:
"""


INTERVENTIONS_PAGE_FINDER_PROMPT = """Analyze these PDF pages and identify which pages contain intervention/product information.

Look for pages that contain:
1. **Investigational Product section** - Usually Section 5 or 6
2. **Study Treatment section**
3. **Dose and Administration section**
4. **Product description/formulation**
5. **Concomitant Medications section** - Permitted/prohibited medications
6. **Prior and Concomitant Therapy section**

Return a JSON object:
```json
{
  "intervention_pages": [page_numbers],
  "confidence": "high/medium/low",
  "notes": "any relevant observations"
}
```

Pages are 0-indexed. Return ONLY valid JSON.
"""


def build_interventions_extraction_prompt(protocol_text: str, context_hints: str = "") -> str:
    """Build the full extraction prompt with protocol content and optional context hints."""
    prompt = INTERVENTIONS_EXTRACTION_PROMPT
    if context_hints:
        prompt += f"\n\nCONTEXT FROM PRIOR EXTRACTION:{context_hints}"
    prompt += f"\n\n---\n\nPROTOCOL CONTENT:\n\n{protocol_text}"
    return prompt


def build_page_finder_prompt() -> str:
    """Build prompt for finding intervention pages."""
    return INTERVENTIONS_PAGE_FINDER_PROMPT
