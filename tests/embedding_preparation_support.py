"""Isolated subprocess helpers for fake-Hub and explicitly enabled live tests."""

import os
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = REPO_ROOT / "scripts/prepare_embedding_models.py"
FAKE_HUB_PATH = REPO_ROOT / "tests/fixtures/embedding_hub"

# Do not read the developer's OS keyring, even in explicitly enabled live tests.
ANONYMOUS_KEYRING = """
import os
from pathlib import Path
import sys
from types import SimpleNamespace
def anonymous_keyring(*args):
    Path(os.environ['RATSI_TEST_KEYRING_CALL']).touch()
    return None
sys.modules['keyring'] = SimpleNamespace(get_password=anonymous_keyring)
"""


def isolated_environment(tmp_path: Path, *, fake_hub: bool) -> dict[str, str]:
    """Isolate model/log/Hub paths and remove inherited authentication."""

    env = os.environ.copy()
    for name in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HF_HUB_OFFLINE"):
        env.pop(name, None)
    env.update({
        "RATSI_MODELS_DIR": str(tmp_path / "models"),
        "RATSI_LOG_DIR": str(tmp_path / "logs"),
        "RATSI_TEST_KEYRING_CALL": str(tmp_path / "keyring-call"),
        "HF_HOME": str(tmp_path / "hf-home"),
        "HF_HUB_CACHE": str(tmp_path / "hf-home/hub"),
        "HF_XET_CACHE": str(tmp_path / "hf-home/xet"),
        "HF_TOKEN_PATH": str(tmp_path / "hf-home/token"),
        "HF_ENDPOINT": "https://huggingface.co",
        "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
        "HF_HUB_DISABLE_PROGRESS_BARS": "1",
        "RATSI_TEST_HUB_CALLS": str(tmp_path / "hub-calls.jsonl"),
        "PYTHONPATH": os.pathsep.join(str(path) for path in (
            (FAKE_HUB_PATH, REPO_ROOT) if fake_hub else (REPO_ROOT,)
        )),
    })
    return env


def run_cli(
    tmp_path: Path, arguments: list[str], *, fake_hub: bool = True,
    forbid_hub: bool = False, failure: bool = False,
    different_versions: bool = False, timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    """Run the real CLI from a foreign working directory with isolated state."""

    env = isolated_environment(tmp_path, fake_hub=fake_hub)
    env["RATSI_TEST_FORBID_HUB"] = "1" if forbid_hub else "0"
    env["RATSI_TEST_DOWNLOAD_FAILURE"] = "1" if failure else "0"
    bootstrap = ANONYMOUS_KEYRING
    if fake_hub:
        bootstrap += """
import socket
import urllib.request
def reject_network(*args, **kwargs):
    raise AssertionError('Fake-Hub tests must not access the network')
socket.socket.connect = reject_network
socket.create_connection = reject_network
urllib.request.urlopen = reject_network
"""
    if different_versions:
        bootstrap += """
from src import embedding_model_preparation as preparation
original_version = preparation.version
preparation.version = lambda name: original_version(name) + '-changed-test'
"""
    bootstrap += f"\nimport runpy\nrunpy.run_path({str(CLI_PATH)!r}, run_name='__main__')\n"
    return subprocess.run(
        [sys.executable, "-c", bootstrap, *arguments], cwd=tmp_path,
        env=env, capture_output=True, text=True, timeout=timeout,
    )
