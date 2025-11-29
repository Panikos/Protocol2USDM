"""
USDM v4.0 Reference Examples

This module provides validated JSON examples for all USDM entity types.
These examples are derived from the official USDM OpenAPI schema (USDM_API.json)
and should be used as the source of truth for prompt engineering.

Usage in prompts:
    from validation.usdm_examples import STUDY_TITLE_EXAMPLE, get_example_json
    
    prompt = f'''
    Output format must match this USDM v4.0 structure:
    {get_example_json('StudyTitle')}
    '''

All examples include:
- Required fields per OpenAPI schema
- Proper 'instanceType' values
- Code objects with code/codeSystem/decode structure
- Realistic placeholder values
"""

import json
from typing import Dict, Any, Optional


# =============================================================================
# CORE ENTITIES
# =============================================================================

STUDY_EXAMPLE = {
    "id": "study_1",
    "name": "A Phase 2 Study of Drug X in Patients with Condition Y",
    "description": "This study evaluates the safety and efficacy of Drug X",
    "instanceType": "Study"
}

STUDY_VERSION_EXAMPLE = {
    "id": "sv_1",
    "versionIdentifier": "1.0",
    "rationale": "Initial protocol version",
    "instanceType": "StudyVersion",
    # Required arrays (can be empty but must exist)
    "titles": [],           # See STUDY_TITLE_EXAMPLE
    "studyIdentifiers": [], # See STUDY_IDENTIFIER_EXAMPLE
    "studyDesigns": [],     # See STUDY_DESIGN_EXAMPLE
}

STUDY_TITLE_EXAMPLE = {
    "id": "title_1",
    "text": "A Phase 2, Randomized, Double-Blind Study of Drug X",
    "type": {
        "code": "OfficialStudyTitle",
        "codeSystem": "http://www.cdisc.org/USDM/titleType",
        "decode": "Official Study Title"
    },
    "instanceType": "StudyTitle"
}

STUDY_TITLE_TYPES = {
    "official": {"code": "OfficialStudyTitle", "decode": "Official Study Title"},
    "brief": {"code": "BriefStudyTitle", "decode": "Brief Study Title"},
    "acronym": {"code": "StudyAcronym", "decode": "Study Acronym"},
    "scientific": {"code": "ScientificStudyTitle", "decode": "Scientific Study Title"},
}

STUDY_IDENTIFIER_EXAMPLE = {
    "id": "sid_1",
    "text": "NCT04123456",
    "scopeId": "org_sponsor",  # Reference to Organization
    "instanceType": "StudyIdentifier"
}

ORGANIZATION_EXAMPLE = {
    "id": "org_1",
    "name": "Acme Pharmaceuticals, Inc.",
    "type": {
        "code": "Sponsor",
        "codeSystem": "http://www.cdisc.org/USDM/organizationType",
        "decode": "Sponsor"
    },
    "instanceType": "Organization"
}

ORGANIZATION_TYPES = {
    "sponsor": {"code": "Sponsor", "decode": "Sponsor"},
    "cro": {"code": "CRO", "decode": "Contract Research Organization"},
    "regulatory": {"code": "RegulatoryAuthority", "decode": "Regulatory Authority"},
}


# =============================================================================
# STUDY DESIGN ENTITIES
# =============================================================================

STUDY_DESIGN_EXAMPLE = {
    "id": "sd_1",
    "name": "Main Study Design",
    "description": "Randomized, double-blind, placebo-controlled design",
    "instanceType": "InterventionalStudyDesign",  # or "ObservationalStudyDesign"
    # Optional but common fields
    "blindingSchema": {
        "code": "DoubleBlind",
        "codeSystem": "http://www.cdisc.org/USDM/blindingSchema",
        "decode": "Double Blind"
    },
    "studyArms": [],        # See STUDY_ARM_EXAMPLE
    "studyCells": [],       # See STUDY_CELL_EXAMPLE
    "activities": [],       # See ACTIVITY_EXAMPLE
    "encounters": [],       # See ENCOUNTER_EXAMPLE
    "epochs": [],           # See EPOCH_EXAMPLE
}

BLINDING_SCHEMA_CODES = {
    "open": {"code": "OpenLabel", "decode": "Open Label"},
    "single": {"code": "SingleBlind", "decode": "Single Blind"},
    "double": {"code": "DoubleBlind", "decode": "Double Blind"},
    "triple": {"code": "TripleBlind", "decode": "Triple Blind"},
}

