"""Offline regression workflows using copied real municipal PDF documents."""

from hashlib import sha256
import json
import os
from pathlib import Path
import re
from types import SimpleNamespace
import unicodedata

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
import pytest

from src.analysis import extraction_pipeline
from src.indexing import passages


pytestmark = pytest.mark.integration
FIXTURES = Path(__file__).parent / "fixtures" / "pdf"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
CASES = MANIFEST["fixtures"]
READABLE = [case for case in CASES if case["page_count"] is not None]


def normalized(text):
    """Ignore layout whitespace while retaining words, punctuation and Unicode."""
    return " ".join(unicodedata.normalize("NFKC", text).split())


class WhitespaceTokenizer:
    """Measure deterministic test tokens without downloading a model."""

    def __call__(self, text, **kwargs):
        return {"offset_mapping": [match.span() for match in re.finditer(r"\S+", text)]}


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["file"])
def test_fixture_matches_documented_original_or_derivation(case):
    raw = (FIXTURES / case["file"]).read_bytes()
    assert len(raw) == case["bytes"]
    assert sha256(raw).hexdigest() == case["sha256"]
    if "source_sha256" in case:
        assert case["sha256"] == case["source_sha256"]
        assert case["source_path"].startswith("data/raw/")
        assert case["source_url"].startswith("https://session.melle.info/")
    else:
        assert case["derived_from"] and case["transformation"]


@pytest.mark.parametrize("case", READABLE, ids=lambda case: case["file"])
def test_search_extracts_original_page_content_and_unicode(case):
    pages = passages.extract_pages(FIXTURES / case["file"], use_ocr=False)
    assert [page["page"] for page in pages] == list(range(1, case["page_count"] + 1))
    assert [page["page"] for page in pages if not page["text"]] == case["expected_empty_pages"]
    for page in pages:
        assert page["method"] == ("ocr_needed" if page["page"] in case["expected_empty_pages"] else "text")
    for number, anchors in case["expected_page_text"].items():
        text = normalized(pages[int(number) - 1]["text"])
        for anchor in anchors:
            assert normalized(anchor) in text


@pytest.mark.parametrize("case", READABLE, ids=lambda case: case["file"])
def test_passages_cover_original_text_without_losing_pages(case):
    pages = passages.extract_pages(FIXTURES / case["file"], use_ocr=False)
    chunks = passages.chunk_pages(pages, WhitespaceTokenizer(), tokens=64, overlap=12)
    assert {chunk["page_start"] for chunk in chunks} == {page["page"] for page in pages if page["text"]}
    for page in pages:
        pieces = [chunk for chunk in chunks if chunk["page_start"] == page["page"]]
        if not page["text"]:
            assert not pieces
            continue
        covered_end = 0
        for piece in pieces:
            assert piece["page_end"] == page["page"]
            assert piece["extraction_method"] == "text"
            assert 0 < piece["token_count"] <= 64
            assert piece["char_start"] <= covered_end
            assert piece["text"] == page["text"][piece["char_start"]:piece["char_end"]]
            covered_end = max(covered_end, piece["char_end"])
        assert covered_end == len(page["text"])
    if case["file"] == "council_rules.pdf":
        assert len(chunks) > case["page_count"]
        assert any(chunk["page_start"] == 10 and "Inkrafttreten" in chunk["text"] for chunk in chunks)


def test_real_mixed_pdf_routes_only_the_scan_page_to_ocr(monkeypatch):
    path = FIXTURES / "mixed_text_scan.pdf"
    calls = []

    def ocr(source, page):
        calls.append((source, page))
        return "Übersicht über unsere Lösungen und Preise"

    monkeypatch.setattr(passages, "ocr_page", ocr)
    pages = passages.extract_pages(path)
    assert calls == [(path, 2)]
    assert "Beschlussvorlage" in pages[0]["text"] and pages[0]["method"] == "text"
    assert pages[1] == {"page": 2, "text": "Übersicht über unsere Lösungen und Preise", "method": "ocr"}


def test_truncated_original_is_rejected_by_search():
    with pytest.raises(PdfReadError):
        passages.extract_pages(FIXTURES / "truncated_proposal.pdf", use_ocr=False)


@pytest.mark.parametrize("case", [case for case in READABLE if case["expected_page_text"] and not case["expected_empty_pages"]],
                         ids=lambda case: case["file"])
def test_analysis_preserves_real_words_numbers_and_page_mapping(case, monkeypatch):
    monkeypatch.setattr(extraction_pipeline, "_extract_text_via_ocr",
                        lambda path: pytest.fail("A readable text layer must not require OCR"))
    result = extraction_pipeline.extract_text_for_analysis(
        FIXTURES / case["file"], content_type="application/pdf", max_text_chars=100000)
    assert result.extraction_status == "ok" and not result.ocr_needed
    assert result.page_count == case["page_count"]
    by_page = {page["page"]: normalized(page["text"]) for page in result.page_texts}
    for number, anchors in case["expected_page_text"].items():
        for anchor in anchors:
            assert normalized(anchor) in by_page[int(number)]
    if case["file"] == "budget_proposal.pdf":
        assert any(section["page"] == 1 and "Beschlussvorschlag" in section["heading"]
                   for section in result.detected_sections)


