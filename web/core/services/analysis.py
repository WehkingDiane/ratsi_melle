"""Analysis form handling for the Django web UI."""

from __future__ import annotations

from typing import Any

from src.analysis.service import AnalysisRequest
from src.analysis.service import AnalysisService

from . import paths
from .prompts import get_prompt_template
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
    prompt = str(data.get("prompt_text") or "").strip()
    purpose = str(data.get("purpose") or "content_analysis").strip()

    session = get_session(session_id) if session_id else None
    if not session:
        errors.append("Bitte eine vorhandene Sitzung wählen.")
    if scope not in {"session", "tops"}:
        errors.append("Der Scope ist ungültig.")
    if scope == "tops" and not selected_tops:
        errors.append("Bitte mindestens einen TOP wählen oder Scope 'Ganze Sitzung' nutzen.")
    if scope == "tops" and session and selected_tops:
        available_tops = {
            str(item.get("number") or "")
            for item in session.get("agenda_items", [])
            if item.get("has_analysis_documents")
        }
        invalid_tops = [top for top in selected_tops if top not in available_tops]
        if invalid_tops:
            errors.append(
                "Bitte nur TOPs mit lokal vorhandenen Dokumenten auswählen: "
                + ", ".join(invalid_tops)
            )
    if provider_id not in {option["value"] for option in provider_options()}:
        errors.append("Der KI-Provider ist ungültig.")
    if purpose not in {option["value"] for option in analysis_purpose_options()}:
        errors.append("Der Analysezweck ist ungültig.")

    template = get_prompt_template(template_id) if template_id else None
    if template:
        purpose = str(template.get("purpose") or purpose)
        if not prompt:
            prompt = str(template.get("text") or "")
    if not prompt:
        errors.append("Bitte einen Prompt eingeben oder eine Vorlage wählen.")

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
        prompt_version=template_id or "web",
        purpose=purpose,
    )
    record = AnalysisService().run_journalistic_analysis(request)
    return record.to_dict(), []
