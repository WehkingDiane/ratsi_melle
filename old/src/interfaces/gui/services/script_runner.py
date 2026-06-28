"""Subprocess helper for GUI actions."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class ScriptResult:
    status: str
    command: str
    exit_code: int
    lines: int
    summary: str
    cancelled: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "command": self.command,
            "exit_code": self.exit_code,
            "lines": self.lines,
            "summary": self.summary,
            "cancelled": self.cancelled,
        }


class ScriptRunner:
    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd
        self.current_process: subprocess.Popen | None = None

    def run(
        self,
        cmd: list[str],
        *,
        on_line: Callable[[str], None],
        is_cancel_requested: Callable[[], bool],
        on_process_start: Callable[[subprocess.Popen], None] | None = None,
        on_process_done: Callable[[], None] | None = None,
    ) -> ScriptResult:
        process = subprocess.Popen(
            cmd,
            cwd=str(self.cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self.current_process = process
        if on_process_start:
            on_process_start(process)

        assert process.stdout is not None
        last_line = ""
        line_count = 0
        for line in process.stdout:
            if is_cancel_requested() and process.poll() is None:
                process.terminate()
            stripped = line.rstrip()
            if stripped:
                last_line = stripped
            on_line(stripped)
            line_count += 1
        process.wait()

        cancelled = is_cancel_requested() and process.returncode not in (0, None)
        if on_process_done:
            on_process_done()

        self.current_process = None
        return ScriptResult(
            status="cancelled" if cancelled else ("ok" if process.returncode == 0 else "error"),
            command=" ".join(cmd),
            exit_code=int(process.returncode or 0),
            lines=line_count,
            summary=last_line,
            cancelled=cancelled,
        )

    def cancel(self) -> None:
        process = self.current_process
        if process is not None and process.poll() is None:
            process.terminate()
