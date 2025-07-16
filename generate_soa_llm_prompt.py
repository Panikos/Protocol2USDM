import json
import os
from pathlib import Path
import argparse

NAMING_RULE = (
    "**Naming vs. Timing Rule**\n\n"
    "For every visit you must output **two linked objects**: an `Encounter` and a `PlannedTimepoint` (PT).\n\n"
    "1. `Encounter.name` **and** `PlannedTimepoint.name` **must be identical** and contain ONLY the visit label — e.g., `\"Visit 1\"`. **Do NOT** include timing details such as weeks or days.\n"
    "2. Put timing information (e.g., `\"Week -2\"`, `\"Day 1 ±2\"`) in *exactly one* of these places:\n"
    "   • Preferred: `Encounter.timing.windowLabel` (and use `timing.windowLower/Upper` if you have numeric bounds).\n"
    "   • Acceptable fallback: `PlannedTimepoint.description` if a window label is not applicable.\n"
    "3. Never repeat the timing text inside the `name` field.\n")

MAPPING_PATH = "soa_entity_mapping.json"

MINI_EXAMPLE = (
    "**Mini Example (correct split):**\n\n"
    "Encounter snippet\n"
    "```json\n"
    "{ \"id\": \"enc-1\", \"name\": \"Visit 1\",\n"
    "  \"timing\": { \"windowLabel\": \"Week -2\" } }\n"
    "```\n\n"
    "Linked PlannedTimepoint snippet\n"
    "```json\n"
    "{ \"id\": \"pt-1\", \"encounterId\": \"enc-1\",\n"
    "  \"name\": \"Visit 1\", \"description\": \"Week -2\" }\n"
    "```\n")

# Full prompt template (kept for reference / future use)
FULL_PROMPT_TEMPLATE = """
You are an expert at extracting structured data from clinical trial protocols.
Your task is to extract the Schedule of Activities (SoA) and return it as a JSON object graph conforming to the USDM v4.0 model.

**IMPORTANT INSTRUCTIONS:**

1.  **Analyze and Classify the Study Design:** First, determine if the study is an **Interventional** or **Observational** study based on the protocol description.
2.  **Generate the Correct StudyDesign Object:** The `study.versions[0].studyDesigns` array must contain exactly ONE study design object. Based on your classification, you MUST generate either an `InterventionalStudyDesign` or an `ObservationalStudyDesign` object.

    *   **If Interventional:**
        *   Set `instanceType` to `InterventionalStudyDesign`.
        *   You MUST include the `trialType` attribute.
        *   Only include the fields listed below for `InterventionalStudyDesign`.

    *   **If Observational:**
        *   Set `instanceType` to `ObservationalStudyDesign`.
        *   You MUST include the `observationalStudyModel` attribute.
        *   Only include the fields listed below for `ObservationalStudyDesign`.

3.  **Adhere to the Schema:** For all other entities, use the fields and allowed values specified below.

**Schema Definitions:**

{entity_instructions}

{naming_rule}

{mini_example}

**Output Rules:**

- Use unique IDs for all cross-referencing.
- The output MUST be a single JSON object that exactly matches the **Wrapper-Input** schema (top-level keys: `study`, `usdmVersion`).
- The `studyDesigns` object must also contain the `epochs` array. The `epochs` array should contain `StudyEpoch` objects. `StudyEpoch` objects contain `encounters`, which in turn contain `plannedTimepoints`. The `timeline` object should still contain the full list of `activities`.
- Include empty arrays/objects for any optional fields that are not present in the protocol.
- Set `usdmVersion` to `4.0.0`.
- Your final output must be ONLY the valid JSON object, with no explanations, comments, or markdown. The entire string you return must be directly consumable by `json.loads()`.
"""

