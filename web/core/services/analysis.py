"""Analysis form handling for the Django web UI."""

from __future__ import annotations

from typing import Any

from src.analysis.prompts.validation import render_prompt
from src.analysis.service import AnalysisRequest
from src.analysis.service import AnalysisService

from . import paths
from .prompts import get_active_prompt_template
from .sessions import get_session


def analysis_purpose_options() -> list[dict[str, str]]:
    """Return supported analysis purposes for the web form."""
    return [
        {"value": "content_analysis", "label": "Inhaltsanalyse"},
        {"value": "fact_extraction", "label": "Strukturierte Faktenerfassung"},
        {"value": "session_preparation", "label": "Sitzungsvorbereitung"},
        {"value": "journalistic_publication", "label": "Journalistischer Publikationsentwurf"},
    ]


def provider_options() -> list[dict[str, str]]:
    """Return provider options known to the existing analysis service."""
    return [
        {"value": "none", "label": "Kein Provider (nur Grundlage)"},
        {"value": "claude", "label": "Claude (Anthropic)"},
        {"value": "codex", "label": "Codex (OpenAI)"},
        {"value": "ollama", "label": "Ollama (lokal)"},
    ]


def run_analysis_from_form(data: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    """Validate web form data and run the existing analysis service."""
    errors: list[str] = []
    session_id = str(data.get("session_id") or "").strip()
    scope = str(data.get("scope") or "session").strip()
    selected_tops = [str(top).strip() for top in data.get("top_numbers", []) if str(top).strip()]
    provider_id = str(data.get("provider_id") or "none").strip()
    model_name = str(data.get("model_name") or "").strip()
    template_id = str(data.get("template_id") or "").strip()
    purpose = str(data.get("purpose") or "content_analysis").strip()

    session = get_session(session_id) if session_id else None
    if not session:
        errors.append("Bitte eine vorhandene Sitzung waehlen.")
    if scope not in {"session", "tops"}:
        errors.append("Der Scope ist ungueltig.")
    if scope == "tops" and not selected_tops:
        errors.append("Bitte mindestens einen TOP waehlen oder Scope 'Ganze Sitzung' nutzen.")
    if scope == "tops" and session and selected_tops:
        available_tops = {
            str(item.get("number") or "")
            for item in session.get("agenda_items", [])
            if item.get("has_analysis_documents")
        }
        invalid_tops = [top for top in selected_tops if top not in available_tops]
        if invalid_tops:
            errors.append(
                "Bitte nur TOPs mit lokal vorhandenen Dokumenten auswaehlen: "
                + ", ".join(invalid_tops)
            )
    if provider_id not in {option["value"] for option in provider_options()}:
        errors.append("Der KI-Provider ist ungueltig.")
    if purpose not in {option["value"] for option in analysis_purpose_options()}:
        errors.append("Der Analysezweck ist ungueltig.")

    template, template_errors = get_active_prompt_template(template_id, scope)
    errors.extend(template_errors)
    prompt = ""
    if template and session:
        prompt = render_prompt(template, _prompt_context(session, scope, selected_tops, purpose))

    if errors or not session:
        return None, errors

    request = AnalysisRequest(
        db_path=paths.LOCAL_INDEX_DB,
        session=session,
        scope=scope,
        selected_tops=selected_tops if scope == "tops" else [],
        prompt=prompt,
        provider_id=provider_id,
        model_name=model_name,
        prompt_version=f"{template.id}@{template.revision}" if template else "web",
        prompt_template_id=template.id if template else "",
        prompt_template_revision=template.revision if template else None,
        prompt_template_label=template.label if template else "",
        purpose=purpose,
    )
    record = AnalysisService().run_journalistic_analysis(request)
    return record.to_dict(), []


def _prompt_context(
    session: dict[str, Any],
    scope: str,
    selected_tops: list[str],
    purpose: str,
) -> dict[str, object]:
    title = str(session.get("meeting_name") or session.get("committee") or session.get("session_id") or "")
    agenda_items = session.get("agenda_items") or []
    selected_items = [
        item for item in agenda_items
        if not selected_tops or str(item.get("number") or "") in selected_tops
    ]
    source_list = "\n".join(
        f"- {item.get('number', '')} {item.get('title', '')}".strip()
        for item in selected_items
    )
    return {
        "session_title": title,
        "session_date": session.get("display_date") or session.get("date") or "",
        "committee": session.get("committee") or "",
        "agenda_item": ", ".join(selected_tops) if scope == "tops" else "",
        "document_text": "",
        "source_list": source_list,
        "analysis_goal": purpose,
    }
