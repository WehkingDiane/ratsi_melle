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


@pytest.mark.parametrize("pipeline,limit", [("analysis", 25 * 1024 * 1024), ("search", 100 * 1024 * 1024)])
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
            with pytest.raises(ValueError, match="100 MiB"):
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
