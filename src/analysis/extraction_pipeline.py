"""Text extraction pipeline for analysis-ready document exports."""

from __future__ import annotations

import re
import zlib
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

PIPELINE_VERSION = "1.1"


@dataclass(frozen=True)
class ExtractionResult:
    """Extraction output plus quality markers for downstream analysis."""

    extraction_status: str
    parsing_quality: str
    extracted_text: str
    extracted_char_count: int
    page_count: int | None
    page_texts: list[dict[str, object]]
    detected_sections: list[dict[str, object]]
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
            page_texts=[],
            detected_sections=[],
            extraction_error="Local file does not exist",
            ocr_needed=False,
            extraction_pipeline_version=PIPELINE_VERSION,
            extracted_at=now,
        )

    normalized_content_type = (content_type or "").lower()
    suffix = file_path.suffix.lower()

    try:
        if "pdf" in normalized_content_type or suffix == ".pdf":
            text, page_count, page_texts, detected_sections = _extract_text_from_pdf(file_path)
            return _classify_result(
                text=text,
                page_count=page_count,
                page_texts=page_texts,
                detected_sections=detected_sections,
                max_text_chars=max_text_chars,
                is_pdf=True,
                extracted_at=now,
            )

        if _looks_like_text_file(suffix, normalized_content_type):
            text = _extract_text_from_text_file(file_path)
            return _classify_result(
                text=text,
                page_count=None,
                page_texts=[],
                detected_sections=[],
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
            page_texts=[],
            detected_sections=[],
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
            page_texts=[],
            detected_sections=[],
            extraction_error=str(exc),
            ocr_needed=False,
            extraction_pipeline_version=PIPELINE_VERSION,
            extracted_at=now,
        )


