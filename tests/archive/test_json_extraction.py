"""
Unit tests for defensive JSON extraction functions.
Tests the extract_json_str() function with various malformed inputs.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import json
from send_pdf_to_llm import extract_json_str


class TestExtractJsonStr:
    """Test suite for defensive JSON extraction."""
    
    def test_clean_json_fast_path(self):
        """Test that clean JSON passes through unchanged."""
        clean = '{"study": {"versions": []}}'
        result = extract_json_str(clean)
        assert result == clean
        # Verify it's valid
        parsed = json.loads(result)
        assert 'study' in parsed
    
    def test_json_with_code_fences(self):
        """Test removal of markdown code fences."""
        with_fences = '```json\n{"study": {"versions": []}}\n```'
        result = extract_json_str(with_fences)
        parsed = json.loads(result)
        assert 'study' in parsed
    
    def test_json_with_leading_prose(self):
        """Test removal of leading prose like 'Here is the JSON:'."""
        with_prose = 'Here is your JSON output:\n{"study": {"versions": []}}'
        result = extract_json_str(with_prose)
        parsed = json.loads(result)
        assert 'study' in parsed
    
    def test_json_with_trailing_comma(self):
        """Test fixing of trailing commas in objects."""
        with_comma = '{"study": {"versions": [],}}'
        result = extract_json_str(with_comma)
        parsed = json.loads(result)
        assert 'study' in parsed
    
    def test_json_with_trailing_comma_in_array(self):
        """Test fixing of trailing commas in arrays."""
        with_comma = '{"study": {"versions": ["v1",]}}'
        result = extract_json_str(with_comma)
        parsed = json.loads(result)
        assert len(parsed['study']['versions']) == 1
    
    def test_json_embedded_in_text(self):
        """Test extraction of JSON from surrounding text."""
        embedded = """
        Some preamble text here.
        
        {"study": {"versions": []}}
        
        Some trailing text.
        """
        result = extract_json_str(embedded)
        parsed = json.loads(result)
        assert 'study' in parsed
    
    def test_complex_nested_json(self):
        """Test extraction of complex nested structure."""
        complex_json = {
            "study": {
                "versions": [{
                    "timeline": {
                        "activities": [{"id": "act-1", "name": "Test"}],
                        "encounters": []
                    }
                }]
            },
            "usdmVersion": "4.0.0"
        }
        json_str = json.dumps(complex_json)
        
        # Wrap in markdown
        wrapped = f"```json\n{json_str}\n```"
        
        result = extract_json_str(wrapped)
        parsed = json.loads(result)
        assert parsed == complex_json
    
    def test_no_json_raises_error(self):
        """Test that non-JSON input raises ValueError."""
        no_json = "This is just plain text with no JSON object"
        with pytest.raises(ValueError, match="No JSON object found"):
            extract_json_str(no_json)
    
    def test_invalid_json_raises_error(self):
        """Test that malformed JSON raises ValueError."""
        bad_json = '{"study": {"versions": ['
        with pytest.raises(ValueError, match="(invalid|No JSON object found)"):
            extract_json_str(bad_json)
    
    def test_multiple_trailing_commas(self):
        """Test fixing multiple trailing commas."""
        multi_comma = '{"study": {"versions": [], "timeline": {},}}'
        result = extract_json_str(multi_comma)
        parsed = json.loads(result)
        assert 'study' in parsed
    
    def test_json_with_unicode(self):
        """Test JSON with unicode characters."""
        unicode_json = '{"study": {"name": "Test™ Protocol®"}}'
        result = extract_json_str(unicode_json)
        parsed = json.loads(result)
        assert "™" in parsed['study']['name']
    
    def test_empty_objects_and_arrays(self):
        """Test that empty structures are preserved."""
        empty = '{"study": {"versions": [], "attributes": {}}}'
        result = extract_json_str(empty)
        parsed = json.loads(result)
        assert parsed['study']['versions'] == []
        assert parsed['study']['attributes'] == {}


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
