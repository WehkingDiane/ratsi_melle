"""Prompt template repository interfaces and JSON implementation."""

from __future__ import annotations

import json
import os
import tempfile
from abc import ABC, abstractmethod
from dataclasses import replace
from pathlib import Path
from typing import Any

from src.analysis.prompts.models import PromptTemplate, utc_now
from src.analysis.prompts.validation import PromptTemplateError, validate_template
from src.paths import PROMPT_TEMPLATES_EXAMPLE, PROMPT_TEMPLATES_PATH


class PromptTemplateRepository(ABC):
    """Storage interface for prompt templates."""

    @abstractmethod
    def list_templates(self, scope: str | None = None) -> list[PromptTemplate]:
        """Return templates, optionally filtered by scope."""

    @abstractmethod
    def get_template(self, template_id: str) -> PromptTemplate | None:
        """Return one template by id."""

    @abstractmethod
    def save_template(self, template: PromptTemplate) -> PromptTemplate:
        """Create or update one template."""

    @abstractmethod
    def delete_template(self, template_id: str) -> None:
        """Delete or deactivate one template."""


class MemoryPromptTemplateRepository(PromptTemplateRepository):
    """In-memory repository for tests."""

    def __init__(self, templates: list[PromptTemplate] | None = None) -> None:
        self._templates = {template.id: validate_template(template) for template in templates or []}

    def list_templates(self, scope: str | None = None) -> list[PromptTemplate]:
        templates = sorted(self._templates.values(), key=lambda item: item.label.lower())
        if scope:
            return [replace(template, scope=scope) for template in templates if template.matches_scope(scope)]
        return templates

    def get_template(self, template_id: str) -> PromptTemplate | None:
        return self._templates.get(template_id)

    def save_template(self, template: PromptTemplate) -> PromptTemplate:
        existing = self._templates.get(template.id)
        if existing:
            template = replace(
                template,
                revision=existing.revision + 1,
                created_at=existing.created_at,
                updated_at=utc_now(),
            )
        saved = validate_template(template)
        self._templates[saved.id] = saved
        return saved

    def delete_template(self, template_id: str) -> None:
        existing = self._templates.get(template_id)
        if existing:
            self.save_template(replace(existing, is_active=False))


class JsonPromptTemplateRepository(PromptTemplateRepository):
    """JSON-backed prompt template repository using a private file."""

    def __init__(self, path: Path | None = None, example_path: Path | None = None) -> None:
        self.path = Path(path or PROMPT_TEMPLATES_PATH).expanduser()
        self.example_path = Path(example_path or PROMPT_TEMPLATES_EXAMPLE).expanduser()

    def list_templates(self, scope: str | None = None) -> list[PromptTemplate]:
        templates = self._load()
        if scope:
            templates = [replace(template, scope=scope) for template in templates if template.matches_scope(scope)]
        return sorted(templates, key=lambda item: item.label.lower())

    def get_template(self, template_id: str) -> PromptTemplate | None:
        for template in self._load():
            if template.id == template_id:
                return template
        return None

    def save_template(self, template: PromptTemplate) -> PromptTemplate:
        templates = {item.id: item for item in self._load()}
        existing = templates.get(template.id)
        if existing:
            template = replace(
                template,
                revision=existing.revision + 1,
                created_at=existing.created_at,
                updated_at=utc_now(),
            )
        saved = validate_template(template)
        templates[saved.id] = saved
        self._write(list(templates.values()))
        return saved

    def delete_template(self, template_id: str) -> None:
        existing = self.get_template(template_id)
        if existing:
            self.save_template(replace(existing, is_active=False))

    def _ensure_initialized(self) -> None:
        if self.path.exists():
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.example_path.exists():
            data = self.example_path.read_text(encoding="utf-8")
        else:
            data = '{"templates": []}\n'
        self._write_raw(data)

    def _load(self) -> list[PromptTemplate]:
        self._ensure_initialized()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise PromptTemplateError(f"Invalid prompt template JSON in {self.path}") from exc
        except OSError as exc:
            raise PromptTemplateError(f"Could not read prompt template store: {self.path}") from exc

        raw_templates = data.get("templates") if isinstance(data, dict) else data
        if not isinstance(raw_templates, list):
            raise PromptTemplateError("Prompt template JSON must contain a templates list.")
        return [_template_from_record(item) for item in raw_templates if isinstance(item, dict)]

    def _write(self, templates: list[PromptTemplate]) -> None:
        payload = {"templates": [template.to_dict() for template in sorted(templates, key=lambda item: item.id)]}
        self._write_raw(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    def _write_raw(self, data: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=str(self.path.parent),
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(data)
            Path(tmp_name).replace(self.path)
        finally:
            tmp_path = Path(tmp_name)
            if tmp_path.exists():
                tmp_path.unlink()


def default_prompt_template_repository() -> PromptTemplateRepository:
    """Return the default private JSON prompt template repository."""
    return JsonPromptTemplateRepository()


def _template_from_record(item: dict[str, Any]) -> PromptTemplate:
    try:
        return validate_template(PromptTemplate.from_dict(item))
    except PromptTemplateError:
        raise
    except (TypeError, ValueError) as exc:
        raise PromptTemplateError("Invalid prompt template record.") from exc
