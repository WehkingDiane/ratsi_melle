from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import time
import uuid
from pathlib import Path
from types import FunctionType

import pytest


ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"
if str(WEB_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_ROOT))

from analysis import services as analysis_services
from core import service_jobs
from core import services as core_services
from data_tools import services as data_services
from src.analysis.workflow_db import AnalysisArtifactRecord
from src.analysis.workflow_db import AnalysisJobRecord
from src.analysis.workflow_db import add_analysis_output
from src.analysis.workflow_db import create_analysis_job


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


def test_workflow_analysis_output_schema_is_displayed(workspace_tmp: Path, monkeypatch) -> None:
    output_dir = workspace_tmp / "data" / "analysis_outputs" / "2026" / "03" / "session"
    output_dir.mkdir(parents=True)
    json_path = output_dir / "job_1.raw.json"
    markdown_path = output_dir / "job_1.md"
    json_path.write_text(
        json.dumps(
            {
                "schema_version": "2.0",
                "output_type": "raw_analysis",
                "job_id": 1,
                "session_id": "7123",
                "scope": "session",
                "purpose": "content_analysis",
                "status": "done",
            }
        ),
        encoding="utf-8",
    )
    markdown_path.write_text("# Workflow-Analyse", encoding="utf-8")
    workflow_db = workspace_tmp / "data" / "db" / "analysis_workflow.sqlite"
    create_analysis_job(
        AnalysisJobRecord(
            session_id="old",
            scope="session",
            purpose="content_analysis",
            model_name="none",
            prompt_version="web",
            status="done",
        ),
        workflow_db,
    )
    job_id = create_analysis_job(
        AnalysisJobRecord(
            session_id="7123",
            scope="session",
            purpose="content_analysis",
            model_name="none",
            prompt_version="web",
            status="done",
        ),
        workflow_db,
    )
    add_analysis_output(
        AnalysisArtifactRecord(
            job_id=job_id,
            output_type="raw_analysis",
            schema_version="2.0",
            json_path="data/analysis_outputs/2026/03/session/job_1.raw.json",
            markdown_path="data/analysis_outputs/2026/03/session/job_1.md",
            status="done",
        ),
        workflow_db,
    )
    monkeypatch.setattr(analysis_services, "REPO_ROOT", workspace_tmp)
    monkeypatch.setattr(analysis_services, "LOCAL_INDEX_DB", workspace_tmp / "missing.sqlite")
    monkeypatch.setattr(analysis_services, "ANALYSIS_WORKFLOW_DB", workflow_db)
    monkeypatch.setattr(analysis_services, "ANALYSIS_OUTPUTS_DIR", workspace_tmp / "missing_outputs")

    job = analysis_services.get_analysis_output(f"workflow:{job_id}")

    assert job is not None
    assert job_id != 1
    assert job["job_id"] == f"workflow:{job_id}"
    assert job["db_job_id"] == job_id
    assert job["session_id"] == "7123"
    assert job["output_type"] == "raw_analysis"
    assert job["schema_version"] == "2.0"
    assert job["markdown"] == "# Workflow-Analyse"
    assert "data/analysis_outputs/2026/03/session/job_1.raw.json" in job["files"]


