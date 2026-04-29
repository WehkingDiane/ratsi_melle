"""Helpers for building analysis-ready document context."""

from __future__ import annotations

from datetime import date
from datetime import datetime
from pathlib import Path

from src.fetching.storage_layout import resolve_local_file_path


def enrich_documents_for_analysis(documents: list[dict]) -> list[dict]:
    """Attach source path metadata without performing local document analysis."""

    enriched: list[dict] = []
    for document in documents:
        entry = dict(document)
        resolved_path = resolve_local_file_path(
            session_path=_as_text(entry.get("session_path")),
            local_path=_as_text(entry.get("local_path")),
        )
        existing_path = _existing_file_path(resolved_path)
        entry["resolved_local_path"] = str(resolved_path) if resolved_path else None
        entry["source_file_available"] = existing_path is not None
        entry["analysis_transfer_mode"] = _transfer_mode(existing_path)
        entry["analysis_text_excerpt"] = _read_text_excerpt(existing_path)
        enriched.append(entry)
    return enriched


def build_analysis_markdown(
    *,
    session: dict,
    scope: str,
    selected_tops: list[str],
    documents: list[dict],
    prompt: str,
) -> str:
    """Render a markdown summary for the KI-oriented analysis workflow."""

    top_text = "alle TOPs" if scope == "session" else ", ".join(selected_tops)
    doc_count = len(documents)
    headline = f"Analyse Sitzung {session.get('date')} - {session.get('committee') or '-'}"
    session_state = _session_state(_as_text(session.get("date")))

    summary_lines = [
        f"# {headline}",
        "",
        "## Sitzungskontext",
        f"- Sitzung: {session_state}",
        f"- Datum: {session.get('date') or '-'}",
        f"- Gremium: {session.get('committee') or '-'}",
        f"- Sitzungsname: {session.get('meeting_name') or '-'}",
        "",
        f"- Scope: {scope}",
        f"- TOP-Auswahl: {top_text}",
        f"- Dokumente im Scope: {doc_count}",
        "",
        "## Analysehinweis",
        "Dies ist nur eine lokal erzeugte Analysegrundlage. "
        "Die eigentliche Inhaltsanalyse soll über einen KI-Provider pro TOP erfolgen.",
    ]

    agenda_items = _agenda_items_in_scope(session, scope, selected_tops)
    if agenda_items:
        summary_lines.extend(["", "## TOP- und Abstimmungsinformationen"])
        for item in agenda_items:
            number = item.get("number") or "TOP"
            title = item.get("title") or "(ohne Titel)"
            status = item.get("status") or "-"
            decision = item.get("decision") or "-"
            summary_lines.append(f"- {number}: {title}")
            summary_lines.append(f"  - Status: {status}")
            summary_lines.append(f"  - Beschluss/Abstimmung: {decision}")

    if documents:
        summary_lines.extend(["", "## Quellen im Scope"])
        for document in documents:
            title = document.get("title") or "(ohne Titel)"
            doc_type = document.get("document_type") or "unbekannt"
            top_number = document.get("agenda_item") or "-"
            source_file = "ja" if document.get("source_file_available") else "nein"
            transfer_mode = document.get("analysis_transfer_mode") or "metadata_only"
            resolved_path = document.get("resolved_local_path") or "-"
            url = document.get("url") or "-"
            summary_lines.append(
                f"- {top_number} | {doc_type} | {title} | lokale Quelle: {source_file} | KI-Übergabe: {transfer_mode}"
            )
            summary_lines.append(f"  - pfad: {resolved_path}")
            summary_lines.append(f"  - url: {url}")
            excerpt = document.get("analysis_text_excerpt") or ""
            if excerpt:
                summary_lines.append("  - Textauszug:")
                for line in str(excerpt).splitlines():
                    summary_lines.append(f"    {line}")

    summary_lines.extend(["", "## Prompt-Hinweis", prompt or "(kein Prompt gesetzt)"])
    return "\n".join(summary_lines)


def _as_text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _existing_file_path(path: Path | None) -> Path | None:
    if path is None:
        return None
    return path if path.is_file() else None


def _transfer_mode(path: Path | None) -> str:
    if path is None:
        return "metadata_only"
    if path.suffix.lower() == ".pdf":
        return "pdf_attachment"
    if path.suffix.lower() in {".txt", ".md", ".markdown", ".html", ".htm"}:
        return "text_excerpt"
    return "metadata_only"


def _read_text_excerpt(path: Path | None, max_chars: int = 12000) -> str:
    if path is None or path.suffix.lower() not in {".txt", ".md", ".markdown", ".html", ".htm"}:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars].strip()
    except OSError:
        return ""


def _session_state(date_value: str) -> str:
    if not date_value:
        return "Datum unbekannt"
    try:
        session_date = datetime.strptime(date_value[:10], "%Y-%m-%d").date()
    except ValueError:
        return "Datum nicht auswertbar"
    if session_date < date.today():
        return "vergangene Sitzung"
    if session_date > date.today():
        return "zukünftige Sitzung"
    return "heutige Sitzung"


def _agenda_items_in_scope(session: dict, scope: str, selected_tops: list[str]) -> list[dict]:
    items = session.get("agenda_items") or []
    if not isinstance(items, list):
        return []
    if scope == "tops":
        selected = {str(top) for top in selected_tops}
        return [item for item in items if str(item.get("number") or "") in selected]
    return items
