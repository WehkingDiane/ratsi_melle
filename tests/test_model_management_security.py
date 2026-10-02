"""M6.10: web gates, persisted results and public responses for model jobs."""

import json
import sqlite3
import sys
from types import SimpleNamespace
from urllib.parse import quote

from django.test import Client
import pytest

from test_web_legacy_inspection import ROOT, setup, post_data, write_report
from test_web_legacy_apply import verified, data_for
from core import service_jobs
from core.services import paths
from core.services.model_preparation import preparation_confirmation
from data_tools import services, views


pytestmark = pytest.mark.integration
ACTIONS = (
    "check_embedding_models", "prepare_embedding_models",
    "inspect_legacy_index", "apply_legacy_index",
)


@pytest.fixture(autouse=True)
def isolated_status_inputs(tmp_path, monkeypatch):
    """Keep fake CLI contracts and unrelated status data local to each test."""
    monkeypatch.setattr("src.model_operations.version", lambda name: "test-library-version")
    monkeypatch.setattr(paths, "RAW_DATA_DIR", tmp_path / "raw")
    monkeypatch.setattr(paths, "ONLINE_INDEX_DB", tmp_path / "online.sqlite")
    monkeypatch.setattr(services, "LANDKREIS_PUBLICATIONS_DB", tmp_path / "landkreis.sqlite")


def request_data(action, source):
    if action == "apply_legacy_index":
        return data_for(source)
    if action == "inspect_legacy_index":
        return post_data("ratsi_passages")
    if action == "prepare_embedding_models":
        return {"action": action, "confirmation": "prepare",
                "preparation_binding": preparation_confirmation()}
    return {"action": action}


def job_ids():
    with sqlite3.connect(service_jobs.SERVICE_JOBS_DB) as conn:
        return {row[0] for row in conn.execute("SELECT job_id FROM service_jobs")}


def post_job(client, action, source, data=None):
    url = f"/daten/jobs/{source.job_id}/" if action == "apply_legacy_index" else "/daten/vektor/"
    client.get(url)
    values = request_data(action, source) if data is None else dict(data)
    values.setdefault("csrfmiddlewaretoken", client.cookies["csrftoken"].value)
    return client.post(url, values)


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("token", [None, "invalid", "x" * 64])
def test_missing_malformed_or_foreign_csrf_never_reserves_a_job(verified, monkeypatch, action, token):
    source, _, _ = verified
    before = job_ids()
    monkeypatch.setattr(views.service_jobs, "start_service_job",
                        lambda *a, **kw: pytest.fail("CSRF failure reached job start"))
    client = Client(enforce_csrf_checks=True)
    url = f"/daten/jobs/{source.job_id}/" if action == "apply_legacy_index" else "/daten/vektor/"
    client.get(url)
    data = request_data(action, source)
    if token is not None:
        data["csrfmiddlewaretoken"] = token
    assert client.post(url, data).status_code == 403
    assert job_ids() == before


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("change", ["extra", "duplicate", "binding"])
def test_invalid_post_with_valid_csrf_never_reserves_a_job(verified, monkeypatch, action, change):
    source, _, _ = verified
    data = request_data(action, source)
    if change == "extra":
        data["command"] = "--download; provider-secret"
    elif change == "duplicate":
        data["action"] = [action, action]
    elif action == "check_embedding_models":
        data["action"] = "unknown-provider-secret"
    else:
        field = {"prepare_embedding_models": "preparation_binding",
                 "inspect_legacy_index": "inspection_binding",
                 "apply_legacy_index": "apply_binding"}[action]
        data[field] += "tampered"
    before = job_ids()
    monkeypatch.setattr(views.service_jobs, "start_service_job",
                        lambda *a, **kw: pytest.fail("Invalid POST reached job start"))
    response = post_job(Client(enforce_csrf_checks=True), action, source, data)
    assert response.status_code == 200
    assert "provider-secret" not in response.content.decode()
    assert job_ids() == before