STUDY_ARM_EXAMPLE = {
    "id": "arm_1",
    "name": "Treatment Arm A",
    "description": "Patients receiving Drug X 100mg",
    "type": {
        "code": "Experimental",
        "codeSystem": "http://www.cdisc.org/USDM/armType",
        "decode": "Experimental Arm"
    },
    "instanceType": "StudyArm"
}

STUDY_CELL_EXAMPLE = {
    "id": "cell_1",
    "armId": "arm_1",
    "epochId": "epoch_1",
    "instanceType": "StudyCell"
}


# =============================================================================
# ELIGIBILITY ENTITIES
# =============================================================================

ELIGIBILITY_CRITERION_EXAMPLE = {
    "id": "ec_1",
    "name": "Age requirement",
    "identifier": "I1",
    "category": {
        "code": "Inclusion",
        "codeSystem": "http://www.cdisc.org/USDM/criterionCategory",
        "decode": "Inclusion Criterion"
    },
    "criterionItemId": "eci_1",  # Reference to EligibilityCriterionItem
    "instanceType": "EligibilityCriterion"
}

ELIGIBILITY_CRITERION_ITEM_EXAMPLE = {
    "id": "eci_1",
    "name": "Age requirement",
    "text": "Age ≥ 18 years at the time of signing informed consent",
    "instanceType": "EligibilityCriterionItem"
}

CRITERION_CATEGORIES = {
    "inclusion": {"code": "Inclusion", "decode": "Inclusion Criterion"},
    "exclusion": {"code": "Exclusion", "decode": "Exclusion Criterion"},
}

STUDY_DESIGN_POPULATION_EXAMPLE = {
    "id": "pop_1",
    "name": "Intent-to-Treat Population",
    "description": "All randomized patients",
    "includesHealthySubjects": False,
    "plannedEnrollmentNumber": {
        "maxValue": 200,
        "instanceType": "Range"
    },
    "plannedMinimumAge": "P18Y",  # ISO 8601 duration
    "plannedMaximumAge": "P75Y",
    "criterionIds": ["ec_1", "ec_2"],
    "instanceType": "StudyDesignPopulation"
}


# =============================================================================
# OBJECTIVES & ENDPOINTS
# =============================================================================

OBJECTIVE_EXAMPLE = {
    "id": "obj_1",
    "name": "Primary Efficacy Objective",
    "text": "To evaluate the efficacy of Drug X compared to placebo",
    "level": {
        "code": "Primary",
        "codeSystem": "http://www.cdisc.org/USDM/objectiveLevel",
        "decode": "Primary Objective"
    },
    "endpointIds": ["ep_1"],
    "instanceType": "Objective"
}

ENDPOINT_EXAMPLE = {
    "id": "ep_1",
    "name": "Primary Efficacy Endpoint",
    "text": "Change from baseline in disease severity score at Week 12",
    "level": {
        "code": "Primary",
        "codeSystem": "http://www.cdisc.org/USDM/endpointLevel",
        "decode": "Primary Endpoint"
    },
    "purpose": "Efficacy",
    "instanceType": "Endpoint"
}

OBJECTIVE_LEVELS = {
    "primary": {"code": "Primary", "decode": "Primary"},
    "secondary": {"code": "Secondary", "decode": "Secondary"},
    "exploratory": {"code": "Exploratory", "decode": "Exploratory"},
}


# =============================================================================
# INTERVENTION ENTITIES
# =============================================================================

STUDY_INTERVENTION_EXAMPLE = {
    "id": "int_1",
    "name": "Drug X 100mg",
    "description": "Active treatment arm intervention",
    "type": {
        "code": "Drug",
        "codeSystem": "http://www.cdisc.org/USDM/interventionType",
        "decode": "Drug"
    },
    "productIds": ["prod_1"],
    "instanceType": "StudyIntervention"
}

ADMINISTRABLE_PRODUCT_EXAMPLE = {
    "id": "prod_1",
    "name": "Drug X Tablet 100mg",
    "description": "Film-coated tablet for oral administration",
    "instanceType": "AdministrableProduct"
}

ADMINISTRATION_EXAMPLE = {
    "id": "admin_1",
    "name": "Drug X Administration",
    "route": {
        "code": "Oral",
        "codeSystem": "http://www.cdisc.org/USDM/route",
        "decode": "Oral"
    },
    "frequency": {
        "code": "QD",
        "codeSystem": "http://www.cdisc.org/USDM/frequency",
        "decode": "Once Daily"
    },
    "instanceType": "Administration"
}