def test_analysis_does_not_interpret_scan_image_bytes_as_text(monkeypatch):
    path = FIXTURES / "scanned_price_table.pdf"
    calls = []
    monkeypatch.setattr(extraction_pipeline, "_extract_text_via_ocr", lambda source: calls.append(source) or [])
    result = extraction_pipeline.extract_text_for_analysis(path, content_type="application/pdf", max_text_chars=10000)
    assert calls == [path]
    assert result.extraction_status == "ocr_needed" and result.ocr_needed
    assert result.page_count == 1
    assert result.extracted_text == "" and result.extracted_char_count == 0
    assert result.page_texts == [{"page": 1, "text": "", "char_count": 0}]


def test_analysis_returns_controlled_error_for_truncated_original(monkeypatch):
    monkeypatch.setattr(extraction_pipeline, "_extract_text_via_ocr",
                        lambda path: pytest.fail("An unreadable PDF must not be submitted to OCR"))
    result = extraction_pipeline.extract_text_for_analysis(
        FIXTURES / "truncated_proposal.pdf", content_type="application/pdf", max_text_chars=10000)
    assert result.extraction_status == "error" and result.extraction_error
    assert not result.extracted_text and not result.page_texts and not result.ocr_needed


def test_analysis_limits_long_original_text_without_losing_page_evidence(monkeypatch):
    monkeypatch.setattr(extraction_pipeline, "_extract_text_via_ocr", lambda path: [])
    result = extraction_pipeline.extract_text_for_analysis(
        FIXTURES / "council_rules.pdf", content_type="application/pdf", max_text_chars=1000)
    assert result.extracted_char_count == len(result.extracted_text) == 1000
    assert result.page_count == 10
    assert "Inkrafttreten" in result.page_texts[-1]["text"]


@pytest.mark.parametrize("pipeline,limit", [("analysis", 25 * 1024 * 1024), ("search", 128 * 1024 * 1024)])
@pytest.mark.parametrize("extra_byte", [0, 1])
def test_actual_size_boundaries_before_pdf_reading_or_ocr(tmp_path, monkeypatch, pipeline, limit, extra_byte):
    path = tmp_path / "size_boundary.pdf"
    with path.open("wb") as stream:
        stream.write(b"%PDF-1.4\n")
        stream.truncate(limit + extra_byte)
    calls = []
    text = "Originaltext aus der Groessenpruefung. " * 30

    def reject_ocr(*args):
        pytest.fail("Size validation must not invoke OCR")

    if pipeline == "analysis":
        assert extraction_pipeline.MAX_EXTRACT_FILE_BYTES == limit
        monkeypatch.setattr(extraction_pipeline, "_extract_text_from_pdf",
                            lambda source: calls.append(source) or (text, 1, [], []))
        monkeypatch.setattr(extraction_pipeline, "_extract_text_via_ocr", reject_ocr)
        result = extraction_pipeline.extract_text_for_analysis(path, content_type="application/pdf", max_text_chars=2000)
        assert result.extraction_status == ("file_too_large" if extra_byte else "ok")
        if extra_byte:
            assert not result.extracted_text and not result.page_texts
    else:
        assert passages.MAX_FILE_BYTES == limit
        monkeypatch.setattr("pypdf.PdfReader", lambda source: calls.append(source) or SimpleNamespace(
            pages=[SimpleNamespace(extract_text=lambda: text)]))
        monkeypatch.setattr(passages, "ocr_page", reject_ocr)
        if extra_byte:
            with pytest.raises(ValueError, match="128 MiB"):
                passages.extract_pages(path)
        else:
            assert passages.extract_pages(path)[0]["text"] == text.strip()
    assert len(calls) == (0 if extra_byte else 1)


@pytest.mark.skipif(os.environ.get("RATSI_PDF_STRESS") != "1", reason="Opt-in: RATSI_PDF_STRESS=1")
def test_pdf_stress_with_300_original_pages(tmp_path):
    reader = PdfReader(FIXTURES / "council_rules.pdf")
    writer = PdfWriter()
    for number in range(300):
        writer.add_page(reader.pages[number % len(reader.pages)])
    path = tmp_path / "300_page_council_rules.pdf"
    writer.write(path)
    pages = passages.extract_pages(path, use_ocr=False)
    assert [page["page"] for page in pages] == list(range(1, 301))
    chunks = passages.chunk_pages(pages, WhitespaceTokenizer(), tokens=64, overlap=12)
    assert {chunk["page_start"] for chunk in chunks} == set(range(1, 301))
    assert all(chunk["token_count"] <= 64 for chunk in chunks)
    assert "Inkrafttreten" in pages[-1]["text"]


@pytest.mark.parametrize("ocr_text", ["Übersicht über unsere Lösungen und Preise", ""])
def test_analysis_mixed_pdf_preserves_text_and_ocr_page(monkeypatch, ocr_text):
    path = FIXTURES / "mixed_text_scan.pdf"
    calls = []
    def ocr(source, *, page_number):
        calls.append((source, page_number))
        return [ocr_text] if ocr_text else []
    monkeypatch.setattr(extraction_pipeline, "_extract_text_via_ocr", ocr)
    result = extraction_pipeline.extract_text_for_analysis(
        path, content_type="application/pdf", max_text_chars=100000)
    assert calls == [(path, 2)]
    assert result.page_count == 2
    assert [page["page"] for page in result.page_texts] == [1, 2]
    assert "Beschlussvorlage" in result.page_texts[0]["text"]
    assert result.page_texts[1] == {"page": 2, "text": ocr_text, "char_count": len(ocr_text)}
    assert result.extraction_status == ("ok" if ocr_text else "partial")
    assert result.ocr_needed is (not bool(ocr_text))
    assert "Beschlussvorlage" in result.extracted_text
    if ocr_text:
        assert ocr_text in result.extracted_text
