from __future__ import annotations

import re
from pathlib import Path

from src import __version__, get_version


SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def test_version_file_contains_semver() -> None:
    version = Path("VERSION").read_text(encoding="utf-8").strip()
    assert SEMVER_RE.match(version)


def test_python_version_matches_version_file() -> None:
    version = Path("VERSION").read_text(encoding="utf-8").strip()
    assert get_version() == version
    assert __version__ == version
