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
        "decode": "Trial Primary Objective",
        "definition": "The main purpose of the trial.",
    },
    "secondary": {
        "code": "C85827", 
        "decode": "Trial Secondary Objective",
        "definition": "The secondary purpose of the trial.",
    },
    "exploratory": {
        "code": "C163559",
        "decode": "Trial Exploratory Objective",
        "definition": "The exploratory purpose of the trial.",
    },
}


# =============================================================================
# ENDPOINT/OUTCOME MEASURE LEVEL CODES (OUTLEV)
# Source: CDISC Protocol Controlled Terminology
# =============================================================================

ENDPOINT_LEVEL_CODES: Dict[str, Dict[str, str]] = {
    "primary": {
        "code": "C98772",
        "decode": "Primary Outcome Measure",
        "definition": "The outcome measure(s) of greatest importance specified in the protocol.",
    },
    "secondary": {
        "code": "C98781",
        "decode": "Secondary Outcome Measure", 
        "definition": "The outcome measure(s) that is part of a pre-specified analysis plan used to evaluate the secondary endpoint(s).",
    },
    "exploratory": {
        "code": "C98724",
        "decode": "Exploratory Outcome Measure",
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
