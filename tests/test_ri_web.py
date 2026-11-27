"""RI UI isolation and script controls with temporary databases and fake workers."""
import io
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'web'))
django = pytest.importorskip('django')
pytestmark = pytest.mark.integration


@pytest.fixture(scope='module')
def web_runtime():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web.settings')
    django.setup()


@pytest.fixture
def ri_env(web_runtime, tmp_path, monkeypatch):
    from core import ri_jobs, ri_views, service_jobs
    monkeypatch.setattr(ri_jobs, 'JOBS_DB', tmp_path / 'ri/ri_jobs.sqlite')
    monkeypatch.setattr(ri_views, 'RI_LOCAL_INDEX_DB', tmp_path / 'ri/local.sqlite')
    monkeypatch.setattr(ri_views, 'RI_ONLINE_INDEX_DB', tmp_path / 'ri/online.sqlite')
    monkeypatch.setattr(service_jobs, 'SERVICE_JOBS_DB', tmp_path / 'public_jobs.sqlite')
    monkeypatch.setattr('src.config.ri.RI_ROOT', tmp_path / 'ri')
    return ri_jobs


@pytest.fixture
def client(ri_env):
    from django.test import Client
    return Client()


@pytest.mark.parametrize('path', ['', 'zugang/', 'daten/', 'daten/fetch/', 'daten/build/'])
def test_local_ri_pages_are_accessible_without_login(client, ri_env, monkeypatch, path):
    monkeypatch.setattr(ri_env, 'start_job', lambda *args: pytest.fail('GET started a job'))
    response = client.get('/ratsbereich/' + path)
    assert response.status_code == 200
    assert 'no-store' in response['Cache-Control']
    assert 'Angemeldet als' not in response.content.decode()
    assert b'type="password"' not in response.content
    assert not ri_env.JOBS_DB.exists()


@pytest.mark.parametrize('path', ['anmelden/', 'abmelden/'])
def test_old_login_links_open_ri_status_without_login(client, path):
    response = client.get('/ratsbereich/' + path)
    assert response.status_code == 302
    assert response['Location'] == '/ratsbereich/daten/'


@pytest.mark.parametrize('path,expected', [('zugang/', ['ri_login']), ('daten/fetch/', ['ri_fetch']),
                                          ('daten/build/', ['ri_online', 'ri_local'])])
def test_local_forms_do_not_execute_on_get(client, ri_env, monkeypatch, path, expected):
    from bs4 import BeautifulSoup
    monkeypatch.setattr(ri_env, 'start_job', lambda *args: pytest.fail('GET started a job'))
    response = client.get('/ratsbereich/' + path)
    assert response.status_code == 200
    soup = BeautifulSoup(response.content, 'html.parser')
    assert [field['value'] for field in soup.select('input[name="action"]')] == expected
    assert soup.select('input[name="csrfmiddlewaretoken"]')


@pytest.mark.parametrize('action,path,extra,expected', [
    ('ri_login', 'zugang/', {}, ['scripts/login_ri.py']),
    ('ri_fetch', 'daten/fetch/', {'year': '2026', 'months': '10,11', 'force_download': 'on'},
     ['scripts/fetch_ri_sessions.py', '2026', '--months', '11', '--force-download']),
    ('ri_online', 'daten/build/', {'year': '2026', 'months': '11', 'only_refresh': 'on'},
     ['scripts/build_ri_online_index_db.py', '2026', '--months', '11', '--only-refresh']),
    ('ri_local', 'daten/build/', {'refresh_existing': 'on'}, ['scripts/build_ri_local_index.py', '--refresh-existing']),
])
def test_valid_ri_forms_start_only_fixed_commands(client, ri_env, monkeypatch, action, path, extra, expected):
    calls = []
    class Thread:
        def __init__(self, **kwargs): calls.append(kwargs)
        def start(self): pass
    monkeypatch.setattr(ri_env.threading, 'Thread', Thread)
    response = client.post('/ratsbereich/' + path, {'action': action, **extra})
    assert response.status_code == 302
    assert '/ratsbereich/daten/jobs/' in response['Location']
    assert calls[0]['args'][1] == [sys.executable, *expected]
    assert len(ri_env.list_jobs()) == 1


