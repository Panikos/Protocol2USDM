"""
Schema-Driven Prompt Generator

Generates LLM prompts and entity definitions directly from the official CDISC dataStructure.yml.
This ensures prompts always match the official schema and include accurate:
- NCI codes and definitions
- Required/optional field indicators
- Cardinality constraints
- Relationship types

Usage:
    from core.schema_prompt_generator import SchemaPromptGenerator
    
    generator = SchemaPromptGenerator()
    prompt = generator.generate_soa_prompt()
    entity_groups = generator.generate_entity_groups()
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field

from .usdm_schema_loader import (
    USDMSchemaLoader, EntityDefinition, AttributeDefinition,
    get_schema_loader
)


# Entity groupings for different extraction tasks
ENTITY_GROUPS = {
    "soa_core": {
        "Activity",
        "Encounter", 
        "StudyEpoch",
        "ScheduleTimeline",
        "ScheduledActivityInstance",
        "Timing",
        "StudyArm",
    },
    "study_design": {
        "Study",
        "StudyVersion",
        "StudyDesign",
        "InterventionalStudyDesign",
        "ObservationalStudyDesign",
        "StudyCell",
    },
    "eligibility": {
        "EligibilityCriterion",
        "EligibilityCriterionItem",
        "StudyDesignPopulation",
    },
    "objectives": {
        "Objective",
        "Endpoint",
        "Estimand",
        "IntercurrentEvent",
    },
    "interventions": {
        "StudyIntervention",
        "Administration",
        "AdministrableProduct",
        "Procedure",
    },
    "metadata": {
        "StudyTitle",
        "StudyIdentifier",
        "Organization",
        "Indication",
        "Abbreviation",
    },
    "core_types": {
        "Code",
        "AliasCode",
        "CommentAnnotation",
        "Duration",
        "Quantity",
        "Range",
    },
}


@dataclass
class PromptEntityDefinition:
    """Entity definition formatted for LLM prompts."""
    name: str
    nci_code: Optional[str]
    definition: Optional[str]
    attributes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    relationships: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    complex_datatype_relationships: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "definition": self.definition or f"A USDM {self.name} entity.",
        }
        if self.nci_code:
            result["nci_code"] = self.nci_code
        if self.attributes:
            result["attributes"] = self.attributes
        if self.relationships:
            result["relationships"] = self.relationships
        if self.complex_datatype_relationships:
            result["complex_datatype_relationships"] = self.complex_datatype_relationships
        return result


class SchemaPromptGenerator:
    """Generates LLM prompts from the official USDM schema."""
    
    def __init__(self, schema_loader: Optional[USDMSchemaLoader] = None):
        self.loader = schema_loader or get_schema_loader()
        self._entities: Dict[str, EntityDefinition] = {}
        
    def _ensure_loaded(self):
        if not self._entities:
            self._entities = self.loader.load()
    
    def get_entity(self, name: str) -> Optional[EntityDefinition]:
        """Get entity definition by name."""
        self._ensure_loaded()
        return self._entities.get(name)
    
    def convert_to_prompt_format(self, entity: EntityDefinition) -> PromptEntityDefinition:
        """Convert EntityDefinition to prompt-friendly format."""
        attributes = {}
        relationships = {}
        complex_relationships = {}
        
        for attr_name, attr in entity.attributes.items():
            attr_dict = {
                "name": attr_name,
                "role": "Attribute" if not attr.is_reference else "Reference",
                "required": attr.is_required,
            }
            if attr.nci_code:
                attr_dict["c_code"] = attr.nci_code
            if attr.definition:
                attr_dict["definition"] = attr.definition
            if attr.is_list:
                attr_dict["cardinality"] = "0..*" if not attr.is_required else "1..*"
            
            # Categorize based on type
            type_ref = attr.type_ref.replace('#/', '')
            if type_ref in ['Code', 'AliasCode', 'CommentAnnotation', 'Duration', 'Quantity']:
                complex_relationships[attr_name] = attr_dict
                attr_dict["role"] = "Complex Datatype Relationship"
            elif attr.is_reference:
                relationships[attr_name] = attr_dict
                attr_dict["role"] = "Relationship"
            else:
                attributes[attr_name] = attr_dict
        
        return PromptEntityDefinition(
            name=entity.name,
            nci_code=entity.nci_code,
            definition=entity.definition,
            attributes=attributes,
            relationships=relationships,
            complex_datatype_relationships=complex_relationships,
        )
    
    def generate_entity_instructions(self, entity_names: Optional[Set[str]] = None) -> str:
        """Generate entity instruction text for LLM prompts."""
        self._ensure_loaded()
        
        lines = []
        entities_to_include = entity_names or set(self._entities.keys())
        
        for name in sorted(entities_to_include):
            entity = self._entities.get(name)
            if not entity:
                continue
            
            # Header with NCI code
            header = f"For {name}:"
            if entity.nci_code:
                header = f"For {name} (NCI: {entity.nci_code}):"
            lines.append(header)
            
            # Definition if available
            if entity.definition:
                lines.append(f"  Definition: {entity.definition[:200]}...")
            
            # Attributes
            for attr_name, attr in entity.attributes.items():
                req = " (required)" if attr.is_required else ""
                role = attr.relationship_type if attr.is_reference else "Attribute"
                
                # Add definition hint if available
                hint = ""
                if attr.definition:
                    hint = f" - {attr.definition[:80]}..."
                
                lines.append(f"  - {attr_name} [{role}]{req}{hint}")
            
            lines.append("")
        
        return '\n'.join(lines)
    
    def generate_entity_groups(self) -> Dict[str, Dict[str, Any]]:
        """Generate entity groups JSON (replaces soa_entity_mapping.json)."""
        self._ensure_loaded()
        
        result = {}
        assigned = set()
        
        # Process defined groups
        for group_name, entity_names in ENTITY_GROUPS.items():
            group_entities = {}
            for name in entity_names:
                entity = self._entities.get(name)
                if entity:
                    prompt_entity = self.convert_to_prompt_format(entity)
                    group_entities[name] = prompt_entity.to_dict()
                    assigned.add(name)
            if group_entities:
                result[group_name] = group_entities
        
        # Add unassigned entities to "other"
        other = {}
        for name, entity in self._entities.items():
            if name not in assigned and not entity.is_abstract:
                prompt_entity = self.convert_to_prompt_format(entity)
                other[name] = prompt_entity.to_dict()
        
        if other:
            result["other"] = other
        
        return result
    
    def generate_soa_prompt(self) -> str:
        """Generate the main SoA extraction prompt."""
        self._ensure_loaded()
        
        # Core SoA entities
        soa_entities = ENTITY_GROUPS["soa_core"]
        entity_instructions = self.generate_entity_instructions(soa_entities)
        
        prompt = f"""You are an expert at extracting the Schedule of Activities (SoA) from a clinical trial protocol and converting it to a structured JSON object compliant with USDM v4.0.

