"""Source availability checks for indexed sessions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import paths
from .db import first_row
from .db import rows


def check_sources(session_id: str) -> dict[str, Any]:
    """Return lightweight source availability information for a session."""

    session = first_row(
        paths.LOCAL_INDEX_DB,
        "SELECT session_path FROM sessions WHERE session_id = ?",
        (session_id,),
    )
    documents = rows(
        paths.LOCAL_INDEX_DB,
        "SELECT local_path FROM documents WHERE session_id = ?",
        (session_id,),
    )
    session_path = Path(str(session.get("session_path") or "")) if session else None
    available = 0
    missing = 0
    for document in documents:
        local_path = str(document.get("local_path") or "")
        candidates = []
        if local_path:
            candidates.append(paths.REPO_ROOT / local_path)
            if session_path and not Path(local_path).is_absolute():
                candidates.append(session_path / local_path)
        if any(path.exists() for path in candidates):
            available += 1
        else:
            missing += 1
    return {
        "session_path": str(session_path or ""),
        "document_count": len(documents),
        "available_count": available,
        "missing_count": missing,
    }
