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
    review_required: bool = True
    review_notes: str = ""
    reviewed_by: str = ""
    reviewed_at: str = ""
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
                review_required INTEGER NOT NULL DEFAULT 1,
                review_notes TEXT,
                reviewed_by TEXT,
                reviewed_at TEXT,
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
        _ensure_column(conn, "publication_jobs", "review_required", "INTEGER NOT NULL DEFAULT 1")
        _ensure_column(conn, "publication_jobs", "review_notes", "TEXT")
        _ensure_column(conn, "publication_jobs", "reviewed_by", "TEXT")
        _ensure_column(conn, "publication_jobs", "reviewed_at", "TEXT")
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
                (output_id, target, slug, title, status, review_status, review_required,
                 review_notes, reviewed_by, reviewed_at, published_url, created_at,
                 published_at, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                publication.output_id,
                publication.target,
                publication.slug,
                publication.title,
                publication.status,
                publication.review_status,
                1 if publication.review_required else 0,
                publication.review_notes or None,
                publication.reviewed_by or None,
                publication.reviewed_at or None,
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


def list_analysis_jobs_with_outputs(db_path: Path | None = None) -> list[dict[str, object]]:
    """Return workflow jobs with output and publication metadata for UI consumers."""

    db_path = db_path or ANALYSIS_WORKFLOW_DB
    if not db_path.exists():
        return []

    initialize_analysis_workflow_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT
                j.job_id,
                j.session_id,
                j.scope,
                j.top_numbers_json,
                j.purpose,
                j.source_db,
                j.source_job_id,
                j.model_name,
                j.prompt_version,
                j.status,
                j.created_at,
                j.updated_at,
                j.error_message,
                o.output_id,
                o.output_type,
                o.schema_version,
                o.json_path,
                o.markdown_path,
                o.status AS output_status,
                o.created_at AS output_created_at,
                p.publication_id,
                p.target,
                p.slug,
                p.title,
                p.status AS publication_status,
                p.review_status,
                p.review_required,
                p.review_notes,
                p.reviewed_by,
                p.reviewed_at,
                p.published_url,
                p.published_at
            FROM analysis_jobs j
            LEFT JOIN analysis_outputs o ON o.job_id = j.job_id
            LEFT JOIN publication_jobs p ON p.output_id = o.output_id
            ORDER BY j.created_at DESC, o.created_at DESC, o.output_id DESC
            """
        ).fetchall()

    grouped: dict[int, dict[str, object]] = {}
    for row in rows:
        job_id = int(row["job_id"])
        if job_id not in grouped:
            grouped[job_id] = {
                "job_id": job_id,
                "session_id": str(row["session_id"] or ""),
                "scope": str(row["scope"] or ""),
                "top_numbers": json.loads(row["top_numbers_json"] or "[]"),
                "purpose": str(row["purpose"] or DEFAULT_ANALYSIS_PURPOSE),
                "source_db": str(row["source_db"] or ""),
                "source_job_id": row["source_job_id"],
                "model_name": str(row["model_name"] or ""),
                "prompt_version": str(row["prompt_version"] or ""),
                "status": str(row["status"] or ""),
                "created_at": str(row["created_at"] or ""),
                "updated_at": str(row["updated_at"] or ""),
                "error_message": str(row["error_message"] or ""),
                "outputs": [],
                "last_output_type": "",
                "last_output_path": "",
                "review_status": "",
                "publication_status": "",
            }
        job = grouped[job_id]

        if row["output_id"] is None:
            continue

        publication = None
        if row["publication_id"] is not None:
            publication = {
                "publication_id": int(row["publication_id"]),
                "target": str(row["target"] or ""),
                "slug": str(row["slug"] or ""),
                "title": str(row["title"] or ""),
                "status": str(row["publication_status"] or ""),
                "review_status": str(row["review_status"] or ""),
                "review_required": bool(row["review_required"]),
                "review_notes": str(row["review_notes"] or ""),
                "reviewed_by": str(row["reviewed_by"] or ""),
                "reviewed_at": str(row["reviewed_at"] or ""),
                "published_url": str(row["published_url"] or ""),
                "published_at": str(row["published_at"] or ""),
            }
            if not job["review_status"]:
                job["review_status"] = publication["review_status"]
            if not job["publication_status"]:
                job["publication_status"] = publication["status"]

        output = {
            "output_id": int(row["output_id"]),
            "output_type": str(row["output_type"] or ""),
            "schema_version": str(row["schema_version"] or ""),
            "json_path": str(row["json_path"] or ""),
            "markdown_path": str(row["markdown_path"] or ""),
            "status": str(row["output_status"] or ""),
            "created_at": str(row["output_created_at"] or ""),
            "publication": publication,
        }
        if not job["last_output_type"]:
            job["last_output_type"] = output["output_type"]
            job["last_output_path"] = output["json_path"] or output["markdown_path"]
        job["outputs"].append(output)

    return list(grouped.values())


def update_publication_job(
    *,
    output_id: int,
    review_required: bool,
    review_status: str,
    review_notes: str,
    reviewed_by: str,
    reviewed_at: str,
    publication_status: str,
    published_url: str,
    published_at: str,
    target: str = "local_static_site",
    title: str = "",
    slug: str = "",
    db_path: Path | None = None,
) -> int:
    """Create or update local review/publication state without publishing anything."""

    db_path = initialize_analysis_workflow_db(db_path)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT publication_id FROM publication_jobs WHERE output_id = ?",
            (output_id,),
        ).fetchone()
        if row:
            conn.execute(
                """
                UPDATE publication_jobs
                SET target = ?, slug = ?, title = ?, status = ?, review_status = ?,
                    review_required = ?, review_notes = ?, reviewed_by = ?, reviewed_at = ?,
                    published_url = ?, published_at = ?
                WHERE output_id = ?
                """,
                (
                    target,
                    slug,
                    title,
                    publication_status,
                    review_status,
                    1 if review_required else 0,
                    review_notes or None,
                    reviewed_by or None,
                    reviewed_at or None,
                    published_url or None,
                    published_at or None,
                    output_id,
                ),
            )
            conn.commit()
            return int(row[0])

    return create_publication_job(
        PublicationJobRecord(
            output_id=output_id,
            target=target,
            slug=slug,
            title=title,
            status=publication_status,
            review_status=review_status,
            review_required=review_required,
            review_notes=review_notes,
            reviewed_by=reviewed_by,
            reviewed_at=reviewed_at,
            published_url=published_url,
            published_at=published_at,
        ),
        db_path,
    )
