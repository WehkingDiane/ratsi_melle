"""Shared paths for web UI services."""

from __future__ import annotations

import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
PRIVATE_DATA_DIR = Path(os.environ.get("RATSI_PRIVATE_DATA_DIR", REPO_ROOT / "data" / "private")).expanduser()
LOCAL_INDEX_DB = REPO_ROOT / "data" / "db" / "local_index.sqlite"
ANALYSIS_WORKFLOW_DB = REPO_ROOT / "data" / "db" / "analysis_workflow.sqlite"
ANALYSIS_OUTPUTS_DIR = REPO_ROOT / "data" / "analysis_outputs"
ANALYSIS_PROMPTS_DIR = PRIVATE_DATA_DIR / "analysis_prompts"
PROMPT_TEMPLATES_EXAMPLE = REPO_ROOT / "configs" / "prompt_templates.example.json"
PROMPT_TEMPLATES_PATH = Path(
    os.environ.get("RATSI_PROMPT_TEMPLATES_PATH", PRIVATE_DATA_DIR / "prompt_templates.json")
).expanduser()
PROMPT_SNAPSHOTS_DIR = PRIVATE_DATA_DIR / "prompt_snapshots"
DEFAULT_SCRIPT_TIMEOUT_SECONDS = 900
