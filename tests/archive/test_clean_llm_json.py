import os
import sys

os.environ.setdefault("OPENAI_API_KEY", "test")

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from json_utils import clean_llm_json


def test_strip_code_block_markers():
    raw = "```json\n{\"a\": 1}\n```"
    assert clean_llm_json(raw).strip() == '{"a": 1}'


def test_remove_trailing_text():
    raw = '{"a": 1} some trailing text'
    assert clean_llm_json(raw) == '{"a": 1}'

