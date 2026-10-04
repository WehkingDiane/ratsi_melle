"""Result provenance, completion ordering and durable job evidence."""
import json
import os
from pathlib import Path
import sqlite3
import sys

import django
from django.test import Client
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'web'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web.settings')
from core import service_jobs
from core.services import model_job_history as history
from core.services import paths
from data_tools import services


def job(job_id='done', **kwargs):
    values = dict(status='ok', models_dir='/models', model_binding='binding',
                  model_manifest_sha256='a' * 64, completed_at='2026-10-02T10:00:00+00:00',
                  output=json.dumps({'status': 'bereit'}))
    values.update(kwargs)
    return service_jobs.ServiceJob(job_id, 'check_embedding_models', [], **values)


@pytest.fixture
def models():
    return {'status': 'bereit', 'models_dir': '/models', 'manifest_sha256': 'a' * 64}


@pytest.mark.parametrize('changed', ['path', 'binding', 'manifest', 'readiness'])
def test_changed_inventory_is_historical(models, changed):
    binding = 'binding'
    if changed == 'path':
        models['models_dir'] = '/different'
    elif changed == 'binding':
        binding = 'new-library-version'
    elif changed == 'manifest':
        models['manifest_sha256'] = 'b' * 64
    else:
        models['status'] = 'fehlt'
    assert history.job_evidence(job(), models, binding)['association'] == 'historical'


def test_verified_result_matches_current_snapshot(models):
    assert history.job_evidence(job(), models, 'binding')['association'] == 'current'


@pytest.mark.parametrize('missing', ['model_binding', 'models_dir', 'model_manifest_sha256'])
def test_unproven_success_never_claims_current(models, missing):
    assert history.job_evidence(job(**{missing: ''}), models, 'binding')['association'] == 'unknown'


def test_latest_failure_and_active_job_are_separate(monkeypatch, models):
    older = job('older', completed_at='2026-10-02T09:00:00+00:00')
    failed = job('failed', status='error', model_manifest_sha256='',
                 output=json.dumps({'status': 'inkompatibel', 'message': 'secret'}))
    running = job('active', status='running', completed_at='', model_manifest_sha256='')
    monkeypatch.setattr(service_jobs, 'list_service_jobs', lambda **kw: [running, older, failed])
    monkeypatch.setattr(history, 'current_binding', lambda: 'binding')
    result = history.model_job_history(models)['entries'][0]
    assert result['last_finished']['job_id'] == 'failed'
    assert result['last_finished']['result'] == 'inkompatibel'
    assert [value['job_id'] for value in result['active']] == ['active']
    assert 'secret' not in json.dumps(result)
    monkeypatch.setattr(service_jobs, 'list_service_jobs', lambda **kw: [])
    assert history.model_job_history(models)['entries'][0]['last_finished'] is None


def test_completion_time_decides_order(monkeypatch, models):
    slow = job('slow', created_at='2026-10-01T00:00:00+00:00')
    fast = job('fast', created_at='2026-10-02T09:00:00+00:00', completed_at='2026-10-02T09:30:00+00:00')
    monkeypatch.setattr(service_jobs, 'list_service_jobs', lambda **kw: [fast, slow])
    monkeypatch.setattr(history, 'current_binding', lambda: 'binding')
    assert history.model_job_history(models)['entries'][0]['last_finished']['job_id'] == 'slow'


def test_storage_failure_preserves_refreshable_scopes(monkeypatch, models):
    def unavailable(**kwargs):
        raise sqlite3.OperationalError('private path')
    monkeypatch.setattr(service_jobs, 'list_service_jobs', unavailable)
    result = history.model_job_history(models)
    assert not result['available']
    assert len(result['entries']) == len(history.SCOPES)
    assert 'private path' not in json.dumps(result)


@pytest.mark.parametrize('status', ['queued', 'running', 'ok', 'error'])
def test_progress_reports_lifecycle_without_percentage(status):
    progress = job(status=status).progress
    assert progress['phase'] == status
    assert progress['indeterminate'] == (status in {'queued', 'running'})
    assert 'percent' not in progress


def test_failed_job_does_not_publish_positive_result(models):
    assert history.job_evidence(job(status='error'), models, 'binding')['result'] == 'fehlgeschlagen'


@pytest.mark.parametrize('payload', [[], {}, {'status': 'bereit'}, {'status': 'fehlt', 'check_level': []},
                                    {'status': 'secret', 'check_level': 'fast'}])
def test_check_output_rejects_untrusted_or_incomplete_json(payload):
    assert service_jobs._safe_model_check_output(json.dumps(payload)) is None