Your task is to analyze the provided SoA table(s) and generate a JSON object containing the full timeline of study events.

**Key Concepts and Entity Relationships (from official CDISC USDM v4.0):**

The SoA is structured around these core entities:

*   **StudyEpoch:** Major phases of the study (e.g., Screening, Treatment, Follow-up). Each has a required `type` field.
*   **Encounter:** Specific visits or time windows within an Epoch. Each has a required `type` field.
*   **Activity:** Individual procedures or assessments performed (e.g., "Physical Exam", "Blood Draw").
*   **ScheduledActivityInstance:** Links an Activity to an Encounter, indicating what happens when.
*   **ScheduleTimeline:** Container for all ScheduledActivityInstances. Requires `entryCondition` and `entryId`.
*   **StudyArm:** Treatment arms. Requires `type`, `dataOriginType`, and `dataOriginDescription`.

**CRITICAL SCHEMA REQUIREMENTS:**

1. Every entity MUST have `id` and `instanceType` fields.
2. All `Code` objects MUST have: `id`, `code`, `codeSystem`, `codeSystemVersion`, `decode`, `instanceType`.
3. `Encounter.type` and `StudyEpoch.type` are REQUIRED - infer from name if not specified.
4. `StudyArm` requires: `type`, `dataOriginType`, `dataOriginDescription`.

