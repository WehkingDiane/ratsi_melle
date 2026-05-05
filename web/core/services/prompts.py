"""Prompt template access for the Django web UI."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from src.analysis.prompts.models import PromptTemplate
from src.analysis.prompts.repository import JsonPromptTemplateRepository, PromptTemplateRepository
from src.analysis.prompts.validation import PromptTemplateError

from . import paths


def prompt_repository() -> PromptTemplateRepository:
    """Return the configured prompt repository."""
    return JsonPromptTemplateRepository(
        path=paths.PROMPT_TEMPLATES_PATH,
        example_path=paths.PROMPT_TEMPLATES_EXAMPLE,
    )


def list_prompt_templates(scope: str = "", *, active_only: bool = False) -> list[dict[str, Any]]:
    """Return configured prompt templates, optionally filtered by scope."""
    templates = prompt_repository().list_templates(scope or None)
    if active_only:
        templates = [template for template in templates if template.is_active]
    return [template.to_dict() for template in templates]


def get_prompt_template(template_id: str) -> dict[str, Any] | None:
    """Return one prompt template by id."""
    template = prompt_repository().get_template(template_id)
    return template.to_dict() if template else None


def get_active_prompt_template(template_id: str, scope: str) -> tuple[PromptTemplate | None, list[str]]:
    """Return an active template and validate that it matches the requested scope."""
    if not template_id:
        return None, ["Bitte eine Prompt-Vorlage wÃ¤hlen."]
    template = prompt_repository().get_template(template_id)
    if template is None:
        return None, ["Die gewÃ¤hlte Prompt-Vorlage wurde nicht gefunden."]
    if not template.is_active:
        return None, ["Die gewÃ¤hlte Prompt-Vorlage ist deaktiviert."]
    if template.scope != scope:
        return None, ["Die gewÃ¤hlte Prompt-Vorlage passt nicht zum Analyse-Scope."]
    return template, []


def save_prompt_template_from_form(data: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    """Persist a prompt template from the management form."""
    template_id = str(data.get("id") or "").strip() or _slugify(str(data.get("label") or ""))
    label = str(data.get("label") or "").strip()
    scope = str(data.get("scope") or "session").strip()
    description = str(data.get("description") or "").strip()
    prompt_text = str(data.get("prompt_text") or "").strip()
    variables = _parse_variables(data.get("variables"))
    visibility = str(data.get("visibility") or "private").strip()
    is_active = str(data.get("is_active", "1")).lower() not in {"0", "false", "off", ""}

    template = PromptTemplate(
        id=template_id,
        label=label,
        scope=scope,
        description=description,
        prompt_text=prompt_text,
        variables=variables,
        is_active=is_active,
        visibility=visibility,
    )
    try:
        saved = prompt_repository().save_template(template)
    except PromptTemplateError as exc:
        return None, [str(exc)]
    return saved.to_dict(), []


def duplicate_prompt_template(template_id: str) -> tuple[dict[str, Any] | None, list[str]]:
    """Duplicate a template with a new id and revision 1."""
    repo = prompt_repository()
    template = repo.get_template(template_id)
    if template is None:
        return None, ["Die Prompt-Vorlage wurde nicht gefunden."]
    duplicate = replace(
        template,
        id=_unique_template_id(f"{template.id}_copy", repo),
        label=f"{template.label} Kopie",
        revision=1,
    )
    try:
        saved = repo.save_template(duplicate)
    except PromptTemplateError as exc:
        return None, [str(exc)]
    return saved.to_dict(), []


def deactivate_prompt_template(template_id: str) -> list[str]:
    """Deactivate a template instead of hard-deleting it."""
    repo = prompt_repository()
    if repo.get_template(template_id) is None:
        return ["Die Prompt-Vorlage wurde nicht gefunden."]
    repo.delete_template(template_id)
    return []


def _parse_variables(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value or "").replace("\n", ",").split(",") if item.strip()]


def _unique_template_id(base_id: str, repo: PromptTemplateRepository) -> str:
    used = {template.id for template in repo.list_templates()}
    candidate = base_id or "prompt_vorlage"
    counter = 2
    while candidate in used:
        candidate = f"{base_id}_{counter}"
        counter += 1
    return candidate


def _slugify(value: str) -> str:
    value = (
        value.lower()
        .replace("Ã¤", "ae")
        .replace("Ã¶", "oe")
        .replace("Ã¼", "ue")
        .replace("ÃŸ", "ss")
    )
    chars = []
    for char in value:
        if char.isalnum():
            chars.append(char)
        elif chars and chars[-1] != "_":
            chars.append("_")
    return "".join(chars).strip("_") or "prompt_vorlage"
