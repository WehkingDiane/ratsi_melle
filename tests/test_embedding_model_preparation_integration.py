"""Real CLI subprocess workflows with a tiny fake Hub and blocked networking."""

import json

import pytest

from embedding_preparation_support import run_cli
from src.config.embedding_model_status import load_and_validate_model_inventory


pytestmark = pytest.mark.integration


def test_subprocess_download_deep_check_and_offline_reuse(tmp_path):
    result = run_cli(tmp_path, ["--download", "--json", "--log-level", "DEBUG"])
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "bereit"
    assert payload["reused"] is False
    assert not result.stderr
    manifest = load_and_validate_model_inventory(tmp_path / "models", deep=True)
    assert manifest.manifest_sha256 == payload["manifest_sha256"]
    calls = (tmp_path / "hub-calls.jsonl").read_bytes()
    assert len(calls.splitlines()) == 2
    manifest_before = (tmp_path / "models/manifest.json").read_bytes()
    (tmp_path / "keyring-call").unlink()
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns)
              for path in (tmp_path / "models").rglob("*") if path.is_file()}

    check = run_cli(tmp_path, ["--check", "--deep", "--json"], forbid_hub=True)
    assert check.returncode == 0, check.stderr
    assert json.loads(check.stdout)["check_level"] == "deep"
    reuse = run_cli(tmp_path, ["--download", "--json"], forbid_hub=True)
    assert reuse.returncode == 0, reuse.stderr
    assert json.loads(reuse.stdout)["reused"] is True
    assert json.loads(reuse.stdout)["manifest_sha256"] == manifest.manifest_sha256
    assert not (tmp_path / "keyring-call").exists()
    assert (tmp_path / "hub-calls.jsonl").read_bytes() == calls
    assert (tmp_path / "models/manifest.json").read_bytes() == manifest_before
    assert before == {path: (path.read_bytes(), path.stat().st_mtime_ns)
                      for path in (tmp_path / "models").rglob("*") if path.is_file()}
    assert "hf_subprocess_secret" not in result.stdout + result.stderr + (
        tmp_path / "logs/embedding_model_preparation.log"
    ).read_text()


def test_subprocess_provider_failure_preserves_active_inventory_and_resumes(tmp_path):
    initial = run_cli(tmp_path, ["--download", "--json"])
    assert initial.returncode == 0, initial.stderr
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns)
              for path in (tmp_path / "models/inventories").rglob("*") if path.is_file()}
    active = (tmp_path / "models/manifest.json").read_bytes()

    failed = run_cli(tmp_path, ["--download", "--json"], failure=True, different_versions=True)
    assert failed.returncode == 1
    assert json.loads(failed.stdout)["error_code"] == "network_unavailable"
    assert not failed.stderr
    assert (tmp_path / "models/manifest.json").read_bytes() == active
    assert all((path.read_bytes(), path.stat().st_mtime_ns) == state for path, state in before.items())
    log = (tmp_path / "logs/embedding_model_preparation.log").read_text()
    assert "hf_subprocess_secret" not in failed.stdout + failed.stderr + log
    assert "Traceback" not in failed.stdout + failed.stderr
    load_and_validate_model_inventory(tmp_path / "models", deep=True)

    resumed = run_cli(tmp_path, ["--download", "--json"], different_versions=True)
    assert resumed.returncode == 0, resumed.stderr
    assert json.loads(resumed.stdout)["status"] == "bereit"
    # Two initial snapshots, two in the failed attempt, only BM25 on resume.
    assert len((tmp_path / "hub-calls.jsonl").read_text().splitlines()) == 5
    load_and_validate_model_inventory(tmp_path / "models", deep=True)
