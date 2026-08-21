"""Build Qdrant payloads from local index document rows."""

from __future__ import annotations

from src.fetching.storage_layout import resolve_local_file_path


def resolve_local_path(doc: dict) -> str:
    """Return an absolute local document path for the payload when available."""
    resolved = resolve_local_file_path(
        session_path=str(doc.get("session_path") or ""),
        local_path=str(doc.get("local_path") or ""),
    )
    if resolved is None or not resolved.is_file():
        return ""
    return str(resolved.resolve())


def build_document_payload(doc: dict, *, search_text: str = "") -> dict:
    """Build the Qdrant payload for a document row."""
    return {
        "session_id": doc.get("session_id"),
        "title": doc.get("title") or "",
        "document_type": doc.get("document_type") or "",
        "agenda_item": doc.get("agenda_item") or "",
        "url": doc.get("url") or "",
        "local_path": resolve_local_path(doc),
        "date": doc.get("date") or "",
        "committee": doc.get("committee") or "",
        "snippet": _snippet(search_text),
    }


def _snippet(value: str, *, max_chars: int = 500) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= max_chars:
        return normalized
    shortened = normalized[: max_chars + 1].rsplit(" ", 1)[0].strip()
    return f"{shortened or normalized[:max_chars].strip()} …"
