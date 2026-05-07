from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.analysis.schemas import (
    ANALYSIS_OUTPUT_SCHEMA_VERSION,
    ANALYSIS_OUTPUT_SCHEMA_VERSION_V2,
    AnalysisOutputRecord,
)
from src.analysis.service import AnalysisRequest, AnalysisService, _parse_ki_json_response


# ---------------------------------------------------------------------------
# DB schema: ensure_analysis_tables
# ---------------------------------------------------------------------------


def test_ensure_analysis_tables_creates_correct_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite"
    with sqlite3.connect(db_path) as conn:
        AnalysisService().ensure_analysis_tables(conn)
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "analysis_jobs" in tables
        assert "analysis_outputs" in tables

        jobs_cols = {row[1] for row in conn.execute("PRAGMA table_info(analysis_jobs)").fetchall()}
        assert jobs_cols >= {
            "id", "created_at", "session_id", "scope",
            "top_numbers_json", "purpose", "model_name", "prompt_version",
            "prompt_template_id", "prompt_template_revision", "prompt_template_label",
            "rendered_prompt_snapshot_path", "status", "error_message",
        }

        outputs_cols = {row[1] for row in conn.execute("PRAGMA table_info(analysis_outputs)").fetchall()}
        assert outputs_cols >= {"id", "job_id", "output_format", "content", "created_at"}


def test_ensure_analysis_tables_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite"
    svc = AnalysisService()
    with sqlite3.connect(db_path) as conn:
        svc.ensure_analysis_tables(conn)
        svc.ensure_analysis_tables(conn)  # second call must not raise