def test_check_output_discards_provider_message():
    value = json.loads(service_jobs._safe_model_check_output(json.dumps(
        {'status': 'bereit', 'check_level': 'fast', 'manifest_sha256': 'a' * 64, 'message': 'secret'})))
    assert value['manifest_sha256'] == 'a' * 64
    assert 'secret' not in json.dumps(value)


@pytest.mark.integration
def test_model_job_evidence_survives_database_reload(tmp_path, monkeypatch):
    django.setup()
    monkeypatch.setattr(paths, 'PRIVATE_DATA_DIR', tmp_path / 'private')
    monkeypatch.setenv('RATSI_MODELS_DIR', str(tmp_path / 'models'))
    monkeypatch.setattr(service_jobs.threading.Thread, 'start', lambda self: None)
    record = service_jobs.start_service_job('check_embedding_models', [], ROOT)
    assert record.model_binding and record.models_dir == str(tmp_path / 'models')
    service_jobs._update_job(record.job_id, status='ok', model_manifest_sha256='a' * 64)
    completed = record.completed_at
    assert completed
    service_jobs._update_job(record.job_id, summary='Updated annotation')
    assert record.completed_at == completed
    monkeypatch.setattr(service_jobs, '_loaded_db_path', None)
    restored = service_jobs.get_service_job(record.job_id)
    assert (restored.model_binding, restored.model_manifest_sha256, restored.completed_at) == (
        record.model_binding, 'a' * 64, completed)
    assert not (tmp_path / 'models').exists()


@pytest.mark.integration
def test_history_endpoint_is_local_and_read_only(monkeypatch, models):
    django.setup()
    monkeypatch.setattr(services, 'embedding_model_status', lambda: models)
    monkeypatch.setattr(service_jobs, 'list_service_jobs', lambda **kw: [])
    monkeypatch.setattr(history, 'current_binding', lambda: 'binding')
    monkeypatch.setattr(services, 'service_status', lambda: pytest.fail('No Qdrant probe allowed'))
    response = Client().get('/daten/model-jobs/status/')
    assert response.status_code == 200
    assert response.json()['history']['available']
    assert len(response.json()['history']['entries']) == 6


@pytest.mark.integration
def test_cli_rejects_changed_check_binding_without_reading_inventory(tmp_path, monkeypatch, capsys):
    from scripts import prepare_embedding_models as cli
    monkeypatch.setenv('RATSI_MODELS_DIR', str(tmp_path / 'missing'))
    monkeypatch.setenv('RATSI_MODEL_CHECK_BINDING', 'outdated')
    monkeypatch.setattr(cli, 'check_embedding_model_status', lambda *a, **kw: pytest.fail('Wrong contract'))
    assert cli.main(['--check', '--json']) == 1
    assert json.loads(capsys.readouterr().out)['status'] == 'inkompatibel'
    assert not (tmp_path / 'missing').exists()

@pytest.mark.integration
@pytest.mark.parametrize('returncode,state,expected', [(0, 'bereit', 'ok'), (1, 'bereit', 'error'), (0, 'fehlt', 'error')])
def test_check_worker_freezes_binding_and_records_only_successful_manifest(tmp_path, monkeypatch, returncode, state, expected):
    from types import SimpleNamespace
    django.setup()
    monkeypatch.setattr(paths, 'PRIVATE_DATA_DIR', tmp_path / 'private')
    monkeypatch.setenv('RATSI_MODELS_DIR', str(tmp_path / 'models'))
    monkeypatch.setattr(service_jobs.threading.Thread, 'start', lambda self: None)
    record = service_jobs.start_service_job('check_embedding_models', [], ROOT)
    output = json.dumps({'status': state, 'check_level': 'fast', 'manifest_sha256': 'a' * 64, 'message': 'secret'})
    def launch(*args, **kwargs):
        assert kwargs['env']['RATSI_MODEL_CHECK_BINDING'] == record.model_binding
        assert kwargs['env']['RATSI_MODELS_DIR'] == record.models_dir
        assert kwargs['stderr'] == service_jobs.subprocess.DEVNULL
        return SimpleNamespace(stdout=[output], returncode=returncode, wait=lambda: None)
    monkeypatch.setattr(service_jobs.subprocess, 'Popen', launch)
    service_jobs._execute_job(record.job_id, ROOT)
    assert record.status == expected and record.completed_at
    assert record.model_manifest_sha256 == ('a' * 64 if expected == 'ok' else '')
    assert 'secret' not in record.output
    if returncode:
        assert 'erfolgreicher Abschluss nicht bestätigt' in record.output
