"""Opt-in acceptance using real prepared models and an isolated local index."""

import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODELS = os.environ.get("RATSI_EMBEDDING_ACCEPTANCE_MODELS")
pytestmark = [pytest.mark.live, pytest.mark.integration]


OFFLINE_ACCEPTANCE = r'''
import contextlib
import io
import json
import os
from pathlib import Path
import socket
import sys

root = Path(sys.argv[1])
sys.path.insert(0, str(Path.cwd() / 'web'))
attempts = []
def forbid_network(*args, **kwargs):
    attempts.append('socket')
    raise ConnectionError('Offline acceptance forbids network access')
socket.socket.connect = forbid_network
socket.socket.connect_ex = forbid_network
socket.create_connection = forbid_network

import huggingface_hub as hub
original_download = hub.snapshot_download
original_file_download = hub.hf_hub_download
offline_lookups = []
def forbid_hub(*args, **kwargs):
    attempts.append('hub')
    raise AssertionError('Offline consumer attempted a Hub lookup')
def local_file_lookup(*args, **kwargs):
    if kwargs.get('local_files_only') is not True:
        return forbid_hub(*args, **kwargs)
    offline_lookups.append(kwargs.get('filename'))
    return original_file_download(*args, **kwargs)
hub.snapshot_download = forbid_hub
hub.hf_hub_download = local_file_lookup

import torch
torch.set_num_threads(4)
from src.config.embedding_model_status import load_and_validate_model_inventory
from src.config.index_compatibility import current_index_compatibility
from src.qdrant_connection import QdrantConnection
from scripts.prepare_embedding_models import main as prepare
from scripts.build_vector_index import main as build
from search import services

models = Path(os.environ['RATSI_MODELS_DIR'])
manifest = load_and_validate_model_inventory(models, deep=True)
model_files = {path: (path.stat().st_size, path.stat().st_mtime_ns)
               for path in models.rglob('*') if path.is_file()}
assert prepare(['--check', '--deep', '--json']) == 0
assert prepare(['--download', '--json']) == 0  # Reuse must also stay offline.
arguments = ['--db', str(root / 'source.sqlite'), '--qdrant-dir', str(root / 'qdrant'),
             '--no-ocr', '--batch-size', '1']
build(arguments)
connection = QdrantConnection.from_env(root / 'qdrant')
marker_path = connection.release_path('ratsi_passages')
marker_bytes = marker_path.read_bytes()
marker = json.loads(marker_bytes)
assert marker['ready'] is True
assert marker['compatibility'] == current_index_compatibility().as_dict()

services.QDRANT_DIR = root / 'qdrant'
services.LOCAL_INDEX_DB = root / 'source.sqlite'
result = services.search_semantic_documents('Gesamtfinanzhaushalt 2026 2027', limit=5)
assert not result['error'], result['error']
assert result['results'], result
assert any(hit['sqlite_document_id'] == 2 for hit in result['results']), result
assert any('finanz' in hit.get('text', '').lower() or 'finanz' in hit.get('snippet', '').lower()
           for hit in result['results']), result

# Evaluation uses the same local models and validates a real PDF quotation.
benchmark = {'queries': [{'id': 'offline-acceptance',
             'query': 'Gesamtfinanzhaushalt 2026 2027',
             'relevant': [{'url': 'https://example.invalid/budget_tables.pdf',
                           'page': 2, 'evidence': 'Gesamtfinanzhaushalt'}]}]}
(root / 'benchmark.json').write_text(json.dumps(benchmark), encoding='utf-8')
from scripts.evaluate_search import main as evaluate
evaluate(['--benchmark', str(root / 'benchmark.json'), '--db', str(root / 'source.sqlite'),
          '--qdrant-dir', str(root / 'qdrant'), '--collection', 'ratsi_passages',
          '--k', '5', '--output', str(root / 'evaluation.json')])
evaluation = json.loads((root / 'evaluation.json').read_text(encoding='utf-8'))
assert evaluation['query_count'] == 1 and evaluation['metrics']['hit_at_k'] == 1
assert not attempts, attempts

# A real contract mismatch rejects a rebuild and search without changing points.
from src.analysis.vector_store import DocumentVectorStore
store = DocumentVectorStore(root / 'qdrant', collection_name='ratsi_passages')
points_before = store.get_point_payloads()
store.close()
marker['compatibility']['pipeline_version'] = 'acceptance-incompatible'
marker_path.write_text(json.dumps(marker), encoding='utf-8')
changed_marker = marker_path.read_bytes()
try:
    build(arguments)
except SystemExit as error:
    assert error.code == 1
else:
    raise AssertionError('Incompatible index accepted a rebuild')
assert marker_path.read_bytes() == changed_marker
rejected = services.search_semantic_documents('Haushalt')
assert rejected['error'] and not rejected['results'], rejected
store = DocumentVectorStore(root / 'qdrant', collection_name='ratsi_passages')
assert store.get_point_payloads() == points_before
store.close()
marker_path.write_bytes(marker_bytes)

# Missing models must produce a short CLI/web error, even after encoder caching.
os.environ['RATSI_MODELS_DIR'] = str(root / 'missing-models')
missing = services.search_semantic_documents('Haushalt')
assert missing['model_status_unavailable'] and not missing['results'], missing
assert 'prepare_embedding_models.py --download' in missing['error']
assert prepare(['--check', '--json']) == 1
assert not attempts, attempts

# The real SDK cannot reach its source; no active inventory may be published.
hub.snapshot_download = original_download
os.environ.pop('HF_HUB_OFFLINE', None)
os.environ['HF_ENDPOINT'] = 'http://127.0.0.1:9'
import huggingface_hub.constants
huggingface_hub.constants.ENDPOINT = 'http://127.0.0.1:9'
huggingface_hub.constants.HF_HUB_OFFLINE = False
failure_output = io.StringIO()
with contextlib.redirect_stdout(failure_output):
    code = prepare(['--download', '--json'])
failure = json.loads(failure_output.getvalue())
assert code == 1 and failure['error_code'] == 'network_unavailable', failure
assert not (root / 'missing-models/manifest.json').exists()
assert attempts and set(attempts) == {'socket'}, attempts
os.environ['RATSI_MODELS_DIR'] = str(models)
assert load_and_validate_model_inventory(models, deep=True) == manifest
assert all((path.stat().st_size, path.stat().st_mtime_ns) == previous
           for path, previous in model_files.items())
report = {'manifest_sha256': manifest.manifest_sha256,
          'points': len(points_before), 'search_hits': len(result['results']),
          'device': services._get_semantic_resources()[0]._get_model().device.type,
          'offline_consumer_network_attempts': 0,
          'offline_optional_file_lookups': len(offline_lookups),
          'evaluation_queries': evaluation['query_count'],
          'missing_model': True, 'incompatible_index': True,
          'unreachable_source': failure['error_code']}
(root / 'acceptance.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report), flush=True)
'''