**Detailed Schema Definitions (from official dataStructure.yml):**

{entity_instructions}

**OUTPUT FORMAT:**

Return a single JSON object with this structure:
```json
{{
  "study": {{
    "id": "study_1",
    "name": "Study Name",
    "instanceType": "Study",
    "versions": [{{
      "id": "sv_1",
      "versionIdentifier": "1.0",
      "rationale": "Initial version",
      "instanceType": "StudyVersion",
      "studyDesigns": [{{
        "id": "sd_1",
        "name": "Study Design",
        "instanceType": "InterventionalStudyDesign",
        "arms": [...],
        "epochs": [...],
        "encounters": [...],
        "activities": [...],
        "scheduleTimelines": [{{
          "id": "timeline_1",
          "name": "Main Timeline",
          "entryCondition": "Subject enrolled",
          "entryId": "first_instance_id",
          "instanceType": "ScheduleTimeline",
          "instances": [...]
        }}]
      }}]
    }}]
  }},
  "usdmVersion": "4.0.0"
}}
```

**HARD CONSTRAINTS:**
- All entities must derive from the provided SoA table - do not hallucinate.
- For ScheduledActivityInstances, only create entries where the SoA cell has a visible tick/marker.
- If information is ambiguous, omit rather than guess.
"""
        return prompt
    
    def generate_full_prompt(self) -> str:
        """Generate a comprehensive prompt with all entity definitions."""
        self._ensure_loaded()
        
        # All non-abstract entities
        all_entities = {name for name, e in self._entities.items() if not e.is_abstract}
        entity_instructions = self.generate_entity_instructions(all_entities)
        
        prompt = f"""You are an expert at extracting structured data from clinical trial protocols.
Your task is to extract the Schedule of Activities (SoA) and return it as a JSON object graph conforming to the USDM v4.0 model.

**IMPORTANT INSTRUCTIONS:**

1.  **Analyze and Classify the Study Design:** First, determine if the study is an **Interventional** or **Observational** study based on the protocol description.
2.  **Generate the Correct StudyDesign Object:** The `study.versions[0].studyDesigns` array must contain exactly ONE study design object.

    *   **If Interventional:** Set `instanceType` to `InterventionalStudyDesign`.
    *   **If Observational:** Set `instanceType` to `ObservationalStudyDesign`.

3.  **Adhere to the Schema:** Use the fields and constraints specified below.

**Schema Definitions (from official CDISC dataStructure.yml):**

{entity_instructions}

**CRITICAL REQUIREMENTS:**
- Every entity MUST have `id` and `instanceType` fields
- All Code objects MUST include: id, code, codeSystem, codeSystemVersion, decode, instanceType
- Required fields for complex types:
  - StudyArm: type, dataOriginType, dataOriginDescription
  - Encounter: type
  - StudyEpoch: type
  - ScheduleTimeline: entryCondition, entryId
  - AliasCode: standardCode

**OUTPUT:**
Return exactly one JSON object conforming to the USDM Wrapper-Input schema.
"""
        return prompt
    
    def save_entity_groups(self, output_path: str):
        """Save entity groups to JSON file."""
        groups = self.generate_entity_groups()
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(groups, f, indent=2)
        print(f"[SUCCESS] Saved entity groups to {output_path}")
    
    def save_prompt(self, output_path: str, full: bool = False):
        """Save prompt to text file."""
        prompt = self.generate_full_prompt() if full else self.generate_soa_prompt()
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(prompt)
        print(f"[SUCCESS] Saved prompt to {output_path}")


def generate_all_prompts(output_dir: str = "output"):
    """Generate all prompt files from the official schema."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    generator = SchemaPromptGenerator()
    
    # Generate files
    generator.save_prompt(output_path / "1_llm_prompt.txt", full=False)
    generator.save_prompt(output_path / "1_llm_prompt_full.txt", full=True)
    generator.save_entity_groups(output_path / "1_llm_entity_groups.json")
    
    print(f"\n[INFO] Generated prompts from official CDISC schema v4.0")
    print(f"[INFO] Source: {generator.loader.schema_path}")


if __name__ == "__main__":
    generate_all_prompts()
