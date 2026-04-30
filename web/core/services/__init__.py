"""Shared service helpers for the Django web UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import paths
from . import status


REPO_ROOT = paths.REPO_ROOT
LOCAL_INDEX_DB = paths.LOCAL_INDEX_DB
ANALYSIS_WORKFLOW_DB = paths.ANALYSIS_WORKFLOW_DB
ANALYSIS_OUTPUTS_DIR = paths.ANALYSIS_OUTPUTS_DIR
PROMPT_TEMPLATES_PATH = paths.PROMPT_TEMPLATES_PATH
DEFAULT_SCRIPT_TIMEOUT_SECONDS = paths.DEFAULT_SCRIPT_TIMEOUT_SECONDS


def _sync_paths() -> None:
    paths.REPO_ROOT = Path(REPO_ROOT)
    paths.LOCAL_INDEX_DB = Path(LOCAL_INDEX_DB)
    paths.ANALYSIS_WORKFLOW_DB = Path(ANALYSIS_WORKFLOW_DB)
    paths.ANALYSIS_OUTPUTS_DIR = Path(ANALYSIS_OUTPUTS_DIR)
    paths.PROMPT_TEMPLATES_PATH = Path(PROMPT_TEMPLATES_PATH)
    paths.DEFAULT_SCRIPT_TIMEOUT_SECONDS = int(DEFAULT_SCRIPT_TIMEOUT_SECONDS)


def service_status() -> dict[str, Any]:
    _sync_paths()
    return status.service_status()


def source_overview() -> dict[str, Any]:
    _sync_paths()
    return status.source_overview()
