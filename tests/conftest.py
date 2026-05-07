from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolate_analysis_runtime_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep analysis side effects from tests inside pytest's temp directory."""

    data_dir = tmp_path / "data"
    private_dir = data_dir / "private"
    outputs_dir = data_dir / "analysis_outputs"
    workflow_db = data_dir / "db" / "analysis_workflow.sqlite"
    prompts_dir = private_dir / "analysis_prompts"
    snapshots_dir = private_dir / "prompt_snapshots"
    latest_md = outputs_dir / "summaries" / "analysis_latest.md"

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
