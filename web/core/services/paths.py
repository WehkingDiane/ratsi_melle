"""Shared paths for web UI services."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
LOCAL_INDEX_DB = REPO_ROOT / "data" / "db" / "local_index.sqlite"
ANALYSIS_WORKFLOW_DB = REPO_ROOT / "data" / "db" / "analysis_workflow.sqlite"
ANALYSIS_OUTPUTS_DIR = REPO_ROOT / "data" / "analysis_outputs"
PROMPT_TEMPLATES_PATH = REPO_ROOT / "configs" / "prompt_templates.json"
DEFAULT_SCRIPT_TIMEOUT_SECONDS = 900
