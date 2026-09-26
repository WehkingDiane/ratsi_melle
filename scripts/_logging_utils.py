"""Compatibility wrapper for shared project logging."""

from __future__ import annotations

from pathlib import Path

from src.observability import configure_logging


def configure_file_logging(script_name: str, log_level: str = "INFO") -> Path:
    """Log CLI messages with the shared project configuration."""

    return configure_logging(script_name, log_level)
