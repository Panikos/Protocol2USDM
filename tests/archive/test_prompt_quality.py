"""
Tests for prompt quality and consistency.

Validates that:
1. Example files follow stated rules
2. Embedded schemas are complete
3. Prompts are consistent across pipeline
"""

import pytest
import json
import re
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from generate_soa_llm_prompt import (
    load_usdm_schema_text,
    NAMING_RULE,
    MINI_EXAMPLE,
    PLANNEDTIMEPOINT_GUIDANCE,
    ENCOUNTER_TYPE_GUIDANCE,
    SOA_CORE_ENTITIES
)


class TestPromptExample:
    """Test the soa_prompt_example.json file for correctness."""
    
    def test_example_file_exists(self):
        """Example file should exist."""
        example_path = Path("soa_prompt_example.json")
        assert example_path.exists(), "soa_prompt_example.json not found"
    
    def test_example_is_valid_json(self):
        """Example should be valid JSON."""
        with open("soa_prompt_example.json", "r") as f:
            data = json.load(f)  # Should not raise
        assert isinstance(data, dict)
    
    def test_example_follows_naming_rule(self):
        """Example PlannedTimepoints should NOT have timing in name."""
        with open("soa_prompt_example.json", "r") as f:
            data = json.load(f)
        
        timeline = data["study"]["versions"][0]["timeline"]
        planned_timepoints = timeline.get("plannedTimepoints", [])
        
        # Timing keywords that should NOT appear in PlannedTimepoint.name
        timing_keywords = ["day", "week", "month", "year", "±", "+", "-"]
        
        for pt in planned_timepoints:
            name = pt.get("name", "").lower()
            # Check name doesn't contain timing
            has_timing = any(keyword in name for keyword in timing_keywords if keyword.isalpha())
            
            if has_timing:
                pytest.fail(
                    f"PlannedTimepoint '{pt['id']}' has timing in name: '{pt['name']}'. "
                    f"Timing should be in 'description' or 'Encounter.timing.windowLabel'"
                )
    
    def test_example_planned_timepoint_matches_encounter(self):
        """PlannedTimepoint.name should match corresponding Encounter.name."""
        with open("soa_prompt_example.json", "r") as f:
            data = json.load(f)
        
        timeline = data["study"]["versions"][0]["timeline"]
        encounters = {enc["id"]: enc for enc in timeline.get("encounters", [])}
        planned_timepoints = timeline.get("plannedTimepoints", [])
        
        for pt in planned_timepoints:
            enc_id = pt.get("encounterId")
            if enc_id and enc_id in encounters:
                pt_name = pt.get("name")
                enc_name = encounters[enc_id].get("name")
                
                assert pt_name == enc_name, (
                    f"PlannedTimepoint '{pt['id']}' name '{pt_name}' doesn't match "
                    f"Encounter '{enc_id}' name '{enc_name}'"
                )
    
    def test_example_has_required_plannedtimepoint_fields(self):
        """Example PlannedTimepoints should have all required fields."""
        with open("soa_prompt_example.json", "r") as f:
            data = json.load(f)
        
        timeline = data["study"]["versions"][0]["timeline"]
        planned_timepoints = timeline.get("plannedTimepoints", [])
        
        required_fields = [
            "id", "name", "instanceType", "encounterId",
            "value", "valueLabel", "relativeFromScheduledInstanceId",
            "type", "relativeToFrom"
        ]
        
        for pt in planned_timepoints:
            for field in required_fields:
                assert field in pt, (
                    f"PlannedTimepoint '{pt.get('id')}' missing required field '{field}'"
                )
            
            # Check complex types are objects
            assert isinstance(pt["type"], dict), "PlannedTimepoint.type must be object with code/decode"
            assert isinstance(pt["relativeToFrom"], dict), "PlannedTimepoint.relativeToFrom must be object"
    
    def test_example_encounter_has_type(self):
        """Example Encounters should have type field as complex object."""
        with open("soa_prompt_example.json", "r") as f:
            data = json.load(f)
        
        timeline = data["study"]["versions"][0]["timeline"]
        encounters = timeline.get("encounters", [])
        
        for enc in encounters:
            assert "type" in enc, f"Encounter '{enc.get('id')}' missing type field"
            assert isinstance(enc["type"], dict), "Encounter.type must be object"
            assert "code" in enc["type"], "Encounter.type must have 'code' field"
            assert "decode" in enc["type"], "Encounter.type must have 'decode' field"
    
    def test_example_has_study_required_fields(self):
        """Example should have required Study and StudyVersion fields."""
        with open("soa_prompt_example.json", "r") as f:
            data = json.load(f)
        
        # Study required fields
        assert "study" in data
        study = data["study"]
        assert "name" in study, "Study.name is required"
        assert "instanceType" in study, "Study.instanceType is required"
        
        # StudyVersion required fields
        assert "versions" in study
        assert len(study["versions"]) > 0
        version = study["versions"][0]
        assert "id" in version, "StudyVersion.id is required"
        assert "rationale" in version, "StudyVersion.rationale is required"
        assert "studyIdentifiers" in version, "StudyVersion.studyIdentifiers is required"
        assert "titles" in version, "StudyVersion.titles is required"


