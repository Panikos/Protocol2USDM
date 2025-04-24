import json
from typing import Any, Dict

# Load the SoA entity mapping (from the generated mapping file)
with open("soa_entity_mapping.json", "r", encoding="utf-8") as f:
    ENTITY_MAP = json.load(f)

# Helper: Get all required attributes/relationships for an entity
def get_required_fields(entity: str) -> Dict[str, Any]:
    return ENTITY_MAP.get(entity, {})

# Validate a single entity instance against the mapping
# Optionally check value sets for coded attributes

def validate_entity(entity_type: str, instance: dict, errors: list):
    mapping = get_required_fields(entity_type)
    for field, meta in mapping.items():
        # Check presence
        if field not in instance:
            errors.append(f"Missing field '{field}' in {entity_type}")
            continue
        # Check value set if coded
        if 'allowed_values' in meta:
            val = instance[field]
            allowed = [v['term'] for v in meta['allowed_values']]
            if isinstance(val, list):
                for v in val:
                    if v not in allowed:
                        errors.append(f"Invalid value '{v}' for '{field}' in {entity_type}. Allowed: {allowed}")
            else:
                if val not in allowed:
                    errors.append(f"Invalid value '{val}' for '{field}' in {entity_type}. Allowed: {allowed}")

# Recursively validate SoA JSON structure

def validate_soa_json(soa_json: dict) -> list:
    errors = []
    # Study
    validate_entity("Study", soa_json, errors)
    for sv in soa_json.get("studyVersions", []):
        validate_entity("StudyVersion", sv, errors)
        sd = sv.get("studyDesign", {})
        timeline = sd.get("timeline", {})
        validate_entity("Timeline", timeline, errors)
        # PlannedTimepoints
        for pt in timeline.get("plannedTimepoints", []):
            validate_entity("PlannedTimepoint", pt, errors)
        # Activities
        for act in timeline.get("activities", []):
            validate_entity("Activity", act, errors)
        # ActivityGroups
        for ag in timeline.get("activityGroups", []):
            validate_entity("ActivityGroup", ag, errors)
        # ActivityTimepoints
        for atp in timeline.get("activityTimepoints", []):
            validate_entity("ActivityTimepoint", atp, errors)
    return errors

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python soa_extraction_validator.py <soa_file.json>")
        exit(1)
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        soa = json.load(f)
    errs = validate_soa_json(soa)
    if errs:
        print("[VALIDATION ERRORS]")
        for e in errs:
            print("-", e)
        exit(2)
    else:
        print("[SUCCESS] SoA JSON passes entity/attribute/value set validation.")
