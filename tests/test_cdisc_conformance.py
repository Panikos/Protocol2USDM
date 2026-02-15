"""Tests for validation.cdisc_conformance parsing and timeout behavior."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from validation.cdisc_conformance import (
    DEFAULT_CORE_TIMEOUT_SECONDS,
    _extract_core_issues,
    _get_core_timeout_seconds,
)


def test_extract_core_issues_legacy_schema_counts_warning_and_error():
    report = {
        "issues": [
            {"severity": "Warning", "message": "warn"},
            {"severity": "Error", "message": "err"},
            {"severity": "CRITICAL", "message": "crit"},
        ]
    }

    issues, errors, warnings = _extract_core_issues(report)

    assert len(issues) == 3
    assert errors == 2
    assert warnings == 1


def test_extract_core_issues_v014_issue_details_defaults_missing_severity_to_error():
    report = {
        "Issue_Details": [
            {"core_id": "CORE-1", "message": "A"},
            {"cdisc_rule_id": "DDF-1", "message": "B", "severity": "warning"},
        ]
    }

    issues, errors, warnings = _extract_core_issues(report)

    assert len(issues) == 2
    assert errors == 1
    assert warnings == 1
    assert issues[0]["rule"] == "CORE-1"


def test_extract_core_issues_v014_issue_summary_fallback_uses_counts():
    report = {
        "Issue_Summary": [
            {"core_id": "CORE-1", "message": "A", "issues": 2},
            {"cdisc_rule_id": "DDF-2", "message": "B", "issues": "3"},
            {"core_id": "CORE-3", "message": "C", "issues": "bad"},
        ]
    }

    issues, errors, warnings = _extract_core_issues(report)

    assert len(issues) == 3
    assert errors == 5
    assert warnings == 0
    assert issues[0]["count"] == 2
    assert issues[1]["count"] == 3
    assert issues[2]["count"] == 0


def test_get_core_timeout_seconds_defaults_when_env_missing(monkeypatch):
    monkeypatch.delenv("CDISC_CORE_TIMEOUT_SECONDS", raising=False)

    assert _get_core_timeout_seconds() == DEFAULT_CORE_TIMEOUT_SECONDS


def test_get_core_timeout_seconds_uses_env(monkeypatch):
    monkeypatch.setenv("CDISC_CORE_TIMEOUT_SECONDS", "420")

    assert _get_core_timeout_seconds() == 420


def test_get_core_timeout_seconds_handles_invalid_env(monkeypatch):
    monkeypatch.setenv("CDISC_CORE_TIMEOUT_SECONDS", "not-a-number")

    assert _get_core_timeout_seconds() == DEFAULT_CORE_TIMEOUT_SECONDS


def test_get_core_timeout_seconds_enforces_positive_explicit_value():
    assert _get_core_timeout_seconds(timeout_seconds=-5) == 1
