"""Isolated persistent background jobs for the RI script controls."""
from contextlib import contextmanager
from collections import deque
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import threading
from uuid import uuid4

from src.observability import RUN_ID_ENV
from src.paths import REPO_ROOT, RI_DB_DIR
from .ri_forms import ACTIONS, build_command, RiFetchForm
import sys
from .service_jobs import _pid_alive

JOBS_DB = RI_DB_DIR / "ri_jobs.sqlite"
STATUS_LABELS = {"queued": "wartet", "running": "läuft", "ok": "erfolgreich",
                 "partial": "mit Hinweisen abgeschlossen", "error": "fehlgeschlagen"}


class RiJobError(ValueError):
    """A RI task cannot be reserved or started."""


class RiJobBusyError(RiJobError):
    """A new request can open the already active RI job instead."""

    def __init__(self, job_id):
        super().__init__('Ein RI-Auftrag läuft bereits. Bitte dessen Abschluss abwarten.')
        self.job_id = job_id


def _now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _connect(create=False):
    path = Path(JOBS_DB)
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    if create:
        connection.execute('''CREATE TABLE IF NOT EXISTS ri_jobs (
            job_id TEXT PRIMARY KEY, action TEXT NOT NULL, status TEXT NOT NULL,
            exit_code INTEGER, output TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
            started_at TEXT NOT NULL DEFAULT '', finished_at TEXT NOT NULL DEFAULT '',
            owner_pid INTEGER NOT NULL, child_pid INTEGER NOT NULL DEFAULT 0)''')
        columns = {row[1] for row in connection.execute('PRAGMA table_info(ri_jobs)')}
        for name, declaration in (('phase', "TEXT NOT NULL DEFAULT ''"), ('index_requested', 'INTEGER NOT NULL DEFAULT 0'),
                                  ('download_exit_code', 'INTEGER'), ('index_exit_code', 'INTEGER')):
            if name not in columns:
                connection.execute(f'ALTER TABLE ri_jobs ADD COLUMN {name} {declaration}')
        connection.commit()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _recover(connection):
    for row in connection.execute("SELECT * FROM ri_jobs WHERE status IN ('queued','running')").fetchall():
        if not _pid_alive(row['owner_pid']) and not _pid_alive(row['child_pid']):
            connection.execute("UPDATE ri_jobs SET status='error', finished_at=?, output=? WHERE job_id=?",
                               (_now(), "RI-Auftrag wurde unterbrochen. Bitte erneut starten.", row['job_id']))


def _present(row):
    if row is None:
        return None
    result = dict(row)
    result['label'] = ACTIONS.get(result['action'], ('RI-Auftrag',))[0]
    result['status_label'] = STATUS_LABELS.get(result['status'], 'unbekannt')
    result['running'] = result['status'] in {'queued', 'running'}
    result['phase_label'] = {'download': 'Download', 'index': 'Lokalen Index aufbauen', 'completed': 'Abgeschlossen'}.get(result.get('phase'), 'Auftrag')
    if result.get('index_requested'):
        result['label'] = 'Unterlagen und lokalen Index aktualisieren'
        result['index_result_label'] = ('läuft' if result.get('phase') == 'index' and result['running'] else
            'Noch nicht gestartet' if result['running'] and result.get('index_exit_code') is None else
            'Nicht ausgeführt' if result.get('index_exit_code') is None else str(result['index_exit_code']))
    result.pop('owner_pid', None)
    result.pop('child_pid', None)
    return result


def list_jobs():
    """Read only the RI history, without opening the public job database."""
    if not Path(JOBS_DB).is_file():
        return []
    with _connect() as connection:
        _recover(connection)
        return [_present(row) for row in connection.execute(
            'SELECT * FROM ri_jobs ORDER BY created_at DESC, rowid DESC LIMIT 20')]


def get_job(job_id):
    """Read one private RI job by its identifier."""
    if not Path(JOBS_DB).is_file():
        return None
    with _connect() as connection:
        _recover(connection)
        return _present(connection.execute('SELECT * FROM ri_jobs WHERE job_id=?', (job_id,)).fetchone())


def _update(job_id, **values):
    # Keys come only from the worker implementation, never from request input.
    with _connect() as connection:
        connection.execute('UPDATE ri_jobs SET ' + ','.join(key + '=?' for key in values) + ' WHERE job_id=?',
                           (*values.values(), job_id))


