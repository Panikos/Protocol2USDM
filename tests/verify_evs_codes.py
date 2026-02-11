"""
Verify all NCI codes in terminology_codes.py against NIH EVS API.

This script fetches each code from the live EVS API to confirm:
1. The code exists
2. The decode/preferred name matches our expected value
"""

import sys
from core.evs_client import EVSClient

# All codes we need to verify - Updated with EVS-verified codes
CODES_TO_VERIFY = {
    # Objective Level Codes (USDM CT C188725)
    "C85826": "Primary Objective",
    "C85827": "Secondary Objective",
    "C163559": "Exploratory Objective",
    
    # Endpoint Level Codes (USDM CT C188726)
    "C94496": "Primary Endpoint",
    "C139173": "Secondary Endpoint",
    "C170559": "Exploratory Endpoint",
    
    # Study Phase Codes
    "C15600": "Phase I Trial",
    "C15601": "Phase II Trial",
    "C15602": "Phase III Trial",
    "C15603": "Phase IV Trial",
    "C15693": "Phase I/II Trial",
    "C15694": "Phase II/III Trial",
    
    # Blinding Codes - EVS-verified
    "C49659": "Open Label Study",
    "C28233": "Single Blind Study",
    "C15228": "Double Blind Study",
    "C66959": "Triple Blind Study",
    
    # Epoch Type Codes - EVS-verified
    "C48262": "Trial Screening",
    "C98779": "Run-in Period",
    "C101526": "Treatment Epoch",
    "C99158": "Clinical Study Follow-up",
    
    # Encounter Type (USDM CT C188728)
    "C25716": "Visit",
    
    # StudyTitle Type (USDM CT C207419)
    "C207615": "Brief Study Title",
    "C207616": "Official Study Title",
    "C207617": "Public Study Title",
    "C207618": "Scientific Study Title",
    "C94108": "Study Acronym",
    
    # StudyIntervention Role (USDM CT C207417)
    "C41161": "Experimental Intervention",
    "C68609": "Active Comparator",
    "C753": "Placebo",
    "C165835": "Rescue Medicine",
    "C207614": "Additional Required Treatment",
    "C165822": "Background Treatment",
    
    # AdministrableProduct Designation (USDM CT C207418)
    "C202579": "IMP",
    "C156473": "NIMP",
    
    # Eligibility Codes
    "C25532": "Inclusion Criteria",
    "C25370": "Exclusion Criteria",
    
    # Arm Type Codes - Verified 2024-11-30
    "C174266": "Investigational Arm",
    "C174268": "Placebo Control Arm",
    "C174267": "Active Comparator Arm",
    "C49649": "Active Control",
    "C174270": "No Intervention Arm",
    "C174269": "Sham Comparator Arm",
    
    # Study Identifier Type Codes - Verified 2024-11-30
    "C132351": "Sponsor Protocol Identifier",
    "C172240": "Clinicaltrials.gov Identifier",
    "C98714": "Clinical Trial Registry Identifier",
    "C218685": "US FDA Investigational New Drug Application Number"
}


def verify_codes():
    """Verify all codes against EVS API."""
    print("=" * 70)
    print("Verifying NCI codes against NIH EVS API")
    print("=" * 70)
    print()
    
    client = EVSClient()
    
    passed = 0
    failed = 0
    warnings = 0
    
    for code, expected_decode in CODES_TO_VERIFY.items():
        result = client.fetch_ncit_code(code)
        
        if result is None:
            print(f"[FAIL] {code}: NOT FOUND in EVS API")
            failed += 1
            continue
        
        actual_decode = result.get("decode", "")
        
        # Check if decode matches (case-insensitive, allowing partial matches)
        expected_lower = expected_decode.lower()
        actual_lower = actual_decode.lower()
        
        if expected_lower == actual_lower:
            print(f"[PASS] {code}: {actual_decode}")
            passed += 1
        elif expected_lower in actual_lower or actual_lower in expected_lower:
            print(f"[WARN] {code}: Expected '{expected_decode}', got '{actual_decode}'")
            warnings += 1
        else:
            print(f"[FAIL] {code}: Expected '{expected_decode}', got '{actual_decode}'")
            failed += 1
    
    print()
    print("=" * 70)
    print(f"Results: {passed} passed, {warnings} warnings, {failed} failed")
    print("=" * 70)
    
    if failed > 0:
        print("\nFailed codes need to be corrected in core/terminology_codes.py")
        return 1
    
    if warnings > 0:
        print("\nWarnings indicate slight naming differences - review manually")
    
    return 0


if __name__ == "__main__":
    sys.exit(verify_codes())
