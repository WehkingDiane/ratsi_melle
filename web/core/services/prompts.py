"""Prompt template access for the Django web UI."""

from __future__ import annotations

from typing import Any

from src.analysis.prompt_registry import load_templates
from src.analysis.prompt_registry import save_templates

from . import paths


def list_prompt_templates(scope: str = "") -> list[dict[str, Any]]:
    """Return configured prompt templates, optionally filtered by scope."""

    templates = load_templates(paths.PROMPT_TEMPLATES_PATH)
    if not scope:
        return templates
    return [template for template in templates if scope in template.get("scope", [])]


def get_prompt_template(template_id: str) -> dict[str, Any] | None:
    """Return one prompt template by id."""

    for template in list_prompt_templates():
        if str(template.get("id") or "") == template_id:
            return template
    return None


def save_prompt_template_from_form(data: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    """Persist a user-defined prompt template from the analysis form."""

    label = str(data.get("template_label") or "").strip()
    prompt_text = str(data.get("prompt_text") or "").strip()
    scope = str(data.get("scope") or "session").strip()
    purpose = str(data.get("purpose") or "content_analysis").strip()
    if not label:
        return None, ["Bitte einen Namen für die Prompt-Vorlage angeben."]
    if not prompt_text:
        return None, ["Bitte einen Prompt eingeben, bevor die Vorlage gespeichert wird."]
    if scope not in {"session", "tops", "document"}:
        scope = "session"

    templates = load_templates(paths.PROMPT_TEMPLATES_PATH)
    template_id = _unique_template_id(_slugify(label), templates)
    template = {
        "id": template_id,
        "label": label,
        "scope": [scope],
        "purpose": purpose,
        "text": prompt_text,
    }
    templates.append(template)
    save_templates(templates, paths.PROMPT_TEMPLATES_PATH)
    return template, []


def _unique_template_id(base_id: str, templates: list[dict[str, Any]]) -> str:
    used = {str(template.get("id") or "") for template in templates}
    candidate = base_id or "prompt_vorlage"
    counter = 2
    while candidate in used:
        candidate = f"{base_id}_{counter}"
        counter += 1
    return candidate


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
    return "".join(chars).strip("_")
