"""Offline checks for the isolated RI local builder."""
import json
from pathlib import Path
import sqlite3

import pytest

from scripts import build_ri_local_index as builder
pytestmark = pytest.mark.integration


@pytest.fixture
def setup(tmp_path, monkeypatch):
    root = tmp_path / 'ri'
    raw = root / 'raw'
    raw.mkdir(parents=True)
    monkeypatch.setattr(builder, 'RI_ROOT', root)

    def no_network(*args, **kwargs):
        pytest.fail('Local builder must not make network requests')

    monkeypatch.setattr(builder.SessionNetClient, '_request', no_network)
    return raw, root / 'db/local_index.sqlite'


def seed(raw, session_id='8174'):
    folder = raw / '2026/11' / f'2026-11-19-Ausschuss-{session_id}'
    folder.mkdir(parents=True)
    (folder / 'public.pdf').write_bytes(b'%PDF-public')
    (folder / 'private.pdf').write_bytes(b'%PDF-private')
    (folder / 'empty.pdf').touch()
    docs = []
    for identifier, path, visibility in [('145203', 'public.pdf', 'öffentlich'),
                                         ('145460', 'private.pdf', 'nicht öffentlich'),
                                         ('1', 'missing.pdf', 'öffentlich'),
                                         ('2', '../../outside.pdf', 'öffentlich'),
                                         ('3', 'empty.pdf', 'öffentlich')]:
        docs.append({'url': f'https://session.melle.info/ri/getfile.asp?id={identifier}&type=do',
                     'path': path, 'title': 'Vorlage', 'visibility': visibility,
                     'visibility_checked_at': '2026-11-17T10:00:00Z'})
    manifest = {'session': {'id': session_id}, 'documents': docs}
    (folder / 'manifest.json').write_text(json.dumps(manifest))
    (folder / 'agenda_summary.json').write_text(json.dumps({'agenda_items': [{'number': 'Ö 13', 'title': 'Sport', 'documents_present': True}]}))
    return folder


def rows(output):
    with sqlite3.connect(output) as conn:
        return conn.execute('SELECT document_id, visibility, local_path FROM documents ORDER BY document_id').fetchall()


def test_local_only_documents_and_manifest_visibility(setup):
    raw, output = setup
    seed(raw)
    before = {str(p): p.read_bytes() for p in raw.rglob('*') if p.is_file()}
    builder.build_index(raw, output, False, False)
    assert rows(output) == [('145203', 'öffentlich', 'public.pdf'), ('145460', 'nicht öffentlich', 'private.pdf')]
    assert before == {str(p): p.read_bytes() for p in raw.rglob('*') if p.is_file()}
    builder.build_index(raw, output, False, False)
    assert len(rows(output)) == 2


def test_manifest_update_and_deleted_file_refresh_automatically(setup):
    raw, output = setup
    folder = seed(raw)
    builder.build_index(raw, output, False, False)
    path = folder / 'manifest.json'
    payload = json.loads(path.read_text())
    payload['documents'][0].pop('visibility')
    path.write_text(json.dumps(payload))
    (folder / 'private.pdf').unlink()
    builder.build_index(raw, output, False, False)
    assert rows(output) == [('145203', 'nicht öffentlich', 'public.pdf')]


def test_only_refresh_does_not_insert_new_sessions(setup):
    raw, output = setup
    seed(raw)
    builder.build_index(raw, output, False, True)
    assert rows(output) == []
    builder.build_index(raw, output, False, False)
    seed(raw, '9999')
    builder.build_index(raw, output, True, True)
    with sqlite3.connect(output) as conn:
        assert conn.execute('SELECT session_id FROM sessions').fetchall() == [('8174',)]


def test_stale_html_reparse_preserves_visibility(setup):
    raw, output = setup
    folder = seed(raw)
    html = '<table class="smctablesitzung"><tr><td>Ö 13</td><td>Sport</td><td><a href="getfile.asp?id=145203&amp;type=do">Vorlage</a><a href="getfile.asp?id=145460&amp;type=do">Anlage</a></td></tr></table>'
    (folder / 'session_detail.html').write_text(html)
    builder.build_index(raw, output, False, False)
    assert rows(output) == [('145203', 'öffentlich', 'public.pdf'), ('145460', 'nicht öffentlich', 'private.pdf')]
    with sqlite3.connect(output) as conn:
        assert '/ri/' in conn.execute('SELECT detail_url FROM sessions').fetchone()[0]


def test_public_and_online_outputs_rejected(setup):
    raw, output = setup
    with pytest.raises(ValueError):
        builder.build_index(raw, builder.REPO_ROOT / 'data/db/local_index.sqlite', False, False)
    with pytest.raises(ValueError):
        builder.build_index(raw, output.parent / 'online_session_index.sqlite', False, False)
    with pytest.raises(ValueError):
        builder.build_index(raw.parent, output, False, False)
    assert not output.exists()
