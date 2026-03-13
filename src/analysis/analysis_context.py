"""Helpers for building analysis-ready document context."""

from __future__ import annotations

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
        entry["resolved_local_path"] = str(resolved_path) if resolved_path else None
        entry["source_file_available"] = resolved_path is not None
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

    summary_lines = [
        f"# {headline}",
        "",
        f"- Scope: {scope}",
        f"- TOP-Auswahl: {top_text}",
        f"- Dokumente im Scope: {doc_count}",
        "",
        "## Analysehinweis",
        "Dies ist nur eine lokal erzeugte Analysegrundlage. "
        "Die eigentliche Inhaltsanalyse soll ueber einen KI-Provider pro TOP erfolgen.",
    ]

    if documents:
        summary_lines.extend(["", "## Quellen im Scope"])
        for document in documents:
            title = document.get("title") or "(ohne Titel)"
            doc_type = document.get("document_type") or "unbekannt"
            top_number = document.get("agenda_item") or "-"
            source_file = "ja" if document.get("source_file_available") else "nein"
            resolved_path = document.get("resolved_local_path") or "-"
            url = document.get("url") or "-"
            summary_lines.append(
                f"- {top_number} | {doc_type} | {title} | lokale Quelle: {source_file}"
            )
            summary_lines.append(f"  - pfad: {resolved_path}")
            summary_lines.append(f"  - url: {url}")

    summary_lines.extend(["", "## Prompt-Hinweis", prompt or "(kein Prompt gesetzt)"])
    return "\n".join(summary_lines)


def _as_text(value: object) -> str:
    return value if isinstance(value, str) else ""