@pytest.mark.parametrize('payload', [
    {'action': 'fetch_sessions'}, {'action': 'ri_local'},
    {'action': 'ri_fetch', 'year': '2025', 'months': '11'},
    {'action': 'ri_fetch', 'year': '2026', 'months': '13'},
    {'action': 'ri_fetch', 'year': '2026', 'months': '11', 'output': 'data/db/local_index.sqlite'},
    {'action': 'ri_fetch', 'year': '2026', 'months': '11', 'token': 'synthetic-token'},
])
def test_wrong_actions_and_parameters_do_not_start_jobs(client, ri_env, monkeypatch, payload):
    monkeypatch.setattr(ri_env, 'start_job', lambda *args: pytest.fail('Invalid action started'))
    assert client.post('/ratsbereich/daten/fetch/', payload).status_code in {200, 400}
    assert not ri_env.JOBS_DB.exists()


def test_csrf_is_required_for_ri_actions(ri_env, monkeypatch):
    from django.test import Client
    client = Client(enforce_csrf_checks=True)
    monkeypatch.setattr(ri_env, 'start_job', lambda *args: pytest.fail('CSRF bypass'))
    assert client.post('/ratsbereich/zugang/', {'action': 'ri_login'}).status_code == 403


def test_parallel_ri_jobs_are_rejected_and_never_public(client, ri_env, monkeypatch):
    class Thread:
        def __init__(self, **kwargs): pass
        def start(self): pass
    monkeypatch.setattr(ri_env.threading, 'Thread', Thread)
    job_id = ri_env.start_job('ri_login', {'action': 'ri_login'})
    with pytest.raises(ri_env.RiJobError, match='läuft bereits'):
        ri_env.start_job('ri_local', {'action': 'ri_local'})
    ri_env._update(job_id, output='<script>synthetic-private-output</script>')
    public = client.get('/daten/jobs/status/')
    assert job_id not in public.content.decode()
    assert 'synthetic-private-output' not in public.content.decode()
    assert client.get(f'/daten/jobs/{job_id}/status/').status_code == 404
    response = client.get(f'/ratsbereich/daten/jobs/{job_id}/')
    assert response.status_code == 200
    assert b'&lt;script&gt;' in response.content
    assert b'<script>synthetic-private-output' not in response.content
    assert 'no-store' in response['Cache-Control']


@pytest.mark.parametrize('code,status', [(0, 'ok'), (2, 'partial'), (1, 'error')])
def test_worker_persists_exit_status_without_exposing_urls(ri_env, monkeypatch, code, status):
    class Thread:
        def __init__(self, **kwargs): pass
        def start(self): pass
    monkeypatch.setattr(ri_env.threading, 'Thread', Thread)
    job_id = ri_env.start_job('ri_login', {'action': 'ri_login'})
    class Process:
        pid = os.getpid()
        stdout = io.StringIO('https://session.melle.info/ri/getfile.asp?id=123&type=do\n')
        def wait(self): return code
        def poll(self): return code
    monkeypatch.setattr(ri_env.subprocess, 'Popen', lambda *args, **kwargs: Process())
    ri_env._run_job(job_id, [sys.executable, 'scripts/login_ri.py'])
    job = ri_env.get_job(job_id)
    assert job['status'] == status
    assert job['exit_code'] == code
    assert 'getfile.asp' not in job['output']


def test_abandoned_job_is_marked_interrupted(ri_env, monkeypatch):
    class Thread:
        def __init__(self, **kwargs): pass
        def start(self): pass
    monkeypatch.setattr(ri_env.threading, 'Thread', Thread)
    job_id = ri_env.start_job('ri_login', {'action': 'ri_login'})
    monkeypatch.setattr(ri_env, '_pid_alive', lambda pid: False)
    assert ri_env.get_job(job_id)['status'] == 'error'
    assert 'unterbrochen' in ri_env.get_job(job_id)['output']


def test_build_forms_have_unique_control_ids(client):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(client.get('/ratsbereich/daten/build/').content, 'html.parser')
    ids = [node['id'] for node in soup.select('[id]')]
    assert len(ids) == len(set(ids))


def test_repeated_parameters_are_rejected(client, ri_env, monkeypatch):
    monkeypatch.setattr(ri_env, 'start_job', lambda *args: pytest.fail('Duplicate input started job'))
    response = client.post('/ratsbereich/daten/fetch/',
                           'action=ri_fetch&year=2026&months=11&months=12',
                           content_type='application/x-www-form-urlencoded')
    assert response.status_code == 200
    assert 'nur einmal' in response.content.decode()


def test_public_fetch_endpoint_rejects_ri_actions(client, ri_env, monkeypatch):
    from core import service_jobs
    monkeypatch.setattr(service_jobs, 'start_service_job', lambda *args: pytest.fail('Public RI command'))
    response = client.post('/buergerinformation/daten/fetch/', {'action': 'ri_login'})
    assert response.status_code == 400
    assert not ri_env.JOBS_DB.exists()


