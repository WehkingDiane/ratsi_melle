"""Expose central project paths to web services without duplicating defaults."""

from __future__ import annotations

from src.paths import (
    ANALYSIS_OUTPUTS_DIR,
    ANALYSIS_PROMPTS_DIR,
    ANALYSIS_WORKFLOW_DB,
    LANDKREIS_PUBLICATIONS_DB,
    LOCAL_INDEX_DB,
    ONLINE_INDEX_DB,
    PRIVATE_DATA_DIR,
    PROMPT_SNAPSHOTS_DIR,
    PROMPT_TEMPLATES_EXAMPLE,
    PROMPT_TEMPLATES_PATH,
    QDRANT_DIR,
    RAW_DATA_DIR,
    REPO_ROOT,
    SERVICE_JOBS_DB,
)

DEFAULT_SCRIPT_TIMEOUT_SECONDS = 900
