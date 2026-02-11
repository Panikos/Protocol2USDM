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
- Product name (generic name)
- Label / trade name (if different from generic name)
- Dose form (tablet, capsule, injection, etc.)
- Strength (e.g., "15 mg", "100 mg/mL")
- Route of administration (oral, IV, SC, etc.)
- Product designation: "IMP" (investigational) or "NIMP" (non-investigational/auxiliary)
- Sourcing: "Centrally Sourced" or "Locally Sourced" (if mentioned)
- Pharmacologic class (e.g., "Copper Chelator", "Monoclonal Antibody", "PDE4 Inhibitor")
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
      "name": "ABC-1234",
      "role": "Experimental Intervention",
      "type": "Drug",
      "description": "Investigational drug under evaluation"
    },
    {
      "name": "Placebo",
      "role": "Placebo",
      "type": "Drug",
      "description": "Matching placebo tablets"
    },
    {
      "name": "Paracetamol/acetaminophen",
      "role": "Additional Required Treatment",
      "type": "Drug",
      "description": "Permitted for mild pain relief"
    }
  ],
  "products": [
    {
      "name": "ABC-1234 tablets",
      "label": "Xyzomab",
      "doseForm": "Tablet",
      "strength": "100 mg",
      "route": "Oral",
      "productDesignation": "IMP",
      "sourcing": "Centrally Sourced",
      "pharmacologicClass": "Kinase Inhibitor",
      "manufacturer": "Sponsor Pharmaceuticals"
    }
  ],
  "substances": [
    {
      "name": "abcizumab",
      "description": "Active pharmaceutical ingredient"
    }
  ],
  "administrations": [
    {
      "name": "ABC-1234 100 mg daily",
      "dose": "100 mg",
      "frequency": "once daily",
      "route": "Oral",
      "duration": "24 weeks"
    },
    {
      "name": "ABC-1234 200 mg daily",
      "dose": "200 mg",
      "frequency": "once daily",
      "route": "Oral",
      "duration": "After Week 4"
    }
  ],
  "devices": []
}
```

## Rules

1. **Extract from IP section** - Usually Section 5 or 6 (Investigational Product)
2. **Include all dosing regimens** - Different doses, titration steps, dose escalation
3. **Extract concomitant medications** - Look in "Concomitant Medications" or "Prior and Concomitant Therapy" sections for permitted/prohibited medications
4. **Use CDISC USDM controlled terminology** (exact values required):
   - Roles (USDM CT C207417): "Experimental Intervention", "Active Comparator", "Placebo", "Rescue Medicine", "Additional Required Treatment", "Background Treatment", "Challenge Agent", "Diagnostic"
   - Types (ICH M11): "Drug", "Biological", "Device", "Dietary Supplement", "Procedure", "Radiation", "Other"
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
