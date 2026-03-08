"""Safety helpers for masking and quality signals in analysis outputs."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path


_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"(?<!\w)(?:\+49|0)[0-9][0-9\s/\-]{6,}[0-9]\b")
_IBAN_RE = re.compile(r"\bDE[0-9A-Z]{20}\b")


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


def estimate_hallucination_risk(documents: list[dict], uncertainty_flags: list[str]) -> str:
    """Estimate hallucination risk from available evidence quality."""

    if not documents:
        return "high"
    if any(flag.startswith("source_") for flag in uncertainty_flags):
        return "high"
    if any(flag == "parser_low" for flag in uncertainty_flags):
        return "medium"
    return "low"
