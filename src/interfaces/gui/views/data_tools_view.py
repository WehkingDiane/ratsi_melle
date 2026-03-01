"""Data tools view layout."""

from __future__ import annotations

import customtkinter as ctk

from ..config import (
    B_R_BLUE,
    BUTTON_FONT,
    FIELD_FONT,
    HOVER_BLUE,
    LABEL_FONT,
    LOG_FONT,
)


def build_data_tools_view(app, parent: ctk.CTkFrame) -> None:
    app._build_controls(parent)
    app._build_status(parent)
    app._build_log(parent)
    app._build_footer(parent)


def build_controls(app, parent: ctk.CTkFrame) -> None:
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    frame.pack(fill="x", padx=20, pady=12)
    frame.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(frame, text="Action:", font=LABEL_FONT).grid(row=0, column=0, sticky="w")
    action_box = ctk.CTkComboBox(
        frame,
        variable=app.selected_action,
        values=app.data_tool_actions,
        width=460,
        font=FIELD_FONT,
    )
    action_box.grid(row=1, column=0, sticky="w", pady=(0, 8))
    action_box.configure(command=lambda _value: app._on_action_changed())

    params_frame = ctk.CTkFrame(frame, fg_color="transparent")
    params_frame.grid(row=1, column=1, sticky="w", padx=(20, 0))

    ctk.CTkLabel(params_frame, text="Year:", font=FIELD_FONT).grid(
        row=0, column=0, sticky="w", padx=(0, 6)
    )
    ctk.CTkEntry(
        params_frame,
        textvariable=app.year_value,
        width=80,
        placeholder_text="2026",
    ).grid(
        row=0, column=1, sticky="w", padx=(0, 12)
    )
    ctk.CTkLabel(params_frame, text="Months (e.g. 5 6):", font=FIELD_FONT).grid(
        row=0, column=2, sticky="w", padx=(0, 6)
    )
    ctk.CTkEntry(
        params_frame,
        textvariable=app.months_value,
        width=140,
        placeholder_text="5 6 7",
    ).grid(
        row=0, column=3, sticky="w"
    )

    ctk.CTkCheckBox(frame, text="Verbose", variable=app.verbose_mode, font=FIELD_FONT).grid(
        row=1, column=2, sticky="w", padx=(20, 0)
    )

    app.run_button = ctk.CTkButton(
        frame,
        text="Run",
        command=app._run_action,
        fg_color=B_R_BLUE,
        hover_color=HOVER_BLUE,
        font=BUTTON_FONT,
        height=36,
    )
    app.run_button.grid(row=1, column=3, sticky="w", padx=(20, 0))

    app.cancel_button = ctk.CTkButton(
        frame,
        text="Cancel",
        command=app._cancel_running_action,
        fg_color="#B91C1C",
        hover_color="#991B1B",
        font=BUTTON_FONT,
        height=36,
        state="disabled",
    )
    app.cancel_button.grid(row=1, column=4, sticky="w", padx=(10, 0))

    preset_frame = ctk.CTkFrame(frame, fg_color="transparent")
    preset_frame.grid(row=2, column=0, columnspan=5, sticky="w", pady=(8, 0))
    ctk.CTkLabel(preset_frame, text="Preset:", font=FIELD_FONT).pack(side="left", padx=(0, 6))
    preset_box = ctk.CTkComboBox(
        preset_frame,
        variable=app.selected_preset,
        values=list(app.presets.keys()),
        width=300,
        font=FIELD_FONT,
    )
    preset_box.pack(side="left", padx=(0, 10))

    app.run_preset_button = ctk.CTkButton(
        preset_frame,
        text="Run Preset",
        command=app._run_selected_preset,
        fg_color="#0F766E",
        hover_color="#115E59",
        font=BUTTON_FONT,
        height=34,
    )
    app.run_preset_button.pack(side="left")

    app.export_frame = ctk.CTkFrame(frame, fg_color="transparent")
    app.export_frame.grid(row=3, column=0, columnspan=5, sticky="ew", pady=(10, 0))
    app.export_frame.grid_columnconfigure(1, weight=1)
    app.export_frame.grid_columnconfigure(3, weight=1)

    ctk.CTkLabel(app.export_frame, text="DB Path:", font=FIELD_FONT).grid(
        row=0, column=0, sticky="w", padx=(0, 6), pady=(0, 6)
    )
    ctk.CTkEntry(
        app.export_frame,
        textvariable=app.export_db_path,
        font=FIELD_FONT,
        placeholder_text="data/processed/local_index.sqlite",
    ).grid(
        row=0, column=1, sticky="ew", padx=(0, 16), pady=(0, 6)
    )

    ctk.CTkLabel(app.export_frame, text="Output:", font=FIELD_FONT).grid(
        row=0, column=2, sticky="w", padx=(0, 6), pady=(0, 6)
    )
    ctk.CTkEntry(
        app.export_frame,
        textvariable=app.export_output_path,
        font=FIELD_FONT,
        placeholder_text="data/analysis_requests/analysis_batch.json",
    ).grid(
        row=0, column=3, sticky="ew", pady=(0, 6)
    )

    ctk.CTkLabel(app.export_frame, text="Committees (comma):", font=FIELD_FONT).grid(
        row=1, column=0, sticky="w", padx=(0, 6), pady=(0, 6)
    )
    ctk.CTkEntry(
        app.export_frame,
        textvariable=app.export_committees,
        font=FIELD_FONT,
        placeholder_text="Rat, Ausschuss fuer Finanzen",
    ).grid(
        row=1, column=1, sticky="ew", padx=(0, 16), pady=(0, 6)
    )

    ctk.CTkLabel(app.export_frame, text="Document types (comma):", font=FIELD_FONT).grid(
        row=1, column=2, sticky="w", padx=(0, 6), pady=(0, 6)
    )
    ctk.CTkEntry(
        app.export_frame,
        textvariable=app.export_document_types,
        font=FIELD_FONT,
        placeholder_text="vorlage, beschlussvorlage, protokoll",
    ).grid(
        row=1, column=3, sticky="ew", pady=(0, 6)
    )

    ctk.CTkLabel(app.export_frame, text="Date from:", font=FIELD_FONT).grid(
        row=2, column=0, sticky="w", padx=(0, 6), pady=(0, 6)
    )
    ctk.CTkEntry(
        app.export_frame,
        textvariable=app.export_date_from,
        font=FIELD_FONT,
        placeholder_text="2026-01-01",
    ).grid(
        row=2, column=1, sticky="ew", padx=(0, 16), pady=(0, 6)
    )

    ctk.CTkLabel(app.export_frame, text="Date to:", font=FIELD_FONT).grid(
        row=2, column=2, sticky="w", padx=(0, 6), pady=(0, 6)
    )
    ctk.CTkEntry(
        app.export_frame,
        textvariable=app.export_date_to,
        font=FIELD_FONT,
        placeholder_text="2026-12-31",
    ).grid(
        row=2, column=3, sticky="ew", pady=(0, 6)
    )

    ctk.CTkCheckBox(
        app.export_frame,
        text="Require local path",
        variable=app.export_require_local_path,
        font=FIELD_FONT,
    ).grid(row=3, column=0, sticky="w", pady=(0, 2))
    ctk.CTkCheckBox(
        app.export_frame,
        text="Include text extraction",
        variable=app.export_include_text_extraction,
        font=FIELD_FONT,
    ).grid(row=3, column=1, sticky="w", pady=(0, 2))
    ctk.CTkLabel(app.export_frame, text="Max text chars:", font=FIELD_FONT).grid(
        row=3, column=2, sticky="w", padx=(0, 6), pady=(0, 2)
    )
    ctk.CTkEntry(
        app.export_frame,
        textvariable=app.export_max_text_chars,
        width=160,
        placeholder_text="12000",
    ).grid(
        row=3, column=3, sticky="w", pady=(0, 2)
    )

    app.validation_label = ctk.CTkLabel(
        frame,
        text="",
        font=FIELD_FONT,
        text_color="#DC2626",
        anchor="w",
    )
    app.validation_label.grid(row=4, column=0, columnspan=5, sticky="ew", pady=(8, 0))


