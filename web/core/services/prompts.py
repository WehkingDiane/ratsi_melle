"""Prompt template access for the Django web UI."""

from __future__ import annotations

from typing import Any

from src.analysis.prompt_registry import load_templates

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
