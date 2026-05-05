from __future__ import annotations

import json
from pathlib import Path

from src.analysis.schemas import AnalysisOutputRecord
from src.analysis.service import AnalysisService


def test_v2_output_paths_use_session_folder_and_do_not_overwrite(
    tmp_path: Path, monkeypatch
) -> None:
    outputs_dir = tmp_path / "data" / "analysis_outputs"
    prompts_dir = tmp_path / "data" / "private" / "analysis_prompts"
    snapshots_dir = tmp_path / "data" / "private" / "prompt_snapshots"
    latest_md = outputs_dir / "summaries" / "analysis_latest.md"
    workflow_db = tmp_path / "data" / "db" / "analysis_workflow.sqlite"

    monkeypatch.setattr("src.analysis.service.ANALYSIS_OUTPUTS_DIR", outputs_dir)
    monkeypatch.setattr("src.analysis.service.ANALYSIS_PROMPTS_DIR", prompts_dir)
    monkeypatch.setattr("src.analysis.service.PROMPT_SNAPSHOTS_DIR", snapshots_dir)
    monkeypatch.setattr("src.analysis.service.DEFAULT_ANALYSIS_MARKDOWN", latest_md)
    monkeypatch.setattr("src.analysis.workflow_db.ANALYSIS_WORKFLOW_DB", workflow_db)

    session_path = tmp_path / "data" / "raw" / "2026" / "03" / "2026-03-11_Rat_7123"
    existing_doc = session_path / "agenda" / "oe8" / "vorlage.txt"
    existing_doc.parent.mkdir(parents=True, exist_ok=True)
    existing_doc.write_text("Quelle", encoding="utf-8")
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
                "session_path": str(session_path),
                "url": "https://example.org/vorlage",
            },
            {
                "title": "Vorhandene Vorlage",
                "document_type": "beschlussvorlage",
                "agenda_item": "Oe 8",
                "local_path": "agenda/oe8/vorlage.txt",
                "session_path": str(session_path),
                "url": "https://example.org/vorlage2",
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
    assert (prompts_dir / "job_1.txt").exists()
    assert (snapshots_dir / "job_1.txt").exists()
    assert not (outputs_dir / "prompts" / "job_1.txt").exists()

    raw_payload = json.loads((session_out_dir / "job_1.raw.json").read_text(encoding="utf-8"))
    availability = {
        doc["agenda_item"]: doc["source_available"] for doc in raw_payload["documents"]
    }
    assert availability == {"Oe 7": False, "Oe 8": True}


def test_publication_artifacts_are_skipped_for_failed_jobs(
    tmp_path: Path, monkeypatch
) -> None:
    outputs_dir = tmp_path / "data" / "analysis_outputs"
    prompts_dir = tmp_path / "data" / "private" / "analysis_prompts"
    snapshots_dir = tmp_path / "data" / "private" / "prompt_snapshots"
    latest_md = outputs_dir / "summaries" / "analysis_latest.md"
    workflow_db = tmp_path / "data" / "db" / "analysis_workflow.sqlite"

    monkeypatch.setattr("src.analysis.service.ANALYSIS_OUTPUTS_DIR", outputs_dir)
    monkeypatch.setattr("src.analysis.service.ANALYSIS_PROMPTS_DIR", prompts_dir)
    monkeypatch.setattr("src.analysis.service.PROMPT_SNAPSHOTS_DIR", snapshots_dir)
    monkeypatch.setattr("src.analysis.service.DEFAULT_ANALYSIS_MARKDOWN", latest_md)
    monkeypatch.setattr("src.analysis.workflow_db.ANALYSIS_WORKFLOW_DB", workflow_db)

    session_path = tmp_path / "data" / "raw" / "2026" / "03" / "2026-03-11_Rat_7123"
    record = AnalysisOutputRecord(
        job_id=2,
        created_at="2026-03-11T10:00:00Z",
        session_id="7123",
        scope="tops",
        top_numbers=["Oe 7"],
        purpose="journalistic_publication",
        markdown="# Analyse",
        source_db=str(tmp_path / "local_index.sqlite"),
        session_path=str(session_path),
        session_date="2026-03-11",
        status="error",
        error_message="Provider fehlgeschlagen",
    )

    AnalysisService().persist_analysis_artifacts(
        record,
        documents=[],
        session={"meeting_name": "Rat"},
    )

    session_out_dir = outputs_dir / "2026" / "03" / "2026-03-11_Rat_7123"
    assert (session_out_dir / "job_2.raw.json").exists()
    assert (session_out_dir / "job_2.structured.json").exists()
    assert (session_out_dir / "job_2.article.md").exists()
    assert not (session_out_dir / "job_2.publication.json").exists()
