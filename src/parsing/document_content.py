"""Heuristic content parsers for analysis-relevant SessionNet documents."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

PARSER_VERSION = "1.0"

SUPPORTED_DOCUMENT_TYPES = {"vorlage", "beschlussvorlage", "protokoll"}


@dataclass(frozen=True)
class DocumentContentParseResult:
    """Structured document content extracted from normalized raw text."""

    content_parser_status: str
    content_parser_quality: str
    content_parser_version: str
    structured_fields: dict[str, str]
    matched_sections: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def parse_document_content(
    *,
    document_type: str | None,
    text: str | None,
    title: str | None = None,
) -> DocumentContentParseResult:
    """Extract analysis-relevant sections from normalized document text."""

    normalized_type = (document_type or "").strip().lower()
    normalized_text = _normalize_text(text or "")
    normalized_title = (title or "").strip()

    if normalized_type not in SUPPORTED_DOCUMENT_TYPES:
        return DocumentContentParseResult(
            content_parser_status="unsupported_document_type",
            content_parser_quality="failed",
            content_parser_version=PARSER_VERSION,
            structured_fields={},
        )

    if not normalized_text:
        return DocumentContentParseResult(
            content_parser_status="empty_text",
            content_parser_quality="failed",
            content_parser_version=PARSER_VERSION,
            structured_fields={},
        )

    parser = {
        "vorlage": _parse_vorlage_like_document,
        "beschlussvorlage": _parse_vorlage_like_document,
        "protokoll": _parse_protokoll_document,
    }[normalized_type]

    fields = parser(normalized_text)
    if normalized_title and "titel" not in fields:
        fields["titel"] = normalized_title

    matched_sections = sorted(fields)
    status = "ok" if matched_sections else "no_structured_fields"
    quality = _classify_quality(normalized_type, fields, normalized_text)

    return DocumentContentParseResult(
        content_parser_status=status,
        content_parser_quality=quality,
        content_parser_version=PARSER_VERSION,
        structured_fields=fields,
        matched_sections=matched_sections,
    )


def _parse_vorlage_like_document(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}

    beschlusstext = _extract_labeled_section(
        text,
        labels=("Beschlussvorschlag", "Beschluss", "Empfehlung", "Antrag"),
        stop_labels=(
            "Begruendung",
            "Sachverhalt",
            "Finanzielle Auswirkungen",
            "Zustaendigkeit",
            "Federfuehrung",
            "Anlagen",
        ),
    )
    if beschlusstext:
        fields["beschlusstext"] = beschlusstext

    begruendung = _extract_labeled_section(
        text,
        labels=("Begruendung", "Sachverhalt", "Erläuterung", "Erlaeuterung"),
        stop_labels=(
            "Finanzielle Auswirkungen",
            "Zustaendigkeit",
            "Federfuehrung",
            "Beschlussvorschlag",
            "Beschluss",
            "Anlagen",
        ),
    )
    if begruendung:
        fields["begruendung"] = begruendung

    finanzbezug = _extract_labeled_section(
        text,
        labels=("Finanzielle Auswirkungen", "Finanzierung", "Haushaltsmittel", "Kosten"),
        stop_labels=("Zustaendigkeit", "Federfuehrung", "Anlagen", "Beschluss", "Begruendung"),
    )
    if finanzbezug:
        fields["finanzbezug"] = finanzbezug

    zustaendigkeit = _extract_labeled_section(
        text,
        labels=("Zustaendigkeit", "Federfuehrung", "Beratungsfolge", "Zustaendige Stelle"),
        stop_labels=("Anlagen", "Finanzielle Auswirkungen", "Begruendung", "Beschluss"),
    )
    if zustaendigkeit:
        fields["zustaendigkeit"] = zustaendigkeit

    return fields


def _parse_protokoll_document(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}

    entscheidung = _extract_labeled_section(
        text,
        labels=("Beschluss", "Abstimmung", "Entscheidung", "Ergebnis"),
        stop_labels=("Begruendung", "Sachverhalt", "Notiz", "Hinweis", "Anlagen"),
    )
    if entscheidung:
        fields["entscheidung"] = entscheidung

    beschlusstext = _extract_labeled_section(
        text,
        labels=("Beschlusstext", "Beschluss", "Beschlussvorschlag"),
        stop_labels=("Abstimmung", "Ergebnis", "Notiz", "Hinweis", "Anlagen"),
    )
    if beschlusstext:
        fields["beschlusstext"] = beschlusstext

    begruendung = _extract_labeled_section(
        text,
        labels=("Begruendung", "Sachverhalt", "Diskussion", "Beratung"),
        stop_labels=("Beschluss", "Abstimmung", "Ergebnis", "Anlagen"),
    )
    if begruendung:
        fields["begruendung"] = begruendung

    return fields


def _extract_labeled_section(text: str, *, labels: tuple[str, ...], stop_labels: tuple[str, ...]) -> str | None:
    label_pattern = "|".join(re.escape(label) for label in labels)
    stop_pattern = "|".join(re.escape(label) for label in stop_labels)
    pattern = re.compile(
        rf"(?is)\b(?:{label_pattern})\b\s*[:\-]?\s*(.*?)"
        rf"(?=(?:\b(?:{stop_pattern})\b\s*[:\-]?)|$)"
    )
    match = pattern.search(text)
    if not match:
        return None
    value = _normalize_text(match.group(1))
    return value or None


def _classify_quality(document_type: str, fields: dict[str, str], text: str) -> str:
    if not fields:
        return "low" if len(text) >= 120 else "failed"

    strong_fields = {
        "vorlage": {"beschlusstext", "begruendung", "finanzbezug", "zustaendigkeit"},
        "beschlussvorlage": {"beschlusstext", "begruendung", "finanzbezug", "zustaendigkeit"},
        "protokoll": {"beschlusstext", "entscheidung", "begruendung"},
    }[document_type]
    hit_count = len(strong_fields.intersection(fields))

    if hit_count >= 3:
        return "high"
    if hit_count >= 2:
        return "medium"
    return "low"


def _normalize_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{2,}", "\n", normalized)
    return normalized.strip()
