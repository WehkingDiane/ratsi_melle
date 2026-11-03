"""Compatibility evidence must report mismatches without modifying reference points."""

from dataclasses import replace
from copy import deepcopy
from contextlib import nullcontext
import json

import pytest

from src.config.index_compatibility import IndexCompatibility
from src.config.embedding_models import HARRIER_MODEL, HARRIER_TOKENIZER, BM25_MODEL
from src.indexing.vector_compatibility_probe import probe, vector_metrics, _ranking


@pytest.fixture
def contract():
    return IndexCompatibility(
        dense_model_id=HARRIER_MODEL.model_id, dense_revision=HARRIER_MODEL.revision,
        tokenizer_model_id=HARRIER_TOKENIZER.model_id, tokenizer_revision=HARRIER_TOKENIZER.revision,
        sparse_model_id=BM25_MODEL.model_id, sparse_revision=BM25_MODEL.revision,
        manifest_sha256="a"*64, vector_dimension=3, pipeline_version="passages-1")


def vectors(axis=0, weight=1.0):
    return {"dense_vector": [1.0 if i == axis else 0.0 for i in range(3)],
            "sparse_vector": {"indices": [axis], "values": [weight]}}


class Encoder:
    def __init__(self, vector):
        self.vector = vector

    def encode_documents(self, texts):
        return [deepcopy(self.vector) for _ in texts]


def test_metrics_detect_dense_and_sparse_changes():
    candidate = vectors()
    stored = {"harrier": candidate["dense_vector"], "bm25": candidate["sparse_vector"]}
    assert vector_metrics(stored, candidate, 3)["strict_match"]
    changed = vector_metrics(stored, vectors(1), 3)
    assert changed["dense_cosine"] == 0
    assert changed["sparse_indices_equal"] is False
    assert changed["strict_match"] is False
    assert vector_metrics(stored, vectors(weight=2), 3)["mismatch"] == "sparse_values_mismatch"


def test_sample_ranking_detects_reversed_dense_and_sparse_matches():
    def stored(axis):
        return {"harrier": vectors(axis)["dense_vector"], "bm25": vectors(axis)["sparse_vector"]}
    assert _ranking([1, 2], [stored(0), stored(1)], vectors(), 1) == [1]
    assert _ranking([1, 2], [stored(1), stored(0)], vectors(), 1) == [2]


@pytest.mark.parametrize("dense", [[float("nan"), 0, 0], [0, 0, 0], [1]])
def test_invalid_vectors_are_not_compatibility_evidence(dense):
    candidate = vectors()
    candidate["dense_vector"] = dense
    with pytest.raises(ValueError):
        vector_metrics({"harrier": [1, 0, 0], "bm25": vectors()["sparse_vector"]}, candidate, 3)


@pytest.fixture
def reference(contract):
    from qdrant_client import QdrantClient, models
    client = QdrantClient(":memory:")
    client.create_collection("ratsi_passages",
        vectors_config={"harrier": models.VectorParams(size=3, distance=models.Distance.COSINE)},
        sparse_vectors_config={"bm25": models.SparseVectorParams()})
    client.upsert("ratsi_passages", [models.PointStruct(
        id=i, vector={"harrier": vectors()["dense_vector"],
                      "bm25": models.SparseVector(**vectors()["sparse_vector"])},
        payload={"text": f"Straßenbau {i}", "committed": True,
                 "index_compatibility": contract.as_dict()}) for i in range(1, 12)])
    yield client
    client.close()


@pytest.mark.integration
@pytest.mark.parametrize("axis,expected", [(0, "sample_matches"), (1, "differences_found")])
def test_probe_reads_only_and_records_new_manifest(reference, contract, axis, expected, monkeypatch):
    before = reference.scroll("ratsi_passages", limit=100, with_vectors=True)
    for method in ("upsert", "set_payload", "delete", "create_collection", "delete_collection"):
        monkeypatch.setattr(reference, method, lambda *a, **k: pytest.fail("Probe attempted a write"))
    result = probe(reference, contract, replace(contract, manifest_sha256="b"*64),
                   Encoder(vectors(axis)), ["Straßenbau"], lambda _: vectors(), sample_size=5)
    assert result["result"] == expected
    assert result["migration_authorized"] is False
    assert len(result["sample"]) == 5
    assert set(result["contract_differences"]) == {"manifest_sha256"}
    assert result["queries"]
    assert before == reference.scroll("ratsi_passages", limit=100, with_vectors=True)
    repeated = probe(reference, contract, contract, Encoder(vectors()), [], lambda _: vectors(), sample_size=5)
    assert [r["point_id"] for r in result["sample"]] == [r["point_id"] for r in repeated["sample"]]


@pytest.mark.integration
def test_model_change_cannot_be_reported_as_library_upgrade(reference, contract):
    with pytest.raises(ValueError, match="identical model"):
        probe(reference, contract, replace(contract, dense_revision="c"*40),
              Encoder(vectors()), [], lambda _: vectors())


@pytest.mark.integration
def test_concurrent_vector_change_aborts(reference, contract):
    from qdrant_client import models

    class MutatingEncoder(Encoder):
        def encode_documents(self, texts):
            reference.update_vectors("ratsi_passages", [models.PointVectors(
                id=i, vector={"harrier": [0.0, 1.0, 0.0]}) for i in range(1, 12)])
            return super().encode_documents(texts)

    with pytest.raises(ValueError, match="Sample changed"):
        probe(reference, contract, contract, MutatingEncoder(vectors()), [], lambda _: vectors())


@pytest.mark.integration
def test_cli_aborted_model_check_writes_report_and_restores_environment(tmp_path, monkeypatch):
    from scripts import probe_bi_vector_compatibility as cli
    monkeypatch.setenv("RATSI_MODELS_DIR", "original-models")
    monkeypatch.setattr(cli, "model_operation_lock", nullcontext)
    def unavailable(*args, **kwargs):
        raise ValueError("Candidate inventory unavailable")
    monkeypatch.setattr(cli, "current_index_compatibility", unavailable)
    report = tmp_path / "report.json"
    args = ["--models-dir", str(tmp_path / "candidate"), "--report", str(report)]
    assert cli.main(args) == 2
    payload = json.loads(report.read_text())
    assert payload["result"] == "aborted"
    assert payload["migration_authorized"] is False
    assert payload["error"] == "Candidate inventory unavailable"
    import os
    assert os.environ["RATSI_MODELS_DIR"] == "original-models"
    before = report.read_bytes()
    with pytest.raises(SystemExit):
        cli.main(args)
    assert report.read_bytes() == before
