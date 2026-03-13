from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.analysis.schemas import ANALYSIS_OUTPUT_SCHEMA_VERSION
from src.analysis.service import AnalysisRequest, AnalysisService


def _build_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "data" / "db" / "local_index.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    session_dir = tmp_path / "data" / "raw" / "2026" / "03" / "2026-03-10_Rat_7001"
    doc_dir = session_dir / "agenda" / "o1"
    doc_dir.mkdir(parents=True, exist_ok=True)
    (doc_dir / "vorlage.txt").write_text(
        "Beschlussvorschlag: Der Rat beschliesst die Umsetzung des Projekts.\n"
        "Finanzielle Auswirkungen: 20.000 EUR im Haushalt 2026.\n",
        encoding="utf-8",
    )

    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE sessions (
                session_id TEXT PRIMARY KEY,
                date TEXT,
                committee TEXT,
                meeting_name TEXT,
                session_path TEXT
            );
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                agenda_item TEXT,
                title TEXT,
                document_type TEXT,
                local_path TEXT,
                url TEXT,
                content_type TEXT
            );
            """
        )
        conn.execute(
            "INSERT INTO sessions (session_id, date, committee, meeting_name, session_path) VALUES (?, ?, ?, ?, ?)",
            ("7001", "2026-03-10", "Rat", "Ratssitzung", str(session_dir)),
        )
        conn.execute(
            "INSERT INTO documents (session_id, agenda_item, title, document_type, local_path, url, content_type) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("7001", "Oe 1", "Vorlage Projekt", "vorlage", "agenda/o1/vorlage.txt", "https://example.org/vorlage", "text/plain"),
        )
        conn.commit()
    return db_path


def test_analysis_service_persists_versioned_outputs(tmp_path: Path, monkeypatch) -> None:
    db_path = _build_db(tmp_path)
    service = AnalysisService()

    summaries_dir = tmp_path / "data" / "analysis_outputs" / "summaries"
    prompts_dir = tmp_path / "data" / "analysis_outputs" / "prompts"
    latest_md = summaries_dir / "analysis_latest.md"
    monkeypatch.setattr("src.analysis.service.ANALYSIS_SUMMARIES_DIR", summaries_dir)
    monkeypatch.setattr("src.analysis.service.ANALYSIS_PROMPTS_DIR", prompts_dir)
    monkeypatch.setattr("src.analysis.service.DEFAULT_ANALYSIS_MARKDOWN", latest_md)

    request = AnalysisRequest(
        db_path=db_path,
        session={"session_id": "7001", "date": "2026-03-10", "committee": "Rat"},
        scope="session",
        selected_tops=[],
        prompt="Bitte zentrale Entscheidungen und Kosten nennen.",
    )
    record = service.run_journalistic_analysis(request)

    assert record.schema_version == ANALYSIS_OUTPUT_SCHEMA_VERSION
    assert record.job_id >= 1
    assert record.document_count == 1
    assert "Quellen im Scope" in record.markdown
    assert "lokale Quelle" in record.markdown

    json_output = summaries_dir / f"job_{record.job_id}.json"
    md_output = summaries_dir / f"job_{record.job_id}.md"
    prompt_output = prompts_dir / f"job_{record.job_id}.txt"

    assert json_output.exists()
    assert md_output.exists()
    assert prompt_output.exists()
    assert latest_md.exists()

    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == ANALYSIS_OUTPUT_SCHEMA_VERSION
    assert payload["job_id"] == record.job_id
