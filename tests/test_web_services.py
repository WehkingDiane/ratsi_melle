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
from search import services as search_services
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


def test_search_documents_finds_document_metadata(workspace_tmp: Path, monkeypatch) -> None:
    db_path = workspace_tmp / "data" / "db" / "local_index.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
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
            ("7123", "2026-03-11", "Rat", "Ratssitzung", "18:00", "Rathaus", "https://example.test/si0057.asp", ""),
        )
        conn.execute(
            "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (1, "7123", "Windkraft in Riemsloh", "BV", "beschlussvorlage", "Oe 7", "https://example.test/do.asp", "agenda/oe7.pdf", "application/pdf", 12),
        )
        conn.execute(
            "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (2, "7123", "Haushalt", "BV", "beschlussvorlage", "Oe 8", "", "agenda/oe8.pdf", "application/pdf", 12),
        )

    monkeypatch.setattr(search_services, "LOCAL_INDEX_DB", db_path)

    results = search_services.search_documents("windkraft rat")

    assert [result["title"] for result in results] == ["Windkraft in Riemsloh"]
    assert results[0]["display_date"] == "11.03.2026"
    assert results[0]["detail_url"] == "https://example.test/si0057.asp"


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


def test_service_status_summarizes_content_counts(workspace_tmp: Path, monkeypatch) -> None:
    from core.services import status as status_service

    raw_session_dir = workspace_tmp / "data" / "raw" / "2026" / "03" / "2026-03-11_Rat_7123"
    raw_session_dir.mkdir(parents=True)
    (raw_session_dir / "agenda").mkdir()
    legacy_raw_session_dir = workspace_tmp / "data" / "raw" / "2025" / "2025-12-08_Ortsrat_6694"
    legacy_raw_session_dir.mkdir(parents=True)
    (legacy_raw_session_dir / "agenda").mkdir()
    (legacy_raw_session_dir / "session-documents").mkdir()
    partial_raw_session_dir = workspace_tmp / "data" / "raw" / "2026" / "03" / "2026-03-12_Rat_7124"
    partial_raw_session_dir.mkdir(parents=True)
    (partial_raw_session_dir / "session_detail.html").write_text("<html></html>", encoding="utf-8")
    summary_only_session_dir = workspace_tmp / "data" / "raw" / "2025" / "2025-12-09_Rat_6695"
    summary_only_session_dir.mkdir(parents=True)
    (summary_only_session_dir / "agenda_summary.json").write_text('{"agenda_items": []}', encoding="utf-8")
    local_db = workspace_tmp / "data" / "db" / "local_index.sqlite"
    local_db.parent.mkdir(parents=True)
    online_db = workspace_tmp / "data" / "db" / "online_session_index.sqlite"
    qdrant_dir = workspace_tmp / "data" / "db" / "qdrant"
    qdrant_dir.mkdir()
    with sqlite3.connect(local_db) as conn:
        conn.executescript(
            """
            CREATE TABLE sessions (session_id TEXT PRIMARY KEY);
            CREATE TABLE documents (id INTEGER PRIMARY KEY, session_id TEXT);
            INSERT INTO sessions VALUES ('7123');
            INSERT INTO documents VALUES (1, '7123');
            INSERT INTO documents VALUES (2, '7123');
            """
        )
    with sqlite3.connect(online_db) as conn:
        conn.executescript(
            """
            CREATE TABLE sessions (session_id TEXT PRIMARY KEY);
            INSERT INTO sessions VALUES ('7123');
            INSERT INTO sessions VALUES ('7124');
            """
        )

    monkeypatch.setattr(status_service.paths, "REPO_ROOT", workspace_tmp)
    monkeypatch.setattr(status_service.paths, "LOCAL_INDEX_DB", local_db)

    status = status_service.service_status()

    assert status["raw_data_summary"] == "4 Sitzungsordner"
    assert status["local_index_summary"] == "1 Sitzungen / 2 Dokumente"
    assert status["online_index_summary"] == "2 Sitzungen"
    assert status["qdrant_summary"] == "vorhanden"


