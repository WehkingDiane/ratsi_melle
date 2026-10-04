"""Confirmed release gates, report substitution and CLI lock ordering."""
import io
import json
import os
from contextlib import redirect_stdout
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

from django.core import signing
from django.http import QueryDict
from django.test import Client
import pytest

from test_web_legacy_inspection import setup, make_job, write_report, ROOT
from test_legacy_index_inspection import compatibility, _client, _point, Vectorizer
from core import service_jobs
from core.services import legacy_inspection as legacy
from core.services.commands import build_service_command
from src.config.index_compatibility import IndexCompatibility
from src.indexing import legacy_index_migration as migration
from src.observability import RUN_ID_ENV


@pytest.fixture
def verified(setup, monkeypatch):
    job = make_job()
    path, report = write_report(job)
    current = IndexCompatibility.from_dict(report["compatibility"])
    monkeypatch.setattr("src.config.index_compatibility.current_index_compatibility", lambda: current)
    digest = legacy.bound_report(job)["report_sha256"]
    service_jobs._update_job(job.job_id, status="ok", exit_code=0, report_sha256=digest)
    return job, path, report


def data_for(job):
    return {"action": "apply_legacy_index", "inspection_job_id": job.job_id,
            "apply_binding": legacy.application_confirmation(job), "confirmation": "apply"}


@pytest.mark.integration
def test_application_command_is_derived_from_the_inspection_job(verified):
    job, path, _ = verified
    command, errors = build_service_command("apply_legacy_index", data_for(job))
    assert not errors
    assert "--apply" in command and "--inspect" not in command
    assert command[command.index("--report") + 1] == str(path)
    assert command[command.index("--confirm-collection") + 1] == "ratsi_passages"
    payload = legacy.confirmed_application_payload(data_for(job))
    application = service_jobs.start_service_job("apply_legacy_index", ["untrusted-command"], ROOT,
                                                 application_context=payload)
    assert application.command == command
    assert application.report_sha256 == job.report_sha256
    assert json.loads(application.application_context)["inspection_job_id"] == job.job_id


@pytest.mark.integration
@pytest.mark.parametrize("field", ["collection", "confirm_collection", "report", "report_path", "source_db", "qdrant_dir", "target", "sample_limit", "tolerance", "args", "model_id", "revision"])
def test_application_rejects_all_free_parameters(verified, field):
    data = data_for(verified[0]) | {field: "untrusted"}
    command, errors = build_service_command("apply_legacy_index", data)
    assert command is None and errors


@pytest.mark.integration
@pytest.mark.parametrize("field", ["action", "inspection_job_id", "apply_binding", "confirmation", "csrfmiddlewaretoken"])
def test_application_rejects_duplicate_fields(verified, field):
    data = QueryDict("", mutable=True)
    data.update(data_for(verified[0]))
    data.setlist(field, [data.get(field, "token")] * 2)
    command, errors = build_service_command("apply_legacy_index", data)
    assert command is None and errors


@pytest.mark.integration
@pytest.mark.parametrize("change", ["missing-consent", "wrong-consent", "forged", "expired", "missing-job", "different-job", "queued", "failed", "wrong-exit", "report", "missing-report", "target", "model"])
def test_application_rejects_missing_or_stale_evidence(verified, monkeypatch, change):
    job, path, report = verified
    data = data_for(job)
    if change == "missing-consent":
        data.pop("confirmation")
    elif change == "wrong-consent":
        data["confirmation"] = "yes"
    elif change == "forged":
        data["apply_binding"] += "tampered"
    elif change == "expired":
        monkeypatch.setattr(signing, "loads", lambda *a, **kw: (_ for _ in ()).throw(signing.SignatureExpired()))
    elif change == "missing-job":
        data["inspection_job_id"] = "absent"
    elif change == "different-job":
        data["inspection_job_id"] = service_jobs.start_service_job("check_embedding_models", [], ROOT).job_id
    elif change in {"queued", "failed", "wrong-exit"}:
        service_jobs._update_job(job.job_id, status="queued" if change == "queued" else "error" if change == "failed" else "ok",
                                 exit_code=1 if change == "wrong-exit" else 0)
    elif change == "report":
        path.write_text(json.dumps(report, indent=2))
    elif change == "missing-report":
        path.unlink()
    elif change == "target":
        monkeypatch.setenv("RATSI_QDRANT_URL", "http://different.example:6333")
    else:
        monkeypatch.setattr("src.config.index_compatibility.current_index_compatibility", lambda: replace(IndexCompatibility.from_dict(report["compatibility"]), manifest_sha256="f" * 64))
    command, errors = build_service_command("apply_legacy_index", data)
    assert command is None and errors
    assert not service_jobs.active_service_jobs() or change in {"queued", "different-job"}


