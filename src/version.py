"""Project software version helpers."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path


VERSION_FILE = Path(__file__).resolve().parents[1] / "VERSION"


@lru_cache(maxsize=1)
def get_version() -> str:
    """Return the canonical project version from the repository root."""

    return VERSION_FILE.read_text(encoding="utf-8").strip()


__version__ = get_version()
