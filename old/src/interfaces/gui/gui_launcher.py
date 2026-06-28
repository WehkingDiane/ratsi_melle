"""Backward-compatible GUI launcher entrypoint."""

from __future__ import annotations

try:
    from .app import GuiLauncher, main
except ImportError:  # pragma: no cover - direct file execution fallback
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from src.interfaces.gui.app import GuiLauncher, main

__all__ = ["GuiLauncher", "main"]


if __name__ == "__main__":
    main()
