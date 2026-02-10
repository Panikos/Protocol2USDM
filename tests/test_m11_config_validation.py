"""
Tests for E18: M11 mapping YAML schema validation at load time.

Validates:
- validate_m11_config() catches structural errors
- load_m11_config() raises M11ConfigValidationError on bad YAML
- Real YAML passes validation
- Missing sections, bad types, missing fields all detected
"""

import copy
import pytest
import yaml

from core.m11_mapping_config import (
    validate_m11_config,
    load_m11_config,
    M11ConfigValidationError,
    _CONFIG_PATH,
)


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def valid_raw():
    """Load the real YAML as a baseline valid config."""
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _minimal_section(title="Test Section", required=True):
    return {
        "title": title,
        "required": required,
        "keywords": ["test"],
        "aliases": ["test"],
        "subheadings": [],
    }


def _minimal_raw():
    """Build a minimal valid config dict."""
    sections = {str(i): _minimal_section(f"Section {i}") for i in range(1, 15)}
    return {
        "schema_version": "1.0",
        "m11_version": "test",
        "usdm_version": "4.0",
        "sections": sections,
        "title_page_fields": [
            {"name": "Full Title", "conformance": "Required", "check": "titles"},
        ],
    }


# ── Real YAML passes ─────────────────────────────────────────────────

class TestRealYAMLValid:
    """The actual m11_usdm_mapping.yaml must pass validation."""

    def test_real_yaml_passes(self, valid_raw):
        errors = validate_m11_config(valid_raw)
        assert errors == [], f"Real YAML has errors: {errors}"

    def test_load_real_yaml_succeeds(self):
        config = load_m11_config()
        assert len(config.sections()) == 14


# ── Top-level keys ───────────────────────────────────────────────────

class TestTopLevelKeys:

    def test_missing_schema_version(self):
        raw = _minimal_raw()
        del raw["schema_version"]
        errors = validate_m11_config(raw)
        assert any("schema_version" in e for e in errors)

    def test_missing_m11_version(self):
        raw = _minimal_raw()
        del raw["m11_version"]
        errors = validate_m11_config(raw)
        assert any("m11_version" in e for e in errors)

    def test_missing_usdm_version(self):
        raw = _minimal_raw()
        del raw["usdm_version"]
        errors = validate_m11_config(raw)
        assert any("usdm_version" in e for e in errors)

    def test_sections_not_a_mapping(self):
        raw = _minimal_raw()
        raw["sections"] = ["not", "a", "dict"]
        errors = validate_m11_config(raw)
        assert any("must be a mapping" in e for e in errors)


# ── Section coverage ─────────────────────────────────────────────────

class TestSectionCoverage:

    def test_missing_section(self):
        raw = _minimal_raw()
        del raw["sections"]["7"]
        errors = validate_m11_config(raw)
        assert any("Missing M11 sections" in e and "7" in e for e in errors)

    def test_all_14_present(self):
        raw = _minimal_raw()
        errors = validate_m11_config(raw)
        assert not any("Missing M11 sections" in e for e in errors)


# ── Per-section validation ───────────────────────────────────────────

class TestPerSectionValidation:

    def test_missing_title(self):
        raw = _minimal_raw()
        del raw["sections"]["3"]["title"]
        errors = validate_m11_config(raw)
        assert any("sections.3" in e and "title" in e for e in errors)

    def test_missing_required(self):
        raw = _minimal_raw()
        del raw["sections"]["5"]["required"]
        errors = validate_m11_config(raw)
        assert any("sections.5" in e and "required" in e for e in errors)

    def test_required_not_bool(self):
        raw = _minimal_raw()
        raw["sections"]["1"]["required"] = "yes"
        errors = validate_m11_config(raw)
        assert any("must be boolean" in e for e in errors)

    def test_keywords_not_list(self):
        raw = _minimal_raw()
        raw["sections"]["2"]["keywords"] = "not a list"
        errors = validate_m11_config(raw)
        assert any("keywords" in e and "must be a list" in e for e in errors)

    def test_aliases_not_list(self):
        raw = _minimal_raw()
        raw["sections"]["2"]["aliases"] = 42
        errors = validate_m11_config(raw)
        assert any("aliases" in e and "must be a list" in e for e in errors)

    def test_section_not_a_mapping(self):
        raw = _minimal_raw()
        raw["sections"]["4"] = "just a string"
        errors = validate_m11_config(raw)
        assert any("sections.4" in e and "must be a mapping" in e for e in errors)


# ── Subheading validation ────────────────────────────────────────────

