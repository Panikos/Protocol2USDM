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
- Drug delivery devices (infusion pumps, autoinjectors, inhalers)
- Monitoring devices (glucose monitors, ECG devices, wearables)
- Diagnostic devices (spirometers, imaging equipment)
- Any specific device mentioned by name or model

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
        "code": "36415",
        "codeSystem": "CPT",
        "decode": "Collection of venous blood by venipuncture"
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

Extract all procedures, devices, and ingredients mentioned. Include standard medical codes if identifiable."""


def get_procedures_prompt(protocol_text: str) -> str:
    """Generate the full prompt for procedures extraction."""
    return PROCEDURES_USER_PROMPT.format(protocol_text=protocol_text)


def get_system_prompt() -> str:
    """Get the system prompt for procedures extraction."""
    return PROCEDURES_SYSTEM_PROMPT
