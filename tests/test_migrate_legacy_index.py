"""The migration CLI requires confirmation before opening Qdrant."""

import pytest

from scripts.migrate_legacy_index import main


def test_apply_requires_matching_collection_confirmation(monkeypatch, tmp_path):
    def unexpectedly_open(*args, **kwargs):
        raise AssertionError("Qdrant was opened before confirmation")

    monkeypatch.setattr("scripts.migrate_legacy_index.QdrantConnection.from_env", unexpectedly_open)
    for confirmation in ([], ["--confirm-collection", "ratsi_documents"]):
        with pytest.raises(SystemExit) as error:
            main(["--apply", "--collection", "ratsi_passages", "--report",
                  str(tmp_path / "report.json"), *confirmation])
        assert error.value.code == 2
