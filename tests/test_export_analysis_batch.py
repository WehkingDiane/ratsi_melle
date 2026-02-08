from __future__ import annotations

import json
from pathlib import Path

from scripts import build_local_index, export_analysis_batch


def _write_fixture(root: Path) -> None:
    session_dir = root / "2025" / "2025-09-18_Rat_901"
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "session-documents").mkdir(parents=True, exist_ok=True)
    (session_dir / "agenda" / "o1").mkdir(parents=True, exist_ok=True)

    (session_dir / "session_detail.html").write_text("<html></html>", encoding="utf-8")
    (session_dir / "agenda_summary.json").write_text(
        json.dumps(
            {
                "session": {"id": "901", "committee": "Rat", "meeting_name": "Ratssitzung", "date": "2025-09-18"},
                "generated_at": "2025-09-18T10:00:00Z",
                "agenda_items": [
                    {
                        "number": "Ö 1",
                        "title": "Haushalt",
                        "reporter": "Kämmerei",
                        "status": "beschlossen",
                        "decision": "accepted",
                        "documents_present": True,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (session_dir / "manifest.json").write_text(
        json.dumps(
            {
                "session": {
                    "id": "901",
                    "committee": "Rat",
                    "meeting_name": "Ratssitzung",
                    "date": "2025-09-18",
                    "detail_url": "https://example.org/si0057.asp?__ksinr=901",
                    "location": "Rathaus",
                },
                "retrieved_at": "2025-09-18T10:00:00Z",
                "documents": [
                    {
                        "title": "Protokoll öffentlich",
                        "category": "PR",
                        "agenda_item": None,
                        "url": "https://example.org/protokoll.pdf",
                        "path": "session-documents/protokoll.pdf",
                        "sha1": "sha-proto",
                        "content_type": "application/pdf",
                        "content_length": 500,
                    },
                    {
                        "title": "Beschlussvorlage Haushalt",
                        "category": "BV",
                        "agenda_item": "Ö 1",
                        "url": "https://example.org/beschluss.pdf",
                        "path": "agenda/o1/beschluss.pdf",
                        "sha1": "sha-bv",
                        "content_type": "application/pdf",
                        "content_length": 1200,
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (session_dir / "session-documents" / "protokoll.pdf").write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /Contents 4 0 R >> endobj\n"
        b"4 0 obj << /Length 120 >> stream\n"
        b"BT /F1 12 Tf 72 700 Td (Protokolltext fuer Analyse Export mit ausreichend Textumfang fuer Qualitaet.) Tj ET\n"
        b"endstream endobj\n"
        b"trailer << /Root 1 0 R >>\n"
        b"%%EOF\n"
    )
    (session_dir / "agenda" / "o1" / "beschluss.pdf").write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /Contents 4 0 R >> endobj\n"
        b"4 0 obj << /Length 118 >> stream\n"
        b"BT /F1 12 Tf 72 700 Td (Beschlussvorlage mit Freigabetext und Basisdaten zur KI-Auswertung.) Tj ET\n"
        b"endstream endobj\n"
        b"trailer << /Root 1 0 R >>\n"
        b"%%EOF\n"
    )


def _build_db(tmp_path: Path) -> Path:
    data_root = tmp_path / "data" / "raw"
    _write_fixture(data_root)
    db_path = tmp_path / "data" / "processed" / "local_index.sqlite"
    build_local_index.build_index(data_root, db_path, refresh_existing=False, only_refresh=False)
    return db_path


def test_export_analysis_batch_writes_expected_payload(tmp_path: Path) -> None:
    db_path = _build_db(tmp_path)
    output_path = tmp_path / "data" / "processed" / "analysis_batch.json"

    count = export_analysis_batch.export_analysis_batch(
        db_path,
        output_path,
        session_ids=["901"],
        document_types=["protokoll", "beschlussvorlage"],
        require_local_path=True,
    )

    assert count == 2
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert payload["source_db"] == str(db_path)
    assert payload["filters"]["session_ids"] == ["901"]
    assert payload["filters"]["document_types"] == ["beschlussvorlage", "protokoll"]

    docs = payload["documents"]
    assert len(docs) == 2
    assert docs[0]["session_id"] == "901"
    assert docs[0]["retrieved_at"] == "2025-09-18T10:00:00Z"
    assert {entry["document_type"] for entry in docs} == {"protokoll", "beschlussvorlage"}
    assert any(entry["top_number"] == "Ö 1" and entry["top_title"] == "Haushalt" for entry in docs)


def test_normalize_document_types_rejects_unknown_values() -> None:
    try:
        export_analysis_batch._normalize_document_types(["foo"])
    except ValueError as exc:
        assert "Unsupported document type" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected ValueError for unsupported document type")


def test_export_analysis_batch_includes_text_extraction(tmp_path: Path) -> None:
    db_path = _build_db(tmp_path)
    output_path = tmp_path / "data" / "processed" / "analysis_batch_with_text.json"

    count = export_analysis_batch.export_analysis_batch(
        db_path,
        output_path,
        session_ids=["901"],
        include_text_extraction=True,
        max_text_chars=10_000,
    )

    assert count == 2
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["filters"]["include_text_extraction"] is True
    assert payload["filters"]["max_text_chars"] == 10_000

    docs = payload["documents"]
    assert len(docs) == 2
    for entry in docs:
        assert entry["extraction_status"] in {"ok", "partial"}
        assert entry["parsing_quality"] in {"low", "medium", "high"}
        assert entry["extracted_char_count"] > 0
        assert entry["resolved_local_path"]
        assert entry["extraction_pipeline_version"] == "1.0"
        assert isinstance(entry["extracted_at"], str)
