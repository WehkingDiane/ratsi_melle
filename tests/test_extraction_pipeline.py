from __future__ import annotations

from pathlib import Path

from src.analysis.extraction_pipeline import extract_text_for_analysis


def test_extract_text_for_analysis_pdf_ok(tmp_path: Path) -> None:
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /Contents 4 0 R >> endobj\n"
        b"4 0 obj << /Length 96 >> stream\n"
        b"BT /F1 12 Tf 72 700 Td (Dies ist ein laengerer Testtext fuer die PDF Extraktion.) Tj ET\n"
        b"endstream endobj\n"
        b"trailer << /Root 1 0 R >>\n"
        b"%%EOF\n"
    )

    result = extract_text_for_analysis(
        pdf_path,
        content_type="application/pdf",
        max_text_chars=10_000,
    )

    assert result.extraction_status in {"ok", "partial"}
    assert "PDF Extraktion" in result.extracted_text
    assert result.extracted_char_count > 0
    assert result.ocr_needed is False
    assert result.page_texts
    assert result.page_texts[0]["page"] == 1


def test_extract_text_for_analysis_pdf_ocr_needed(tmp_path: Path) -> None:
    pdf_path = tmp_path / "scan.pdf"
    pdf_path.write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /Contents 4 0 R >> endobj\n"
        b"4 0 obj << /Length 15 >> stream\n"
        b"q 0 0 10 10 cm\n"
        b"endstream endobj\n"
        b"trailer << /Root 1 0 R >>\n"
        b"%%EOF\n"
    )

    result = extract_text_for_analysis(
        pdf_path,
        content_type="application/pdf",
        max_text_chars=10_000,
    )

    assert result.extraction_status == "ocr_needed"
    assert result.parsing_quality == "low"
    assert result.extracted_char_count == 0
    assert result.ocr_needed is True
    assert result.page_texts == []
    assert result.detected_sections == []


def test_extract_text_for_analysis_missing_file() -> None:
    result = extract_text_for_analysis(
        Path("/tmp/does-not-exist.pdf"),
        content_type="application/pdf",
        max_text_chars=10_000,
    )

    assert result.extraction_status == "missing_file"
    assert result.parsing_quality == "failed"
    assert result.page_texts == []
    assert result.detected_sections == []


def test_extract_text_for_analysis_pdf_ignores_unterminated_literal(tmp_path: Path) -> None:
    pdf_path = tmp_path / "broken.pdf"
    pdf_path.write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /Contents 4 0 R >> endobj\n"
        b"4 0 obj << /Length 24 >> stream\n"
        b"BT (Unvollstaendig ET\n"
        b"endstream endobj\n"
        b"trailer << /Root 1 0 R >>\n"
        b"%%EOF\n"
    )

    result = extract_text_for_analysis(
        pdf_path,
        content_type="application/pdf",
        max_text_chars=10_000,
    )

    assert result.extraction_status == "ocr_needed"
    assert result.extracted_text == ""
    assert result.extracted_char_count == 0


def test_extract_text_for_analysis_pdf_keeps_nested_parentheses(tmp_path: Path) -> None:
    pdf_path = tmp_path / "nested.pdf"
    pdf_path.write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /Contents 4 0 R >> endobj\n"
        b"4 0 obj << /Length 88 >> stream\n"
        b"BT (Text mit (Klammern) bleibt erhalten.) Tj ET\n"
        b"endstream endobj\n"
        b"trailer << /Root 1 0 R >>\n"
        b"%%EOF\n"
    )

    result = extract_text_for_analysis(
        pdf_path,
        content_type="application/pdf",
        max_text_chars=10_000,
    )

    assert result.extraction_status in {"ok", "partial"}
    assert "Text mit (Klammern) bleibt erhalten." in result.extracted_text


def test_extract_text_for_analysis_pdf_tracks_pages_and_sections(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sections.pdf"
    pdf_path.write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /Contents 4 0 R >> endobj\n"
        b"4 0 obj << /Length 120 >> stream\n"
        b"BT (Beschlussvorschlag: Der Rat beschliesst den Ausbau.) Tj ET\n"
        b"endstream endobj\n"
        b"5 0 obj << /Type /Page /Parent 2 0 R /Contents 6 0 R >> endobj\n"
        b"6 0 obj << /Length 135 >> stream\n"
        b"BT (Finanzielle Auswirkungen: 50.000 EUR im Haushalt 2026.) Tj ET\n"
        b"endstream endobj\n"
        b"trailer << /Root 1 0 R >>\n"
        b"%%EOF\n"
    )

    result = extract_text_for_analysis(
        pdf_path,
        content_type="application/pdf",
        max_text_chars=10_000,
    )

    assert result.page_count == 2
    assert [entry["page"] for entry in result.page_texts] == [1, 2]
    assert any(section["heading"].lower().startswith("beschluss") for section in result.detected_sections)
    assert any(section["heading"].lower().startswith("finanz") for section in result.detected_sections)
