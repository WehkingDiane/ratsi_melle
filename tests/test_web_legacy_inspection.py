"""Server-bound legacy commands, private reports and read-only web workflows."""
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import django
from django.core import signing
from django.http import QueryDict
from django.test import Client
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web.settings")
from core import service_jobs
REAL_THREAD_START = service_jobs.threading.Thread.start
from core.services import paths
from core.services.commands import build_service_command
from core.services import legacy_inspection as legacy
from data_tools import services as data_services
from src.config.embedding_models import BM25_MODEL, HARRIER_MODEL, HARRIER_TOKENIZER
from src.config.index_compatibility import IndexCompatibility
from src.indexing.legacy_inspection_report import REPORT_VERSION, report_tolerances


@pytest.fixture
def setup(tmp_path, monkeypatch):
    django.setup()
    monkeypatch.setattr(paths, "PRIVATE_DATA_DIR", tmp_path / "private")
    monkeypatch.setattr(paths, "QDRANT_DIR", tmp_path / "qdrant")
    monkeypatch.setattr(paths, "LOCAL_INDEX_DB", tmp_path / "source.sqlite")
    monkeypatch.setattr(data_services, "QDRANT_DIR", paths.QDRANT_DIR)
    monkeypatch.setattr(data_services, "LOCAL_INDEX_DB", paths.LOCAL_INDEX_DB)
    monkeypatch.setattr(service_jobs.threading.Thread, "start", lambda self: None)
    return tmp_path


def post_data(collection):
    context = legacy.inspection_context(collection)
    return {"action": "inspect_legacy_index", "collection": collection,
            "inspection_binding": signing.dumps(context, salt=legacy.SALT)}


def make_job(collection="ratsi_passages"):
    data = post_data(collection)
    command, errors = build_service_command("inspect_legacy_index", data)
    assert not errors
    return service_jobs.start_service_job("inspect_legacy_index", command, ROOT,
                                         inspection_context=legacy.confirmed_inspection_context(data))


def write_report(job, verified=True):
    context = json.loads(job.inspection_context)
    report = {"report_version": REPORT_VERSION, "checked_at": "2026-10-02T08:00:00+00:00",
              **{key: context[key] for key in ("collection", "target", "target_sha256", "source_db")},
              "sample_limit": 32, "tolerances": report_tolerances(), "result": "aborted",
              "abort_code": "store_missing", "point_count": None, "point_ids_sha256": None,
              "sample_count": 0, "sample_ids": [], "compatibility": None}
    if verified:
        report.update(result="verified", abort_code=None, point_count=1, point_ids_sha256="b" * 64,
                      sample_count=1, sample_ids=[1], compatibility=IndexCompatibility(
                          dense_model_id=HARRIER_MODEL.model_id, dense_revision=HARRIER_MODEL.revision,
                          sparse_model_id=BM25_MODEL.model_id, sparse_revision=BM25_MODEL.revision,
                          tokenizer_model_id=HARRIER_TOKENIZER.model_id,
                          tokenizer_revision=HARRIER_TOKENIZER.revision, manifest_sha256="a" * 64,
                          vector_dimension=HARRIER_MODEL.vector_dimension,
                          pipeline_version="passages-1").as_dict())
    path = Path(context["report_root"]) / f"{job.job_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report))
    return path, report


@pytest.mark.parametrize("collection", legacy.COLLECTIONS)
@pytest.mark.integration
def test_inspection_command_and_job_path_are_server_derived(setup, collection):
    command, errors = build_service_command("inspect_legacy_index", post_data(collection))
    assert not errors
    assert "--inspect" in command and "--apply" not in command
    assert command[command.index("--qdrant-dir") + 1] == str(paths.QDRANT_DIR.resolve())
    if collection == "ratsi_documents":
        assert command[command.index("--source-db") + 1] == str(paths.LOCAL_INDEX_DB.resolve())
    else:
        assert "--source-db" not in command
    context = legacy.confirmed_inspection_context(post_data(collection))
    job = service_jobs.start_service_job("inspect_legacy_index", command, ROOT, inspection_context=context)
    assert job.command[job.command.index("--report") + 1] == str(Path(context["report_root"]) / f"{job.job_id}.json")


@pytest.mark.parametrize("field", ["report", "report_path", "source_db", "qdrant_dir", "url", "sample_limit", "tolerance", "args", "confirm_collection", "apply"])
def test_inspection_rejects_free_parameters(setup, field):
    data = post_data("ratsi_passages")
    data[field] = "untrusted"
    command, errors = build_service_command("inspect_legacy_index", data)
    assert command is None and errors


