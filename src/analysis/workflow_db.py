"""SQLite index for analysis workflow status and file artifacts."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.analysis.schemas import DEFAULT_ANALYSIS_PURPOSE
from src.paths import ANALYSIS_WORKFLOW_DB


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class AnalysisJobRecord:
    session_id: str
    scope: str
    top_numbers: list[str] = field(default_factory=list)
    purpose: str = DEFAULT_ANALYSIS_PURPOSE
    source_db: str = ""
    source_job_id: int | None = None
    model_name: str = ""
    prompt_version: str = ""
    status: str = "draft"
    error_message: str = ""


@dataclass(frozen=True)
class AnalysisArtifactRecord:
    job_id: int
    output_type: str
    schema_version: str
    json_path: str = ""
    markdown_path: str = ""
    status: str = "draft"


@dataclass(frozen=True)
class PublicationJobRecord:
    output_id: int
    target: str
    slug: str
    title: str
    status: str = "draft"
    review_status: str = "pending"
    published_url: str = ""
    published_at: str = ""
    error_message: str = ""


def initialize_analysis_workflow_db(db_path: Path | None = None) -> Path:
    """Create or migrate the local analysis workflow database."""

    db_path = db_path or ANALYSIS_WORKFLOW_DB
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS analysis_jobs (
                job_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                scope TEXT NOT NULL,
                top_numbers_json TEXT,
                purpose TEXT NOT NULL DEFAULT 'content_analysis',
                source_db TEXT,
                source_job_id INTEGER,
                model_name TEXT,
                prompt_version TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                error_message TEXT
            );

            CREATE TABLE IF NOT EXISTS analysis_outputs (
                output_id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                output_type TEXT NOT NULL,
                schema_version TEXT NOT NULL,
                json_path TEXT,
                markdown_path TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(job_id) REFERENCES analysis_jobs(job_id)
            );

            CREATE TABLE IF NOT EXISTS publication_jobs (
                publication_id INTEGER PRIMARY KEY AUTOINCREMENT,
                output_id INTEGER NOT NULL,
                target TEXT NOT NULL,
                slug TEXT,
                title TEXT,
                status TEXT NOT NULL,
                review_status TEXT NOT NULL,
                published_url TEXT,
                created_at TEXT NOT NULL,
                published_at TEXT,
                error_message TEXT,
                FOREIGN KEY(output_id) REFERENCES analysis_outputs(output_id)
            );
            """
        )
        _ensure_column(conn, "analysis_jobs", "purpose", "TEXT NOT NULL DEFAULT 'content_analysis'")
        _ensure_column(conn, "analysis_jobs", "updated_at", "TEXT")
        _ensure_column(conn, "analysis_jobs", "source_db", "TEXT")
        _ensure_column(conn, "analysis_jobs", "source_job_id", "INTEGER")
        conn.commit()
    return db_path


def create_analysis_job(
    job: AnalysisJobRecord, db_path: Path | None = None
) -> int:
    """Insert an analysis job index row and return its job_id."""

    db_path = initialize_analysis_workflow_db(db_path)
    now = utc_now()
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO analysis_jobs
                (session_id, scope, top_numbers_json, purpose, source_db, source_job_id,
                 model_name, prompt_version, status, created_at, updated_at, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.session_id,
                job.scope,
                json.dumps(job.top_numbers, ensure_ascii=False),
                job.purpose or DEFAULT_ANALYSIS_PURPOSE,
                job.source_db,
                job.source_job_id,
                job.model_name,
                job.prompt_version,
                job.status,
                now,
                now,
                job.error_message or None,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def add_analysis_output(
    artifact: AnalysisArtifactRecord, db_path: Path | None = None
) -> int:
    """Insert an output artifact index row and return its output_id."""

    db_path = initialize_analysis_workflow_db(db_path)
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO analysis_outputs
                (job_id, output_type, schema_version, json_path, markdown_path, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact.job_id,
                artifact.output_type,
                artifact.schema_version,
                artifact.json_path,
                artifact.markdown_path,
                artifact.status,
                utc_now(),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def create_publication_job(
    publication: PublicationJobRecord, db_path: Path | None = None
) -> int:
    """Insert a publication workflow row without publishing anything."""

    db_path = initialize_analysis_workflow_db(db_path)
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO publication_jobs
                (output_id, target, slug, title, status, review_status, published_url,
                 created_at, published_at, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                publication.output_id,
                publication.target,
                publication.slug,
                publication.title,
                publication.status,
                publication.review_status,
                publication.published_url,
                utc_now(),
                publication.published_at or None,
                publication.error_message or None,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def _ensure_column(
    conn: sqlite3.Connection, table: str, column: str, definition: str
) -> None:
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
