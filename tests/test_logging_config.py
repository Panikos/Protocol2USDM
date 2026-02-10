"""
Tests for core.logging_config — structured JSON logging.

Validates:
- JSONFormatter produces valid JSON lines
- ConsoleFormatter produces human-readable output
- configure_logging() sets up handlers correctly
- PhaseLoggerAdapter injects phase/model into records
- --json-log and --log-file integration
"""

import json
import logging
import os
import tempfile

import pytest

from core.logging_config import (
    JSONFormatter,
    ConsoleFormatter,
    PhaseLoggerAdapter,
    configure_logging,
)


@pytest.fixture(autouse=True)
def _reset_root_logger():
    """Reset root logger between tests."""
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    yield
    root.handlers = original_handlers
    root.level = original_level


# ── JSONFormatter ────────────────────────────────────────────────────

class TestJSONFormatter:
    """JSON formatter produces valid, parseable JSON lines."""

    def test_basic_record(self):
        fmt = JSONFormatter()
        record = logging.LogRecord(
            name="test.module", level=logging.INFO, pathname="",
            lineno=0, msg="hello %s", args=("world",), exc_info=None,
        )
        line = fmt.format(record)
        data = json.loads(line)
        assert data["level"] == "INFO"
        assert data["logger"] == "test.module"
        assert data["msg"] == "hello world"
        assert "ts" in data

    def test_includes_phase_if_present(self):
        fmt = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="",
            lineno=0, msg="extracting", args=(), exc_info=None,
        )
        record.phase = "metadata"
        line = fmt.format(record)
        data = json.loads(line)
        assert data["phase"] == "metadata"

    def test_includes_model_if_present(self):
        fmt = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="",
            lineno=0, msg="calling LLM", args=(), exc_info=None,
        )
        record.model = "gemini-3-flash"
        line = fmt.format(record)
        data = json.loads(line)
        assert data["model"] == "gemini-3-flash"

    def test_includes_error_on_exception(self):
        fmt = JSONFormatter()
        try:
            raise ValueError("bad value")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="",
            lineno=0, msg="failed", args=(), exc_info=exc_info,
        )
        line = fmt.format(record)
        data = json.loads(line)
        assert data["error"]["type"] == "ValueError"
        assert "bad value" in data["error"]["message"]

    def test_no_error_key_without_exception(self):
        fmt = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.WARNING, pathname="",
            lineno=0, msg="warn", args=(), exc_info=None,
        )
        line = fmt.format(record)
        data = json.loads(line)
        assert "error" not in data


# ── ConsoleFormatter ─────────────────────────────────────────────────

class TestConsoleFormatter:
    """Console formatter produces human-readable output."""

    def test_info_format(self):
        fmt = ConsoleFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="",
            lineno=0, msg="hello", args=(), exc_info=None,
        )
        line = fmt.format(record)
        assert "[INFO]" in line
        assert "hello" in line

    def test_error_format(self):
        fmt = ConsoleFormatter()
        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="",
            lineno=0, msg="boom", args=(), exc_info=None,
        )
        line = fmt.format(record)
        assert "ERROR" in line
        assert "boom" in line


# ── configure_logging ────────────────────────────────────────────────

class TestConfigureLogging:
    """configure_logging() sets up handlers correctly."""

    def test_default_console_handler(self):
        configure_logging()
        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, ConsoleFormatter)

    def test_json_mode_console(self):
        configure_logging(json_mode=True)
        root = logging.getLogger()
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, JSONFormatter)

    def test_log_file_adds_handler(self):
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
            path = f.name
        try:
            configure_logging(log_file=path)
            root = logging.getLogger()
            assert len(root.handlers) == 2  # console + file
            # File handler uses JSON
            file_handler = [h for h in root.handlers if isinstance(h, logging.FileHandler)][0]
            assert isinstance(file_handler.formatter, JSONFormatter)
        finally:
            # Clean up
            for h in logging.getLogger().handlers[:]:
                if isinstance(h, logging.FileHandler):
                    h.close()
            os.unlink(path)

    def test_quiet_mode_no_console(self):
        configure_logging(quiet=True)
        root = logging.getLogger()
        assert len(root.handlers) == 0

    def test_log_file_writes_json(self):
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False, mode="w") as f:
            path = f.name
        try:
            configure_logging(log_file=path)
            test_logger = logging.getLogger("test.json_write")
            test_logger.info("test message")
            # Flush
            for h in logging.getLogger().handlers:
                h.flush()
            with open(path, "r") as f:
                lines = f.readlines()
            assert len(lines) >= 1
            data = json.loads(lines[0])
            assert data["msg"] == "test message"
        finally:
            for h in logging.getLogger().handlers[:]:
                if isinstance(h, logging.FileHandler):
                    h.close()
            os.unlink(path)


# ── PhaseLoggerAdapter ───────────────────────────────────────────────

class TestPhaseLoggerAdapter:
    """PhaseLoggerAdapter injects phase and model into records."""

    def test_adapter_adds_phase(self):
        base = logging.getLogger("test.adapter")
        adapter = PhaseLoggerAdapter(base, {"phase": "eligibility", "model": "gemini-3-flash"})
        msg, kwargs = adapter.process("test msg", {})
        assert kwargs["extra"]["phase"] == "eligibility"
        assert kwargs["extra"]["model"] == "gemini-3-flash"

    def test_adapter_defaults(self):
        base = logging.getLogger("test.adapter2")
        adapter = PhaseLoggerAdapter(base, {})
        msg, kwargs = adapter.process("test", {})
        assert kwargs["extra"]["phase"] == ""
        assert kwargs["extra"]["model"] == ""
