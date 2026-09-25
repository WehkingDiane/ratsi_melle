from __future__ import annotations

from pathlib import Path
import sys

import pytest


@pytest.fixture(autouse=True)
def isolate_analysis_runtime_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep analysis side effects from tests inside pytest's temp directory."""

    monkeypatch.delenv("RATSI_QDRANT_URL", raising=False)
    monkeypatch.setenv("RATSI_QDRANT_MODE", "local")
    monkeypatch.setenv("RATSI_QDRANT_STATE_DIR", str(tmp_path / "qdrant_server_state"))
    from src.qdrant_connection import QdrantConnection
    original_client = QdrantConnection.create_client

    def isolated_client(connection):
        if connection.url:
            raise AssertionError("Tests must mock remote clients or use a dedicated test server")
        allowed = (tmp_path.resolve(), Path(__file__).resolve().parent / "_runtime_tmp")
        if not any(connection.path.resolve().is_relative_to(path) for path in allowed):
            raise AssertionError("Tests must use a temporary Qdrant directory")
        return original_client(connection)

    monkeypatch.setattr(QdrantConnection, "create_client", isolated_client)
    data_dir = tmp_path / "data"
    private_dir = data_dir / "private"
    outputs_dir = data_dir / "analysis_outputs"
    workflow_db = data_dir / "db" / "analysis_workflow.sqlite"
    prompts_dir = private_dir / "analysis_prompts"
    snapshots_dir = private_dir / "prompt_snapshots"
    latest_md = outputs_dir / "summaries" / "analysis_latest.md"
    service_jobs_db = data_dir / "db" / "service_jobs.sqlite"

    monkeypatch.setattr("src.paths.ANALYSIS_WORKFLOW_DB", workflow_db)
    monkeypatch.setattr("src.paths.ANALYSIS_OUTPUTS_DIR", outputs_dir)
    monkeypatch.setattr("src.paths.ANALYSIS_PROMPTS_DIR", prompts_dir)
    monkeypatch.setattr("src.paths.PROMPT_SNAPSHOTS_DIR", snapshots_dir)
    monkeypatch.setattr("src.paths.DEFAULT_ANALYSIS_MARKDOWN", latest_md)
    monkeypatch.setattr("src.analysis.workflow_db.ANALYSIS_WORKFLOW_DB", workflow_db)
    monkeypatch.setattr("src.analysis.service.ANALYSIS_OUTPUTS_DIR", outputs_dir)
    monkeypatch.setattr("src.analysis.service.ANALYSIS_PROMPTS_DIR", prompts_dir)
    monkeypatch.setattr("src.analysis.service.PROMPT_SNAPSHOTS_DIR", snapshots_dir)
    monkeypatch.setattr("src.analysis.service.DEFAULT_ANALYSIS_MARKDOWN", latest_md)
    service_jobs = sys.modules.get("core.service_jobs")
    if service_jobs is not None:
        monkeypatch.setattr(service_jobs, "SERVICE_JOBS_DB", service_jobs_db)
