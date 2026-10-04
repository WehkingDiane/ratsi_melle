"""Opt-in real Hub tests, never collected through a provider import."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from embedding_preparation_support import isolated_environment, run_cli
from src.config.embedding_model_status import load_and_validate_model_inventory
from src.config.embedding_models import BM25_MODEL, HARRIER_MODEL, HARRIER_TOKENIZER


pytestmark = [pytest.mark.live, pytest.mark.integration]


@pytest.mark.skipif(
    os.environ.get("RATSI_EMBEDDING_LIVE_SMOKE") != "1",
    reason="Set RATSI_EMBEDDING_LIVE_SMOKE=1 for real Hub metadata/small config downloads",
)
def test_live_pinned_revisions_and_small_config_downloads(tmp_path):
    code = """
import json
import os
from pathlib import Path
from huggingface_hub import HfApi, hf_hub_download
from src.config.embedding_models import BM25_MODEL, HARRIER_MODEL, HARRIER_TOKENIZER
groups = {}
for definition in (HARRIER_MODEL, HARRIER_TOKENIZER, BM25_MODEL):
    identity = (definition.model_id, definition.revision)
    groups.setdefault(identity, set()).update(definition.required_artifacts)
api = HfApi(token=False)
results = []
for (model_id, revision), required in groups.items():
    info = api.model_info(model_id, revision=revision, token=False, timeout=30)
    assert info.sha == revision
    files = {entry.rfilename for entry in info.siblings}
    assert required <= files, sorted(required - files)
    if model_id == HARRIER_MODEL.model_id:
        assert not (set(HARRIER_MODEL.expected_absent_artifacts) & files)
    local_dir = Path(os.environ['RATSI_MODELS_DIR']) / model_id / revision
    path = hf_hub_download(
        repo_id=model_id, filename='config.json', revision=revision,
        local_dir=local_dir, token=False, force_download=True,
    )
    assert Path(path).resolve().is_relative_to(local_dir.resolve())
    assert isinstance(json.loads(Path(path).read_text(encoding='utf-8')), dict)
    results.append({'model_id': model_id, 'revision': info.sha})
print(json.dumps(results))
"""
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=tmp_path,
        env=isolated_environment(tmp_path, fake_hub=False),
        text=True, capture_output=True, timeout=300,
    )
    assert result.returncode == 0, result.stderr
    assert {(item["model_id"], item["revision"]) for item in json.loads(result.stdout)} == {
        (definition.model_id, definition.revision)
        for definition in (HARRIER_MODEL, HARRIER_TOKENIZER, BM25_MODEL)
    }
    assert not (tmp_path / "models/manifest.json").exists()  # Smoke is not readiness.
    assert not list((tmp_path / "models").rglob("*.safetensors"))


@pytest.mark.skipif(
    os.environ.get("RATSI_EMBEDDING_LIVE_DOWNLOAD") != "1",
    reason="Set RATSI_EMBEDDING_LIVE_DOWNLOAD=1 for the full real model download (GB-scale)",
)
def test_live_full_download_deep_check_and_reuse(tmp_path):
    result = run_cli(tmp_path, ["--download", "--json"], fake_hub=False, timeout=3600)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "bereit"
    assert payload["reused"] is False
    assert Path(payload["inventory_dir"]).resolve().is_relative_to((tmp_path / "models").resolve())
    manifest = load_and_validate_model_inventory(tmp_path / "models", deep=True)
    assert payload["manifest_sha256"] == manifest.manifest_sha256
    before = (tmp_path / "models/manifest.json").read_bytes()
    (tmp_path / "keyring-call").unlink()
    # Reuse/check must work with blocked networking and a forbidden Hub import.
    check = run_cli(tmp_path, ["--check", "--deep", "--json"], forbid_hub=True, timeout=300)
    assert check.returncode == 0, check.stderr
    assert json.loads(check.stdout)["status"] == "bereit"
    reuse = run_cli(tmp_path, ["--download", "--json"], forbid_hub=True, timeout=300)
    assert reuse.returncode == 0, reuse.stderr
    assert json.loads(reuse.stdout)["reused"] is True
    assert json.loads(reuse.stdout)["manifest_sha256"] == payload["manifest_sha256"]
    assert not (tmp_path / "keyring-call").exists()
    assert (tmp_path / "models/manifest.json").read_bytes() == before
