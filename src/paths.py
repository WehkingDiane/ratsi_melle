"""Central project path constants used by scripts and GUI components."""

from __future__ import annotations

import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

DATA_ROOT = REPO_ROOT / "data"
PRIVATE_DATA_DIR = Path(os.environ.get("RATSI_PRIVATE_DATA_DIR", DATA_ROOT / "private")).expanduser()
RAW_DATA_DIR = DATA_ROOT / "raw"
DB_DIR = DATA_ROOT / "db"
PROCESSED_DATA_DIR = DATA_ROOT / "processed"
ANALYSIS_REQUESTS_DIR = DATA_ROOT / "analysis_requests"
ANALYSIS_OUTPUTS_DIR = DATA_ROOT / "analysis_outputs"
ANALYSIS_SUMMARIES_DIR = ANALYSIS_OUTPUTS_DIR / "summaries"
ANALYSIS_PROMPTS_DIR = ANALYSIS_OUTPUTS_DIR / "prompts"
MODELS_DIR = DATA_ROOT / "models"
PROMPT_TEMPLATES_EXAMPLE = REPO_ROOT / "configs" / "prompt_templates.example.json"
PROMPT_TEMPLATES_PATH = Path(
    os.environ.get("RATSI_PROMPT_TEMPLATES_PATH", PRIVATE_DATA_DIR / "prompt_templates.json")
).expanduser()
PROMPT_SNAPSHOTS_DIR = PRIVATE_DATA_DIR / "prompt_snapshots"

LOCAL_INDEX_DB = DB_DIR / "local_index.sqlite"
ANALYSIS_WORKFLOW_DB = DB_DIR / "analysis_workflow.sqlite"
QDRANT_DIR = DB_DIR / "qdrant"
ONLINE_INDEX_DB = DB_DIR / "online_session_index.sqlite"
DEFAULT_ANALYSIS_BATCH = ANALYSIS_REQUESTS_DIR / "analysis_batch.json"
DEFAULT_ANALYSIS_MARKDOWN = ANALYSIS_SUMMARIES_DIR / "analysis_latest.md"
