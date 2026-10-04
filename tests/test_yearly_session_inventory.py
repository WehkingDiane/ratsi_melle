from __future__ import annotations

from datetime import date
import os
from pathlib import Path
import sqlite3
import sys

from bs4 import BeautifulSoup
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
from core.services import paths
from core.services.session_inventory import dashboard_session_groups, yearly_session_inventory

pytestmark = pytest.mark.integration


def _database(path, sessions, documents=()):
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE sessions (session_id TEXT PRIMARY KEY, date TEXT,
                committee TEXT, meeting_name TEXT, start_time TEXT, location TEXT);
            CREATE TABLE documents (id INTEGER PRIMARY KEY, session_id TEXT);
        """)
        connection.executemany("INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?)",
                               [(sid, day, title, title, '19:00 Uhr', 'Ratssaal') for sid, day, title in sessions])
        connection.executemany("INSERT INTO documents (session_id) VALUES (?)", [(sid,) for sid in documents])


@pytest.fixture
def inventory_workspace(tmp_path, monkeypatch):
    from data_tools import services as data_services
    from analysis import services as analysis_services
    raw = tmp_path / 'raw'
    raw.mkdir()
    local, online = tmp_path / 'local.sqlite', tmp_path / 'online.sqlite'
    monkeypatch.setattr(paths, 'RAW_DATA_DIR', raw)
    monkeypatch.setattr(paths, 'LOCAL_INDEX_DB', local)
    monkeypatch.setattr(paths, 'ONLINE_INDEX_DB', online)
    monkeypatch.setattr(data_services, 'LOCAL_INDEX_DB', local)
    monkeypatch.setattr(analysis_services, 'LOCAL_INDEX_DB', local)
    return raw, local, online


def test_yearly_status_compares_ids_without_excluding_early_2021(inventory_workspace):
    raw, local, online = inventory_workspace
    for day, sid in [('2021-01-13', '1'), ('2025-03-01', '2')]:
        folder = raw / day[:4] / day[5:7] / f'{day}_Rat_{sid}'
        folder.mkdir(parents=True)
        (folder / 'agenda').mkdir()
    _database(local, [('1', '2021-01-13', 'Rat'), ('2', '2025-03-01', 'Rat')], ['1', '2', '2'])
    _database(online, [('1', '2021-01-13', 'Rat'), ('3', '2025-03-02', 'Ortsrat')], ['3'])
    before = (local.read_bytes(), online.read_bytes())
    result = yearly_session_inventory()
    assert [r['year'] for r in result['years']] == [2025, 2021]
    year, old = result['years']
    assert (year['raw_count'], year['local_count'], year['online_count']) == (1, 1, 1)
    assert (year['missing_online'], year['missing_raw'], year['missing_local']) == (1, 1, 0)
    assert (year['local_documents'], year['online_documents']) == (2, 1)
    assert old['missing_online'] == old['missing_raw'] == 0
    assert old['sessions'][0]['date'] == '2021-01-13'
    assert (local.read_bytes(), online.read_bytes()) == before


def test_missing_source_is_unknown_and_is_not_created(inventory_workspace):
    raw, local, online = inventory_workspace
    _database(local, [('1', '2021-01-13', 'Rat')])
    result = yearly_session_inventory()
    year = result['years'][0]
    assert year['online_count'] is None
    assert year['missing_online'] is None
    assert year['raw_count'] == 0
    assert year['sessions'][0]['online_present'] is None
    assert result['warnings']
    assert not online.exists()


def test_legacy_layout_and_unknown_folder_are_counted_with_warning(inventory_workspace):
    raw, local, online = inventory_workspace
    for name in ('2021-02-01_Rat_1', 'unbekannter_ordner'):
        folder = raw / '2021' / name
        folder.mkdir(parents=True)
        (folder / 'session_detail.html').write_text('<html></html>')
    _database(local, [])
    _database(online, [])
    result = yearly_session_inventory()
    assert result['years'][0]['raw_count'] == 2
    assert result['years'][0]['missing_online'] is None
    assert any('eindeutig zugeordnet' in warning for warning in result['warnings'])


def test_corrupt_index_remains_unknown(inventory_workspace):
    raw, local, online = inventory_workspace
    _database(local, [('1', '2025-03-01', 'Rat')])
    online.write_text('not sqlite')
    result = yearly_session_inventory()
    assert result['years'][0]['online_count'] is None
    assert any('nicht lesbar' in warning for warning in result['warnings'])


def test_upcoming_meetings_include_online_only_and_separate_past(inventory_workspace):
    raw, local, online = inventory_workspace
    _database(online, [('2', '2026-10-07', 'Später'), ('1', '2026-10-04', 'Heute'),
                       ('3', '2026-10-03', 'Gestern'), ('4', 'invalid', 'Ohne Datum')])
    local_sessions = [{'session_id': '3', 'date': '2026-10-03'},
                      {'session_id': '2', 'date': '2026-10-07'}]
    result = dashboard_session_groups(local_sessions, date(2026, 10, 4))
    assert [s['session_id'] for s in result['upcoming_sessions']] == ['1', '2']
    assert [s['local_present'] for s in result['upcoming_sessions']] == [False, True]
    assert result['upcoming_sessions'][0]['display_date'] == '04.10.2026'
    assert [s['session_id'] for s in result['recent_sessions']] == ['3']
    assert len(dashboard_session_groups(local_sessions, date(2026, 10, 4), limit=1)['upcoming_sessions']) == 1


def test_upcoming_local_fallback_does_not_create_online_database(inventory_workspace):
    raw, local, online = inventory_workspace
    result = dashboard_session_groups([{'session_id': '1', 'date': '2026-10-04'}], date(2026, 10, 4))
    assert result['upcoming_sessions'][0]['local_present']
    assert result['upcoming_notice']
    assert not online.exists()


def _client():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web.settings')
    import django
    django.setup()
    from django.test import Client
    return Client()


def test_yearly_detail_page_displays_all_years_and_rejects_writes(inventory_workspace, monkeypatch):
    from data_tools import services
    raw, local, online = inventory_workspace
    _database(local, [('1', '2021-01-13', '<script>unsafe</script>')])
    _database(online, [('2', '2025-03-01', 'Rat')])
    monkeypatch.setattr(services, 'service_status', lambda: {'qdrant_summary': 'Index unvollständig'})
    client = _client()
    response = client.get('/daten/status/details/')
    assert response.status_code == 200
    content = response.content.decode()
    assert '2021' in content and '2025' in content
    assert 'Index unvollständig' in content
    assert '<script>unsafe</script>' not in content
    assert '&lt;script&gt;unsafe&lt;/script&gt;' in content
    assert client.post('/daten/status/details/').status_code == 405
    assert client.head('/daten/status/details/').status_code == 200


def test_dashboard_renders_upcoming_before_recent_without_dead_local_link(inventory_workspace, monkeypatch):
    from core import views
    raw, local, online = inventory_workspace
    _database(online, [('2', '2026-10-07', 'Kommender Ortsrat')])
    monkeypatch.setattr(views.timezone, 'localdate', lambda: date(2026, 10, 4))
    monkeypatch.setattr(views.analysis_services, 'source_overview', lambda: {})
    monkeypatch.setattr(views.analysis_services, 'list_analysis_outputs', lambda: [])
    monkeypatch.setattr(views.analysis_services, 'list_sessions', lambda: [
        {'session_id': '1', 'date': '2026-10-03', 'meeting_name': 'Vergangener Rat'}])
    response = _client().get('/')
    assert response.status_code == 200
    content = response.content.decode()
    assert content.index('Nächste Sitzungen') < content.index('Letzte Sitzungen')
    assert 'Kommender Ortsrat' in content and 'Vergangener Rat' in content
    assert 'Noch nicht lokal indexiert' in content
    soup = BeautifulSoup(content, 'html.parser')
    upcoming = next(section for section in soup.select('section') if section.find('h2', string='Nächste Sitzungen'))
    assert not upcoming.select('a[href*="/sitzungen/2"]')
