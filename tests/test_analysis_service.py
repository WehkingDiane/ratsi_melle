from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

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
        conn.execute(
            "INSERT INTO documents (session_id, agenda_item, title, document_type, local_path, url, content_type) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "7001",
                "Oe 2",
                "Kontakt Max Mustermann max@example.org",
                "hinweis",
                "agenda/o1/vorlage.txt",
                "https://example.org/kontakt",
                "text/plain",
            ),
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
        mode="summary",
        parameters={"temperature": 0.0},
    )
    record = service.run_analysis(request)

    assert record.schema_version == ANALYSIS_OUTPUT_SCHEMA_VERSION
    assert record.job_id >= 1
    assert record.document_count == 2
    assert record.mode == "summary"
    assert record.parameters["temperature"] == 0.0
    assert record.sensitive_data_masked is True
    assert record.document_hashes
    assert record.sources
    assert record.draft_status == "draft"
    assert record.hallucination_risk in {"low", "medium", "high"}
    assert "run_at" in record.audit_trail
    assert "Dokumentkontext" in record.markdown
    assert "max@example.org" not in record.markdown
    assert "[EMAIL_MASKED]" in record.markdown

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
    assert payload["mode"] == "summary"
    assert payload["sensitive_data_masked"] is True


def test_analysis_service_review_job_updates_status(tmp_path: Path) -> None:
    db_path = _build_db(tmp_path)
    service = AnalysisService()

    request = AnalysisRequest(
        db_path=db_path,
        session={"session_id": "7001", "date": "2026-03-10", "committee": "Rat"},
        scope="session",
        selected_tops=[],
        prompt="Kurzfassen.",
    )
    record = service.run_analysis(request)
    service.review_job(
        db_path,
        job_id=record.job_id,
        reviewer="qa@example.org",
        status="approved",
        notes="Faktenlage plausibel.",
    )

    with sqlite3.connect(db_path) as conn:
        draft_status = conn.execute("SELECT draft_status FROM analysis_jobs WHERE id = ?", (record.job_id,)).fetchone()
        review_row = conn.execute(
            "SELECT reviewer, status, notes FROM analysis_reviews WHERE job_id = ? ORDER BY id DESC LIMIT 1",
            (record.job_id,),
        ).fetchone()

    assert draft_status is not None and draft_status[0] == "approved"
    assert review_row is not None
    assert review_row[0] == "qa@example.org"
    assert review_row[1] == "approved"


def test_analysis_service_rejects_unknown_mode(tmp_path: Path) -> None:
    db_path = _build_db(tmp_path)
    service = AnalysisService()
    request = AnalysisRequest(
        db_path=db_path,
        session={"session_id": "7001", "date": "2026-03-10", "committee": "Rat"},
        scope="session",
        selected_tops=[],
        prompt="Kurzfassen.",
        mode="unknown_mode",
    )
    with pytest.raises(ValueError):
        service.run_analysis(request)
