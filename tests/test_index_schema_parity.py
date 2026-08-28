from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from scripts import build_local_index, build_online_index_db
from src.fetching.models import AgendaItem, DocumentReference, SessionDetail, SessionReference


TIME_RE = re.compile(r"^\d{1,2}:\d{2}(?:\s*Uhr)?$")


def _schema_snapshot(path: Path) -> dict[str, dict[str, list[tuple[str, str]]]]:
    snapshot: dict[str, dict[str, list[tuple[str, str]]]] = {}
    with sqlite3.connect(path) as conn:
        tables = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence'"
        ).fetchall()]
        for table in sorted(tables):
            cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
            snapshot[table] = {
                "columns": [(row[1], row[2]) for row in cols],
                "indexes": [
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=? ORDER BY name",
                        (table,),
                    ).fetchall()
                ],
            }
    return snapshot


def _assert_time_format(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        rows = conn.execute("SELECT date, start_time FROM sessions").fetchall()
    for date_value, start_time in rows:
        assert isinstance(date_value, str)
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", date_value)
        if start_time is not None:
            assert TIME_RE.match(start_time), f"Unexpected time format: {start_time}"


def _write_local_fixture(root: Path) -> None:
    session_dir = root / "2025" / "06" / "2025-06-05_Rat_123"
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "session_detail.html").write_text("<html></html>", encoding="utf-8")
    (session_dir / "agenda_summary.json").write_text(
        json.dumps(
            {
                "session": {"id": "123", "committee": "Rat", "meeting_name": "Ratssitzung", "date": "2025-06-05"},
                "generated_at": "2025-06-05T10:00:00Z",
                "agenda_items": [
                    {
                        "number": "Ö 1",
                        "title": "Test TOP",
                        "reporter": "Tester",
                        "status": "beschlossen",
                        "decision": "accepted",
                        "documents_present": True,
                    }
                ],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    manifest_path = session_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "session": {
                    "id": "123",
                    "committee": "Rat",
                    "meeting_name": "Ratssitzung",
                    "date": "2025-06-05",
                    "detail_url": "https://example.org/si0057.asp?__ksinr=123",
                    "location": "Rathaus",
                },
                "retrieved_at": "2025-06-05T10:00:00Z",
                "documents": [
                    {
                        "title": "Dokument",
                        "category": "PR",
                        "agenda_item": "Ö 1",
                        "url": "https://example.org/doc.pdf",
                        "path": "session-documents/doc.pdf",
                        "sha1": "abc123",
                        "retrieved_at": "2025-06-05T10:00:00Z",
                        "content_type": "application/pdf",
                        "content_length": 1234,
                    }
                ],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _build_local_db(tmp_path: Path) -> Path:
    data_root = tmp_path / "data" / "raw"
    _write_local_fixture(data_root)
    output_path = tmp_path / "data" / "db" / "local_index.sqlite"
    build_local_index.build_index(data_root, output_path, refresh_existing=False, only_refresh=False)
    return output_path


@dataclass(frozen=True)
class _StubClient:
    references: list[SessionReference]
    detail: SessionDetail

    def fetch_month(self, year: int, month: int) -> list[SessionReference]:
        return self.references

    def fetch_session(self, reference: SessionReference) -> SessionDetail:
        return self.detail


def _build_online_db(tmp_path: Path) -> Path:
    reference = SessionReference(
        committee="Rat",
        meeting_name="Ratssitzung",
        session_id="123",
        date=date(2025, 6, 5),
        start_time="17:00 Uhr",
        detail_url="https://example.org/si0057.asp?__ksinr=123",
        location="Rathaus",
    )
    detail = SessionDetail(
        reference=reference,
        agenda_items=[
            AgendaItem(
                number="Ö 1",
                title="Test TOP",
                status="beschlossen",
                reporter="Tester",
                documents=[DocumentReference(title="Dokument", url="https://example.org/doc.pdf", on_agenda_item="Ö 1")],
            )
        ],
        session_documents=[DocumentReference(title="Dokument", url="https://example.org/doc.pdf", category="PR")],
        retrieved_at=datetime(2025, 6, 5, 10, 0, 0, tzinfo=timezone.utc),
        raw_html="",
    )
    client = _StubClient(references=[reference], detail=detail)
    output_path = tmp_path / "data" / "db" / "online_session_index.sqlite"
    build_online_index_db.build_session_db(
        client, 2025, [6], output_path, refresh_existing=False, only_refresh=False, migrate_from=Path("missing")
    )
    return output_path


def test_index_schema_parity_and_time_format(tmp_path: Path) -> None:
    local_db = _build_local_db(tmp_path)
    online_db = _build_online_db(tmp_path)

    assert _schema_snapshot(local_db) == _schema_snapshot(online_db)
    _assert_time_format(local_db)
    _assert_time_format(online_db)
    _assert_document_metadata(local_db)
    _assert_document_metadata(online_db)


def test_local_build_refreshes_stale_agenda_summary_from_newer_html(tmp_path: Path) -> None:
    data_root = tmp_path / "data" / "raw"
    session_dir = data_root / "2025" / "06" / "2025-06-05_Rat_123"
    session_dir.mkdir(parents=True)
    detail_html = Path("tests/fixtures/si0057_sample.html").read_text(encoding="utf-8")
    source_html_sha1 = build_local_index.SessionNetClient.source_html_sha1(detail_html)
    summary_path = session_dir / "agenda_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "session": {"id": "123", "committee": "Rat", "meeting_name": "Ratssitzung", "date": "2025-06-05"},
                "generated_at": "2025-06-05T10:00:00Z",
                "source_html_sha1": source_html_sha1,
                "agenda_items": [{"number": "Ö 1", "title": "Veralteter TOP"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    manifest_path = session_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "session": {
                    "id": "123",
                    "committee": "Rat",
                    "meeting_name": "Ratssitzung",
                    "date": "2025-06-05",
                    "detail_url": "https://example.org/si0057.asp?__ksinr=123",
                },
                "retrieved_at": "2025-06-05T10:00:00Z",
                "source_html_sha1": source_html_sha1,
                "documents": [
                    {
                        "title": "Dokument",
                        "url": "https://example.org/document.pdf",
                        "path": "session-documents/document.pdf",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    detail_path = session_dir / "session_detail.html"
    detail_path.write_text(detail_html, encoding="utf-8")
    os.utime(detail_path, (1_700_000_000, 1_700_000_000))
    os.utime(summary_path, (1_700_000_100, 1_700_000_100))
    os.utime(manifest_path, (1_700_000_100, 1_700_000_100))

    output_path = tmp_path / "data" / "db" / "local_index.sqlite"
    build_local_index.build_index(data_root, output_path, refresh_existing=False, only_refresh=False)
    with sqlite3.connect(output_path) as conn:
        assert conn.execute(
            "SELECT title FROM agenda_items WHERE session_id = '123'"
        ).fetchall() == [("Veralteter TOP",)]

    os.utime(detail_path, (1_700_000_200, 1_700_000_200))
    build_local_index.build_index(data_root, output_path, refresh_existing=False, only_refresh=False)

    with sqlite3.connect(output_path) as conn:
        agenda_items = conn.execute(
            "SELECT number, title FROM agenda_items WHERE session_id = '123' ORDER BY id"
        ).fetchall()
        documents = conn.execute(
            "SELECT agenda_item, title, local_path FROM documents WHERE session_id = '123' ORDER BY id"
        ).fetchall()
    refreshed_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    refreshed_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert [number for number, _title in agenda_items] == ["Ö 1", "Ö 2", "Ö 3"]
    assert agenda_items[0][1] == "Genehmigung des Protokolls"
    assert [item["number"] for item in refreshed_summary["agenda_items"]] == ["Ö 1", "Ö 2", "Ö 3"]
    assert len(documents) == 5
    assert len(refreshed_manifest["documents"]) == 5


def test_local_session_discovery_excludes_separate_landkreis_raw_data(tmp_path: Path) -> None:
    data_root = tmp_path / "data" / "raw"
    session_dir = data_root / "2026" / "09" / "2026-09-01_Rat_8209"
    session_dir.mkdir(parents=True)
    (session_dir / "agenda_summary.json").write_text('{"agenda_items": []}', encoding="utf-8")
    landkreis_dir = data_root / "landkreis" / "amtsblaetter" / "2026" / "2026-01-15_amtsblatt-01-2026"
    landkreis_dir.mkdir(parents=True)
    (landkreis_dir / "manifest.json").write_text("{}", encoding="utf-8")

    sessions = list(build_local_index.iter_session_folders(data_root))

    assert [(session.session_id, session.path) for session in sessions] == [("8209", session_dir)]


def test_local_build_removes_historical_landkreis_rows(tmp_path: Path) -> None:
    output_path = _build_local_db(tmp_path)
    with sqlite3.connect(output_path) as conn:
        conn.execute(
            "INSERT INTO sessions (session_id, date, session_path) VALUES (?, ?, ?)",
            ("2026", "2026-07-15", "data/raw/landkreis/amtsblaetter/2026/example-2026"),
        )
        conn.execute("INSERT INTO agenda_items (session_id, number) VALUES (?, ?)", ("2026", "Ö 1"))
        conn.execute("INSERT INTO documents (session_id, title) VALUES (?, ?)", ("2026", "Amtsblatt"))

    build_local_index.build_index(
        tmp_path / "data" / "raw",
        output_path,
        refresh_existing=False,
        only_refresh=False,
    )

    with sqlite3.connect(output_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM sessions WHERE session_id = '2026'").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM agenda_items WHERE session_id = '2026'").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM documents WHERE session_id = '2026'").fetchone()[0] == 0


def _assert_document_metadata(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        rows = conn.execute(
            """
            SELECT title, category, document_type, sha1, retrieved_at
            FROM documents
            ORDER BY id
            """
        ).fetchall()
    assert rows
    for _, _, document_type, _, retrieved_at in rows:
        assert document_type in {
            "vorlage",
            "beschlussvorlage",
            "protokoll",
            "bekanntmachung",
            "sonstiges",
        }
        assert isinstance(retrieved_at, str)
        assert retrieved_at.endswith("Z")
    assert any(category == "PR" and document_type == "protokoll" for _, category, document_type, _, _ in rows)
