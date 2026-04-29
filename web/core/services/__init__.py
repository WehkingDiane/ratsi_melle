"""Service facade for the Django web UI.

The implementation is split into focused modules, while this facade keeps the
existing ``from core import services`` call sites stable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import outputs
from . import paths
from . import prompts
from . import sessions
from . import source_check
from . import status
from .analysis import analysis_purpose_options
from .analysis import provider_options
from .analysis import run_analysis_from_form as _run_analysis_from_form
from .commands import build_service_command


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


def list_sessions() -> list[dict[str, Any]]:
    _sync_paths()
    return sessions.list_sessions()


def get_session(session_id: str) -> dict[str, Any] | None:
    _sync_paths()
    return sessions.get_session(session_id)


def check_sources(session_id: str) -> dict[str, Any]:
    _sync_paths()
    return source_check.check_sources(session_id)


def list_analysis_outputs() -> list[dict[str, Any]]:
    _sync_paths()
    return outputs.list_analysis_outputs()


def get_analysis_output(job_id: str) -> dict[str, Any] | None:
    _sync_paths()
    return outputs.get_analysis_output(job_id)


def list_prompt_templates(scope: str = "") -> list[dict[str, Any]]:
    _sync_paths()
    return prompts.list_prompt_templates(scope)


def get_prompt_template(template_id: str) -> dict[str, Any] | None:
    _sync_paths()
    return prompts.get_prompt_template(template_id)


def save_prompt_template_from_form(data: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    _sync_paths()
    return prompts.save_prompt_template_from_form(data)


def service_status() -> dict[str, Any]:
    _sync_paths()
    return status.service_status()


def source_overview() -> dict[str, Any]:
    _sync_paths()
    return status.source_overview()


def run_analysis_from_form(data: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    _sync_paths()
    return _run_analysis_from_form(data)
