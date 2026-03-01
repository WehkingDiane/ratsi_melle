from __future__ import annotations

import json
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
    (session_dir / "manifest.json").write_text(
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
    output_path = tmp_path / "data" / "processed" / "local_index.sqlite"
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
    output_path = tmp_path / "data" / "processed" / "online_session_index.sqlite"
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
