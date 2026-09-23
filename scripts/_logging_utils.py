"""Shared logging setup for command-line data workflows."""

from __future__ import annotations

import logging
from pathlib import Path
import sys
from time import gmtime


def configure_file_logging(script_name: str, log_level: str = "INFO") -> Path:
    """Log CLI messages to stderr and ``logs/<script_name>.log``."""

    log_dir = Path(__file__).resolve().parents[1] / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{script_name}.log"
    level = getattr(logging, log_level.upper(), logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)sZ %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    formatter.converter = gmtime
    root = logging.getLogger()
    root.setLevel(level)
    # Replace handlers so repeated main() calls do not duplicate log records.
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(console)
    root.addHandler(file_handler)
    return log_path
