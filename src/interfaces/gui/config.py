"""Shared GUI constants and paths."""

from __future__ import annotations

from pathlib import Path

import customtkinter as ctk

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT_DEFAULT = REPO_ROOT / "data" / "raw"
SETTINGS_PATH = REPO_ROOT / "configs" / "gui_settings.json"

B_R_BLUE = "#3B82F6"
HOVER_BLUE = "#2563EB"

LABEL_FONT = ("Segoe UI", 14, "bold")
FIELD_FONT = ("Segoe UI", 14)
BUTTON_FONT = ("Segoe UI", 14, "bold")
LOG_FONT = ("Consolas", 12)

SPINNER_FRAMES = ["|", "/", "-", "\\"]


def configure_theme() -> None:
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
