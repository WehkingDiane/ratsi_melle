"""Service facade for local data and technical service views."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.services import paths
from core.services import status
from core.services.commands import build_service_command as _build_service_command


REPO_ROOT = paths.REPO_ROOT
LOCAL_INDEX_DB = paths.LOCAL_INDEX_DB
DEFAULT_SCRIPT_TIMEOUT_SECONDS = paths.DEFAULT_SCRIPT_TIMEOUT_SECONDS


def _sync_paths() -> None:
    paths.REPO_ROOT = Path(REPO_ROOT)
    paths.LOCAL_INDEX_DB = Path(LOCAL_INDEX_DB)
    paths.DEFAULT_SCRIPT_TIMEOUT_SECONDS = int(DEFAULT_SCRIPT_TIMEOUT_SECONDS)


def build_service_command(action: str, data: dict[str, Any]) -> tuple[list[str] | None, list[str]]:
    _sync_paths()
    return _build_service_command(action, data)


def service_status() -> dict[str, Any]:
    _sync_paths()
    return status.service_status()