# =============================================================================
# SCHEDULE OF ACTIVITIES ENTITIES
# =============================================================================

ACTIVITY_EXAMPLE = {
    "id": "act_1",
    "name": "Informed Consent",
    "description": "Obtain written informed consent from participant",
    "instanceType": "Activity",
    # Optional fields
    "definedProcedures": [],    # See PROCEDURE_EXAMPLE
    "biomedicalConceptIds": [], # References to BiomedicalConcept
}

ENCOUNTER_EXAMPLE = {
    "id": "enc_1",
    "name": "Screening Visit",
    "description": "Initial screening visit",
    "type": {
        "code": "ScheduledVisit",
        "codeSystem": "http://www.cdisc.org/USDM/encounterType",
        "decode": "Scheduled Visit"
    },
    "epochId": "epoch_1",
    "instanceType": "Encounter"
}

EPOCH_EXAMPLE = {
    "id": "epoch_1",
    "name": "Screening",
    "description": "Screening period",
    "type": {
        "code": "Screening",
        "codeSystem": "http://www.cdisc.org/USDM/epochType",
        "decode": "Screening"
    },
    "instanceType": "Epoch"
}

EPOCH_TYPES = {
    "screening": {"code": "Screening", "decode": "Screening"},
    "treatment": {"code": "Treatment", "decode": "Treatment"},
    "followup": {"code": "FollowUp", "decode": "Follow-up"},
    "washout": {"code": "Washout", "decode": "Washout"},
}

PLANNED_TIMEPOINT_EXAMPLE = {
    "id": "pt_1",
    "name": "Visit 1",
    "description": "Screening visit timepoint",
    "encounterId": "enc_1",
    "value": "-14",       # Relative timing value
    "valueLabel": "Day -14",
    "instanceType": "PlannedTimepoint"
}

ACTIVITY_TIMEPOINT_EXAMPLE = {
    "id": "at_1",
    "activityId": "act_1",
    "plannedTimepointId": "pt_1",
    "instanceType": "ActivityTimepoint"
}


# =============================================================================
# NARRATIVE & DOCUMENT ENTITIES
# =============================================================================

NARRATIVE_CONTENT_EXAMPLE = {
    "id": "nc_1",
    "name": "Study Synopsis",
    "text": "This is a Phase 2, randomized, double-blind study...",
    "instanceType": "NarrativeContent"
}

ABBREVIATION_EXAMPLE = {
    "id": "abbr_1",
    "abbreviatedText": "AE",
    "expandedText": "Adverse Event",
    "instanceType": "Abbreviation"
}


# =============================================================================
# AMENDMENT ENTITIES
# =============================================================================

STUDY_AMENDMENT_EXAMPLE = {
    "id": "amend_1",
    "number": "1",
    "summary": "Amendment to increase sample size",
    "instanceType": "StudyAmendment"
}


# =============================================================================
# CODE OBJECT TEMPLATE
# =============================================================================

def make_code(code: str, decode: str, code_system: str = "http://www.cdisc.org/USDM") -> Dict[str, str]:
    """
    Create a properly formatted Code object.
    
    Args:
        code: The code value
        decode: Human-readable decode
        code_system: The code system URI (defaults to USDM)
        
    Returns:
        Dict with code, codeSystem, decode
    """
    return {
        "code": code,
        "codeSystem": code_system,
        "decode": decode
    }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

# Map of entity names to examples
_EXAMPLES = {
    "Study": STUDY_EXAMPLE,
    "StudyVersion": STUDY_VERSION_EXAMPLE,
    "StudyTitle": STUDY_TITLE_EXAMPLE,
    "StudyIdentifier": STUDY_IDENTIFIER_EXAMPLE,
    "Organization": ORGANIZATION_EXAMPLE,
    "InterventionalStudyDesign": STUDY_DESIGN_EXAMPLE,
    "ObservationalStudyDesign": STUDY_DESIGN_EXAMPLE,
    "StudyDesign": STUDY_DESIGN_EXAMPLE,
    "StudyArm": STUDY_ARM_EXAMPLE,
    "StudyCell": STUDY_CELL_EXAMPLE,
    "EligibilityCriterion": ELIGIBILITY_CRITERION_EXAMPLE,
    "EligibilityCriterionItem": ELIGIBILITY_CRITERION_ITEM_EXAMPLE,
    "StudyDesignPopulation": STUDY_DESIGN_POPULATION_EXAMPLE,
    "Objective": OBJECTIVE_EXAMPLE,
    "Endpoint": ENDPOINT_EXAMPLE,
    "StudyIntervention": STUDY_INTERVENTION_EXAMPLE,
    "AdministrableProduct": ADMINISTRABLE_PRODUCT_EXAMPLE,
    "Administration": ADMINISTRATION_EXAMPLE,
    "Activity": ACTIVITY_EXAMPLE,
    "Encounter": ENCOUNTER_EXAMPLE,
    "Epoch": EPOCH_EXAMPLE,
    "PlannedTimepoint": PLANNED_TIMEPOINT_EXAMPLE,
    "ActivityTimepoint": ACTIVITY_TIMEPOINT_EXAMPLE,
    "NarrativeContent": NARRATIVE_CONTENT_EXAMPLE,
    "Abbreviation": ABBREVIATION_EXAMPLE,
    "StudyAmendment": STUDY_AMENDMENT_EXAMPLE,
}