def build_status(app, parent: ctk.CTkFrame) -> None:
    app.status_label = ctk.CTkLabel(parent, text="Ready", height=24, anchor="w", font=FIELD_FONT)
    app.status_label.pack(fill="x", padx=20, pady=(0, 6))


def build_log(app, parent: ctk.CTkFrame) -> None:
    app.output_frame = ctk.CTkFrame(parent, fg_color="transparent")
    app.output_frame.pack(fill="both", expand=True, padx=20, pady=10)
    app.output_frame.grid_columnconfigure(0, weight=3)
    app.output_frame.grid_columnconfigure(1, weight=2)
    app.output_frame.grid_rowconfigure(0, weight=1)

    app.log_text = ctk.CTkTextbox(
        app.output_frame,
        wrap="word",
        font=LOG_FONT,
        border_width=1,
        corner_radius=6,
    )
    app.log_text.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
    app.log_text.configure(state="disabled")

    textbox = app.log_text._textbox
    textbox.tag_configure("error", foreground="#ef4444")
    textbox.tag_configure("warning", foreground="#f59e0b")
    textbox.tag_configure("info", foreground="#22c55e")
    textbox.tag_configure(
        "normal",
        foreground="white" if ctk.get_appearance_mode() == "Dark" else "black",
    )

    right_panel = ctk.CTkFrame(app.output_frame, corner_radius=8)
    right_panel.grid(row=0, column=1, sticky="nsew")
    right_panel.grid_rowconfigure(1, weight=1)
    right_panel.grid_columnconfigure(0, weight=1)

    app.right_title = ctk.CTkLabel(right_panel, text="Details", font=LABEL_FONT, anchor="w")
    app.right_title.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))

    app.right_content = ctk.CTkScrollableFrame(right_panel)
    app.right_content.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
    app._render_placeholder()


def build_footer(app, parent: ctk.CTkFrame) -> None:
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    frame.pack(fill="x", padx=20, pady=(0, 16))

    ctk.CTkButton(
        frame,
        text="Clear Log",
        command=app._clear_log,
        fg_color="#374151",
        hover_color="#4b5563",
        font=BUTTON_FONT,
        height=34,
    ).pack(side="right")

    ctk.CTkButton(
        frame,
        text="Open Output Folder",
        command=app._open_output_folder,
        fg_color="#1D4ED8",
        hover_color="#1E40AF",
        font=BUTTON_FONT,
        height=34,
    ).pack(side="right", padx=(0, 10))
