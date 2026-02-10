"""
Unit tests for USDM normalization functions.
Tests normalize_names_vs_timing(), ensure_required_fields(), and postprocess_usdm().
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import json
from copy import deepcopy
from soa_postprocess_consolidated import (
    normalize_names_vs_timing,
    ensure_required_fields,
    postprocess_usdm
)


class TestNormalizeNamesTiming:
    """Test suite for normalize_names_vs_timing function."""
    
    def test_encounter_with_week_timing(self):
        """Test that Week timing is extracted from Encounter name."""
        timeline = {
            'encounters': [
                {'id': 'enc_1', 'name': 'Visit 1 - Week -2'}
            ],
            'plannedTimepoints': []
        }
        
        count = normalize_names_vs_timing(timeline)
        
        assert count == 1
        assert timeline['encounters'][0]['name'] == 'Visit 1'
        assert timeline['encounters'][0]['timing']['windowLabel'] == 'Week -2'
    
    def test_encounter_with_day_timing(self):
        """Test that Day timing is extracted from Encounter name."""
        timeline = {
            'encounters': [
                {'id': 'enc_1', 'name': 'Screening - Day 1'}
            ],
            'plannedTimepoints': []
        }
        
        count = normalize_names_vs_timing(timeline)
        
        assert count == 1
        assert timeline['encounters'][0]['name'] == 'Screening'
        assert timeline['encounters'][0]['timing']['windowLabel'] == 'Day 1'
    
    def test_encounter_with_parentheses_timing(self):
        """Test timing in parentheses is extracted."""
        timeline = {
            'encounters': [
                {'id': 'enc_1', 'name': 'Visit 2 (Week 4)'}
            ],
            'plannedTimepoints': []
        }
        
        count = normalize_names_vs_timing(timeline)
        
        assert count == 1
        assert timeline['encounters'][0]['name'] == 'Visit 2'
        assert timeline['encounters'][0]['timing']['windowLabel'] == '(Week 4)'
    
    def test_planned_timepoint_with_timing(self):
        """Test that timing is moved to description in PlannedTimepoint."""
        timeline = {
            'encounters': [],
            'plannedTimepoints': [
                {'id': 'pt_1', 'name': 'Visit 1 Week -2'}
            ]
        }
        
        count = normalize_names_vs_timing(timeline)
        
        assert count == 1
        assert timeline['plannedTimepoints'][0]['name'] == 'Visit 1'
        assert timeline['plannedTimepoints'][0]['description'] == 'Week -2'
    
    def test_multiple_entities(self):
        """Test normalizing multiple entities."""
        timeline = {
            'encounters': [
                {'id': 'enc_1', 'name': 'Visit 1 - Week -2'},
                {'id': 'enc_2', 'name': 'Visit 2 - Week 0'},
            ],
            'plannedTimepoints': [
                {'id': 'pt_1', 'name': 'Baseline Day 1'},
            ]
        }
        
        count = normalize_names_vs_timing(timeline)
        
        assert count == 3
        assert timeline['encounters'][0]['name'] == 'Visit 1'
        assert timeline['encounters'][1]['name'] == 'Visit 2'
        assert timeline['plannedTimepoints'][0]['name'] == 'Baseline'
    
    def test_no_timing_in_name(self):
        """Test that clean names are not modified."""
        timeline = {
            'encounters': [
                {'id': 'enc_1', 'name': 'Screening Visit'}
            ],
            'plannedTimepoints': [
                {'id': 'pt_1', 'name': 'Baseline'}
            ]
        }
        
        count = normalize_names_vs_timing(timeline)
        
        assert count == 0
        assert timeline['encounters'][0]['name'] == 'Screening Visit'
        assert timeline['plannedTimepoints'][0]['name'] == 'Baseline'
    
    def test_preserves_existing_timing_fields(self):
        """Test that existing timing fields are not overwritten."""
        timeline = {
            'encounters': [
                {
                    'id': 'enc_1',
                    'name': 'Visit 1 - Week -2',
                    'timing': {'windowLabel': 'Week -2 to Week -1'}
                }
            ],
            'plannedTimepoints': []
        }
        
        count = normalize_names_vs_timing(timeline)
        
        assert count == 1
        assert timeline['encounters'][0]['name'] == 'Visit 1'
        # Existing windowLabel is preserved
        assert timeline['encounters'][0]['timing']['windowLabel'] == 'Week -2 to Week -1'
    
    def test_empty_timeline(self):
        """Test that empty timeline doesn't cause errors."""
        timeline = {}
        count = normalize_names_vs_timing(timeline)
        assert count == 0


