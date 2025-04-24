import json
import sys
from jsonschema import validate, ValidationError

# Usage: python validate_usdm_json.py <usdm_schema.json> <soa_file.json>
if len(sys.argv) != 3:
    print("Usage: python validate_usdm_json.py <usdm_schema.json> <soa_file.json>")
    sys.exit(1)

schema_path, soa_path = sys.argv[1], sys.argv[2]

with open(schema_path, 'r', encoding='utf-8') as f:
    schema = json.load(f)
with open(soa_path, 'r', encoding='utf-8') as f:
    soa = json.load(f)

try:
    validate(instance=soa, schema=schema["components"]["schemas"]["Study"])
    print("[SUCCESS] JSON is valid against USDM schema.")
except ValidationError as e:
    print(f"[ERROR] JSON validation error: {e.message}")
    sys.exit(2)
