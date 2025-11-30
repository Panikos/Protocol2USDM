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
    # Objective Level Codes
    "C85826": "Trial Primary Objective",
    "C85827": "Trial Secondary Objective",
    "C163559": "Trial Exploratory Objective",
    
    # Endpoint Level Codes
    "C98772": "Primary Outcome Measure",
    "C98781": "Secondary Outcome Measure",
    "C98724": "Exploratory Outcome Measure",
    
    # Study Phase Codes
    "C15600": "Phase I Trial",
    "C15601": "Phase II Trial",
    "C15602": "Phase III Trial",
    "C15603": "Phase IV Trial",
    "C15693": "Phase I/II Trial",
    "C15694": "Phase II/III Trial",
    
    # Blinding Codes - Verified 2024-11-30
    "C49659": "Open Label Study",
    "C28233": "Single Blind Study",
    "C15228": "Double Blind Study",
    "C66959": "Triple Blind Study",
    
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
