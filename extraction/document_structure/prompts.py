"""
LLM Prompts for Document Structure extraction.
Phase 12: DocumentContentReference, CommentAnnotation, StudyDefinitionDocumentVersion
"""

DOCUMENT_STRUCTURE_SYSTEM_PROMPT = """You are an expert clinical protocol analyst specializing in document structure and cross-references.

Your task is to extract:
1. Cross-references between protocol sections
2. Footnotes and annotations
3. Document version information

Return valid JSON only."""

DOCUMENT_STRUCTURE_USER_PROMPT = """Extract Document Structure information from the following protocol text.

**Document Content References to extract:**
- Cross-references to other sections (e.g., "See Section 5.2")
- References to tables, figures, appendices
- Internal links between protocol components

**Comment Annotations to extract:**
- Footnotes (marked with *, †, ‡, numbers, or letters)
- Notes and clarifications
- Important comments in margins or boxes

**Document Version Info to extract:**
- Protocol version number
- Version date
- Amendment numbers if applicable
- Document status (Draft, Final, Approved)

Return JSON in this exact format:
```json
{{
  "contentReferences": [
    {{
      "id": "ref_1",
      "name": "Eligibility Reference",
      "sectionNumber": "5.2",
      "sectionTitle": "Exclusion Criteria",
      "description": "Reference to exclusion criteria from inclusion section"
    }}
  ],
  "annotations": [
    {{
      "id": "annot_1",
      "text": "Subjects must fast for at least 8 hours prior to PK sampling",
      "annotationType": "Footnote",
      "sourceSection": "Schedule of Activities",
      "pageNumber": 15
    }}
  ],
  "documentVersions": [
    {{
      "id": "ver_1",
      "versionNumber": "4.0",
      "versionDate": "2020-06-15",
      "status": "Final",
      "amendmentNumber": "Amendment 3",
      "description": "Protocol Amendment 3 incorporating regulatory feedback"
    }}
  ]
}}
```

Valid annotationType values: Footnote, Comment, Note, Clarification, Reference
Valid status values: Draft, Final, Approved

PROTOCOL TEXT:
{protocol_text}

Extract all cross-references, footnotes/annotations, and version information."""


def get_document_structure_prompt(protocol_text: str) -> str:
    """Generate the full prompt for document structure extraction."""
    return DOCUMENT_STRUCTURE_USER_PROMPT.format(protocol_text=protocol_text)


def get_system_prompt() -> str:
    """Get the system prompt for document structure extraction."""
    return DOCUMENT_STRUCTURE_SYSTEM_PROMPT
