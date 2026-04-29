"""Status and overview data for web UI pages."""

from __future__ import annotations

from typing import Any

from . import paths
from .outputs import list_analysis_outputs
from .sessions import list_sessions


def service_status() -> dict[str, Any]:
    """Return lightweight status for service pages."""

    return {
        "local_index_exists": paths.LOCAL_INDEX_DB.exists() and paths.LOCAL_INDEX_DB.stat().st_size > 0,
        "online_index_exists": (paths.REPO_ROOT / "data" / "db" / "online_session_index.sqlite").exists(),
        "qdrant_exists": (paths.REPO_ROOT / "data" / "db" / "qdrant").exists(),
        "raw_data_exists": (paths.REPO_ROOT / "data" / "raw").exists(),
        "local_index_path": "data/db/local_index.sqlite",
        "online_index_path": "data/db/online_session_index.sqlite",
        "qdrant_path": "data/db/qdrant/",
        "raw_data_path": "data/raw/",
    }


def source_overview() -> dict[str, Any]:
    """Return basic source availability for overview pages."""

    return {
        "local_index_exists": paths.LOCAL_INDEX_DB.exists() and paths.LOCAL_INDEX_DB.stat().st_size > 0,
        "analysis_outputs_exists": paths.ANALYSIS_OUTPUTS_DIR.exists(),
        "session_count": len(list_sessions()),
        "analysis_count": len(list_analysis_outputs()),
        "local_index_path": str(paths.LOCAL_INDEX_DB.relative_to(paths.REPO_ROOT)),
        "analysis_outputs_path": str(paths.ANALYSIS_OUTPUTS_DIR.relative_to(paths.REPO_ROOT)),
    }