@pytest.mark.integration
def test_pruned_job_is_rejected_at_transactional_start(verified):
    job, _, _ = verified
    payload = legacy.confirmed_application_payload(data_for(job))
    import sqlite3
    with sqlite3.connect(service_jobs.SERVICE_JOBS_DB) as conn:
        conn.execute("DELETE FROM service_jobs WHERE job_id=?", (job.job_id,))
    with pytest.raises(service_jobs.ServiceJobStartError):
        service_jobs.start_service_job("apply_legacy_index", [], ROOT, application_context=payload)


@pytest.mark.integration
def test_csrf_confirmation_and_busy_release_form(verified):
    from bs4 import BeautifulSoup
    job, _, _ = verified
    client = Client(enforce_csrf_checks=True)
    url = f"/daten/jobs/{job.job_id}/"
    assert client.post(url, data_for(job)).status_code == 403
    page = client.get(url)
    form = BeautifulSoup(page.content, "html.parser").select_one("#legacy-apply")
    assert form is not None
    assert {item["name"] for item in form.select("[name]")} == {"action", "csrfmiddlewaretoken", "inspection_job_id", "apply_binding", "confirmation"}
    data = data_for(job) | {"csrfmiddlewaretoken": client.cookies["csrftoken"].value}
    assert client.post(url, data).status_code == 302
    assert client.post(url, data).status_code == 200
    assert len(service_jobs.active_service_jobs()) == 1


@pytest.mark.integration
def test_unconfirmed_or_aborted_job_has_no_release_form(verified):
    job, _, _ = verified
    service_jobs._update_job(job.job_id, status="error", exit_code=1)
    assert legacy.application_confirmation(job) is None
    assert b'id="legacy-apply"' not in Client().get(f"/daten/jobs/{job.job_id}/").content


@pytest.mark.integration
@pytest.mark.parametrize("returncode,success", [(0, True), (1, True), (1, False)])
def test_release_worker_keeps_only_safe_results(verified, monkeypatch, caplog, returncode, success):
    source, _, _ = verified
    payload = legacy.confirmed_application_payload(data_for(source))
    job = service_jobs.start_service_job("apply_legacy_index", [], ROOT, application_context=payload)
    secret = "provider-secret-not-for-storage"
    result = ({"collection": "ratsi_passages", "provenance": "legacy_verified", "point_count": 1,
               "backfilled_points": 1, "message": secret} if success else
              {"result": "aborted", "abort_code": "report_changed", "message": secret})
    def launch(*args, **kwargs):
        import subprocess
        assert kwargs["stderr"] == subprocess.DEVNULL
        assert json.loads(kwargs["env"]["RATSI_LEGACY_APPLY_CONTEXT"]) == payload
        assert "RATSI_LEGACY_INSPECTION_CONTEXT" not in kwargs["env"]
        return SimpleNamespace(stdout=iter([secret, json.dumps(result)]), pid=0, wait=lambda: None, returncode=returncode)
    monkeypatch.setattr(service_jobs.subprocess, "Popen", launch)
    service_jobs._run_job(job.job_id, ROOT)
    assert job.status == ("ok" if success and returncode == 0 else "error")
    assert secret not in job.output + job.summary + caplog.text
    assert secret.encode() not in Path(service_jobs.SERVICE_JOBS_DB).read_bytes()


@pytest.mark.integration
def test_cli_rejects_report_substitution_under_collection_lock(verified, monkeypatch, capsys):
    from contextlib import contextmanager
    from scripts import migrate_legacy_index as cli
    source, path, report = verified
    payload = legacy.confirmed_application_payload(data_for(source))
    command = legacy.application_command(payload)
    monkeypatch.setenv("RATSI_LEGACY_APPLY_CONTEXT", json.dumps(payload))
    monkeypatch.setattr(cli, "_local_store_exists", lambda path: True)
    original_lock = cli._migration_lock
    @contextmanager
    def substitute(connection, collection):
        with original_lock(connection, collection):
            path.write_text(json.dumps(report, indent=2))
            yield
    monkeypatch.setattr(cli, "_migration_lock", substitute)
    monkeypatch.setattr(cli.QdrantConnection, "create_client", lambda self: pytest.fail("client opened"))
    assert cli.main(command[2:]) == 1
    assert json.loads(capsys.readouterr().out)["abort_code"] == "report_changed"


