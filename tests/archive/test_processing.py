"""
Tests for the processing/ module.

Run with: pytest tests/test_processing.py -v
"""

import pytest
from copy import deepcopy


class TestNormalizer:
    """Tests for processing.normalizer module."""
    
    def test_normalize_names_vs_timing_encounter(self):
        """Test timing extraction from encounter names."""
        from processing.normalizer import normalize_names_vs_timing
        
        timeline = {
            "encounters": [
                {"id": "enc_1", "name": "Visit 1 (Week -2)"},
                {"id": "enc_2", "name": "Visit 2 Week 0"},
            ],
            "plannedTimepoints": []
        }
        
        count = normalize_names_vs_timing(timeline)
        
        assert count == 2
        assert timeline["encounters"][0]["name"] == "Visit 1"
        # Timing is extracted with parentheses as found in the name
        assert "(Week -2)" in timeline["encounters"][0]["timing"]["windowLabel"]
        assert "Week" not in timeline["encounters"][1]["name"]
    
    def test_normalize_names_vs_timing_timepoint(self):
        """Test timing extraction from timepoint names."""
        from processing.normalizer import normalize_names_vs_timing
        
        timeline = {
            "encounters": [],
            "plannedTimepoints": [
                {"id": "pt_1", "name": "Screening Day -14"},
            ]
        }
        
        count = normalize_names_vs_timing(timeline)
        
        assert count == 1
        assert "Day -14" in timeline["plannedTimepoints"][0].get("description", "")
    
    def test_clean_entity_names(self):
        """Test name cleaning."""
        from processing.normalizer import clean_entity_names
        
        timeline = {
            "activities": [
                {"id": "act_1", "name": "Vital  Signs"},  # Extra space
                {"id": "act_2", "name": "Blood\tDraw"},   # Tab
            ]
        }
        
        count = clean_entity_names(timeline)
        
        assert count == 2
        assert timeline["activities"][0]["name"] == "Vital Signs"
        assert timeline["activities"][1]["name"] == "Blood Draw"
    
    def test_normalize_timing_codes(self):
        """Test timing code normalization."""
        from processing.normalizer import normalize_timing_codes
        
        timeline = {
            "epochs": [
                {"id": "epoch_1", "name": "Screening Phase"},
                {"id": "epoch_2", "name": "Treatment Period"},
            ]
        }
        
        count = normalize_timing_codes(timeline)
        
        assert count == 2
        assert timeline["epochs"][0].get("code") is not None
        assert timeline["epochs"][0]["code"]["code"] == "C48262"  # Screening


class TestEnricher:
    """Tests for processing.enricher module."""
    
    def test_ensure_required_fields_empty(self):
        """Test adding required fields to empty data."""
        from processing.enricher import ensure_required_fields
        
        data = {}
        added = ensure_required_fields(data)
        
        assert "usdmVersion" in data
        assert data["usdmVersion"] == "4.0"
        assert "study" in data
        assert "versions" in data["study"]
        assert "timeline" in data["study"]["versions"][0]
    
    def test_ensure_required_fields_partial(self):
        """Test adding required fields to partial data."""
        from processing.enricher import ensure_required_fields
        
        data = {
            "study": {
                "versions": [{"timeline": {"activities": []}}]
            }
        }
        
        added = ensure_required_fields(data)
        
        # Should add missing arrays but not duplicate existing ones
        timeline = data["study"]["versions"][0]["timeline"]
        assert "activities" in timeline
        assert "encounters" in timeline
        assert "epochs" in timeline
    
    def test_ensure_default_epoch(self):
        """Test that default epoch is created."""
        from processing.enricher import ensure_required_fields
        
        data = {}
        ensure_required_fields(data)
        
        timeline = data["study"]["versions"][0]["timeline"]
        assert len(timeline["epochs"]) == 1
        assert timeline["epochs"][0]["name"] == "Study Period"
    
    def test_add_instance_types(self):
        """Test adding instanceType to entities."""
        from processing.enricher import add_instance_types
        
        timeline = {
            "activities": [{"id": "act_1", "name": "Test"}],
            "encounters": [{"id": "enc_1", "name": "Visit 1"}],
            "epochs": [],
        }
        
        count = add_instance_types(timeline)
        
        assert count == 2
        assert timeline["activities"][0]["instanceType"] == "Activity"
        assert timeline["encounters"][0]["instanceType"] == "Encounter"
    
    def test_get_timeline(self):
        """Test timeline extraction from wrapper format."""
        from processing.enricher import get_timeline
        
        data = {
            "study": {
                "versions": [{
                    "timeline": {"activities": [{"id": "act_1"}]}
                }]
            }
        }
        
        timeline = get_timeline(data)
        
        assert "activities" in timeline
        assert len(timeline["activities"]) == 1


class TestIntegration:
    """Integration tests for processing module."""
    
    def test_full_normalization_flow(self):
        """Test complete normalization flow."""
        from processing import normalize_names_vs_timing, ensure_required_fields
        from processing.normalizer import clean_entity_names
        from processing.enricher import add_instance_types
        
        # Simulate raw LLM output
        data = {
            "study": {
                "versions": [{
                    "timeline": {
                        "activities": [
                            {"id": "act-1", "name": "Vital  Signs"},
                        ],
                        "encounters": [
                            {"id": "enc-1", "name": "Visit 1 (Week -2)"},
                        ],
                        "plannedTimepoints": [
                            {"id": "pt-1", "name": "Screening Day -7"},
                        ],
                    }
                }]
            }
        }
        
        # Apply normalization
        ensure_required_fields(data)
        timeline = data["study"]["versions"][0]["timeline"]
        
        clean_entity_names(timeline)
        normalize_names_vs_timing(timeline)
        add_instance_types(timeline)
        
        # Verify results
        assert timeline["activities"][0]["name"] == "Vital Signs"
        assert timeline["encounters"][0]["name"] == "Visit 1"
        assert "windowLabel" in timeline["encounters"][0].get("timing", {})
        assert timeline["activities"][0]["instanceType"] == "Activity"
