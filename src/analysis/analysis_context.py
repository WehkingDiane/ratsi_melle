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
    plausibility_flags: list[str] | None = None,
    bias_metrics: dict[str, object] | None = None,
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
    if uncertainty_flags or plausibility_flags or bias_metrics:
        summary_lines.append("")
        summary_lines.append("## Qualitaetssignale")
    if uncertainty_flags:
        summary_lines.append(f"- Unsicherheit: {', '.join(uncertainty_flags)}")
    if plausibility_flags:
        summary_lines.append(f"- Plausibilitaet: {', '.join(plausibility_flags)}")
    if bias_metrics:
        balance = bias_metrics.get("source_balance", "-")
        evidence = bias_metrics.get("evidence_balance", "-")
        diversity = bias_metrics.get("document_type_diversity", "-")
        summary_lines.append(
            f"- Bias-Metriken: source_balance={balance}, evidence_balance={evidence}, "
            f"document_type_diversity={diversity}"
        )

    field_keys = _mode_field_keys(mode)
    if documents:
        session_sections = _build_session_sections(session, documents, mode)
        if session_sections:
            summary_lines.extend(["", "## Sitzungsanalyse", *session_sections])
        top_sections = _build_top_sections(documents, mode)
        if top_sections:
            summary_lines.extend(["", "## TOP-Analyse", *top_sections])
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
    if mode == "change_monitor":
        return ("entscheidung", "beschlusstext", "finanzbezug", "zustaendigkeit")
    if mode == "journalistic_brief":
        return ("entscheidung", "beschlusstext", "begruendung", "finanzbezug", "zustaendigkeit")
    if mode == "decision_brief":
        return ("beschlusstext", "entscheidung", "zustaendigkeit", "begruendung")
    if mode == "financial_impact":
        return ("finanzbezug", "begruendung", "entscheidung")
    if mode == "topic_classifier":
        return ("titel", "begruendung", "finanzbezug")
    if mode == "citizen_explainer":
        return ("beschlusstext", "begruendung", "finanzbezug")
    if mode == "summary":
        return ("beschlusstext", "finanzbezug")
    return ("beschlusstext", "entscheidung", "begruendung", "finanzbezug", "zustaendigkeit")


def _build_session_sections(session: dict, documents: list[dict], mode: str) -> list[str]:
    if mode not in {"journalistic_brief", "change_monitor"}:
        return []

    top_groups = _group_documents_by_top(documents)
    if not top_groups:
        return []

    lines = [
        f"- Sitzung: {session.get('meeting_name') or session.get('committee') or 'Unbekannt'}",
        f"- TOPs im Scope: {len(top_groups)}",
        f"- Dominante Themen: {', '.join(_infer_topics(documents) or ['keine klaren Themenschwerpunkte'])}",
    ]

    if mode == "change_monitor":
        changes = _session_change_signals(top_groups)
        lines.append(f"- Beobachtete Aenderungen: {', '.join(changes) if changes else 'keine markanten Aenderungen im Scope'}")
        follow_ups = _session_follow_ups(top_groups)
        if follow_ups:
            lines.append("- Beobachtungsbedarf:")
            for task in follow_ups[:3]:
                lines.append(f"  - {task}")
        return lines

    conflicts = _session_conflicts(top_groups)
    lines.append(f"- Konfliktlinien: {', '.join(conflicts) if conflicts else 'keine klaren Konfliktlinien erkannt'}")

    open_questions = _session_open_questions(top_groups)
    if open_questions:
        lines.append("- Offene Fragen:")
        for question in open_questions[:3]:
            lines.append(f"  - {question}")

    follow_ups = _session_follow_ups(top_groups)
    if follow_ups:
        lines.append("- Priorisierte Folgeaufgaben:")
        for task in follow_ups[:3]:
            lines.append(f"  - {task}")

    return lines


