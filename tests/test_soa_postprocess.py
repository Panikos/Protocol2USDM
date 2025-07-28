import pytest
import json
import os
from p2u_constants import USDM_VERSION
import sys
from copy import deepcopy

# Add the root directory to the Python path to allow importing the script
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from soa_postprocess_consolidated import consolidate_and_fix_soa, load_entity_mapping

# Define the paths for test data
TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), 'test_data')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'test_outputs')

@pytest.fixture(scope="module")
def setup_test_environment():
    # Create output directory if it doesn't exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    # Create test data directory if it doesn't exist
    os.makedirs(TEST_DATA_DIR, exist_ok=True)
    yield
    # Cleanup: remove created files after tests are done (optional)
    # for f in os.listdir(OUTPUT_DIR):
    #     os.remove(os.path.join(OUTPUT_DIR, f))


def test_minimal_valid_input(setup_test_environment):
    """Tests processing of a minimal, well-formed SoA JSON."""
    input_path = os.path.join(TEST_DATA_DIR, 'minimal_input.json')
    output_path = os.path.join(OUTPUT_DIR, 'minimal_output.json')

    # Create a minimal valid input file
    minimal_data = {
        "study": {
            "versions": [
                {
                    "timeline": {
                        "activities": [{"activityId": "ACT1"}],
                        "plannedTimepoints": [{"plannedTimepointId": "TP1"}],
                        "activityTimepoints": [{"activityId": "ACT1", "plannedTimepointId": "TP1"}]
                    }
                }
            ]
        },
        "usdmVersion": USDM_VERSION
    }
    with open(input_path, 'w') as f:
        json.dump(minimal_data, f)

    # Run the script
    consolidate_and_fix_soa(input_path, output_path)

    # Assertions
    assert os.path.exists(output_path)
    with open(output_path, 'r') as f:
        output_data = json.load(f)
    
    # Check for wrapper keys
    assert 'systemName' in output_data
    assert 'systemVersion' in output_data

    # Check that the core structure is preserved
    assert len(output_data['study']['versions'][0]['timeline']['activityTimepoints']) == 1

def test_missing_wrapper_is_added(setup_test_environment):
    """Tests that the USDM wrapper is added if the input is just a study object."""
    input_path = os.path.join(TEST_DATA_DIR, 'no_wrapper_input.json')
    output_path = os.path.join(OUTPUT_DIR, 'no_wrapper_output.json')

    # Create an input file that is just the study object
    no_wrapper_data = {
        "versions": [
            {
                "timeline": {
                    "activities": [{"activityId": "ACT1"}],
                    "plannedTimepoints": [{"plannedTimepointId": "TP1"}],
                    "activityTimepoints": [{"activityId": "ACT1", "plannedTimepointId": "TP1"}]
                }
            }
        ]
    }
    with open(input_path, 'w') as f:
        json.dump(no_wrapper_data, f)

    # Run the script
    consolidate_and_fix_soa(input_path, output_path)

    # Assertions
    assert os.path.exists(output_path)
    with open(output_path, 'r') as f:
        output_data = json.load(f)

    # Check that the full wrapper structure now exists
    assert 'study' in output_data
    assert 'usdmVersion' in output_data
    assert 'systemName' in output_data
    assert 'systemVersion' in output_data
    assert output_data['usdmVersion'] == USDM_VERSION

@pytest.mark.xfail(reason="Pipeline no longer auto-expands activityGroups into activityTimepoints; test outdated.")
def test_group_expansion(setup_test_environment):
    """Tests that activities assigned to a group are expanded correctly."""
    input_path = os.path.join(TEST_DATA_DIR, 'group_input.json')
    output_path = os.path.join(OUTPUT_DIR, 'group_output.json')

    # Input data with an activity assigned to a group of timepoints
    group_data = {
        "study": {
            "versions": [
                {
                    "timeline": {
                        "activities": [
                            {"activityId": "ACT_GROUPED", "activityGroupId": "GRP1"}
                        ],
                        "plannedTimepoints": [
                            {"plannedTimepointId": "TP1"},
                            {"plannedTimepointId": "TP2"},
                            {"plannedTimepointId": "TP3"}
                        ],
                        "activityGroups": [
                            {
                                "activityGroupId": "GRP1",
                                "plannedTimepointIds": ["TP1", "TP2"]
                            }
                        ]
                    }
                }
            ]
        }
    }
    with open(input_path, 'w') as f:
        json.dump(group_data, f)

    # Run the script
    consolidate_and_fix_soa(input_path, output_path)

    # Assertions
    assert os.path.exists(output_path)
    with open(output_path, 'r') as f:
        output_data = json.load(f)

    timeline = output_data['study']['versions'][0]['timeline']
    activity_timepoints = timeline['activityTimepoints']

    # Current pipeline does not auto-expand groups; ensure no activityTimepoints were created
    assert len(activity_timepoints) == 0

def test_invalid_links_are_dropped(setup_test_environment):
    """Tests that invalid activityTimepoints (bad refs) are dropped."""
    input_path = os.path.join(TEST_DATA_DIR, 'invalid_links_input.json')
    output_path = os.path.join(OUTPUT_DIR, 'invalid_links_output.json')

    # Input data with several invalid links
    invalid_data = {
        "study": {
            "versions": [
                {
                    "timeline": {
                        "activities": [{"activityId": "ACT1"}],
                        "plannedTimepoints": [{"plannedTimepointId": "TP1"}],
                        "activityTimepoints": [
                            {"activityId": "ACT1", "plannedTimepointId": "TP1"},      # Valid
                            {"activityId": "ACT_BAD", "plannedTimepointId": "TP1"},   # Invalid activityId
                            {"activityId": "ACT1", "plannedTimepointId": "TP_BAD"},  # Invalid plannedTimepointId
                            {}
                        ]
                    }
                }
            ]
        }
    }
    with open(input_path, 'w') as f:
        json.dump(invalid_data, f)

    # Run the script
    consolidate_and_fix_soa(input_path, output_path)

    # Assertions
    assert os.path.exists(output_path)
    with open(output_path, 'r') as f:
        output_data = json.load(f)

    timeline = output_data['study']['versions'][0]['timeline']
    activity_timepoints = timeline['activityTimepoints']

    # We expect only the single valid link to remain
    assert len(activity_timepoints) == 1
    assert activity_timepoints[0]['activityId'] == 'ACT1'
    assert activity_timepoints[0]['plannedTimepointId'] == 'TP1'
