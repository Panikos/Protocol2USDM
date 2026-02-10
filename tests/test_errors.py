"""
Tests for core.errors — PipelineError hierarchy.

Validates:
- Hierarchy relationships (isinstance checks)
- Structured to_dict() output
- Retryable flag on LLM errors
- Cause chaining
- Backward compatibility (all are subclasses of Exception)
"""

import pytest
from core.errors import (
    PipelineError,
    ConfigurationError,
    LLMError,
    LLMRateLimitError,
    LLMSafetyFilterError,
    LLMResponseError,
    LLMConnectionError,
    ExtractionError,
    SchemaValidationError,
    PDFExtractionError,
    ValidationError,
    USDMValidationError,
    M11ConformanceError,
)


# ── Hierarchy ────────────────────────────────────────────────────────

class TestHierarchy:
    """All errors inherit from PipelineError and Exception."""

    @pytest.mark.parametrize("cls", [
        ConfigurationError,
        LLMError, LLMRateLimitError, LLMSafetyFilterError,
        LLMResponseError, LLMConnectionError,
        ExtractionError, SchemaValidationError, PDFExtractionError,
        ValidationError, USDMValidationError, M11ConformanceError,
    ])
    def test_is_pipeline_error(self, cls):
        err = cls("test")
        assert isinstance(err, PipelineError)
        assert isinstance(err, Exception)

    def test_llm_subtypes(self):
        assert issubclass(LLMRateLimitError, LLMError)
        assert issubclass(LLMSafetyFilterError, LLMError)
        assert issubclass(LLMResponseError, LLMError)
        assert issubclass(LLMConnectionError, LLMError)

    def test_extraction_subtypes(self):
        assert issubclass(SchemaValidationError, ExtractionError)
        assert issubclass(PDFExtractionError, ExtractionError)

    def test_validation_subtypes(self):
        assert issubclass(USDMValidationError, ValidationError)
        assert issubclass(M11ConformanceError, ValidationError)


# ── Attributes ───────────────────────────────────────────────────────

class TestAttributes:
    """Test phase, model, cause attributes."""

    def test_base_attributes(self):
        err = PipelineError("boom", phase="metadata", model="gemini-3-flash")
        assert str(err) == "boom"
        assert err.phase == "metadata"
        assert err.model == "gemini-3-flash"
        assert err.cause is None

    def test_cause_chaining(self):
        original = ValueError("bad json")
        err = LLMResponseError("parse failed", cause=original)
        assert err.cause is original
        assert err.__cause__ is original

    def test_defaults_are_none(self):
        err = PipelineError("simple")
        assert err.phase is None
        assert err.model is None
        assert err.cause is None


# ── to_dict ──────────────────────────────────────────────────────────

class TestToDict:
    """Structured output for logging / telemetry."""

    def test_minimal(self):
        d = PipelineError("oops").to_dict()
        assert d == {"error_type": "PipelineError", "message": "oops"}

    def test_full(self):
        cause = RuntimeError("timeout")
        err = LLMError(
            "call failed",
            phase="objectives",
            model="gpt-4o",
            cause=cause,
            retryable=True,
        )
        d = err.to_dict()
        assert d["error_type"] == "LLMError"
        assert d["message"] == "call failed"
        assert d["phase"] == "objectives"
        assert d["model"] == "gpt-4o"
        assert d["retryable"] is True
        assert "RuntimeError: timeout" in d["cause"]

    def test_subclass_type_name(self):
        d = LLMRateLimitError().to_dict()
        assert d["error_type"] == "LLMRateLimitError"


# ── Retryable ────────────────────────────────────────────────────────

class TestRetryable:
    """LLM errors carry a retryable flag."""

    def test_rate_limit_is_retryable(self):
        assert LLMRateLimitError().retryable is True

    def test_safety_filter_not_retryable(self):
        assert LLMSafetyFilterError().retryable is False

    def test_response_error_retryable(self):
        assert LLMResponseError().retryable is True

    def test_connection_error_retryable(self):
        assert LLMConnectionError().retryable is True

    def test_base_llm_default_not_retryable(self):
        assert LLMError("generic").retryable is False


# ── Catch patterns ───────────────────────────────────────────────────

class TestCatchPatterns:
    """Verify real-world except clauses work as expected."""

    def test_catch_all_pipeline_errors(self):
        with pytest.raises(PipelineError):
            raise LLMRateLimitError()

    def test_catch_llm_errors(self):
        with pytest.raises(LLMError):
            raise LLMSafetyFilterError("blocked")

    def test_catch_extraction_errors(self):
        with pytest.raises(ExtractionError):
            raise SchemaValidationError("bad schema")

    def test_catch_validation_errors(self):
        with pytest.raises(ValidationError):
            raise M11ConformanceError("missing section")

    def test_catch_as_exception(self):
        """Backward compat: all pipeline errors are catchable as Exception."""
        with pytest.raises(Exception):
            raise ConfigurationError("no key")
