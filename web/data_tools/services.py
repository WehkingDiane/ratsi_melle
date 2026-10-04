"""Service facade for local data and technical service views."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.services import paths
from core.services import status
from core.services.session_inventory import yearly_session_inventory as _yearly_session_inventory
from core.services.commands import build_service_command as _build_service_command
from core.services.model_preparation import preparation_confirmation
from core.services.model_preparation import confirmed_preparation_binding
from core.services.legacy_inspection import confirmed_inspection_context
from core.services.legacy_inspection import inspection_forms as _inspection_forms
from core.services.legacy_inspection import inspection_result
from core.services.legacy_inspection import application_confirmation
from core.services.legacy_inspection import confirmed_application_payload
from core.services.model_job_history import model_job_history
from core.services.model_job_history import model_job_detail
from src.config.embedding_model_status import embedding_model_inventory_status as _embedding_model_inventory_status
from src.indexing.vector_status import landkreis_vector_index_status as _landkreis_vector_index_status
from src.indexing.vector_status import vector_index_status as _vector_index_status


REPO_ROOT = paths.REPO_ROOT
LOCAL_INDEX_DB = paths.LOCAL_INDEX_DB
LANDKREIS_PUBLICATIONS_DB = paths.LANDKREIS_PUBLICATIONS_DB
QDRANT_DIR = paths.QDRANT_DIR
DEFAULT_SCRIPT_TIMEOUT_SECONDS = paths.DEFAULT_SCRIPT_TIMEOUT_SECONDS


def _sync_paths() -> None:
    paths.REPO_ROOT = Path(REPO_ROOT)
    paths.LOCAL_INDEX_DB = Path(LOCAL_INDEX_DB)
    paths.LANDKREIS_PUBLICATIONS_DB = Path(LANDKREIS_PUBLICATIONS_DB)
    paths.QDRANT_DIR = Path(QDRANT_DIR)
    paths.DEFAULT_SCRIPT_TIMEOUT_SECONDS = int(DEFAULT_SCRIPT_TIMEOUT_SECONDS)


def build_service_command(action: str, data: dict[str, Any]) -> tuple[list[str] | None, list[str]]:
    _sync_paths()
    return _build_service_command(action, data)


def service_status() -> dict[str, Any]:
    _sync_paths()
    return status.service_status()


def yearly_session_inventory() -> dict[str, Any]:
    """Return the full yearly inventory without a date cutoff."""
    _sync_paths()
    return _yearly_session_inventory()


def legacy_inspection_forms() -> list[dict]:
    """Present the two fixed Melle targets without inspecting their contents."""
    _sync_paths()
    return _inspection_forms()


def embedding_model_status() -> dict[str, object]:
    """Return the shared offline model summary without querying Qdrant."""

    return _embedding_model_inventory_status()


def vector_index_status() -> dict[str, Any]:
    _sync_paths()
    return _vector_index_status(
        local_index_db=paths.LOCAL_INDEX_DB,
        qdrant_dir=paths.QDRANT_DIR,
    )


def landkreis_vector_index_status() -> dict[str, Any]:
    _sync_paths()
    return _landkreis_vector_index_status(
        landkreis_db=paths.LANDKREIS_PUBLICATIONS_DB,
        qdrant_dir=paths.QDRANT_DIR,
    )