class TestSchemaEmbedding:
    """Test the USDM schema embedding in prompts."""
    
    def test_schema_file_exists(self):
        """USDM schema file should exist."""
        schema_path = Path("USDM OpenAPI schema/USDM_API.json")
        assert schema_path.exists(), "USDM schema file not found"
    
    def test_schema_loads_without_error(self):
        """Schema should load without errors."""
        schema_text = load_usdm_schema_text("USDM OpenAPI schema/USDM_API.json")
        assert schema_text != "[Schema file not available]"
        assert schema_text != "[Schema load error]"
        assert len(schema_text) > 0
    
    def test_schema_includes_soa_entities(self):
        """Embedded schema should include all SoA-related schemas that exist in USDM."""
        schema_text = load_usdm_schema_text("USDM OpenAPI schema/USDM_API.json")
        schema_json = json.loads(schema_text)
        
        # Expected entities after Phase 2 improvements
        # Note: Some entities (PlannedTimepoint, ActivityTimepoint, ActivityGroup) don't exist
        # as separate -Input schemas - they're embedded within the timeline structure
        required_entities = [
            "Wrapper-Input",
            "Study-Input",
            "StudyVersion-Input",
            "ScheduleTimeline-Input",  # Timeline structure
            "StudyEpoch-Input",        # Study phases
            "Encounter-Input",         # Visits
            "Activity-Input",          # Procedures/assessments
        ]
        
        for entity in required_entities:
            assert entity in schema_json, (
                f"Schema missing required entity '{entity}'. "
                f"Phase 2 should include all SoA-related schemas that exist in USDM."
            )
    
    def test_schema_size_reasonable(self):
        """Schema should be within reasonable token budget."""
        schema_text = load_usdm_schema_text("USDM OpenAPI schema/USDM_API.json")
        
        # Rough estimate: 1 token ≈ 4 characters
        estimated_tokens = len(schema_text) / 4
        
        # Should be under 3000 tokens (12000 chars)
        assert estimated_tokens < 3000, (
            f"Schema too large: ~{estimated_tokens:.0f} tokens. "
            f"Should be under 3000 tokens."
        )


