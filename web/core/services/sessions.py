"""Session loading for the Django web UI."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from . import paths
from .db import first_row
from .db import rows
from .source_check import check_sources


def list_sessions() -> list[dict[str, Any]]:
    """Return indexed sessions, enriched with simple counts when available."""

    sessions = rows(
        paths.LOCAL_INDEX_DB,
        """
        SELECT
            s.session_id,
            s.date,
            s.committee,
            s.meeting_name,
            s.start_time,
            s.location,
            COUNT(DISTINCT ai.id) AS agenda_count,
            COUNT(DISTINCT d.id) AS document_count
        FROM sessions s
        LEFT JOIN agenda_items ai ON ai.session_id = s.session_id
        LEFT JOIN documents d ON d.session_id = s.session_id
        GROUP BY s.session_id, s.date, s.committee, s.meeting_name, s.start_time, s.location
        ORDER BY s.date DESC, s.committee ASC
        """,
    )
    return [_with_session_display_fields(session) for session in sessions]


def get_session(session_id: str) -> dict[str, Any] | None:
    """Return one session with agenda items and documents."""

    session = first_row(
        paths.LOCAL_INDEX_DB,
        """
        SELECT session_id, date, committee, meeting_name, start_time, location, detail_url, session_path
        FROM sessions
        WHERE session_id = ?
        """,
        (session_id,),
    )
    if not session:
        return None
    session = _with_session_display_fields(session)

    agenda_items = rows(
        paths.LOCAL_INDEX_DB,
        """
        SELECT id, number, title, reporter, status, decision, documents_present
        FROM agenda_items
        WHERE session_id = ?
        ORDER BY id
        """,
        (session_id,),
    )
    documents = rows(
        paths.LOCAL_INDEX_DB,
        """
        SELECT id, title, category, document_type, agenda_item, url, local_path, content_type, content_length
        FROM documents
        WHERE session_id = ?
        ORDER BY COALESCE(agenda_item, ''), title
        """,
        (session_id,),
    )
    documents_by_agenda: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for document in documents:
        documents_by_agenda[str(document.get("agenda_item") or "")].append(document)
    for item in agenda_items:
        item["documents"] = documents_by_agenda.get(str(item.get("number") or ""), [])

    session["agenda_items"] = agenda_items
    session["documents"] = documents
    session["source_status"] = check_sources(session_id)
    return session


def _with_session_display_fields(session: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(session)
    enriched["display_date"] = _format_german_date(str(enriched.get("date") or ""))
    return enriched


def _format_german_date(value: str) -> str:
    if not value:
        return ""
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return value
