from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import uuid
from pathlib import Path
from types import FunctionType

import pytest


ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"
if str(WEB_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_ROOT))

from analysis import services as analysis_services
from core import services as core_services
from data_tools import services as data_services


@pytest.fixture()
def workspace_tmp() -> Path:
    tmp = ROOT / "tests" / "_runtime_tmp" / uuid.uuid4().hex
    tmp.mkdir(parents=True)
    try:
        yield tmp
    finally:
        if tmp.is_relative_to(ROOT / "tests" / "_runtime_tmp"):
            shutil.rmtree(tmp, ignore_errors=True)


def test_analysis_services_return_empty_lists_without_data(workspace_tmp: Path, monkeypatch) -> None:
    tmp_path = workspace_tmp
    monkeypatch.setattr(analysis_services, "LOCAL_INDEX_DB", tmp_path / "missing.sqlite")
    monkeypatch.setattr(analysis_services, "ANALYSIS_WORKFLOW_DB", tmp_path / "missing_workflow.sqlite")
    monkeypatch.setattr(analysis_services, "ANALYSIS_OUTPUTS_DIR", tmp_path / "missing_outputs")

    assert analysis_services.list_sessions() == []
    assert analysis_services.get_session("7123") is None
    assert analysis_services.list_analysis_outputs() == []
    assert analysis_services.get_analysis_output("1") is None


def test_service_facades_keep_domain_exports_separate() -> None:
    core_functions = {
        name
        for name, value in vars(core_services).items()
        if isinstance(value, FunctionType) and value.__module__ == core_services.__name__ and not name.startswith("_")
    }

    assert core_functions == {"service_status", "source_overview"}
    assert hasattr(analysis_services, "run_analysis_from_form")
    assert hasattr(analysis_services, "list_analysis_outputs")
    assert hasattr(data_services, "build_service_command")
    assert not hasattr(core_services, "run_analysis_from_form")
    assert not hasattr(core_services, "build_service_command")
    assert not hasattr(core_services, "list_analysis_outputs")


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

    monkeypatch.setattr(analysis_services, "LOCAL_INDEX_DB", tmp_path / "missing.sqlite")
    monkeypatch.setattr(analysis_services, "ANALYSIS_WORKFLOW_DB", tmp_path / "missing_workflow.sqlite")
    monkeypatch.setattr(analysis_services, "ANALYSIS_OUTPUTS_DIR", outputs)

    job = analysis_services.get_analysis_output("4")

    assert job is not None
    assert job["output_type"] == "legacy_analysis_output"
    assert job["ki_response"] == "Antwort"
    assert job["markdown"] == "# Analyse"


def test_session_detail_reads_agenda_and_documents(workspace_tmp: Path, monkeypatch) -> None:
    tmp_path = workspace_tmp
    db_path = tmp_path / "local_index.sqlite"
    session_dir = tmp_path / "data" / "raw" / "2026" / "03" / "2026-03-11_Rat_7123"
    document_dir = session_dir / "agenda" / "oe7"
    document_dir.mkdir(parents=True)
    (document_dir / "vorlage.txt").write_text("Beschlussvorschlag", encoding="utf-8")
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
            ("7123", "2026-03-11", "Rat", "Ratssitzung", "18:00", "Rathaus", "", str(session_dir)),
        )
        conn.execute(
            "INSERT INTO agenda_items VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (1, "7123", "Oe 7", "Windkraft", "", "oeffentlich", "", 1),
        )
        conn.execute(
            "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (1, "7123", "Vorlage", "", "Beschlussvorlage", "Oe 7", "", "agenda/oe7/vorlage.txt", "text/plain", 12),
        )

    monkeypatch.setattr(analysis_services, "LOCAL_INDEX_DB", db_path)

    session = analysis_services.get_session("7123")

    assert session is not None
    assert session["meeting_name"] == "Ratssitzung"
    assert session["display_date"] == "11.03.2026"
    assert session["agenda_items"][0]["documents"][0]["title"] == "Vorlage"
    assert session["agenda_items"][0]["has_analysis_documents"] is True
    assert session["agenda_items"][0]["analysis_document_count"] == 1


def test_run_analysis_from_form_validates_missing_session(monkeypatch, workspace_tmp: Path) -> None:
    monkeypatch.setattr(analysis_services, "LOCAL_INDEX_DB", workspace_tmp / "missing.sqlite")

    result, errors = analysis_services.run_analysis_from_form(
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


def test_run_analysis_from_form_rejects_top_without_analysis_documents(monkeypatch, workspace_tmp: Path) -> None:
    db_path = workspace_tmp / "local_index.sqlite"
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
            ("7123", "2026-03-11", "Rat", "Ratssitzung", "18:00", "Rathaus", "", str(workspace_tmp / "missing")),
        )
        conn.execute(
            "INSERT INTO agenda_items VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (1, "7123", "Oe 7", "Windkraft", "", "öffentlich", "", 0),
        )

    monkeypatch.setattr(analysis_services, "LOCAL_INDEX_DB", db_path)

    result, errors = analysis_services.run_analysis_from_form(
        {
            "session_id": "7123",
            "scope": "tops",
            "top_numbers": ["Oe 7"],
            "prompt_text": "Analysiere den TOP.",
            "provider_id": "none",
            "purpose": "content_analysis",
        }
    )

    assert result is None
    assert any("lokal vorhandenen Dokumenten" in error for error in errors)


def test_save_prompt_template_from_form_persists_template(monkeypatch, workspace_tmp: Path) -> None:
    template_path = workspace_tmp / "prompt_templates.json"
    monkeypatch.setattr(analysis_services, "PROMPT_TEMPLATES_PATH", template_path)

    template, errors = analysis_services.save_prompt_template_from_form(
        {
            "template_label": "Meine TOP Vorlage",
            "prompt_text": "Bitte mit Beschlusskontext analysieren.",
            "scope": "tops",
            "purpose": "content_analysis",
        }
    )

    assert errors == []
    assert template is not None
    loaded = analysis_services.list_prompt_templates("tops")
    assert any(item["label"] == "Meine TOP Vorlage" for item in loaded)


def test_service_action_builds_local_index_command() -> None:
    command, errors = data_services.build_service_command(
        "build_local_index",
        {"refresh_existing": "1"},
    )

    assert errors == []
    assert command is not None
    assert command[1:] == ["scripts/build_local_index.py", "--refresh-existing"]


def test_service_action_validates_months() -> None:
    command, errors = data_services.build_service_command(
        "fetch_sessions",
        {"year": "2026", "months": "13"},
    )

    assert command is None
    assert errors
