"""Shared GUI constants and paths."""

from __future__ import annotations

from pathlib import Path

import customtkinter as ctk

from src.paths import RAW_DATA_DIR, REPO_ROOT

DATA_ROOT_DEFAULT = RAW_DATA_DIR
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
