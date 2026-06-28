"""Settings view layout."""

from __future__ import annotations

import customtkinter as ctk

from ..config import BUTTON_FONT, FIELD_FONT, LABEL_FONT

# Providers that require an API key (ollama uses local HTTP, no key needed)
_KEY_PROVIDERS: list[tuple[str, str]] = [
    ("claude", "Claude (Anthropic)"),
    ("codex", "Codex (OpenAI)"),
    ("huggingface", "Hugging Face"),
]


def build_settings_view(app, parent: ctk.CTkFrame) -> None:
    outer = ctk.CTkScrollableFrame(parent)
    outer.pack(fill="both", expand=True, padx=20, pady=20)
    outer.grid_columnconfigure(0, weight=1)

    # ------------------------------------------------------------------ #
    # Section: API-Keys                                                    #
    # ------------------------------------------------------------------ #
    ctk.CTkLabel(outer, text="API-Keys", font=LABEL_FONT).pack(anchor="w", padx=12, pady=(12, 2))
    ctk.CTkLabel(
        outer,
        text=(
            "Schluessel werden sicher im OS-Schluesselring gespeichert\n"
            "(Windows Credential Manager)  –  nie in einer Datei auf der Festplatte.\n"
            "Umgebungsvariablen (ANTHROPIC_API_KEY, OPENAI_API_KEY, HF_TOKEN) wirken als Fallback."
        ),
        font=FIELD_FONT,
        justify="left",
        text_color="gray60",
    ).pack(anchor="w", padx=12, pady=(0, 12))

    # One row per provider
    app.settings_api_key_entries = {}
    app.settings_key_source_labels = {}

    for provider_id, label in _KEY_PROVIDERS:
        row_frame = ctk.CTkFrame(outer, fg_color="transparent")
        row_frame.pack(fill="x", padx=12, pady=4)

        ctk.CTkLabel(row_frame, text=f"{label}:", font=FIELD_FONT, width=160, anchor="w").pack(
            side="left"
        )

        entry = ctk.CTkEntry(
            row_frame,
            show="\u2022",
            placeholder_text="API-Key eingeben \u2026",
            width=300,
        )
        entry.pack(side="left", padx=(6, 8))
        app.settings_api_key_entries[provider_id] = entry

        ctk.CTkButton(
            row_frame,
            text="Speichern",
            width=90,
            fg_color="#1D4ED8",
            hover_color="#1E40AF",
            font=BUTTON_FONT,
            command=lambda pid=provider_id: app._save_settings_api_key(pid),
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            row_frame,
            text="Loeschen",
            width=90,
            fg_color="#7F1D1D",
            hover_color="#991B1B",
            font=BUTTON_FONT,
            command=lambda pid=provider_id: app._delete_settings_api_key(pid),
        ).pack(side="left")

        src_label = ctk.CTkLabel(
            row_frame, text="", font=FIELD_FONT, anchor="w", text_color="gray60"
        )
        src_label.pack(side="left", padx=(12, 0))
        app.settings_key_source_labels[provider_id] = src_label

    app._settings_api_key_feedback = ctk.CTkLabel(
        outer, text="", font=FIELD_FONT, text_color="gray60", anchor="w"
    )
    app._settings_api_key_feedback.pack(anchor="w", padx=12, pady=(4, 0))

    # ------------------------------------------------------------------ #
    # Divider                                                              #
    # ------------------------------------------------------------------ #
    ctk.CTkFrame(outer, height=1, fg_color="gray30").pack(fill="x", padx=12, pady=16)

    # ------------------------------------------------------------------ #
    # Section: Allgemeine Einstellungen                                    #
    # ------------------------------------------------------------------ #
    ctk.CTkLabel(outer, text="Allgemeine Einstellungen", font=LABEL_FONT).pack(
        anchor="w", padx=12, pady=(0, 4)
    )
    ctk.CTkButton(
        outer,
        text="Einstellungen speichern",
        command=app._save_settings,
        fg_color="#374151",
        hover_color="#4B5563",
        font=BUTTON_FONT,
    ).pack(anchor="w", padx=12, pady=(4, 0))

    # Populate source labels after widgets are built
    app._refresh_settings_api_key_status()
