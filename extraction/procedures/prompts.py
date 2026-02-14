"""
LLM Prompts for Procedure and Medical Device extraction.
"""

PROCEDURES_SYSTEM_PROMPT = """You are an expert clinical protocol analyst specializing in extracting 
procedure and medical device information from clinical trial protocols.

Your task is to identify:
1. Clinical procedures performed during the study
2. Medical devices used (drug delivery, diagnostic, monitoring devices)
3. Drug ingredients and their strengths

Return valid JSON only."""

PROCEDURES_USER_PROMPT = """Extract all Procedures, Medical Devices, and Drug Ingredients from the following protocol text.

**Procedures to extract:**
- Sampling procedures (blood draws, biopsies, urine collection)
- Diagnostic procedures (imaging, ECG, endoscopy)
- Therapeutic procedures (infusions, injections)
- Monitoring procedures (vital signs, telemetry)
- Assessment procedures (physical exams, neurological assessments)

**Medical Devices to extract:**
- Drug delivery devices (infusion pumps, autoinjectors, inhalers, syringes)
- Monitoring devices (glucose monitors, ECG devices, wearables)
- Diagnostic devices (spirometers, imaging equipment)
- Venous access devices (cannulas, catheters, IV lines)
- Any specific device mentioned by name or model

**DO NOT classify as medical devices:**
- Drug formulations (tablets, capsules, pills, solutions, suspensions)
- The study drug itself (this is an intervention, not a device)
- Chemical compounds or active ingredients

**Ingredients/Strengths to extract:**
- Active pharmaceutical ingredients
- Excipients if mentioned
- Drug strengths and concentrations

Return JSON in this exact format:
```json
{{
  "procedures": [
    {{
      "id": "proc_1",
      "name": "Venipuncture",
      "label": "Blood Draw",
      "description": "Collection of blood samples for laboratory analysis",
      "procedureType": "Sampling",
      "code": {{
        "code": "C28221",
        "codeSystem": "NCI",
        "decode": "Venipuncture"
      }}
    }},
    {{
      "id": "proc_2",
      "name": "Electrocardiogram",
      "label": "12-lead ECG",
      "description": "Standard 12-lead electrocardiogram",
      "procedureType": "Diagnostic",
      "code": {{
        "code": "C168186",
        "codeSystem": "NCI",
        "decode": "Electrocardiogram"
      }}
    }}
  ],
  "medicalDevices": [
    {{
      "id": "dev_1",
      "name": "Prefilled Syringe",
      "label": "PFS",
      "description": "Prefilled syringe for subcutaneous injection",
      "deviceType": "Drug Delivery Device",
      "manufacturer": "Manufacturer Name",
      "modelNumber": "Model-123"
    }}
  ],
  "deviceIdentifiers": [
    {{
      "id": "dev_id_1",
      "text": "UDI-12345",
      "scopeId": "org_fda"
    }}
  ],
  "ingredients": [
    {{
      "id": "ing_1",
      "name": "Drug Active Ingredient",
      "role": "Active",
      "substanceId": "subst_1"
    }}
  ],
  "strengths": [
    {{
      "id": "str_1",
      "value": 100,
      "unit": "mg",
      "numeratorValue": 100,
      "numeratorUnit": "mg",
      "denominatorValue": 1,
      "denominatorUnit": "mL"
    }}
  ]
}}
```

Valid procedureType values: Diagnostic, Therapeutic, Surgical, Sample Collection, Imaging, Monitoring, Assessment
Valid deviceType values: Drug Delivery Device, Diagnostic Device, Monitoring Device, Implantable Device, Wearable Device
Valid ingredient role values: Active, Inactive, Adjuvant

PROTOCOL TEXT:
{protocol_text}

Extract all procedures, devices, and ingredients mentioned.

**Code priority** (use the FIRST system where you know the code):
1. **NCI C-codes** (preferred) — e.g. C28221 (Venipuncture), C168186 (ECG), C17610 (Biopsy), C38299 (Injection), C16809 (MRI), C17204 (Physical Examination), C62103 (Vital Signs), C49672 (Urinalysis)
2. **ICD-10-PCS / ICD-10-CM** — e.g. R94.31 (Abnormal ECG), Z01.818 (Other preprocedural exam)
3. **SNOMED CT** — e.g. 82078001 (Collection of blood specimen)
4. **CPT** (fallback) — e.g. 36415 (Venipuncture), 93000 (ECG)

Set codeSystem to "NCI", "ICD-10", "SNOMED", or "CPT" accordingly."""


def get_procedures_prompt(protocol_text: str) -> str:
    """Generate the full prompt for procedures extraction."""
    return PROCEDURES_USER_PROMPT.format(protocol_text=protocol_text)


def get_system_prompt() -> str:
    """Get the system prompt for procedures extraction."""
    return PROCEDURES_SYSTEM_PROMPT
