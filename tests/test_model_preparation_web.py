"""Confirmation, process coordination and private-output regression tests for M6.4."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from types import SimpleNamespace

import django
from django.core import signing
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web.settings")
from core import service_jobs
from core.services.commands import build_service_command
from core.services.model_preparation import preparation_confirmation, SALT
from src.model_operations import model_operation_lock, ModelOperationBusyError, model_preparation_binding


@pytest.fixture
def confirmation():
    django.setup()
    return {"action": "prepare_embedding_models", "confirmation": "prepare",
            "preparation_binding": preparation_confirmation()}


def test_confirmed_preparation_command_is_fixed(confirmation):
    command, errors = build_service_command("prepare_embedding_models", confirmation)
    assert not errors
    assert command == [sys.executable, "scripts/prepare_embedding_models.py", "--download", "--json"]


@pytest.mark.parametrize("change", ["missing", "wrong", "forged", "expired", "path", "contract", "extra", "duplicate"])
def test_preparation_rejects_invalid_confirmation(confirmation, monkeypatch, tmp_path, change):
    from django.http import QueryDict
    if change == "missing":
        confirmation.pop("confirmation")
    elif change == "wrong":
        confirmation["confirmation"] = "yes"
    elif change == "forged":
        confirmation["preparation_binding"] += "bad"
    elif change == "expired":
        monkeypatch.setattr(signing, "loads", lambda *a, **kw: (_ for _ in ()).throw(signing.SignatureExpired()))
    elif change == "path":
        monkeypatch.setenv("RATSI_MODELS_DIR", str(tmp_path / "other"))
    elif change == "contract":
        monkeypatch.setattr("src.model_operations.definitions.EMBEDDING_PIPELINE_VERSION", "changed")
    elif change == "extra":
        confirmation["model_id"] = "untrusted/model"
    else:
        data = QueryDict("", mutable=True)
        data.update(confirmation)
        data.appendlist("confirmation", "prepare")
        confirmation = data
    command, errors = build_service_command("prepare_embedding_models", confirmation)
    assert command is None
    assert errors


@pytest.mark.integration
def test_preparation_form_post_and_csrf(confirmation, monkeypatch):
    from django.test import Client
    from data_tools import views
    captured = []
    def start(action, command, cwd, **kwargs):
        captured.append((action, command, kwargs))
        return service_jobs.ServiceJob("prep-test", action, command)
    monkeypatch.setattr(views.service_jobs, "start_service_job", start)
    client = Client(enforce_csrf_checks=True)
    assert client.post("/daten/vektor/", confirmation).status_code == 403
    page = client.get("/daten/vektor/")
    assert page.status_code == 200
    assert b'Modelle vorbereiten' in page.content
    assert b'name="preparation_binding"' in page.content
    confirmation["csrfmiddlewaretoken"] = client.cookies["csrftoken"].value
    response = client.post("/daten/vektor/", confirmation)
    assert response.status_code == 302
    assert captured[0][0] == "prepare_embedding_models"
    assert captured[0][2]["preparation_binding"] == model_preparation_binding()


@pytest.mark.integration
def test_busy_preparation_displays_error_without_redirect(confirmation, monkeypatch):
    from django.test import Client
    from data_tools import views
    def busy(*args, **kwargs):
        raise service_jobs.ServiceJobStartError("Modellvorbereitung oder Indexjob ist bereits aktiv.")
    monkeypatch.setattr(views.service_jobs, "start_service_job", busy)
    response = Client().post("/daten/vektor/", confirmation)
    assert response.status_code == 200
    assert b'bereits aktiv' in response.content


@pytest.mark.integration
def test_model_lock_is_process_exclusive_and_released_on_exit(tmp_path):
    root = tmp_path / "models"
    script = "from pathlib import Path; from src.model_operations import model_operation_lock; import sys; " \
             "ctx=model_operation_lock(Path(sys.argv[1])); ctx.__enter__(); print('locked', flush=True); sys.stdin.read()"
    process = subprocess.Popen([sys.executable, "-c", script, str(root)], cwd=ROOT,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert process.stdout.readline().strip() == "locked"
        with pytest.raises(ModelOperationBusyError):
            with model_operation_lock(root, blocking=False):
                pytest.fail("A second process acquired the live lock")
    finally:
        process.kill()
        process.wait(timeout=10)
    with model_operation_lock(root, blocking=False):
        with model_operation_lock(root, blocking=False):
            assert (root / ".operation.lock").exists()


@pytest.mark.integration
def test_another_web_process_preserves_live_reservation_and_recovery(tmp_path, monkeypatch):
    db = tmp_path / "shared.sqlite"
    monkeypatch.setattr(service_jobs, "SERVICE_JOBS_DB", db)
    script = """