@pytest.mark.skipif(not MODELS, reason="Set RATSI_EMBEDDING_ACCEPTANCE_MODELS to a prepared inventory")
def test_real_prepared_models_build_and_search_offline(tmp_path):
    """Build real PDF passages and query them with every network call blocked."""

    models = Path(MODELS).resolve(strict=True)
    raw = tmp_path / "data/raw/2026/10/acceptance"
    raw.mkdir(parents=True)
    files = ("council_public_notice.pdf", "budget_tables.pdf")
    for name in files:
        shutil.copyfile(ROOT / "tests/fixtures/pdf" / name, raw / name)
    with sqlite3.connect(tmp_path / "source.sqlite") as db:
        db.execute("CREATE TABLE sessions (session_id TEXT, date TEXT, committee TEXT, session_path TEXT)")
        db.execute("INSERT INTO sessions VALUES (?, ?, ?, ?)",
                   ("acceptance", "2026-10-04", "Abnahme", str(raw)))
        db.execute("CREATE TABLE documents (id INTEGER, session_id TEXT, title TEXT, "
                   "document_type TEXT, agenda_item TEXT, url TEXT, local_path TEXT)")
        db.executemany("INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?)", [
            (number, "acceptance", name, "vorlage", str(number),
             f"https://example.invalid/{name}", name)
            for number, name in enumerate(files, start=1)
        ])
    env = {**os.environ, "RATSI_MODELS_DIR": str(models), "RATSI_QDRANT_MODE": "local",
           "RATSI_QDRANT_URL": "", "RATSI_LOG_DIR": str(tmp_path / "logs"),
           "HF_HOME": str(tmp_path / "empty-hf-home"), "HF_HUB_OFFLINE": "0",
           "HF_HUB_CACHE": str(tmp_path / "empty-hf-home/hub"),
           "HF_TOKEN_PATH": str(tmp_path / "empty-hf-home/token"),
           "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1", "TOKENIZERS_PARALLELISM": "false"}
    for name in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "TRANSFORMERS_OFFLINE"):
        env.pop(name, None)
    # A reusable prepared inventory never needs credentials. Avoid developer keyrings.
    bootstrap = "from types import SimpleNamespace\nimport sys\nsys.modules['keyring'] = SimpleNamespace(get_password=lambda *args: None)\n"
    result = subprocess.run([sys.executable, "-c", bootstrap + OFFLINE_ACCEPTANCE, str(tmp_path)],
                            cwd=ROOT, env=env, capture_output=True, text=True, timeout=900)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((tmp_path / "acceptance.json").read_text(encoding="utf-8"))
    assert report["points"] > 0 and report["offline_consumer_network_attempts"] == 0
    print(json.dumps(report))
