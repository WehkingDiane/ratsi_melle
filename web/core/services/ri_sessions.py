"""Read the RI catalogue and resolve files exclusively inside its raw-data root."""

from collections import defaultdict
from contextlib import closing
from pathlib import Path
import re
import sqlite3

from src.paths import REPO_ROOT, RI_LOCAL_INDEX_DB, RI_RAW_DATA_DIR, RI_ONLINE_INDEX_DB
from .sessions import _with_session_display_fields


class RiCatalogueError(Exception):
    """The existing RI catalogue could not be read."""


def _rows(query, params=(), *, db_path=None):
    path = Path(db_path if db_path is not None else RI_LOCAL_INDEX_DB)
    if not path.is_file():
        return []
    try:
        with closing(sqlite3.connect(f'{path.resolve().as_uri()}?mode=ro', uri=True)) as connection:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute(query, params)]
    except (OSError, sqlite3.Error) as error:
        raise RiCatalogueError('RI-Index nicht lesbar. Bitte die lokale RI-Datenbank aktualisieren.') from error


def list_calendar_sessions():
    """Read the separate RI online calendar without accessing BI data."""
    return _rows("SELECT * FROM sessions ORDER BY date DESC", db_path=RI_ONLINE_INDEX_DB)


def list_sessions():
    """Return local RI sessions with TOP and document counts."""
    return [_with_session_display_fields(row) for row in _rows('''
        SELECT s.*,
            (SELECT COUNT(*) FROM agenda_items a WHERE a.session_id=s.session_id) AS agenda_count,
            (SELECT COUNT(*) FROM documents d WHERE d.session_id=s.session_id) AS document_count
        FROM sessions s ORDER BY s.date DESC, s.committee, s.session_id
    ''')]


def _local_file(session_path, local_path):
    if not session_path or not local_path:
        return None
    try:
        root = Path(RI_RAW_DATA_DIR).resolve()
        session = Path(str(session_path).replace('\\', '/'))
        if not session.is_absolute():
            session = REPO_ROOT / session
        session = session.resolve()
        if not session.is_relative_to(root) or session == root:
            return None
        document = Path(str(local_path).replace('\\', '/'))
        path = (session / document).resolve()
        if not path.is_relative_to(session) or not path.is_relative_to(root):
            return None
        return path if path.is_file() and path.stat().st_size > 0 else None
    except (OSError, ValueError, RuntimeError):
        return None


def _prepare_document(document, session):
    path = _local_file(session.get('session_path'), document.get('local_path'))
    document['source_file_available'] = path is not None
    document['pdf_view_available'] = path is not None and path.suffix.lower() == '.pdf'
    document['display_type'] = document.get('document_type') or document.get('content_type') or '–'
    # Document visibility comes from the BI comparison, independently of TOP labels.
    document['visibility'] = 'öffentlich' if document.get('visibility') == 'öffentlich' else 'nicht öffentlich'
    return path


def get_session(session_id):
    """Return RI TOPs and documents without consulting the public catalogue."""
    found = _rows('SELECT * FROM sessions WHERE session_id=?', (session_id,))
    if not found:
        return None
    session = _with_session_display_fields(found[0])
    agenda = _rows('SELECT * FROM agenda_items WHERE session_id=? ORDER BY id', (session_id,))
    documents = _rows('SELECT * FROM documents WHERE session_id=? ORDER BY id', (session_id,))
    by_agenda = defaultdict(list)
    for document in documents:
        _prepare_document(document, session)
        by_agenda[str(document.get('agenda_item') or '')].append(document)
    for item in agenda:
        number = str(item.get('number') or '')
        prefix = re.match(r'^\s*(Ö|N)(?=\s|\d|$)', number, re.IGNORECASE)
        item['visibility'] = ('öffentlich' if prefix[1].upper() == 'Ö' else 'nicht öffentlich') if prefix else 'nicht gekennzeichnet'
        item['documents'] = by_agenda[number]
    available = sum(document['source_file_available'] for document in documents)
    session.update(agenda_items=agenda, documents=documents, source_status={
        'document_count': len(documents), 'available_count': available,
        'missing_count': len(documents) - available,
    })
    return session


def get_local_pdf_document(session_id, document_id):
    """Resolve a PDF bound to the requested RI session and RI raw-data tree."""
    found = _rows('''SELECT d.*, s.session_path FROM documents d
        JOIN sessions s ON s.session_id=d.session_id WHERE d.session_id=? AND d.id=?''',
        (session_id, document_id))
    if not found:
        return None
    document = found[0]
    path = _prepare_document(document, document)
    return path if document['pdf_view_available'] else None
