"""
CDISC/NCI Terminology Codes - Single Source of Truth

All NCI codes used in Protocol2USDM should be defined here.
This prevents duplication and ensures consistency across:
- extraction/objectives/schema.py
- enrichment/terminology.py  
- core/usdm_types.py

Sources:
- CDISC Protocol Controlled Terminology: https://evs.nci.nih.gov/ftp1/CDISC/Protocol/
- NCI Thesaurus: https://ncithesaurus.nci.nih.gov/
- EVS REST API: https://api-evsrest.nci.nih.gov/

IMPORTANT: All codes in this file have been verified against the NIH EVS API.
Run `python tests/verify_evs_codes.py` to re-verify codes after any changes.
Last verified: 2024-11-30
"""

from typing import Dict, Any


# =============================================================================
# OBJECTIVE LEVEL CODES (OBJLVL)
# Source: https://ncithesaurus.nci.nih.gov/
# =============================================================================

OBJECTIVE_LEVEL_CODES: Dict[str, Dict[str, str]] = {
    "primary": {
        "code": "C85826",
        "decode": "Primary Objective",
        "definition": "The main purpose of the trial.",
    },
    "secondary": {
        "code": "C85827", 
        "decode": "Secondary Objective",
        "definition": "The secondary purpose of the trial.",
    },
    "exploratory": {
        "code": "C163559",
        "decode": "Exploratory Objective",
        "definition": "The exploratory purpose of the trial.",
    },
}


# =============================================================================
# ENDPOINT/OUTCOME MEASURE LEVEL CODES (OUTLEV)
# Source: CDISC Protocol Controlled Terminology
# =============================================================================

ENDPOINT_LEVEL_CODES: Dict[str, Dict[str, str]] = {
    "primary": {
        "code": "C94496",
        "decode": "Primary Endpoint",
        "definition": "The outcome measure(s) of greatest importance specified in the protocol.",
    },
    "secondary": {
        "code": "C139173",
        "decode": "Secondary Endpoint", 
        "definition": "The outcome measure(s) that is part of a pre-specified analysis plan used to evaluate the secondary endpoint(s).",
    },
    "exploratory": {
        "code": "C170559",
        "decode": "Exploratory Endpoint",
        "definition": "The outcome measure(s) that is part of a pre-specified analysis plan used to evaluate the exploratory endpoint(s).",
    },
}


# =============================================================================
# STUDY PHASE CODES (TPHASE)
# =============================================================================

STUDY_PHASE_CODES: Dict[str, Dict[str, str]] = {
    "phase 1": {"code": "C15600", "decode": "Phase I Trial"},
    "phase i": {"code": "C15600", "decode": "Phase I Trial"},
    "phase 2": {"code": "C15601", "decode": "Phase II Trial"},
    "phase ii": {"code": "C15601", "decode": "Phase II Trial"},
    "phase 3": {"code": "C15602", "decode": "Phase III Trial"},
    "phase iii": {"code": "C15602", "decode": "Phase III Trial"},
    "phase 4": {"code": "C15603", "decode": "Phase IV Trial"},
    "phase iv": {"code": "C15603", "decode": "Phase IV Trial"},
    "phase 1/2": {"code": "C15693", "decode": "Phase I/II Trial"},
    "phase i/ii": {"code": "C15693", "decode": "Phase I/II Trial"},
    "phase 2/3": {"code": "C15694", "decode": "Phase II/III Trial"},
    "phase ii/iii": {"code": "C15694", "decode": "Phase II/III Trial"},
}


# =============================================================================
# BLINDING CODES (TBLIND) - Verified against NIH EVS API
# =============================================================================

BLINDING_CODES: Dict[str, Dict[str, str]] = {
    "open label": {"code": "C49659", "decode": "Open Label Study"},
    "open-label": {"code": "C49659", "decode": "Open Label Study"},
    "single blind": {"code": "C28233", "decode": "Single Blind Study"},
    "single-blind": {"code": "C28233", "decode": "Single Blind Study"},
    "double blind": {"code": "C15228", "decode": "Double Blind Study"},
    "double-blind": {"code": "C15228", "decode": "Double Blind Study"},
    "triple blind": {"code": "C66959", "decode": "Triple Blind Study"},
    "triple-blind": {"code": "C66959", "decode": "Triple Blind Study"},
}


# =============================================================================
# ELIGIBILITY CATEGORY CODES
# =============================================================================

ELIGIBILITY_CODES: Dict[str, Dict[str, str]] = {
    "inclusion": {"code": "C25532", "decode": "Inclusion Criteria"},
    "exclusion": {"code": "C25370", "decode": "Exclusion Criteria"},
}


# =============================================================================
# STUDY MODEL CODES (SDESIGN) - Verified against NIH EVS API
# Source: CDISC Protocol Controlled Terminology
# =============================================================================