class TestSubheadingValidation:

    def test_subheading_missing_number(self):
        raw = _minimal_raw()
        raw["sections"]["1"]["subheadings"] = [{"title": "Foo", "level": 2}]
        errors = validate_m11_config(raw)
        assert any("subheadings[0]" in e and "number" in e for e in errors)

    def test_subheading_missing_title(self):
        raw = _minimal_raw()
        raw["sections"]["1"]["subheadings"] = [{"number": "1.1", "level": 2}]
        errors = validate_m11_config(raw)
        assert any("subheadings[0]" in e and "title" in e for e in errors)

    def test_subheading_level_not_int(self):
        raw = _minimal_raw()
        raw["sections"]["1"]["subheadings"] = [
            {"number": "1.1", "title": "Foo", "level": "two"}
        ]
        errors = validate_m11_config(raw)
        assert any("level" in e and "integer" in e for e in errors)

    def test_valid_subheading(self):
        raw = _minimal_raw()
        raw["sections"]["1"]["subheadings"] = [
            {"number": "1.1", "title": "Synopsis", "level": 2, "keywords": ["synopsis"]}
        ]
        errors = validate_m11_config(raw)
        assert not any("subheadings" in e for e in errors)


# ── Synopsis fields validation ───────────────────────────────────────

class TestSynopsisFieldValidation:

    def test_synopsis_field_missing_name(self):
        raw = _minimal_raw()
        raw["sections"]["1"]["synopsis_fields"] = [
            {"conformance": "Required", "check": "x"}
        ]
        errors = validate_m11_config(raw)
        assert any("synopsis_fields[0]" in e and "name" in e for e in errors)

    def test_synopsis_field_bad_conformance(self):
        raw = _minimal_raw()
        raw["sections"]["1"]["synopsis_fields"] = [
            {"name": "Test", "conformance": "Mandatory", "check": "x"}
        ]
        errors = validate_m11_config(raw)
        assert any("conformance" in e and "Mandatory" in e for e in errors)

    def test_valid_synopsis_field(self):
        raw = _minimal_raw()
        raw["sections"]["1"]["synopsis_fields"] = [
            {"name": "Test", "conformance": "Optional", "check": "x"}
        ]
        errors = validate_m11_config(raw)
        assert not any("synopsis_fields" in e for e in errors)


# ── Title page fields validation ─────────────────────────────────────

class TestTitlePageFieldValidation:

    def test_title_page_missing_name(self):
        raw = _minimal_raw()
        raw["title_page_fields"] = [{"conformance": "Required", "check": "x"}]
        errors = validate_m11_config(raw)
        assert any("title_page_fields[0]" in e and "name" in e for e in errors)

    def test_title_page_bad_conformance(self):
        raw = _minimal_raw()
        raw["title_page_fields"] = [
            {"name": "Test", "conformance": "Mandatory", "check": "x"}
        ]
        errors = validate_m11_config(raw)
        assert any("conformance" in e and "Mandatory" in e for e in errors)


# ── Regulatory frameworks validation ─────────────────────────────────

class TestRegulatoryFrameworkValidation:

    def test_frameworks_not_mapping(self):
        raw = _minimal_raw()
        raw["regulatory_frameworks"] = ["not", "a", "dict"]
        errors = validate_m11_config(raw)
        assert any("regulatory_frameworks" in e and "must be a mapping" in e for e in errors)

    def test_framework_missing_name(self):
        raw = _minimal_raw()
        raw["regulatory_frameworks"] = {
            "ich_e9": {"version": "2019"}  # missing 'name'
        }
        errors = validate_m11_config(raw)
        assert any("ich_e9" in e and "name" in e for e in errors)

    def test_valid_framework(self):
        raw = _minimal_raw()
        raw["regulatory_frameworks"] = {
            "ich_e9": {"name": "ICH E9(R1)", "version": "2019"}
        }
        errors = validate_m11_config(raw)
        assert not any("regulatory_frameworks" in e for e in errors)


# ── M11ConfigValidationError ─────────────────────────────────────────

class TestValidationError:

    def test_error_contains_all_messages(self):
        errs = ["error 1", "error 2"]
        exc = M11ConfigValidationError(errs)
        assert exc.errors == errs
        assert "2 validation error(s)" in str(exc)
        assert "error 1" in str(exc)
        assert "error 2" in str(exc)

    def test_load_raises_on_invalid(self, tmp_path):
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("sections: not_a_dict\n", encoding="utf-8")
        with pytest.raises(M11ConfigValidationError) as exc_info:
            load_m11_config(str(bad_yaml))
        assert len(exc_info.value.errors) > 0


# ── Multiple errors accumulated ──────────────────────────────────────

class TestMultipleErrors:

    def test_accumulates_multiple_errors(self):
        raw = {
            # missing schema_version, m11_version, usdm_version
            "sections": {
                "1": {"required": "not_bool"},
                # missing sections 2-14
            },
        }
        errors = validate_m11_config(raw)
        assert len(errors) >= 4  # 3 missing top-level + missing sections + bad required
