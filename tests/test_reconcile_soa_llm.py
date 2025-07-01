import os
import json
import pytest
from unittest.mock import patch, MagicMock

from reconcile_soa_llm import reconcile_soa

# --- Test Setup ---
TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), 'test_data')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'test_outputs')

@pytest.fixture(scope="module", autouse=True)
def setup_test_environment():
    """Create test directories before tests run, and clean up after."""
    os.makedirs(TEST_DATA_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    yield
    # No cleanup needed for now, but could add `shutil.rmtree` here if needed

# --- Test Cases ---

def test_vision_only_passthrough():
    """Tests that vision SoA is passed through when no text SoA is provided."""
    vision_input_path = os.path.join(TEST_DATA_DIR, 'vision_only_input.json')
    output_path = os.path.join(OUTPUT_DIR, 'vision_only_output.json')

    vision_data = {"study": {"studyId": "VISION-123"}}
    with open(vision_input_path, 'w') as f:
        json.dump(vision_data, f)

    reconcile_soa(vision_path=vision_input_path, output_path=output_path, text_path=None)

    assert os.path.exists(output_path)
    with open(output_path, 'r') as f:
        output_data = json.load(f)
    assert output_data == vision_data

def test_invalid_text_soa_passthrough():
    """Tests that vision SoA is passed through when text SoA is invalid."""
    vision_input_path = os.path.join(TEST_DATA_DIR, 'invalid_text_vision_input.json')
    text_input_path = os.path.join(TEST_DATA_DIR, 'invalid_text_input.json')
    output_path = os.path.join(OUTPUT_DIR, 'invalid_text_output.json')

    vision_data = {"study": {"studyId": "VISION-456"}}
    with open(vision_input_path, 'w') as f:
        json.dump(vision_data, f)
    
    # Create an invalid JSON file
    with open(text_input_path, 'w') as f:
        f.write('{"this is not valid json,')

    reconcile_soa(vision_path=vision_input_path, output_path=output_path, text_path=text_input_path)

    assert os.path.exists(output_path)
    with open(output_path, 'r') as f:
        output_data = json.load(f)
    assert output_data == vision_data

@patch('reconcile_soa_llm.client.chat.completions.create')
def test_successful_reconciliation(mock_create):
    """Tests a successful reconciliation call to the LLM."""
    vision_input_path = os.path.join(TEST_DATA_DIR, 'reconcile_vision_input.json')
    text_input_path = os.path.join(TEST_DATA_DIR, 'reconcile_text_input.json')
    output_path = os.path.join(OUTPUT_DIR, 'reconcile_output.json')

    vision_data = {"study": {"studyId": "VISION-789"}}
    text_data = {"study": {"studyId": "TEXT-789"}}
    reconciled_data = {"study": {"studyId": "RECONCILED-789"}}

    with open(vision_input_path, 'w') as f:
        json.dump(vision_data, f)
    with open(text_input_path, 'w') as f:
        json.dump(text_data, f)

    # Mock the OpenAI API response
    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps(reconciled_data)
    mock_create.return_value = mock_response

    reconcile_soa(vision_path=vision_input_path, output_path=output_path, text_path=text_input_path, model_name='o3')

    mock_create.assert_called_once()
    assert os.path.exists(output_path)
    with open(output_path, 'r') as f:
        output_data = json.load(f)
    assert output_data == reconciled_data

@patch('reconcile_soa_llm.client.chat.completions.create')
def test_llm_failure_and_fallback(mock_create):
    """Tests model fallback logic when the primary model fails."""
    vision_input_path = os.path.join(TEST_DATA_DIR, 'fallback_vision_input.json')
    text_input_path = os.path.join(TEST_DATA_DIR, 'fallback_text_input.json')
    output_path = os.path.join(OUTPUT_DIR, 'fallback_output.json')

    vision_data = {"study": {"studyId": "VISION-FB"}}
    text_data = {"study": {"studyId": "TEXT-FB"}}
    fallback_data = {"study": {"studyId": "FALLBACK-FB"}}

    with open(vision_input_path, 'w') as f:
        json.dump(vision_data, f)
    with open(text_input_path, 'w') as f:
        json.dump(text_data, f)

    # Mock the OpenAI API to fail on the first call, succeed on the second
    mock_fallback_response = MagicMock()
    mock_fallback_response.choices[0].message.content = json.dumps(fallback_data)
    mock_create.side_effect = [
        Exception("Primary model failed"),
        mock_fallback_response
    ]

    reconcile_soa(vision_path=vision_input_path, output_path=output_path, text_path=text_input_path, model_name='o3')

    assert mock_create.call_count == 2
    # Check that the first call was with 'o3' and the second with 'gpt-4o'
    assert mock_create.call_args_list[0].kwargs['model'] == 'o3'
    assert mock_create.call_args_list[1].kwargs['model'] == 'gpt-4o'
    
    assert os.path.exists(output_path)
    with open(output_path, 'r') as f:
        output_data = json.load(f)
    assert output_data == fallback_data
