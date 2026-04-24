"""Helpers for current and legacy raw storage layouts."""

from __future__ import annotations

import re
from pathlib import Path

from src.paths import RAW_DATA_DIR, REPO_ROOT


SESSION_DIR_RE = re.compile(r"^\d{4}-(\d{2})-\d{2}[-_].+$")


def resolve_local_file_path(*, session_path: str | None, local_path: str | None) -> Path | None:
    """Resolve a local document path for current and legacy raw-data layouts."""

    normalized_local = (local_path or "").strip()
    if not normalized_local:
        return None
    normalized_local = normalized_local.replace("\\", "/")

    candidate = Path(normalized_local)
    normalized_session = (session_path or "").strip()
    base = _normalized_session_path(normalized_session)
    allowed_roots = _allowed_raw_roots(base)

    if candidate.is_absolute():
        resolved_absolute = _safe_resolve(candidate)
        if resolved_absolute is None:
            return None
        return resolved_absolute if _is_within_allowed_roots(resolved_absolute, allowed_roots) else None

    if base is None:
        return None

    resolved = _safe_resolve(base / candidate)
    if resolved is None:
        return None
    if _is_within_allowed_roots(resolved, allowed_roots) and resolved.exists():
        return resolved

    migrated_base = upgrade_legacy_session_path(base)
    if migrated_base is not None:
        migrated_resolved = _safe_resolve(migrated_base / candidate)
        if migrated_resolved is None:
            return None
        if _is_within_allowed_roots(migrated_resolved, allowed_roots) and migrated_resolved.exists():
            return migrated_resolved

    return resolved if _is_within_allowed_roots(resolved, allowed_roots) else None


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


def _normalized_session_path(session_path: str) -> Path | None:
    if not session_path:
        return None
    normalized = session_path.replace("\\", "/")
    path = Path(normalized)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return _safe_resolve(path)


def _allowed_raw_roots(base: Path | None) -> tuple[Path, ...]:
    raw_root = _safe_resolve(RAW_DATA_DIR)
    roots: list[Path] = [raw_root] if raw_root is not None else []
    if base is not None:
        derived = _derive_raw_root(base)
        if derived is not None and derived not in roots:
            roots.append(derived)
    return tuple(roots)


def _derive_raw_root(path: Path) -> Path | None:
    parts = path.parts
    for index in range(len(parts) - 1):
        if parts[index] == "data" and parts[index + 1] == "raw":
            return _safe_resolve(Path(*parts[: index + 2]))
    return None


def _is_within_allowed_roots(path: Path, roots: tuple[Path, ...]) -> bool:
    return any(_is_relative_to(path, root) for root in roots)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _safe_resolve(path: Path) -> Path | None:
    try:
        return path.resolve(strict=False)
    except (OSError, RuntimeError):
        return None