@pytest.mark.integration
@pytest.mark.parametrize("scenario", ["clean", "report-changed", "points-changed", "backfill-error"])
def test_bound_web_cli_release_rechecks_and_preserves_vectors(setup, monkeypatch, compatibility, scenario):
    from scripts import migrate_legacy_index as cli
    from src.indexing.legacy_inspection_report import inspect_and_write_report
    from src.indexing import legacy_index_inspection as inspection
    from src.qdrant_connection import QdrantConnection
    monkeypatch.setattr("src.config.index_compatibility.current_index_compatibility", lambda: compatibility)
    monkeypatch.setattr(inspection, "current_index_compatibility", lambda *, deep: compatibility)
    real_inspect = migration.inspect_legacy_collection
    monkeypatch.setattr(migration, "inspect_legacy_collection", lambda *a, **kw: real_inspect(*a, **kw, vectorizer_factory=Vectorizer))
    client = _client()
    closed = []
    class Wrapped:
        def __getattr__(self, name):
            return getattr(client, name)
        def close(self):
            closed.append(True)
        def set_payload(self, **kwargs):
            client.set_payload(**kwargs)
            if scenario == "backfill-error":
                raise RuntimeError("private-provider-detail")
    try:
        client.upsert("ratsi_passages", [_point(1, "one", {"text": "one", "snippet": "one", "committed": True})])
        source = make_job()
        context = json.loads(source.inspection_context)
        path = Path(context["report_root"]) / f"{source.job_id}.json"
        connection = QdrantConnection.from_env(Path(context["qdrant_dir"]))
        inspect_and_write_report(connection, client, "ratsi_passages", path, vectorizer_factory=Vectorizer)
        service_jobs._update_job(source.job_id, status="ok", exit_code=0, report_sha256=sha256(path.read_bytes()).hexdigest())
        before = client.retrieve("ratsi_passages", ids=[1], with_vectors=True)[0].vector
        payload = legacy.confirmed_application_payload(data_for(source))
        job = service_jobs.start_service_job("apply_legacy_index", [], ROOT, application_context=payload)
        monkeypatch.setattr(cli, "_local_store_exists", lambda path: True)
        def open_client(self):
            assert self.release_path("ratsi_passages").with_suffix(".migration.lock").resolve() in migration._held_locks.paths
            if scenario == "report-changed":
                path.write_text(path.read_text() + " ")
            if scenario == "points-changed":
                client.upsert("ratsi_passages", [_point(2, "two", {"text": "two", "snippet": "two", "committed": True})])
            return Wrapped()
        monkeypatch.setattr(cli.QdrantConnection, "create_client", open_client)
        def launch(command, **kwargs):
            output = io.StringIO()
            with monkeypatch.context() as local:
                local.setenv("RATSI_LEGACY_APPLY_CONTEXT", kwargs["env"]["RATSI_LEGACY_APPLY_CONTEXT"])
                local.setenv(RUN_ID_ENV, kwargs["env"][RUN_ID_ENV])
                with redirect_stdout(output):
                    code = cli.main(command[2:])
            return SimpleNamespace(stdout=iter(output.getvalue().splitlines()), pid=0, wait=lambda: None, returncode=code)
        monkeypatch.setattr(service_jobs.subprocess, "Popen", launch)
        service_jobs._run_job(job.job_id, ROOT)
        assert closed == [True]
        after = client.retrieve("ratsi_passages", ids=[1], with_vectors=True)[0]
        assert after.vector == before
        if scenario == "clean":
            assert job.status == "ok"
            assert after.payload["index_provenance"] == "legacy_verified"
            assert connection.read_index_compatibility("ratsi_passages") == compatibility
            assert legacy.application_confirmation(source) is None
        else:
            assert job.status == "error"
            assert "index_compatibility" not in after.payload
            assert "index_provenance" not in after.payload
            assert not connection.release_path("ratsi_passages").exists()
            assert json.loads(job.output)["abort_code"] == {
                "report-changed": "report_changed", "points-changed": "report_stale", "backfill-error": "release_failed",
            }[scenario]
            assert "private-provider-detail" not in job.output
    finally:
        client.close()