def start_job(action, data):
    """Reserve a single RI operation before launching its background worker."""
    command = build_command(action, data)
    index_after = False
    if action == 'ri_fetch':
        form = RiFetchForm(data)
        if form.is_valid():
            index_after = form.cleaned_data['update_local_index']
    job_id = uuid4().hex
    try:
        with _connect(create=True) as connection:
            connection.execute('BEGIN IMMEDIATE')
            _recover(connection)
            active = connection.execute("SELECT job_id FROM ri_jobs WHERE status IN ('queued','running')").fetchone()
            if active:
                raise RiJobBusyError(active['job_id'])
            connection.execute('INSERT INTO ri_jobs(job_id,action,status,created_at,owner_pid) VALUES(?,?,?,?,?)',
                               (job_id, action, 'queued', _now(), os.getpid()))
            connection.execute('UPDATE ri_jobs SET index_requested=? WHERE job_id=?', (int(index_after), job_id))
            connection.execute("DELETE FROM ri_jobs WHERE status NOT IN ('queued','running') AND job_id NOT IN "
                               '(SELECT job_id FROM ri_jobs ORDER BY created_at DESC, rowid DESC LIMIT 50)')
    except (OSError, sqlite3.Error):
        raise RiJobError('RI-Jobablage ist nicht verfügbar. Dateirechte und Datenbank prüfen.') from None
    try:
        threading.Thread(target=_run_job, args=(job_id, command, index_after), daemon=True).start()
    except Exception:
        _update(job_id, status='error', finished_at=_now(), output='RI-Auftrag konnte nicht gestartet werden.')
        raise RiJobError('RI-Auftrag konnte nicht gestartet werden.') from None
    return job_id


def _safe_line(line):
    return re.sub(r'https?://session\.melle\.info/ri/[^\s"\'<>]*', '[RI-URL]', line.rstrip())[:2000]


def _run_job(job_id, command, index_after=False):
    process = None
    lines = deque(maxlen=300)
    try:
        _update(job_id, status='running', started_at=_now())
        environment = {**os.environ, RUN_ID_ENV: job_id, 'PYTHONUNBUFFERED': '1', 'PYTHONIOENCODING': 'utf-8'}
        stages = [('download' if index_after else 'operation', command)]
        if index_after:
            stages.append(('index', [sys.executable, 'scripts/build_ri_local_index.py']))
        exit_code = 0
        download_exit = None
        active_phase = 'operation'
        for phase, stage_command in stages:
            if phase == 'index' and download_exit not in (0, 2):
                lines.append('Indexnachlauf nicht ausgeführt: Download wurde abgebrochen.')
                break
            active_phase = phase
            _update(job_id, phase=phase, child_pid=0)
            if index_after:
                lines.append('--- ' + ('Download' if phase == 'download' else 'Lokalen Index aufbauen') + ' ---')
            process = subprocess.Popen(stage_command, cwd=str(REPO_ROOT), env=environment,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, encoding='utf-8', errors='replace')
            _update(job_id, child_pid=process.pid)
            for line in process.stdout:
                lines.append(_safe_line(line))
                _update(job_id, output='\n'.join(lines)[-64000:])
            stage_exit = process.wait()
            process.stdout.close()
            _update(job_id, child_pid=0)
            if index_after:
                _update(job_id, **{('download_exit_code' if phase == 'download' else 'index_exit_code'): stage_exit})
            if phase == 'download':
                download_exit = stage_exit
                exit_code = stage_exit
            elif phase == 'index':
                exit_code = download_exit if stage_exit == 0 else 1
                if stage_exit != 0:
                    lines.append('Indexaufbau fehlgeschlagen. Heruntergeladene Dateien bleiben erhalten; lokalen Index separat erneut starten.')
            else:
                exit_code = stage_exit
        status = 'ok' if exit_code == 0 else 'partial' if exit_code == 2 else 'error'
        _update(job_id, status=status, phase='completed' if status != 'error' else active_phase,
                exit_code=exit_code, finished_at=_now(), output='\n'.join(lines)[-64000:])
    except Exception:
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait()
        try:
            _update(job_id, status='error', exit_code=1, finished_at=_now(),
                    output='\n'.join([*lines, 'RI-Auftrag abgebrochen. Jobablage und lokale Protokolle prüfen.'])[-64000:])
        except (OSError, sqlite3.Error):
            pass
    finally:
        if process is not None and process.stdout is not None:
            process.stdout.close()
