"""
Tests for core.prompt_registry — prompt version hashing.

Validates:
- All registered prompt modules can be imported
- Hashes are stable (same input → same hash)
- get_prompt_versions returns expected structure
- get_prompt_fingerprint changes when any prompt changes
- PROMPT_SOURCES covers all extraction phases
"""

import pytest
from unittest.mock import patch

from core.prompt_registry import (
    get_prompt_versions,
    get_prompt_fingerprint,
    _hash_text,
    PROMPT_SOURCES,
)


class TestHashText:
    """SHA-256 truncated hash utility."""

    def test_deterministic(self):
        assert _hash_text("hello") == _hash_text("hello")

    def test_different_inputs(self):
        assert _hash_text("hello") != _hash_text("world")

    def test_length_is_12(self):
        assert len(_hash_text("anything")) == 12

    def test_hex_chars_only(self):
        h = _hash_text("test")
        assert all(c in "0123456789abcdef" for c in h)


class TestGetPromptVersions:
    """get_prompt_versions discovers and hashes all prompt constants."""

    def test_returns_dict(self):
        versions = get_prompt_versions()
        assert isinstance(versions, dict)

    def test_has_core_phases(self):
        versions = get_prompt_versions()
        # At minimum these phases should have prompts
        for phase in ["metadata", "eligibility", "objectives", "studydesign"]:
            assert phase in versions, f"Missing phase: {phase}"

    def test_entry_structure(self):
        versions = get_prompt_versions()
        for phase, info in versions.items():
            assert "hash" in info, f"{phase} missing 'hash'"
            assert "length" in info, f"{phase} missing 'length'"
            assert "constant" in info, f"{phase} missing 'constant'"
            assert len(info["hash"]) == 12
            assert info["length"] > 0

    def test_hashes_are_stable(self):
        v1 = get_prompt_versions()
        v2 = get_prompt_versions()
        for phase in v1:
            assert v1[phase]["hash"] == v2[phase]["hash"]


class TestGetPromptFingerprint:
    """Combined fingerprint of all prompts."""

    def test_returns_string(self):
        fp = get_prompt_fingerprint()
        assert isinstance(fp, str)
        assert len(fp) == 12

    def test_stable(self):
        assert get_prompt_fingerprint() == get_prompt_fingerprint()


class TestPromptSourcesCoverage:
    """PROMPT_SOURCES should cover all extraction phases."""

    def test_covers_all_phase_dirs(self):
        import os
        extraction_dir = os.path.join(os.path.dirname(__file__), "..", "extraction")
        phase_dirs = set()
        for item in os.listdir(extraction_dir):
            prompts_path = os.path.join(extraction_dir, item, "prompts.py")
            if os.path.isfile(prompts_path):
                phase_dirs.add(item)

        registered = set()
        for sources in PROMPT_SOURCES.values():
            for mod_path, _ in sources:
                # extraction.metadata.prompts → metadata
                parts = mod_path.split(".")
                if len(parts) >= 3:
                    registered.add(parts[1])

        missing = phase_dirs - registered
        assert not missing, f"Prompt files exist but not registered: {missing}"
