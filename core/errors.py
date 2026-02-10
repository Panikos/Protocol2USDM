"""
PipelineError hierarchy for Protocol2USDM.

Provides typed exceptions so callers can distinguish retryable from fatal
errors, and so logging/telemetry can categorize failures without parsing
message strings.

Hierarchy:
    PipelineError                       (base — all pipeline errors)
    ├── ConfigurationError              (missing env vars, bad model name)
    ├── LLMError                        (any LLM provider failure)
    │   ├── LLMRateLimitError           (retryable — 429 / quota)
    │   ├── LLMSafetyFilterError        (content blocked by safety filter)
    │   ├── LLMResponseError            (malformed / unparseable response)
    │   └── LLMConnectionError          (network / timeout)
    ├── ExtractionError                 (phase-level extraction failure)
    │   ├── SchemaValidationError       (LLM output doesn't match Pydantic schema)
    │   └── PDFExtractionError          (PDF read / page range issues)
    └── ValidationError                 (post-extraction validation)
        ├── USDMValidationError         (USDM schema violations)
        └── M11ConformanceError         (M11 conformance failures)
"""

from typing import Optional


class PipelineError(Exception):
    """Base exception for all Protocol2USDM pipeline errors."""

    def __init__(self, message: str, *, phase: Optional[str] = None,
                 model: Optional[str] = None, cause: Optional[Exception] = None):
        self.phase = phase
        self.model = model
        self.cause = cause
        super().__init__(message)
        if cause and not self.__cause__:
            self.__cause__ = cause

    def to_dict(self) -> dict:
        """Structured representation for logging / telemetry."""
        d = {
            "error_type": type(self).__name__,
            "message": str(self),
        }
        if self.phase:
            d["phase"] = self.phase
        if self.model:
            d["model"] = self.model
        if self.cause:
            d["cause"] = f"{type(self.cause).__name__}: {self.cause}"
        return d


# ── Configuration ────────────────────────────────────────────────────

class ConfigurationError(PipelineError):
    """Missing environment variable, invalid model name, bad config file."""
    pass


# ── LLM Provider ─────────────────────────────────────────────────────

class LLMError(PipelineError):
    """Base for all LLM provider errors."""

    def __init__(self, message: str, *, phase: Optional[str] = None,
                 model: Optional[str] = None, cause: Optional[Exception] = None,
                 retryable: bool = False):
        self.retryable = retryable
        super().__init__(message, phase=phase, model=model, cause=cause)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["retryable"] = self.retryable
        return d


class LLMRateLimitError(LLMError):
    """429 / quota exhausted — always retryable."""

    def __init__(self, message: str = "Rate limit exceeded", **kwargs):
        super().__init__(message, retryable=True, **kwargs)


class LLMSafetyFilterError(LLMError):
    """Content blocked by provider safety filter — not retryable."""

    def __init__(self, message: str = "Content blocked by safety filter", **kwargs):
        super().__init__(message, retryable=False, **kwargs)


class LLMResponseError(LLMError):
    """LLM returned malformed / unparseable response."""

    def __init__(self, message: str = "Malformed LLM response", **kwargs):
        super().__init__(message, retryable=True, **kwargs)


class LLMConnectionError(LLMError):
    """Network timeout or connection failure — retryable."""

    def __init__(self, message: str = "LLM connection failed", **kwargs):
        super().__init__(message, retryable=True, **kwargs)


# ── Extraction ───────────────────────────────────────────────────────

class ExtractionError(PipelineError):
    """Phase-level extraction failure."""
    pass


class SchemaValidationError(ExtractionError):
    """LLM output doesn't match the expected Pydantic schema."""
    pass


class PDFExtractionError(ExtractionError):
    """PDF read failure, page range issues, or corrupt file."""
    pass


# ── Validation ───────────────────────────────────────────────────────

class ValidationError(PipelineError):
    """Post-extraction validation failure."""
    pass


class USDMValidationError(ValidationError):
    """USDM schema violations detected."""
    pass


class M11ConformanceError(ValidationError):
    """M11 conformance check failures."""
    pass