def test_service_status_marks_raw_data_file_missing(workspace_tmp: Path, monkeypatch) -> None:
    from core.services import status as status_service

    raw_data_path = workspace_tmp / "data" / "raw"
    raw_data_path.parent.mkdir(parents=True)
    raw_data_path.write_text("not a directory", encoding="utf-8")
    local_db = workspace_tmp / "data" / "db" / "local_index.sqlite"
    local_db.parent.mkdir(parents=True)

    monkeypatch.setattr(status_service.paths, "REPO_ROOT", workspace_tmp)
    monkeypatch.setattr(status_service.paths, "LOCAL_INDEX_DB", local_db)

    status = status_service.service_status()

    assert status["raw_data_exists"] is False
    assert status["raw_session_count"] is None
    assert status["raw_data_summary"] == "fehlt"


def test_raw_session_directory_count_handles_unreadable_root() -> None:
    from core.services import status as status_service

    class UnreadableRoot:
        def is_dir(self) -> bool:
            return True

        def iterdir(self):
            raise PermissionError("unreadable")

    assert status_service._raw_session_directory_count(UnreadableRoot()) is None


def test_service_status_marks_unreadable_online_index_missing(workspace_tmp: Path, monkeypatch) -> None:
    from core.services import status as status_service

    local_db = workspace_tmp / "data" / "db" / "local_index.sqlite"
    local_db.parent.mkdir(parents=True)
    online_db = workspace_tmp / "data" / "db" / "online_session_index.sqlite"
    online_db.write_text("", encoding="utf-8")

    monkeypatch.setattr(status_service.paths, "REPO_ROOT", workspace_tmp)
    monkeypatch.setattr(status_service.paths, "LOCAL_INDEX_DB", local_db)

    status = status_service.service_status()

    assert status["online_index_exists"] is False
    assert status["online_index_summary"] == "fehlt"


def test_service_status_marks_unreadable_local_index_missing(workspace_tmp: Path, monkeypatch) -> None:
    from core.services import status as status_service

    local_db = workspace_tmp / "data" / "db" / "local_index.sqlite"
    local_db.parent.mkdir(parents=True)
    local_db.write_text("not sqlite", encoding="utf-8")

    monkeypatch.setattr(status_service.paths, "REPO_ROOT", workspace_tmp)
    monkeypatch.setattr(status_service.paths, "LOCAL_INDEX_DB", local_db)

    status = status_service.service_status()

    assert status["local_index_exists"] is False
    assert status["local_index_summary"] == "fehlt"


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


def test_workflow_output_paths_accept_windows_separators(workspace_tmp: Path, monkeypatch) -> None:
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
                "status": "done",
            }
        ),
        encoding="utf-8",
    )
    markdown_path.write_text("# Windows-Pfad", encoding="utf-8")
    workflow_db = workspace_tmp / "data" / "db" / "analysis_workflow.sqlite"
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
            json_path=r"data\analysis_outputs\2026\03\session\job_1.raw.json",
            markdown_path=r"data\analysis_outputs\2026\03\session\job_1.md",
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
    assert job["markdown"] == "# Windows-Pfad"
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


