"""Safety helpers for masking and quality signals in analysis outputs."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path


_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"(?<!\w)(?:\+49|0)[0-9][0-9\s/\-]{6,}[0-9]\b")
_IBAN_RE = re.compile(r"\bDE[0-9A-Z]{20}\b")
_MONEY_RE = re.compile(r"\b\d[\d.,\s]*\s*(?:EUR|Euro)\b", re.IGNORECASE)


def mask_sensitive_text(value: str) -> tuple[str, bool]:
    """Mask common sensitive tokens (email, phone, IBAN) from free text."""

    masked = value
    changed = False
    for pattern, replacement in (
        (_EMAIL_RE, "[EMAIL_MASKED]"),
        (_PHONE_RE, "[PHONE_MASKED]"),
        (_IBAN_RE, "[IBAN_MASKED]"),
    ):
        updated = pattern.sub(replacement, masked)
        if updated != masked:
            changed = True
        masked = updated
    return masked, changed


def mask_document_for_analysis(document: dict) -> tuple[dict, bool]:
    """Return a masked document copy suitable for safe AI prompting/output."""

    entry = dict(document)
    changed = False
    for field_name in ("title", "extracted_text"):
        value = entry.get(field_name)
        if isinstance(value, str) and value:
            masked, field_changed = mask_sensitive_text(value)
            entry[field_name] = masked
            changed = changed or field_changed

    fields = entry.get("structured_fields")
    if isinstance(fields, dict):
        updated_fields: dict[str, object] = {}
        for key, value in fields.items():
            if isinstance(value, str):
                masked, field_changed = mask_sensitive_text(value)
                updated_fields[key] = masked
                changed = changed or field_changed
            else:
                updated_fields[key] = value
        entry["structured_fields"] = updated_fields
    return entry, changed


def hash_document(document: dict) -> dict[str, str]:
    """Compute a stable source hash from local file bytes or source identifiers."""

    source_ref = ""
    resolved_local_path = document.get("resolved_local_path")
    if isinstance(resolved_local_path, str) and resolved_local_path.strip():
        source_ref = resolved_local_path
        path = Path(resolved_local_path)
        if path.exists() and path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            return {"source": source_ref, "sha256": digest}

    url = document.get("url")
    if isinstance(url, str) and url.strip():
        source_ref = url.strip()
    else:
        local_path = document.get("local_path")
        source_ref = str(local_path) if local_path else "unknown"

    digest = hashlib.sha256(source_ref.encode("utf-8")).hexdigest()
    return {"source": source_ref, "sha256": digest}


def derive_uncertainty_flags(documents: list[dict]) -> list[str]:
    """Create uncertainty markers based on extraction and parser quality."""

    flags: set[str] = set()
    for document in documents:
        extraction_status = str(document.get("extraction_status") or "")
        parser_quality = str(document.get("content_parser_quality") or "")
        if extraction_status in {"missing_file", "ocr_needed", "error"}:
            flags.add(f"source_{extraction_status}")
        if parser_quality in {"failed", "low"}:
            flags.add(f"parser_{parser_quality}")
    if not documents:
        flags.add("no_documents")
    return sorted(flags)


def derive_plausibility_flags(documents: list[dict], mode: str) -> list[str]:
    """Return deterministic plausibility flags derived from structured evidence."""

    flags: set[str] = set()
    if not documents:
        return ["no_documents"]

    structured_docs = [doc for doc in documents if isinstance(doc.get("structured_fields"), dict)]
    if not structured_docs:
        flags.add("missing_structured_evidence")

    decision_values = _distinct_structured_values(structured_docs, "entscheidung", "beschlusstext")
    responsibility_values = _distinct_structured_values(structured_docs, "zustaendigkeit")
    if len(decision_values) > 1:
        flags.add("conflicting_decision_signals")
    if len(responsibility_values) > 1:
        flags.add("conflicting_responsibility_signals")

    if mode == "decision_brief" and not _has_structured_evidence(structured_docs, "entscheidung", "beschlusstext", "zustaendigkeit"):
        flags.add("missing_decision_evidence")
    if mode == "financial_impact" and not _has_financial_evidence(documents):
        flags.add("missing_financial_evidence")

    for document in documents:
        extracted_text = str(document.get("extracted_text") or "")
        if extracted_text and len(extracted_text.strip()) < 80:
            flags.add("limited_source_context")
            break

    return sorted(flags)


def derive_bias_metrics(documents: list[dict]) -> dict[str, object]:
    """Estimate simple evidence-balance metrics for review and auditing."""

    total_documents = len(documents)
    if total_documents == 0:
        return {
            "document_count": 0,
            "document_type_diversity": 0,
            "dominant_document_type_share": 0.0,
            "source_balance": "no_sources",
            "evidence_balance": "insufficient",
        }

    type_counts: dict[str, int] = {}
    agenda_items: set[str] = set()
    structured_docs = 0
    for document in documents:
        doc_type = str(document.get("document_type") or "unknown")
        type_counts[doc_type] = type_counts.get(doc_type, 0) + 1
        agenda_item = str(document.get("agenda_item") or "").strip()
        if agenda_item:
            agenda_items.add(agenda_item)
        if isinstance(document.get("structured_fields"), dict) and document["structured_fields"]:
            structured_docs += 1

    dominant_share = max(type_counts.values()) / total_documents
    if total_documents == 1:
        source_balance = "single_document"
    elif dominant_share >= 0.8:
        source_balance = "type_dominated"
    else:
        source_balance = "mixed_sources"

    evidence_ratio = structured_docs / total_documents
    if evidence_ratio >= 0.75 and len(agenda_items) > 1:
        evidence_balance = "broad"
    elif evidence_ratio >= 0.5:
        evidence_balance = "moderate"
    else:
        evidence_balance = "thin"

    return {
        "document_count": total_documents,
        "document_type_diversity": len(type_counts),
        "dominant_document_type": max(type_counts, key=type_counts.get),
        "dominant_document_type_share": round(dominant_share, 2),
        "source_balance": source_balance,
        "agenda_item_coverage": len(agenda_items),
        "structured_data_coverage": round(evidence_ratio, 2),
        "evidence_balance": evidence_balance,
    }


def estimate_hallucination_risk(
    documents: list[dict],
    uncertainty_flags: list[str],
    plausibility_flags: list[str] | None = None,
) -> str:
    """Estimate hallucination risk from available evidence quality."""

    plausibility_flags = plausibility_flags or []
    if not documents:
        return "high"
    if any(flag.startswith("source_") for flag in uncertainty_flags):
        return "high"
    if any(flag in {"parser_failed"} for flag in uncertainty_flags):
        return "high"
    if any(flag in {"missing_structured_evidence", "missing_financial_evidence"} for flag in plausibility_flags):
        return "high"
    if any(flag.startswith("conflicting_") for flag in plausibility_flags):
        return "medium"
    if any(flag == "parser_low" for flag in uncertainty_flags):
        return "medium"
    return "low"


def _distinct_structured_values(documents: list[dict], *keys: str) -> set[str]:
    values: set[str] = set()
    for document in documents:
        fields = document.get("structured_fields")
        if not isinstance(fields, dict):
            continue
        for key in keys:
            value = fields.get(key)
            if isinstance(value, str) and value.strip():
                values.add(" ".join(value.split()))
    return values


def _has_structured_evidence(documents: list[dict], *keys: str) -> bool:
    return bool(_distinct_structured_values(documents, *keys))


def _has_financial_evidence(documents: list[dict]) -> bool:
    for document in documents:
        fields = document.get("structured_fields")
        if isinstance(fields, dict):
            finanzbezug = fields.get("finanzbezug")
            if isinstance(finanzbezug, str) and finanzbezug.strip():
                return True
        extracted_text = str(document.get("extracted_text") or "")
        if _MONEY_RE.search(extracted_text):
            return True
    return False
