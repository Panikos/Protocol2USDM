#!/usr/bin/env python3
"""
Validate a USDM JSON file and output results as JSON to stdout.

Used by the Next.js publish API to run live validation on candidate USDM
before writing to disk.

Usage:
    python scripts/validate_usdm_json.py <path_to_usdm.json>

Output (JSON):
    {
        "schema": { "valid": bool, "errors": int, "warnings": int, "issues": [...] },
        "usdm": { "valid": bool, "errors": int, "warnings": int, "issues": [...] }
    }
"""

import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def validate(filepath: str) -> dict:
    """Run schema + USDM validation and return structured results."""
    result = {
        "schema": {"valid": True, "errors": 0, "warnings": 0, "issues": []},
        "usdm": {"valid": True, "errors": 0, "warnings": 0, "issues": []},
    }

    # 1. Basic JSON schema check (can we parse it?)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        result["schema"] = {
            "valid": False,
            "errors": 1,
            "warnings": 0,
            "issues": [{"location": "file", "message": f"Invalid JSON: {e}", "severity": "error"}],
        }
        return result
    except FileNotFoundError:
        result["schema"] = {
            "valid": False,
            "errors": 1,
            "warnings": 0,
            "issues": [{"location": "file", "message": f"File not found: {filepath}", "severity": "error"}],
        }
        return result

    # 2. Structural checks
    schema_issues = []
    if not isinstance(data, dict):
        schema_issues.append({"location": "/", "message": "Root must be an object", "severity": "error"})
    elif "study" not in data:
        schema_issues.append({"location": "/", "message": "Missing required 'study' property", "severity": "error"})
    else:
        study = data.get("study", {})
        if not isinstance(study, dict):
            schema_issues.append({"location": "/study", "message": "'study' must be an object", "severity": "error"})
        elif not study.get("id"):
            schema_issues.append({"location": "/study/id", "message": "Missing study.id", "severity": "warning"})

        versions = study.get("versions", [])
        if not versions:
            schema_issues.append({"location": "/study/versions", "message": "No study versions", "severity": "error"})

    if schema_issues:
        errors = sum(1 for i in schema_issues if i["severity"] == "error")
        warnings = sum(1 for i in schema_issues if i["severity"] == "warning")
        result["schema"] = {
            "valid": errors == 0,
            "errors": errors,
            "warnings": warnings,
            "issues": schema_issues,
        }

    # 3. USDM package validation (if available)
    try:
        from validation.usdm_validator import validate_usdm_dict, HAS_USDM

        if HAS_USDM:
            vr = validate_usdm_dict(data)
            result["usdm"] = {
                "valid": vr.valid,
                "errors": vr.error_count,
                "warnings": vr.warning_count,
                "issues": [i.to_dict() for i in vr.issues[:50]],  # Cap at 50
            }
        else:
            result["usdm"] = {
                "valid": True,
                "errors": 0,
                "warnings": 1,
                "issues": [{"location": "validator", "message": "usdm package not installed, skipping", "severity": "warning"}],
            }
    except Exception as e:
        result["usdm"] = {
            "valid": False,
            "errors": 1,
            "warnings": 0,
            "issues": [{"location": "validator", "message": f"Validation error: {e}", "severity": "error"}],
        }

    return result


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: validate_usdm_json.py <path>"}))
        sys.exit(1)

    filepath = sys.argv[1]
    result = validate(filepath)
    print(json.dumps(result))
    sys.exit(0)


if __name__ == "__main__":
    main()