def _classify_result(
    *,
    text: str,
    page_count: int | None,
    page_texts: list[dict[str, object]],
    detected_sections: list[dict[str, object]],
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
            page_texts=page_texts,
            detected_sections=detected_sections,
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
            page_texts=page_texts,
            detected_sections=detected_sections,
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
        page_texts=page_texts,
        detected_sections=detected_sections,
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


def _extract_text_from_pdf(file_path: Path) -> tuple[str, int | None, list[dict[str, object]], list[dict[str, object]]]:
    raw = file_path.read_bytes()
    object_map = _parse_pdf_objects(raw)
    page_object_ids = _find_page_object_ids(object_map)
    page_count = len(page_object_ids) or None

    page_texts = _extract_pdf_page_texts(object_map, page_object_ids)
    if not page_texts:
        fallback_text = _extract_pdf_stream_text(raw)
        if not fallback_text:
            return "", page_count, [], []
        page_texts = [
            {
                "page": 1,
                "char_count": len(_normalize_whitespace(fallback_text)),
                "text": fallback_text,
            }
        ]

    detected_sections = _detect_pdf_sections(page_texts)
    text = "\n\n".join(str(page.get("text", "")) for page in page_texts if page.get("text"))
    normalized_pages = [
        {
            "page": int(page["page"]),
            "char_count": int(page["char_count"]),
            "text": _normalize_whitespace(str(page["text"])),
        }
        for page in page_texts
        if str(page.get("text", "")).strip()
    ]
    return text, page_count or len(normalized_pages) or None, normalized_pages, detected_sections


def _extract_pdf_page_texts(
    object_map: dict[int, bytes],
    page_object_ids: list[int],
) -> list[dict[str, object]]:
    pages: list[dict[str, object]] = []
    for index, page_id in enumerate(page_object_ids, start=1):
        page_object = object_map.get(page_id, b"")
        stream_ids = _extract_contents_object_ids(page_object)
        text_chunks: list[str] = []
        for stream_id in stream_ids:
            stream_object = object_map.get(stream_id, b"")
            stream = _extract_stream_data(stream_object)
            if stream is None:
                continue
            decoded = _extract_text_from_stream_bytes(stream)
            if decoded:
                text_chunks.append(decoded)

        page_text = "\n".join(chunk for chunk in text_chunks if chunk)
        if not page_text.strip():
            continue
        pages.append(
            {
                "page": index,
                "char_count": len(_normalize_whitespace(page_text)),
                "text": page_text,
            }
        )
    return pages


def _extract_pdf_stream_text(raw: bytes) -> str:
    text_chunks: list[str] = []
    for stream in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", raw, flags=re.DOTALL):
        decoded = _extract_text_from_stream_bytes(stream)
        if decoded:
            text_chunks.append(decoded)
    return "\n".join(text_chunks)


def _iter_stream_candidates(stream: bytes) -> list[bytes]:
    candidates = [stream]
    decompressed = _try_decompress(stream)
    if decompressed is not None:
        candidates.append(decompressed)
    return candidates


def _extract_text_from_stream_bytes(stream: bytes) -> str:
    text_chunks: list[str] = []
    for candidate in _iter_stream_candidates(stream):
        text_blocks = re.findall(rb"BT(.*?)ET", candidate, flags=re.DOTALL)
        for block in text_blocks:
            decoded = _extract_pdf_literal_text(block)
            if decoded:
                text_chunks.append(decoded)
    return "\n".join(text_chunks)


def _parse_pdf_objects(raw: bytes) -> dict[int, bytes]:
    objects: dict[int, bytes] = {}
    for match in re.finditer(rb"(\d+)\s+\d+\s+obj(.*?)endobj", raw, flags=re.DOTALL):
        objects[int(match.group(1))] = match.group(2)
    return objects


def _find_page_object_ids(object_map: dict[int, bytes]) -> list[int]:
    page_ids = [
        object_id
        for object_id, data in object_map.items()
        if re.search(rb"/Type\s*/Page\b", data)
    ]
    return sorted(page_ids)


def _extract_contents_object_ids(page_object: bytes) -> list[int]:
    array_match = re.search(rb"/Contents\s*\[(.*?)\]", page_object, flags=re.DOTALL)
    if array_match:
        return [int(value) for value in re.findall(rb"(\d+)\s+\d+\s+R", array_match.group(1))]

    single_match = re.search(rb"/Contents\s+(\d+)\s+\d+\s+R", page_object)
    if single_match:
        return [int(single_match.group(1))]
    return []


def _extract_stream_data(object_bytes: bytes) -> bytes | None:
    match = re.search(rb"stream\r?\n(.*?)\r?\nendstream", object_bytes, flags=re.DOTALL)
    if not match:
        return None
    stream = match.group(1)
    decompressed = _try_decompress(stream)
    return decompressed if decompressed is not None else stream


def _detect_pdf_sections(page_texts: list[dict[str, object]]) -> list[dict[str, object]]:
    sections: list[dict[str, object]] = []
    heading_pattern = re.compile(
        r"(Beschlussvorschlag|Beschluss|Begruendung|Sachverhalt|Finanzielle Auswirkungen|"
        r"Auswirkungen auf den Haushalt|Anlagen|Protokoll|Ergebnis|Empfehlung)\s*:",
        flags=re.IGNORECASE,
    )

    for page in page_texts:
        page_number = int(page["page"])
        text = str(page.get("text", ""))
        for match in heading_pattern.finditer(text):
            heading = match.group(1).strip()
            sections.append(
                {
                    "page": page_number,
                    "heading": heading,
                    "anchor_text": _normalize_whitespace(text[match.start() : match.start() + 180]),
                }
            )
    return sections


def _try_decompress(data: bytes) -> bytes | None:
    try:
        return zlib.decompress(data)
    except zlib.error:
        return None


def _extract_pdf_literal_text(data: bytes) -> str:
    literals = _iter_pdf_literal_strings(data)
    if not literals:
        return ""

    parts = []
    for literal in literals:
        parts.append(_decode_pdf_escapes(literal))
    return " ".join(part for part in parts if part)


def _iter_pdf_literal_strings(data: bytes) -> list[bytes]:
    literals: list[bytes] = []
    i = 0
    while i < len(data):
        if data[i] != ord("("):
            i += 1
            continue
        i += 1
        depth = 1
        terminated = False
        current = bytearray()
        while i < len(data):
            char = data[i]
            if char == 0x5C:  # backslash
                if i + 1 < len(data):
                    current.append(char)
                    current.append(data[i + 1])
                    i += 2
                    continue
                current.append(char)
                i += 1
                continue
            if char == ord("("):
                depth += 1
                current.append(char)
                i += 1
                continue
            if char == ord(")"):
                depth -= 1
                if depth == 0:
                    terminated = True
                    i += 1
                    break
                current.append(char)
                i += 1
                continue
            current.append(char)
            i += 1
        if terminated:
            literals.append(bytes(current))
    return literals


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