STUDY_MODEL_CODES: Dict[str, Dict[str, str]] = {
    "parallel": {
        "code": "C82639",
        "decode": "Parallel Study",
        "description": "A study in which groups of participants receive different interventions simultaneously.",
    },
    "crossover": {
        "code": "C49649",
        "decode": "Crossover Study",
        "description": "A study in which each subject receives each treatment in sequence.",
    },
    "single group": {
        "code": "C82638",
        "decode": "Single Group Study",
        "description": "A study in which all subjects receive the same intervention.",
    },
    "factorial": {
        "code": "C82640",
        "decode": "Factorial Study",
        "description": "A study in which two or more interventions, each with two or more levels, are evaluated in combination.",
    },
    "sequential": {
        "code": "C139287",
        "decode": "Sequential Study",
        "description": "A study in which groups of participants receive different interventions in sequence.",
    },
}


# =============================================================================
# STUDY ARM TYPE CODES - Verified against NIH EVS API
# =============================================================================

ARM_TYPE_CODES: Dict[str, Dict[str, str]] = {
    "experimental": {"code": "C174266", "decode": "Investigational Arm"},
    "investigational": {"code": "C174266", "decode": "Investigational Arm"},
    "treatment": {"code": "C174266", "decode": "Investigational Arm"},
    "placebo": {"code": "C174268", "decode": "Placebo Control Arm"},
    "placebo control": {"code": "C174268", "decode": "Placebo Control Arm"},
    "active comparator": {"code": "C174267", "decode": "Active Comparator Arm"},
    "comparator": {"code": "C174267", "decode": "Active Comparator Arm"},
    "active control": {"code": "C49649", "decode": "Active Control"},
    "no intervention": {"code": "C174270", "decode": "No Intervention Arm"},
    "sham comparator": {"code": "C174269", "decode": "Sham Comparator Arm"},
    "control": {"code": "C49649", "decode": "Active Control"},
}


# =============================================================================
# STUDY TYPE CODES
# =============================================================================

STUDY_TYPE_CODES: Dict[str, Dict[str, str]] = {
    "interventional": {"code": "C98388", "decode": "Interventional Study"},
    "observational": {"code": "C15208", "decode": "Observational Study"},
    "clinical trial": {"code": "C15273", "decode": "Clinical Trial"},
    "not applicable": {"code": "C48660", "decode": "Not Applicable"},
}


# =============================================================================
# RANDOMIZATION CODES
# =============================================================================

RANDOMIZATION_CODES: Dict[str, Dict[str, str]] = {
    "randomized": {"code": "C25196", "decode": "Randomized"},
    "non-randomized": {"code": "C127779", "decode": "Non-Randomized"},
    "not randomized": {"code": "C127779", "decode": "Non-Randomized"},
}


# =============================================================================
# ENCOUNTER TYPE CODES (for visits)
# =============================================================================

ENCOUNTER_TYPE_CODES: Dict[str, Dict[str, str]] = {
    "initial visit": {"code": "C16741", "decode": "Initial Visit"},
    "screening": {"code": "C25188", "decode": "Screening"},
    "baseline": {"code": "C25582", "decode": "Baseline"},
    "follow-up": {"code": "C18080", "decode": "Follow-up"},
    "follow up": {"code": "C18080", "decode": "Follow-up"},
    "end of study": {"code": "C41379", "decode": "End of Study"},
    "end of treatment": {"code": "C41379", "decode": "End of Study"},
}


# =============================================================================
# STUDY IDENTIFIER TYPE CODES
# Source: CDISC Protocol Controlled Terminology
# =============================================================================