def test_canonical_analysis_job_id_prefers_workflow_source_job(
    workspace_tmp: Path, monkeypatch
) -> None:
    workflow_db = workspace_tmp / "data" / "db" / "analysis_workflow.sqlite"
    workflow_job_id = create_analysis_job(
        AnalysisJobRecord(
            session_id="workflow-session",
            scope="session",
            purpose="content_analysis",
            source_db=str(workspace_tmp / "data" / "db" / "local_index.sqlite"),
            source_job_id=1,
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
    monkeypatch.setattr(analysis_services, "REPO_ROOT", workspace_tmp)
    monkeypatch.setattr(analysis_services, "LOCAL_INDEX_DB", local_db)
    monkeypatch.setattr(analysis_services, "ANALYSIS_WORKFLOW_DB", workflow_db)
    monkeypatch.setattr(analysis_services, "ANALYSIS_OUTPUTS_DIR", workspace_tmp / "missing_outputs")

    assert analysis_services.canonical_analysis_job_id({"job_id": 1}) == f"workflow:{workflow_job_id}"


def test_prompt_artifact_is_loaded_from_prompt_directory(workspace_tmp: Path, monkeypatch) -> None:
    local_db = workspace_tmp / "data" / "db" / "local_index.sqlite"
    prompt_dir = workspace_tmp / "data" / "analysis_prompts"
    local_db.parent.mkdir(parents=True, exist_ok=True)
    prompt_dir.mkdir(parents=True)
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
    (prompt_dir / "job_1.txt").write_text("Prompt aus Datei\n", encoding="utf-8")
    monkeypatch.setattr(analysis_services, "REPO_ROOT", workspace_tmp)
    monkeypatch.setattr(analysis_services, "LOCAL_INDEX_DB", local_db)
    monkeypatch.setattr(analysis_services, "ANALYSIS_WORKFLOW_DB", workspace_tmp / "missing_workflow.sqlite")
    monkeypatch.setattr(analysis_services, "ANALYSIS_OUTPUTS_DIR", workspace_tmp / "missing_outputs")
    monkeypatch.setattr(analysis_services, "ANALYSIS_PROMPTS_DIR", prompt_dir)

    job = analysis_services.get_analysis_output("local:1")

    assert job is not None
    assert job["prompt_text"] == "Prompt aus Datei"
    assert "data/analysis_prompts/job_1.txt" not in job["files"]


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
    (document_dir / "anlage.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
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
        conn.execute(
            "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (2, "7123", "Anlage", "", "Anlage", "Oe 7", "", "agenda/oe7/anlage.pdf", "application/octet-stream", 18),
        )

    monkeypatch.setattr(analysis_services, "LOCAL_INDEX_DB", db_path)

    session = analysis_services.get_session("7123")

    assert session is not None
    assert session["meeting_name"] == "Ratssitzung"
    assert session["display_date"] == "11.03.2026"
    documents_by_title = {
        document["title"]: document for document in session["agenda_items"][0]["documents"]
    }
    assert documents_by_title["Vorlage"]["source_file_available"] is True
    assert documents_by_title["Anlage"]["pdf_view_available"] is True
    assert session["agenda_items"][0]["has_analysis_documents"] is True
    assert session["agenda_items"][0]["analysis_document_count"] == 2

    pdf_document = analysis_services.get_local_pdf_document("7123", 2)

    assert pdf_document is not None
    assert pdf_document["path"] == document_dir / "anlage.pdf"
    assert pdf_document["content_type"] == "application/pdf"
    assert analysis_services.get_local_pdf_document("7123", 1) is None


def test_session_display_fields_fall_back_to_humanized_committee(
    workspace_tmp: Path, monkeypatch
) -> None:
    db_path = workspace_tmp / "local_index.sqlite"
    session_path = (
        workspace_tmp
        / "data"
        / "raw"
        / "2026"
        / "02"
        / "2026-02-26-Ausschuss-für-Bildung-7121"
    )
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
            (
                "7121",
                "2026-02-26",
                "Ausschuss-für-Bildung",
                None,
                "",
                "",
                "",
                str(session_path),
            ),
        )
        conn.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "9001",
                "2026-02-27",
                "",
                None,
                "",
                "",
                "",
                str(
                    workspace_tmp
                    / "data"
                    / "raw"
                    / "2026"
                    / "02"
                    / "2026-02-27-Ortsrat-Oldendorf-9001"
                ),
            ),
        )
        conn.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "9002",
                "2026-02-28",
                "Ausschuss-für-Umwelt-Klimaschutz-Straßen-und-Tiefbau",
                "Ausschuss für Umwelt, Klimaschutz, Straßen und Tiefbau",
                "",
                "",
                "",
                "",
            ),
        )
        conn.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "9003",
                "2026-02-24",
                "",
                None,
                "",
                "",
                "",
                str(
                    workspace_tmp
                    / "data"
                    / "raw"
                    / "2026"
                    / "02"
                    / "2026-02-24_Ortsrat_Gesmold_9003"
                ),
            ),
        )

    monkeypatch.setattr(analysis_services, "LOCAL_INDEX_DB", db_path)

    sessions = {
        session["session_id"]: session for session in analysis_services.list_sessions()
    }
    detail = analysis_services.get_session("7121")

    assert sessions["7121"]["committee"] == "Ausschuss für Bildung"
    assert sessions["7121"]["meeting_name"] == "Ausschuss für Bildung"
    assert sessions["9001"]["committee"] == "Ortsrat Oldendorf"
    assert sessions["9001"]["meeting_name"] == "Ortsrat Oldendorf"
    assert sessions["9003"]["committee"] == "Ortsrat Gesmold"
    assert sessions["9003"]["meeting_name"] == "Ortsrat Gesmold"
    assert (
        sessions["9002"]["committee"]
        == "Ausschuss für Umwelt, Klimaschutz, Straßen und Tiefbau"
    )
    assert (
        sessions["9002"]["meeting_name"]
        == "Ausschuss für Umwelt, Klimaschutz, Straßen und Tiefbau"
    )
    assert detail is not None
    assert detail["committee"] == "Ausschuss für Bildung"
    assert detail["meeting_name"] == "Ausschuss für Bildung"


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


