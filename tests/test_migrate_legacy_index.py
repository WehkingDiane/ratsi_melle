"""The migration CLI requires confirmation before opening Qdrant."""

import json

import pytest

from scripts import migrate_legacy_index
from scripts.migrate_legacy_index import main
from src.qdrant_connection import QdrantConnection, QdrantServerUnavailableError


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
    selected.mkdir()
    (selected / "meta.json").write_text('{"collections":{},"aliases":{}}', encoding="utf-8")
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


@pytest.mark.parametrize("action", ["inspect", "apply"])
def test_missing_local_store_does_not_open_or_create_qdrant(tmp_path, monkeypatch, capsys, action):
    monkeypatch.setenv("RATSI_QDRANT_MODE", "local")
    monkeypatch.delenv("RATSI_QDRANT_URL", raising=False)
    selected = tmp_path / "missing"
    monkeypatch.setattr(QdrantConnection, "create_client",
                        lambda self: pytest.fail("Missing store must not be opened"))
    args = [f"--{action}", "--collection", "ratsi_passages", "--report",
            str(tmp_path / "report.json"), "--qdrant-dir", str(selected)]
    if action == "apply":
        args.extend(["--confirm-collection", "ratsi_passages"])
    assert main(args) == 1
    assert '"abort_code": "store_missing"' in capsys.readouterr().err
    assert not selected.exists()
    if action == "inspect":
        assert json.loads((tmp_path / "report.json").read_text())["abort_code"] == "store_missing"


@pytest.mark.parametrize("contents", [None, "{}", "garbage", '{"collections":{},"aliases":{}}'])
def test_uninitialized_local_directory_is_not_opened(tmp_path, monkeypatch, capsys, contents):
    monkeypatch.setenv("RATSI_QDRANT_MODE", "local")
    monkeypatch.delenv("RATSI_QDRANT_URL", raising=False)
    selected = tmp_path / "unrelated"
    selected.mkdir()
    if contents is not None:
        (selected / "meta.json").write_text(contents, encoding="utf-8")
    before = {p.name: p.read_bytes() for p in selected.iterdir()}
    opened = []

    def open_client(self):
        opened.append(True)
        if contents == '{"collections":{},"aliases":{}}':
            class Client:
                def close(self):
                    pass
            return Client()
        pytest.fail("Uninitialized directory must not be opened")

    monkeypatch.setattr(QdrantConnection, "create_client", open_client)
    monkeypatch.setattr(migrate_legacy_index, "inspect_and_write_report",
                        lambda *a, **k: {"result": "aborted", "abort_code": "collection_missing"}
                        if k.get("abort_code") is None else {"result": "aborted", "abort_code": k["abort_code"]})
    result = main(["--inspect", "--collection", "ratsi_passages", "--report",
                   str(tmp_path / "report.json"), "--qdrant-dir", str(selected)])
    assert result == 1
    assert opened == ([True] if contents == '{"collections":{},"aliases":{}}' else [])
    assert {p.name: p.read_bytes() for p in selected.iterdir()} == before
    assert "Traceback" not in capsys.readouterr().err


@pytest.mark.parametrize("action", ["inspect", "apply"])
def test_server_unavailable_returns_structured_abort(tmp_path, monkeypatch, capsys, action):
    monkeypatch.setenv("RATSI_QDRANT_URL", "http://test.invalid:6333")
    monkeypatch.setattr(QdrantConnection, "create_client",
                        lambda self: (_ for _ in ()).throw(
                            QdrantServerUnavailableError("Qdrant-Server nicht erreichbar.")))
    report = tmp_path / "report.json"
    args = [f"--{action}", "--collection", "ratsi_passages", "--report", str(report)]
    if action == "apply":
        args.extend(["--confirm-collection", "ratsi_passages"])
    assert main(args) == 1
    output = capsys.readouterr()
    assert json.loads(output.err) == {"result": "aborted", "abort_code": "qdrant_unavailable"}
    assert "Traceback" not in output.err
    if action == "inspect":
        assert json.loads(report.read_text())["abort_code"] == "qdrant_unavailable"
    else:
        assert not report.exists()
