from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


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


def test_git_pre_commit_does_not_restrict_new_old_files(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    old_file = repo / "old" / "legacy.txt"
    old_file.parent.mkdir()
    old_file.write_text("legacy\n", encoding="utf-8")
    git(repo, "add", "old/legacy.txt")

    result = run_policy("git-pre-commit", cwd=repo)

    assert result.returncode == 0
    assert "old/" not in result.stderr


def test_git_pre_commit_allows_existing_old_file_changes(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    old_file = repo / "old" / "legacy.txt"
    old_file.parent.mkdir()
    old_file.write_text("legacy\n", encoding="utf-8")
    git(repo, "add", "old/legacy.txt")
    git(repo, "commit", "-m", "Archive legacy file")
    old_file.write_text("changed\n", encoding="utf-8")
    git(repo, "add", "old/legacy.txt")

    result = run_policy("git-pre-commit", cwd=repo)

    assert result.returncode == 0
    assert "old/" not in result.stderr


def test_git_pre_commit_allows_python_archive_move(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    git(repo, "config", "diff.renames", "false")
    (repo / "src").mkdir()
    (repo / "src" / "module.py").write_text("print('x')\n", encoding="utf-8")
    git(repo, "add", "src/module.py")
    git(repo, "commit", "-m", "Add module")
    archived = repo / "archive/src/module.py"
    archived.parent.mkdir(parents=True)
    shutil.copy2(repo / "src/module.py", archived)
    (repo / "src/module.py").unlink()
    git(repo, "add", "-u")

    result = run_policy("git-pre-commit", cwd=repo)

    assert result.returncode == 0
    assert "Python-Dateien" not in result.stderr


def test_git_pre_commit_blocks_python_archive_with_wrong_path(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "src").mkdir()
    (repo / "src" / "module.py").write_text("print('x')\n", encoding="utf-8")
    git(repo, "add", "src/module.py")
    git(repo, "commit", "-m", "Add module")
    archived = repo / "archive/src/renamed.py"
    archived.parent.mkdir(parents=True)
    shutil.copy2(repo / "src/module.py", archived)
    (repo / "src/module.py").unlink()
    git(repo, "add", "-u")

    result = run_policy("git-pre-commit", cwd=repo)

    assert result.returncode == 1
    assert "src/module.py" in result.stderr


def test_git_pre_commit_blocks_changed_archive_copy(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    source = repo / "module.py"
    source.write_text("print('original')\n", encoding="utf-8")
    git(repo, "add", "module.py")
    git(repo, "commit", "-m", "Add module")
    archived = repo / "archive/module.py"
    archived.parent.mkdir()
    archived.write_text("print('changed')\n", encoding="utf-8")
    source.unlink()
    git(repo, "add", "-u")

    result = run_policy("git-pre-commit", cwd=repo)

    assert result.returncode == 1
    assert "module.py" in result.stderr


def test_git_pre_commit_blocks_python_rename_to_non_python(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "module.py").write_text("print('x')\n", encoding="utf-8")
    git(repo, "add", "module.py")
    git(repo, "commit", "-m", "Add module")
    git(repo, "mv", "module.py", "module.txt")

    result = run_policy("git-pre-commit", cwd=repo)

    assert result.returncode == 1
    assert "module.py -> module.txt" in result.stderr


def test_git_pre_commit_allows_python_rename_from_old(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    old_file = repo / "old" / "legacy.py"
    old_file.parent.mkdir()
    old_file.write_text("print('legacy')\n", encoding="utf-8")
    git(repo, "add", "old/legacy.py")
    git(repo, "commit", "-m", "Archive legacy file")
    (repo / "src").mkdir()
    git(repo, "mv", "old/legacy.py", "src/legacy.py")

    result = run_policy("git-pre-commit", cwd=repo)

    assert result.returncode == 0


def test_git_pre_commit_blocks_edited_python_rename_without_archive(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    source = repo / "module.py"
    original = "".join(f"VALUE_{index} = {index}\n" for index in range(30))
    source.write_text(original, encoding="utf-8")
    git(repo, "add", "module.py")
    git(repo, "commit", "-m", "Add module")
    git(repo, "mv", "module.py", "renamed.py")
    (repo / "renamed.py").write_text(original.replace("VALUE_29 = 29", "VALUE_29 = 99"), encoding="utf-8")
    git(repo, "add", "renamed.py")

    assert git(repo, "diff", "--cached", "--name-status", "-M").stdout.startswith("R")
    result = run_policy("git-pre-commit", cwd=repo)

    assert result.returncode == 1
    assert "module.py -> renamed.py" in result.stderr


def test_git_pre_commit_allows_edited_python_rename_with_archive(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    source = repo / "module.py"
    original = "".join(f"VALUE_{index} = {index}\n" for index in range(30))
    source.write_text(original, encoding="utf-8")
    git(repo, "add", "module.py")
    git(repo, "commit", "-m", "Add module")
    archived = repo / "archive" / "module.py"
    archived.parent.mkdir()
    shutil.copy2(source, archived)
    git(repo, "mv", "module.py", "renamed.py")
    (repo / "renamed.py").write_text(
        original.replace("VALUE_29 = 29", "VALUE_29 = 99"),
        encoding="utf-8",
    )
    git(repo, "add", "renamed.py")

    assert git(repo, "diff", "--cached", "--name-status", "-M").stdout.startswith("R")
    result = run_policy("git-pre-commit", cwd=repo)

    assert result.returncode == 0


def test_git_pre_push_blocks_remote_main_ref_from_stdin(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    stdin = "refs/heads/codex/chore/hooks abc123 refs/heads/main def456\n"

    result = run_policy("git-pre-push", cwd=repo, stdin=stdin)

    assert result.returncode == 1
    assert "refs/heads/main" in result.stderr


def test_git_pre_push_allows_non_main_remote_ref_from_stdin(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    stdin = "refs/heads/codex/chore/hooks abc123 refs/heads/codex/chore/hooks def456\n"

    result = run_policy("git-pre-push", cwd=repo, stdin=stdin)

    assert result.returncode == 0
    assert result.stderr == ""


def test_git_pre_commit_ignores_explanatory_lists_in_project_tasks(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    project_tasks = repo / "docs" / "project_tasks.md"
    project_tasks.parent.mkdir()
    project_tasks.write_text(
        "## 3. Offene Aufgaben nach Architekturschicht\n\n"
        "### 3.4 Analyse und Artefakte\n"
        "#### Konkrete Aufgaben\n"
        "- Analyseziele verbindlich festlegen `[Mittel · GPT-6 Sol / Medium]`\n\n"
        "#### Kontext und Zielbild\n"
        "Das fachliche Zielbild umfasst drei Ebenen:\n\n"
        "- **Dokument:** Kernaussagen\n"
        "- **Sitzung:** Ergebnisse verdichten\n\n"
        "## 4. Abhängigkeiten und sinnvolle Reihenfolge\n",
        encoding="utf-8",
    )
    git(repo, "add", "docs/project_tasks.md")
    git(repo, "commit", "-m", "Add project task guidance")
    updated = project_tasks.read_text(encoding="utf-8").replace(
        "- **Dokument:** Kernaussagen", "- **Dokument:** Kernaussagen und Beschlussbezug"
    )
    project_tasks.write_text(updated, encoding="utf-8")
    git(repo, "add", "docs/project_tasks.md")

    result = run_policy("git-pre-commit", cwd=repo)

    assert result.returncode == 0
    assert "optionale Aufwand-/Modell-Empfehlung" not in result.stderr


def test_git_pre_commit_only_warns_about_missing_task_recommendations(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    project_tasks = repo / "docs" / "project_tasks.md"
    project_tasks.parent.mkdir()
    project_tasks.write_text(
        "## 3. Offene Aufgaben nach Architekturschicht\n\n"
        "### 3.1 Datenzufuhr\n"
        "#### Konkrete Aufgaben\n"
        "- Neue Aufgabe ohne Einstufung\n\n"
        "## 4. Abhängigkeiten und sinnvolle Reihenfolge\n",
        encoding="utf-8",
    )
    git(repo, "add", "docs/project_tasks.md")
    git(repo, "commit", "-m", "Add initial task list")
    updated = project_tasks.read_text(encoding="utf-8").replace(
        "## 4. Abhängigkeiten und sinnvolle Reihenfolge\n",
        "- Weitere neue Aufgabe ohne Einstufung\n\n"
        "## 4. Abhängigkeiten und sinnvolle Reihenfolge\n",
    )
    project_tasks.write_text(updated, encoding="utf-8")
    git(repo, "add", "docs/project_tasks.md")

    result = run_policy("git-pre-commit", cwd=repo)

    assert result.returncode == 0
    assert "optionale Aufwand-/Modell-Empfehlung" in result.stderr
    assert "blockiert keinen Commit" in result.stderr


def test_git_pre_commit_keeps_checking_after_description_paragraph(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    project_tasks = repo / "docs" / "project_tasks.md"
    project_tasks.parent.mkdir()
    project_tasks.write_text(
        "## 3. Offene Aufgaben nach Architekturschicht\n\n"
        "### 3.1 Datenzufuhr\n"
        "#### Konkrete Aufgaben\n"
        "- Bestehende Aufgabe `[Mittel · GPT-6 Sol / Medium]`\n"
        "  Ergänzende Beschreibung der Aufgabe über mehrere Zeilen.\n\n"
        "Analyseartefakte sollen Quellenangaben und Unsicherheit unterstützen.\n\n"
        "## 4. Abhängigkeiten und sinnvolle Reihenfolge\n",
        encoding="utf-8",
    )
    git(repo, "add", "docs/project_tasks.md")
    git(repo, "commit", "-m", "Add described project task")
    updated = project_tasks.read_text(encoding="utf-8").replace(
        "## 4. Abhängigkeiten und sinnvolle Reihenfolge\n",
        "- Neue Aufgabe nach Fortsetzung ohne Einstufung\n"
        "## 4. Abhängigkeiten und sinnvolle Reihenfolge\n",
    )
    project_tasks.write_text(updated, encoding="utf-8")
    git(repo, "add", "docs/project_tasks.md")

    result = run_policy("git-pre-commit", cwd=repo)

    assert result.returncode == 0
    assert "optionale Aufwand-/Modell-Empfehlung" in result.stderr


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
