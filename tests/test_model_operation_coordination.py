"""M6.9: lifecycle locks, Windows waiting and real cross-process CLI entrypoints."""
from contextlib import contextmanager
import errno
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from embedding_preparation_support import kill_test_process

from src import model_operations as operations
from src.analysis.vector_store import DocumentVectorStore
from src.indexing.legacy_index_migration import _migration_lock
from src.qdrant_connection import QdrantConnection

from test_build_compatibility import compatibility

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('blocking,failures', [(True, 15), (False, 1)])
def test_windows_waits_beyond_native_retry_limit(monkeypatch, blocking, failures):
    calls, pauses = [], []
    def locking(fd, mode, size):
        calls.append(mode)
        if mode == 1 and calls.count(1) <= failures:
            raise OSError(errno.EACCES, 'held by another process')
    monkeypatch.setitem(sys.modules, 'msvcrt', SimpleNamespace(LK_NBLCK=1, LK_UNLCK=2, locking=locking))
    monkeypatch.setattr(operations, 'os', SimpleNamespace(name='nt'))
    monkeypatch.setattr(operations.time, 'sleep', pauses.append)
    stream = io.BytesIO()
    stream.fileno = lambda: 42
    if blocking:
        with operations.process_file_lock(stream):
            assert len(pauses) == failures
        assert calls[-1] == 2
        assert stream.getvalue() == b'\0'
    else:
        with pytest.raises(operations.ModelOperationBusyError):
            with operations.process_file_lock(stream, blocking=False):
                pytest.fail('Acquired busy lock')
        assert calls == [1] and not pauses


def test_windows_lock_io_error_is_not_retried_or_misreported(monkeypatch):
    def invalid(*args):
        raise OSError(errno.EBADF, 'invalid descriptor')
    monkeypatch.setitem(sys.modules, 'msvcrt', SimpleNamespace(LK_NBLCK=1, LK_UNLCK=2, locking=invalid))
    monkeypatch.setattr(operations, 'os', SimpleNamespace(name='nt'))
    monkeypatch.setattr(operations.time, 'sleep', lambda _: pytest.fail('Unexpected retry'))
    stream = io.BytesIO(b'\0')
    stream.fileno = lambda: 42
    with pytest.raises(OSError) as error:
        with operations.process_file_lock(stream):
            pytest.fail('Acquired invalid lock')
    assert error.value.errno == errno.EBADF


@pytest.mark.parametrize('phase', ['success', 'begin-error', 'publish-error', 'close-error'])
def test_build_locks_outlive_client_through_success_and_failure(tmp_path, monkeypatch, phase, compatibility):
    contract = compatibility
    events = []
    @contextmanager
    def model(*args, **kwargs):
        events.append('model acquired')
        try:
            yield
        finally:
            events.append('model released')
    @contextmanager
    def collection(*args, **kwargs):
        events.append('collection acquired')
        try:
            yield
        finally:
            events.append('collection released')
    def close():
        events.append('client closed')
        if phase == 'close-error':
            raise OSError('close failed')
    def check(*args, **kwargs):
        if phase == 'begin-error':
            raise ValueError('incompatible')
        return 'native'
    def publish(self, client, state, **kwargs):
        if state['ready'] and phase == 'publish-error':
            raise OSError('marker write failed')
    monkeypatch.setattr(operations, 'model_operation_lock', model)
    monkeypatch.setattr('src.indexing.legacy_index_migration._migration_lock', collection)
    monkeypatch.setattr('src.indexing.build_compatibility.check_build_compatibility', check)
    monkeypatch.setattr(QdrantConnection, 'write_readiness', publish)
    store = DocumentVectorStore(tmp_path / 'qdrant')
    store._client = SimpleNamespace(close=close)
    monkeypatch.setattr(store, 'ensure_collection', lambda: None)
    try:
        if phase == 'begin-error':
            with pytest.raises(ValueError):
                store.begin_build(contract)
        else:
            store.begin_build(contract)
            if phase == 'publish-error':
                with pytest.raises(OSError):
                    store.finish_build(contract)
            else:
                store.finish_build(contract)
        assert events == ['model acquired', 'collection acquired']
    finally:
        if phase == 'close-error':
            with pytest.raises(OSError):
                store.close()
        else:
            store.close()
    assert events[-3:] == ['client closed', 'collection released', 'model released']
    store.close()  # Repeated cleanup must not unlock another operation.
    assert len(events) == 5


