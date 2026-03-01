"""Helpers for current and legacy raw storage layouts."""

from __future__ import annotations

import re
from pathlib import Path


SESSION_DIR_RE = re.compile(r"^\d{4}-(\d{2})-\d{2}[-_].+$")


def resolve_local_file_path(*, session_path: str | None, local_path: str | None) -> Path | None:
    """Resolve a local document path for current and legacy raw-data layouts."""

    normalized_local = (local_path or "").strip()
    if not normalized_local:
        return None
    normalized_local = normalized_local.replace("\\", "/")

    candidate = Path(normalized_local)
    if candidate.is_absolute():
        return candidate

    normalized_session = (session_path or "").strip()
    if not normalized_session:
        return candidate
    normalized_session = normalized_session.replace("\\", "/")

    base = Path(normalized_session)
    resolved = base / candidate
    if resolved.exists():
        return resolved

    migrated_base = upgrade_legacy_session_path(base)
    if migrated_base is not None:
        migrated_resolved = migrated_base / candidate
        if migrated_resolved.exists():
            return migrated_resolved

    return resolved


def upgrade_legacy_session_path(path: Path) -> Path | None:
    """Insert the month segment for a legacy session path if it can be derived."""

    if len(path.parts) < 2:
        return None

    if path.parent.name.isdigit() and len(path.parent.name) == 2:
        return path

    year_dir = path.parent
    if not year_dir.name.isdigit() or len(year_dir.name) != 4:
        return None

    month = _extract_month_from_name(path.name)
    if month is None:
        return None
    return year_dir / month / path.name


def _extract_month_from_name(name: str) -> str | None:
    match = SESSION_DIR_RE.match(name)
    if match:
        return match.group(1)

    overview_match = re.match(r"^\d{4}-(\d{2})_overview\.html$", name)
    if overview_match:
        return overview_match.group(1)

    return None