def test_worker_launch_failure_releases_reservation(ri_env, monkeypatch):
    class Thread:
        def __init__(self, **kwargs): pass
        def start(self): pass
    monkeypatch.setattr(ri_env.threading, 'Thread', Thread)
    job_id = ri_env.start_job('ri_login', {'action': 'ri_login'})
    def fail(*args, **kwargs):
        raise OSError('synthetic-private-launch-detail')
    monkeypatch.setattr(ri_env.subprocess, 'Popen', fail)
    ri_env._run_job(job_id, [sys.executable, 'scripts/login_ri.py'])
    job = ri_env.get_job(job_id)
    assert job['status'] == 'error'
    assert 'synthetic-private-launch-detail' not in job['output']
    assert ri_env.start_job('ri_local', {'action': 'ri_local'})


def test_repeated_start_opens_existing_job_and_completed_job_does_not_block(client, ri_env, monkeypatch):
    launches = []
    class Thread:
        def __init__(self, **kwargs): launches.append(kwargs)
        def start(self): pass
    monkeypatch.setattr(ri_env.threading, 'Thread', Thread)
    payload = {'action': 'ri_fetch', 'year': '2026', 'months': '12'}
    first = client.post('/ratsbereich/daten/fetch/', payload)
    job = ri_env.list_jobs()[0]
    second = client.post('/ratsbereich/daten/fetch/', payload)
    assert first.status_code == second.status_code == 302
    assert second['Location'].split('?')[0] == first['Location']
    assert 'already_running=1' in second['Location']
    assert len(launches) == 1
    assert len(ri_env.list_jobs()) == 1
    response = client.get(second['Location'])
    assert 'kein weiterer Auftrag gestartet' in response.content.decode()
    ri_env._update(job['job_id'], status='partial', exit_code=2)
    completed = client.get(second['Location'])
    assert 'mit Hinweisen abgeschlossen' in completed.content.decode()
    third = client.post('/ratsbereich/daten/fetch/', payload)
    assert third.status_code == 302
    assert third['Location'] != first['Location']
    assert len(launches) == 2


def test_ri_job_indicator_and_form_banner_follow_active_job_only(client, ri_env, monkeypatch):
    from bs4 import BeautifulSoup
    class Thread:
        def __init__(self, **kwargs): pass
        def start(self): pass
    monkeypatch.setattr(ri_env.threading, 'Thread', Thread)
    job_id = ri_env.start_job('ri_login', {'action': 'ri_login'})
    ri_env._update(job_id, output='synthetic-private-output')
    response = client.get('/ratsbereich/daten/fetch/')
    soup = BeautifulSoup(response.content, 'html.parser')
    assert soup.select_one('#job-indicator')['data-status-url'] == '/ratsbereich/daten/jobs/status/'
    banner = soup.select_one('[data-ri-active-job]')
    assert not banner.has_attr('hidden')
    assert job_id in banner.select_one('a')['href']
    assert soup.select_one('script[src="/static/core/js/ri_forms.js"]')
    api = client.get('/ratsbereich/daten/jobs/status/')
    assert api.status_code == 200
    assert 'no-store' in api['Cache-Control']
    active = api.json()['active']
    assert [job['job_id'] for job in active] == [job_id]
    assert active[0]['area'] == 'ri'
    assert 'output' not in active[0]
    assert 'synthetic-private-output' not in api.content.decode()
    public = client.get('/daten/jobs/status/')
    assert job_id not in public.content.decode()
    ri_env._update(job_id, status='partial', exit_code=2)
    assert client.get('/ratsbereich/daten/jobs/status/').json()['active'] == []
    soup = BeautifulSoup(client.get('/ratsbereich/daten/fetch/').content, 'html.parser')
    assert soup.select_one('[data-ri-active-job]').has_attr('hidden')


@pytest.mark.parametrize('path', ['daten/', 'daten/fetch/', 'daten/build/', 'zugang/'])
def test_ri_data_status_distinguishes_empty_available_and_unreadable(client, monkeypatch, tmp_path, path):
    import sqlite3
    from bs4 import BeautifulSoup
    from core import ri_views

    online = tmp_path / 'online.sqlite'
    local = tmp_path / 'local.sqlite'
    monkeypatch.setattr(ri_views, 'RI_ONLINE_INDEX_DB', online)
    monkeypatch.setattr(ri_views, 'RI_LOCAL_INDEX_DB', local)
    with sqlite3.connect(online) as db:
        for table in ('sessions', 'agenda_items', 'documents'):
            db.execute(f'CREATE TABLE {table} (id INTEGER)')
    soup = BeautifulSoup(client.get('/ratsbereich/' + path).content, 'html.parser')
    panel = soup.select_one('.service-status')
    assert 'noch nicht aufgebaut' in panel.select_one('dd.status-muted').text
    assert '0 Sitzungen' in panel.select_one('dd.status-ok').text
    local.write_bytes(b'not a database')
    soup = BeautifulSoup(client.get('/ratsbereich/' + path).content, 'html.parser')
    assert 'nicht lesbar' in soup.select_one('.service-status dd.status-error').text


