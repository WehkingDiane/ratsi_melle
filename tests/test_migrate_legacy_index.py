"""The migration CLI requires confirmation before opening Qdrant."""

import pytest

from scripts import migrate_legacy_index
from scripts.migrate_legacy_index import main
from src.qdrant_connection import QdrantConnection


def test_apply_requires_matching_collection_confirmation(monkeypatch, tmp_path):
    def unexpectedly_open(*args, **kwargs):
        raise AssertionError("Qdrant was opened before confirmation")

    monkeypatch.setattr("scripts.migrate_legacy_index.QdrantConnection.from_env", unexpectedly_open)
    for confirmation in ([], ["--confirm-collection", "ratsi_documents"]):
        with pytest.raises(SystemExit) as error:
            main(["--apply", "--collection", "ratsi_passages", "--report",
                  str(tmp_path / "report.json"), *confirmation])
        assert error.value.code == 2


@pytest.mark.parametrize("action", ["inspect", "apply"])
def test_custom_local_qdrant_path_is_used_for_both_migration_actions(
    tmp_path, monkeypatch, action,
):
    monkeypatch.setenv("RATSI_QDRANT_MODE", "local")
    monkeypatch.delenv("RATSI_QDRANT_URL", raising=False)
    selected = tmp_path / "custom_store"
    seen = []

    class Client:
        def close(self):
            pass

    monkeypatch.setattr(QdrantConnection, "create_client", lambda self: Client())

    def inspect(connection, *_args):
        seen.append(connection.path)
        return {"result": "verified", "abort_code": None}

    def apply(connection, *_args, **_kwargs):
        seen.append(connection.path)
        return {"result": "released"}

    monkeypatch.setattr(migrate_legacy_index, "inspect_and_write_report", inspect)
    monkeypatch.setattr(migrate_legacy_index, "apply_verified_legacy_report", apply)
    args = [f"--{action}", "--collection", "ratsi_passages", "--report",
            str(tmp_path / "report.json"), "--qdrant-dir", str(selected)]
    if action == "apply":
        args.extend(["--confirm-collection", "ratsi_passages"])

    assert main(args) == 0
    assert seen == [selected]
