"""Analysis form handling for the Django web UI."""

from __future__ import annotations

from typing import Any

from src.analysis.prompts.models import PromptTemplate
from src.analysis.prompts.validation import render_prompt
from src.analysis.service import AnalysisRequest
from src.analysis.service import AnalysisService

from . import paths
from .prompts import get_active_prompt_template
from .sessions import get_session


def analysis_purpose_options() -> list[dict[str, str]]:
    """Return supported analysis purposes for the web form."""
    return [
        {"value": "meeting_briefing", "label": "Sitzung vorbereiten: Überblick über alle TOPs"},
        {"value": "top_deep_dive", "label": "TOP analysieren: erklären und kritisch prüfen"},
        {"value": "session_preparation", "label": "Sitzungsvorbereitung"},
        {"value": "content_analysis", "label": "Inhaltsanalyse"},
        {"value": "fact_extraction", "label": "Strukturierte Faktenerfassung"},
        {"value": "journalistic_publication", "label": "Journalistischer Publikationsentwurf"},
    ]


def default_purpose_for_scope(scope: str) -> str:
    """Return the user-oriented default analysis purpose for a scope."""
    return "top_deep_dive" if scope == "tops" else "meeting_briefing"


def provider_options() -> list[dict[str, str]]:
    """Return provider options known to the existing analysis service."""
    return [
        {"value": "none", "label": "Manuell / ChatGPT: Grundlage und Prompt erzeugen"},
        {"value": "codex", "label": "OpenAI API: Analyse automatisch erstellen"},
        {"value": "claude", "label": "Claude API (Anthropic)"},
        {"value": "ollama", "label": "Ollama lokal"},
    ]


def default_provider_id() -> str:
    """Return the safe default provider for the local web form."""
    return "none"


def run_analysis_from_form(data: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    """Validate web form data and run the existing analysis service."""
    errors: list[str] = []
    session_id = str(data.get("session_id") or "").strip()
    scope = str(data.get("scope") or "session").strip()
    selected_tops = [str(top).strip() for top in data.get("top_numbers", []) if str(top).strip()]
    provider_id = str(data.get("provider_id") or "none").strip()
    model_name = str(data.get("model_name") or "").strip()
    template_id = str(data.get("template_id") or "").strip()
    purpose = str(data.get("purpose") or default_purpose_for_scope(scope)).strip()

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

    selected_tops_for_scope = selected_tops if scope == "tops" else []
    if not template_id:
        template_id = default_template_id(scope, purpose)
    template, template_errors = get_active_prompt_template(template_id, scope)
    errors.extend(template_errors)
    prompt = ""
    if template and session:
        prompt = render_prompt(template, _prompt_context(session, scope, selected_tops_for_scope, purpose))

    if errors or not session:
        return None, errors

    request = AnalysisRequest(
        db_path=paths.LOCAL_INDEX_DB,
        session=session,
        scope=scope,
        selected_tops=selected_tops_for_scope,
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


def execute_prepared_analysis(
    job_id: str, provider_id: str, model_name: str = ""
) -> tuple[dict[str, Any] | None, list[str]]:
    """Execute one prepared workflow job in place."""

    from .outputs import get_analysis_output

    job = get_analysis_output(job_id)
    if not job:
        return None, ["Der Analysejob wurde nicht gefunden."]
    if str(job.get("status") or "") != "prepared":
        return None, ["Nur vorbereitete Analysen können nachträglich abgesendet werden."]
    if provider_id == "none":
        return None, ["Bitte einen KI-Provider für die Ausführung wählen."]
    if provider_id not in {option["value"] for option in provider_options()}:
        return None, ["Der KI-Provider ist ungültig."]

    session_id = str(job.get("session_id") or "")
    session = get_session(session_id)
    if not session:
        return None, ["Die zugehörige Sitzung ist nicht mehr im lokalen Index vorhanden."]
    try:
        workflow_job_id = int(job.get("db_job_id") or job_id)
        source_job_id = int(job.get("source_job_id") or workflow_job_id)
    except (TypeError, ValueError):
        return None, ["Der Analysejob besitzt keine gültige interne Verknüpfung."]

    artifact_paths: dict[str, Path] = {}
    for value in job.get("files", []):
        path = Path(str(value))
        if not path.is_absolute():
            path = paths.REPO_ROOT / path
        normalized = path.name.lower()
        if normalized.endswith(".article.md"):
            artifact_paths["article"] = path
        elif normalized.endswith(".raw.json"):
            artifact_paths["raw"] = path
        elif normalized.endswith(".structured.json"):
            artifact_paths["structured"] = path
    if "article" not in artifact_paths:
        return None, ["Die Markdown-Datei des vorbereiteten Jobs wurde nicht gefunden."]

    request = AnalysisRequest(
        db_path=paths.LOCAL_INDEX_DB,
        session=session,
        scope=str(job.get("scope") or "session"),
        selected_tops=[str(value) for value in job.get("top_numbers", [])],
        prompt=str(job.get("prompt_text") or ""),
        provider_id=provider_id,
        model_name=model_name.strip(),
        prompt_version=str(job.get("prompt_version") or "web"),
        prompt_template_id=str(job.get("prompt_template_id") or ""),
        prompt_template_revision=job.get("prompt_template_revision"),
        prompt_template_label=str(job.get("prompt_template_label") or ""),
        purpose=str(job.get("purpose") or default_purpose_for_scope(str(job.get("scope") or "session"))),
    )
    record = AnalysisService().execute_prepared_analysis(
        request,
        workflow_job_id=workflow_job_id,
        source_job_id=source_job_id,
        markdown=str(job.get("markdown") or ""),
        artifact_paths=artifact_paths,
        workflow_db_path=paths.ANALYSIS_WORKFLOW_DB,
    )
    return record.to_dict(), []


def default_template_id(scope: str, purpose: str = "") -> str:
    """Return the best active template id for a requested analysis mode."""
    purpose = purpose or default_purpose_for_scope(scope)
    templates = _templates_for_scope(scope)
    if not templates:
        return ""
    preferred_ids = {
        ("session", "meeting_briefing"): ["meeting_briefing", "session_preparation_briefing"],
        ("session", "session_preparation"): ["meeting_briefing", "session_preparation_briefing"],
        ("tops", "top_deep_dive"): ["top_critical_analysis", "top_deep_dive"],
        ("tops", "content_analysis"): ["top_critical_analysis", "top_deep_dive"],
    }.get((scope, purpose), [])
    for template_id in preferred_ids:
        if any(template.id == template_id for template in templates):
            return template_id
    return templates[0].id


def _templates_for_scope(scope: str) -> list[PromptTemplate]:
    try:
        return [template for template in _read_active_prompt_templates(scope) if template.is_active]
    except Exception:  # noqa: BLE001
        return []


def _read_active_prompt_templates(scope: str) -> list[PromptTemplate]:
    from .prompts import prompt_repository

    return prompt_repository().list_templates(scope)


def _prompt_context(
    session: dict[str, Any],
    scope: str,
    selected_tops: list[str],
    purpose: str,
) -> dict[str, object]:
    title = str(session.get("meeting_name") or session.get("committee") or session.get("session_id") or "")
    agenda_items = session.get("agenda_items") or []
    selected_top_set = {str(top) for top in selected_tops} if scope == "tops" else set()
    selected_items = [
        item for item in agenda_items
        if not selected_top_set or str(item.get("number") or "") in selected_top_set
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
