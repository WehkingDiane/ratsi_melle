"""Shared RI paths, access boundary and isolated CLI logging."""
from __future__ import annotations

from datetime import date
import json
import logging
from pathlib import Path
import re

from src.config.ri_proton import RiAccessError
from src.observability import SafeFormatter, configure_logging
from src.paths import REPO_ROOT, RI_DATA_DIR

BASE_URL = "https://session.melle.info/ri"
RI_ROOT = RI_DATA_DIR
DEFAULT_CONFIG = Path(__file__).with_name("ri.json")


def select_months(year, months, config_path=None):
    """Exclude inaccessible months before any authentication or network request."""
    path = config_path or (RI_ROOT / "config.json" if (RI_ROOT / "config.json").exists() else DEFAULT_CONFIG)
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))["earliest_month"]
        boundary = date.fromisoformat(value + "-01")
        if boundary.strftime("%Y-%m") != value:
            raise ValueError
    except (OSError, ValueError, TypeError, KeyError):
        raise RiAccessError("RI-Konfiguration benötigt earliest_month im Format YYYY-MM.") from None
    if not 1 <= year <= 9999 or not months or any(m not in range(1, 13) for m in months):
        raise RiAccessError("Gültiges Jahr und mindestens einen Monat (1-12) angeben.")
    selected = tuple(dict.fromkeys(m for m in months if date(year, m, 1) >= boundary))
    if not selected:
        raise RiAccessError(f"Keine abrufbaren Monate: RI-Zugang erst ab {value}.")
    return selected


class RiFormatter(SafeFormatter):
    """Keep protected URLs out of RI console output and log files."""

    def format(self, record):
        return re.sub(r"https?://session\.melle\.info/ri/[^\s\"'<>]*", "[RI-URL]", super().format(record))


def configure_file_logging(script_name: str, log_level: str | None = None) -> Path:
    """Use bounded project logging in the dedicated logs/ri directory."""
    path = configure_logging(script_name, log_level, log_dir=REPO_ROOT / "logs" / "ri")
    for handler in logging.getLogger().handlers:
        formatter = handler.formatter
        handler.setFormatter(RiFormatter(formatter._fmt, formatter.datefmt))
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    return path
