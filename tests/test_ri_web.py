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
    assert css in soup.select_one('#ri-job-status')['class']
    assert soup.select_one('#ri-job-exit').text == ('–' if code is None else str(code))
    assert soup.select_one('#ri-job-running').has_attr('hidden') == (state != 'queued')


def test_ri_job_polling_updates_completion_and_preserves_status_on_network_error():
    import shutil
    import subprocess

    node = shutil.which('node')
    if node is None:
        pytest.skip('Node.js is required for JavaScript execution')
    script = ROOT / 'web/core/static/core/js/ri_job.js'
    harness = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ids = ['ri-job', 'ri-job-status', 'ri-job-exit', 'ri-job-output', 'ri-job-start',
             'ri-job-end', 'ri-job-running', 'ri-job-feedback'];
const elements = Object.fromEntries(ids.map(id => [id, {textContent: '', hidden: false}]));
elements['ri-job'].dataset = {statusUrl: '/ri/job/status/'};
let job = {status: 'running', status_label: 'läuft', running: true};
let poll;
let fail = false;
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), {
  document: {getElementById: id => elements[id]},
  window: {setTimeout: callback => { poll = callback; }},
  fetch: async () => {
    if (fail) throw Error('offline');
    return {ok: true, json: async () => ({job})};
  },
});
const settle = () => new Promise(resolve => setImmediate(resolve));
(async () => {
  await settle();
  assert.equal(elements['ri-job-status'].className, 'status-warning');
  assert.equal(elements['ri-job-running'].hidden, false);
  job = {status: 'partial', status_label: 'mit Hinweisen abgeschlossen', running: false,
         exit_code: 2, finished_at: '2026-11-22', output: '<script>text</script>'};
  await poll();
  assert.equal(elements['ri-job-status'].className, 'status-warning');
  assert.equal(elements['ri-job-running'].hidden, true);
  assert.equal(elements['ri-job-exit'].textContent, 2);
  assert.equal(elements['ri-job-output'].textContent, job.output);
  assert.equal(elements['ri-job-end'].textContent, job.finished_at);
  job = {...job, status: 'ok', status_label: 'erfolgreich', exit_code: 0};
  await poll();
  assert.equal(elements['ri-job-status'].className, 'status-ok');
  assert.equal(elements['ri-job-exit'].textContent, 0);
  job = {...job, status: 'error', status_label: 'fehlgeschlagen', exit_code: 1};
  await poll();
  assert.equal(elements['ri-job-status'].className, 'status-error');
  fail = true;
  await poll();
  assert.equal(elements['ri-job-status'].textContent, 'fehlgeschlagen');
  assert.equal(elements['ri-job-feedback'].hidden, false);
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
    result = subprocess.run([node, '-e', harness, str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