@pytest.mark.parametrize("change", ["landkreis", "unknown", "forged", "expired", "duplicate", "target", "source", "model", "root"])
def test_inspection_rejects_stale_or_invalid_binding(setup, monkeypatch, change):
    data = post_data("ratsi_documents")
    if change in {"landkreis", "unknown"}:
        data["collection"] = "landkreis_publications" if change == "landkreis" else "unknown"
    elif change == "forged":
        data["inspection_binding"] += "invalid"
    elif change == "expired":
        monkeypatch.setattr(signing, "loads", lambda *a, **kw: (_ for _ in ()).throw(signing.SignatureExpired()))
    elif change == "duplicate":
        values = QueryDict("", mutable=True)
        values.update(data)
        values.appendlist("collection", "ratsi_passages")
        data = values
    elif change == "target":
        monkeypatch.setenv("RATSI_QDRANT_URL", "http://different.example:6333")
    elif change == "source":
        monkeypatch.setattr(paths, "LOCAL_INDEX_DB", setup / "different.sqlite")
    elif change == "root":
        monkeypatch.setattr(paths, "PRIVATE_DATA_DIR", setup / "different")
    else:
        monkeypatch.setenv("RATSI_MODELS_DIR", str(setup / "different-models"))
    command, errors = build_service_command("inspect_legacy_index", data)
    assert command is None and errors


@pytest.mark.integration
def test_inspection_forms_csrf_post_and_busy_state(setup):
    from bs4 import BeautifulSoup
    client = Client(enforce_csrf_checks=True)
    assert client.post("/daten/vektor/", post_data("ratsi_passages")).status_code == 403
    page = client.get("/daten/vektor/")
    soup = BeautifulSoup(page.content, "html.parser")
    forms = soup.select("#legacy-inspection form")
    assert len(forms) == 2
    for form in forms:
        assert {item["name"] for item in form.select("[name]")} == {"action", "collection", "csrfmiddlewaretoken", "inspection_binding"}
    assert "rebuild_required" in page.content.decode()
    data = post_data("ratsi_passages") | {"csrfmiddlewaretoken": client.cookies["csrftoken"].value}
    response = client.post("/daten/vektor/", data)
    assert response.status_code == 302
    assert client.post("/daten/vektor/", data).status_code == 200
    assert len(service_jobs.list_service_jobs()) == 1


@pytest.mark.integration
@pytest.mark.parametrize("verified", [True, False])
def test_private_worker_preserves_report_and_safe_result(setup, monkeypatch, verified, caplog):
    job = make_job("ratsi_documents")
    path, report = write_report(job, verified)
    secret = "private-token-DO-NOT-PERSIST"
    process = SimpleNamespace(stdout=iter([secret]), pid=0, wait=lambda: None, returncode=0 if verified else 1)
    def launch(*args, **kwargs):
        import subprocess
        assert kwargs["stderr"] == subprocess.DEVNULL
        assert json.loads(kwargs["env"]["RATSI_LEGACY_INSPECTION_CONTEXT"]) == json.loads(job.inspection_context)
        return process
    monkeypatch.setattr(service_jobs.subprocess, "Popen", launch)
    service_jobs._run_job(job.job_id, ROOT)
    assert job.status == ("ok" if verified else "error")
    assert path.exists() and job.report_sha256
    assert secret not in job.output + job.summary + caplog.text
    assert secret.encode() not in Path(service_jobs.SERVICE_JOBS_DB).read_bytes()
    client = Client()
    page = client.get(f"/daten/jobs/{job.job_id}/")
    assert b"Legacy-Pr" in page.content
    result = client.get(f"/daten/jobs/{job.job_id}/status/").json()["legacy_report"]
    assert result["result"] == report["result"]
    assert result["source_db"] == str(paths.LOCAL_INDEX_DB.resolve())
    assert result["historical"] is False


@pytest.mark.integration
@pytest.mark.parametrize("change", ["target", "collection", "source", "format", "timestamp", "samples", "result", "symlink", "oversize", "after-completion"])
def test_foreign_or_invalid_report_is_not_displayed(setup, monkeypatch, change):
    job = make_job("ratsi_documents")
    path, report = write_report(job)
    if change == "after-completion":
        service_jobs._update_job(job.job_id, status="ok", report_sha256=legacy.bound_report(job)["report_sha256"])
        report["point_ids_sha256"] = "c" * 64
    elif change in {"target", "collection", "source"}:
        report[{"target": "target_sha256", "collection": "collection", "source": "source_db"}[change]] = "different"
    elif change == "format":
        report["report_version"] = 99
    elif change == "timestamp":
        report["checked_at"] = "2026-10-02T08:00:00"
    elif change == "samples":
        report["sample_count"] = 33
    elif change == "result":
        report["result"] = "untrusted"
    if change == "symlink":
        other = setup / "report.json"
        path.rename(other)
        path.symlink_to(other)
    elif change == "oversize":
        path.write_text(" " * (1024 * 1024 + 1))
    else:
        path.write_text(json.dumps(report))
    if change == "after-completion":
        assert legacy.inspection_result(job)["invalid"]
    else:
        monkeypatch.setattr(service_jobs.subprocess, "Popen", lambda *a, **kw: SimpleNamespace(stdout=iter([]), pid=0, wait=lambda: None, returncode=0))
        service_jobs._run_job(job.job_id, ROOT)
        assert job.status == "error" and not job.report_sha256
        assert legacy.inspection_result(job)["invalid"]


