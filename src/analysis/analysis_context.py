"""Helpers for building analysis-ready document context."""

from __future__ import annotations

import unicodedata
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

    if documents:
        session_sections = _build_session_sections(session, documents, mode)
        if session_sections:
            summary_lines.extend(["", "## Sitzungsueberblick", *session_sections])
        top_sections = _build_top_sections(documents, mode)
        if top_sections:
            summary_lines.extend(["", "## TOP-Analyse", *top_sections])
        summary_lines.extend(["", "## Kurzquellen"])
        for line in _build_source_preview(documents):
            summary_lines.append(line)

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
        "citizen_explainer": "Buergererklaerung",
        "topic_classifier": "Thematische Einordnung",
    }
    return mapping.get(mode, "Analysezusammenfassung")


def _mode_summary_text(mode: str) -> str:
    mapping = {
        "summary": "Lokale, titelbasierte Kurzsichtung ohne Detailanalyse des Dokumentinhalts.",
        "citizen_explainer": "Leicht verstaendliche, titelbasierte Einordnung fuer nicht-fachliches Publikum.",
        "topic_classifier": "Titelbasierte thematische Zuordnung der Dokumente und TOPs.",
    }
    return mapping.get(mode, "Analyse auf Basis der verfuegbaren Dokumente.")


def _mode_field_keys(mode: str) -> tuple[str, ...]:
    return ()


def _build_session_sections(session: dict, documents: list[dict], mode: str) -> list[str]:
    if mode not in {"summary", "citizen_explainer", "topic_classifier"}:
        return []

    top_groups = _group_documents_by_top(documents)
    if not top_groups:
        return []

    lines = [
        f"- Sitzung: {session.get('meeting_name') or session.get('committee') or 'Unbekannt'}",
        f"- TOPs im Scope: {len(top_groups)}",
        f"- Dokumente im Scope: {len(documents)}",
        f"- Dominante Titelthemen: {', '.join(_infer_topics(documents) or ['keine klaren Themenschwerpunkte'])}",
    ]
    lines.append("- Hinweis: lokale Analyse nutzt nur TOP- und Dokumenttitel, keine inhaltliche PDF-Auswertung.")
    if mode == "citizen_explainer":
        lines.append("- Lesart: vereinfachte Orientierung aus Titeln und Dokumenttypen.")
    if mode == "topic_classifier":
        lines.append(
            f"- Titelbasierte Themenklassifikation: {', '.join(_infer_topics(documents) or ['allgemeine Verwaltung'])}"
        )
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
        lines.append(f"- Relevante Titel: {', '.join(_top_document_titles(top_documents)[:3])}")
        topics = _infer_topics(top_documents)
        if topics:
            lines.append(f"- Themenhinweise: {', '.join(topics)}")

        if mode == "citizen_explainer":
            lines.append(f"- Kurz erklaert: {_build_citizen_note(top_documents, agenda_title)}")
        elif mode == "topic_classifier":
            lines.append(f"- Themenklassifikation: {', '.join(topics or ['allgemeine Verwaltung'])}")
        else:
            lines.append(f"- Kurzhinweis: {_build_summary_note(top_documents, agenda_title)}")
        lines.append("")
    if lines and not lines[-1]:
        lines.pop()
    return lines


def _build_source_preview(documents: list[dict]) -> list[str]:
    lines: list[str] = []
    for top_number, top_documents in sorted(_group_documents_by_top(documents).items()):
        titles = _top_document_titles(top_documents)
        if not titles:
            continue
        lines.append(f"- {top_number}: {', '.join(titles[:3])}")
    return lines[:8]


def _top_document_titles(documents: list[dict]) -> list[str]:
    titles: list[str] = []
    seen: set[str] = set()
    for document in documents:
        title = document.get("title")
        if isinstance(title, str) and title.strip():
            normalized = " ".join(title.split())
            if normalized not in seen:
                seen.add(normalized)
                titles.append(normalized)
    return titles


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
    return []


