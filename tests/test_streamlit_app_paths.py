from __future__ import annotations

from pathlib import Path

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
