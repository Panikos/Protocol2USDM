"""
LLM Prompts for Advanced Entities Extraction.

These prompts guide the LLM to extract amendments, geographic scope, and sites.
"""

ADVANCED_EXTRACTION_PROMPT = """You are an expert at extracting protocol amendment and geographic information from clinical trial protocols.

Analyze the provided protocol content and extract advanced protocol entities.

## Required Information

### 1. Protocol Amendments (CRITICAL - extract ALL amendments)
Look for the "Protocol Amendment History" section, typically near the end of the document (section 10.x).
For EACH amendment in the history, extract:
- Amendment number (e.g., "1", "2", "3", "3.1 (US)")
- Effective date / approval date
- **Summary**: The "Overall Rationale for the Amendment" paragraph that describes WHY the amendment was made
- Previous and new version numbers
- Reasons for amendment (e.g., Safety, Efficacy, Regulatory, Operational)

**IMPORTANT**: Each amendment should have its own summary text. Look for sections like:
- "Overall Rationale for the Amendment"
- "The main reason for preparation of this amendment was..."
- Summary text appears BEFORE the "Changes to the Protocol" table for each amendment

### 2. Geographic Scope
- List of participating countries
- Regions (if mentioned)
- Number of planned sites (if mentioned)

### 3. Study Sites (if listed)
- Site names or numbers
- City and country

## Output Format

Return a JSON object with this exact structure:

```json
{
  "amendments": [
    {
      "number": "1",
      "effectiveDate": "2020-06-15",
      "summary": "The main reason for preparation of this amendment was to update procedures outlined in the Schedule of Activities, remove contradictory text on the reporting of serious adverse events, and add details of an interim analysis.",
      "previousVersion": "Original Protocol",
      "newVersion": "1",
      "reasons": ["Operational", "Administrative"]
    },
    {
      "number": "2",
      "effectiveDate": "2021-03-19",
      "summary": "The main reason for preparation of this amendment was to revise the exclusion criterion for a urine drug screen and incorporate COVID vaccination guidance.",
      "previousVersion": "1",
      "newVersion": "2",
      "reasons": ["Regulatory", "Safety"]
    }
  ],
  "geographicScope": {
    "type": "Global",
    "countries": [
      {"name": "United States", "code": "US"},
      {"name": "Germany", "code": "DE"}
    ],
    "regions": ["North America", "Europe"],
    "plannedSites": 20
  },
  "sites": []
}
```

## Rules

1. **Extract ALL amendments** - There may be 3-5+ amendments in a protocol
2. **Amendment summaries are REQUIRED** - Look for "Overall Rationale" or "main reason" text
3. **Check amendment history section** - Usually in Section 10.x near end of document
4. **Check title page** - May contain current version and date
5. **Standard country codes** - Use ISO 3166-1 alpha-2 codes when possible
6. **Amendment reasons** - Common: Safety, Efficacy, Regulatory, Administrative, Operational, Scientific
7. **Return ONLY valid JSON** - no markdown, no explanations

Now analyze the protocol content and extract the advanced entities:
"""


def build_advanced_extraction_prompt(protocol_text: str) -> str:
    """Build the full extraction prompt with protocol content."""
    return f"{ADVANCED_EXTRACTION_PROMPT}\n\n---\n\nPROTOCOL CONTENT:\n\n{protocol_text}"
