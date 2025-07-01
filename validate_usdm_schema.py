import json
import argparse
import os
from openapi_schema_validator import OAS31Validator
from referencing import Registry
from referencing.jsonschema import DRAFT202012

# Load the USDM v4.0.0 OpenAPI schema
schema_dir = os.path.join(os.path.dirname(__file__), 'USDM OpenAPI schema')
with open(os.path.join(schema_dir, 'USDM_API.json'), 'r', encoding='utf-8') as f:
    USDM_SCHEMA = json.load(f)

# Inject permissive stub for missing Study-Input to support Wrapper validation without altering the official spec
schemas_dict = USDM_SCHEMA.setdefault('components', {}).setdefault('schemas', {})

def validate_json_against_schema(json_data, component_name):
    """Validate a JSON object against a specific component in the USDM schema."""
    try:
        # To allow the validator to resolve internal $refs (e.g., from Wrapper-Input to Study-Input),
        # we must provide it a schema that contains the full components dictionary.
        # We construct a temporary schema that references our target component and includes
        # the original schema's components block for resolution.

        # First, ensure the 'Study-Input' stub is present in the main schema's components
        # to prevent downstream PointerToNowhere errors, as it's not in the official spec.
        if 'Study-Input' not in USDM_SCHEMA.get('components', {}).get('schemas', {}):
            USDM_SCHEMA.setdefault('components', {}).setdefault('schemas', {})['Study-Input'] = {
                "title": "Study (Stub)",
                "type": "object",
                "description": "Stub inserted by validator to satisfy $ref. Accepts any properties.",
                "additionalProperties": True
            }

        # Now, build the temporary schema for this specific validation run.
        validation_schema = {
            "$ref": f"#/components/schemas/{component_name}",
            "components": USDM_SCHEMA.get('components', {})
        }

        # The validator can now resolve the top-level $ref against the 'components' key
        # in the same document.
        validator = OAS31Validator(validation_schema)

        # Perform the validation
        validator.validate(instance=json_data)

        print(f"[SUCCESS] Validation passed for component '{component_name}'.")
        return True
    except Exception as e:
        print(f"[ERROR] Schema validation failed for component '{component_name}': {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate a JSON file against the USDM OpenAPI schema.")
    parser.add_argument("json_file_path", help="Path to the JSON file to validate.")
    parser.add_argument("component_name", help="The name of the schema component to validate against (e.g., 'Wrapper-Input').")
    args = parser.parse_args()

    with open(args.json_file_path, 'r') as f:
        data_to_validate = json.load(f)

    if not validate_json_against_schema(data_to_validate, args.component_name):
        exit(1)