@pytest.mark.parametrize("action", ACTIONS)
def test_confirmed_web_post_reserves_one_job_and_redirects_to_it(verified, action):
    source, _, _ = verified
    before = job_ids()
    response = post_job(Client(enforce_csrf_checks=True), action, source)
    assert response.status_code == 302
    added = job_ids() - before
    assert len(added) == 1
    job = service_jobs.get_service_job(added.pop())
    assert response.headers["Location"] == f"/daten/jobs/{job.job_id}/"
    assert job.action == action and job.status == "queued"
    assert job.command[0] == sys.executable
    assert "--json" in job.command or "--inspect" in job.command or "--apply" in job.command
    assert len(service_jobs.active_service_jobs()) == 1


@pytest.mark.parametrize("action", ["prepare_embedding_models", "apply_legacy_index"])
@pytest.mark.parametrize("consent", [None, "yes"])
def test_signed_binding_alone_does_not_authorize_a_write(verified, action, consent):
    source, _, _ = verified
    data = request_data(action, source)
    data.pop("confirmation")
    if consent is not None:
        data["confirmation"] = consent
    before = job_ids()
    assert post_job(Client(enforce_csrf_checks=True), action, source, data).status_code == 200
    assert job_ids() == before


@pytest.mark.parametrize("action", ACTIONS[1:])
@pytest.mark.parametrize("when", ["before-post", "before-reservation"])
def test_changed_library_contract_requires_fresh_confirmation(verified, monkeypatch, action, when):
    source, _, _ = verified
    client = Client(enforce_csrf_checks=True)
    client.get(f"/daten/jobs/{source.job_id}/" if action == "apply_legacy_index" else "/daten/vektor/")
    data = request_data(action, source)
    before = job_ids()

    def change_contract():
        monkeypatch.setattr("src.model_operations.version", lambda name: "changed-after-confirmation")

    if when == "before-post":
        change_contract()
    else:
        start = service_jobs.start_service_job

        def changed_start(*args, **kwargs):
            change_contract()
            return start(*args, **kwargs)

        monkeypatch.setattr(service_jobs, "start_service_job", changed_start)
    response = post_job(client, action, source, data)
    assert response.status_code == 200
    assert job_ids() == before
    assert not service_jobs.active_service_jobs()


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("failure", ["launch", "stream", "exit"])
def test_private_child_failures_stay_private_in_storage_and_all_web_surfaces(
    verified, monkeypatch, caplog, action, failure,
):
    source, _, _ = verified
    # Credentials known only to the child cannot be removed by parent-side replacement.
    secret = "child-only-secret:/+ DO-NOT-PUBLISH"
    encoded = quote(secret, safe="")
    raw = [secret[:12], secret[12:], f"https://user:{encoded}@example.test/?token={encoded}",
           json.dumps({"status": secret, "message": secret, "error_code": secret})]
    terminated = []

    def stream():
        yield from raw
        if failure == "stream":
            raise OSError(secret)

    def launch(*args, **kwargs):
        assert kwargs["stderr"] == service_jobs.subprocess.DEVNULL
        if failure == "launch":
            raise OSError(secret)
        return SimpleNamespace(stdout=stream(), pid=0, returncode=-15, wait=lambda: None,
                               terminate=lambda: terminated.append(True))

    response = post_job(Client(enforce_csrf_checks=True), action, source)
    assert response.status_code == 302
    job_id = response.headers["Location"].strip("/").split("/")[-1]
    monkeypatch.setattr(service_jobs.subprocess, "Popen", launch)
    service_jobs._run_job(job_id, ROOT)
    record = service_jobs.get_service_job(job_id)
    assert record.status == "error" and record.completed_at
    assert bool(terminated) == (failure == "stream")
    assert not service_jobs.active_service_jobs()
    client = Client()
    public = [json.dumps(record.to_dict()), caplog.text]
    for url in (f"/daten/jobs/{job_id}/", f"/daten/jobs/{job_id}/status/",
                "/daten/jobs/status/", "/daten/model-jobs/status/", "/daten/status/"):
        response = client.get(url)
        assert response.status_code == 200
        public.append(response.content.decode())
    public.append(service_jobs.SERVICE_JOBS_DB.read_bytes().decode(errors="replace"))
    for value in public:
        assert secret not in value and encoded not in value
        assert secret[:12] not in value and secret[12:] not in value
    # Reloading the persisted row must preserve the failure and safe last line.
    monkeypatch.setattr(service_jobs, "_loaded_db_path", None)
    restored = service_jobs.get_service_job(job_id)
    assert (restored.status, restored.output, restored.summary) == (
        record.status, record.output, record.summary)


