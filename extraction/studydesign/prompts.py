"""
LLM Prompts for Study Design Structure Extraction.

These prompts guide the LLM to extract study design elements
from protocol synopsis and study design sections.
"""

STUDY_DESIGN_EXTRACTION_PROMPT = """You are an expert at extracting study design information from clinical trial protocols.

Analyze the provided protocol section and extract the study design structure.

## Required Information

### 1. Study Design Type
- Is this Interventional or Observational?
- If Interventional: Treatment, Prevention, Diagnostic, Supportive Care, Screening, Health Services Research, Basic Science?

### 1a. Design Rationale
- Extract the scientific rationale for the chosen study design (usually 1-3 sentences from §4 or Synopsis)
- Why was this particular design chosen? (e.g., "A randomized, double-blind design was chosen to minimize bias...")

### 1b. Design Characteristics
- Extract study design characteristics: Parallel, Crossover, Factorial, Single Group, Adaptive, Basket, Umbrella, Platform, Sequential, etc.
- Multiple characteristics may apply (e.g., ["Parallel", "Adaptive"])

### 2. Blinding
- Open Label, Single Blind, Double Blind, Triple Blind, or Quadruple Blind?
- Who is blinded? (Subject, Investigator, Outcome Assessor, Caregiver, Data Analyst)

### 3. Randomization
- Randomized or Non-Randomized?
- Allocation ratio (e.g., 1:1, 2:1, 1:1:1)
- Stratification factors (e.g., age, disease severity, site)

### 4. Control Type
- Placebo, Active Control, Dose Comparison, No Treatment, Historical Control?

### 5. Study Arms
Extract treatment arms - but DISTINGUISH between:
- **Parallel Arms**: Different treatments given to DIFFERENT subjects (e.g., Drug A vs Placebo)
- **Within-Subject Titration**: Same subjects receive sequential doses (e.g., 15mg for 4 weeks, then titrated to 30mg)

**CRITICAL**: If the protocol describes dose escalation/titration where ALL subjects start at one dose and increase to another:
- This is NOT two separate arms
- Model as ONE arm with "isTitration": true and "doseEpochs" array
- Look for phrases: "titrated up", "dose escalation", "following X period", "after Day X increase"

For each arm extract:
- Arm name
- Arm type (Experimental, Active Comparator, Placebo Comparator, No Intervention)
- Description
- isTitration (true/false)
- doseEpochs (if titration): [{dose, startDay, endDay}]

### 6. Study Cohorts (if any)
Sub-populations within the study (NOT dose levels):
- Cohort name
- Defining characteristic (e.g., treatment-naive vs experienced)

### 7. Study Phases/Epochs (if described)
- Screening, Treatment, Follow-up, etc.
- For titration studies, include dose-level epochs (e.g., "15mg Treatment", "30mg Treatment")

### 8. Therapeutic Areas
Classify the study into one or more therapeutic areas based on the disease/condition, study drug, and medical specialty.
Pick ONLY from this list (use exact spelling):
- Oncology, Cardiovascular, Endocrinology & Metabolism, Neurology, Psychiatry
- Infectious Disease, Immunology & Inflammation, Respiratory, Gastroenterology
- Nephrology, Dermatology, Hematology, Ophthalmology, Musculoskeletal
- Hepatology, Urology, Rheumatology, Rare Diseases, Vaccines, Pain
- Gynecology & Obstetrics

Multiple areas may apply (e.g., a rare hematologic disease → ["Hematology", "Rare Diseases"]).

## Output Format

Return a JSON object with this exact structure:

```json
{
  "studyDesign": {
    "type": "Interventional",
    "trialIntentTypes": ["Treatment"],
    "blinding": {
      "schema": "Open Label",
      "maskedRoles": []
    },
    "randomization": {
      "type": "Non-Randomized",
      "allocationRatio": null,
      "stratificationFactors": []
    },
    "controlType": null,
    "therapeuticAreas": ["Cardiovascular"],
    "designRationale": "An open-label, single-arm design was chosen because the primary objective is to evaluate the pharmacokinetics and safety profile of ABC-1234 in this population.",
    "characteristics": ["Single Group"]
  },
  "arms": [
    {
      "name": "ABC-1234 Treatment",
      "type": "Experimental Arm",
      "description": "All participants receive ABC-1234 with dose titration from 50mg to 100mg",
      "isTitration": true,
      "doseEpochs": [
        {"dose": "50 mg/day", "startDay": 1, "endDay": 28, "description": "Initial dose period"},
        {"dose": "100 mg/day", "startDay": 29, "endDay": null, "description": "Titrated dose period"}
      ]
    }
  ],
  "cohorts": [
    {
      "name": "Treatment-naive",
      "characteristic": "Participants who have not received prior therapy for this condition"
    },
    {
      "name": "Previously treated",
      "characteristic": "Participants with prior standard-of-care therapy"
    }
  ],
  "epochs": [
    {"name": "Screening", "description": "Up to 28 days"},
    {"name": "Low-Dose Treatment", "description": "Days 1-28, initial dose"},
    {"name": "Full-Dose Treatment", "description": "Day 29 onwards, titrated dose"},
    {"name": "Follow-up", "description": "4 weeks after last dose"}
  ]
}
```

### Example 2: Parallel Arms (for comparison)
If the study randomizes subjects to DIFFERENT doses (not titration):
```json
{
  "arms": [
    {
      "name": "Low Dose Arm",
      "type": "Experimental Arm", 
      "description": "Randomized to receive 15mg for entire study",
      "isTitration": false
    },
    {
      "name": "High Dose Arm",
      "type": "Experimental Arm",
      "description": "Randomized to receive 30mg for entire study", 
      "isTitration": false
    }
  ]
}
```

## Rules

1. **Extract from design section** - Usually Section 3 or Synopsis
2. **Classify arms correctly** - Experimental vs Comparator based on study drug vs control
3. **Identify cohorts** - Sub-groups based on prior treatment, disease severity, etc.
4. **Use standard terminology** - Use USDM-compliant codes where possible
5. **CRITICAL: Detect titration** - If ALL subjects go through sequential doses, use ONE arm with isTitration=true
6. **Return ONLY valid JSON** - no markdown, no explanations

Now analyze the protocol content and extract the study design:
"""


DESIGN_PAGE_FINDER_PROMPT = """Analyze these PDF pages and identify which pages contain study design information.

Look for pages that contain:
1. **Synopsis** - Usually has study design overview table
2. **Study Design section** - Usually Section 3
3. **Randomization/Blinding description**
4. **Treatment arms description**

Return a JSON object:
```json
{
  "design_pages": [page_numbers],
  "synopsis_page": page_number,
  "confidence": "high/medium/low",
  "notes": "any relevant observations"
}
```

Pages are 0-indexed. Return ONLY valid JSON.
"""


def build_study_design_extraction_prompt(protocol_text: str, context_hints: str = "") -> str:
    """Build the full extraction prompt with protocol content and optional context hints."""
    prompt = STUDY_DESIGN_EXTRACTION_PROMPT
    if context_hints:
        prompt += f"\n\nCONTEXT FROM PRIOR EXTRACTION:{context_hints}"
    prompt += f"\n\n---\n\nPROTOCOL CONTENT:\n\n{protocol_text}"
    return prompt


def build_page_finder_prompt() -> str:
    """Build prompt for finding study design pages."""
    return DESIGN_PAGE_FINDER_PROMPT
