"""
Structured logging configuration for Protocol2USDM.

Provides two formatters:
- **ConsoleFormatter**: Human-readable colored output (default for terminal)
- **JSONFormatter**: Machine-parseable JSON lines (for --json-log flag or file output)

Usage:
    from core.logging_config import configure_logging
    configure_logging(json_mode=args.json_log, log_file=args.log_file)
"""

import json
import logging
import sys
import time
from typing import Optional


class JSONFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.name != "root":
            # Add module path for non-root loggers
            entry["module"] = record.module
        if hasattr(record, "phase"):
            entry["phase"] = record.phase
        if hasattr(record, "model"):
            entry["model"] = record.model
        if record.exc_info and record.exc_info[1]:
            entry["error"] = {
                "type": type(record.exc_info[1]).__name__,
                "message": str(record.exc_info[1]),
            }
        return json.dumps(entry, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    """Human-readable formatter with level-based prefixes."""

    FORMATS = {
        logging.DEBUG: "\033[90m[DEBUG]\033[0m %(message)s",
        logging.INFO: "[%(levelname)s] %(message)s",
        logging.WARNING: "\033[33m[WARN]\033[0m %(message)s",
        logging.ERROR: "\033[31m[ERROR]\033[0m %(message)s",
        logging.CRITICAL: "\033[1;31m[CRIT]\033[0m %(message)s",
    }

    def format(self, record: logging.LogRecord) -> str:
        fmt = self.FORMATS.get(record.levelno, "[%(levelname)s] %(message)s")
        formatter = logging.Formatter(fmt)
        return formatter.format(record)


def configure_logging(
    *,
    json_mode: bool = False,
    log_file: Optional[str] = None,
    level: int = logging.INFO,
    quiet: bool = False,
) -> None:
    """
    Configure root logger with appropriate handlers.

    Args:
        json_mode: If True, use JSON formatter for console output.
        log_file: If set, also write JSON logs to this file.
        level: Logging level (default INFO).
        quiet: If True, suppress console output (only file).
    """
    root = logging.getLogger()
    root.setLevel(level)

    # Remove any existing handlers (e.g., from basicConfig)
    root.handlers.clear()

    # Console handler
    if not quiet:
        console = logging.StreamHandler(sys.stderr)
        console.setLevel(level)
        if json_mode:
            console.setFormatter(JSONFormatter())
        else:
            console.setFormatter(ConsoleFormatter())
        root.addHandler(console)

    # File handler (always JSON)
    if log_file:
        from pathlib import Path
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(JSONFormatter())
        root.addHandler(fh)


class PhaseLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that injects phase and model into every record."""

    def process(self, msg, kwargs):
        extra = kwargs.setdefault("extra", {})
        extra.setdefault("phase", self.extra.get("phase", ""))
        extra.setdefault("model", self.extra.get("model", ""))
        return msg, kwargs
