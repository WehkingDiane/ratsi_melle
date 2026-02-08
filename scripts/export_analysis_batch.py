"""Export selected sessions/documents from an index DB as analysis batch JSON."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from src.analysis.extraction_pipeline import extract_text_for_analysis


ALLOWED_DOCUMENT_TYPES = {
    "vorlage",
    "beschlussvorlage",
    "protokoll",
    "bekanntmachung",
    "sonstiges",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("data/processed/local_index.sqlite"),
        help="Path to source SQLite index database.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/analysis_batch.json"),
        help="Path to JSON output file.",
    )
    parser.add_argument(
        "--session-id",
        action="append",
        default=[],
        dest="session_ids",
        help="Restrict export to one or more session IDs.",
    )
    parser.add_argument(
        "--committee",
        action="append",
        default=[],
        dest="committees",
        help="Restrict export to one or more committee names.",
    )
    parser.add_argument(
        "--date-from",
        default=None,
        help="Lower date bound (inclusive), format YYYY-MM-DD.",
    )
    parser.add_argument(
        "--date-to",
        default=None,
        help="Upper date bound (inclusive), format YYYY-MM-DD.",
    )
    parser.add_argument(
        "--document-type",
        action="append",
        default=[],
        dest="document_types",
        help="Restrict export to one or more document types.",
    )
    parser.add_argument(
        "--require-local-path",
        action="store_true",
        help="Export only rows with a non-empty local_path.",
    )
    parser.add_argument(
        "--include-text-extraction",
        action="store_true",
        help="Extract local document text and include extraction quality metadata.",
    )
    parser.add_argument(
        "--max-text-chars",
        type=int,
        default=12000,
        help="Maximum number of extracted characters included per document.",
    )
    return parser.parse_args()


def export_analysis_batch(
    db_path: Path,
    output_path: Path,
    *,
    session_ids: Sequence[str] | None = None,
    committees: Sequence[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    document_types: Sequence[str] | None = None,
    require_local_path: bool = False,
    include_text_extraction: bool = False,
    max_text_chars: int = 12000,
) -> int:
    _validate_date(date_from)
    _validate_date(date_to)
    normalized_types = _normalize_document_types(document_types)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        top_titles = _load_top_titles(conn)
        rows = conn.execute(
            *_build_query(
                session_ids=session_ids or (),
                committees=committees or (),
                date_from=date_from,
                date_to=date_to,
                document_types=normalized_types,
                require_local_path=require_local_path,
            )
        ).fetchall()

    documents: list[dict[str, object]] = []
    for row in rows:
        document = {
            "session_id": row["session_id"],
            "date": row["date"],
            "committee": row["committee"],
            "meeting_name": row["meeting_name"],
            "top_number": row["agenda_item"],
            "top_title": top_titles.get((row["session_id"], row["agenda_item"])),
            "title": row["title"],
            "category": row["category"],
            "document_type": row["document_type"],
            "url": row["url"],
            "local_path": row["local_path"],
            "sha1": row["sha1"],
            "retrieved_at": row["retrieved_at"],
            "content_type": row["content_type"],
            "content_length": row["content_length"],
        }
        if include_text_extraction:
            document.update(
                _extract_document_payload(
                    session_path=row["session_path"],
                    local_path=row["local_path"],
                    content_type=row["content_type"],
                    max_text_chars=max_text_chars,
                )
            )
        documents.append(document)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_db": str(db_path),
        "filters": {
            "session_ids": sorted(set(session_ids or ())),
            "committees": sorted(set(committees or ())),
            "date_from": date_from,
            "date_to": date_to,
            "document_types": normalized_types,
            "require_local_path": require_local_path,
            "include_text_extraction": include_text_extraction,
            "max_text_chars": max_text_chars,
        },
        "documents": documents,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return len(rows)


def _build_query(
    *,
    session_ids: Iterable[str],
    committees: Iterable[str],
    date_from: str | None,
    date_to: str | None,
    document_types: Iterable[str],
    require_local_path: bool,
) -> tuple[str, tuple[object, ...]]:
    where_clauses: list[str] = []
    params: list[object] = []

    where_clauses.append("d.session_id = s.session_id")

    session_ids = tuple(sorted(set(session_ids)))
    if session_ids:
        placeholders = ", ".join("?" for _ in session_ids)
        where_clauses.append(f"s.session_id IN ({placeholders})")
        params.extend(session_ids)

    committees = tuple(sorted(set(committees)))
    if committees:
        placeholders = ", ".join("?" for _ in committees)
        where_clauses.append(f"s.committee IN ({placeholders})")
        params.extend(committees)

    if date_from:
        where_clauses.append("s.date >= ?")
        params.append(date_from)
    if date_to:
        where_clauses.append("s.date <= ?")
        params.append(date_to)

    document_types = tuple(sorted(set(document_types)))
    if document_types:
        placeholders = ", ".join("?" for _ in document_types)
        where_clauses.append(f"d.document_type IN ({placeholders})")
        params.extend(document_types)

    if require_local_path:
        where_clauses.append("COALESCE(TRIM(d.local_path), '') != ''")

    where_sql = " AND ".join(where_clauses)
    query = f"""
        SELECT
            s.session_id,
            s.date,
            s.committee,
            s.meeting_name,
            d.title,
            d.category,
            d.document_type,
            d.agenda_item,
            d.url,
            d.local_path,
            d.sha1,
            d.retrieved_at,
            d.content_type,
            d.content_length,
            s.session_path
        FROM sessions s, documents d
        WHERE {where_sql}
        ORDER BY s.date, s.session_id, COALESCE(d.agenda_item, ''), d.title, d.url
    """
    return query, tuple(params)


def _load_top_titles(conn: sqlite3.Connection) -> dict[tuple[str, str | None], str]:
    rows = conn.execute(
        """
        SELECT session_id, number, title
        FROM agenda_items
        ORDER BY session_id, id
        """
    ).fetchall()
    mapping: dict[tuple[str, str | None], str] = {}
    for row in rows:
        key = (row[0], row[1])
        if key in mapping:
            continue
        mapping[key] = row[2]
    return mapping


def _validate_date(value: str | None) -> None:
    if value is None:
        return
    datetime.strptime(value, "%Y-%m-%d")


def _normalize_document_types(document_types: Sequence[str] | None) -> list[str]:
    normalized = sorted({entry.strip().lower() for entry in (document_types or ()) if entry.strip()})
    for value in normalized:
        if value not in ALLOWED_DOCUMENT_TYPES:
            raise ValueError(
                f"Unsupported document type '{value}'. Allowed: {', '.join(sorted(ALLOWED_DOCUMENT_TYPES))}"
            )
    return normalized


def _extract_document_payload(
    *,
    session_path: str | None,
    local_path: str | None,
    content_type: str | None,
    max_text_chars: int,
) -> dict[str, object]:
    if max_text_chars < 1:
        raise ValueError("--max-text-chars must be >= 1")

    resolved_path = _resolve_local_file_path(session_path=session_path, local_path=local_path)
    if resolved_path is None:
        return {
            "resolved_local_path": None,
            "extraction_status": "missing_file",
            "parsing_quality": "failed",
            "extracted_text": "",
            "extracted_char_count": 0,
            "page_count": None,
            "extraction_error": "No local path available",
            "ocr_needed": False,
            "extraction_pipeline_version": None,
            "extracted_at": None,
        }

    result = extract_text_for_analysis(
        resolved_path,
        content_type=content_type,
        max_text_chars=max_text_chars,
    )
    payload = result.to_dict()
    payload["resolved_local_path"] = str(resolved_path)
    return payload


def _resolve_local_file_path(*, session_path: str | None, local_path: str | None) -> Path | None:
    normalized_local = (local_path or "").strip()
    if not normalized_local:
        return None
    normalized_local = normalized_local.replace("\\", "/")

    candidate = Path(normalized_local)
    if candidate.is_absolute():
        return candidate

    normalized_session = (session_path or "").strip()
    if not normalized_session:
        return candidate
    normalized_session = normalized_session.replace("\\", "/")

    return Path(normalized_session) / candidate


def main() -> None:
    args = parse_args()
    count = export_analysis_batch(
        args.db_path,
        args.output,
        session_ids=args.session_ids,
        committees=args.committees,
        date_from=args.date_from,
        date_to=args.date_to,
        document_types=args.document_types,
        require_local_path=args.require_local_path,
        include_text_extraction=args.include_text_extraction,
        max_text_chars=args.max_text_chars,
    )
    print(f"Exported {count} documents to {args.output}")


if __name__ == "__main__":  # pragma: no cover
    main()
