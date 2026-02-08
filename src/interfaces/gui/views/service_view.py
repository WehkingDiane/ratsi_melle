"""Service view layout."""

from __future__ import annotations

import customtkinter as ctk

from ..config import BUTTON_FONT, FIELD_FONT, LABEL_FONT


def build_service_view(app, parent: ctk.CTkFrame) -> None:
    frame = ctk.CTkFrame(parent)
    frame.pack(fill="both", expand=True, padx=20, pady=20)
    ctk.CTkLabel(frame, text="Service", font=LABEL_FONT).pack(anchor="w", padx=12, pady=(12, 4))
    ctk.CTkLabel(
        frame,
        text="Diese Seite ist als Erweiterungspunkt vorbereitet.\n"
        "Hier koennen spaeter Scheduler, Queue-Worker oder Healthchecks eingebunden werden.",
        font=FIELD_FONT,
        justify="left",
        anchor="w",
    ).pack(anchor="w", padx=12, pady=(0, 12))
    ctk.CTkButton(
        frame,
        text="Logs/Output-Ordner oeffnen",
        command=app._open_output_folder,
        fg_color="#374151",
        hover_color="#4B5563",
        font=BUTTON_FONT,
    ).pack(anchor="w", padx=12)
