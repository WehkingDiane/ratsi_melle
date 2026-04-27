from __future__ import annotations

import sqlite3
from pathlib import Path

from src.analysis.workflow_db import (
    AnalysisArtifactRecord,
    AnalysisJobRecord,
    PublicationJobRecord,
    add_analysis_output,
    create_analysis_job,
    create_publication_job,
    initialize_analysis_workflow_db,
)


def test_analysis_workflow_db_initializes_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "analysis_workflow.sqlite"
    initialize_analysis_workflow_db(db_path)

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

    assert {"analysis_jobs", "analysis_outputs", "publication_jobs"} <= tables


def test_analysis_workflow_db_stores_job_output_and_publication(tmp_path: Path) -> None:
    db_path = tmp_path / "analysis_workflow.sqlite"
    job_id = create_analysis_job(
        AnalysisJobRecord(
            session_id="7123",
            scope="tops",
            top_numbers=["Oe 7"],
            purpose="journalistic_publication",
            source_db="data/db/local_index.sqlite",
            source_job_id=1,
            model_name="mock",
            prompt_version="v2",
            status="done",
        ),
        db_path,
    )
    output_id = add_analysis_output(
        AnalysisArtifactRecord(
            job_id=job_id,
            output_type="publication_draft",
            schema_version="2.0",
            json_path="data/analysis_outputs/2026/03/session/job_1.publication.json",
            status="draft",
        ),
        db_path,
    )
    publication_id = create_publication_job(
        PublicationJobRecord(
            output_id=output_id,
            target="local_static_site",
            slug="test-artikel",
            title="Test Artikel",
            status="draft",
            review_status="pending",
        ),
        db_path,
    )

    with sqlite3.connect(db_path) as conn:
        job = conn.execute(
            "SELECT purpose, top_numbers_json, source_db, source_job_id FROM analysis_jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        output = conn.execute(
            "SELECT job_id, output_type, json_path FROM analysis_outputs WHERE output_id = ?",
            (output_id,),
        ).fetchone()
        publication = conn.execute(
            "SELECT status, review_status FROM publication_jobs WHERE publication_id = ?",
            (publication_id,),
        ).fetchone()

    assert job == (
        "journalistic_publication",
        '["Oe 7"]',
        "data/db/local_index.sqlite",
        1,
    )
    assert output == (
        job_id,
        "publication_draft",
        "data/analysis_outputs/2026/03/session/job_1.publication.json",
    )
    assert publication == ("draft", "pending")


def test_analysis_workflow_db_allocates_ids_for_duplicate_source_jobs(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "analysis_workflow.sqlite"

    local_job_id = create_analysis_job(
        AnalysisJobRecord(
            session_id="7123",
            scope="session",
            source_db="data/db/local_index.sqlite",
            source_job_id=1,
        ),
        db_path,
    )
    online_job_id = create_analysis_job(
        AnalysisJobRecord(
            session_id="7123",
            scope="session",
            source_db="data/db/online_session_index.sqlite",
            source_job_id=1,
        ),
        db_path,
    )

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT job_id, source_db, source_job_id FROM analysis_jobs ORDER BY job_id"
        ).fetchall()

    assert local_job_id != online_job_id
    assert rows == [
        (local_job_id, "data/db/local_index.sqlite", 1),
        (online_job_id, "data/db/online_session_index.sqlite", 1),
    ]