STUDY_IDENTIFIER_TYPE_CODES: Dict[str, Dict[str, str]] = {
    "sponsor": {
        "code": "C132351",  # Verified against EVS API
        "decode": "Sponsor Protocol Identifier",
        "pattern": None,  # Default for sponsor identifiers
    },
    "nct": {
        "code": "C172240",  # Verified against EVS API
        "decode": "Clinicaltrials.gov Identifier",
        "pattern": r"^NCT\d+$",
    },
    "eudract": {
        "code": "C98714",  # Clinical Trial Registry Identifier (generic)
        "decode": "Clinical Trial Registry Identifier",
        "pattern": r"^\d{4}-\d{6}-\d{2}$",
    },
    "ind": {
        "code": "C218685",  # Verified against EVS API
        "decode": "US FDA Investigational New Drug Application Number",
        "pattern": r"^\d{5,6}$",  # Usually 5-6 digit numbers
    },
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_code_object(
    level: str, 
    codes_dict: Dict[str, Dict[str, str]],
    code_system: str = "http://www.cdisc.org",
    code_system_version: str = "2024-09-27",
) -> Dict[str, Any]:
    """
    Get a USDM-compliant Code object for a given level.
    
    Args:
        level: The level text (e.g., "primary", "secondary", "exploratory")
        codes_dict: The dictionary of codes to look up from
        code_system: The code system URI
        code_system_version: The code system version
        
    Returns:
        USDM Code object dict
    """
    level_lower = level.lower().strip()
    
    if level_lower not in codes_dict:
        # Return a minimal code object for unknown levels
        return {
            "code": level,
            "codeSystem": code_system,
            "codeSystemVersion": code_system_version,
            "decode": level,
            "instanceType": "Code",
        }
    
    info = codes_dict[level_lower]
    return {
        "code": info["code"],
        "codeSystem": code_system,
        "codeSystemVersion": code_system_version,
        "decode": info["decode"],
        "instanceType": "Code",
    }


def get_objective_level_code(level: str) -> Dict[str, Any]:
    """Get USDM Code object for an objective level."""
    return get_code_object(level, OBJECTIVE_LEVEL_CODES)


def get_endpoint_level_code(level: str) -> Dict[str, Any]:
    """Get USDM Code object for an endpoint level."""
    return get_code_object(level, ENDPOINT_LEVEL_CODES)


def get_study_identifier_type(identifier_text: str) -> Dict[str, Any]:
    """
    Infer the type of a study identifier based on its format.
    
    Args:
        identifier_text: The identifier value (e.g., "NCT04573309", "2020-001104-41")
        
    Returns:
        USDM Code object for the identifier type
        
    Mappings (EVS-verified):
        NCT... -> C172240 (Clinicaltrials.gov Identifier)
        YYYY-NNNNNN-NN -> C98714 (Clinical Trial Registry Identifier) 
        5-6 digits -> C218685 (US FDA IND Number)
        Other -> C132351 (Sponsor Protocol Identifier)
    """
    import re
    
    if not identifier_text:
        info = STUDY_IDENTIFIER_TYPE_CODES["sponsor"]
        return {
            "code": info["code"],
            "codeSystem": "http://www.cdisc.org",
            "codeSystemVersion": "2024-09-27",
            "decode": info["decode"],
            "instanceType": "Code",
        }
    
    text = identifier_text.strip()
    
    # Check NCT format (ClinicalTrials.gov)
    if re.match(r'^NCT\d+$', text, re.IGNORECASE):
        info = STUDY_IDENTIFIER_TYPE_CODES["nct"]
        return {
            "code": info["code"],
            "codeSystem": "http://www.cdisc.org",
            "codeSystemVersion": "2024-09-27",
            "decode": info["decode"],
            "instanceType": "Code",
        }
    
    # Check EudraCT format (YYYY-NNNNNN-NN)
    if re.match(r'^\d{4}-\d{6}-\d{2}$', text):
        info = STUDY_IDENTIFIER_TYPE_CODES["eudract"]
        return {
            "code": info["code"],
            "codeSystem": "http://www.cdisc.org",
            "codeSystemVersion": "2024-09-27",
            "decode": info["decode"],
            "instanceType": "Code",
        }
    
    # Check IND format (5-6 digit number)
    if re.match(r'^\d{5,6}$', text):
        info = STUDY_IDENTIFIER_TYPE_CODES["ind"]
        return {
            "code": info["code"],
            "codeSystem": "http://www.cdisc.org",
            "codeSystemVersion": "2024-09-27",
            "decode": info["decode"],
            "instanceType": "Code",
        }
    
    # Default to Sponsor Protocol Identifier
    info = STUDY_IDENTIFIER_TYPE_CODES["sponsor"]
    return {
        "code": info["code"],
        "codeSystem": "http://www.cdisc.org",
        "codeSystemVersion": "2024-09-27",
        "decode": info["decode"],
        "instanceType": "Code",
    }


# =============================================================================
# UNIFIED REGISTRY — single flat {nci_code: decode} for EVS cache seeding
# Derived from all dicts above. Import this instead of maintaining a copy.
# =============================================================================

def _build_registry() -> Dict[str, str]:
    """Build a flat {code: decode} dict from all terminology dicts."""
    registry: Dict[str, str] = {}
    for codes_dict in [
        OBJECTIVE_LEVEL_CODES, ENDPOINT_LEVEL_CODES, STUDY_PHASE_CODES,
        BLINDING_CODES, ELIGIBILITY_CODES, STUDY_MODEL_CODES,
        ARM_TYPE_CODES, STUDY_TYPE_CODES, RANDOMIZATION_CODES,
        ENCOUNTER_TYPE_CODES, STUDY_IDENTIFIER_TYPE_CODES,
    ]:
        for info in codes_dict.values():
            registry[info["code"]] = info["decode"]
    return registry


USDM_CODES_REGISTRY: Dict[str, str] = _build_registry()
"""Flat {NCI_code: decode} dict covering all USDM-relevant terminology codes."""


def find_code_by_text(text: str, codes_dict: Dict[str, Dict[str, str]]) -> str | None:
    """
    Find NCI code for text using exact or partial matching.
    
    Used by enrichment to look up codes from free text.
    """
    if not text:
        return None
    
    text_lower = text.lower().strip()
    
    # Exact match
    if text_lower in codes_dict:
        return codes_dict[text_lower]["code"]
    
    # Partial match (text contains key or key contains text)
    for key, info in codes_dict.items():
        if key in text_lower or text_lower in key:
            return info["code"]
    
    return None
