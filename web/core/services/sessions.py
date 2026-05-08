"""Session loading for the Django web UI."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import re
from pathlib import Path
from typing import Any

from src.fetching.storage_layout import resolve_local_file_path

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
            s.session_path,
            COUNT(DISTINCT ai.id) AS agenda_count,
            COUNT(DISTINCT d.id) AS document_count
        FROM sessions s
        LEFT JOIN agenda_items ai ON ai.session_id = s.session_id
        LEFT JOIN documents d ON d.session_id = s.session_id
        GROUP BY s.session_id, s.date, s.committee, s.meeting_name, s.start_time, s.location, s.session_path
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
        document["session_path"] = session.get("session_path") or ""
        _add_document_analysis_fields(document)
        documents_by_agenda[str(document.get("agenda_item") or "")].append(document)
    for item in agenda_items:
        item_documents = documents_by_agenda.get(str(item.get("number") or ""), [])
        item["documents"] = item_documents
        item["document_count"] = len(item_documents)
        item["analysis_document_count"] = sum(
            1 for document in item_documents if document.get("source_file_available")
        )
        item["has_analysis_documents"] = item["analysis_document_count"] > 0

    session["agenda_items"] = agenda_items
    session["documents"] = documents
    session["source_status"] = check_sources(session_id)
    return session


def _add_document_analysis_fields(document: dict[str, Any]) -> None:
    resolved = resolve_local_file_path(
        session_path=str(document.get("session_path") or ""),
        local_path=str(document.get("local_path") or ""),
    )
    document["resolved_local_path"] = str(resolved) if resolved else ""
    document["source_file_available"] = bool(resolved and Path(resolved).is_file())
    document["pdf_view_available"] = _is_pdf_document(document, resolved)
    document["display_type"] = (
        document.get("document_type")
        or document.get("content_type")
        or document.get("category")
        or "-"
    )


def get_local_pdf_document(session_id: str, document_id: int) -> dict[str, Any] | None:
    """Return an existing local PDF document path for browser display."""

    document = first_row(
        paths.LOCAL_INDEX_DB,
        """
        SELECT d.id, d.session_id, d.title, d.local_path, d.content_type, s.session_path
        FROM documents d
        JOIN sessions s ON s.session_id = d.session_id
        WHERE d.session_id = ? AND d.id = ?
        """,
        (session_id, document_id),
    )
    if not document:
        return None

    resolved = resolve_local_file_path(
        session_path=str(document.get("session_path") or ""),
        local_path=str(document.get("local_path") or ""),
    )
    if not _is_pdf_document(document, resolved):
        return None

    return {
        "path": Path(resolved),
        "title": document.get("title") or f"document-{document_id}.pdf",
        "content_type": "application/pdf",
    }


def _is_pdf_document(document: dict[str, Any], resolved: Path | None) -> bool:
    if not resolved or not Path(resolved).is_file():
        return False
    content_type = str(document.get("content_type") or "").lower()
    local_path = str(document.get("local_path") or "").lower()
    return "pdf" in content_type or local_path.endswith(".pdf") or Path(resolved).suffix.lower() == ".pdf"


def _with_session_display_fields(session: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(session)
    enriched["display_date"] = _format_german_date(str(enriched.get("date") or ""))
    raw_committee = str(enriched.get("committee") or "")
    meeting_name = str(enriched.get("meeting_name") or "").strip()
    committee = _humanize_committee_name(
        raw_committee
        or _committee_from_session_path(str(enriched.get("session_path") or ""))
    )
    if meeting_name and (not committee or _looks_like_storage_slug(raw_committee)):
        committee = meeting_name
    if committee:
        enriched["committee"] = committee

    if not meeting_name:
        enriched["meeting_name"] = (
            committee or f"Sitzung {enriched.get('session_id') or ''}".strip()
        )
    return enriched


def _committee_from_session_path(session_path: str) -> str:
    folder_name = Path(session_path.replace("\\", "/")).name
    match = re.match(r"^\d{4}-\d{2}-\d{2}[-_](?P<committee>.+)[-_]\d+$", folder_name)
    return match.group("committee") if match else ""


def _humanize_committee_name(value: str) -> str:
    text = value.strip().replace("_", "-")
    if not text:
        return ""
    text = re.sub(r"-+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _looks_like_storage_slug(value: str) -> bool:
    return "-" in value.strip()


def _format_german_date(value: str) -> str:
    if not value:
        return ""
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return value
