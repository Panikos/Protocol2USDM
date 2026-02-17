"""
LLM Prompts for Study Metadata Extraction.

These prompts guide the LLM to extract study identity and metadata
from protocol title pages and synopsis sections.

Output format follows USDM v4.0 OpenAPI schema requirements.
"""

METADATA_EXTRACTION_PROMPT = """You are an expert at extracting study metadata from clinical trial protocols.
Your output must conform to USDM v4.0 schema specifications.

Analyze the provided protocol pages (title page, synopsis, or first few pages) and extract the following information:

## Required Information

### 1. Study Titles
Extract ALL title variations found:
- **Official Study Title**: Full formal title (usually the longest)
- **Brief Study Title**: Short version for registries
- **Study Acronym**: If present (e.g., "REGEN-COV", "KEYNOTE-001")
- **Scientific Study Title**: Technical title if different from official

### 2. Study Identifiers
Extract ALL identifier numbers found anywhere in the document:
- **NCT Number**: ClinicalTrials.gov ID (format: NCT########)
- **Sponsor Protocol Number**: Company internal ID (e.g., "ABC-1234-ONCO-301", "LY3298176")
- **EudraCT Number**: European registry (format: ####-######-##)
- **IND/IDE Number**: FDA application numbers (e.g., "IND 123456")
- **ISRCTN Number**: International registry (format: ISRCTN########)
- **WHO UTN**: Universal Trial Number
- **CTIS Number**: EU Clinical Trial Information System
- **Internal Study ID**: Any other internal reference numbers

For each identifier, note the issuing organization (e.g., ClinicalTrials.gov issues NCT numbers).

### 3. Organizations
Extract ALL organizations mentioned with their roles:
- **Sponsor**: Primary funding company/institution
- **Co-Sponsor**: Additional funding organizations
- **CRO**: Contract Research Organization managing the trial
- **Academic Partners**: Universities or research institutions collaborating
- **Regulatory Agencies**: FDA, EMA, etc. if mentioned
- **Central Laboratories**: Labs performing central assays
- **Data Management**: Organizations handling data
- **Medical Monitor**: Organization providing medical oversight

Look for organizations on the title page, in the synopsis, and in the "Sponsor Information" or "Contact Information" sections.

### 4. Study Phase & Type
- Phase (1, 2, 3, 4 or combinations)
- Interventional or Observational

### 5. Indication/Disease
- Primary disease or condition being studied

### 6. Study Rationale / Background
- Extract the study rationale or scientific background (usually from Section 2 "Introduction" or "Background")
- This is the justification for conducting the study (1-3 sentences)

### 7. Sponsor Address
- If the sponsor's address is visible on the title page or contact section, extract it
- Include city, state/province, country, postal code if available

### 8. Key Dates
- Protocol date (date on title page or approval date)
- Sponsor approval date (if mentioned)
- Original protocol date vs amendment date

### 9. Key Personnel
- Principal Investigator name (if on title page or synopsis)
- Medical Monitor name (if mentioned)
- Statistician name (if mentioned)
- For each person, note which organization role they belong to

### 10. Cross-Reference Identifiers
- Any references to related protocols, sub-studies, or companion documents
- IB (Investigator's Brochure) reference numbers
- Related study protocol numbers

### 11. Planned Enrollment Number
- Target number of participants/subjects to be enrolled
- Look for phrases like "approximately N participants", "planned enrollment of N", "target N subjects", "sample size of N"
- Return the number as an integer (e.g., 200), or null if not found
- If a range is given (e.g., "100-200 participants"), return the upper bound

## USDM v4.0 Output Format (MUST follow exactly)

Every entity MUST have `id` and `instanceType` fields.
Code fields MUST use the {"code": "...", "codeSystem": "...", "decode": "..."} structure.

```json
{
  "titles": [
    {
      "id": "title_1",
      "text": "A Phase 2, Randomized Study of Drug X in Patients with Condition Y",
      "type": {
        "code": "OfficialStudyTitle",
        "codeSystem": "http://www.cdisc.org/USDM/titleType",
        "decode": "Official Study Title"
      },
      "instanceType": "StudyTitle"
    },
    {
      "id": "title_2",
      "text": "Drug X Phase 2 Study",
      "type": {
        "code": "BriefStudyTitle",
        "codeSystem": "http://www.cdisc.org/USDM/titleType",
        "decode": "Brief Study Title"
      },
      "instanceType": "StudyTitle"
    }
  ],
  "identifiers": [
    {
      "id": "sid_1",
      "text": "NCT04123456",
      "identifierType": "NCT",
      "issuingOrganization": "ClinicalTrials.gov",
      "instanceType": "StudyIdentifier"
    },
    {
      "id": "sid_2",
      "text": "SPONSOR-2020-001",
      "identifierType": "SponsorProtocolNumber",
      "issuingOrganization": "Sponsor",
      "instanceType": "StudyIdentifier"
    },
    {
      "id": "sid_3",
      "text": "2020-001234-56",
      "identifierType": "EudraCT",
      "issuingOrganization": "EudraCT",
      "instanceType": "StudyIdentifier"
    },
    {
      "id": "sid_4",
      "text": "IND 123456",
      "identifierType": "IND",
      "issuingOrganization": "FDA",
      "instanceType": "StudyIdentifier"
    }
  ],
  "organizations": [
    {
      "id": "org_1",
      "name": "Acme Pharmaceuticals, Inc.",
      "type": {
        "code": "Sponsor",
        "codeSystem": "http://www.cdisc.org/USDM/organizationType",
        "decode": "Sponsor"
      },
      "role": "Sponsor",
      "instanceType": "Organization"
    },
    {
      "id": "org_2",
      "name": "PRA Health Sciences",
      "type": {
        "code": "CRO",
        "codeSystem": "http://www.cdisc.org/USDM/organizationType",
        "decode": "Contract Research Organization"
      },
      "role": "CRO",
      "instanceType": "Organization"
    },
    {
      "id": "org_3",
      "name": "ClinicalTrials.gov",
      "type": {
        "code": "Registry",
        "codeSystem": "http://www.cdisc.org/USDM/organizationType",
        "decode": "Clinical Study Registry"
      },
      "role": "Registry",
      "instanceType": "Organization"
    }
  ],
  "studyPhase": {
    "code": "Phase2",
    "codeSystem": "http://www.cdisc.org/USDM/studyPhase",
    "decode": "Phase 2"
  },
  "studyType": "Interventional",
  "indication": {
    "id": "ind_1",
    "name": "Type 2 Diabetes Mellitus",
    "description": "Patients with inadequately controlled T2DM",
    "instanceType": "Indication"
  },
  "studyRationale": "This study is designed to evaluate the efficacy and safety of Drug X in patients with T2DM who have inadequate glycemic control on metformin monotherapy.",
  "sponsorAddress": {
    "city": "New York",
    "state": "NY",
    "country": "United States",
    "postalCode": "10001"
  },
  "protocolVersion": {
    "version": "3.0",
    "date": "2024-03-15",
    "amendment": "Amendment 2"
  },
  "governanceDates": {
    "protocolDate": "2024-03-15",
    "sponsorApprovalDate": "2024-03-20",
    "originalProtocolDate": "2023-01-10"
  },
  "keyPersonnel": [
    {"name": "Dr. Jane Smith", "role": "Principal Investigator"},
    {"name": "Dr. John Doe", "role": "Medical Monitor"}
  ],
  "referenceIdentifiers": [
    {"text": "IB-2024-001", "type": "Investigator Brochure"},
    {"text": "SPONSOR-2020-002", "type": "Related Protocol"}
  ],
  "plannedEnrollmentNumber": 200
}
```

## Title Type Codes
- OfficialStudyTitle = Official Study Title (full formal title)
- BriefStudyTitle = Brief Study Title (short registry version)
- StudyAcronym = Study Acronym (e.g., KEYNOTE-001)
- ScientificStudyTitle = Scientific Study Title

## Identifier Type Codes
- NCT = ClinicalTrials.gov identifier
- SponsorProtocolNumber = Sponsor's internal protocol ID
- EudraCT = European Clinical Trials Database
- IND = FDA Investigational New Drug application
- IDE = FDA Investigational Device Exemption
- ISRCTN = International Standard Randomised Controlled Trial Number
- CTIS = EU Clinical Trial Information System
- WHO_UTN = WHO Universal Trial Number

## Organization Type Codes
- Sponsor = Study Sponsor (primary funding source)
- CoSponsor = Co-Sponsor (additional funding)
- CRO = Contract Research Organization
- RegulatoryAuthority = Regulatory Authority (FDA, EMA, etc.)
- AcademicInstitution = University or research institution
- CentralLab = Central laboratory for assays
- Registry = Clinical study registry (ClinicalTrials.gov, EudraCT)

## Study Phase Codes
- Phase1, Phase2, Phase3, Phase4
- Phase1Phase2 (combined), Phase2Phase3 (combined)
- NotApplicable (for observational)

## Rules

1. **Every entity must have `id` and `instanceType`** - this is mandatory
2. **Use sequential IDs** - title_1, title_2, sid_1, sid_2, org_1, etc.
3. **Extract exactly what you see** - do not infer information
4. **Use null** for optional fields where information is not found
5. **Return ONLY valid JSON** - no markdown fences, no explanations

Now analyze the protocol content and extract the metadata:
"""


