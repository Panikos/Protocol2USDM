import sys
import os
import json
import yaml
from openapi_schema_validator import validate

# Path to the OpenAPI schema (JSON or YAML)
SCHEMA_PATH = os.path.join("USDM OpenAPI schema", "USDM_API.json")

# Path to the file to validate (default: soa_text.json)
if len(sys.argv) > 1:
    DATA_PATH = sys.argv[1]
else:
    DATA_PATH = "soa_text.json"

# Load the OpenAPI schema
def load_schema(path):
    with open(path, 'r', encoding='utf-8') as f:
        if path.endswith('.yaml') or path.endswith('.yml'):
            return yaml.safe_load(f)
        else:
            return json.load(f)

# Load the data to validate
def load_data(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

if __name__ == "__main__":
    schema = load_schema(SCHEMA_PATH)
    data = load_data(DATA_PATH)

    # Try to get the requestBody schema for /v3/studyDefinitions POST
    try:
        req_schema = schema["paths"]["/v3/studyDefinitions"]["post"]["requestBody"]["content"]["application/json"]["schema"]
        # If the schema is a $ref, try to resolve it
        if "$ref" in req_schema:
            ref = req_schema["$ref"]
            # If the reference is missing, fallback to Study-Input
            if ref == "#/components/schemas/Wrapper-Input":
                req_schema = schema["components"]["schemas"]["Study-Input"]
            else:
                # Resolve the reference
                ref_path = ref.lstrip("#/").split("/")
                req_schema = schema
                for part in ref_path:
                    req_schema = req_schema[part]
    except Exception as e:
        print(f"Could not locate request schema in OpenAPI spec: {e}")
        sys.exit(1)

    # Validate
    try:
        validate(data, req_schema)
        print(f"SUCCESS: {DATA_PATH} is valid against the USDM OpenAPI schema.")
    except Exception as e:
        print(f"VALIDATION ERROR: {e}")
        sys.exit(1)
