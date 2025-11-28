"""
LLM Prompts for Amendment Details extraction.
Phase 13: StudyAmendmentImpact, StudyAmendmentReason, StudyChange
"""

AMENDMENTS_SYSTEM_PROMPT = """You are an expert clinical protocol analyst specializing in protocol amendments and change tracking.

Your task is to extract:
1. Which sections/entities are impacted by amendments
2. Reasons for the amendments
3. Specific before/after changes

Return valid JSON only."""

AMENDMENTS_USER_PROMPT = """Extract Amendment Details from the following protocol text.

**Amendment Impacts to extract:**
- Which sections were modified (e.g., "Section 5.2 - Exclusion Criteria")
- Level of impact (Major, Minor, Administrative)
- Which study elements are affected

**Amendment Reasons to extract:**
- Rationale for each change
- Category (Safety, Efficacy, Regulatory, Operational, Scientific, Administrative)
- Whether it's the primary reason for the amendment

**Study Changes to extract:**
- Specific text that was changed
- Before and after text where available
- Type of change (Addition, Deletion, Modification, Clarification)

Return JSON in this exact format:
```json
{{
  "impacts": [
    {{
      "id": "impact_1",
      "amendmentId": "amend_1",
      "affectedSection": "Section 5.2 - Exclusion Criteria",
      "impactLevel": "Minor",
      "description": "Clarified exclusion criterion regarding hepatic impairment"
    }}
  ],
  "reasons": [
    {{
      "id": "reason_1",
      "amendmentId": "amend_1",
      "reasonText": "Regulatory authority feedback requested clarification of hepatic impairment criteria",
      "category": "Regulatory",
      "isPrimary": true
    }}
  ],
  "changes": [
    {{
      "id": "change_1",
      "amendmentId": "amend_1",
      "changeType": "Modification",
      "sectionNumber": "5.2",
      "beforeText": "Subjects with hepatic impairment",
      "afterText": "Subjects with moderate or severe hepatic impairment (Child-Pugh Class B or C)",
      "summary": "Added specific Child-Pugh classification to hepatic impairment criterion"
    }}
  ]
}}
```

Valid impactLevel values: Major, Minor, Administrative
Valid category values: Safety, Efficacy, Regulatory, Operational, Scientific, Administrative
Valid changeType values: Addition, Deletion, Modification, Clarification

PROTOCOL TEXT:
{protocol_text}

Extract all amendment impacts, reasons, and specific changes. Focus on any amendment summary tables or change logs."""


def get_amendments_prompt(protocol_text: str) -> str:
    """Generate the full prompt for amendment details extraction."""
    return AMENDMENTS_USER_PROMPT.format(protocol_text=protocol_text)


def get_system_prompt() -> str:
    """Get the system prompt for amendment details extraction."""
    return AMENDMENTS_SYSTEM_PROMPT
