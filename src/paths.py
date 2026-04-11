"""Central project path constants used by scripts and GUI components."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

DATA_ROOT = REPO_ROOT / "data"
RAW_DATA_DIR = DATA_ROOT / "raw"
DB_DIR = DATA_ROOT / "db"
PROCESSED_DATA_DIR = DATA_ROOT / "processed"
ANALYSIS_REQUESTS_DIR = DATA_ROOT / "analysis_requests"
ANALYSIS_OUTPUTS_DIR = DATA_ROOT / "analysis_outputs"
ANALYSIS_SUMMARIES_DIR = ANALYSIS_OUTPUTS_DIR / "summaries"
ANALYSIS_PROMPTS_DIR = ANALYSIS_OUTPUTS_DIR / "prompts"
MODELS_DIR = DATA_ROOT / "models"

LOCAL_INDEX_DB = DB_DIR / "local_index.sqlite"
QDRANT_DIR = DB_DIR / "qdrant"
ONLINE_INDEX_DB = DB_DIR / "online_session_index.sqlite"
DEFAULT_ANALYSIS_BATCH = ANALYSIS_REQUESTS_DIR / "analysis_batch.json"
DEFAULT_ANALYSIS_MARKDOWN = ANALYSIS_SUMMARIES_DIR / "analysis_latest.md"