@pytest.mark.parametrize("state,exit_code,expected", [
    ("bereit", 0, "ok"), ("bereit", 1, "error"), ("bereit", -15, "error"),
    ("fehlt", 0, "error"), ("fehlt", 1, "error"),
    ("unvollstaendig", 1, "error"), ("inkompatibel", 1, "error"),
    ("inkompatibel", 2, "error"), ("unknown", 0, "error"),
])
def test_model_check_status_exit_code_and_public_job_evidence_agree(
    verified, monkeypatch, state, exit_code, expected,
):
    source, _, _ = verified
    response = post_job(Client(enforce_csrf_checks=True), "check_embedding_models", source)
    job_id = response.headers["Location"].strip("/").split("/")[-1]
    payload = {"status": state, "check_level": "fast", "manifest_sha256": "a" * 64,
               "message": "private-provider-message"}
    monkeypatch.setattr(service_jobs.subprocess, "Popen", lambda *a, **kw: SimpleNamespace(
        stdout=[json.dumps(payload)], pid=0, returncode=exit_code, wait=lambda: None))
    service_jobs._run_job(job_id, ROOT)
    record = service_jobs.get_service_job(job_id)
    assert record.status == expected and record.exit_code == exit_code
    assert record.model_manifest_sha256 == ("a" * 64 if expected == "ok" else "")
    client = Client()
    detail = client.get(f"/daten/jobs/{job_id}/status/").json()
    recent = client.get("/daten/jobs/status/").json()["recent"]
    history = client.get("/daten/model-jobs/status/").json()["history"]["entries"][0]["last_finished"]
    assert detail["job"] == next(item for item in recent if item["job_id"] == job_id)
    assert history == detail["model_job_evidence"]
    assert history["status"] == expected
    assert history["result"] != "bereit" or expected == "ok"
    assert "private-provider-message" not in json.dumps(detail) + json.dumps(history)


@pytest.mark.parametrize("action", ACTIONS)
def test_successful_worker_discards_extra_fields_across_public_surfaces(verified, monkeypatch, action):
    source, _, _ = verified
    response = post_job(Client(enforce_csrf_checks=True), action, source)
    job_id = response.headers["Location"].strip("/").split("/")[-1]
    record = service_jobs.get_service_job(job_id)
    secret = "successful-child-secret"
    if action == "inspect_legacy_index":
        path, report = write_report(record)
        report["message"] = secret
        path.write_text(json.dumps(report))
        payload = report
    elif action == "apply_legacy_index":
        payload = {"collection": "ratsi_passages", "provenance": "legacy_verified",
                   "point_count": 1, "backfilled_points": 1}
    else:
        payload = {"status": "bereit", "check_level": "fast", "operation": "download",
                   "manifest_sha256": "a" * 64}
    payload["message"] = secret
    monkeypatch.setattr(service_jobs.subprocess, "Popen", lambda *a, **kw: SimpleNamespace(
        stdout=[secret, json.dumps(payload)], pid=0, returncode=0, wait=lambda: None))
    service_jobs._run_job(job_id, ROOT)
    assert record.status == "ok"
    client = Client()
    for url in (f"/daten/jobs/{job_id}/", f"/daten/jobs/{job_id}/status/",
                "/daten/jobs/status/", "/daten/model-jobs/status/"):
        response = client.get(url)
        assert response.status_code == 200 and secret not in response.content.decode()
    assert secret.encode() not in service_jobs.SERVICE_JOBS_DB.read_bytes()
