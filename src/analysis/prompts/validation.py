"""Prompt template validation and rendering helpers."""

from __future__ import annotations

import re
from dataclasses import replace
from string import Template

from src.analysis.prompts.models import PromptTemplate

VALID_SCOPES = {"session", "tops", "document"}
VALID_VISIBILITIES = {"private", "shared"}
ALLOWED_PLACEHOLDERS = {
    "session_title",
    "session_date",
    "committee",
    "agenda_item",
    "document_text",
    "source_list",
    "analysis_goal",
}
PLACEHOLDER_RE = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")


class PromptTemplateError(ValueError):
    """Raised when prompt template data is invalid."""


def validate_template(template: PromptTemplate) -> PromptTemplate:
    """Validate and normalize one prompt template."""
    errors: list[str] = []
    scopes = template.all_scopes
    if not template.id.strip():
        errors.append("id is required")
    if not template.label.strip():
        errors.append("label is required")
    invalid_scopes = sorted(scope for scope in scopes if scope not in VALID_SCOPES)
    if not scopes:
        errors.append(f"scope must be one of {', '.join(sorted(VALID_SCOPES))}")
    elif invalid_scopes:
        errors.append(f"scope must be one of {', '.join(sorted(VALID_SCOPES))}")
    if not template.prompt_text.strip():
        errors.append("prompt_text is required")
    if template.visibility not in VALID_VISIBILITIES:
        errors.append(f"visibility must be one of {', '.join(sorted(VALID_VISIBILITIES))}")
    if template.revision < 1:
        errors.append("revision must be >= 1")
    placeholders = extract_placeholders(template.prompt_text)
    unknown_placeholders = sorted(placeholders - ALLOWED_PLACEHOLDERS)
    if unknown_placeholders:
        errors.append("unknown placeholders: " + ", ".join(unknown_placeholders))
    if errors:
        raise PromptTemplateError("; ".join(errors))
    return replace(
        template,
        id=template.id.strip(),
        label=template.label.strip(),
        scope=scopes[0] if scopes else template.scope.strip(),
        description=template.description.strip(),
        prompt_text=template.prompt_text.strip(),
        variables=sorted(placeholders),
        scopes=scopes,
        visibility=template.visibility.strip(),
    )


def extract_placeholders(prompt_text: str) -> set[str]:
    """Return placeholder names used in a prompt template."""
    return {match.group(1) for match in PLACEHOLDER_RE.finditer(prompt_text)}


def render_prompt(template: PromptTemplate, context: dict[str, object]) -> str:
    """Render ``{{name}}`` placeholders using the provided context values."""
    source = PLACEHOLDER_RE.sub(lambda match: "${" + match.group(1) + "}", template.prompt_text)
    safe_context = {key: str(value or "") for key, value in context.items()}
    return Template(source).safe_substitute(safe_context)
