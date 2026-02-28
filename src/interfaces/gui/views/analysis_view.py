"""Analysis workspace view layout."""

from __future__ import annotations

import customtkinter as ctk

from ..config import BUTTON_FONT, FIELD_FONT, LABEL_FONT, LOG_FONT


def build_analysis_view(app, parent: ctk.CTkFrame) -> None:
    parent.grid_columnconfigure(0, weight=2)
    parent.grid_columnconfigure(1, weight=3)
    parent.grid_rowconfigure(1, weight=1)

    filter_frame = ctk.CTkFrame(parent)
    filter_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=(16, 8))
    filter_frame.grid_columnconfigure(7, weight=1)

    ctk.CTkLabel(filter_frame, text="Von", font=FIELD_FONT).grid(row=0, column=0, padx=(10, 4), pady=8)
    ctk.CTkEntry(
        filter_frame,
        textvariable=app.analysis_date_from,
        width=120,
        placeholder_text="2026-01-01",
    ).grid(row=0, column=1, pady=8)
    ctk.CTkLabel(filter_frame, text="Bis", font=FIELD_FONT).grid(row=0, column=2, padx=(10, 4), pady=8)
    ctk.CTkEntry(
        filter_frame,
        textvariable=app.analysis_date_to,
        width=120,
        placeholder_text="2026-12-31",
    ).grid(row=0, column=3, pady=8)

    ctk.CTkLabel(filter_frame, text="Gremium", font=FIELD_FONT).grid(row=0, column=4, padx=(10, 4), pady=8)
    app.analysis_committee_box = ctk.CTkComboBox(
        filter_frame, variable=app.analysis_committee, values=[""], width=220
    )
    app.analysis_committee_box.grid(row=0, column=5, pady=8)
    app.analysis_committee_box.configure(command=lambda _value: app._refresh_analysis_sessions())

    ctk.CTkEntry(
        filter_frame,
        textvariable=app.analysis_search,
        placeholder_text="z. B. Rat oder Haushalt",
        width=220,
    ).grid(row=0, column=6, padx=(10, 6), pady=8)

    ctk.CTkCheckBox(
        filter_frame,
        text="Nur vergangene",
        variable=app.analysis_past_only,
        command=app._refresh_analysis_sessions,
        font=FIELD_FONT,
    ).grid(row=0, column=7, padx=(0, 6), pady=8, sticky="w")

    ctk.CTkButton(
        filter_frame,
        text="Filtern",
        command=app._refresh_analysis_sessions,
        fg_color="#0F766E",
        hover_color="#115E59",
        font=BUTTON_FONT,
    ).grid(row=0, column=8, padx=(0, 10), pady=8)

    left_panel = ctk.CTkFrame(parent)
    left_panel.grid(row=1, column=0, sticky="nsew", padx=(20, 10), pady=(0, 20))
    left_panel.grid_rowconfigure(1, weight=1)
    left_panel.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(left_panel, text="Sitzungen", font=LABEL_FONT).grid(
        row=0, column=0, sticky="w", padx=12, pady=(12, 6)
    )
    app.analysis_session_list_frame = ctk.CTkScrollableFrame(left_panel)
    app.analysis_session_list_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

    right_panel = ctk.CTkFrame(parent)
    right_panel.grid(row=1, column=1, sticky="nsew", padx=(10, 20), pady=(0, 20))
    right_panel.grid_rowconfigure(5, weight=1)
    right_panel.grid_columnconfigure(0, weight=1)

    app.analysis_selected_session_label = ctk.CTkLabel(
        right_panel,
        text="Keine Sitzung ausgewaehlt",
        font=LABEL_FONT,
        anchor="w",
    )
    app.analysis_selected_session_label.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))

    scope_row = ctk.CTkFrame(right_panel, fg_color="transparent")
    scope_row.grid(row=1, column=0, sticky="ew", padx=12)
    ctk.CTkLabel(scope_row, text="Scope:", font=FIELD_FONT).pack(side="left")
    ctk.CTkRadioButton(scope_row, text="Ganze Sitzung", variable=app.analysis_scope, value="session").pack(
        side="left", padx=(10, 10)
    )
    ctk.CTkRadioButton(scope_row, text="Ausgewaehlte TOPs", variable=app.analysis_scope, value="tops").pack(
        side="left"
    )

    ctk.CTkLabel(right_panel, text="Tagesordnung", font=FIELD_FONT).grid(
        row=2, column=0, sticky="w", padx=12, pady=(10, 4)
    )
    app.analysis_tops_frame = ctk.CTkScrollableFrame(right_panel, height=160)
    app.analysis_tops_frame.grid(row=3, column=0, sticky="ew", padx=12)

    ctk.CTkLabel(right_panel, text="Prompt", font=FIELD_FONT).grid(
        row=4, column=0, sticky="w", padx=12, pady=(10, 4)
    )
    app.analysis_prompt_box = ctk.CTkTextbox(right_panel, height=90, font=LOG_FONT)
    app.analysis_prompt_box.grid(row=5, column=0, sticky="nsew", padx=12)
    app.analysis_prompt_box.insert("1.0", app.analysis_prompt_value)

    action_row = ctk.CTkFrame(right_panel, fg_color="transparent")
    action_row.grid(row=6, column=0, sticky="ew", padx=12, pady=(10, 0))
    ctk.CTkButton(
        action_row,
        text="Analyse starten",
        command=app._start_analysis_job,
        fg_color="#1D4ED8",
        hover_color="#1E40AF",
        font=BUTTON_FONT,
    ).pack(side="left")
    ctk.CTkButton(
        action_row,
        text="Prompt zuruecksetzen",
        command=app._reset_analysis_prompt,
        fg_color="#374151",
        hover_color="#4B5563",
        font=BUTTON_FONT,
    ).pack(side="left", padx=(10, 0))
    ctk.CTkButton(
        action_row,
        text="Markdown exportieren",
        command=app._export_analysis_markdown,
        fg_color="#0F766E",
        hover_color="#115E59",
        font=BUTTON_FONT,
    ).pack(side="left", padx=(10, 0))

    app.analysis_status_label = ctk.CTkLabel(right_panel, text="Bereit", font=FIELD_FONT, anchor="w")
    app.analysis_status_label.grid(row=7, column=0, sticky="ew", padx=12, pady=(10, 4))

    app.analysis_result_text = ctk.CTkTextbox(right_panel, height=170, font=LOG_FONT)
    app.analysis_result_text.grid(row=8, column=0, sticky="nsew", padx=12, pady=(0, 12))

    app._refresh_analysis_committee_options()
    app._refresh_analysis_sessions()
