"""
Tests for the new core/ module.

Run with: pytest tests/test_core_modules.py -v
"""

import pytest
import json
import os
import tempfile


class TestJsonUtils:
    """Tests for core.json_utils module."""
    
    def test_extract_json_str_direct(self):
        """Test direct JSON parsing."""
        from core.json_utils import extract_json_str
        
        result = extract_json_str('{"key": "value"}')
        assert result == '{"key": "value"}'
    
    def test_extract_json_str_with_fence(self):
        """Test JSON extraction from markdown fences."""
        from core.json_utils import extract_json_str
        
        input_text = '```json\n{"key": "value"}\n```'
        result = extract_json_str(input_text)
        assert result is not None
        assert "key" in result
    
    def test_extract_json_str_with_prose(self):
        """Test JSON extraction with leading prose."""
        from core.json_utils import extract_json_str
        
        input_text = 'Here is the result:\n{"data": 123}'
        result = extract_json_str(input_text)
        assert result is not None
        data = json.loads(result)
        assert data["data"] == 123
    
    def test_parse_llm_json_valid(self):
        """Test parsing valid JSON."""
        from core.json_utils import parse_llm_json
        
        result = parse_llm_json('{"key": "value"}')
        assert result == {"key": "value"}
    
    def test_parse_llm_json_with_fallback(self):
        """Test parsing invalid JSON with fallback."""
        from core.json_utils import parse_llm_json
        
        result = parse_llm_json('invalid json', fallback={"default": True})
        assert result == {"default": True}
    
    def test_standardize_ids(self):
        """Test ID standardization."""
        from core.json_utils import standardize_ids
        
        data = {"id": "act-1", "groupId": "grp-2", "name": "Test"}
        standardize_ids(data)
        assert data["id"] == "act_1"
        assert data["groupId"] == "grp_2"
        assert data["name"] == "Test"
    
    def test_standardize_ids_nested(self):
        """Test ID standardization in nested structures."""
        from core.json_utils import standardize_ids
        
        data = {
            "activities": [
                {"id": "act-1", "name": "Test"},
                {"id": "act-2", "groupId": "grp-1"}
            ]
        }
        standardize_ids(data)
        assert data["activities"][0]["id"] == "act_1"
        assert data["activities"][1]["groupId"] == "grp_1"
    
    def test_get_timeline(self):
        """Test timeline extraction from USDM structure."""
        from core.json_utils import get_timeline
        
        usdm = {
            "study": {
                "versions": [{
                    "timeline": {
                        "activities": [{"id": "act_1"}]
                    }
                }]
            }
        }
        timeline = get_timeline(usdm)
        assert "activities" in timeline
        assert len(timeline["activities"]) == 1


class TestProvenance:
    """Tests for core.provenance module."""
    
    def test_tracker_creation(self):
        """Test ProvenanceTracker creation."""
        from core.provenance import ProvenanceTracker
        
        tracker = ProvenanceTracker()
        assert tracker.entities is not None
        assert tracker.cells is not None
    
    def test_tag_entity(self):
        """Test entity tagging."""
        from core.provenance import ProvenanceTracker, ProvenanceSource
        
        tracker = ProvenanceTracker()
        tracker.tag_entity('activities', 'act_1', ProvenanceSource.TEXT)
        
        assert tracker.get_entity_source('activities', 'act_1') == 'text'
    
    def test_tag_entity_both(self):
        """Test entity tagging from multiple sources."""
        from core.provenance import ProvenanceTracker, ProvenanceSource
        
        tracker = ProvenanceTracker()
        tracker.tag_entity('activities', 'act_1', ProvenanceSource.TEXT)
        tracker.tag_entity('activities', 'act_1', ProvenanceSource.VISION)
        
        assert tracker.get_entity_source('activities', 'act_1') == 'both'
    
    def test_tag_cell(self):
        """Test cell-level tagging."""
        from core.provenance import ProvenanceTracker, ProvenanceSource
        
        tracker = ProvenanceTracker()
        tracker.tag_cell('act_1', 'pt_1', ProvenanceSource.TEXT)
        
        assert tracker.get_cell_source('act_1', 'pt_1') == 'text'
    
    def test_save_and_load(self):
        """Test saving and loading provenance."""
        from core.provenance import ProvenanceTracker, ProvenanceSource
        
        tracker = ProvenanceTracker()
        tracker.tag_entity('activities', 'act_1', ProvenanceSource.TEXT)
        tracker.tag_cell('act_1', 'pt_1', ProvenanceSource.VISION)
        
        # Create temp file, close it, then use the path
        fd, temp_path = tempfile.mkstemp(suffix='.json')
        os.close(fd)
        
        try:
            tracker.save(temp_path)
            loaded = ProvenanceTracker.load(temp_path)
            
            assert loaded.get_entity_source('activities', 'act_1') == 'text'
            assert loaded.get_cell_source('act_1', 'pt_1') == 'vision'
        finally:
            os.unlink(temp_path)
    
    def test_merge_trackers(self):
        """Test merging provenance trackers."""
        from core.provenance import ProvenanceTracker, ProvenanceSource
        
        tracker1 = ProvenanceTracker()
        tracker1.tag_entity('activities', 'act_1', ProvenanceSource.TEXT)
        
        tracker2 = ProvenanceTracker()
        tracker2.tag_entity('activities', 'act_1', ProvenanceSource.VISION)
        tracker2.tag_entity('activities', 'act_2', ProvenanceSource.VISION)
        
        tracker1.merge(tracker2)
        
        assert tracker1.get_entity_source('activities', 'act_1') == 'both'
        assert tracker1.get_entity_source('activities', 'act_2') == 'vision'


