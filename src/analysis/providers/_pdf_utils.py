"""Shared PDF text-extraction utility for providers that lack native PDF support."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract plain text from a PDF file using pypdf (lazy import).

    Returns the extracted text, or an empty string if extraction fails or
    pypdf is not installed.
    """
    try:
        import pypdf  # noqa: PLC0415
    except ImportError:
        logger.warning(
            "pypdf not installed – PDF text extraction unavailable. "
            "Run: pip install pypdf"
        )
        return ""

    try:
        reader = pypdf.PdfReader(str(pdf_path))
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text)
        return "\n\n".join(pages)
    except Exception as exc:  # noqa: BLE001
        logger.warning("PDF text extraction failed for %s: %s", pdf_path.name, exc)
        return ""
