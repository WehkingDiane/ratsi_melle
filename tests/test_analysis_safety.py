from __future__ import annotations

from pathlib import Path

from src.analysis.safety import (
    derive_bias_metrics,
    derive_plausibility_flags,
    derive_uncertainty_flags,
    estimate_hallucination_risk,
    hash_document,
    mask_document_for_analysis,
    mask_sensitive_text,
)


def test_mask_sensitive_text_masks_email_phone_and_iban() -> None:
    masked, changed = mask_sensitive_text("Kontakt: test@example.org, +4915112345678, DE89370400440532013000")
    assert changed is True
    assert "test@example.org" not in masked
    assert "+4915112345678" not in masked
    assert "DE89370400440532013000" not in masked
    assert "[EMAIL_MASKED]" in masked
    assert "[PHONE_MASKED]" in masked
    assert "[IBAN_MASKED]" in masked


def test_hash_document_prefers_local_file_bytes(tmp_path: Path) -> None:
    file_path = tmp_path / "doc.txt"
    file_path.write_text("abc", encoding="utf-8")
    hashed = hash_document({"resolved_local_path": str(file_path)})
    assert hashed["source"] == str(file_path)
    assert len(hashed["sha256"]) == 64


def test_mask_document_for_analysis_masks_title_and_structured_fields() -> None:
    masked_doc, changed = mask_document_for_analysis(
        {
            "title": "Kontakt max@example.org",
            "structured_fields": {"begruendung": "Rueckruf unter 015112345678"},
        }
    )
    assert changed is True
    assert "[EMAIL_MASKED]" in str(masked_doc["title"])
    assert "[PHONE_MASKED]" in str(masked_doc["structured_fields"]["begruendung"])


def test_uncertainty_and_risk_flags() -> None:
    documents = [{"extraction_status": "ocr_needed", "content_parser_quality": "low"}]
    flags = derive_uncertainty_flags(documents)
    assert "source_ocr_needed" in flags
    assert "parser_low" in flags
    assert estimate_hallucination_risk(documents, flags) in {"high", "medium"}


def test_plausibility_flags_detect_conflicts_and_missing_financial_evidence() -> None:
    documents = [
        {
            "structured_fields": {
                "entscheidung": "angenommen",
                "zustaendigkeit": "Rat",
            },
            "extracted_text": "Kurztext",
        },
        {
            "structured_fields": {
                "entscheidung": "vertagt",
                "zustaendigkeit": "Ausschuss",
            },
            "extracted_text": "Auch kurz.",
        },
    ]

    flags = derive_plausibility_flags(documents, "financial_impact")

    assert "conflicting_decision_signals" in flags
    assert "conflicting_responsibility_signals" in flags
    assert "missing_financial_evidence" in flags
    assert "limited_source_context" in flags


def test_bias_metrics_describe_source_balance() -> None:
    metrics = derive_bias_metrics(
        [
            {"document_type": "vorlage", "agenda_item": "Oe 1", "structured_fields": {"entscheidung": "a"}},
            {"document_type": "protokoll", "agenda_item": "Oe 2", "structured_fields": {"entscheidung": "b"}},
        ]
    )

    assert metrics["document_count"] == 2
    assert metrics["document_type_diversity"] == 2
    assert metrics["source_balance"] == "mixed_sources"
    assert metrics["evidence_balance"] in {"moderate", "broad"}
