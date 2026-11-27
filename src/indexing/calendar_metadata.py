"""Additive SQLite storage for calendar status in both public and RI indices."""
from src.fetching.calendar_status import calendar_metadata, FIELDS


def ensure_calendar_columns(connection):
    """Upgrade existing session tables without dropping rows or documents."""
    columns = {row[1] for row in connection.execute('PRAGMA table_info(sessions)')}
    for name, declaration in (('calendar_status', "TEXT NOT NULL DEFAULT 'scheduled'"),
                              ('calendar_note', 'TEXT'), ('rescheduled_date', 'TEXT'),
                              ('replacement_session_id', 'TEXT'), ('calendar_observed_at', 'TEXT')):
        if name not in columns:
            connection.execute(f'ALTER TABLE sessions ADD COLUMN {name} {declaration}')


def store_calendar_metadata(connection, session_id, source):
    """Persist calendar information independently of existing detail/document rows."""
    values = calendar_metadata(source)
    connection.execute('UPDATE sessions SET calendar_status=?, calendar_note=?, rescheduled_date=?, replacement_session_id=?, calendar_observed_at=? WHERE session_id=?',
                       (*values.values(), session_id))


def sync_saved_calendars(connection, data_root, client, *, only_refresh=False):
    """Read saved calendars locally; preserve documents and retain changed terms."""
    import json
    from datetime import datetime, timezone
    for path in data_root.glob('[0-9][0-9][0-9][0-9]/[0-9][0-9]/*_overview.html'):
        year, month = path.parent.parent.name, path.parent.name
        refs = client._parse_overview(path.read_text(encoding='utf-8'), int(year), int(month), include_planned=True)
        changes = {}
        saved = path.parent / 'calendar_changes.json'
        if saved.is_file():
            from hashlib import sha256
            payload = json.loads(saved.read_text(encoding='utf-8'))
            if payload.get('source_sha256') == sha256(path.read_bytes()).hexdigest():
                changes = payload.get('sessions', {})
        for ref in refs:
            ref.calendar_observed_at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
            if ref.session_id in changes:
                for key, value in changes[ref.session_id].items():
                    if key in FIELDS:
                        setattr(ref, key, value)
            exists = connection.execute('SELECT 1 FROM sessions WHERE session_id=?', (ref.session_id,)).fetchone()
            if not exists and (ref.calendar_status == 'scheduled' or only_refresh):
                continue
            if not exists:
                connection.execute('INSERT INTO sessions (session_id,date,year,month,committee,meeting_name,start_time,location,detail_url) VALUES (?,?,?,?,?,?,?,?,?)',
                    (ref.session_id,ref.date.isoformat(),ref.date.year,ref.date.month,ref.committee,ref.meeting_name,ref.start_time,ref.location,ref.detail_url))
            else:
                connection.execute('UPDATE sessions SET date=?, start_time=?, location=? WHERE session_id=?',
                    (ref.date.isoformat(),ref.start_time,ref.location,ref.session_id))
            store_calendar_metadata(connection,ref.session_id,ref)