import sys
from pathlib import Path
sys.path.insert(0, 'web')
from core import service_jobs as jobs
jobs.SERVICE_JOBS_DB=Path(sys.argv[1])
class Thread:
    def __init__(self, **kwargs): pass
    def start(self): pass
jobs.threading.Thread=Thread
job=jobs.start_service_job('build_vector_index', ['unused'], Path.cwd())
print(job.job_id, flush=True)
sys.stdin.read()
"""
    process = subprocess.Popen([sys.executable, "-c", script, str(db)], cwd=ROOT,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        job_id = process.stdout.readline().strip()
        assert job_id
        assert service_jobs.get_service_job(job_id).status == "queued"
        with pytest.raises(service_jobs.ServiceJobStartError, match="bereits aktiv"):
            service_jobs.start_service_job("build_landkreis_vector_index", ["unused"], ROOT)
        assert service_jobs.get_service_job(job_id).status == "queued"
        # An unrelated local write must not overwrite the foreign reservation.
        service_jobs._jobs["other"] = service_jobs.ServiceJob("other", "check_embedding_models", [], status="ok")
        service_jobs._persist_snapshot_locked()
        with sqlite3.connect(db) as conn:
            assert conn.execute("SELECT status FROM service_jobs WHERE job_id=?", (job_id,)).fetchone()[0] == "queued"
    finally:
        process.kill()
        process.wait(timeout=10)
    assert service_jobs.get_service_job(job_id).status == "error"
    monkeypatch.setattr(service_jobs.threading.Thread, "start", lambda self: None)
    assert service_jobs.start_service_job("build_vector_index", ["unused"], ROOT).status == "queued"


@pytest.mark.integration
def test_alive_child_keeps_reservation_after_parent_exit(tmp_path, monkeypatch):
    job = service_jobs.ServiceJob("orphan", "build_vector_index", [], owner_pid=0, child_pid=os.getpid())
    service_jobs.list_service_jobs()
    with sqlite3.connect(service_jobs.SERVICE_JOBS_DB) as conn:
        service_jobs._store_job(conn, job)
    assert service_jobs.get_service_job("orphan").status == "queued"
    with pytest.raises(service_jobs.ServiceJobStartError):
        service_jobs.start_service_job("build_vector_index", [], ROOT)


def test_storage_failure_never_launches_worker(monkeypatch):
    def fail(*args):
        raise sqlite3.OperationalError("disk full")
    monkeypatch.setattr(service_jobs, "_initialize_db", fail)
    monkeypatch.setattr(service_jobs.threading.Thread, "start", lambda self: pytest.fail("worker started"))
    with pytest.raises(service_jobs.ServiceJobStartError):
        service_jobs.start_service_job("build_vector_index", [], ROOT)


@pytest.mark.parametrize("returncode,success", [(0, True), (1, True), (1, False)])
@pytest.mark.integration
def test_preparation_persists_only_safe_output(confirmation, monkeypatch, returncode, success, caplog):
    monkeypatch.setattr(service_jobs.threading.Thread, "start", lambda self: None)
    secret = "private-provider-token-DO-NOT-STORE"
    payload = {"operation": "download", "status": "bereit" if success else "fehlgeschlagen",
               "manifest_sha256": "a" * 64, "error_code": "network_unavailable", "message": secret,
               "inventory_dir": secret}
    process = SimpleNamespace(stdout=iter([secret + "\n", json.dumps(payload) + "\n"]),
                              pid=0, returncode=returncode, wait=lambda: None)
    def launch(*args, **kwargs):
        assert kwargs["stderr"] == subprocess.DEVNULL
        assert kwargs["env"]["RATSI_MODEL_PREPARATION_BINDING"] == model_preparation_binding()
        return process
    monkeypatch.setattr(service_jobs.subprocess, "Popen", launch)
    job = service_jobs.start_service_job("prepare_embedding_models", ["fixed"], ROOT,
                                        preparation_binding=model_preparation_binding())
    service_jobs._run_job(job.job_id, ROOT)
    assert job.status == ("ok" if success and returncode == 0 else "error")
    assert secret not in job.output + job.summary + caplog.text
    assert secret.encode() not in Path(service_jobs.SERVICE_JOBS_DB).read_bytes()
    assert job.summary


def test_cli_rejects_changed_confirmation_before_downloading(tmp_path, monkeypatch, capsys):
    from scripts import prepare_embedding_models as cli
    monkeypatch.setenv("RATSI_MODEL_PREPARATION_BINDING", "old-contract")
    monkeypatch.setattr(cli, "prepare_embedding_models", lambda path: pytest.fail("download started"))
    assert cli.main(["--download", "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error_code"] == "confirmation_changed"


@pytest.mark.integration
def test_simultaneous_web_starts_reserve_exactly_one_job(tmp_path):
    script = """
