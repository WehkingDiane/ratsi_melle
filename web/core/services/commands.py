"""Whitelisted service command construction for local data tools."""

from __future__ import annotations

from datetime import date
import sys
from typing import Any


def build_service_command(action: str, data: dict[str, Any]) -> tuple[list[str] | None, list[str]]:
    """Build a whitelisted fetch/build command."""

    try:
        command = _service_command(action, data)
    except ValueError as exc:
        return None, [str(exc)]
    return command, []


def _service_command(action: str, data: dict[str, Any]) -> list[str]:
    if action == "fetch_sessions":
        year = _validated_year(data.get("year"))
        months = _validated_months(data.get("months"))
        return [sys.executable, "scripts/fetch_sessions.py", str(year), "--months", *months]

    if action == "fetch_session_from_index":
        session_id = str(data.get("session_id") or "").strip()
        if not session_id:
            raise ValueError("Bitte eine Session-ID angeben.")
        return [sys.executable, "scripts/fetch_session_from_index.py", "--session-id", session_id]

    if action == "fetch_landkreis_publications":
        command = [
            sys.executable,
            "scripts/fetch_landkreis_publications.py",
            "--source",
            _validated_landkreis_source(data.get("source")),
        ]
        query = str(data.get("query") or "").strip()
        if query:
            command.extend(["--query", query])
        from_date = _optional_iso_date(data.get("from_date"), "Von-Datum")
        if from_date:
            command.extend(["--from-date", from_date])
        to_date = _optional_iso_date(data.get("to_date"), "Bis-Datum")
        if to_date:
            command.extend(["--to-date", to_date])
        limit = _optional_positive_int(data.get("limit"), "Limit")
        if limit is not None:
            command.extend(["--limit", str(limit)])
        if data.get("dry_run"):
            command.append("--dry-run")
        if data.get("refresh_existing"):
            command.append("--refresh-existing")
        return command

    if action == "build_local_index":
        command = [sys.executable, "scripts/build_local_index.py"]
        if data.get("refresh_existing"):
            command.append("--refresh-existing")
        if data.get("only_refresh"):
            command.append("--only-refresh")
        return command

    if action == "build_online_index":
        year = _validated_year(data.get("year"))
        months = _validated_months(data.get("months"))
        command = [sys.executable, "scripts/build_online_index_db.py", str(year), "--months", *months]
        if data.get("refresh_existing"):
            command.append("--refresh-existing")
        if data.get("only_refresh"):
            command.append("--only-refresh")
        return command

    if action == "build_landkreis_publications_db":
        command = [sys.executable, "scripts/build_landkreis_publications_db.py"]
        max_text_chars = _optional_positive_int(data.get("max_text_chars"), "Maximale Textzeichen")
        if max_text_chars is not None:
            command.extend(["--max-text-chars", str(max_text_chars)])
        return command

    if action == "build_vector_index":
        command = [sys.executable, "scripts/build_vector_index.py"]
        parsed_limit = _optional_positive_int(data.get("limit"), "Limit")
        if parsed_limit is not None:
            command.extend(["--limit", str(parsed_limit)])
        return command

    if action == "build_landkreis_vector_index":
        command = [sys.executable, "scripts/build_landkreis_vector_index.py"]
        parsed_limit = _optional_positive_int(data.get("limit"), "Limit")
        if parsed_limit is not None:
            command.extend(["--limit", str(parsed_limit)])
        return command

    raise ValueError("Unbekannte Service-Aktion.")


def _validated_year(value: Any) -> int:
    try:
        year = int(str(value or "").strip())
    except ValueError as exc:
        raise ValueError("Bitte ein gültiges Jahr angeben.") from exc
    if year < 2000 or year > 2100:
        raise ValueError("Das Jahr muss zwischen 2000 und 2100 liegen.")
    return year


def _validated_months(value: Any) -> list[str]:
    raw = str(value or "").replace(",", " ").strip()
    if not raw:
        return [str(month) for month in range(1, 13)]
    months: list[str] = []
    for token in raw.split():
        try:
            month = int(token)
        except ValueError as exc:
            raise ValueError("Monate müssen Zahlen zwischen 1 und 12 sein.") from exc
        if month < 1 or month > 12:
            raise ValueError("Monate müssen zwischen 1 und 12 liegen.")
        months.append(str(month))
    return months


def _validated_landkreis_source(value: Any) -> str:
    source = str(value or "all").strip()
    if source not in {"bekanntmachungen", "amtsblaetter", "all"}:
        raise ValueError("Bitte eine gültige Landkreis-Quelle auswählen.")
    return source


def _optional_positive_int(value: Any, field_name: str) -> int | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = int(raw)
    except ValueError as exc:
        raise ValueError(f"{field_name} muss eine Zahl sein.") from exc
    if parsed < 1:
        raise ValueError(f"{field_name} muss größer als 0 sein.")
    return parsed


def _optional_iso_date(value: Any, field_name: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"{field_name} muss im Format YYYY-MM-DD angegeben werden.") from exc
    return raw