class TestEnsureRequiredFields:
    """Test suite for ensure_required_fields function."""
    
    def test_adds_wrapper_fields(self):
        """Test that wrapper-level fields are added."""
        data = {}
        fields = ensure_required_fields(data)
        
        assert 'usdmVersion' in fields
        assert 'systemName' in fields
        assert 'systemVersion' in fields
        assert data['usdmVersion']  # Should be set to USDM_VERSION constant
    
    def test_adds_study_structure(self):
        """Test that study structure is created."""
        data = {}
        fields = ensure_required_fields(data)
        
        assert 'study' in data
        assert 'versions' in data['study']
        assert isinstance(data['study']['versions'], list)
        assert len(data['study']['versions']) > 0
    
    def test_adds_timeline(self):
        """Test that timeline is created."""
        data = {}
        ensure_required_fields(data)
        
        assert 'timeline' in data['study']['versions'][0]
    
    def test_adds_required_arrays(self):
        """Test that all required arrays are added."""
        data = {}
        ensure_required_fields(data)
        
        timeline = data['study']['versions'][0]['timeline']
        required_arrays = [
            'activities', 'plannedTimepoints', 'encounters',
            'activityTimepoints', 'activityGroups', 'epochs'
        ]
        
        for array_name in required_arrays:
            assert array_name in timeline
            assert isinstance(timeline[array_name], list)
    
    def test_adds_default_epoch(self):
        """Test that default epoch is added when none present."""
        data = {}
        fields = ensure_required_fields(data)
        
        assert 'timeline.epochs (default)' in fields
        epochs = data['study']['versions'][0]['timeline']['epochs']
        assert len(epochs) == 1
        assert epochs[0]['name'] == 'Study Period'
        assert epochs[0]['position'] == 1
    
    def test_preserves_existing_data(self):
        """Test that existing data is not overwritten."""
        data = {
            'usdmVersion': '3.0.0',
            'study': {
                'versions': [{
                    'timeline': {
                        'activities': [{'id': 'act_1'}],
                        'epochs': [{'id': 'epoch_custom'}]
                    }
                }]
            }
        }
        
        ensure_required_fields(data)
        
        # Version should NOT be overwritten
        assert data['usdmVersion'] == '3.0.0'
        # Activities should be preserved
        assert data['study']['versions'][0]['timeline']['activities'][0]['id'] == 'act_1'
        # Epochs should be preserved
        assert data['study']['versions'][0]['timeline']['epochs'][0]['id'] == 'epoch_custom'
    
    def test_normalizes_studyVersions_to_versions(self):
        """Test that legacy studyVersions is normalized to versions."""
        data = {
            'study': {
                'studyVersions': [{'timeline': {}}]
            }
        }
        
        ensure_required_fields(data)
        
        assert 'versions' in data['study']
        assert 'studyVersions' not in data['study']


class TestPostprocessUSDM:
    """Test suite for postprocess_usdm orchestrator function."""
    
    def test_full_normalization_pipeline(self):
        """Test complete normalization pipeline."""
        data = {
            'study': {
                'versions': [{
                    'timeline': {
                        'encounters': [
                            {'id': 'enc-1', 'name': 'Visit 1 - Week -2'}
                        ],
                        'plannedTimepoints': []
                    }
                }]
            }
        }
        
        result = postprocess_usdm(data, verbose=False)
        
        # Check wrapper fields added
        assert 'usdmVersion' in result
        
        # Check ID standardization (- → _)
        assert result['study']['versions'][0]['timeline']['encounters'][0]['id'] == 'enc_1'
        
        # Check name normalization
        assert result['study']['versions'][0]['timeline']['encounters'][0]['name'] == 'Visit 1'
        assert result['study']['versions'][0]['timeline']['encounters'][0]['timing']['windowLabel'] == 'Week -2'
    
    def test_empty_input(self):
        """Test that empty input is gracefully handled."""
        data = {}
        result = postprocess_usdm(data, verbose=False)
        
        # Should add all required structure
        assert 'study' in result
        assert 'usdmVersion' in result
        assert 'versions' in result['study']
    
    def test_verbose_output(self, capsys):
        """Test that verbose mode produces output."""
        data = {
            'study': {
                'versions': [{
                    'timeline': {
                        'encounters': [{'id': 'enc-1', 'name': 'Visit 1 Week -2'}]
                    }
                }]
            }
        }
        
        postprocess_usdm(data, verbose=True)
        
        captured = capsys.readouterr()
        assert '[POST-PROCESS]' in captured.out
        assert 'normalization' in captured.out.lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