@pytest.mark.integration
def test_config_change_marks_completed_report_historical(setup, monkeypatch):
    job = make_job()
    write_report(job)
    service_jobs._update_job(job.job_id, status="ok", report_sha256=legacy.bound_report(job)["report_sha256"])
    monkeypatch.setenv("RATSI_QDRANT_URL", "http://different.example:6333")
    assert legacy.inspection_result(job)["historical"]


@pytest.mark.integration
def test_real_cli_aborted_inspection_does_not_create_qdrant_store(setup, monkeypatch):
    job = make_job()
    from scripts import migrate_legacy_index as cli
    monkeypatch.setenv("RATSI_LEGACY_INSPECTION_CONTEXT", job.inspection_context)
    from src.observability import RUN_ID_ENV
    monkeypatch.setenv(RUN_ID_ENV, job.job_id)
    assert cli.main(job.command[2:]) == 1
    report = legacy.bound_report(job)
    assert report["abort_code"] == "store_missing"
    assert not paths.QDRANT_DIR.exists()


@pytest.mark.integration
def test_cli_rechecks_bound_target_before_opening_client(setup, monkeypatch):
    job = make_job()
    from scripts import migrate_legacy_index as cli
    from src.observability import RUN_ID_ENV
    monkeypatch.setenv("RATSI_LEGACY_INSPECTION_CONTEXT", job.inspection_context)
    monkeypatch.setenv(RUN_ID_ENV, job.job_id)
    monkeypatch.setenv("RATSI_QDRANT_URL", "http://different.example:6333")
    monkeypatch.setattr(cli.QdrantConnection, "create_client", lambda self: pytest.fail("client opened"))
    assert cli.main(job.command[2:]) == 1
    assert not (Path(json.loads(job.inspection_context)["report_root"]) / f"{job.job_id}.json").exists()


@pytest.mark.parametrize("handle,exit_code,error,expected", [
    (123, 259, 0, True), (123, 0, 0, False), (0, 0, 87, False), (0, 0, 5, True),
])
def test_windows_liveness_probe_queries_without_termination(monkeypatch, handle, exit_code, error, expected):
    import ctypes
    closed = []
    class Call:
        def __init__(self, function):
            self.function = function
        def __call__(self, *args):
            return self.function(*args)
    def get_exit(handle, pointer):
        pointer._obj.value = exit_code
        return True
    kernel = SimpleNamespace(OpenProcess=Call(lambda *a: handle), GetExitCodeProcess=Call(get_exit),
                             CloseHandle=Call(lambda handle: closed.append(handle)))
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **kw: kernel, raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: error, raising=False)
    assert service_jobs._windows_pid_alive(1234) is expected
    assert closed == ([handle] if handle else [])


@pytest.mark.integration
def test_real_web_job_runs_read_only_cli_and_retains_abort_report(setup, monkeypatch):
    import time
    monkeypatch.setattr(service_jobs.threading.Thread, "start", REAL_THREAD_START)
    job = make_job()
    deadline = time.monotonic() + 10
    while job.status in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(0.02)
    assert job.status == "error" and job.exit_code == 1
    assert legacy.inspection_result(job)["abort_code"] == "store_missing"
    assert not paths.QDRANT_DIR.exists()


@pytest.mark.integration
def test_server_url_secrets_are_not_stored_or_displayed(setup, monkeypatch):
    monkeypatch.setenv("RATSI_QDRANT_URL", "http://username:secret-password@example.test:6333/private-path")
    job = make_job()
    public = job.to_dict()
    assert "secret-password" not in json.dumps(public) + job.inspection_context
    assert "private-path" not in json.dumps(public) + job.inspection_context
    assert json.loads(job.inspection_context)["target"] == "http://example.test:6333"
    assert b"secret-password" not in Path(service_jobs.SERVICE_JOBS_DB).read_bytes()


@pytest.mark.integration
def test_invalid_post_never_starts_legacy_job(setup, monkeypatch):
    client = Client(enforce_csrf_checks=True)
    client.get("/daten/vektor/")
    data = post_data("ratsi_passages") | {"report": "foreign.json", "csrfmiddlewaretoken": client.cookies["csrftoken"].value}
    monkeypatch.setattr(service_jobs, "start_service_job", lambda *a, **kw: pytest.fail("job started"))
    assert client.post("/daten/vektor/", data).status_code == 200