import sys
from pathlib import Path
sys.path.insert(0, 'web')
from core import service_jobs as jobs
jobs.SERVICE_JOBS_DB=Path(sys.argv[1])
class Thread:
    def __init__(self, **kwargs): pass
    def start(self): pass
jobs.threading.Thread=Thread
print('ready', flush=True)
sys.stdin.readline()
try:
    job=jobs.start_service_job('build_vector_index', ['unused'], Path.cwd())
    print('started', flush=True)
except jobs.ServiceJobStartError:
    print('busy', flush=True)
sys.stdin.read()
"""
    db = tmp_path / "shared.sqlite"
    processes = [subprocess.Popen([sys.executable, "-c", script, str(db)], cwd=ROOT,
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True) for _ in range(2)]
    try:
        for process in processes:
            assert process.stdout.readline().strip() == "ready"
        for process in processes:
            process.stdin.write("start\n")
            process.stdin.flush()
        assert sorted(process.stdout.readline().strip() for process in processes) == ["busy", "started"]
        with sqlite3.connect(db) as conn:
            assert conn.execute("SELECT COUNT(*) FROM service_jobs").fetchone()[0] == 1
    finally:
        for process in processes:
            process.kill()
            process.wait(timeout=10)


@pytest.mark.integration
def test_thread_failure_leaves_terminal_reservation(monkeypatch):
    def fail(self):
        raise RuntimeError("unable to start thread")
    monkeypatch.setattr(service_jobs.threading.Thread, "start", fail)
    with pytest.raises(service_jobs.ServiceJobStartError):
        service_jobs.start_service_job("build_vector_index", [], ROOT)
    assert not service_jobs.active_service_jobs()
    assert service_jobs.list_service_jobs()[0].status == "error"


@pytest.mark.integration
def test_preparation_launch_failure_hides_exception(confirmation, monkeypatch, caplog):
    monkeypatch.setattr(service_jobs.threading.Thread, "start", lambda self: None)
    secret = "unexpected-provider-token"
    def fail(*args, **kwargs):
        raise OSError(secret)
    monkeypatch.setattr(service_jobs.subprocess, "Popen", fail)
    job = service_jobs.start_service_job("prepare_embedding_models", ["fixed"], ROOT,
                                        preparation_binding=model_preparation_binding())
    service_jobs._run_job(job.job_id, ROOT)
    assert job.status == "error"
    assert secret not in job.output + job.summary + caplog.text
    assert secret.encode() not in Path(service_jobs.SERVICE_JOBS_DB).read_bytes()


@pytest.mark.integration
def test_preparation_job_refuses_stale_binding(monkeypatch):
    monkeypatch.setattr(service_jobs.threading.Thread, "start", lambda self: pytest.fail("worker started"))
    with pytest.raises(service_jobs.ServiceJobStartError, match="geändert"):
        service_jobs.start_service_job("prepare_embedding_models", [], ROOT, preparation_binding="stale")
    assert not service_jobs.list_service_jobs()


@pytest.mark.integration
def test_transient_worker_storage_failure_kills_child_and_allows_retry(confirmation, monkeypatch):
    monkeypatch.setattr(service_jobs.threading.Thread, "start", lambda self: None)
    terminated = []
    process = SimpleNamespace(stdout=iter([]), pid=os.getpid(), returncode=1,
                              wait=lambda: None, terminate=lambda: terminated.append(True))
    monkeypatch.setattr(service_jobs.subprocess, "Popen", lambda *a, **kw: process)
    job = service_jobs.start_service_job("prepare_embedding_models", [], ROOT,
                                        preparation_binding=model_preparation_binding())
    monkeypatch.setattr(service_jobs, "_last_persist_monotonic", service_jobs.time.monotonic())
    original = service_jobs._persist_snapshot_locked
    def fail():
        raise sqlite3.OperationalError("temporary disk failure")
    monkeypatch.setattr(service_jobs, "_persist_snapshot_locked", fail)
    service_jobs._run_job(job.job_id, ROOT)
    assert terminated
    monkeypatch.setattr(service_jobs, "_persist_snapshot_locked", original)
    assert service_jobs.get_service_job(job.job_id).status == "error"
    assert service_jobs.start_service_job("build_vector_index", [], ROOT).status == "queued"