@pytest.mark.parametrize('state,code,css', [('queued', None, 'status-warning'),
                                          ('ok', 0, 'status-ok'),
                                          ('partial', 2, 'status-warning'),
                                          ('error', 1, 'status-error')])
def test_ri_job_presentation_preserves_result_and_running_state(client, ri_env, monkeypatch, state, code, css):
    from bs4 import BeautifulSoup

    class Thread:
        def __init__(self, **kwargs): pass
        def start(self): pass

    monkeypatch.setattr(ri_env.threading, 'Thread', Thread)
    job_id = ri_env.start_job('ri_login', {'action': 'ri_login'})
    ri_env._update(job_id, status=state, exit_code=code)
    soup = BeautifulSoup(client.get(f'/ratsbereich/daten/jobs/{job_id}/').content, 'html.parser')
    assert css in soup.select_one('#job-status')['class']
    assert soup.select_one('#job-exit-code').text == ('–' if code is None else str(code))
    assert soup.select_one('#job-running-banner').has_attr('hidden') == (state != 'queued')


@pytest.mark.parametrize('area', ['ri', 'bi', 'legacy'])
def test_shared_job_polling_updates_completion_and_preserves_status_on_network_error(area):
    import shutil
    import subprocess

    node = shutil.which('node')
    if node is None:
        pytest.skip('Node.js is required for JavaScript execution')
    script = ROOT / 'web/core/static/core/js/service_job_detail.js'
    harness = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ids = ['job-panel', 'job-completion-message', 'job-status', 'job-exit-code', 'job-output', 'job-started-at',
             'job-finished-at', 'job-running-banner', 'job-feedback'];
const elements = Object.fromEntries(ids.map(id => [id, {textContent: '', hidden: false}]));
const legacy = process.argv[2] === 'legacy';
const area = legacy ? 'bi' : process.argv[2];
const attrs = {'data-status-url': '/' + area + '/job/status/', 'data-job-area': area,
               'data-service-job-running': 'true', 'data-job-label': 'Testauftrag',
               'data-legacy-job': legacy ? 'true' : 'false'};
