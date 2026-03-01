"""Helpers for building analysis-ready document context."""

from __future__ import annotations

from pathlib import Path

from src.analysis.extraction_pipeline import extract_text_for_analysis
from src.fetching.storage_layout import resolve_local_file_path
from src.parsing.document_content import parse_document_content


def enrich_documents_for_analysis(documents: list[dict], *, max_text_chars: int = 4000) -> list[dict]:
    """Attach extraction and structured content metadata to analysis documents."""

    enriched: list[dict] = []
    for document in documents:
        entry = dict(document)
        resolved_path = resolve_local_file_path(
            session_path=_as_text(entry.get("session_path")),
            local_path=_as_text(entry.get("local_path")),
        )
        entry["resolved_local_path"] = str(resolved_path) if resolved_path else None

        if resolved_path is None:
            entry["structured_fields"] = {}
            entry["content_parser_status"] = "missing_file"
            entry["content_parser_quality"] = "failed"
            entry["extraction_status"] = "missing_file"
            enriched.append(entry)
            continue

        extraction = extract_text_for_analysis(
            resolved_path,
            content_type=_as_text(entry.get("content_type")),
            max_text_chars=max_text_chars,
        )
        entry.update(extraction.to_dict())

        parsed = parse_document_content(
            document_type=_as_text(entry.get("document_type")),
            text=extraction.extracted_text,
            title=_as_text(entry.get("title")),
        )
        entry.update(parsed.to_dict())
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
    """Render a markdown summary for the local analysis workflow."""

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
        "## Journalistische Kurzfassung",
        "Die Sitzung enthielt mehrere politische Beratungen. "
        "Die unten aufgefuehrten Dokumentfelder markieren inhaltliche Anker fuer weitere redaktionelle Pruefung.",
    ]

    if documents:
        summary_lines.extend(["", "## Dokumentkontext"])
        for document in documents:
            title = document.get("title") or "(ohne Titel)"
            doc_type = document.get("document_type") or "unbekannt"
            top_number = document.get("agenda_item") or "-"
            parser_quality = document.get("content_parser_quality") or "n/a"
            extraction_status = document.get("extraction_status") or "n/a"
            summary_lines.append(
                f"- {top_number} | {doc_type} | {title} | Extraktion: {extraction_status} | Parser: {parser_quality}"
            )
            fields = document.get("structured_fields")
            if isinstance(fields, dict) and fields:
                for key in ("beschlusstext", "entscheidung", "begruendung", "finanzbezug", "zustaendigkeit"):
                    value = fields.get(key)
                    if isinstance(value, str) and value.strip():
                        summary_lines.append(f"  - {key}: {_truncate(value, 240)}")

    summary_lines.extend(["", "## Prompt-Hinweis", prompt or "(kein Prompt gesetzt)"])
    return "\n".join(summary_lines)

def _truncate(value: str, max_chars: int) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "..."


def _as_text(value: object) -> str:
    return value if isinstance(value, str) else ""