def _wait_for_file(path, process, timeout=60):
    # Cold imports from a Windows-mounted WSL environment can exceed ten seconds.
    deadline = time.monotonic() + timeout
    while not path.exists() and process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.02)
    assert path.exists(), process.communicate(timeout=5) if process.poll() is not None else 'Child did not reach barrier'


CLI_BOOTSTRAP = r'''
import json, os, sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
root, action = Path(sys.argv[1]), sys.argv[2]
sys.path.insert(0, str(Path.cwd() / 'web'))
from src import model_operations as ops
from src.analysis.vector_store import DocumentVectorStore
from src.qdrant_connection import QdrantConnection
from src.indexing import legacy_index_migration as migration
class Stop(Exception): pass
events = []
original_model, original_collection = ops.model_operation_lock, migration._migration_lock
@contextmanager
def model(*args, **kwargs):
    try:
        with original_model(*args, **kwargs):
            events.append('model')
            yield
    finally:
        events.append('model released')
@contextmanager
def collection(*args, **kwargs):
    with original_collection(*args, **kwargs):
        events.append('collection')
        yield
    events.append('collection released')
ops.model_operation_lock, migration._migration_lock = model, collection
def stop(*args, **kwargs):
    (root / 'entered').touch()
    raise Stop()
def client(self):
    events.append('client')
    return SimpleNamespace(close=lambda: events.append('client closed'))
QdrantConnection.create_client = client
if action == 'prepare':
    from scripts import prepare_embedding_models as cli
    cli.prepare_embedding_models = stop
    if os.environ.get('TEST_CHANGE_BINDING'):
        cli.model_preparation_binding = lambda path: 'changed' if (root / 'changed').exists() else 'original'
    arguments = ['--download', '--json']
elif action in {'inspect', 'apply'}:
    from scripts import migrate_legacy_index as cli
    cli._migration_lock = collection
    cli._local_store_exists = lambda path: True
    cli.inspect_and_write_report = cli.apply_verified_legacy_report = stop
    arguments = ['--' + action, '--collection', 'ratsi_passages', '--report', str(root / 'report.json'),
                 '--qdrant-dir', str(root / 'qdrant')]
    if action == 'apply': arguments += ['--confirm-collection', 'ratsi_passages']
else:
    if action == 'landkreis':
        from scripts import build_landkreis_vector_index as cli
    else:
        from scripts import build_vector_index as cli
    cli._validate_runtime_dependencies = lambda: (object, DocumentVectorStore)
    cli.current_index_compatibility = stop
    from src.indexing import passage_builder
    passage_builder.current_index_compatibility = stop
    arguments = ['--db', str(root / 'source.sqlite'), '--qdrant-dir', str(root / 'qdrant')]
    if action == 'legacy': arguments += ['--legacy-document-index']
(root / 'ready').touch()
try:
    cli.main(arguments)
except Stop:
    pass
print(json.dumps(events), flush=True)
'''


