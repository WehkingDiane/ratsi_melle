"""Legacy Streamlit path helper compatibility tests.

The active UI path is the Django application under ``web/``. These tests remain
only while deprecated Streamlit helpers are still shipped.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.legacy_ui
pytest.importorskip("streamlit")

from src.interfaces.web.streamlit_app import _existing_local_document_path, _local_document_policy_text


def test_existing_local_document_path_resolves_session_relative_pdf(tmp_path: Path) -> None:
    session_dir = tmp_path / "data" / "raw" / "2025" / "09" / "2025-09-18_Rat_901"
    pdf_path = session_dir / "session-documents" / "protokoll.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"pdf")

    resolved = _existing_local_document_path(
        session_path=str(session_dir),
        local_path="session-documents/protokoll.pdf",
    )

    assert resolved == pdf_path


def test_existing_local_document_path_rejects_missing_file() -> None:
    resolved = _existing_local_document_path(
        session_path="data/raw/2025/09/2025-09-18_Rat_901",
        local_path="session-documents/fehlend.pdf",
    )

    assert resolved is None


def test_existing_local_document_path_rejects_absolute_path_outside_raw_root(tmp_path: Path) -> None:
    outside_file = tmp_path / "outside.pdf"
    outside_file.write_bytes(b"pdf")

    resolved = _existing_local_document_path(local_path=str(outside_file))

    assert resolved is None


def test_local_document_policy_text_mentions_security_constraints() -> None:
    text = _local_document_policy_text()

    assert "data/raw/" in text
    assert "25 MiB" in text


def test_existing_local_document_path_returns_none_when_resolve_fails(tmp_path: Path) -> None:
    session_dir = tmp_path / "data" / "raw" / "2025" / "09" / "2025-09-18_Rat_901"
    session_dir.mkdir(parents=True, exist_ok=True)
    target = session_dir / "session-documents" / "loop.pdf"
    original_resolve = Path.resolve

    def fake_resolve(self: Path, *args, **kwargs):  # type: ignore[no-untyped-def]
        if self == target:
            raise RuntimeError("symlink loop")
        return original_resolve(self, *args, **kwargs)

    with patch.object(Path, "resolve", fake_resolve):
        resolved = _existing_local_document_path(
            session_path=str(session_dir),
            local_path="session-documents/loop.pdf",
        )

    assert resolved is None
