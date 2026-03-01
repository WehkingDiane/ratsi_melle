"""Developer analysis batch export view layout."""

from __future__ import annotations

import customtkinter as ctk

from ..config import BUTTON_FONT, FIELD_FONT, LABEL_FONT, LOG_FONT


def build_export_view(app, parent: ctk.CTkFrame) -> None:
    parent.grid_columnconfigure(0, weight=5)
    parent.grid_columnconfigure(1, weight=4)
    parent.grid_rowconfigure(2, weight=1)

    info_frame = ctk.CTkFrame(parent)
    info_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=(16, 8))
    ctk.CTkLabel(
        info_frame,
        text="Analyse-Batch Export (Developer)",
        font=LABEL_FONT,
        anchor="w",
    ).pack(fill="x", padx=12, pady=(12, 4))
    ctk.CTkLabel(
        info_frame,
        text=(
            "Erzeugt eine reproduzierbare JSON-Datei mit gefilterten Sitzungen und Dokumenten. "
            "Die Datei ist fuer Modelltests, API-Weitergabe und spaetere Vergleiche gedacht, "
            "nicht fuer die direkte journalistische Analyse in der GUI."
        ),
        font=FIELD_FONT,
        anchor="w",
        justify="left",
        wraplength=1180,
    ).pack(fill="x", padx=12, pady=(0, 12))

    controls = ctk.CTkFrame(parent)
    controls.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 8))
    for column in range(4):
        controls.grid_columnconfigure(column, weight=1)

    ctk.CTkLabel(controls, text="Exportprofil", font=FIELD_FONT).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))
    app.export_profile_box = ctk.CTkComboBox(
        controls,
        variable=app.export_profile,
        values=list(app.export_profiles.keys()),
        command=app._on_export_profile_changed,
        width=260,
    )
    app.export_profile_box.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))

    ctk.CTkLabel(controls, text="Zeitraum", font=FIELD_FONT).grid(row=0, column=1, sticky="w", padx=12, pady=(12, 6))
    app.export_date_preset_box = ctk.CTkComboBox(
        controls,
        variable=app.export_date_preset,
        values=list(app.export_date_presets.keys()),
        command=app._on_export_date_preset_changed,
        width=220,
    )
    app.export_date_preset_box.grid(row=1, column=1, sticky="ew", padx=12, pady=(0, 10))

    ctk.CTkLabel(controls, text="Gremium aus DB", font=FIELD_FONT).grid(row=0, column=2, sticky="w", padx=12, pady=(12, 6))
    app.export_committee_box = ctk.CTkComboBox(
        controls,
        variable=app.export_committee_selection,
        values=["Alle Gremien"],
        command=app._on_export_committee_selected,
        width=260,
    )
    app.export_committee_box.grid(row=1, column=2, sticky="ew", padx=12, pady=(0, 10))

    ctk.CTkLabel(controls, text="Dokumentprofil", font=FIELD_FONT).grid(row=0, column=3, sticky="w", padx=12, pady=(12, 6))
    app.export_document_profile_box = ctk.CTkComboBox(
        controls,
        variable=app.export_document_profile,
        values=list(app.export_document_profiles.keys()),
        command=app._on_export_document_profile_changed,
        width=260,
    )
    app.export_document_profile_box.grid(row=1, column=3, sticky="ew", padx=12, pady=(0, 10))

    ctk.CTkLabel(controls, text="DB-Pfad", font=FIELD_FONT).grid(row=2, column=0, sticky="w", padx=12, pady=(0, 6))
    ctk.CTkEntry(controls, textvariable=app.export_db_path, font=FIELD_FONT).grid(
        row=3, column=0, sticky="ew", padx=12, pady=(0, 8)
    )

    ctk.CTkLabel(controls, text="Output-Datei", font=FIELD_FONT).grid(row=2, column=1, sticky="w", padx=12, pady=(0, 6))
    ctk.CTkEntry(controls, textvariable=app.export_output_path, font=FIELD_FONT).grid(
        row=3, column=1, sticky="ew", padx=12, pady=(0, 8)
    )

    ctk.CTkLabel(controls, text="Gremien (kommagetrennt)", font=FIELD_FONT).grid(row=2, column=2, sticky="w", padx=12, pady=(0, 6))
    ctk.CTkEntry(controls, textvariable=app.export_committees, font=FIELD_FONT).grid(
        row=3, column=2, sticky="ew", padx=12, pady=(0, 8)
    )

    ctk.CTkLabel(controls, text="Dokumenttypen (kommagetrennt)", font=FIELD_FONT).grid(row=2, column=3, sticky="w", padx=12, pady=(0, 6))
    ctk.CTkEntry(controls, textvariable=app.export_document_types, font=FIELD_FONT).grid(
        row=3, column=3, sticky="ew", padx=12, pady=(0, 8)
    )

    ctk.CTkLabel(controls, text="Von", font=FIELD_FONT).grid(row=4, column=0, sticky="w", padx=12, pady=(0, 6))
    ctk.CTkEntry(controls, textvariable=app.export_date_from, font=FIELD_FONT, width=180).grid(
        row=5, column=0, sticky="ew", padx=12, pady=(0, 8)
    )

    ctk.CTkLabel(controls, text="Bis", font=FIELD_FONT).grid(row=4, column=1, sticky="w", padx=12, pady=(0, 6))
    ctk.CTkEntry(controls, textvariable=app.export_date_to, font=FIELD_FONT, width=180).grid(
        row=5, column=1, sticky="ew", padx=12, pady=(0, 8)
    )

    ctk.CTkLabel(controls, text="Max Textzeichen", font=FIELD_FONT).grid(row=4, column=2, sticky="w", padx=12, pady=(0, 6))
    ctk.CTkEntry(controls, textvariable=app.export_max_text_chars, font=FIELD_FONT, width=180).grid(
        row=5, column=2, sticky="ew", padx=12, pady=(0, 8)
    )

    toggle_row = ctk.CTkFrame(controls, fg_color="transparent")
    toggle_row.grid(row=5, column=3, sticky="w", padx=12, pady=(0, 8))
    ctk.CTkCheckBox(
        toggle_row,
        text="Nur lokale Dateien",
        variable=app.export_require_local_path,
        font=FIELD_FONT,
    ).pack(anchor="w")
    ctk.CTkCheckBox(
        toggle_row,
        text="Text-Extraktion einbeziehen",
        variable=app.export_include_text_extraction,
        font=FIELD_FONT,
    ).pack(anchor="w", pady=(6, 0))

    action_row = ctk.CTkFrame(controls, fg_color="transparent")
    action_row.grid(row=6, column=0, columnspan=4, sticky="ew", padx=12, pady=(4, 12))
    app.export_run_button = ctk.CTkButton(
        action_row,
        text="Analyse-Batch als JSON erzeugen",
        command=app._run_export_action,
        fg_color="#0F766E",
        hover_color="#115E59",
        font=BUTTON_FONT,
    )
    app.export_run_button.pack(side="left")
    app.export_open_button = ctk.CTkButton(
        action_row,
        text="Exportdatei anzeigen",
        command=app._preview_current_export_file,
        fg_color="#374151",
        hover_color="#4B5563",
        font=BUTTON_FONT,
    )
    app.export_open_button.pack(side="left", padx=(10, 0))

    app.export_validation_label = ctk.CTkLabel(
        controls,
        text="",
        font=FIELD_FONT,
        text_color="#DC2626",
        anchor="w",
    )
    app.export_validation_label.grid(row=7, column=0, columnspan=4, sticky="ew", padx=12, pady=(0, 10))

    app.status_label = ctk.CTkLabel(parent, text="Bereit", height=24, anchor="w", font=FIELD_FONT)
    app.status_label.grid(row=3, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 6))

    app.log_text = ctk.CTkTextbox(parent, wrap="word", font=LOG_FONT, border_width=1, corner_radius=6)
    app.log_text.grid(row=4, column=0, sticky="nsew", padx=(20, 10), pady=(0, 20))
    app.log_text.configure(state="disabled")

    textbox = app.log_text._textbox
    textbox.tag_configure("error", foreground="#ef4444")
    textbox.tag_configure("warning", foreground="#f59e0b")
    textbox.tag_configure("info", foreground="#22c55e")
    textbox.tag_configure(
        "normal",
        foreground="white" if ctk.get_appearance_mode() == "Dark" else "black",
    )

    right_panel = ctk.CTkFrame(parent)
    right_panel.grid(row=4, column=1, sticky="nsew", padx=(10, 20), pady=(0, 20))
    right_panel.grid_columnconfigure(0, weight=1)
    right_panel.grid_rowconfigure(1, weight=1)
    right_panel.grid_rowconfigure(3, weight=3)

    app.right_title = ctk.CTkLabel(right_panel, text="Exportdetails", font=LABEL_FONT, anchor="w")
    app.right_title.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))

    app.right_content = ctk.CTkScrollableFrame(right_panel, height=220)
    app.right_content.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))

    ctk.CTkLabel(right_panel, text="Dateivorschau", font=FIELD_FONT, anchor="w").grid(
        row=2, column=0, sticky="ew", padx=12, pady=(0, 4)
    )
    app.export_preview_text = ctk.CTkTextbox(right_panel, font=LOG_FONT, wrap="none")
    app.export_preview_text.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0, 12))
    app.export_preview_text.insert(
        "1.0",
        "Noch keine Exportdatei geladen. Fuehre einen Export aus oder nutze 'Exportdatei anzeigen'.",
    )
    app.export_preview_text.configure(state="disabled")

    app._refresh_export_committee_options()
    app._render_placeholder()
