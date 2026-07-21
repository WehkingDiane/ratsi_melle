#!/usr/bin/env python3
"""Repository policy checks for Git and Codex hooks."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

AGENT_BRANCH_RE = re.compile(r"^(codex|claude|gemini|gpt)/(feature|fix|security|refactor|chore)/.+")
DESTRUCTIVE_COMMAND_RE = re.compile(r"(^|\s)(rm\s+-|git\s+(reset\s+--hard|checkout\s+--|clean\s+-))")
DOC_TOUCH_RE = re.compile(r"(web/|src/(analysis|fetching|parsing|indexing)/|scripts/)")
DOC_PATH_RE = re.compile(r"^(README\.md|docs/)")


def main(argv: list[str]) -> int:
    mode = argv[1] if len(argv) > 1 else ""
    if mode == "git-pre-commit":
        return git_pre_commit()
    if mode == "git-pre-push":
        return git_pre_push()
    if mode == "codex-pre-tool-use":
        return codex_pre_tool_use()
    print("Usage: repo_policy.py git-pre-commit|git-pre-push|codex-pre-tool-use", file=sys.stderr)
    return 2


def git_pre_commit() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    branch = current_branch()
    if branch == "main":
        errors.append("Commit auf main ist nicht erlaubt. Erstelle zuerst einen Arbeitsbranch.")
    elif branch and not AGENT_BRANCH_RE.match(branch):
        warnings.append(
            "Branch folgt keinem Agent-Praefix-Muster "
            "(z. B. codex/feature/name oder codex/chore/name)."
        )

    staged = staged_changes()
    deleted_py = [change.display_path for change in staged if change.removes_python_file]
    old_blocked = [change.display_path for change in staged if change.touches_existing_old_path]
    old_added = [change.display_path for change in staged if change.adds_old_path]
    if deleted_py:
        errors.append(
            "Python-Dateien duerfen nicht geloescht werden; nach old/ verschieben: "
            + ", ".join(deleted_py)
        )
    if old_blocked:
        errors.append(
            "Bestehende Dateien unter old/ duerfen nur auf explizite Anfrage geaendert werden: "
            + ", ".join(old_blocked)
        )
    if old_added:
        warnings.append(
            "Neue Dateien unter old/ erkannt. Das ist nur fuer explizite Archivierung/Legacy-Verschiebung gedacht: "
            + ", ".join(old_added)
        )

    touched = [path for change in staged for path in change.paths]
    if any(DOC_TOUCH_RE.search(path) for path in touched) and not any(DOC_PATH_RE.search(path) for path in touched):
        warnings.append(
            "Code-/Workflow-Dateien geaendert, aber keine README.md/docs-Datei gestaged. "
            "Bitte Doku-Pruefung bewusst bestaetigen."
        )

    return report("pre-commit", errors, warnings)


def git_pre_push() -> int:
    errors: list[str] = []
    pushed_main_refs = [ref for ref in pushed_remote_refs(sys.stdin.read()) if _is_main_ref(ref)]
    if pushed_main_refs:
        errors.append("Push nach main ist nicht erlaubt: " + ", ".join(pushed_main_refs))
    elif current_branch() == "main":
        errors.append("Push von main ist nicht erlaubt.")
    return report("pre-push", errors, [])


def codex_pre_tool_use() -> int:
    payload = read_json_stdin()
    tool_input = payload.get("tool_input") or payload.get("input") or payload.get("arguments") or {}
    command = ""
    if isinstance(tool_input, dict):
        command = str(tool_input.get("cmd") or tool_input.get("command") or "")
    matcher_text = json.dumps(tool_input, ensure_ascii=False) if tool_input else ""
    branch = current_branch(cwd=Path(str(payload.get("cwd") or os.getcwd())))
    messages: list[str] = []

    if branch == "main":
        messages.append("Repo-Regel: Nicht auf main arbeiten; zuerst einen codex/* Branch erstellen.")
    elif branch and not branch.startswith("codex/"):
        messages.append(f"Repo-Regel: Codex-Arbeit sollte auf codex/* laufen; aktueller Branch: {branch}.")

    if command and DESTRUCTIVE_COMMAND_RE.search(command):
        messages.append("Repo-Regel: destruktive Shell-Kommandos nur nach expliziter Freigabe verwenden.")
    if "old/" in matcher_text or "old\\" in matcher_text:
        messages.append("Repo-Regel: Dateien unter old/ nicht aendern, ausser explizit angefordert.")
    if ("Delete File" in matcher_text and ".py" in matcher_text) or re.search(r"rm\s+[^\n]*\.py", matcher_text):
        messages.append("Repo-Regel: Python-Dateien nicht loeschen; bei Obsoleszenz nach old/ verschieben.")

    if messages:
        print(json.dumps({"systemMessage": "\n".join(messages)}, ensure_ascii=False))
    return 0


def current_branch(cwd: Path | None = None) -> str:
    result = run_git(["branch", "--show-current"], cwd=cwd)
    return result.stdout.strip() if result.returncode == 0 else ""


class StagedChange:
    def __init__(self, status: str, paths: list[str]) -> None:
        self.status = status
        self.paths = paths

    @property
    def display_path(self) -> str:
        return " -> ".join(self.paths)

    @property
    def removes_python_file(self) -> bool:
        if not self.paths or not self.paths[0].endswith(".py"):
            return False
        if self.status.startswith("D"):
            return True
        if self.status.startswith("R"):
            return not self.is_python_archive_move
        return False

    @property
    def is_python_archive_move(self) -> bool:
        if not self.status.startswith("R") or len(self.paths) < 2:
            return False
        source, destination = self.paths[0], self.paths[-1]
        return (
            source.endswith(".py")
            and _is_old_path(destination)
            and destination.endswith(".py")
            and Path(source).name == Path(destination).name
        )

    @property
    def touches_existing_old_path(self) -> bool:
        return any(_is_old_path(path) for path in self.existing_paths)

    @property
    def adds_old_path(self) -> bool:
        return self.status.startswith(("A", "R")) and _is_old_path(self.paths[-1])

    @property
    def existing_paths(self) -> list[str]:
        if self.status.startswith("A"):
            return []
        if self.status.startswith("R"):
            return [self.paths[0]]
        return self.paths


def staged_changes() -> list[StagedChange]:
    result = run_git(["diff", "--cached", "--name-status", "-M", "--diff-filter=ACDMRTUXB"])
    if result.returncode != 0:
        return []
    changes: list[StagedChange] = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0]
        paths = parts[1:]
        changes.append(StagedChange(status, paths))
    return changes


def pushed_remote_refs(stdin_text: str) -> list[str]:
    refs: list[str] = []
    for line in stdin_text.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            refs.append(parts[2])
    return refs


def _is_main_ref(ref: str) -> bool:
    return ref in {"main", "refs/heads/main"}

def _is_old_path(path: str) -> bool:
    return path == "old" or path.startswith("old/")

def run_git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=str(cwd) if cwd else None, text=True, capture_output=True, check=False)


def read_json_stdin() -> dict[str, Any]:
    try:
        data = sys.stdin.read()
        parsed = json.loads(data) if data.strip() else {}
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def report(hook_name: str, errors: list[str], warnings: list[str]) -> int:
    if warnings:
        print(f"[{hook_name}] Hinweise:", file=sys.stderr)
        for warning in warnings:
            print(f"  - {warning}", file=sys.stderr)
    if errors:
        print(f"[{hook_name}] Blockiert:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
