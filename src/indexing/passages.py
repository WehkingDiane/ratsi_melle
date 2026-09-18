"""Page-aware extraction and bounded passages for local search."""

from __future__ import annotations

from hashlib import sha256
import logging
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

LOGGER = logging.getLogger(__name__)
COLLECTION = "ratsi_passages"
MODEL = "microsoft/harrier-oss-v1-0.6b"
PIPELINE_VERSION = "passages-1"
MAX_FILE_BYTES = 100 * 1024 * 1024


def file_digest(path: Path) -> str:
    """Hash a source file without loading it into memory."""
    with path.open("rb") as stream:
        return sha256_stream(stream)


def sha256_stream(stream) -> str:
    digest = sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
    return digest.hexdigest()


def ocr_page(path: Path, page: int) -> str:
    """OCR exactly one PDF page, preserving its original page number."""
    if not shutil.which("pdftoppm") or not shutil.which("tesseract"):
        return ""
    with tempfile.TemporaryDirectory(prefix="ratsi_search_ocr_") as directory:
        prefix = str(Path(directory) / "page")
        try:
            raster = subprocess.run(
                ["pdftoppm", "-f", str(page), "-l", str(page), "-singlefile",
                 "-scale-to", "2400", "-png", str(path), prefix],
                capture_output=True, timeout=120, check=False,
            )
            if raster.returncode:
                return ""
            result = subprocess.run(
                ["tesseract", prefix + ".png", "stdout", "-l", "deu+eng"],
                capture_output=True, text=True, timeout=120, check=False,
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except (OSError, subprocess.TimeoutExpired) as exc:
            LOGGER.warning("OCR failed for %s page %s: %s", path, page, exc)
            return ""


def extract_pages(path: Path, *, use_ocr: bool = True) -> list[dict]:
    """Read all pages, using OCR for individual empty or failed PDF pages."""
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("Source exceeds the 100 MiB search extraction limit")
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        pages = []
        for number, page in enumerate(reader.pages, 1):
            try:
                text = page.extract_text() or ""
            except Exception as exc:
                LOGGER.warning("Text extraction failed on page %s: %s", number, exc)
                text = ""
            method = "text"
            if not text.strip():
                text = ocr_page(path, number) if use_ocr else ""
                method = "ocr" if text else "ocr_needed"
            pages.append({"page": number, "text": text.strip(), "method": method})
        return pages
    if path.suffix.lower() not in {".txt", ".md", ".html", ".htm", ".csv"}:
        raise ValueError(f"Unsupported source format: {path.suffix}")
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() in {".html", ".htm"}:
        from bs4 import BeautifulSoup

        text = BeautifulSoup(text, "html.parser").get_text("\n", strip=True)
    return [{"page": None, "text": text, "method": "text"}]


def chunk_pages(pages: list[dict], tokenizer, *, tokens: int = 768, overlap: int = 96) -> list[dict]:
    """Split on page/paragraph boundaries with tokenizer-measured overlap."""
    if tokens < 32 or not 0 <= overlap < tokens:
        raise ValueError("Require tokens >= 32 and 0 <= overlap < tokens")
    chunks = []
    for page in pages:
        text = page["text"].strip()
        if not text:
            continue
        encoded = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
        offsets = encoded["offset_mapping"]
        start = 0
        while start < len(offsets):
            end = min(start + tokens, len(offsets))
            if end < len(offsets):
                # Prefer a paragraph end in the latter half of the window.
                for candidate in range(end, start + tokens // 2, -1):
                    gap = text[offsets[candidate - 1][1]:offsets[candidate][0]]
                    if "\n" in gap:
                        end = candidate
                        break
            begin_char, end_char = offsets[start][0], offsets[end - 1][1]
            chunks.append({
                "text": text[begin_char:end_char], "page_start": page["page"],
                "page_end": page["page"], "token_count": end - start,
                "char_start": begin_char, "char_end": end_char,
                "extraction_method": page["method"],
            })
            if end == len(offsets):
                break
            start = max(start + 1, end - overlap)
    return chunks