elements['job-panel'].getAttribute = key => attrs[key] || null;
const events = [];
let reloads = 0;
const evidence = {textContent: '', getAttribute: () => 'association_label'};
if (area === 'bi') {
  elements['job-progress'] = {hidden: false};
  elements['job-progress-text'] = {textContent: ''};
  elements['model-job-evidence'] = {querySelectorAll: () => [evidence]};
}
let job = {status: 'running', status_label: 'läuft', running: true};
let poll;
let fail = false;
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), {
  document: {getElementById: id => elements[id], querySelector: () => elements['job-panel'],
             dispatchEvent: event => events.push(event)},
  CustomEvent: class {constructor(name, init) {this.type = name; this.detail = init.detail;}},
  window: {setTimeout: callback => { poll = callback; }, location: {reload: () => reloads++}},
  fetch: async (url, options) => {
    assert.equal(url, '/' + area + '/job/status/');
    assert.equal(options.cache, 'no-store');
    if (fail) throw Error('offline');
    return {ok: true, json: async () => ({job, model_job_evidence: {association_label: 'Belegt'}})};
  },
});
const settle = () => new Promise(resolve => setImmediate(resolve));
(async () => {
  await settle();
  assert.equal(elements['job-status'].className, 'status-warning');
  assert.equal(elements['job-running-banner'].hidden, false);
  job = {status: 'partial', status_label: 'mit Hinweisen abgeschlossen', running: false,
         exit_code: 2, finished_at: '2026-11-22', output: '<script>text</script>'};
  await poll();
  assert.equal(elements['job-status'].className, 'status-warning');
  assert.equal(elements['job-running-banner'].hidden, true);
  assert.equal(elements['job-exit-code'].textContent, 2);
  assert.equal(elements['job-output'].textContent, job.output);
  assert.equal(elements['job-finished-at'].textContent, job.finished_at);
  assert.equal(elements['job-completion-message'].textContent, 'Testauftrag wurde mit Hinweisen abgeschlossen.');
  assert.equal(events.length, 1);
  assert.equal(events[0].detail.area, area);
  assert.equal(reloads, legacy ? 1 : 0);
  if (area === 'bi') {
    assert.equal(evidence.textContent, 'Belegt');
    assert.equal(elements['job-progress'].hidden, true);
  }
  job = {...job, status: 'ok', status_label: 'erfolgreich', exit_code: 0};
  await poll();
  assert.equal(elements['job-status'].className, 'status-ok');
  assert.equal(elements['job-exit-code'].textContent, 0);
  job = {...job, status: 'error', status_label: 'fehlgeschlagen', exit_code: 1};
  await poll();
  assert.equal(elements['job-status'].className, 'status-error');
  fail = true;
  await poll();
  assert.equal(elements['job-status'].textContent, 'fehlgeschlagen');
  assert.equal(elements['job-feedback'].hidden, false);
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
    result = subprocess.run([node, '-e', harness, str(script), area], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.fixture
def ri_catalogue(ri_env, tmp_path, monkeypatch):
    import sqlite3
    from core.services import ri_sessions

    raw = tmp_path / 'ri/raw'
    session = raw / '2026/12/2026-12-02-Ausschuss-8179'
    session.mkdir(parents=True)
    (session / 'private.pdf').write_bytes(b'%PDF-1.4\nsynthetic-ri-private')
    db_path = tmp_path / 'catalogue.sqlite'
    monkeypatch.setattr(ri_sessions, 'RI_LOCAL_INDEX_DB', db_path)
    monkeypatch.setattr(ri_sessions, 'RI_RAW_DATA_DIR', raw)
    with sqlite3.connect(db_path) as db:
        db.executescript('''
            CREATE TABLE sessions (session_id TEXT PRIMARY KEY, date TEXT, committee TEXT,
                meeting_name TEXT, start_time TEXT, location TEXT, detail_url TEXT, session_path TEXT);
            CREATE TABLE agenda_items (id INTEGER PRIMARY KEY, session_id TEXT, number TEXT,
                title TEXT, reporter TEXT, status TEXT, decision TEXT, documents_present INTEGER);
            CREATE TABLE documents (id INTEGER PRIMARY KEY, session_id TEXT, title TEXT,
                agenda_item TEXT, document_type TEXT, content_type TEXT, local_path TEXT,
                visibility TEXT);
        ''')
        db.execute('INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?)',
                   ('8179', '2026-12-02', 'Ausschuss', 'Interne Beispielsitzung', '16:00', 'Rathaus',
                    'https://session.melle.info/ri/si0057.asp?__ksinr=8179', str(session)))
        for identifier, number in enumerate(('Ö 1', 'N 1', 'N 1.1', '2'), 1):
            db.execute('INSERT INTO agenda_items VALUES (?,?,?,?,?,?,?,?)',
                       (identifier, '8179', number, 'TOP ' + number, '', '', '', 1))
        for identifier, top, path, visibility in [(1, 'Ö 1', 'private.pdf', 'nicht öffentlich'),
                                                   (2, 'N 1', 'missing.pdf', 'nicht öffentlich'),
                                                   (3, 'N 1.1', 'private.pdf', 'öffentlich')]:
            db.execute('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?)',
                       (identifier, '8179', 'Anlage ' + str(identifier), top, 'Vorlage',
                        'application/pdf', path, visibility))
    return db_path, session


def test_ri_session_details_separate_top_labels_from_document_visibility(client, ri_catalogue):
    from bs4 import BeautifulSoup

    response = client.get('/ratsbereich/sitzungen/8179/')
    assert response.status_code == 200
    assert 'private' in response['Cache-Control'] and 'no-store' in response['Cache-Control']
    soup = BeautifulSoup(response.content, 'html.parser')
    tops = soup.select('.list-item')
    assert ['öffentlich' in tops[0].select_one('.item-main').text,
            'nicht öffentlich' in tops[1].select_one('.item-main').text,
            'nicht öffentlich' in tops[2].select_one('.item-main').text,
            'nicht gekennzeichnet' in tops[3].select_one('.item-main').text] == [True] * 4
    assert 'nicht öffentlich (BI-Abgleich)' in tops[0].text
    assert 'öffentlich (BI-Abgleich)' in tops[2].text
    assert tops[0].select_one('a')['href'] == '/ratsbereich/sitzungen/8179/dokumente/1/pdf/'
    assert not tops[1].select('a')
    assert not soup.select('.page-actions a[href*="analyse/starten"]')
    assert '3' in soup.select_one('.facts').text


def test_ri_session_list_filters_and_paginates_using_ri_links(client, ri_catalogue):
    import sqlite3
    from bs4 import BeautifulSoup

    db_path, session = ri_catalogue
    with sqlite3.connect(db_path) as db:
        for index in range(25):
            db.execute('INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?)',
                       (str(index), '2027-01-01', 'Verwaltungsausschuss', 'Weitere Sitzung',
                        '', 'Rathaus', '', str(session)))
    response = client.get('/ratsbereich/sitzungen/?q=Rathaus&year=2027&committee=Verwaltungsausschuss&page=2')
    assert response.status_code == 200
    soup = BeautifulSoup(response.content, 'html.parser')
    assert '25 Sitzungen gefunden' in soup.text
    assert len(soup.select('tbody tr')) == 5
    assert all(link['href'].startswith('/ratsbereich/sitzungen/') for link in soup.select('tbody a'))
    assert 'year=2027' in soup.select_one('.pagination a')['href']
    assert not soup.select('tbody a[href*="analyse/starten"]')
    assert '1 Sitzungen gefunden' in client.get('/ratsbereich/sitzungen/?q=8179').content.decode()
    assert '0 Sitzungen gefunden' in client.get('/ratsbereich/sitzungen/?year=1999').content.decode()


def test_ri_pdf_is_session_bound_private_and_not_available_from_bi(client, ri_catalogue, monkeypatch, tmp_path):
    import shutil
    import sqlite3
    from analysis import services as bi_services

    ri_db, _ = ri_catalogue
    public_db = tmp_path / 'public.sqlite'
    shutil.copyfile(ri_db, public_db)
    public_session = tmp_path / 'data/raw/2026/12/public-session'
    public_session.mkdir(parents=True)
    (public_session / 'private.pdf').write_bytes(b'%PDF-1.4\nsynthetic-public')
    with sqlite3.connect(public_db) as db:
        db.execute("UPDATE sessions SET meeting_name='Public example', session_path=?", (str(public_session),))
    monkeypatch.setattr(bi_services, 'LOCAL_INDEX_DB', public_db)
    response = client.get('/ratsbereich/sitzungen/8179/dokumente/1/pdf/')
    assert response.status_code == 200
    assert response['Content-Type'] == 'application/pdf'
    assert response['Content-Disposition'].startswith('inline;')
    assert 'no-store' in response['Cache-Control']
    assert b'synthetic-ri-private' in b''.join(response.streaming_content)
    response.close()
    for path in ['/ratsbereich/sitzungen/other/dokumente/1/pdf/',
                 '/ratsbereich/sitzungen/8179/dokumente/2/pdf/']:
        assert client.get(path).status_code == 404
    public_response = client.get('/analyse/sitzungen/8179/dokumente/1/pdf/')
    assert public_response.status_code == 200
    public_bytes = b''.join(public_response.streaming_content)
    public_response.close()
    assert b'synthetic-public' in public_bytes and b'synthetic-ri-private' not in public_bytes
    public_list = client.get('/analyse/sitzungen/').content.decode()
    assert 'Public example' in public_list and 'Interne Beispielsitzung' not in public_list


@pytest.mark.parametrize('kind', ['absolute', 'traversal', 'symlink', 'other_session', 'empty', 'non_pdf', 'session_outside'])
def test_ri_pdf_rejects_paths_outside_its_session_and_invalid_files(client, ri_catalogue, tmp_path, kind):
    import sqlite3

    db_path, session = ri_catalogue
    outside = tmp_path / 'outside.pdf'
    outside.write_bytes(b'%PDF-outside')
    if kind == 'absolute':
        path = str(outside)
    elif kind == 'traversal':
        path = '../../../../outside.pdf'
    elif kind == 'symlink':
        link = session / 'link.pdf'
        try:
            link.symlink_to(outside)
        except OSError:
            pytest.skip('Symbolic links are unavailable on this platform')
        path = 'link.pdf'
    elif kind == 'other_session':
        other = session.parent / 'another-session'
        other.mkdir()
        (other / 'other.pdf').write_bytes(b'%PDF-other')
        path = '../another-session/other.pdf'
    elif kind == 'empty':
        (session / 'empty.pdf').touch()
        path = 'empty.pdf'
    elif kind == 'non_pdf':
        (session / 'page.html').write_text('<script>test</script>')
        path = 'page.html'
    else:
        path = str(outside)
    with sqlite3.connect(db_path) as db:
        db.execute('UPDATE documents SET local_path=? WHERE id=1', (path,))
        if kind == 'session_outside':
            db.execute('UPDATE sessions SET session_path=?', (str(tmp_path),))
    assert client.get('/ratsbereich/sitzungen/8179/dokumente/1/pdf/').status_code == 404
    assert '/dokumente/1/pdf/' not in client.get('/ratsbereich/sitzungen/8179/').content.decode()


def test_ri_catalogue_missing_and_corrupt_never_falls_back_to_bi(client, ri_catalogue, monkeypatch, tmp_path):
    from core.services import ri_sessions

    path = tmp_path / 'missing.sqlite'
    monkeypatch.setattr(ri_sessions, 'RI_LOCAL_INDEX_DB', path)
    response = client.get('/ratsbereich/sitzungen/')
    assert response.status_code == 200
    assert 'Keine RI-Sitzungen gefunden' in response.content.decode()
    assert not path.exists()
    assert client.get('/ratsbereich/sitzungen/8179/').status_code == 404
    path.write_bytes(b'invalid-sqlite')
    assert 'RI-Index nicht lesbar' in client.get('/ratsbereich/sitzungen/').content.decode()
    assert client.get('/ratsbereich/sitzungen/8179/').status_code == 503
    assert client.get('/ratsbereich/sitzungen/8179/dokumente/1/pdf/').status_code == 503


def test_ri_catalogue_pages_are_read_only(client, ri_catalogue):
    for path in ('/ratsbereich/sitzungen/', '/ratsbereich/sitzungen/8179/',
                 '/ratsbereich/sitzungen/8179/dokumente/1/pdf/'):
        assert client.post(path, {'action': 'fetch_sessions'}).status_code == 405


@pytest.mark.parametrize('page', ['fetch', 'build'])
def test_shared_script_forms_keep_action_scope_and_accessible_unique_ids(client, monkeypatch, page):
    from bs4 import BeautifulSoup
    from data_tools import views

    monkeypatch.setattr(views.services, 'service_status', lambda: {})
    for area in ('buergerinformation', 'ratsbereich', 'landkreis'):
        soup = BeautifulSoup(client.get(f'/{area}/daten/{page}/').content, 'html.parser')
        forms = soup.select('form.form-stack')
        assert forms
        ids = [element['id'] for element in soup.select('[id]')]
        assert len(ids) == len(set(ids))
        for form in forms:
            assert form.select_one('input[name="csrfmiddlewaretoken"]')
            assert form.has_attr('data-ri-script-form') == (area == 'ratsbereich')
            action = form.select_one('input[name="action"]')['value']
            assert action.startswith('ri_') == (area == 'ratsbereich')
            for label in form.select('label[for]'):
                assert soup.find(id=label['for']) is not None


@pytest.mark.parametrize('download_code,index_code,expected',[(0,0,'ok'),(2,0,'partial'),(1,None,'error'),(0,1,'error'),(2,1,'error')])
def test_ri_download_index_pipeline_preserves_results_and_slot(ri_env,monkeypatch,download_code,index_code,expected):
    calls=[]
    class Thread:
        def __init__(self,**kwargs):pass
        def start(self):pass
    monkeypatch.setattr(ri_env.threading,'Thread',Thread)
    payload={'action':'ri_fetch','year':'2026','months':'12','update_local_index':'on'}
    job_id=ri_env.start_job('ri_fetch',payload)
    codes=[download_code]+([] if index_code is None else [index_code])
    class Process:
        pid=os.getpid()
        def __init__(self,code):self.code=code;self.stdout=io.StringIO('test output\n')
        def wait(self):return self.code
        def poll(self):return self.code
    def process(command,**kwargs):
        calls.append(command)
        if len(calls)==2:
            assert ri_env.get_job(job_id)['phase']=='index'
            with pytest.raises(ri_env.RiJobBusyError):ri_env.start_job('ri_local',{'action':'ri_local'})
        return Process(codes[len(calls)-1])
    monkeypatch.setattr(ri_env.subprocess,'Popen',process)
    ri_env._run_job(job_id,[sys.executable,'scripts/fetch_ri_sessions.py','2026','--months','12'],True)
    job=ri_env.get_job(job_id)
    assert job['status']==expected
    assert job['download_exit_code']==download_code
    assert job['index_exit_code']==index_code
    assert len(calls)==(1 if download_code==1 else 2)
    if len(calls)==2:assert calls[1]==[sys.executable,'scripts/build_ri_local_index.py']
    if download_code==1:
        assert job['phase']=='download'
        assert job['index_result_label']=='Nicht ausgeführt'


def test_ri_index_option_defaults_on_and_can_be_unchecked(client,ri_env,monkeypatch):
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(client.get('/ratsbereich/daten/fetch/').content,'html.parser')
    assert soup.select_one('input[name=update_local_index]').has_attr('checked')
    calls=[]
    class Thread:
        def __init__(self,**kwargs):calls.append(kwargs)
        def start(self):pass
    monkeypatch.setattr(ri_env.threading,'Thread',Thread)
    client.post('/ratsbereich/daten/fetch/',{'action':'ri_fetch','year':'2026','months':'12'})
    assert calls[0]['args'][2] is False


def test_ri_pipeline_real_local_builder_closes_download_index_gap(ri_env,monkeypatch,tmp_path):
    import json
    import sqlite3
    from scripts import build_ri_local_index as builder
    root=tmp_path/'pipeline-ri';raw=root/'raw';folder=raw/'2026/11/2026-11-25-Testgremium-8176'
    folder.mkdir(parents=True);output=root/'db/local_index.sqlite'
    monkeypatch.setattr(builder,'RI_ROOT',root)
    def seed(count):
        documents=[]
        for index in range(count):
            (folder/f'{index}.pdf').write_bytes(b'%PDF-synthetic')
            documents.append({'url':f'https://session.melle.info/ri/getfile.asp?id={index+1}&type=do','path':f'{index}.pdf','title':'Test','document_id':str(index+1)})
        (folder/'manifest.json').write_text(json.dumps({'session':{'id':'8176','committee':'Testgremium'},'documents':documents}))
        (folder/'agenda_summary.json').write_text(json.dumps({'agenda_items':[{'number':'Ö 1','title':'Test'}]}))
    seed(11);builder.build_index(raw,output,False,False)
    class Thread:
        def __init__(self,**kwargs):pass
        def start(self):pass
    monkeypatch.setattr(ri_env.threading,'Thread',Thread)
    job_id=ri_env.start_job('ri_fetch',{'action':'ri_fetch','year':'2026','months':'11','update_local_index':'on'})
    class Process:
        pid=os.getpid()
        def __init__(self,command):
            if command[1]=='scripts/fetch_ri_sessions.py':seed(14)
            else:builder.build_index(raw,output,False,False)
            self.stdout=io.StringIO('Synthetic phase complete\n')
        def wait(self):return 0
        def poll(self):return 0
    monkeypatch.setattr(ri_env.subprocess,'Popen',lambda command,**kw:Process(command))
    ri_env._run_job(job_id,[sys.executable,'scripts/fetch_ri_sessions.py','2026','--months','11'],True)
    assert ri_env.get_job(job_id)['status']=='ok'
    with sqlite3.connect(output) as db:
        assert db.execute("SELECT COUNT(*) FROM documents WHERE session_id='8176'").fetchone()[0]==14


def test_old_ri_job_database_upgrades_without_losing_history(ri_env,monkeypatch):
    import sqlite3
    ri_env.JOBS_DB.parent.mkdir(parents=True)
    with sqlite3.connect(ri_env.JOBS_DB) as db:
        db.execute('CREATE TABLE ri_jobs (job_id TEXT PRIMARY KEY, action TEXT NOT NULL,status TEXT NOT NULL,exit_code INTEGER,output TEXT NOT NULL DEFAULT \'\',created_at TEXT NOT NULL,started_at TEXT NOT NULL DEFAULT \'\',finished_at TEXT NOT NULL DEFAULT \'\',owner_pid INTEGER NOT NULL,child_pid INTEGER NOT NULL DEFAULT 0)')
        db.execute("INSERT INTO ri_jobs (job_id,action,status,created_at,owner_pid) VALUES ('old','ri_local','ok','2026-11-01',?)",(os.getpid(),))
    class Thread:
        def __init__(self,**kwargs):pass
        def start(self):pass
    monkeypatch.setattr(ri_env.threading,'Thread',Thread)
    ri_env.start_job('ri_local',{'action':'ri_local'})
    assert ri_env.get_job('old')['status']=='ok'
    assert not ri_env.get_job('old')['index_requested']


def test_changed_ri_session_renders_calendar_notice(client,ri_catalogue):
    import sqlite3
    from src.indexing.calendar_metadata import ensure_calendar_columns
    db,_=ri_catalogue
    with sqlite3.connect(db) as connection:
        ensure_calendar_columns(connection)
        connection.execute("UPDATE sessions SET calendar_status='postponed',calendar_note='verschoben auf den 12.01.2027',rescheduled_date='2027-01-12'")
    response=client.get('/ratsbereich/sitzungen/8179/')
    assert response.status_code==200
    assert 'Verschoben' in response.content.decode()
    assert 'Ersatzdatum: 12.01.2027' in response.content.decode()
