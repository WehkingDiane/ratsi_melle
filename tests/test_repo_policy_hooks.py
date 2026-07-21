from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "scripts" / "hooks" / "repo_policy.py"


def run_policy(mode: str, *, cwd: Path, stdin: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(POLICY), mode],
        cwd=str(cwd),
        input=stdin,
        text=True,
        capture_output=True,
        check=False,
    )


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )


def init_repo(tmp_path: Path, branch: str = "codex/chore/hooks") -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", branch)
    git(repo, "config", "user.email", "test@example.invalid")
    git(repo, "config", "user.name", "Test User")
    (repo / "README.md").write_text("# Test\n", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "Initial commit")
    return repo


def test_git_pre_commit_blocks_main_branch(tmp_path: Path) -> None:
    repo = init_repo(tmp_path, branch="main")
    (repo / "README.md").write_text("# Test\nchanged\n", encoding="utf-8")
    git(repo, "add", "README.md")

    result = run_policy("git-pre-commit", cwd=repo)

    assert result.returncode == 1
    assert "main" in result.stderr


def test_git_pre_commit_blocks_python_deletion(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "module.py").write_text("print('x')\n", encoding="utf-8")
    git(repo, "add", "module.py")
    git(repo, "commit", "-m", "Add module")
    (repo / "module.py").unlink()
    git(repo, "add", "module.py")

    result = run_policy("git-pre-commit", cwd=repo)

    assert result.returncode == 1
    assert "Python-Dateien" in result.stderr


def test_git_pre_commit_warns_about_new_old_files(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    old_file = repo / "old" / "legacy.txt"
    old_file.parent.mkdir()
    old_file.write_text("legacy\n", encoding="utf-8")
    git(repo, "add", "old/legacy.txt")

    result = run_policy("git-pre-commit", cwd=repo)

    assert result.returncode == 0
    assert "Neue Dateien unter old/" in result.stderr


def test_git_pre_commit_blocks_existing_old_file_changes(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    old_file = repo / "old" / "legacy.txt"
    old_file.parent.mkdir()
    old_file.write_text("legacy\n", encoding="utf-8")
    git(repo, "add", "old/legacy.txt")
    git(repo, "commit", "-m", "Archive legacy file")
    old_file.write_text("changed\n", encoding="utf-8")
    git(repo, "add", "old/legacy.txt")

    result = run_policy("git-pre-commit", cwd=repo)

    assert result.returncode == 1
    assert "Bestehende Dateien unter old/" in result.stderr


def test_codex_pre_tool_use_warns_about_destructive_python_delete(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    payload = {
        "cwd": str(repo),
        "tool_input": {"cmd": "rm src/example.py"},
    }

    result = run_policy("codex-pre-tool-use", cwd=repo, stdin=json.dumps(payload))

    assert result.returncode == 0
    assert "systemMessage" in result.stdout
    assert "Python-Dateien" in result.stdout