def _group_documents_by_top(documents: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for document in documents:
        top_number = str(document.get("agenda_item") or "-")
        grouped.setdefault(top_number, []).append(document)
    return grouped


def _build_top_sections(documents: list[dict], mode: str) -> list[str]:
    grouped = _group_documents_by_top(documents)
    if not grouped:
        return []

    lines: list[str] = []
    for top_number, top_documents in sorted(grouped.items()):
        agenda_title = _top_title(top_documents)
        lines.append(f"### {top_number} - {agenda_title}")
        lines.append(f"- Dokumente: {len(top_documents)}")
        lines.append(f"- Dokumenttypen: {', '.join(sorted({_doc_type(doc) for doc in top_documents}))}")
        inconsistencies = _top_inconsistencies(top_documents)
        lines.append(
            f"- Inkonsistenzen: {', '.join(inconsistencies) if inconsistencies else 'keine auffaelligen Widersprueche'}"
        )

        topics = _infer_topics(top_documents)
        if topics:
            lines.append(f"- Themenhinweise: {', '.join(topics)}")

        if mode == "citizen_explainer":
            lines.append(f"- Kurz erklaert: {_build_citizen_note(top_documents, agenda_title)}")
        elif mode == "change_monitor":
            lines.extend([f"- {entry}" for entry in _build_change_monitor_note(top_documents, agenda_title)])
        elif mode == "journalistic_brief":
            brief = _build_journalistic_brief(top_documents, agenda_title)
            lines.extend([f"- {entry}" for entry in brief])
        elif mode == "topic_classifier":
            lines.append(f"- Themenklassifikation: {', '.join(topics or ['allgemeine Verwaltung'])}")
        else:
            summary_bits = _top_summary_bits(top_documents, mode)
            if summary_bits:
                lines.append(f"- Kernaussagen: {' | '.join(summary_bits)}")
        lines.append("")
    if lines and not lines[-1]:
        lines.pop()
    return lines


def _top_title(documents: list[dict]) -> str:
    for document in documents:
        agenda_title = document.get("agenda_title")
        if isinstance(agenda_title, str) and agenda_title.strip():
            return agenda_title.strip()
    for document in documents:
        title = document.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
    return "(ohne TOP-Titel)"


def _doc_type(document: dict) -> str:
    return str(document.get("document_type") or "unbekannt")


def _top_inconsistencies(documents: list[dict]) -> list[str]:
    inconsistencies: list[str] = []
    if len(_distinct_field_values(documents, "entscheidung", "beschlusstext")) > 1:
        inconsistencies.append("abweichende Beschlusssignale")
    if len(_distinct_field_values(documents, "finanzbezug")) > 1:
        inconsistencies.append("abweichende Finanzangaben")
    if len(_distinct_field_values(documents, "zustaendigkeit")) > 1:
        inconsistencies.append("abweichende Zustaendigkeiten")
    return inconsistencies


def _top_summary_bits(documents: list[dict], mode: str) -> list[str]:
    fields = _mode_field_keys(mode)
    values: list[str] = []
    for key in fields:
        for value in _distinct_field_values(documents, key):
            values.append(f"{key}: {_truncate(value, 140)}")
            if len(values) >= 3:
                return values
    return values


def _distinct_field_values(documents: list[dict], key: str, *extra_keys: str) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for document in documents:
        fields = document.get("structured_fields")
        if not isinstance(fields, dict):
            continue
        for field_key in (key, *extra_keys):
            value = fields.get(field_key)
            if isinstance(value, str) and value.strip():
                normalized = " ".join(value.split())
                if normalized not in seen:
                    seen.add(normalized)
                    values.append(normalized)
    return values


def _infer_topics(documents: list[dict]) -> list[str]:
    text_parts: list[str] = []
    for document in documents:
        text_parts.extend(
            [
                str(document.get("agenda_title") or ""),
                str(document.get("title") or ""),
                str(document.get("extracted_text") or ""),
            ]
        )
        fields = document.get("structured_fields")
        if isinstance(fields, dict):
            text_parts.append(" ".join(str(value) for value in fields.values() if isinstance(value, str)))
    text = " ".join(text_parts).lower()
    topic_keywords = {
        "Finanzen": ("haushalt", "finanz", "eur", "kosten", "foerder"),
        "Verkehr": ("verkehr", "strasse", "mobil", "park", "radweg"),
        "Bildung": ("schule", "kita", "bildung", "schueler"),
        "Soziales": ("sozial", "jugend", "famil", "wohnen", "pflege"),
        "Umwelt": ("klima", "umwelt", "energie", "gruen", "solar"),
    }
    matches = [topic for topic, keywords in topic_keywords.items() if any(keyword in text for keyword in keywords)]
    return matches[:3]


def _build_citizen_note(documents: list[dict], agenda_title: str) -> str:
    doc_count = len(documents)
    topics = _infer_topics(documents)
    topic_text = f" Themen: {', '.join(topics)}." if topics else ""
    return f"Zu diesem TOP liegen {doc_count} Dokumente vor. Thema: {agenda_title}.{topic_text}".strip()


def _build_journalistic_brief(documents: list[dict], agenda_title: str) -> list[str]:
    summary_bits = _top_summary_bits(documents, "journalistic_brief")
    inconsistencies = _top_inconsistencies(documents)
    topics = _infer_topics(documents)
    lines = [
        f"Redaktioneller Fokus: {agenda_title}",
        f"Kernaussagen: {' | '.join(summary_bits) if summary_bits else 'noch keine belastbaren Kernaussagen'}",
        f"Konfliktpunkte: {', '.join(inconsistencies) if inconsistencies else 'keine klaren Konfliktpunkte'}",
    ]
    if topics:
        lines.append(f"Themenlage: {', '.join(topics)}")
    if _top_needs_follow_up(documents):
        lines.append("Offene Punkte: weitere Verifikation oder politische Einordnung sinnvoll")
    return lines


def _build_change_monitor_note(documents: list[dict], agenda_title: str) -> list[str]:
    change_signals = _top_change_signals(documents)
    doc_titles = sorted({str(document.get("title") or "(ohne Titel)") for document in documents})
    lines = [
        f"Monitoring-Fokus: {agenda_title}",
        f"Dokumentvarianten: {', '.join(doc_titles[:3])}",
        f"Aenderungssignale: {', '.join(change_signals) if change_signals else 'keine klaren Feldabweichungen'}",
    ]
    if _top_needs_follow_up(documents):
        lines.append("Beobachtung: weitere Versionen oder Beschlussstaende pruefen")
    return lines


def _session_conflicts(top_groups: dict[str, list[dict]]) -> list[str]:
    conflicts: list[str] = []
    for top_number, documents in sorted(top_groups.items()):
        inconsistencies = _top_inconsistencies(documents)
        if inconsistencies:
            conflicts.append(f"{top_number}: {', '.join(inconsistencies)}")
    return conflicts


def _session_open_questions(top_groups: dict[str, list[dict]]) -> list[str]:
    questions: list[str] = []
    for top_number, documents in sorted(top_groups.items()):
        title = _top_title(documents)
        if _top_needs_follow_up(documents):
            questions.append(f"{top_number} ({title}): Welche Fakten oder Entscheidungen muessen noch abgesichert werden?")
    return questions


def _session_follow_ups(top_groups: dict[str, list[dict]]) -> list[str]:
    follow_ups: list[str] = []
    for top_number, documents in sorted(top_groups.items()):
        title = _top_title(documents)
        fields = _distinct_field_values(documents, "zustaendigkeit")
        if fields:
            follow_ups.append(f"{top_number} ({title}): Rueckfrage bei {fields[0]} zu naechsten Schritten.")
        elif _top_needs_follow_up(documents):
            follow_ups.append(f"{top_number} ({title}): politische Bewertung und Quellenlage nachrecherchieren.")
    return follow_ups


def _session_change_signals(top_groups: dict[str, list[dict]]) -> list[str]:
    changes: list[str] = []
    for top_number, documents in sorted(top_groups.items()):
        signals = _top_change_signals(documents)
        if signals:
            changes.append(f"{top_number}: {', '.join(signals)}")
    return changes


def _top_needs_follow_up(documents: list[dict]) -> bool:
    if _top_inconsistencies(documents) or _top_change_signals(documents):
        return True
    for document in documents:
        extraction_status = str(document.get("extraction_status") or "")
        parser_quality = str(document.get("content_parser_quality") or "")
        if extraction_status in {"missing_file", "ocr_needed", "error"} or parser_quality in {"failed", "low"}:
            return True
    return False


def _top_change_signals(documents: list[dict]) -> list[str]:
    signals: list[str] = []
    if len({_doc_type(document) for document in documents}) > 1:
        signals.append("mehrere Dokumenttypen")
    if len(_distinct_field_values(documents, "beschlusstext", "entscheidung")) > 1:
        signals.append("veraenderter Beschlussstand")
    if len(_distinct_field_values(documents, "finanzbezug")) > 1:
        signals.append("veraenderter Finanzbezug")
    if len(_distinct_field_values(documents, "zustaendigkeit")) > 1:
        signals.append("veraenderte Zustaendigkeit")
    return signals


def _truncate(value: str, max_chars: int) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "..."


def _as_text(value: object) -> str:
    return value if isinstance(value, str) else ""
