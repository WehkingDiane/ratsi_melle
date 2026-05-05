"""Stable document ID strategy for Qdrant points."""

from __future__ import annotations

import hashlib


def stable_document_id(session_id: str, url: str, agenda_item: str = "") -> int:
    """Derive the stable Qdrant integer ID for one document reference."""
    key = f"{session_id or ''}|{url or ''}|{agenda_item or ''}"
    return int(hashlib.md5(key.encode()).hexdigest()[:16], 16)