@pytest.mark.integration
@pytest.mark.parametrize('action', ['prepare', 'passages', 'legacy', 'landkreis', 'inspect', 'apply'])
def test_real_cli_waits_for_other_process_before_models_and_client(tmp_path, action):
    (tmp_path / 'source.sqlite').touch()
    env = {**os.environ, 'RATSI_MODELS_DIR': str(tmp_path / 'models'),
           'RATSI_LOG_DIR': str(tmp_path / 'logs')}
    with operations.model_operation_lock(tmp_path / 'models'):
        process = subprocess.Popen([sys.executable, '-c', CLI_BOOTSTRAP, str(tmp_path), action],
                                   cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            _wait_for_file(tmp_path / 'ready', process)
            time.sleep(0.15)
            assert not (tmp_path / 'entered').exists()
            assert process.poll() is None
        except BaseException:
            kill_test_process(process)
            process.communicate(timeout=10)
            raise
    try:
        stdout, stderr = process.communicate(timeout=15)
        assert process.returncode == 0, stderr
        assert (tmp_path / 'entered').exists()
        events = json.loads(stdout.splitlines()[-1])
        assert events[0] == 'model'
        if action != 'prepare':
            assert events[:3] == ['model', 'collection', 'client']
            assert events.index('client closed') < events.index('collection released') < events.index('model released')
    finally:
        if process.poll() is None:
            kill_test_process(process)
            process.communicate(timeout=10)


@pytest.mark.integration
def test_collection_lock_rejects_symlink(tmp_path):
    connection = QdrantConnection(tmp_path / 'qdrant')
    path = connection.release_path('ratsi_passages').with_suffix('.migration.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    target = tmp_path / 'unrelated'
    target.write_bytes(b'unchanged')
    try:
        path.symlink_to(target)
    except OSError as error:
        if os.name == 'nt' and error.winerror == 1314:
            pytest.skip('Windows symlink privilege is unavailable')
        raise
    with pytest.raises(OSError, match='Symlink'):
        with _migration_lock(connection, 'ratsi_passages'):
            pytest.fail('Acquired redirected lock')
    assert target.read_bytes() == b'unchanged'

HOLDER = r'''
from pathlib import Path
import sys
from src.model_operations import model_operation_lock
with model_operation_lock(Path(sys.argv[1])):
    Path(sys.argv[2]).touch()
    sys.stdin.read()
'''


@pytest.mark.integration
@pytest.mark.parametrize('action', ['prepare_embedding_models', 'build_vector_index', 'build_landkreis_vector_index',
                                    'inspect_legacy_index', 'apply_legacy_index'])
def test_live_cli_rejects_every_colliding_web_start_without_new_row(tmp_path, monkeypatch, action):
    sys.path.insert(0, str(ROOT / 'web'))
    from core import service_jobs
    monkeypatch.setattr(service_jobs, 'SERVICE_JOBS_DB', tmp_path / 'jobs.sqlite')
    holder = subprocess.Popen([sys.executable, '-c', HOLDER, os.environ['RATSI_MODELS_DIR'], str(tmp_path / 'held')],
                              cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        _wait_for_file(tmp_path / 'held', holder)
        with monkeypatch.context() as worker_patch:
            worker_patch.setattr(service_jobs.threading.Thread, 'start',
                                 lambda self: pytest.fail('Second worker started'))
            with pytest.raises(service_jobs.ServiceJobStartError, match='bereits aktiv'):
                service_jobs.start_service_job(action, [], ROOT)
        assert not service_jobs.list_service_jobs()
    finally:
        kill_test_process(holder)
        holder.communicate(timeout=10)


@pytest.mark.integration
def test_real_surviving_child_blocks_restart_even_when_old_job_status_is_wrong(tmp_path, monkeypatch):
    sys.path.insert(0, str(ROOT / 'web'))
    import sqlite3
    from core import service_jobs
    monkeypatch.setattr(service_jobs, 'SERVICE_JOBS_DB', tmp_path / 'jobs.sqlite')
    holder = subprocess.Popen([sys.executable, '-c', HOLDER, os.environ['RATSI_MODELS_DIR'], str(tmp_path / 'held')],
                              cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        _wait_for_file(tmp_path / 'held', holder)
        service_jobs.list_service_jobs()
        record = service_jobs.ServiceJob('interrupted-parent', 'build_vector_index', [], status='running',
                                        owner_pid=0, child_pid=holder.pid)
        with sqlite3.connect(service_jobs.SERVICE_JOBS_DB) as conn:
            service_jobs._store_job(conn, record)
        assert service_jobs.get_service_job(record.job_id).status == 'running'
        # Even a wrong terminal record cannot override a live OS lock.
        service_jobs._update_job(record.job_id, status='error')
        with pytest.raises(service_jobs.ServiceJobStartError, match='bereits aktiv'):
            service_jobs.start_service_job('build_landkreis_vector_index', [], ROOT)
        with sqlite3.connect(service_jobs.SERVICE_JOBS_DB) as conn:
            service_jobs._store_job(conn, record)
        assert service_jobs.get_service_job(record.job_id).status == 'running'
    finally:
        kill_test_process(holder)
        holder.communicate(timeout=10)
    restored = service_jobs.get_service_job(record.job_id)
    assert restored.status == 'error' and restored.completed_at
    monkeypatch.setattr(service_jobs.threading.Thread, 'start', lambda self: None)
    assert service_jobs.start_service_job('build_landkreis_vector_index', [], ROOT).status == 'queued'
    # A retained lock file is harmless after the owning process has stopped.
    assert (Path(os.environ['RATSI_MODELS_DIR']) / '.operation.lock').exists()

@pytest.mark.integration
@pytest.mark.parametrize('action', ['inspect', 'apply'])
def test_legacy_cli_waits_for_collection_before_opening_client(tmp_path, action):
    connection = QdrantConnection(tmp_path / 'qdrant')
    env = {**os.environ, 'RATSI_MODELS_DIR': str(tmp_path / 'models')}
    with _migration_lock(connection, 'ratsi_passages'):
        process = subprocess.Popen([sys.executable, '-c', CLI_BOOTSTRAP, str(tmp_path), action],
                                   cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            _wait_for_file(tmp_path / 'ready', process)
            time.sleep(0.15)
            assert not (tmp_path / 'entered').exists() and process.poll() is None
        except BaseException:
            kill_test_process(process)
            process.communicate(timeout=10)
            raise
    try:
        stdout, stderr = process.communicate(timeout=15)
        assert process.returncode == 0, stderr
        assert json.loads(stdout.splitlines()[-1])[:3] == ['model', 'collection', 'client']
    finally:
        if process.poll() is None:
            kill_test_process(process)
            process.communicate(timeout=10)


@pytest.mark.integration
def test_waiting_preparation_rechecks_confirmation_after_lock_acquisition(tmp_path):
    env = {**os.environ, 'RATSI_MODELS_DIR': str(tmp_path / 'models'), 'RATSI_LOG_DIR': str(tmp_path / 'logs'),
           'RATSI_MODEL_PREPARATION_BINDING': 'original', 'TEST_CHANGE_BINDING': '1'}
    with operations.model_operation_lock(tmp_path / 'models'):
        process = subprocess.Popen([sys.executable, '-c', CLI_BOOTSTRAP, str(tmp_path), 'prepare'],
                                   cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            _wait_for_file(tmp_path / 'ready', process)
            (tmp_path / 'changed').touch()
        except BaseException:
            kill_test_process(process)
            process.communicate(timeout=10)
            raise
    try:
        stdout, stderr = process.communicate(timeout=15)
        assert process.returncode == 0, stderr
        assert json.loads(stdout.splitlines()[0])['error_code'] == 'confirmation_changed'
        assert not (tmp_path / 'entered').exists()
    finally:
        if process.poll() is None:
            kill_test_process(process)
            process.communicate(timeout=10)

@pytest.mark.integration
def test_killed_partial_preparation_preserves_active_inventory_and_can_resume(tmp_path):
    from embedding_preparation_support import ANONYMOUS_KEYRING, isolated_environment, run_cli
    from src.config.embedding_model_status import load_and_validate_model_inventory
    initial = run_cli(tmp_path, ['--download', '--json'])
    assert initial.returncode == 0, initial.stderr
    manifest = (tmp_path / 'models/manifest.json').read_bytes()
    files = {path: (path.read_bytes(), path.stat().st_mtime_ns)
             for path in (tmp_path / 'models/inventories').rglob('*') if path.is_file()}
    bootstrap = ANONYMOUS_KEYRING + r'''
import socket
socket.socket.connect = lambda *args: (_ for _ in ()).throw(AssertionError('Network forbidden'))
from src import embedding_model_preparation as preparation
original_version = preparation.version
preparation.version = lambda name: original_version(name) + '-changed-test'
import huggingface_hub as hub
from src.config.embedding_models import BM25_MODEL
original_download = hub.snapshot_download
def partial(**kwargs):
    if kwargs['repo_id'] == BM25_MODEL.model_id:
        Path(os.environ['TEST_PARTIAL_BARRIER']).touch()
        sys.stdin.read()  # Dense snapshot receipt is durable; sparse is pending.
    return original_download(**kwargs)
hub.snapshot_download = partial
from scripts.prepare_embedding_models import main
raise SystemExit(main(['--download', '--json']))
'''
    env = isolated_environment(tmp_path, fake_hub=True)
    env['TEST_PARTIAL_BARRIER'] = str(tmp_path / 'partial')
    process = subprocess.Popen([sys.executable, '-c', bootstrap], cwd=ROOT, env=env,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        _wait_for_file(tmp_path / 'partial', process)
        with pytest.raises(operations.ModelOperationBusyError):
            with operations.model_operation_lock(tmp_path / 'models', blocking=False):
                pytest.fail('Preparation lost its lock')
    finally:
        kill_test_process(process)
        process.communicate(timeout=10)
    assert (tmp_path / 'models/manifest.json').read_bytes() == manifest
    assert all((path.read_bytes(), path.stat().st_mtime_ns) == previous for path, previous in files.items())
    load_and_validate_model_inventory(tmp_path / 'models', deep=True)
    resumed = run_cli(tmp_path, ['--download', '--json'], different_versions=True)
    assert resumed.returncode == 0, resumed.stderr
    assert json.loads(resumed.stdout)['status'] == 'bereit'
    assert len((tmp_path / 'hub-calls.jsonl').read_text().splitlines()) == 4
    load_and_validate_model_inventory(tmp_path / 'models', deep=True)
