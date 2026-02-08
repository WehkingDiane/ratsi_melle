"""Text extraction pipeline for analysis-ready document exports."""

from __future__ import annotations

import re
import zlib
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

PIPELINE_VERSION = "1.0"


@dataclass(frozen=True)
class ExtractionResult:
    """Extraction output plus quality markers for downstream analysis."""

    extraction_status: str
    parsing_quality: str
    extracted_text: str
    extracted_char_count: int
    page_count: int | None
    extraction_error: str | None
    ocr_needed: bool
    extraction_pipeline_version: str
    extracted_at: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def extract_text_for_analysis(
    file_path: Path,
    *,
    content_type: str | None,
    max_text_chars: int,
) -> ExtractionResult:
    """Extract text from a local document path with quality classification."""

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if not file_path.exists() or not file_path.is_file():
        return ExtractionResult(
            extraction_status="missing_file",
            parsing_quality="failed",
            extracted_text="",
            extracted_char_count=0,
            page_count=None,
            extraction_error="Local file does not exist",
            ocr_needed=False,
            extraction_pipeline_version=PIPELINE_VERSION,
            extracted_at=now,
        )

    normalized_content_type = (content_type or "").lower()
    suffix = file_path.suffix.lower()

    try:
        if "pdf" in normalized_content_type or suffix == ".pdf":
            text, page_count = _extract_text_from_pdf(file_path)
            return _classify_result(
                text=text,
                page_count=page_count,
                max_text_chars=max_text_chars,
                is_pdf=True,
                extracted_at=now,
            )

        if _looks_like_text_file(suffix, normalized_content_type):
            text = _extract_text_from_text_file(file_path)
            return _classify_result(
                text=text,
                page_count=None,
                max_text_chars=max_text_chars,
                is_pdf=False,
                extracted_at=now,
            )

        return ExtractionResult(
            extraction_status="unsupported_format",
            parsing_quality="failed",
            extracted_text="",
            extracted_char_count=0,
            page_count=None,
            extraction_error="Unsupported file type for text extraction",
            ocr_needed=False,
            extraction_pipeline_version=PIPELINE_VERSION,
            extracted_at=now,
        )
    except Exception as exc:  # pragma: no cover - defensive
        return ExtractionResult(
            extraction_status="error",
            parsing_quality="failed",
            extracted_text="",
            extracted_char_count=0,
            page_count=None,
            extraction_error=str(exc),
            ocr_needed=False,
            extraction_pipeline_version=PIPELINE_VERSION,
            extracted_at=now,
        )


def _classify_result(
    *,
    text: str,
    page_count: int | None,
    max_text_chars: int,
    is_pdf: bool,
    extracted_at: str,
) -> ExtractionResult:
    text = _normalize_whitespace(text)
    if len(text) > max_text_chars:
        text = text[:max_text_chars]

    char_count = len(text)
    if char_count == 0:
        return ExtractionResult(
            extraction_status="ocr_needed" if is_pdf else "empty_text",
            parsing_quality="low" if is_pdf else "failed",
            extracted_text="",
            extracted_char_count=0,
            page_count=page_count,
            extraction_error=None,
            ocr_needed=is_pdf,
            extraction_pipeline_version=PIPELINE_VERSION,
            extracted_at=extracted_at,
        )

    if char_count < 80:
        return ExtractionResult(
            extraction_status="partial",
            parsing_quality="low",
            extracted_text=text,
            extracted_char_count=char_count,
            page_count=page_count,
            extraction_error=None,
            ocr_needed=False,
            extraction_pipeline_version=PIPELINE_VERSION,
            extracted_at=extracted_at,
        )

    if char_count < 500:
        quality = "medium"
    else:
        quality = "high"

    return ExtractionResult(
        extraction_status="ok",
        parsing_quality=quality,
        extracted_text=text,
        extracted_char_count=char_count,
        page_count=page_count,
        extraction_error=None,
        ocr_needed=False,
        extraction_pipeline_version=PIPELINE_VERSION,
        extracted_at=extracted_at,
    )


def _extract_text_from_text_file(file_path: Path) -> str:
    for encoding in ("utf-8", "latin-1"):
        try:
            return file_path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return ""


def _extract_text_from_pdf(file_path: Path) -> tuple[str, int | None]:
    raw = file_path.read_bytes()
    page_count = len(re.findall(rb"/Type\s*/Page\b", raw)) or None

    text_chunks: list[str] = []
    for stream in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", raw, flags=re.DOTALL):
        candidates = [stream]
        decompressed = _try_decompress(stream)
        if decompressed is not None:
            candidates.append(decompressed)

        for candidate in candidates:
            decoded = _extract_pdf_literal_text(candidate)
            if decoded:
                text_chunks.append(decoded)

    return "\n".join(text_chunks), page_count


def _try_decompress(data: bytes) -> bytes | None:
    try:
        return zlib.decompress(data)
    except zlib.error:
        return None


def _extract_pdf_literal_text(data: bytes) -> str:
    literals = re.findall(rb"\((?:\\.|[^\\()])*\)", data)
    if not literals:
        return ""

    parts = []
    for literal in literals:
        inner = literal[1:-1]
        parts.append(_decode_pdf_escapes(inner))
    return " ".join(part for part in parts if part)


def _decode_pdf_escapes(value: bytes) -> str:
    result = bytearray()
    i = 0
    while i < len(value):
        char = value[i]
        if char != 0x5C:  # "\\"
            result.append(char)
            i += 1
            continue

        if i + 1 >= len(value):
            i += 1
            continue

        nxt = value[i + 1]
        mapping = {
            ord("n"): b"\n",
            ord("r"): b"\r",
            ord("t"): b"\t",
            ord("b"): b"\b",
            ord("f"): b"\f",
            ord("("): b"(",
            ord(")"): b")",
            ord("\\"): b"\\",
        }
        if nxt in mapping:
            result.extend(mapping[nxt])
            i += 2
            continue

        if ord("0") <= nxt <= ord("7"):
            octal_digits = [nxt]
            j = i + 2
            while j < len(value) and len(octal_digits) < 3 and ord("0") <= value[j] <= ord("7"):
                octal_digits.append(value[j])
                j += 1
            result.append(int(bytes(octal_digits), 8))
            i = j
            continue

        result.append(nxt)
        i += 2

    return result.decode("latin-1", errors="ignore")


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _looks_like_text_file(suffix: str, content_type: str) -> bool:
    if suffix in {".txt", ".md", ".html", ".htm", ".json", ".xml", ".csv"}:
        return True
    if content_type.startswith("text/"):
        return True
    return False
