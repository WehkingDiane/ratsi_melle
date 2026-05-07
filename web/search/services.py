"""Document search services for the Django web UI."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from core.services import paths
from core.services.db import rows


REPO_ROOT = paths.REPO_ROOT
LOCAL_INDEX_DB = paths.LOCAL_INDEX_DB

MAX_SEARCH_RESULTS = 100


def _sync_paths() -> None:
    paths.REPO_ROOT = Path(REPO_ROOT)
    paths.LOCAL_INDEX_DB = Path(LOCAL_INDEX_DB)


def search_documents(query: str, *, limit: int = MAX_SEARCH_RESULTS) -> list[dict[str, Any]]:
    """Search indexed document metadata in the local SQLite database."""

    normalized_query = " ".join(query.split())
    if not normalized_query:
        return []

    _sync_paths()
    terms = normalized_query.split()
    conditions: list[str] = []
    params: list[str | int] = []
    for term in terms:
        conditions.append(
            """
            (
                LOWER(COALESCE(d.title, '')) LIKE ? ESCAPE '\\'
                OR LOWER(COALESCE(d.document_type, '')) LIKE ? ESCAPE '\\'
                OR LOWER(COALESCE(d.category, '')) LIKE ? ESCAPE '\\'
                OR LOWER(COALESCE(d.agenda_item, '')) LIKE ? ESCAPE '\\'
                OR LOWER(COALESCE(d.local_path, '')) LIKE ? ESCAPE '\\'
                OR LOWER(COALESCE(s.committee, '')) LIKE ? ESCAPE '\\'
                OR LOWER(COALESCE(s.meeting_name, '')) LIKE ? ESCAPE '\\'
                OR LOWER(COALESCE(s.session_id, '')) LIKE ? ESCAPE '\\'
                OR LOWER(COALESCE(s.date, '')) LIKE ? ESCAPE '\\'
            )
            """
        )
        pattern = f"%{_escape_like(term.lower())}%"
        params.extend([pattern] * 9)

    params.append(max(1, min(int(limit), MAX_SEARCH_RESULTS)))
    results = rows(
        paths.LOCAL_INDEX_DB,
        f"""
        SELECT
            d.id,
            d.session_id,
            d.title,
            d.category,
            d.document_type,
            d.agenda_item,
            d.local_path,
            d.content_type,
            s.date,
            s.committee,
            s.meeting_name,
            s.detail_url
        FROM documents d
        LEFT JOIN sessions s ON s.session_id = d.session_id
        WHERE {' AND '.join(conditions)}
        ORDER BY s.date DESC, s.committee ASC, d.agenda_item ASC, d.title ASC
        LIMIT ?
        """,
        tuple(params),
    )
    return [_with_display_fields(result) for result in results]


def _with_display_fields(result: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(result)
    enriched["display_date"] = _format_german_date(str(enriched.get("date") or ""))
    enriched["display_type"] = (
        enriched.get("document_type")
        or enriched.get("category")
        or enriched.get("content_type")
        or "-"
    )
    return enriched


def _format_german_date(value: str) -> str:
    if not value:
        return ""
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return value


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