def test_db_analysis_outputs_are_namespaced_by_source(workspace_tmp: Path, monkeypatch) -> None:
    workflow_db = workspace_tmp / "data" / "db" / "analysis_workflow.sqlite"
    workflow_job_id = create_analysis_job(
        AnalysisJobRecord(
            session_id="workflow-session",
            scope="session",
            purpose="content_analysis",
            model_name="none",
            prompt_version="web",
            status="done",
        ),
        workflow_db,
    )
    local_db = workspace_tmp / "data" / "db" / "local_index.sqlite"
    local_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(local_db) as conn:
        conn.executescript(
            """
            CREATE TABLE analysis_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                session_id TEXT NOT NULL,
                scope TEXT NOT NULL,
                top_numbers_json TEXT,
                purpose TEXT NOT NULL DEFAULT 'content_analysis',
                model_name TEXT,
                prompt_version TEXT,
                status TEXT NOT NULL,
                error_message TEXT
            );
            CREATE TABLE analysis_outputs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                output_format TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            "INSERT INTO analysis_jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                1,
                "2026-04-29T20:00:00Z",
                "local-session",
                "session",
                "[]",
                "content_analysis",
                "none",
                "web",
                "done",
                None,
            ),
        )
        conn.execute(
            "INSERT INTO analysis_outputs (job_id, output_format, content, created_at) VALUES (?, ?, ?, ?)",
            (1, "markdown", "# Lokale Analyse", "2026-04-29T20:00:00Z"),
        )
    assert workflow_job_id == 1
    monkeypatch.setattr(analysis_services, "REPO_ROOT", workspace_tmp)
    monkeypatch.setattr(analysis_services, "LOCAL_INDEX_DB", local_db)
    monkeypatch.setattr(analysis_services, "ANALYSIS_WORKFLOW_DB", workflow_db)
    monkeypatch.setattr(analysis_services, "ANALYSIS_OUTPUTS_DIR", workspace_tmp / "missing_outputs")

    jobs = {str(job["job_id"]): job for job in analysis_services.list_analysis_outputs()}

    assert {"workflow:1", "local:1"} <= set(jobs)
    assert jobs["workflow:1"]["session_id"] == "workflow-session"
    assert jobs["local:1"]["session_id"] == "local-session"
    assert jobs["local:1"]["markdown"] == "# Lokale Analyse"
    assert analysis_services.get_analysis_output("workflow:1")["session_id"] == "workflow-session"
    assert analysis_services.get_analysis_output("local:1")["session_id"] == "local-session"
    assert analysis_services.get_analysis_output("1") is None


def test_file_analysis_outputs_merge_into_unique_db_job(workspace_tmp: Path, monkeypatch) -> None:
    local_db = workspace_tmp / "data" / "db" / "local_index.sqlite"
    output_dir = workspace_tmp / "data" / "analysis_outputs"
    local_db.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True)
    with sqlite3.connect(local_db) as conn:
        conn.executescript(
            """
            CREATE TABLE analysis_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                session_id TEXT NOT NULL,
                scope TEXT NOT NULL,
                top_numbers_json TEXT,
                purpose TEXT NOT NULL DEFAULT 'content_analysis',
                model_name TEXT,
                prompt_version TEXT,
                status TEXT NOT NULL,
                error_message TEXT
            );
            CREATE TABLE analysis_outputs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                output_format TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            "INSERT INTO analysis_jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                1,
                "2026-04-29T20:00:00Z",
                "local-session",
                "session",
                "[]",
                "content_analysis",
                "none",
                "web",
                "done",
                None,
            ),
        )
    (output_dir / "job_1.json").write_text(
        json.dumps(
            {
                "schema_version": "2.0",
                "output_type": "raw_analysis",
                "job_id": 1,
                "ki_response": "Datei-Antwort",
                "status": "done",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(analysis_services, "REPO_ROOT", workspace_tmp)
    monkeypatch.setattr(analysis_services, "LOCAL_INDEX_DB", local_db)
    monkeypatch.setattr(analysis_services, "ANALYSIS_WORKFLOW_DB", workspace_tmp / "missing_workflow.sqlite")
    monkeypatch.setattr(analysis_services, "ANALYSIS_OUTPUTS_DIR", output_dir)

    jobs = {str(job["job_id"]): job for job in analysis_services.list_analysis_outputs()}

    assert "local:1" in jobs
    assert "1" not in jobs
    assert jobs["local:1"]["db_job_id"] == 1
    assert jobs["local:1"]["ki_response"] == "Datei-Antwort"
    assert jobs["local:1"]["output_type"] == "raw_analysis"
    assert "data/analysis_outputs/job_1.json" in jobs["local:1"]["files"]


def test_file_analysis_outputs_prefer_workflow_job_when_db_ids_collide(
    workspace_tmp: Path, monkeypatch
) -> None:
    workflow_db = workspace_tmp / "data" / "db" / "analysis_workflow.sqlite"
    workflow_job_id = create_analysis_job(
        AnalysisJobRecord(
            session_id="workflow-session",
            scope="session",
            purpose="content_analysis",
            model_name="none",
            prompt_version="web",
            status="done",
        ),
        workflow_db,
    )
    local_db = workspace_tmp / "data" / "db" / "local_index.sqlite"
    output_dir = workspace_tmp / "data" / "analysis_outputs"
    local_db.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True)
    with sqlite3.connect(local_db) as conn:
        conn.executescript(
            """
            CREATE TABLE analysis_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                session_id TEXT NOT NULL,
                scope TEXT NOT NULL,
                top_numbers_json TEXT,
                purpose TEXT NOT NULL DEFAULT 'content_analysis',
                model_name TEXT,
                prompt_version TEXT,
                status TEXT NOT NULL,
                error_message TEXT
            );
            CREATE TABLE analysis_outputs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                output_format TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            "INSERT INTO analysis_jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                1,
                "2026-04-29T20:00:00Z",
                "local-session",
                "session",
                "[]",
                "content_analysis",
                "none",
                "web",
                "done",
                None,
            ),
        )
    assert workflow_job_id == 1
    (output_dir / "job_1.json").write_text(
        json.dumps(
            {
                "schema_version": "2.0",
                "output_type": "raw_analysis",
                "job_id": 1,
                "ki_response": "Workflow-Datei",
                "status": "done",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(analysis_services, "REPO_ROOT", workspace_tmp)
    monkeypatch.setattr(analysis_services, "LOCAL_INDEX_DB", local_db)
    monkeypatch.setattr(analysis_services, "ANALYSIS_WORKFLOW_DB", workflow_db)
    monkeypatch.setattr(analysis_services, "ANALYSIS_OUTPUTS_DIR", output_dir)

    jobs = {str(job["job_id"]): job for job in analysis_services.list_analysis_outputs()}

    assert {"workflow:1", "local:1"} <= set(jobs)
    assert "1" not in jobs
    assert jobs["workflow:1"]["ki_response"] == "Workflow-Datei"
    assert jobs["local:1"]["ki_response"] == ""


def test_legacy_db_analysis_outputs_are_read_in_id_order(workspace_tmp: Path, monkeypatch) -> None:
    local_db = workspace_tmp / "data" / "db" / "local_index.sqlite"
    local_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(local_db) as conn:
        conn.executescript(
            """
            CREATE TABLE analysis_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                session_id TEXT NOT NULL,
                scope TEXT NOT NULL,
                top_numbers_json TEXT,
                purpose TEXT NOT NULL DEFAULT 'content_analysis',
                model_name TEXT,
                prompt_version TEXT,
                status TEXT NOT NULL,
                error_message TEXT
            );
            CREATE TABLE analysis_outputs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                output_format TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            "INSERT INTO analysis_jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                1,
                "2026-04-29T20:00:00Z",
                "local-session",
                "session",
                "[]",
                "content_analysis",
                "none",
                "web",
                "done",
                None,
            ),
        )
        conn.execute(
            "INSERT INTO analysis_outputs VALUES (?, ?, ?, ?, ?)",
            (2, 1, "markdown", "# Zweiter Output", "2026-04-29T20:01:00Z"),
        )
        conn.execute(
            "INSERT INTO analysis_outputs VALUES (?, ?, ?, ?, ?)",
            (1, 1, "markdown", "# Erster Output", "2026-04-29T20:00:00Z"),
        )
    monkeypatch.setattr(analysis_services, "REPO_ROOT", workspace_tmp)
    monkeypatch.setattr(analysis_services, "LOCAL_INDEX_DB", local_db)
    monkeypatch.setattr(analysis_services, "ANALYSIS_WORKFLOW_DB", workspace_tmp / "missing_workflow.sqlite")
    monkeypatch.setattr(analysis_services, "ANALYSIS_OUTPUTS_DIR", workspace_tmp / "missing_outputs")

    job = analysis_services.get_analysis_output("local:1")

    assert job is not None
    assert job["markdown"] == "# Erster Output"


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


