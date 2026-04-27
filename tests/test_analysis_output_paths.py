from __future__ import annotations

from pathlib import Path

from src.analysis.schemas import AnalysisOutputRecord
from src.analysis.service import AnalysisService


def test_v2_output_paths_use_session_folder_and_do_not_overwrite(
    tmp_path: Path, monkeypatch
) -> None:
    outputs_dir = tmp_path / "data" / "analysis_outputs"
    prompts_dir = outputs_dir / "prompts"
    latest_md = outputs_dir / "summaries" / "analysis_latest.md"
    workflow_db = tmp_path / "data" / "db" / "analysis_workflow.sqlite"

    monkeypatch.setattr("src.analysis.service.ANALYSIS_OUTPUTS_DIR", outputs_dir)
    monkeypatch.setattr("src.analysis.service.ANALYSIS_PROMPTS_DIR", prompts_dir)
    monkeypatch.setattr("src.analysis.service.DEFAULT_ANALYSIS_MARKDOWN", latest_md)
    monkeypatch.setattr("src.analysis.workflow_db.ANALYSIS_WORKFLOW_DB", workflow_db)

    session_path = tmp_path / "data" / "raw" / "2026" / "03" / "2026-03-11_Rat_7123"
    record = AnalysisOutputRecord(
        job_id=1,
        created_at="2026-03-11T10:00:00Z",
        session_id="7123",
        scope="tops",
        top_numbers=["Oe 7"],
        purpose="journalistic_publication",
        markdown="# Analyse",
        source_db=str(tmp_path / "local_index.sqlite"),
        session_path=str(session_path),
        session_date="2026-03-11",
        status="done",
    )

    service = AnalysisService()
    service.persist_analysis_artifacts(
        record,
        documents=[
            {
                "title": "Vorlage",
                "document_type": "beschlussvorlage",
                "agenda_item": "Oe 7",
                "local_path": "agenda/oe7/vorlage.txt",
                "url": "https://example.org/vorlage",
            }
        ],
        session={"meeting_name": "Rat"},
    )
    service.persist_analysis_artifacts(record, documents=[], session={"meeting_name": "Rat"})

    session_out_dir = outputs_dir / "2026" / "03" / "2026-03-11_Rat_7123"
    assert (session_out_dir / "job_1.raw.json").exists()
    assert (session_out_dir / "job_1.structured.json").exists()
    assert (session_out_dir / "job_1.publication.json").exists()
    assert (session_out_dir / "job_1.article.md").exists()
    assert (session_out_dir / "job_1.raw.1.json").exists()
    assert (session_out_dir / "job_1.article.1.md").exists()