class TestUsdmTypes:
    """Tests for core.usdm_types module."""
    
    def test_activity_creation(self):
        """Test Activity dataclass."""
        from core.usdm_types import Activity
        
        activity = Activity(id="act_1", name="Vital Signs")
        assert activity.instanceType == "Activity"
        
        data = activity.to_dict()
        assert data["id"] == "act_1"
        assert data["name"] == "Vital Signs"
    
    def test_activity_from_dict(self):
        """Test Activity creation from dict."""
        from core.usdm_types import Activity
        
        data = {"id": "act_1", "name": "Blood Draw", "description": "Collect blood sample"}
        activity = Activity.from_dict(data)
        
        assert activity.id == "act_1"
        assert activity.name == "Blood Draw"
        assert activity.description == "Collect blood sample"
    
    def test_header_structure(self):
        """Test HeaderStructure."""
        from core.usdm_types import HeaderStructure, Epoch, Encounter, PlannedTimepoint
        
        header = HeaderStructure(
            epochs=[Epoch(id="epoch_1", name="Screening")],
            encounters=[Encounter(id="enc_1", name="Visit 1", epochId="epoch_1")],
            plannedTimepoints=[PlannedTimepoint(id="pt_1", visit="Visit 1", encounterId="enc_1")]
        )
        
        data = header.to_dict()
        assert len(data["columnHierarchy"]["epochs"]) == 1
        assert len(data["columnHierarchy"]["encounters"]) == 1
        assert len(data["columnHierarchy"]["plannedTimepoints"]) == 1
    
    def test_timeline(self):
        """Test Timeline dataclass."""
        from core.usdm_types import Timeline, Activity, ActivityTimepoint
        
        timeline = Timeline(
            activities=[Activity(id="act_1", name="Test")],
            activityTimepoints=[ActivityTimepoint(activityId="act_1", encounterId="enc_1")]
        )
        
        data = timeline.to_dict()
        assert len(data["activities"]) == 1
        assert len(data["activityTimepoints"]) == 1
    
    def test_create_wrapper_input(self):
        """Test USDM Wrapper-Input creation."""
        from core.usdm_types import Timeline, Activity, create_wrapper_input
        
        timeline = Timeline(activities=[Activity(id="act_1", name="Test")])
        wrapper = create_wrapper_input(timeline)
        
        assert wrapper["usdmVersion"] == "4.0"
        assert wrapper["systemName"] == "Protocol2USDM"
        assert "study" in wrapper
        assert "versions" in wrapper["study"]


class TestConstants:
    """Tests for core.constants module."""
    
    def test_version_constants(self):
        """Test version constants."""
        from core.constants import USDM_VERSION, SYSTEM_NAME, SYSTEM_VERSION
        
        assert USDM_VERSION == "4.0"
        assert SYSTEM_NAME == "Protocol2USDM"
        assert isinstance(SYSTEM_VERSION, str)
    
    def test_reasoning_models(self):
        """Test reasoning models list."""
        from core.constants import REASONING_MODELS
        
        assert "o3" in REASONING_MODELS
        assert "gpt-5.1" in REASONING_MODELS


class TestBackwardCompatibility:
    """Tests for backward compatibility with root-level modules."""
    
    def test_json_utils_compat(self):
        """Test json_utils backward compatibility - now in core.json_utils."""
        from core.json_utils import extract_json_str, clean_json_response
        
        result = extract_json_str('{"test": true}')
        assert result is not None
        
        result = clean_json_response('```json\n{"a": 1}\n```')
        assert '"a": 1' in result
    
    def test_p2u_constants_compat(self):
        """Test p2u_constants backward compatibility - now in core.constants."""
        from core.constants import USDM_VERSION, SYSTEM_NAME
        
        assert USDM_VERSION == "4.0"
        assert SYSTEM_NAME == "Protocol2USDM"


class TestNormalization:
    """Tests for USDM data normalization functions."""
    
    def test_normalize_preserves_standard_code(self):
        """Test that normalize_usdm_data preserves standardCode on Code objects."""
        from core.usdm_types_generated import normalize_usdm_data
        
        data = {
            "study": {
                "versions": [{
                    "administrableProducts": [{
                        "id": "prod_1",
                        "name": "Test Product",
                        "administrableDoseForm": {
                            "id": "df_1",
                            "code": "C42998",
                            "decode": "Tablet",
                            "instanceType": "Code",
                            "standardCode": {
                                "id": "sc_1",
                                "code": "C42998",
                                "decode": "Tablet",
                                "instanceType": "Code"
                            }
                        }
                    }]
                }]
            }
        }
        
        result = normalize_usdm_data(data)
        
        # Verify standardCode is preserved
        prod = result["study"]["versions"][0]["administrableProducts"][0]
        dose_form = prod["administrableDoseForm"]
        assert "standardCode" in dose_form
        assert dose_form["standardCode"]["code"] == "C42998"
    
    def test_normalize_adds_standard_code_when_missing(self):
        """Test that normalize_usdm_data adds standardCode when missing on administrableDoseForm."""
        from core.usdm_types_generated import normalize_usdm_data
        
        data = {
            "study": {
                "versions": [{
                    "administrableProducts": [{
                        "id": "prod_1",
                        "name": "Test Product",
                        "administrableDoseForm": {
                            "id": "df_1",
                            "code": "C42998",
                            "decode": "Tablet",
                            "instanceType": "Code"
                        }
                    }]
                }]
            }
        }
        
        result = normalize_usdm_data(data)
        
        # Verify standardCode is added
        prod = result["study"]["versions"][0]["administrableProducts"][0]
        dose_form = prod["administrableDoseForm"]
        assert "standardCode" in dose_form
        assert dose_form["standardCode"]["code"] == "C42998"
        assert dose_form["standardCode"]["instanceType"] == "Code"