def _top_summary_bits(documents: list[dict], mode: str) -> list[str]:
    values: list[str] = []
    for value in _distinct_title_values(documents):
        values.append(f"titel: {_truncate(value, 140)}")
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
            ]
        )
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


def _distinct_title_values(documents: list[dict]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for document in documents:
        for key in ("agenda_title", "title"):
            value = document.get(key)
            if isinstance(value, str) and value.strip():
                normalized = " ".join(value.split())
                if normalized not in seen:
                    seen.add(normalized)
                    values.append(normalized)
    return values


def _build_summary_note(documents: list[dict], agenda_title: str) -> str:
    doc_types = ", ".join(sorted({_doc_type(doc) for doc in documents}))
    return f"{agenda_title}. Dokumentmix: {doc_types}. Nur titelbasierte lokale Sichtung."


def _build_citizen_note(documents: list[dict], agenda_title: str) -> str:
    doc_count = len(documents)
    topics = _infer_topics(documents)
    topic_text = f" Themen: {', '.join(topics)}." if topics else ""
    return f"Zu diesem TOP liegen {doc_count} Dokumente vor. Thema laut Titeln: {agenda_title}.{topic_text}".strip()


def _build_excerpt_line(document: dict) -> str | None:
    extracted_text = document.get("extracted_text")
    if not isinstance(extracted_text, str):
        return None

    cleaned = _truncate(extracted_text, 240)
    if _is_readable_excerpt(cleaned):
        return f"  - beleg_excerpt: {cleaned}"

    parser_quality = str(document.get("content_parser_quality") or "n/a")
    extraction_status = str(document.get("extraction_status") or "n/a")
    return (
        "  - beleg_excerpt: (unterdrueckt, Textqualitaet unzureichend "
        f"bei Extraktion={extraction_status}, Parser={parser_quality})"
    )


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


def _top_historical_lines(documents: list[dict]) -> list[str]:
    lines: list[str] = []
    for document in documents:
        reference = document.get("historical_reference")
        signals = document.get("historical_change_signals")
        if not isinstance(reference, dict) or not reference:
            continue
        title = str(document.get("title") or "(ohne Titel)")
        previous_date = str(reference.get("date") or "?")
        previous_session = str(reference.get("meeting_name") or reference.get("session_id") or "?")
        signal_text = ", ".join(signals) if isinstance(signals, list) and signals else "keine Feldabweichungen"
        lines.append(f"Vorversion {title}: {previous_date} ({previous_session}) | Signale: {signal_text}")
    return lines[:3]


def _is_readable_excerpt(text: str) -> bool:
    if not text.strip():
        return False

    normalized = " ".join(text.split())
    if len(normalized) < 40:
        return True

    control_chars = sum(1 for char in normalized if unicodedata.category(char).startswith("C"))
    if control_chars:
        return False

    allowed_punctuation = set(".,;:!?()[]%/-+\"'")
    unusual_chars = sum(
        1
        for char in normalized
        if not (char.isalnum() or char.isspace() or char in allowed_punctuation or char in "äöüÄÖÜß")
    )
    unusual_ratio = unusual_chars / len(normalized)

    words = [word for word in normalized.split() if word]
    vowel_words = [
        word for word in words
        if any(vowel in word.lower() for vowel in ("a", "e", "i", "o", "u", "ä", "ö", "ü"))
    ]
    vowel_ratio = len(vowel_words) / len(words) if words else 0.0

    alpha_chars = sum(1 for char in normalized if char.isalpha())
    alpha_ratio = alpha_chars / len(normalized)

    return unusual_ratio < 0.12 and vowel_ratio >= 0.6 and alpha_ratio >= 0.45


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
    if any(isinstance(document.get("historical_change_signals"), list) and document.get("historical_change_signals") for document in documents):
        signals.append("historische Vorversion vorhanden")
    return signals


def _truncate(value: str, max_chars: int) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "..."


def _as_text(value: object) -> str:
    return value if isinstance(value, str) else ""
