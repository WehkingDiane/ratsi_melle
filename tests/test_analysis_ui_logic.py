from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.interfaces.web.analysis_ui import (
    apply_publication_state,
    build_source_check,
    filter_history_rows,
    get_allowed_output_types,
    get_suggested_template_ids,
    map_purpose_label_to_key,
    normalize_analysis_for_ui,
    scan_analysis_outputs,
    validate_publication_status,
    validate_review_status,
)


def test_purpose_label_mapping_uses_expected_internal_keys() -> None:
    assert map_purpose_label_to_key("Journalistische Veroeffentlichung") == "journalistic_publication"
    assert map_purpose_label_to_key("Sitzungsvorbereitung") == "session_preparation"
    assert map_purpose_label_to_key("Inhaltliche Analyse") == "content_analysis"
    assert map_purpose_label_to_key("Faktenextraktion") == "fact_extraction"


def test_template_mapping_and_allowed_output_types_are_purpose_specific() -> None:
    assert get_suggested_template_ids("journalistic_publication") == [
        "structured_fact_extraction",
        "journalistic_publication_draft",
    ]
    assert get_suggested_template_ids("session_preparation") == ["meeting_preparation_briefing"]
    assert get_allowed_output_types("session_preparation") == [
        "raw_analysis",
        "structured_analysis",
        "meeting_briefing",
    ]
    assert "publication_draft" in get_allowed_output_types("journalistic_publication")


def test_normalize_analysis_for_ui_handles_v1_payloads() -> None:
    normalized = normalize_analysis_for_ui(
        {
            "schema_version": "1.0",
            "job_id": 4,
            "session_id": "7123",
            "scope": "tops",
            "top_numbers": ["Oe 7"],
            "ki_response": "Antwort",
            "markdown": "# Analyse",
            "status": "done",
        }
    )

    assert normalized["output_type"] == "legacy_analysis_output"
    assert normalized["legacy_notice"]
    assert normalized["structured"]["topic"]["title"] == ""
    assert normalized["publication_draft"]["body_markdown"] == "# Analyse"


def test_normalize_analysis_for_ui_handles_v2_payloads_with_missing_optional_fields() -> None:
    normalized = normalize_analysis_for_ui(
        {
            "schema_version": "2.0",
            "output_type": "structured_analysis",
            "job_id": 5,
            "session_id": "8001",
            "purpose": "content_analysis",
        }
    )

    assert normalized["structured"]["facts"] == []
    assert normalized["structured"]["open_questions"] == []
    assert normalized["publication_draft"]["publication"]["status"] == "not_published"


def test_build_source_check_detects_mixed_source_quality(tmp_path: Path) -> None:
    session_dir = tmp_path / "data" / "raw" / "2026" / "04" / "2026-04-01_Rat_1"
    pdf_path = session_dir / "docs" / "vorlage.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"pdf")

    source_check = build_source_check(
        [
            {
                "agenda_item": "1",
                "title": "Vorlage",
                "document_type": "vorlage",
                "local_path": "docs/vorlage.pdf",
                "url": "https://example.org/vorlage",
                "content_type": "application/pdf",
                "session_path": str(session_dir),
            },
            {
                "agenda_item": "2",
                "title": "Anlage",
                "document_type": "anlage",
                "local_path": "",
                "url": "",
                "content_type": "application/pdf",
                "session_path": str(session_dir),
            },
        ]
    )

    assert source_check["document_count"] == 2
    assert source_check["local_available_count"] == 1
    assert source_check["local_missing_count"] == 1
    assert source_check["url_missing_count"] == 1
    assert source_check["has_warnings"] is True


def test_status_validators_accept_only_supported_values() -> None:
    assert validate_review_status("approved") == "approved"
    assert validate_publication_status("scheduled") == "scheduled"
    with pytest.raises(ValueError):
        validate_review_status("done")
    with pytest.raises(ValueError):
        validate_publication_status("queued")


def test_apply_publication_state_overrides_json_with_workflow_state() -> None:
    merged = apply_publication_state(
        {
            "schema_version": "2.0",
            "output_type": "publication_draft",
            "title": "Artikel",
            "review": {"required": True, "status": "pending"},
            "publication": {"target": "local_static_site", "status": "not_published"},
        },
        {
            "review_required": 0,
            "review_status": "approved",
            "review_notes": "ok",
            "reviewed_by": "Diane",
            "reviewed_at": "2026-04-27T10:00:00Z",
            "target": "local_static_site",
            "status": "draft_created",
            "published_url": "",
            "published_at": "",
        },
    )

    assert merged["review"]["required"] is False
    assert merged["review"]["status"] == "approved"
    assert merged["publication"]["status"] == "draft_created"


def test_filter_history_rows_supports_purpose_and_status_filters() -> None:
    rows = [
        {
            "job_id": 1,
            "session_id": "7001",
            "purpose": "content_analysis",
            "last_output_type": "structured_analysis",
            "status": "done",
            "review_status": "",
            "publication_status": "",
        },
        {
            "job_id": 2,
            "session_id": "7001",
            "purpose": "journalistic_publication",
            "last_output_type": "publication_draft",
            "status": "draft",
            "review_status": "pending",
            "publication_status": "draft_created",
        },
    ]

    assert [row["job_id"] for row in filter_history_rows(rows, purpose="journalistic_publication")] == [2]
    assert [row["job_id"] for row in filter_history_rows(rows, status="done")] == [1]
    assert [row["job_id"] for row in filter_history_rows(rows, publication_status="draft_created")] == [2]


def test_scan_analysis_outputs_groups_v2_json_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "data" / "analysis_outputs"
    session_dir = output_dir / "2026" / "04" / "2026-04-01_Rat_1"
    session_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "2.0",
        "output_type": "structured_analysis",
        "job_id": 8,
        "session_id": "1",
        "purpose": "content_analysis",
    }
    (session_dir / "job_8.structured.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    rows = scan_analysis_outputs(output_dir)

    assert len(rows) == 1
    assert rows[0]["job_id"] == 8
    assert rows[0]["output_type"] == "structured_analysis"