TITLE_PAGE_FINDER_PROMPT = """Analyze these PDF pages and identify which pages contain study metadata.

Look for pages that contain:
1. **Title Page**: Usually page 1, contains study title, sponsor, protocol number
2. **Synopsis/Summary**: Usually pages 2-5, contains study overview
3. **Protocol Information Table**: Often on title page or page 2

Return a JSON object:
```json
{
  "title_page": [page_numbers],
  "synopsis_pages": [page_numbers],
  "confidence": "high/medium/low",
  "notes": "any relevant observations"
}
```

Pages are 0-indexed. Return ONLY valid JSON.
"""


def build_metadata_extraction_prompt(protocol_text: str) -> str:
    """Build the full extraction prompt with protocol content."""
    return f"{METADATA_EXTRACTION_PROMPT}\n\n---\n\nPROTOCOL CONTENT:\n\n{protocol_text}"


def build_vision_extraction_prompt() -> str:
    """Build prompt for vision-based extraction from title page images."""
    return """Analyze this protocol title page image and extract study metadata.

Extract:
1. All study titles (official, brief, acronym)
2. All identifier numbers (NCT, protocol number, EudraCT, etc.)
3. Sponsor and other organizations
4. Study phase
5. Indication/disease
6. Protocol version and date

Return a JSON object with the extracted information. Use null for any fields not visible.
Return ONLY valid JSON, no explanations.

JSON structure:
{
  "titles": [...],
  "identifiers": [...],
  "organizations": [...],
  "studyPhase": "...",
  "indication": {...},
  "studyType": "...",
  "protocolVersion": {...}
}
"""
