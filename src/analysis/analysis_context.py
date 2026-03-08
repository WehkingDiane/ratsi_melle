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
            entry["page_texts"] = []
            entry["detected_sections"] = []
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
    mode: str,
    scope: str,
    selected_tops: list[str],
    documents: list[dict],
    prompt: str,
    uncertainty_flags: list[str] | None = None,
) -> str:
    """Render a markdown summary for the local analysis workflow."""

    top_text = "alle TOPs" if scope == "session" else ", ".join(selected_tops)
    doc_count = len(documents)
    headline = f"Analyse Sitzung {session.get('date')} - {session.get('committee') or '-'}"

    mode_title = _mode_title(mode)

    summary_lines = [
        f"# {headline}",
        "",
        f"- Modus: {mode}",
        f"- Scope: {scope}",
        f"- TOP-Auswahl: {top_text}",
        f"- Dokumente im Scope: {doc_count}",
        "",
        f"## {mode_title}",
        _mode_summary_text(mode),
    ]
    if uncertainty_flags:
        summary_lines.append("")
        summary_lines.append(f"- Unsicherheit: {', '.join(uncertainty_flags)}")

    field_keys = _mode_field_keys(mode)
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
            extracted_text = document.get("extracted_text")
            if isinstance(extracted_text, str) and extracted_text.strip():
                summary_lines.append(f"  - beleg_excerpt: {_truncate(extracted_text, 240)}")
            sections = document.get("detected_sections")
            if isinstance(sections, list) and sections:
                preview = []
                for section in sections[:3]:
                    if not isinstance(section, dict):
                        continue
                    heading = section.get("heading")
                    page = section.get("page")
                    if isinstance(heading, str) and heading.strip():
                        preview.append(f"{heading} (S. {page})")
                if preview:
                    summary_lines.append(f"  - abschnitte: {', '.join(preview)}")
            fields = document.get("structured_fields")
            if isinstance(fields, dict) and fields:
                for key in field_keys:
                    value = fields.get(key)
                    if isinstance(value, str) and value.strip():
                        summary_lines.append(f"  - {key}: {_truncate(value, 240)}")

        summary_lines.extend(["", "## Quellen"])
        for index, document in enumerate(documents, start=1):
            title = document.get("title") or "(ohne Titel)"
            url = document.get("url") or "-"
            local_path = document.get("resolved_local_path") or document.get("local_path") or "-"
            summary_lines.append(f"- [{index}] {title} | URL: {url} | Datei: {local_path}")

    summary_lines.extend(["", "## Prompt-Hinweis", prompt or "(kein Prompt gesetzt)"])
    return "\n".join(summary_lines)


def _mode_title(mode: str) -> str:
    mapping = {
        "summary": "Neutrale Kurzfassung",
        "decision_brief": "Beschlussorientierte Analyse",
        "financial_impact": "Finanzielle Bewertung",
        "journalistic_brief": "Journalistische Kurzfassung",
        "citizen_explainer": "Buergererklaerung",
        "topic_classifier": "Thematische Einordnung",
        "change_monitor": "Aenderungsmonitoring",
    }
    return mapping.get(mode, "Analysezusammenfassung")


def _mode_summary_text(mode: str) -> str:
    mapping = {
        "summary": "Neutrale, faktenbasierte Kurzbeschreibung mit Quellenhinweisen.",
        "decision_brief": "Fokus auf Beschluesse, Verantwortlichkeiten und naechste Schritte.",
        "financial_impact": "Fokus auf Kosten, Haushalt, Foerdermittel und finanzielle Risiken.",
        "journalistic_brief": "Verdichtung fuer redaktionelle Pruefung mit Konfliktlinien und offenen Fragen.",
        "citizen_explainer": "Leicht verstaendliche Einordnung fuer nicht-fachliches Publikum.",
        "topic_classifier": "Thematische Zuordnung der Inhalte zu Politikfeldern.",
        "change_monitor": "Vergleich mit frueheren Staenden und Hervorhebung relevanter Aenderungen.",
    }
    return mapping.get(mode, "Analyse auf Basis der verfuegbaren Dokumente.")


def _mode_field_keys(mode: str) -> tuple[str, ...]:
    if mode == "decision_brief":
        return ("beschlusstext", "entscheidung", "zustaendigkeit", "begruendung")
    if mode == "financial_impact":
        return ("finanzbezug", "begruendung", "entscheidung")
    if mode == "summary":
        return ("beschlusstext", "finanzbezug")
    return ("beschlusstext", "entscheidung", "begruendung", "finanzbezug", "zustaendigkeit")

def _truncate(value: str, max_chars: int) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "..."


def _as_text(value: object) -> str:
    return value if isinstance(value, str) else ""
