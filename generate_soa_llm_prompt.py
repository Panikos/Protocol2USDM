import json

MAPPING_PATH = "soa_entity_mapping.json"

PROMPT_TEMPLATE = """
You are an expert at extracting structured data from clinical trial protocols.
Extract the Schedule of Activities (SoA) and return it as a JSON object graph conforming to the USDM v4.0 model.
For each entity, use the following fields and allowed values (if specified):

{entity_instructions}

- Use unique IDs for cross-referencing.
- Only include objects and fields as described.
- Use the study name from the protocol for 'name'.
- Output ONLY valid JSON, with no explanations, comments, or markdown.
"""

def generate_entity_instructions(mapping):
    lines = []
    for entity, sections in mapping.items():
        lines.append(f"For {entity}:")
        for section in ["attributes", "relationships", "complex_datatype_relationships"]:
            if section in sections:
                for field, meta in sections[section].items():
                    allowed = ""
                    if 'allowed_values' in meta and meta['allowed_values']:
                        allowed_vals = ', '.join(f"{v['term']}" for v in meta['allowed_values'])
                        allowed = f" (allowed: {allowed_vals})"
                    lines.append(f"  - {field} [{meta.get('role', section)}]{allowed}")
        lines.append("")
    return '\n'.join(lines)

def main():
    with open(MAPPING_PATH, "r", encoding="utf-8") as f:
        mapping = json.load(f)
    entity_instructions = generate_entity_instructions(mapping)
    prompt = PROMPT_TEMPLATE.format(entity_instructions=entity_instructions)
    with open("llm_soa_prompt.txt", "w", encoding="utf-8") as outf:
        outf.write(prompt)
    print("[SUCCESS] Wrote LLM prompt to llm_soa_prompt.txt")

if __name__ == "__main__":
    main()
