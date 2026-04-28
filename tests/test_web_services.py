from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import uuid
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"
if str(WEB_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_ROOT))

from core import services


@pytest.fixture()
def workspace_tmp() -> Path:
    tmp = ROOT / "tests" / "_runtime_tmp" / uuid.uuid4().hex
    tmp.mkdir(parents=True)
    try:
        yield tmp
    finally:
        if tmp.is_relative_to(ROOT / "tests" / "_runtime_tmp"):
            shutil.rmtree(tmp, ignore_errors=True)


def test_services_return_empty_lists_without_data(workspace_tmp: Path, monkeypatch) -> None:
    tmp_path = workspace_tmp
    monkeypatch.setattr(services, "LOCAL_INDEX_DB", tmp_path / "missing.sqlite")
    monkeypatch.setattr(services, "ANALYSIS_WORKFLOW_DB", tmp_path / "missing_workflow.sqlite")
    monkeypatch.setattr(services, "ANALYSIS_OUTPUTS_DIR", tmp_path / "missing_outputs")

    assert services.list_sessions() == []
    assert services.get_session("7123") is None
    assert services.list_analysis_outputs() == []
    assert services.get_analysis_output("1") is None


def test_legacy_analysis_output_file_is_displayed(workspace_tmp: Path, monkeypatch) -> None:
    tmp_path = workspace_tmp
    outputs = tmp_path / "analysis_outputs"
    outputs.mkdir()
    (outputs / "job_4.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "job_id": 4,
                "session_id": "7123",
                "ki_response": "Antwort",
                "markdown": "# Analyse",
                "prompt_text": "Bitte analysieren",
                "status": "done",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(services, "LOCAL_INDEX_DB", tmp_path / "missing.sqlite")
    monkeypatch.setattr(services, "ANALYSIS_WORKFLOW_DB", tmp_path / "missing_workflow.sqlite")
    monkeypatch.setattr(services, "ANALYSIS_OUTPUTS_DIR", outputs)

    job = services.get_analysis_output("4")

    assert job is not None
    assert job["output_type"] == "legacy_analysis_output"
    assert job["ki_response"] == "Antwort"
    assert job["markdown"] == "# Analyse"


def test_session_detail_reads_agenda_and_documents(workspace_tmp: Path, monkeypatch) -> None:
    tmp_path = workspace_tmp
    db_path = tmp_path / "local_index.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE sessions (
                session_id TEXT PRIMARY KEY,
                date TEXT,
                committee TEXT,
                meeting_name TEXT,
                start_time TEXT,
                location TEXT,
                detail_url TEXT,
                session_path TEXT
            );
            CREATE TABLE agenda_items (
                id INTEGER PRIMARY KEY,
                session_id TEXT,
                number TEXT,
                title TEXT,
                reporter TEXT,
                status TEXT,
                decision TEXT,
                documents_present INTEGER
            );
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY,
                session_id TEXT,
                title TEXT,
                category TEXT,
                document_type TEXT,
                agenda_item TEXT,
                url TEXT,
                local_path TEXT,
                content_type TEXT,
                content_length INTEGER
            );
            """
        )
        conn.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("7123", "2026-03-11", "Rat", "Ratssitzung", "18:00", "Rathaus", "", ""),
        )
        conn.execute(
            "INSERT INTO agenda_items VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (1, "7123", "Oe 7", "Windkraft", "", "oeffentlich", "", 1),
        )
        conn.execute(
            "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (1, "7123", "Vorlage", "", "Beschlussvorlage", "Oe 7", "", "", "pdf", 12),
        )

    monkeypatch.setattr(services, "LOCAL_INDEX_DB", db_path)

    session = services.get_session("7123")

    assert session is not None
    assert session["meeting_name"] == "Ratssitzung"
    assert session["agenda_items"][0]["documents"][0]["title"] == "Vorlage"


def test_run_analysis_from_form_validates_missing_session(monkeypatch, workspace_tmp: Path) -> None:
    monkeypatch.setattr(services, "LOCAL_INDEX_DB", workspace_tmp / "missing.sqlite")

    result, errors = services.run_analysis_from_form(
        {
            "session_id": "",
            "scope": "session",
            "top_numbers": [],
            "prompt_text": "Analysiere die Sitzung.",
            "provider_id": "none",
            "purpose": "content_analysis",
        }
    )

    assert result is None
    assert errors
