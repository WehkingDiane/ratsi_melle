"""RI UI isolation and script controls with temporary databases and fake workers."""
import io
import os
from pathlib import Path
import sys
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'web'))
django = pytest.importorskip('django')
pytestmark = pytest.mark.integration


@pytest.fixture(scope='module')
def web_auth(tmp_path_factory):
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web.settings')
    django.setup()
    from django.core.management import call_command
    from django.db import connections
    old = connections['default']
    database = old.__class__({**old.settings_dict, 'NAME': tmp_path_factory.mktemp('ri_auth') / 'auth.sqlite3'}, 'default')
    connections['default'] = database
    try:
        call_command('migrate', verbosity=0, interactive=False)
        yield
    finally:
        database.close()
        connections['default'] = old


@pytest.fixture
def ri_env(web_auth, tmp_path, monkeypatch):
    from core import ri_jobs, ri_views, service_jobs
    monkeypatch.setattr(ri_jobs, 'JOBS_DB', tmp_path / 'ri/ri_jobs.sqlite')
    monkeypatch.setattr(ri_views, 'RI_LOCAL_INDEX_DB', tmp_path / 'ri/local.sqlite')
    monkeypatch.setattr(ri_views, 'RI_ONLINE_INDEX_DB', tmp_path / 'ri/online.sqlite')
    monkeypatch.setattr(service_jobs, 'SERVICE_JOBS_DB', tmp_path / 'public_jobs.sqlite')
    monkeypatch.setattr('src.config.ri.RI_ROOT', tmp_path / 'ri')
    return ri_jobs


@pytest.fixture
def staff(ri_env):
    from django.contrib.auth import get_user_model
    return get_user_model().objects.create_user('ri-' + uuid4().hex, password='synthetic-password', is_staff=True)


@pytest.fixture
def client(ri_env):
    from django.test import Client
    return Client()


@pytest.mark.parametrize('path', ['', 'zugang/', 'daten/', 'daten/fetch/', 'daten/build/',
                                  'daten/jobs/unknown/', 'daten/jobs/unknown/status/'])
def test_anonymous_ri_requests_cannot_read_or_start_jobs(client, ri_env, monkeypatch, path):
    monkeypatch.setattr(ri_env, 'start_job', lambda *args: pytest.fail('Unexpected worker'))
    response = client.get('/ratsbereich/' + path)
    assert response.status_code == 302
    assert response['Location'].startswith('/ratsbereich/anmelden/')
    assert 'no-store' in response['Cache-Control']
    assert client.post('/ratsbereich/' + path, {'action': 'ri_login'}).status_code == 302
    assert not ri_env.JOBS_DB.exists()


def test_nonstaff_cannot_access_ri(client, ri_env):
    from django.contrib.auth import get_user_model
    user = get_user_model().objects.create_user('normal-' + uuid4().hex, password='synthetic-password')
    client.force_login(user)
    assert client.get('/ratsbereich/daten/').status_code == 403
    client.logout()
    response = client.post('/ratsbereich/anmelden/', {'username': user.username, 'password': 'synthetic-password'})
    assert response.status_code == 200
    assert 'keinen Zugang' in response.content.decode()
    assert '_auth_user_id' not in client.session


def test_real_web_login_and_post_logout(client, staff):
    response = client.post('/ratsbereich/anmelden/', {'username': staff.username, 'password': 'synthetic-password'})
    assert response.status_code == 302
    assert client.get('/ratsbereich/daten/').status_code == 200
    assert client.get('/ratsbereich/abmelden/').status_code == 405
    assert client.post('/ratsbereich/abmelden/').status_code == 302
    assert client.get('/ratsbereich/daten/').status_code == 302


@pytest.mark.parametrize('path,expected', [('zugang/', ['ri_login']), ('daten/fetch/', ['ri_fetch']),
                                          ('daten/build/', ['ri_online', 'ri_local'])])
def test_staff_forms_do_not_execute_on_get(client, staff, ri_env, monkeypatch, path, expected):
    from bs4 import BeautifulSoup
    client.force_login(staff)
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
def test_valid_ri_forms_start_only_fixed_commands(client, staff, ri_env, monkeypatch, action, path, extra, expected):
    calls = []
    class Thread:
        def __init__(self, **kwargs): calls.append(kwargs)
        def start(self): pass
    monkeypatch.setattr(ri_env.threading, 'Thread', Thread)
    client.force_login(staff)
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
def test_wrong_actions_and_parameters_do_not_start_jobs(client, staff, ri_env, monkeypatch, payload):
    client.force_login(staff)
    monkeypatch.setattr(ri_env, 'start_job', lambda *args: pytest.fail('Invalid action started'))
    assert client.post('/ratsbereich/daten/fetch/', payload).status_code in {200, 400}
    assert not ri_env.JOBS_DB.exists()


def test_csrf_is_required_for_ri_actions(staff, ri_env, monkeypatch):
    from django.test import Client
    client = Client(enforce_csrf_checks=True)
    client.force_login(staff)
    monkeypatch.setattr(ri_env, 'start_job', lambda *args: pytest.fail('CSRF bypass'))
    assert client.post('/ratsbereich/zugang/', {'action': 'ri_login'}).status_code == 403


def test_parallel_ri_jobs_are_rejected_and_never_public(client, staff, ri_env, monkeypatch):
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
    client.force_login(staff)
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
