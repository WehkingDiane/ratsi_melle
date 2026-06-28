"""Legacy prompt registry for the deprecated Streamlit UI.

New Django UI work should use ``src.analysis.prompts`` repositories and models.
This module stays only for compatibility with ``src.interfaces.web.streamlit_app``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_TEMPLATES: list[dict] = [
    {
        "id": "doc_summary",
        "label": "Dokumentzusammenfassung",
        "scope": ["document", "tops", "session"],
        "text": (
            "Erstelle eine neutrale Zusammenfassung dieses Dokuments. "
            "Nenne Kernthemen, Beschlüsse und offene Fragen. "
            "Beziehe dich auf konkrete Textstellen."
        ),
    }
]


def load_templates(path: Path) -> list[dict]:
    """Load prompt templates from a JSON file.

    Returns the list of template dicts, or built-in defaults on any error.
    """
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        if isinstance(data, dict) and isinstance(data.get("templates"), list):
            return [_streamlit_compatible_template(item) for item in data["templates"] if isinstance(item, dict)]
        if isinstance(data, list):
            return [_streamlit_compatible_template(item) for item in data if isinstance(item, dict)]
        logger.warning("prompt_templates.json: expected list, got %s", type(data))
    except FileNotFoundError:
        logger.info("Prompt template file not found: %s – using defaults", path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not load prompt templates from %s: %s", path, exc)
    return list(_DEFAULT_TEMPLATES)


def save_templates(templates: list[dict], path: Path) -> None:
    """Persist prompt templates to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"templates": templates}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def filter_by_scope(templates: list[dict], scope: str) -> list[dict]:
    """Return only templates whose scope list includes the given scope value."""
    filtered = []
    for template in templates:
        template_scope = template.get("scope", [])
        if isinstance(template_scope, str):
            if template_scope == scope:
                filtered.append(template)
        elif scope in template_scope:
            filtered.append(template)
    return filtered


def _streamlit_compatible_template(template: dict) -> dict:
    item = dict(template)
    if "text" not in item and "prompt_text" in item:
        item["text"] = item["prompt_text"]
    if "prompt_text" not in item and "text" in item:
        item["prompt_text"] = item["text"]
    return item