def test_export_markdown_uses_runtime_default_path(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "exports" / "analysis_latest.md"
    monkeypatch.setattr("src.analysis.service.DEFAULT_ANALYSIS_MARKDOWN", target)

    exported = AnalysisService().export_markdown("# Analyse")

    assert exported == target
    assert target.read_text(encoding="utf-8") == "# Analyse\n"


def test_parse_ki_json_response_accepts_plain_json() -> None:
    assert _parse_ki_json_response('{"title": "Test"}') == {"title": "Test"}


def test_parse_ki_json_response_accepts_markdown_fenced_json() -> None:
    assert _parse_ki_json_response('```json\n{"title": "Test"}\n```') == {"title": "Test"}


def test_parse_ki_json_response_returns_empty_dict_for_invalid_json() -> None:
    assert _parse_ki_json_response("kein json") == {}


def test_publication_draft_uses_ki_json_title_and_body() -> None:
    record = AnalysisOutputRecord(
        job_id=1,
        created_at="2026-05-07T12:00:00Z",
        session_id="123",
        purpose="journalistic_publication",
        ki_response=(
            '{"title":"Titel","subtitle":"Untertitel","intro":"Intro",'
            '"body":"Text","sources":[{"title":"Vorlage","document_type":"Beschluss"}]}'
        ),
        session_date="2026-05-07",
    )

    draft = AnalysisService()._build_publication_draft(record, "fallback", {})

    assert draft.title == "Titel"
    assert draft.summary_short == "Untertitel"
    assert draft.summary_long == "Intro"
    assert "# Titel" in draft.body_markdown
    assert "Text" in draft.body_markdown
    assert "Vorlage (Beschluss)" in draft.body_markdown


def test_publication_draft_falls_back_to_markdown_for_invalid_json() -> None:
    record = AnalysisOutputRecord(
        job_id=1,
        created_at="2026-05-07T12:00:00Z",
        session_id="123",
        purpose="journalistic_publication",
        ki_response="kein json",
        session_date="2026-05-07",
    )

    draft = AnalysisService()._build_publication_draft(
        record, "fallback markdown", {"committee": "Rat"}
    )

    assert draft.title == "Rat"
    assert draft.body_markdown == "fallback markdown"


def test_structured_analysis_uses_ki_json_fields() -> None:
    record = AnalysisOutputRecord(
        job_id=1,
        session_id="123",
        purpose="journalistic_publication",
        ki_response=(
            '{"topic":"Thema","missing_information":["Zahl fehlt"],'
            '"source_notes":["Quelle pruefen"]}'
        ),
    )

    structured = AnalysisService()._build_structured_analysis(record, {"committee": "Rat"})

    assert structured.topic.title == "Thema"
    assert structured.open_questions == ["Zahl fehlt"]
    assert structured.risks_or_uncertainties == ["Quelle pruefen"]


def test_persist_analysis_artifacts_writes_valid_ki_json_artifact(
    tmp_path: Path, monkeypatch
) -> None:
    outputs_dir = tmp_path / "data" / "analysis_outputs"
    prompts_dir = tmp_path / "data" / "private" / "analysis_prompts"
    latest_md = outputs_dir / "summaries" / "analysis_latest.md"
    workflow_db = tmp_path / "data" / "db" / "analysis_workflow.sqlite"
    snapshot_dir = tmp_path / "data" / "private" / "prompt_snapshots"
    monkeypatch.setattr("src.analysis.service.ANALYSIS_OUTPUTS_DIR", outputs_dir)
    monkeypatch.setattr("src.analysis.service.ANALYSIS_PROMPTS_DIR", prompts_dir)
    monkeypatch.setattr("src.analysis.service.DEFAULT_ANALYSIS_MARKDOWN", latest_md)
    monkeypatch.setattr("src.analysis.service.PROMPT_SNAPSHOTS_DIR", snapshot_dir)
    monkeypatch.setattr("src.analysis.workflow_db.ANALYSIS_WORKFLOW_DB", workflow_db)

    record = AnalysisOutputRecord(
        job_id=77,
        created_at="2026-05-07T12:00:00Z",
        session_id="123",
        purpose="journalistic_publication",
        markdown="fallback markdown",
        ki_response='{"title":"Titel","intro":"Intro","body":"Text"}',
        source_db=str(tmp_path / "missing.sqlite"),
        session_date="2026-05-07",
    )

    AnalysisService().persist_analysis_artifacts(record, session={"committee": "Rat"})

    output_dir = outputs_dir / "2026" / "05" / "2026-05-07-123"
    ki_json = output_dir / "job_77.ki_response.json"
    article = output_dir / "job_77.article.md"
    assert ki_json.exists()
    assert json.loads(ki_json.read_text(encoding="utf-8")) == {
        "title": "Titel",
        "intro": "Intro",
        "body": "Text",
    }
    assert "# Titel" in article.read_text(encoding="utf-8")


def test_persist_analysis_artifacts_keeps_markdown_for_partial_ki_json(
    tmp_path: Path, monkeypatch
) -> None:
    outputs_dir = tmp_path / "data" / "analysis_outputs"
    prompts_dir = tmp_path / "data" / "private" / "analysis_prompts"
    latest_md = outputs_dir / "summaries" / "analysis_latest.md"
    workflow_db = tmp_path / "data" / "db" / "analysis_workflow.sqlite"
    snapshot_dir = tmp_path / "data" / "private" / "prompt_snapshots"
    monkeypatch.setattr("src.analysis.service.ANALYSIS_OUTPUTS_DIR", outputs_dir)
    monkeypatch.setattr("src.analysis.service.ANALYSIS_PROMPTS_DIR", prompts_dir)
    monkeypatch.setattr("src.analysis.service.DEFAULT_ANALYSIS_MARKDOWN", latest_md)
    monkeypatch.setattr("src.analysis.service.PROMPT_SNAPSHOTS_DIR", snapshot_dir)
    monkeypatch.setattr("src.analysis.workflow_db.ANALYSIS_WORKFLOW_DB", workflow_db)

    record = AnalysisOutputRecord(
        job_id=78,
        created_at="2026-05-07T12:00:00Z",
        session_id="123",
        purpose="journalistic_publication",
        markdown="# Fallback Analyse\n\nVollstaendige Analysegrundlage.",
        ki_response='{"title":"Nur Metadaten"}',
        source_db=str(tmp_path / "missing.sqlite"),
        session_date="2026-05-07",
    )

    AnalysisService().persist_analysis_artifacts(record, session={"committee": "Rat"})

    output_dir = outputs_dir / "2026" / "05" / "2026-05-07-123"
    article = output_dir / "job_78.article.md"
    latest = latest_md.read_text(encoding="utf-8")
    assert article.read_text(encoding="utf-8") == "# Fallback Analyse\n\nVollstaendige Analysegrundlage.\n"
    assert latest == "# Fallback Analyse\n\nVollstaendige Analysegrundlage."


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

    outputs_dir = tmp_path / "data" / "analysis_outputs"
    prompts_dir = tmp_path / "data" / "private" / "analysis_prompts"
    latest_md = outputs_dir / "summaries" / "analysis_latest.md"
    workflow_db = tmp_path / "data" / "db" / "analysis_workflow.sqlite"
    snapshot_dir = tmp_path / "data" / "private" / "prompt_snapshots"
    monkeypatch.setattr("src.analysis.service.ANALYSIS_OUTPUTS_DIR", outputs_dir)
    monkeypatch.setattr("src.analysis.service.ANALYSIS_PROMPTS_DIR", prompts_dir)
    monkeypatch.setattr("src.analysis.service.DEFAULT_ANALYSIS_MARKDOWN", latest_md)
    monkeypatch.setattr("src.analysis.service.PROMPT_SNAPSHOTS_DIR", snapshot_dir)
    monkeypatch.setattr("src.analysis.workflow_db.ANALYSIS_WORKFLOW_DB", workflow_db)

    request = AnalysisRequest(
        db_path=db_path,
        session={"session_id": "7001", "date": "2026-03-10", "committee": "Rat"},
        scope="session",
        selected_tops=[],
        prompt="Bitte zentrale Entscheidungen und Kosten nennen.",
        prompt_template_id="session_demo",
        prompt_template_revision=3,
        prompt_template_label="Demo",
        prompt_version="session_demo@3",
    )
    record = service.run_journalistic_analysis(request)

    assert record.schema_version == ANALYSIS_OUTPUT_SCHEMA_VERSION
    assert record.job_id >= 1
    assert record.document_count == 1
    assert "Quellen im Scope" in record.markdown
    assert "lokale Quelle" in record.markdown

    # Session-oriented output: OUTPUTS_DIR / 2026 / 03 / 2026-03-10_Rat_7001
    session_out_dir = outputs_dir / "2026" / "03" / "2026-03-10_Rat_7001"
    raw_output = session_out_dir / f"job_{record.job_id}.raw.json"
    structured_output = session_out_dir / f"job_{record.job_id}.structured.json"
    md_output = session_out_dir / f"job_{record.job_id}.article.md"
    prompt_output = prompts_dir / f"job_{record.job_id}.txt"

    assert raw_output.exists()
    assert structured_output.exists()
    assert md_output.exists()
    assert prompt_output.exists()
    assert latest_md.exists()
    assert workflow_db.exists()

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        job_row = dict(conn.execute("SELECT * FROM analysis_jobs WHERE id = ?", (record.job_id,)).fetchone())
    assert job_row["prompt_template_id"] == "session_demo"
    assert job_row["prompt_template_revision"] == 3
    assert job_row["prompt_template_label"] == "Demo"
    assert Path(job_row["rendered_prompt_snapshot_path"]).is_file()

    payload = json.loads(raw_output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == ANALYSIS_OUTPUT_SCHEMA_VERSION_V2
    assert payload["output_type"] == "raw_analysis"
    assert payload["job_id"] == record.job_id
