"""Backward-compatible GUI launcher entrypoint."""

from __future__ import annotations

from .app import GuiLauncher, main

__all__ = ["GuiLauncher", "main"]


if __name__ == "__main__":
    main()
