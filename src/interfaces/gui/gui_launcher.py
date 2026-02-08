"""Backward-compatible GUI launcher entrypoint."""

from __future__ import annotations

try:
    from .app import GuiLauncher, main
except ImportError:  # pragma: no cover - direct file execution fallback
    from src.interfaces.gui.app import GuiLauncher, main

__all__ = ["GuiLauncher", "main"]


if __name__ == "__main__":
    main()