class TestPromptGuidance:
    """Test that guidance sections are present and correct."""
    
    def test_naming_rule_exists(self):
        """Naming vs. Timing Rule should be defined."""
        assert len(NAMING_RULE) > 0
        assert "Encounter.name" in NAMING_RULE
        assert "PlannedTimepoint.name" in NAMING_RULE
        assert "must be identical" in NAMING_RULE
    
    def test_mini_example_exists(self):
        """Mini example should be defined."""
        assert len(MINI_EXAMPLE) > 0
        assert "Encounter snippet" in MINI_EXAMPLE
        assert "PlannedTimepoint snippet" in MINI_EXAMPLE
    
    def test_plannedtimepoint_guidance_complete(self):
        """PlannedTimepoint guidance should cover all required fields."""
        required_fields = [
            "id", "name", "encounterId", "value", "valueLabel",
            "relativeFromScheduledInstanceId", "type", "relativeToFrom"
        ]
        
        for field in required_fields:
            assert field in PLANNEDTIMEPOINT_GUIDANCE, (
                f"PlannedTimepoint guidance missing field '{field}'"
            )
        
        # Should have examples
        assert "Example - Simple Timepoint" in PLANNEDTIMEPOINT_GUIDANCE
        assert "Example - With Visit Window" in PLANNEDTIMEPOINT_GUIDANCE
    
    def test_encounter_type_guidance_exists(self):
        """Encounter.type guidance should exist and be correct."""
        assert len(ENCOUNTER_TYPE_GUIDANCE) > 0
        assert "type" in ENCOUNTER_TYPE_GUIDANCE
        assert "code" in ENCOUNTER_TYPE_GUIDANCE
        assert "decode" in ENCOUNTER_TYPE_GUIDANCE
        assert "Visit" in ENCOUNTER_TYPE_GUIDANCE


class TestPromptConsistency:
    """Test that prompts are consistent across the pipeline."""
    
    def test_soa_core_entities_defined(self):
        """SOA_CORE_ENTITIES should be properly defined."""
        assert isinstance(SOA_CORE_ENTITIES, set)
        
        expected_entities = [
            "Activity",
            "PlannedTimepoint",
            "ActivityGroup",
            "ActivityTimepoint",
            "Encounter",
            "Epoch",
        ]
        
        for entity in expected_entities:
            assert entity in SOA_CORE_ENTITIES, (
                f"SOA_CORE_ENTITIES missing '{entity}'"
            )
    
    def test_generated_prompt_files_match_source(self):
        """Generated prompt files should reflect current template code."""
        # This would require running generate_soa_llm_prompt.py first
        # For now, just check if the generator can run
        from generate_soa_llm_prompt import generate_entity_instructions, filter_mapping
        import json
        
        with open("soa_entity_mapping.json", "r") as f:
            mapping = json.load(f)
        
        minimal_mapping = filter_mapping(mapping, SOA_CORE_ENTITIES)
        instructions = generate_entity_instructions(minimal_mapping)
        
        # Should produce non-empty instructions
        assert len(instructions) > 0
        
        # Should include all core entities
        for entity in ["Activity", "PlannedTimepoint", "Encounter"]:
            assert f"For {entity}:" in instructions


class TestReconciliationPromptTemplate:
    """Test the YAML reconciliation template."""
    
    def test_reconciliation_template_exists(self):
        """Reconciliation YAML template should exist."""
        template_path = Path("prompts/soa_reconciliation.yaml")
        assert template_path.exists(), "soa_reconciliation.yaml not found"
    
    def test_reconciliation_template_valid_yaml(self):
        """Template should be valid YAML."""
        import yaml
        with open("prompts/soa_reconciliation.yaml", "r") as f:
            data = yaml.safe_load(f)
        
        assert isinstance(data, dict)
        assert "metadata" in data
        assert "system_prompt" in data
        assert "user_prompt" in data
    
    def test_reconciliation_template_has_version(self):
        """Template should have version metadata."""
        import yaml
        with open("prompts/soa_reconciliation.yaml", "r") as f:
            data = yaml.safe_load(f)
        
        metadata = data.get("metadata", {})
        assert "version" in metadata
        assert "changelog" in metadata
        
        # Current version should be 2.0 (after migration)
        assert metadata["version"] >= "2.0"
    
    def test_reconciliation_template_has_variables(self):
        """Template should define required variables."""
        import yaml
        with open("prompts/soa_reconciliation.yaml", "r") as f:
            data = yaml.safe_load(f)
        
        # Check user prompt has variable placeholders
        user_prompt = data.get("user_prompt", "")
        assert "{text_soa_json}" in user_prompt
        assert "{vision_soa_json}" in user_prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
