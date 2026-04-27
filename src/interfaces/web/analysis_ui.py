"""UI-facing helpers for the Streamlit analysis workflow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.analysis.schemas import DEFAULT_ANALYSIS_PURPOSE, normalize_analysis_output
from src.fetching.storage_layout import resolve_local_file_path
from src.paths import ANALYSIS_OUTPUTS_DIR

PURPOSE_LABELS: list[tuple[str, str]] = [
    ("Journalistische Veroeffentlichung", "journalistic_publication"),
    ("Sitzungsvorbereitung", "session_preparation"),
    ("Inhaltliche Analyse", "content_analysis"),
    ("Faktenextraktion", "fact_extraction"),
]

PURPOSE_LABEL_TO_KEY = dict(PURPOSE_LABELS)
PURPOSE_KEY_TO_LABEL = {value: label for label, value in PURPOSE_LABELS}

ANALYSIS_MODE_LABELS: list[tuple[str, str]] = [
    ("Nur strukturierte Analyse", "structured_only"),
    ("Strukturierte Analyse + Publikationsentwurf", "structured_and_publication"),
    ("Nur Publikationsentwurf aus vorhandener Struktur", "publication_only"),
]
ANALYSIS_MODE_LABEL_TO_KEY = dict(ANALYSIS_MODE_LABELS)
ANALYSIS_MODE_KEY_TO_LABEL = {value: label for label, value in ANALYSIS_MODE_LABELS}

PURPOSE_TEMPLATE_SUGGESTIONS = {
    "journalistic_publication": [
        "structured_fact_extraction",
        "journalistic_publication_draft",
    ],
    "session_preparation": ["meeting_preparation_briefing"],
    "content_analysis": ["structured_content_analysis"],
    "fact_extraction": ["structured_fact_extraction"],
}

PURPOSE_ALLOWED_OUTPUT_TYPES = {
    "journalistic_publication": [
        "raw_analysis",
        "structured_analysis",
        "journalistic_article",
        "publication_draft",
    ],
    "session_preparation": [
        "raw_analysis",
        "structured_analysis",
        "meeting_briefing",
    ],
    "content_analysis": [
        "raw_analysis",
        "structured_analysis",
        "journalistic_article",
    ],
    "fact_extraction": [
        "raw_analysis",
        "structured_analysis",
    ],
}

REVIEW_STATUSES = {"pending", "needs_changes", "approved", "rejected"}
PUBLICATION_STATUSES = {
    "not_published",
    "draft_created",
    "scheduled",
    "published",
    "failed",
}


def get_purpose_options() -> list[str]:
    return [label for label, _ in PURPOSE_LABELS]


def get_analysis_mode_options() -> list[str]:
    return [label for label, _ in ANALYSIS_MODE_LABELS]


def map_purpose_label_to_key(label: str) -> str:
    return PURPOSE_LABEL_TO_KEY.get(label, DEFAULT_ANALYSIS_PURPOSE)


def map_analysis_mode_label_to_key(label: str) -> str:
    return ANALYSIS_MODE_LABEL_TO_KEY.get(label, "structured_only")


def get_suggested_template_ids(purpose: str) -> list[str]:
    return list(PURPOSE_TEMPLATE_SUGGESTIONS.get(purpose, ["structured_content_analysis"]))


def get_allowed_output_types(purpose: str) -> list[str]:
    return list(PURPOSE_ALLOWED_OUTPUT_TYPES.get(purpose, PURPOSE_ALLOWED_OUTPUT_TYPES[DEFAULT_ANALYSIS_PURPOSE]))


def ensure_required_templates(templates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing_ids = {str(template.get("id") or "") for template in templates}
    result = [dict(template) for template in templates]
    placeholders = [
        {
            "id": "structured_fact_extraction",
            "label": "Strukturierte Faktenextraktion",
            "scope": ["tops", "session"],
            "text": (
                "Erstelle eine strukturierte Faktenextraktion fuer die ausgewaehlten Quellen. "
                "Nenne Kernaussagen, Entscheidungen, Kosten, betroffene Gruppen, offene Fragen "
                "und Unsicherheiten in klar getrennten Abschnitten."
            ),
        },
        {
            "id": "journalistic_publication_draft",
            "label": "Journalistischer Publikationsentwurf",
            "scope": ["tops", "session"],
            "text": (
                "Erzeuge auf Basis der strukturierten Analyse einen journalistischen Entwurf "
                "mit Titel, Kurzfassung, Langfassung, moeglichen Hashtags und SEO-Begriffen. "
                "Trenne belegte Fakten klar von Unsicherheiten."
            ),
        },
        {
            "id": "meeting_preparation_briefing",
            "label": "Sitzungsvorbereitung",
            "scope": ["tops", "session"],
            "text": (
                "Erstelle ein kompaktes Briefing fuer die Sitzungsvorbereitung. "
                "Fasse Themen, erwartbare Entscheidungen, finanzielle Auswirkungen, "
                "kritische Nachfragen und offene Punkte strukturiert zusammen."
            ),
        },
        {
            "id": "structured_content_analysis",
            "label": "Strukturierte Inhaltsanalyse",
            "scope": ["tops", "session"],
            "text": (
                "Analysiere die Inhalte strukturiert nach Themen, Kategorien, betroffenen "
                "Ortsteilen, Entscheidungen, Relevanz fuer Buergerinnen und Buerger sowie "
                "Unsicherheiten."
            ),
        },
    ]
    for placeholder in placeholders:
        if placeholder["id"] not in existing_ids:
            result.append(placeholder)
    return result


def select_default_template_id(templates: list[dict[str, Any]], purpose: str) -> str | None:
    available_ids = {str(template.get("id") or "") for template in templates}
    for template_id in get_suggested_template_ids(purpose):
        if template_id in available_ids:
            return template_id
    if templates:
        return str(templates[0].get("id") or "") or None
    return None


def build_source_check(documents: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    local_count = 0
    missing_local_count = 0
    url_count = 0
    missing_url_count = 0
    pdf_count = 0
    missing_pdf_count = 0
    document_types: set[str] = set()
    warnings: list[str] = []

    for document in documents:
        resolved_local = resolve_local_file_path(
            session_path=str(document.get("session_path") or ""),
            local_path=str(document.get("local_path") or ""),
        )
        local_exists = bool(resolved_local and resolved_local.is_file())
        url = str(document.get("url") or "")
        document_type = str(document.get("document_type") or "") or "-"
        content_type = str(document.get("content_type") or "")
        has_pdf = content_type == "application/pdf" or str(document.get("local_path") or "").lower().endswith(".pdf")
        source_status = "ok"
        if not local_exists or not url:
            source_status = "warning"
        if local_exists:
            local_count += 1
        else:
            missing_local_count += 1
        if url:
            url_count += 1
        else:
            missing_url_count += 1
        if has_pdf:
            if local_exists or url:
                pdf_count += 1
            else:
                missing_pdf_count += 1
        document_types.add(document_type)
        rows.append(
            {
                "top": str(document.get("agenda_item") or ""),
                "title": str(document.get("title") or ""),
                "document_type": document_type,
                "content_type": content_type,
                "local_path": str(resolved_local or document.get("local_path") or ""),
                "local_exists": local_exists,
                "url": url,
                "pdf_available": bool(has_pdf and (local_exists or url)),
                "source_status": source_status,
            }
        )

    if local_count:
        warnings.append(f"{local_count} lokale Datei(en) vorhanden")
    if missing_local_count:
        warnings.append(f"{missing_local_count} Dokument(e) ohne lokale Datei")
    if url_count:
        warnings.append(f"{url_count} Dokument(e) mit URL")
    if missing_url_count:
        warnings.append(f"{missing_url_count} Dokument(e) ohne URL")
    if missing_pdf_count:
        warnings.append(f"{missing_pdf_count} PDF-Quelle(n) ohne Datei oder URL")

    return {
        "document_count": len(documents),
        "document_types": sorted(document_types),
        "local_available_count": local_count,
        "local_missing_count": missing_local_count,
        "url_available_count": url_count,
        "url_missing_count": missing_url_count,
        "pdf_available_count": pdf_count,
        "pdf_missing_count": missing_pdf_count,
        "rows": rows,
        "messages": warnings,
        "has_warnings": any(row["source_status"] != "ok" for row in rows),
    }


def normalize_analysis_for_ui(data: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_analysis_output(data)
    output_type = str(normalized.get("output_type") or "")
    structured = {
        "topic": {"title": "", "category": [], "location": []},
        "facts": [],
        "decisions": [],
        "financial_effects": [],
        "affected_groups": [],
        "citizen_relevance": {"score": 0.0, "reasons": []},
        "open_questions": [],
        "risks_or_uncertainties": [],
    }
    publication = {
        "title": "",
        "summary_short": "",
        "summary_long": "",
        "body_markdown": str(normalized.get("markdown") or ""),
        "hashtags": [],
        "seo_keywords": [],
        "slug": "",
        "status": "draft",
        "review": {
            "required": False,
            "status": "pending",
            "notes": "",
            "reviewed_at": "",
            "reviewed_by": "",
        },
        "publication": {
            "target": "local_static_site",
            "status": "not_published",
            "published_url": "",
            "published_at": "",
        },
    }
    sources = {"documents": []}
    legacy_notice = ""

    if output_type == "legacy_analysis_output":
        legacy_notice = (
            "Diese Analyse stammt aus dem alten Ausgabeformat. "
            "Strukturierte Felder sind nur eingeschraenkt verfuegbar."
        )
    elif output_type == "structured_analysis":
        structured.update(
            {
                "topic": dict(normalized.get("topic") or structured["topic"]),
                "facts": list(normalized.get("facts") or []),
                "decisions": list(normalized.get("decisions") or []),
                "financial_effects": list(normalized.get("financial_effects") or []),
                "affected_groups": list(normalized.get("affected_groups") or []),
                "citizen_relevance": dict(normalized.get("citizen_relevance") or structured["citizen_relevance"]),
                "open_questions": list(normalized.get("open_questions") or []),
                "risks_or_uncertainties": list(normalized.get("risks_or_uncertainties") or []),
            }
        )
    elif output_type == "publication_draft":
        publication.update(
            {
                "title": str(normalized.get("title") or ""),
                "summary_short": str(normalized.get("summary_short") or ""),
                "summary_long": str(normalized.get("summary_long") or ""),
                "body_markdown": str(normalized.get("body_markdown") or ""),
                "hashtags": list(normalized.get("hashtags") or []),
                "seo_keywords": list(normalized.get("seo_keywords") or []),
                "slug": str(normalized.get("slug") or ""),
                "status": str(normalized.get("status") or "draft"),
                "review": dict(normalized.get("review") or publication["review"]),
                "publication": dict(normalized.get("publication") or publication["publication"]),
            }
        )
    elif output_type == "raw_analysis":
        sources["documents"] = list(normalized.get("documents") or [])

    normalized["structured"] = structured
    normalized["publication_draft"] = publication
    normalized["sources"] = sources
    normalized["legacy_notice"] = legacy_notice
    return normalized


def validate_review_status(status: str) -> str:
    if status not in REVIEW_STATUSES:
        raise ValueError(f"Ungueltiger Review-Status: {status}")
    return status


def validate_publication_status(status: str) -> str:
    if status not in PUBLICATION_STATUSES:
        raise ValueError(f"Ungueltiger Publication-Status: {status}")
    return status


def apply_publication_state(
    publication_payload: dict[str, Any],
    workflow_state: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = normalize_analysis_for_ui(publication_payload).get("publication_draft", {})
    if not workflow_state:
        return merged
    review = dict(merged.get("review") or {})
    publication = dict(merged.get("publication") or {})
    if "review_required" in workflow_state:
        review["required"] = bool(workflow_state.get("review_required"))
    if workflow_state.get("review_status"):
        review["status"] = str(workflow_state["review_status"])
    if workflow_state.get("review_notes") is not None:
        review["notes"] = str(workflow_state.get("review_notes") or "")
    if workflow_state.get("reviewed_by") is not None:
        review["reviewed_by"] = str(workflow_state.get("reviewed_by") or "")
    if workflow_state.get("reviewed_at") is not None:
        review["reviewed_at"] = str(workflow_state.get("reviewed_at") or "")
    if workflow_state.get("target"):
        publication["target"] = str(workflow_state["target"])
    if workflow_state.get("status"):
        publication["status"] = str(workflow_state["status"])
    if workflow_state.get("published_url") is not None:
        publication["published_url"] = str(workflow_state.get("published_url") or "")
    if workflow_state.get("published_at") is not None:
        publication["published_at"] = str(workflow_state.get("published_at") or "")
    merged["review"] = review
    merged["publication"] = publication
    return merged


def load_json_file(path_str: str) -> dict[str, Any] | None:
    if not path_str:
        return None
    path = Path(path_str)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def scan_analysis_outputs(root: Path = ANALYSIS_OUTPUTS_DIR) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.json"), reverse=True):
        payload = load_json_file(str(path))
        if not payload:
            continue
        normalized = normalize_analysis_for_ui(payload)
        rows.append(
            {
                "job_id": normalized.get("job_id", 0),
                "session_id": normalized.get("session_id", ""),
                "purpose": normalized.get("purpose", DEFAULT_ANALYSIS_PURPOSE),
                "output_type": normalized.get("output_type", ""),
                "status": normalized.get("status", ""),
                "created_at": normalized.get("created_at", ""),
                "json_path": str(path),
                "normalized": normalized,
            }
        )
    return rows


def filter_history_rows(
    rows: list[dict[str, Any]],
    *,
    session_id: str = "",
    purpose: str = "",
    output_type: str = "",
    status: str = "",
    review_status: str = "",
    publication_status: str = "",
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for row in rows:
        if session_id and str(row.get("session_id") or "") != session_id:
            continue
        if purpose and str(row.get("purpose") or "") != purpose:
            continue
        if output_type and str(row.get("last_output_type") or row.get("output_type") or "") != output_type:
            continue
        if status and str(row.get("status") or "") != status:
            continue
        if review_status and str(row.get("review_status") or "") != review_status:
            continue
        if publication_status and str(row.get("publication_status") or "") != publication_status:
            continue
        filtered.append(row)
    return filtered
