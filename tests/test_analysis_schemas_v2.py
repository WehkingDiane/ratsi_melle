from __future__ import annotations

from src.analysis.schemas import (
    DEFAULT_ANALYSIS_PURPOSE,
    PublicationDraftOutput,
    RawAnalysisDocument,
    RawAnalysisOutput,
    StructuredAnalysisOutput,
    normalize_analysis_output,
)


def test_v2_schemas_can_be_created_with_required_defaults() -> None:
    raw = RawAnalysisOutput(
        job_id=1,
        session_id="7123",
        documents=[
            RawAnalysisDocument(
                title="Beschlussvorlage",
                document_type="beschlussvorlage",
                agenda_item="Oe 7",
                source_available=True,
            )
        ],
    )
    structured = StructuredAnalysisOutput(job_id=1, session_id="7123")

    assert raw.to_dict()["schema_version"] == "2.0"
    assert raw.to_dict()["output_type"] == "raw_analysis"
    assert raw.to_dict()["documents"][0]["source_available"] is True
    assert structured.to_dict()["output_type"] == "structured_analysis"
    assert structured.purpose == DEFAULT_ANALYSIS_PURPOSE


def test_publication_draft_contains_review_and_publication_status() -> None:
    draft = PublicationDraftOutput(job_id=1, session_id="7123", title="Titel")
    payload = draft.to_dict()

    assert payload["purpose"] == "journalistic_publication"
    assert payload["status"] == "draft"
    assert payload["review"]["required"] is True
    assert payload["review"]["status"] == "pending"
    assert payload["publication"]["target"] == "local_static_site"
    assert payload["publication"]["status"] == "not_published"


def test_normalize_v1_analysis_output_keeps_legacy_fields() -> None:
    normalized = normalize_analysis_output(
        {
            "schema_version": "1.0",
            "job_id": 4,
            "session_id": "7123",
            "scope": "tops",
            "top_numbers": ["Oe 7"],
            "ki_response": "Antwort",
            "markdown": "# Analyse",
            "status": "done",
            "session_date": "2026-03-11",
            "session_path": "data/raw/2026/03/2026-03-11_Rat_7123",
        }
    )

    assert normalized["output_type"] == "legacy_analysis_output"
    assert normalized["purpose"] == DEFAULT_ANALYSIS_PURPOSE
    assert normalized["job_id"] == 4
    assert normalized["top_numbers"] == ["Oe 7"]
    assert normalized["ki_response"] == "Antwort"


def test_normalize_v1_analysis_output_tolerates_missing_optional_fields() -> None:
    normalized = normalize_analysis_output({"schema_version": "1.0", "job_id": 1})

    assert normalized["job_id"] == 1
    assert normalized["session_id"] == ""
    assert normalized["top_numbers"] == []
    assert normalized["markdown"] == ""