def get_example(entity_type: str) -> Optional[Dict[str, Any]]:
    """
    Get the reference example for an entity type.
    
    Args:
        entity_type: USDM entity type name (e.g., "StudyTitle", "Activity")
        
    Returns:
        Example dict or None if not found
    """
    return _EXAMPLES.get(entity_type)


def get_example_json(entity_type: str, indent: int = 2) -> str:
    """
    Get the reference example as formatted JSON string.
    
    Args:
        entity_type: USDM entity type name
        indent: JSON indentation level
        
    Returns:
        Formatted JSON string or error message
    """
    example = get_example(entity_type)
    if example:
        return json.dumps(example, indent=indent)
    return f"// No example available for {entity_type}"


def get_all_examples() -> Dict[str, Dict[str, Any]]:
    """Get all examples as a dictionary."""
    return _EXAMPLES.copy()


def get_required_fields(entity_type: str) -> list:
    """
    Get required fields for an entity type based on OpenAPI schema.
    
    Returns list of field names that are required.
    """
    # Based on OpenAPI schema analysis
    required_fields = {
        "Study": ["name", "instanceType"],
        "StudyVersion": ["id", "versionIdentifier", "rationale", "titles", "studyIdentifiers", "instanceType"],
        "StudyTitle": ["id", "text", "type", "instanceType"],
        "StudyIdentifier": ["id", "text", "instanceType"],
        "Organization": ["id", "name", "instanceType"],
        "InterventionalStudyDesign": ["id", "instanceType"],
        "StudyArm": ["id", "name", "instanceType"],
        "EligibilityCriterion": ["id", "name", "category", "identifier", "criterionItemId", "instanceType"],
        "EligibilityCriterionItem": ["id", "name", "text", "instanceType"],
        "Objective": ["id", "text", "level", "instanceType"],
        "Endpoint": ["id", "text", "level", "instanceType"],
        "StudyIntervention": ["id", "name", "instanceType"],
        "Activity": ["id", "name", "instanceType"],
        "Encounter": ["id", "name", "instanceType"],
        "Epoch": ["id", "name", "instanceType"],
        "PlannedTimepoint": ["id", "name", "instanceType"],
        "ActivityTimepoint": ["id", "activityId", "plannedTimepointId", "instanceType"],
        "Abbreviation": ["id", "abbreviatedText", "expandedText", "instanceType"],
    }
    return required_fields.get(entity_type, ["id", "instanceType"])


# =============================================================================
# PROMPT HELPERS - Pre-formatted text for inclusion in prompts
# =============================================================================

USDM_STRUCTURE_REMINDER = """
## USDM v4.0 Structure Requirements

CRITICAL: Every entity MUST include:
1. `id` - Unique identifier string (e.g., "act_1", "enc_1")
2. `instanceType` - Exact entity type name (e.g., "Activity", "Encounter")

For coded values, use Code objects:
```json
{
  "code": "ValueCode",
  "codeSystem": "http://www.cdisc.org/USDM/codeSystemName",
  "decode": "Human Readable Value"
}
```
"""

def get_extraction_footer() -> str:
    """Get standard footer for extraction prompts."""
    return """
## Output Requirements

1. Return ONLY valid JSON - no markdown fences, no explanations
2. Every object MUST have `id` and `instanceType` fields
3. Use sequential IDs (e.g., act_1, act_2 for activities)
4. For coded fields, use the Code object structure: {"code": "...", "codeSystem": "...", "decode": "..."}
5. Use null for optional fields where data is not available
6. Preserve exact text from the protocol where applicable
"""
