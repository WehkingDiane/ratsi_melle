from __future__ import annotations

from pathlib import Path

from src.interfaces.web.streamlit_app import _existing_local_document_path


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
