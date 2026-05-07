"""Modal dialog for managing KI provider API keys stored in the OS keychain."""

from __future__ import annotations

import customtkinter as ctk

from src.config.secrets import delete_api_key, key_source, set_api_key
from src.interfaces.gui.config import BUTTON_FONT, FIELD_FONT, LABEL_FONT

# Providers that require an API key (ollama uses local HTTP, no key needed)
_PROVIDERS: list[tuple[str, str]] = [
    ("claude", "Claude (Anthropic)"),
    ("codex", "Codex (OpenAI)"),
    ("huggingface", "Hugging Face"),
]


class ApiKeysDialog(ctk.CTkToplevel):
    """Modal dialog to enter, save and delete API keys for KI providers.

    Keys are persisted in the OS keychain (Windows Credential Manager,
    macOS Keychain, Linux Secret Service) via the ``secrets`` module.
    """

    def __init__(self, parent: ctk.CTk) -> None:
        super().__init__(parent)
        self.title("API-Keys verwalten")
        self.resizable(False, False)
        self.grab_set()  # modal

        self._entries: dict[str, ctk.CTkEntry] = {}
        self._source_labels: dict[str, ctk.CTkLabel] = {}

        self._build_ui()
        self._refresh_sources()
        self._center_on_parent(parent)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = ctk.CTkFrame(self)
        outer.pack(fill="both", expand=True, padx=20, pady=16)

        ctk.CTkLabel(outer, text="API-Keys verwalten", font=LABEL_FONT).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 12)
        )
        ctk.CTkLabel(
            outer,
            text=(
                "Schlussel werden im OS-Schluesselring gespeichert\n"
                "(Windows Credential Manager).\n"
                "Umgebungsvariablen werden als Fallback verwendet."
            ),
            font=FIELD_FONT,
            justify="left",
            text_color="gray60",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 16))

        for i, (provider_id, label) in enumerate(_PROVIDERS):
            row = i + 2
            ctk.CTkLabel(outer, text=f"{label}:", font=FIELD_FONT, width=160, anchor="w").grid(
                row=row, column=0, sticky="w", pady=6, padx=(0, 8)
            )
            entry = ctk.CTkEntry(outer, width=320, show="\u2022", placeholder_text="API-Key eingeben…")
            entry.grid(row=row, column=1, pady=6)
            self._entries[provider_id] = entry

            src_label = ctk.CTkLabel(outer, text="", font=FIELD_FONT, width=160, anchor="w", text_color="gray60")
            src_label.grid(row=row, column=2, sticky="w", padx=(10, 0))
            self._source_labels[provider_id] = src_label

        # Divider row
        sep_row = len(_PROVIDERS) + 2
        ctk.CTkFrame(outer, height=1, fg_color="gray30").grid(
            row=sep_row, column=0, columnspan=3, sticky="ew", pady=(12, 8)
        )

        btn_row = sep_row + 1
        ctk.CTkButton(
            outer,
            text="Speichern",
            command=self._save,
            fg_color="#1D4ED8",
            hover_color="#1E40AF",
            font=BUTTON_FONT,
            width=110,
        ).grid(row=btn_row, column=0, sticky="w", pady=(4, 0))

        ctk.CTkButton(
            outer,
            text="Alle loeschen",
            command=self._delete_all,
            fg_color="#7F1D1D",
            hover_color="#991B1B",
            font=BUTTON_FONT,
            width=130,
        ).grid(row=btn_row, column=1, sticky="w", padx=(8, 0), pady=(4, 0))

        ctk.CTkButton(
            outer,
            text="Schliessen",
            command=self.destroy,
            fg_color="#374151",
            hover_color="#4B5563",
            font=BUTTON_FONT,
            width=110,
        ).grid(row=btn_row, column=2, sticky="e", pady=(4, 0))

        self._feedback_label = ctk.CTkLabel(
            outer, text="", font=FIELD_FONT, text_color="gray60", anchor="w"
        )
        self._feedback_label.grid(row=btn_row + 1, column=0, columnspan=3, sticky="w", pady=(8, 0))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _save(self) -> None:
        saved: list[str] = []
        for provider_id, entry in self._entries.items():
            value = entry.get().strip()
            if value:
                try:
                    set_api_key(provider_id, value)
                    entry.delete(0, "end")
                    saved.append(provider_id)
                except Exception as exc:  # noqa: BLE001
                    self._set_feedback(f"Fehler beim Speichern ({provider_id}): {exc}", error=True)
                    return

        if saved:
            self._set_feedback(f"Gespeichert: {', '.join(saved)}")
        else:
            self._set_feedback("Keine Eingabe – bitte Key eingeben und dann Speichern klicken.")
        self._refresh_sources()

    def _delete_all(self) -> None:
        for provider_id in self._entries:
            delete_api_key(provider_id)
        self._set_feedback("Alle Eintraege aus dem Schluesselring geloescht.")
        self._refresh_sources()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _refresh_sources(self) -> None:
        for provider_id, label in self._source_labels.items():
            source = key_source(provider_id)
            color = "gray50" if source == "nicht gesetzt" else "#22C55E"
            label.configure(text=f"Quelle: {source}", text_color=color)

    def _set_feedback(self, msg: str, *, error: bool = False) -> None:
        self._feedback_label.configure(
            text=msg, text_color="#EF4444" if error else "gray60"
        )

    def _center_on_parent(self, parent: ctk.CTk) -> None:
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_x(), parent.winfo_y()
        dw, dh = self.winfo_width(), self.winfo_height()
        x = px + (pw - dw) // 2
        y = py + (ph - dh) // 2
        self.geometry(f"+{x}+{y}")
