"""Test-only pinned Hub substitute, imported exclusively by subprocess tests."""

import json
import logging
import os
from pathlib import Path
import sys

if os.environ.get("RATSI_TEST_FORBID_HUB") == "1":
    raise AssertionError("Offline checks/reuse must not import the Hub")


def snapshot_download(**kwargs):
    """Write tiny deterministic artifacts, never using the real provider."""

    from src.config.embedding_models import BM25_MODEL, HARRIER_MODEL, HARRIER_TOKENIZER

    expected = {}
    for definition in (HARRIER_MODEL, HARRIER_TOKENIZER, BM25_MODEL):
        identity = (definition.model_id, definition.revision)
        expected.setdefault(identity, set()).update(definition.required_artifacts)
    assert set(kwargs) == {
        "repo_id", "repo_type", "revision", "local_dir", "allow_patterns",
        "token", "local_files_only", "force_download",
    }
    assert kwargs["token"] is False
    assert kwargs["repo_type"] == "model"
    assert kwargs["local_files_only"] is False
    assert kwargs["force_download"] is True
    identity = (kwargs["repo_id"], kwargs["revision"])
    assert set(kwargs["allow_patterns"]) == expected[identity]
    with Path(os.environ["RATSI_TEST_HUB_CALLS"]).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"model_id": identity[0], "revision": identity[1]}) + "\n")
    print("Authorization: Bearer hf_subprocess_secret")
    print("hf_subprocess_secret", file=sys.stderr)
    logging.getLogger("huggingface_hub").error("hf_subprocess_secret")
    if os.environ.get("RATSI_TEST_DOWNLOAD_FAILURE") == "1" and identity[0] == BM25_MODEL.model_id:
        raise ConnectionError("https://user:hf_subprocess_secret@provider.test")
    root = Path(kwargs["local_dir"])
    for relative_path in kwargs["allow_patterns"]:
        artifact = root / relative_path
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_bytes(f"{identity}/{relative_path}".encode())
    return str(root)