def test_run_analysis_from_form_ignores_stale_tops_for_session_scope(monkeypatch, workspace_tmp: Path) -> None:
    from core.services import analysis as core_analysis_services

    db_path = workspace_tmp / "local_index.sqlite"
    template_path = workspace_tmp / "prompt_templates.json"
    example_path = workspace_tmp / "prompt_templates.example.json"
    template_path.write_text(
        json.dumps(
            {
                "templates": [
                    {
                        "id": "session_sources",
                        "label": "Session Sources",
                        "scope": "session",
                        "description": "",
                        "prompt_text": "Quellen:\n{{source_list}}",
                        "variables": ["source_list"],
                        "is_active": True,
                        "visibility": "private",
                        "revision": 1,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    example_path.write_text('{"templates": []}\n', encoding="utf-8")
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
            ("7123", "2026-03-11", "Rat", "Ratssitzung", "18:00", "Rathaus", "", str(workspace_tmp)),
        )
        conn.execute(
            "INSERT INTO agenda_items VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (1, "7123", "Oe 7", "Windkraft", "", "oeffentlich", "", 1),
        )
        conn.execute(
            "INSERT INTO agenda_items VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (2, "7123", "Oe 8", "Haushalt", "", "oeffentlich", "", 1),
        )

    captured = {}

    class _Record:
        def to_dict(self) -> dict[str, int]:
            return {"job_id": 1}

    class _AnalysisService:
        def run_journalistic_analysis(self, request):
            captured["request"] = request
            return _Record()

    monkeypatch.setattr(analysis_services, "LOCAL_INDEX_DB", db_path)
    monkeypatch.setattr(analysis_services, "PROMPT_TEMPLATES_PATH", template_path)
    monkeypatch.setattr(analysis_services, "PROMPT_TEMPLATES_EXAMPLE", example_path)
    monkeypatch.setattr(core_analysis_services, "AnalysisService", _AnalysisService)

    result, errors = analysis_services.run_analysis_from_form(
        {
            "session_id": "7123",
            "scope": "session",
            "top_numbers": ["Oe 7"],
            "template_id": "session_sources",
            "provider_id": "none",
            "purpose": "content_analysis",
        }
    )

    request = captured["request"]
    assert errors == []
    assert result == {"job_id": 1}
    assert request.selected_tops == []
    assert "- Oe 7 Windkraft" in request.prompt
    assert "- Oe 8 Haushalt" in request.prompt


def test_save_prompt_template_from_form_persists_template(monkeypatch, workspace_tmp: Path) -> None:
    template_path = workspace_tmp / "prompt_templates.json"
    example_path = workspace_tmp / "prompt_templates.example.json"
    example_path.write_text('{"templates": []}\n', encoding="utf-8")
    monkeypatch.setattr(analysis_services, "PROMPT_TEMPLATES_PATH", template_path)
    monkeypatch.setattr(analysis_services, "PROMPT_TEMPLATES_EXAMPLE", example_path)

    template, errors = analysis_services.save_prompt_template_from_form(
        {
            "id": "meine_top_vorlage",
            "label": "Meine TOP Vorlage",
            "prompt_text": "Bitte mit Beschlusskontext analysieren.",
            "scope": "tops",
            "description": "Test",
            "variables": "agenda_item",
            "visibility": "private",
            "is_active": "1",
        }
    )

    assert errors == []
    assert template is not None
    loaded = analysis_services.list_prompt_templates("tops")
    assert any(item["label"] == "Meine TOP Vorlage" for item in loaded)


def test_list_prompt_templates_returns_empty_list_for_invalid_store(monkeypatch, workspace_tmp: Path) -> None:
    template_path = workspace_tmp / "prompt_templates.json"
    template_path.write_text("{not json", encoding="utf-8")
    example_path = workspace_tmp / "prompt_templates.example.json"
    example_path.write_text('{"templates": []}\n', encoding="utf-8")
    monkeypatch.setattr(analysis_services, "PROMPT_TEMPLATES_PATH", template_path)
    monkeypatch.setattr(analysis_services, "PROMPT_TEMPLATES_EXAMPLE", example_path)

    assert analysis_services.list_prompt_templates("session") == []


def test_list_prompt_templates_handles_invalid_revision(monkeypatch, workspace_tmp: Path) -> None:
    template_path = workspace_tmp / "prompt_templates.json"
    template_path.write_text(
        json.dumps(
            {
                "templates": [
                    {
                        "id": "bad_revision",
                        "label": "Bad Revision",
                        "scope": "session",
                        "description": "",
                        "prompt_text": "Analysiere {{session_title}}.",
                        "variables": ["session_title"],
                        "is_active": True,
                        "visibility": "private",
                        "revision": "v2",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    example_path = workspace_tmp / "prompt_templates.example.json"
    example_path.write_text('{"templates": []}\n', encoding="utf-8")
    monkeypatch.setattr(analysis_services, "PROMPT_TEMPLATES_PATH", template_path)
    monkeypatch.setattr(analysis_services, "PROMPT_TEMPLATES_EXAMPLE", example_path)

    templates = analysis_services.list_prompt_templates("session")

    assert len(templates) == 1
    assert templates[0]["id"] == "bad_revision"
    assert templates[0]["revision"] == 1


def test_save_prompt_template_from_form_returns_errors_for_invalid_store(monkeypatch, workspace_tmp: Path) -> None:
    template_path = workspace_tmp / "prompt_templates.json"
    template_path.write_text("{not json", encoding="utf-8")
    example_path = workspace_tmp / "prompt_templates.example.json"
    example_path.write_text('{"templates": []}\n', encoding="utf-8")
    monkeypatch.setattr(analysis_services, "PROMPT_TEMPLATES_PATH", template_path)
    monkeypatch.setattr(analysis_services, "PROMPT_TEMPLATES_EXAMPLE", example_path)

    template, errors = analysis_services.save_prompt_template_from_form(
        {
            "label": "Kaputte Vorlage",
            "prompt_text": "Analysiere {{session_title}}.",
            "scope": "session",
            "visibility": "private",
            "is_active": "1",
        }
    )

    assert template is None
    assert errors == ["Prompt-Vorlagen konnten nicht gelesen werden. Bitte private Vorlagen-Datei prüfen."]
    assert "Analysiere" not in errors[0]


def test_get_prompt_template_returns_none_for_invalid_store(monkeypatch, workspace_tmp: Path) -> None:
    template_path = workspace_tmp / "prompt_templates.json"
    template_path.write_text("{not json", encoding="utf-8")
    example_path = workspace_tmp / "prompt_templates.example.json"
    example_path.write_text('{"templates": []}\n', encoding="utf-8")
    monkeypatch.setattr(analysis_services, "PROMPT_TEMPLATES_PATH", template_path)
    monkeypatch.setattr(analysis_services, "PROMPT_TEMPLATES_EXAMPLE", example_path)

    assert analysis_services.get_prompt_template("kaputt") is None


def test_prompt_template_actions_return_errors_for_invalid_store(monkeypatch, workspace_tmp: Path) -> None:
    from core.services.prompts import deactivate_prompt_template
    from core.services.prompts import duplicate_prompt_template
    from core.services.prompts import get_active_prompt_template
    from core.services import paths

    template_path = workspace_tmp / "prompt_templates.json"
    template_path.write_text("{not json", encoding="utf-8")
    example_path = workspace_tmp / "prompt_templates.example.json"
    example_path.write_text('{"templates": []}\n', encoding="utf-8")
    monkeypatch.setattr(paths, "PROMPT_TEMPLATES_PATH", template_path)
    monkeypatch.setattr(paths, "PROMPT_TEMPLATES_EXAMPLE", example_path)

    _template, active_errors = get_active_prompt_template("kaputt", "session")
    _duplicate, duplicate_errors = duplicate_prompt_template("kaputt")
    deactivate_errors = deactivate_prompt_template("kaputt")

    assert active_errors == ["Prompt-Vorlagen konnten nicht gelesen werden. Bitte private Vorlagen-Datei prüfen."]
    assert duplicate_errors == ["Prompt-Vorlagen konnten nicht gelesen werden. Bitte private Vorlagen-Datei prüfen."]
    assert deactivate_errors == ["Prompt-Vorlagen konnten nicht gelesen werden. Bitte private Vorlagen-Datei prüfen."]


def test_prompt_template_slugify_handles_german_umlauts(monkeypatch, workspace_tmp: Path) -> None:
    template_path = workspace_tmp / "prompt_templates.json"
    example_path = workspace_tmp / "prompt_templates.example.json"
    example_path.write_text('{"templates": []}\n', encoding="utf-8")
    monkeypatch.setattr(analysis_services, "PROMPT_TEMPLATES_PATH", template_path)
    monkeypatch.setattr(analysis_services, "PROMPT_TEMPLATES_EXAMPLE", example_path)

    template, errors = analysis_services.save_prompt_template_from_form(
        {
            "label": "Meine öffentliche Vorlage",
            "prompt_text": "Analysiere {{session_title}}.",
            "scope": "session",
            "visibility": "private",
            "is_active": "1",
        }
    )

    assert errors == []
    assert template["id"] == "meine_oeffentliche_vorlage"


def test_prompt_template_error_messages_use_correct_umlauts(monkeypatch, workspace_tmp: Path) -> None:
    from core.services.prompts import get_active_prompt_template

    template_path = workspace_tmp / "prompt_templates.json"
    example_path = workspace_tmp / "prompt_templates.example.json"
    example_path.write_text('{"templates": []}\n', encoding="utf-8")
    monkeypatch.setattr(analysis_services, "PROMPT_TEMPLATES_PATH", template_path)
    monkeypatch.setattr(analysis_services, "PROMPT_TEMPLATES_EXAMPLE", example_path)

    _template, errors = get_active_prompt_template("fehlt", "session")

    assert "gewählte" in errors[0]
    assert "gewÃ" not in errors[0]


def test_new_prompt_templates_with_same_label_do_not_overwrite(monkeypatch, workspace_tmp: Path) -> None:
    template_path = workspace_tmp / "prompt_templates.json"
    example_path = workspace_tmp / "prompt_templates.example.json"
    example_path.write_text('{"templates": []}\n', encoding="utf-8")
    monkeypatch.setattr(analysis_services, "PROMPT_TEMPLATES_PATH", template_path)
    monkeypatch.setattr(analysis_services, "PROMPT_TEMPLATES_EXAMPLE", example_path)

    first, first_errors = analysis_services.save_prompt_template_from_form(
        {
            "label": "Gleiche Vorlage",
            "prompt_text": "Analysiere {{session_title}}.",
            "scope": "session",
            "visibility": "private",
            "is_active": "1",
        }
    )
    second, second_errors = analysis_services.save_prompt_template_from_form(
        {
            "label": "Gleiche Vorlage",
            "prompt_text": "Analysiere {{committee}}.",
            "scope": "session",
            "visibility": "private",
            "is_active": "1",
        }
    )

    assert first_errors == []
    assert second_errors == []
    assert first["id"] == "gleiche_vorlage"
    assert second["id"] == "gleiche_vorlage_2"
    assert analysis_services.get_prompt_template("gleiche_vorlage")["prompt_text"] == "Analysiere {{session_title}}."


def test_editing_existing_prompt_template_increments_revision(monkeypatch, workspace_tmp: Path) -> None:
    template_path = workspace_tmp / "prompt_templates.json"
    example_path = workspace_tmp / "prompt_templates.example.json"
    example_path.write_text('{"templates": []}\n', encoding="utf-8")
    monkeypatch.setattr(analysis_services, "PROMPT_TEMPLATES_PATH", template_path)
    monkeypatch.setattr(analysis_services, "PROMPT_TEMPLATES_EXAMPLE", example_path)

    created, errors = analysis_services.save_prompt_template_from_form(
        {
            "id": "edit_test",
            "label": "Edit Test",
            "prompt_text": "Analysiere {{session_title}}.",
            "scope": "session",
            "visibility": "private",
            "is_active": "1",
        }
    )
    edited, edit_errors = analysis_services.save_prompt_template_from_form(
        {
            "id": "edit_test",
            "label": "Edit Test",
            "prompt_text": "Analysiere {{committee}}.",
            "scope": "session",
            "visibility": "private",
            "is_active": "1",
            "allow_update": True,
        }
    )

    assert errors == []
    assert edit_errors == []
    assert created["revision"] == 1
    assert edited["id"] == "edit_test"
    assert edited["revision"] == 2
    assert edited["prompt_text"] == "Analysiere {{committee}}."


def test_editing_existing_multi_scope_prompt_template_preserves_scopes(monkeypatch, workspace_tmp: Path) -> None:
    template_path = workspace_tmp / "prompt_templates.json"
    example_path = workspace_tmp / "prompt_templates.example.json"
    example_path.write_text('{"templates": []}\n', encoding="utf-8")
    template_path.write_text(
        json.dumps(
            {
                "templates": [
                    {
                        "id": "multi_scope_edit",
                        "label": "Multi Scope",
                        "scope": ["document", "tops", "session"],
                        "description": "Legacy",
                        "prompt_text": "Analysiere {{session_title}}.",
                        "variables": ["session_title"],
                        "is_active": True,
                        "visibility": "private",
                        "revision": 1,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(analysis_services, "PROMPT_TEMPLATES_PATH", template_path)
    monkeypatch.setattr(analysis_services, "PROMPT_TEMPLATES_EXAMPLE", example_path)

    edited, errors = analysis_services.save_prompt_template_from_form(
        {
            "id": "multi_scope_edit",
            "label": "Multi Scope bearbeitet",
            "prompt_text": "Analysiere {{committee}}.",
            "scope": "session",
            "visibility": "private",
            "is_active": "1",
            "allow_update": True,
        }
    )

    assert errors == []
    assert edited["revision"] == 2
    assert edited["scopes"] == ["session", "document", "tops"]
    assert [item["id"] for item in analysis_services.list_prompt_templates("tops")] == ["multi_scope_edit"]
    assert analysis_services.get_prompt_template("multi_scope_edit")["prompt_text"] == "Analysiere {{committee}}."


def test_analysis_output_reads_private_prompt_snapshot(monkeypatch, workspace_tmp: Path) -> None:
    import sqlite3

    from core.services import outputs
    from core.services import paths

    db_path = workspace_tmp / "data" / "db" / "local_index.sqlite"
    snapshot_path = workspace_tmp / "data" / "private" / "prompt_snapshots" / "job_1.txt"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text("Privater Prompt", encoding="utf-8")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE analysis_jobs (
                id INTEGER PRIMARY KEY,
                created_at TEXT,
                session_id TEXT,
                scope TEXT,
                top_numbers_json TEXT,
                purpose TEXT,
                model_name TEXT,
                prompt_version TEXT,
                prompt_template_id TEXT,
                prompt_template_revision INTEGER,
                prompt_template_label TEXT,
                rendered_prompt_snapshot_path TEXT,
                status TEXT,
                error_message TEXT
            );
            CREATE TABLE analysis_outputs (
                id INTEGER PRIMARY KEY,
                job_id INTEGER,
                output_format TEXT,
                content TEXT,
                created_at TEXT
            );
            """
        )
        conn.execute(
            "INSERT INTO analysis_jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                1,
                "2026-01-01T00:00:00Z",
                "7123",
                "session",
                "[]",
                "content_analysis",
                "none",
                "template@2",
                "template",
                2,
                "Vorlage",
                str(snapshot_path),
                "done",
                "",
            ),
        )
        conn.execute(
            "INSERT INTO analysis_outputs (job_id, output_format, content, created_at) VALUES (?, ?, ?, ?)",
            (1, "markdown", "# Analyse", "2026-01-01T00:00:00Z"),
        )

    monkeypatch.setattr(paths, "LOCAL_INDEX_DB", db_path)
    monkeypatch.setattr(paths, "ANALYSIS_WORKFLOW_DB", workspace_tmp / "missing.sqlite")
    monkeypatch.setattr(paths, "ANALYSIS_OUTPUTS_DIR", workspace_tmp / "data" / "analysis_outputs")
    monkeypatch.setattr(paths, "ANALYSIS_PROMPTS_DIR", workspace_tmp / "data" / "private" / "analysis_prompts")

    job = outputs.get_analysis_output("local:1")

    assert job["prompt_template_label"] == "Vorlage"
    assert job["prompt_template_revision"] == 2
    assert job["prompt_text"] == "Privater Prompt"
    assert str(snapshot_path) not in job["sources"]
    assert str(snapshot_path) not in job["files"]


def test_public_job_filters_configured_private_prompt_paths(monkeypatch, workspace_tmp: Path) -> None:
    from core.services import outputs
    from core.services import paths

    private_dir = workspace_tmp / "custom_private"
    snapshot_path = private_dir / "prompt_snapshots" / "job_1.txt"
    prompt_copy_path = private_dir / "analysis_prompts" / "job_1.txt"
    public_path = "data/analysis_outputs/job_1.raw.json"

    monkeypatch.setattr(paths, "PRIVATE_DATA_DIR", private_dir)
    monkeypatch.setattr(paths, "PROMPT_SNAPSHOTS_DIR", private_dir / "prompt_snapshots")
    monkeypatch.setattr(paths, "ANALYSIS_PROMPTS_DIR", private_dir / "analysis_prompts")
    monkeypatch.setattr(paths, "PROMPT_TEMPLATES_PATH", private_dir / "prompt_templates.json")

    job = outputs._public_job(
        {
            "job_id": "local:1",
            "sources": {str(snapshot_path), str(prompt_copy_path), public_path},
            "files": [str(snapshot_path), str(prompt_copy_path), public_path],
            "rendered_prompt_snapshot_path": str(snapshot_path),
        }
    )

    assert job["sources"] == [public_path]
    assert job["files"] == [public_path]


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


def test_terminal_service_jobs_are_pruned_but_active_jobs_remain() -> None:
    with service_jobs._lock:
        old_jobs = dict(service_jobs._jobs)
        service_jobs._jobs.clear()
        try:
            for index in range(service_jobs.MAX_RETAINED_JOBS + 5):
                job = service_jobs.ServiceJob(
                    job_id=f"done-{index}",
                    action="build_local_index",
                    command=["fake-command"],
                    status="ok",
                    output=f"line-{index}",
                )
                service_jobs._jobs[job.job_id] = job
            active = service_jobs.ServiceJob(
                job_id="active",
                action="fetch_sessions",
                command=["fake-command"],
                status="running",
            )
            service_jobs._jobs[active.job_id] = active

            service_jobs._prune_jobs_locked()

            assert len(service_jobs._jobs) == service_jobs.MAX_RETAINED_JOBS
            assert "active" in service_jobs._jobs
            assert "done-0" not in service_jobs._jobs
            assert f"done-{service_jobs.MAX_RETAINED_JOBS + 4}" in service_jobs._jobs
        finally:
            service_jobs._jobs.clear()
            service_jobs._jobs.update(old_jobs)
