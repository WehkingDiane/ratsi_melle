"""Helpers for enforcing and migrating the repository data directory layout."""

from __future__ import annotations

import shutil
from pathlib import Path

from src.paths import DB_DIR, LOCAL_INDEX_DB, ONLINE_INDEX_DB, PROCESSED_DATA_DIR


def migrate_legacy_database_layout() -> list[tuple[Path, Path]]:
    """Move legacy SQLite databases from data/processed to data/db once."""

    mappings = [
        (PROCESSED_DATA_DIR / "local_index.sqlite", LOCAL_INDEX_DB),
        (PROCESSED_DATA_DIR / "online_session_index.sqlite", ONLINE_INDEX_DB),
    ]
    moved: list[tuple[Path, Path]] = []
    DB_DIR.mkdir(parents=True, exist_ok=True)
    for old_path, new_path in mappings:
        if not old_path.exists() or new_path.exists():
            continue
        new_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_path), str(new_path))
        moved.append((old_path, new_path))
    return moved