def test_service_job_launch_failure_is_marked_error(monkeypatch, workspace_tmp: Path) -> None:
    def fail_popen(*_args, **_kwargs):
        raise OSError("missing executable")

    monkeypatch.setattr(service_jobs.subprocess, "Popen", fail_popen)

    job = service_jobs.start_service_job("build_local_index", ["missing-command"], workspace_tmp)

    for _ in range(50):
        current = service_jobs.get_service_job(job.job_id)
        if current and current.status == "error":
            break
        time.sleep(0.01)

    current = service_jobs.get_service_job(job.job_id)

    assert current is not None
    assert current.status == "error"
    assert current.to_dict()["running"] is False
    assert "Service konnte nicht gestartet werden" in current.summary
    assert "missing executable" in current.output


def test_service_job_output_keeps_only_bounded_tail(monkeypatch, workspace_tmp: Path) -> None:
    class FakeProcess:
        stdout = (f"line-{index}\n" for index in range(600))
        returncode = 0

        def wait(self) -> None:
            return None

    monkeypatch.setattr(service_jobs.subprocess, "Popen", lambda *_args, **_kwargs: FakeProcess())

    job = service_jobs.start_service_job("build_local_index", ["fake-command"], workspace_tmp)

    for _ in range(50):
        current = service_jobs.get_service_job(job.job_id)
        if current and current.status == "ok":
            break
        time.sleep(0.01)

    current = service_jobs.get_service_job(job.job_id)

    assert current is not None
    lines = current.output.splitlines()
    assert current.status == "ok"
    assert len(lines) == 500
    assert lines[0] == "line-100"
    assert lines[-1] == "line-599"
