"""Prompt template access for the Django web UI."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from src.analysis.prompts.models import PromptTemplate, scopes_from_json
from src.analysis.prompts.repository import JsonPromptTemplateRepository, PromptTemplateRepository
from src.analysis.prompts.validation import PromptTemplateError

from . import paths


PROMPT_TEMPLATE_STORE_READ_ERROR = "Prompt-Vorlagen konnten nicht gelesen werden. Bitte private Vorlagen-Datei prüfen."


def prompt_repository() -> PromptTemplateRepository:
    """Return the configured prompt repository."""
    return JsonPromptTemplateRepository(
        path=paths.PROMPT_TEMPLATES_PATH,
        example_path=paths.PROMPT_TEMPLATES_EXAMPLE,
    )


def list_prompt_templates(scope: str = "", *, active_only: bool = False) -> list[dict[str, Any]]:
    """Return configured prompt templates, optionally filtered by scope."""
    try:
        templates = _read_templates(prompt_repository(), scope or None)
    except PromptTemplateError:
        return []
    if active_only:
        templates = [template for template in templates if template.is_active]
    return [template.to_dict() for template in templates]


def get_prompt_template(template_id: str) -> dict[str, Any] | None:
    """Return one prompt template by id."""
    try:
        template = _read_template(prompt_repository(), template_id)
    except PromptTemplateError:
        return None
    return template.to_dict() if template else None


def get_active_prompt_template(template_id: str, scope: str) -> tuple[PromptTemplate | None, list[str]]:
    """Return an active template and validate that it matches the requested scope."""
    if not template_id:
        return None, ["Bitte eine Prompt-Vorlage wählen."]
    try:
        template = _read_template(prompt_repository(), template_id)
    except PromptTemplateError:
        return None, [PROMPT_TEMPLATE_STORE_READ_ERROR]
    if template is None:
        return None, ["Die gewählte Prompt-Vorlage wurde nicht gefunden."]
    if not template.is_active:
        return None, ["Die gewählte Prompt-Vorlage ist deaktiviert."]
    if not template.matches_scope(scope):
        return None, ["Die gewählte Prompt-Vorlage passt nicht zum Analyse-Scope."]
    return template, []


def save_prompt_template_from_form(data: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    """Persist a prompt template from the management form."""
    repo = prompt_repository()
    allow_update = bool(data.get("allow_update"))
    template_id = str(data.get("id") or "").strip() or _slugify(str(data.get("label") or ""))
    try:
        existing = _read_template(repo, template_id)
        if not allow_update and existing is not None:
            template_id = _unique_template_id(template_id, repo)
            existing = None
    except PromptTemplateError:
        return None, [PROMPT_TEMPLATE_STORE_READ_ERROR]
    label = str(data.get("label") or "").strip()
    scope = str(data.get("scope") or "session").strip()
    description = str(data.get("description") or "").strip()
    prompt_text = str(data.get("prompt_text") or "").strip()
    variables = _parse_variables(data.get("variables"))
    visibility = str(data.get("visibility") or "private").strip()
    is_active = str(data.get("is_active", "1")).lower() not in {"0", "false", "off", ""}
    scopes = [scope]
    if allow_update and existing and len(existing.all_scopes) > 1:
        scopes = scopes_from_json(scope, existing.all_scopes)

    template = PromptTemplate(
        id=template_id,
        label=label,
        scope=scope,
        description=description,
        prompt_text=prompt_text,
        variables=variables,
        scopes=scopes,
        is_active=is_active,
        visibility=visibility,
    )
    try:
        saved = repo.save_template(template)
    except PromptTemplateError as exc:
        return None, [str(exc)]
    return saved.to_dict(), []


def duplicate_prompt_template(template_id: str) -> tuple[dict[str, Any] | None, list[str]]:
    """Duplicate a template with a new id and revision 1."""
    repo = prompt_repository()
    try:
        template = _read_template(repo, template_id)
    except PromptTemplateError:
        return None, [PROMPT_TEMPLATE_STORE_READ_ERROR]
    if template is None:
        return None, ["Die Prompt-Vorlage wurde nicht gefunden."]
    try:
        duplicate = replace(
            template,
            id=_unique_template_id(f"{template.id}_copy", repo),
            label=f"{template.label} Kopie",
            revision=1,
        )
        saved = repo.save_template(duplicate)
    except PromptTemplateError as exc:
        return None, [str(exc)]
    return saved.to_dict(), []


def deactivate_prompt_template(template_id: str) -> list[str]:
    """Deactivate a template instead of hard-deleting it."""
    repo = prompt_repository()
    try:
        if _read_template(repo, template_id) is None:
            return ["Die Prompt-Vorlage wurde nicht gefunden."]
        repo.delete_template(template_id)
    except PromptTemplateError:
        return [PROMPT_TEMPLATE_STORE_READ_ERROR]
    return []


def _parse_variables(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value or "").replace("\n", ",").split(",") if item.strip()]


def _unique_template_id(base_id: str, repo: PromptTemplateRepository) -> str:
    used = {template.id for template in _read_templates(repo)}
    candidate = base_id or "prompt_vorlage"
    counter = 2
    while candidate in used:
        candidate = f"{base_id}_{counter}"
        counter += 1
    return candidate


def _read_template(repo: PromptTemplateRepository, template_id: str) -> PromptTemplate | None:
    return repo.get_template(template_id)


def _read_templates(repo: PromptTemplateRepository, scope: str | None = None) -> list[PromptTemplate]:
    return repo.list_templates(scope)


def _slugify(value: str) -> str:
    value = (
        value.lower()
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    chars = []
    for char in value:
        if char.isalnum():
            chars.append(char)
        elif chars and chars[-1] != "_":
            chars.append("_")
    return "".join(chars).strip("_") or "prompt_vorlage"
