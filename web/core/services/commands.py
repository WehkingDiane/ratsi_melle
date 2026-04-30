"""Whitelisted service command construction for local data tools."""

from __future__ import annotations

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

    if action == "build_vector_index":
        command = [sys.executable, "scripts/build_vector_index.py"]
        limit = str(data.get("limit") or "").strip()
        if limit:
            try:
                parsed_limit = int(limit)
            except ValueError as exc:
                raise ValueError("Limit muss eine Zahl sein.") from exc
            if parsed_limit < 1:
                raise ValueError("Limit muss größer als 0 sein.")
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
