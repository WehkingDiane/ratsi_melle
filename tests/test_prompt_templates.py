from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from src.analysis.prompts.models import PromptTemplate
from src.analysis.prompts.repository import JsonPromptTemplateRepository, MemoryPromptTemplateRepository
from src.analysis.prompts.validation import PromptTemplateError, render_prompt, validate_template


def _template(template_id: str = "session_demo", scope: str = "session") -> PromptTemplate:
    return PromptTemplate(
        id=template_id,
        label="Demo",
        scope=scope,
        description="Demo prompt",
        prompt_text="Analysiere {{session_title}} fuer {{analysis_goal}}.",
        variables=["session_title", "analysis_goal"],
    )


def test_prompt_template_model_and_validation() -> None:
    template = validate_template(_template())

    assert template.id == "session_demo"
    assert template.scope == "session"
    assert template.revision == 1


def test_prompt_template_from_dict_parses_is_active_strings() -> None:
    base = _template().to_dict()

    assert PromptTemplate.from_dict({**base, "is_active": "false"}).is_active is False
    assert PromptTemplate.from_dict({**base, "is_active": "0"}).is_active is False
    assert PromptTemplate.from_dict({**base, "is_active": "true"}).is_active is True
    assert PromptTemplate.from_dict({key: value for key, value in base.items() if key != "is_active"}).is_active is True


def test_prompt_template_validation_rejects_invalid_scope() -> None:
    with pytest.raises(PromptTemplateError, match="scope"):
        validate_template(_template(scope="invalid"))


def test_render_prompt_substitutes_known_placeholders() -> None:
    rendered = render_prompt(
        _template(),
        {"session_title": "Ratssitzung", "analysis_goal": "Inhaltsanalyse"},
    )

    assert rendered == "Analysiere Ratssitzung fuer Inhaltsanalyse."


def test_prompt_template_validation_rejects_unknown_placeholder() -> None:
    with pytest.raises(PromptTemplateError, match="unknown placeholders: unknown_value"):
        validate_template(
            PromptTemplate(
                id="bad",
                label="Bad",
                scope="session",
                description="",
                prompt_text="Analysiere {{unknown_value}}.",
            )
        )


def test_prompt_template_validation_accepts_known_placeholders_and_syncs_variables() -> None:
    template = validate_template(
        PromptTemplate(
            id="known",
            label="Known",
            scope="session",
            description="",
            prompt_text="Analysiere {{committee}} und {{session_date}}.",
            variables=["committee", "unused"],
        )
    )

    assert template.variables == ["committee", "session_date"]


def test_memory_repository_filters_and_deactivates() -> None:
    repo = MemoryPromptTemplateRepository([_template(), _template("top_demo", "tops")])

    assert [item.id for item in repo.list_templates("tops")] == ["top_demo"]
    repo.delete_template("top_demo")

    assert repo.get_template("top_demo").is_active is False


def test_json_repository_initializes_from_example(tmp_path: Path) -> None:
    example_path = tmp_path / "prompt_templates.example.json"
    example_path.write_text(
        json.dumps({"templates": [_template().to_dict()]}, ensure_ascii=False),
        encoding="utf-8",
    )
    store_path = tmp_path / "private" / "prompt_templates.json"

    repo = JsonPromptTemplateRepository(path=store_path, example_path=example_path)

    assert [item.id for item in repo.list_templates()] == ["session_demo"]
    assert store_path.exists()


def test_json_repository_scope_filter_save_revision_and_deactivate(tmp_path: Path) -> None:
    repo = JsonPromptTemplateRepository(path=tmp_path / "prompt_templates.json", example_path=tmp_path / "missing.json")
    repo.save_template(_template())
    repo.save_template(_template("top_demo", "tops"))

    assert [item.id for item in repo.list_templates("tops")] == ["top_demo"]

    updated = repo.save_template(replace(_template(), label="Demo aktualisiert"))
    assert updated.revision == 2

    repo.delete_template("session_demo")
    assert repo.get_template("session_demo").is_active is False


def test_json_repository_reports_invalid_json(tmp_path: Path) -> None:
    store_path = tmp_path / "prompt_templates.json"
    store_path.write_text("{not json", encoding="utf-8")
    repo = JsonPromptTemplateRepository(path=store_path)

    with pytest.raises(PromptTemplateError, match="Invalid prompt template JSON"):
        repo.list_templates()
