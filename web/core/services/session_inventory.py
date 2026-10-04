"""Read yearly session inventories and upcoming meetings without changing data."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import re
import sqlite3

from . import paths
from .status import SESSION_DIR_MARKERS, SESSION_FILE_MARKERS


def _read_index(path: Path, label: str, warnings: list[str]) -> list[dict] | None:
    if not path.is_file():
        warnings.append(f"{label}: Datenbank fehlt.")
        return None
    connection = None
    try:
        connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        sessions = [dict(row) for row in connection.execute("SELECT * FROM sessions")]
        try:
            counts = dict(connection.execute(
                "SELECT session_id, COUNT(*) FROM documents GROUP BY session_id"
            ))
        except sqlite3.Error:
            counts = None
            warnings.append(f"{label}: Dokumentanzahlen sind nicht verfügbar.")
        for session in sessions:
            session["document_count"] = (
                counts.get(session.get("session_id"), 0) if counts is not None else None
            )
        return sessions
    except (sqlite3.Error, OSError):
        warnings.append(f"{label}: Datenbank ist nicht lesbar oder enthält keine Sitzungstabelle.")
        return None
    finally:
        if connection is not None:
            connection.close()


def _session_date(session: dict) -> date | None:
    try:
        return date.fromisoformat(str(session.get("date") or ""))
    except ValueError:
        return None


def _year(session: dict) -> int | None:
    parsed = _session_date(session)
    if parsed:
        return parsed.year
    try:
        year = int(session.get("year"))
        return year if 1900 <= year <= 9999 else None
    except (ValueError, TypeError):
        return None


def _read_raw(warnings: list[str]) -> list[dict] | None:
    root = paths.RAW_DATA_DIR
    if not root.is_dir():
        warnings.append("Rohdaten: Verzeichnis fehlt.")
        return None
    result = []
    try:
        for year in root.iterdir():
            if not year.is_dir() or not re.fullmatch(r"\d{4}", year.name):
                continue
            for child in year.iterdir():
                if not child.is_dir():
                    continue
                candidates = (
                    [child] if _is_session(child)
                    else [p for p in child.iterdir() if p.is_dir()]
                )
                for folder in candidates:
                    if not _is_session(folder):
                        continue
                    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[-_](.+)[-_](\d+)", folder.name)
                    result.append({
                        "session_id": match[3] if match else None,
                        "date": match[1] if match else "",
                        "year": int(year.name),
                        "committee": match[2].replace("-", " ") if match else folder.name,
                    })
    except OSError:
        warnings.append("Rohdaten: Verzeichnis ist nicht vollständig lesbar.")
        return None
    return result


def _is_session(folder: Path) -> bool:
    return any((folder / name).is_file() for name in SESSION_FILE_MARKERS) or any(
        (folder / name).is_dir() for name in SESSION_DIR_MARKERS
    )


def yearly_session_inventory() -> dict:
    """Compare all available years and show unknown sources separately from zero."""
    warnings: list[str] = []
    sources = {
        "raw": _read_raw(warnings),
        "local": _read_index(paths.LOCAL_INDEX_DB, "Lokaler Index", warnings),
        "online": _read_index(paths.ONLINE_INDEX_DB, "Online-Index", warnings),
    }
    for label, sessions in sources.items():
        unknown = sum(
            _year(session) is None or not session.get("session_id")
            for session in sessions or []
        )
        if unknown:
            display = {"raw": "Rohdaten", "local": "Lokaler Index", "online": "Online-Index"}[label]
            warnings.append(f"{display}: {unknown} Einträge sind keinem Jahr oder keiner Sitzungs-ID eindeutig zugeordnet.")
    years = sorted({
        _year(s) for sessions in sources.values() for s in sessions or []
        if _year(s) is not None
    }, reverse=True)
    result = []
    for year in years:
        row = {"year": year}
        yearly = {
            key: [s for s in sessions or [] if _year(s) == year]
            for key, sessions in sources.items()
        }
        ids = {
            key: {str(s['session_id']): s for s in sessions if s.get('session_id')}
            for key, sessions in yearly.items()
        }
        identified = {
            key: sources[key] is not None and all(s.get('session_id') for s in sessions)
            for key, sessions in yearly.items()
        }
        for key, sessions in yearly.items():
            row[f"{key}_count"] = len(sessions) if sources[key] is not None else None
            if key != "raw":
                documents_known = sources[key] is not None and all(
                    s['document_count'] is not None for s in sources[key]
                )
                row[f"{key}_documents"] = (
                    sum(s['document_count'] for s in sessions) if documents_known else None
                )
        row["missing_online"] = (
            len((ids['raw'].keys() | ids['local'].keys()) - ids['online'].keys())
            if all(identified.values()) else None
        )
        row["missing_raw"] = (
            len(ids['online'].keys() - ids['raw'].keys())
            if identified['online'] and identified['raw'] else None
        )
        row["missing_local"] = (
            len(ids['raw'].keys() - ids['local'].keys())
            if identified['raw'] and identified['local'] else None
        )
        row['sessions'] = []
        for sid in ids['raw'].keys() | ids['local'].keys() | ids['online'].keys():
            session = dict(ids['local'].get(sid) or ids['online'].get(sid) or ids['raw'][sid])
            session['session_id'] = sid
            for key in sources:
                session[f"{key}_present"] = sid in ids[key] if sources[key] is not None else None
            row['sessions'].append(session)
        row['sessions'].sort(key=lambda s: (str(s.get('date') or ''), s['session_id']))
        result.append(row)
    return {"years": result, "warnings": warnings}


def dashboard_session_groups(local_sessions: list[dict], today: date, limit: int = 5) -> dict:
    """List meetings from today onward and past local sessions independently."""
    warnings: list[str] = []
    online = _read_index(paths.ONLINE_INDEX_DB, "Online-Index", warnings)
    local_ids = {str(s['session_id']) for s in local_sessions}
    merged = {str(s['session_id']): dict(s) for s in local_sessions}
    for session in online or []:
        merged[str(session['session_id'])] = session
    upcoming = []
    for session in merged.values():
        parsed = _session_date(session)
        if parsed and parsed >= today:
            session['display_date'] = parsed.strftime('%d.%m.%Y')
            session['local_present'] = str(session['session_id']) in local_ids
            upcoming.append(session)
    upcoming.sort(key=lambda s: (s['date'], str(s.get('start_time') or ''), str(s['session_id'])))
    recent = [s for s in local_sessions if _session_date(s) and _session_date(s) < today]
    recent.sort(key=lambda s: (s['date'], str(s['session_id'])), reverse=True)
    return {'upcoming_sessions': upcoming[:limit], 'recent_sessions': recent[:limit],
            'upcoming_notice': 'Online-Index nicht verfügbar; angezeigt werden lokal bekannte Termine.' if online is None else ''}