# Lean prompt template focused only on SoA timeline extraction, updated with better entity descriptions.
MINIMAL_PROMPT_TEMPLATE = """
You are an expert at extracting the Schedule of Activities (SoA) from a clinical trial protocol and converting it to a structured JSON object compliant with USDM v4.0.

Your task is to analyze the provided SoA table(s) and generate a JSON object containing the full timeline of study events.

**Key Concepts and Entity Relationships:**

The SoA is structured around a few core entities. Understanding their relationships is crucial for correct extraction:

*   **Epochs:** These are the major phases of the study (e.g., Screening, Treatment, Follow-up).
*   **Encounters:** These represent the specific visits or time windows within an Epoch (e.g., "Screening Visit", "Week 4 Visit").
*   **PlannedTimepoints:** These are the precise moments or intervals when activities happen. They are often linked to Encounters. (e.g., "Day 1", "Week 4").
*   **Activities:** These are the individual procedures or assessments performed (e.g., "Physical Exam", "Blood Draw").
*   **ActivityTimepoints:** This is the mapping that links an Activity to a PlannedTimepoint, indicating *what* happens *when*.
*   **ActivityGroups:** These are optional groupings for related activities (e.g., "Vital Signs"). When an activity belongs to a group, you **MUST** set the `activityGroupId` field on the Activity object to the ID of the corresponding ActivityGroup.

{naming_rule}

{mini_example}

**Your Task:**

Based on the protocol text, identify all instances of these entities and their relationships.

**Example Output Format:**

To ensure you produce the correct output, here is a small, valid example of the JSON structure. Your output MUST follow this format exactly.

```json
{json_example}
```

**Detailed Schema Definitions:**

Below are the specific fields you must use for each entity. Do not invent new fields or entity types.

{entity_instructions}

**Output Rules:**

1.  **JSON Only:** Your entire output MUST be a single, valid JSON object. Do not include any explanatory text, markdown formatting, or comments outside of the JSON structure.
2.  **Schema Conformance:** The JSON must conform to the **Wrapper-Input** schema.
    *   Top-level keys must be `study` and `usdmVersion` (set to "4.0.0").
    *   The `study` object must contain a `versions` array, which in turn contains a `timeline` object.
3.  **Completeness:** Include all activities, timepoints, and groupings shown in the SoA table. If a piece of information is not present, you may use an empty array (`[]`).
4.  **Unique IDs:** Ensure all `id` fields are unique within the document so they can be used for cross-referencing.
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
                    required_text = " (required)" if meta.get('required') else ""
                    lines.append(f"  - {field} [{meta.get('role', section)}]{allowed}{required_text}")
        lines.append("")
    return '\n'.join(lines)

# Entities that are strictly required for the SoA timeline
SOA_CORE_ENTITIES = {
    "Activity",
    "PlannedTimepoint",
    "ActivityGroup",
    "ActivityTimepoint",
    "Encounter",
    "Epoch",
    "StudyArm",
    "StudyElement"
}

# Simple grouping heuristic – can be made data-driven later
ENTITY_GROUPS = {
    "soa_core": set(SOA_CORE_ENTITIES),
    "study_design": {
        "StudyVersion",
        "InterventionalStudyDesign",
        "ObservationalStudyDesign",
        "StudyEpoch",
        "Encounter"
    },
    "interventions": {
        "Administration",
        "AdministrableProduct",
        "MedicalDevice",
        "Substance"
    },
    "eligibility": {
        "EligibilityCriterion",
        "EligibilityCriterionItem",
        "EligibilityCriterionGroup"
    }
}

def filter_mapping(mapping, allowed_entities):
    """Return a copy of mapping containing only the allowed entities."""
    return {k: v for k, v in mapping.items() if k in allowed_entities}

def write_prompt(path: Path, template: str, **kwargs):
    path.write_text(template.format(**kwargs), encoding="utf-8")
    print(f"[PROMPT] Wrote {path}")

def main():
    parser = argparse.ArgumentParser(description="Generate LLM prompts from the SoA entity mapping.")
    parser.add_argument("--output", default="output/1_llm_prompt.txt", help="Path to write the minimal SoA prompt file.")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # Define paths for other generated files based on the primary output path
    full_prompt_path = output_dir / "1_llm_prompt_full.txt"
    groups_path = output_dir / "1_llm_entity_groups.json"

    with open(MAPPING_PATH, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    # --- Load the one-shot example ---
    example_path = Path("soa_prompt_example.json")
    if not example_path.exists():
        raise FileNotFoundError(f"Could not find the prompt example file at {example_path}")
    example_json_str = example_path.read_text(encoding="utf-8")

    # --- write minimal SoA prompt ---
    minimal_mapping = filter_mapping(mapping, SOA_CORE_ENTITIES)
    minimal_instr = generate_entity_instructions(minimal_mapping)
    write_prompt(output_path, MINIMAL_PROMPT_TEMPLATE, entity_instructions=minimal_instr, json_example=example_json_str, naming_rule=NAMING_RULE, mini_example=MINI_EXAMPLE)

    # --- keep full prompt for future richer extraction steps (doesn't need the example) ---
    full_instr = generate_entity_instructions(mapping)
    write_prompt(full_prompt_path, FULL_PROMPT_TEMPLATE, entity_instructions=full_instr, naming_rule=NAMING_RULE, mini_example=MINI_EXAMPLE)

    # --- write grouped entity catalogue ---
    grouped = {}
    for group, ents in ENTITY_GROUPS.items():
        grouped[group] = {e: mapping[e] for e in ents if e in mapping}
    # anything not assigned already
    other = {k: v for k, v in mapping.items() if all(k not in gset for gset in ENTITY_GROUPS.values())}
    grouped["other"] = other
    with open(groups_path, "w", encoding="utf-8") as gf:
        json.dump(grouped, gf, indent=2)
    print(f"[SUCCESS] Wrote grouped entity definitions to {groups_path}")

if __name__ == "__main__":
    main()
