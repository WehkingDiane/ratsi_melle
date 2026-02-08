"""GUI launcher prototype for local data workflows."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import messagebox
from typing import Callable

import customtkinter as ctk
from CTkMenuBar import CTkMenuBar, CustomDropdownMenu


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

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class GuiLauncher:
    def __init__(self) -> None:
        self.root = ctk.CTk()
        self.root.title("Ratsinfo Melle - Developer GUI")
        self.root.geometry("1400x850")

        self.menubar = None
        self.log_text = None
        self.output_frame = None
        self.right_title = None
        self.right_content = None
        self.status_label = None
        self.run_button = None
        self.cancel_button = None
        self.run_preset_button = None
        self.validation_label = None
        self.export_frame = None

        self.selected_action = ctk.StringVar(
            value="Download sessions (raw, script)"
        )
        self.selected_preset = ctk.StringVar(value="Fetch + Build Local + Export")
        self.year_value = ctk.StringVar(value=str(datetime.now().year))
        self.months_value = ctk.StringVar(value="")
        self.verbose_mode = ctk.BooleanVar(value=False)
        self.export_db_path = ctk.StringVar(
            value="data/processed/local_index.sqlite"
        )
        self.export_output_path = ctk.StringVar(
            value="data/processed/analysis_batch.json"
        )
        self.export_committees = ctk.StringVar(value="")
        self.export_date_from = ctk.StringVar(value="")
        self.export_date_to = ctk.StringVar(value="")
        self.export_document_types = ctk.StringVar(value="")
        self.export_require_local_path = ctk.BooleanVar(value=False)
        self.export_include_text_extraction = ctk.BooleanVar(value=False)
        self.export_max_text_chars = ctk.StringVar(value="12000")

        self.spinner_running = False
        self.spinner_index = 0
        self.current_process: subprocess.Popen | None = None
        self.cancel_requested = False
        self.worker_running = False

        self.actions = {
            "Download sessions (raw, script)": ActionConfig(
                name="Download sessions (raw, script)",
                handler=self._run_fetch_sessions,
                renderer=self._render_fetch_summary,
            ),
            "Build local SQLite index (script)": ActionConfig(
                name="Build local SQLite index (script)",
                handler=self._run_build_index,
                renderer=self._render_index_summary,
            ),
            "Build online SQLite index (script)": ActionConfig(
                name="Build online SQLite index (script)",
                handler=self._run_build_online_index,
                renderer=self._render_index_summary,
            ),
            "Export analysis batch (script)": ActionConfig(
                name="Export analysis batch (script)",
                handler=self._run_export_analysis_batch,
                renderer=self._render_export_summary,
            ),
            "List committees (local index)": ActionConfig(
                name="List committees (local index)",
                handler=self._run_list_committees,
                renderer=self._render_committees,
            ),
            "Show Data Inventory (local)": ActionConfig(
                name="Show Data Inventory (local)",
                handler=self._run_data_inventory,
                renderer=self._render_inventory,
            ),
            "Show Data Structure (local)": ActionConfig(
                name="Show Data Structure (local)",
                handler=self._run_data_structure,
                renderer=self._render_structure,
            ),
        }
        self.presets = {
            "Fetch + Build Local + Export": [
                "Download sessions (raw, script)",
                "Build local SQLite index (script)",
                "Export analysis batch (script)",
            ],
            "Build Local + Export": [
                "Build local SQLite index (script)",
                "Export analysis batch (script)",
            ],
            "Build Online Index": [
                "Build online SQLite index (script)",
            ],
        }

        self._load_settings()
        self._build_ui()
        self._update_menubar_theme()
        self._bind_validation()
        self._update_dynamic_controls()
        self._update_run_state()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        self._build_header()
        self._build_controls()
        self._build_status()
        self._build_log()
        self._build_footer()

    def _build_header(self) -> None:
        self.menubar = CTkMenuBar(master=self.root)

        file_btn = self.menubar.add_cascade("File")
        file_dropdown = CustomDropdownMenu(widget=file_btn)
        file_dropdown.add_option("Clear log", self._clear_log)
        file_dropdown.add_separator()
        file_dropdown.add_option("Exit", self.root.quit)

        theme_btn = self.menubar.add_cascade("Theme")
        theme_dropdown = CustomDropdownMenu(widget=theme_btn)
        theme_dropdown.add_option("Light Mode", lambda: self._set_theme("Light"))
        theme_dropdown.add_option("Dark Mode", lambda: self._set_theme("Dark"))

        self.menubar.add_cascade("About", command=self._show_about)
        self.menubar.pack(fill="x")

    def _build_controls(self) -> None:
        frame = ctk.CTkFrame(self.root, fg_color="transparent")
        frame.pack(fill="x", padx=20, pady=12)
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(frame, text="Action:", font=LABEL_FONT).grid(
            row=0, column=0, sticky="w"
        )
        action_box = ctk.CTkComboBox(
            frame,
            variable=self.selected_action,
            values=list(self.actions.keys()),
            width=460,
            font=FIELD_FONT,
        )
        action_box.grid(row=1, column=0, sticky="w", pady=(0, 8))
        action_box.configure(command=lambda _value: self._on_action_changed())

        params_frame = ctk.CTkFrame(frame, fg_color="transparent")
        params_frame.grid(row=1, column=1, sticky="w", padx=(20, 0))

        ctk.CTkLabel(params_frame, text="Year:", font=FIELD_FONT).grid(
            row=0, column=0, sticky="w", padx=(0, 6)
        )
        ctk.CTkEntry(params_frame, textvariable=self.year_value, width=80).grid(
            row=0, column=1, sticky="w", padx=(0, 12)
        )
        ctk.CTkLabel(params_frame, text="Months (e.g. 5 6):", font=FIELD_FONT).grid(
            row=0, column=2, sticky="w", padx=(0, 6)
        )
        ctk.CTkEntry(params_frame, textvariable=self.months_value, width=140).grid(
            row=0, column=3, sticky="w"
        )

        ctk.CTkCheckBox(
            frame, text="Verbose", variable=self.verbose_mode, font=FIELD_FONT
        ).grid(row=1, column=2, sticky="w", padx=(20, 0))

        self.run_button = ctk.CTkButton(
            frame,
            text="Run",
            command=self._run_action,
            fg_color=B_R_BLUE,
            hover_color=HOVER_BLUE,
            font=BUTTON_FONT,
            height=36,
        )
        self.run_button.grid(row=1, column=3, sticky="w", padx=(20, 0))

        self.cancel_button = ctk.CTkButton(
            frame,
            text="Cancel",
            command=self._cancel_running_action,
            fg_color="#B91C1C",
            hover_color="#991B1B",
            font=BUTTON_FONT,
            height=36,
            state="disabled",
        )
        self.cancel_button.grid(row=1, column=4, sticky="w", padx=(10, 0))

        preset_frame = ctk.CTkFrame(frame, fg_color="transparent")
        preset_frame.grid(row=2, column=0, columnspan=5, sticky="w", pady=(8, 0))
        ctk.CTkLabel(preset_frame, text="Preset:", font=FIELD_FONT).pack(
            side="left", padx=(0, 6)
        )
        preset_box = ctk.CTkComboBox(
            preset_frame,
            variable=self.selected_preset,
            values=list(self.presets.keys()),
            width=300,
            font=FIELD_FONT,
        )
        preset_box.pack(side="left", padx=(0, 10))
        self.run_preset_button = ctk.CTkButton(
            preset_frame,
            text="Run Preset",
            command=self._run_selected_preset,
            fg_color="#0F766E",
            hover_color="#115E59",
            font=BUTTON_FONT,
            height=34,
        )
        self.run_preset_button.pack(side="left")

        self.export_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self.export_frame.grid(row=3, column=0, columnspan=5, sticky="ew", pady=(10, 0))
        self.export_frame.grid_columnconfigure(1, weight=1)
        self.export_frame.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(self.export_frame, text="DB Path:", font=FIELD_FONT).grid(
            row=0, column=0, sticky="w", padx=(0, 6), pady=(0, 6)
        )
        ctk.CTkEntry(
            self.export_frame, textvariable=self.export_db_path, font=FIELD_FONT
        ).grid(row=0, column=1, sticky="ew", padx=(0, 16), pady=(0, 6))

        ctk.CTkLabel(self.export_frame, text="Output:", font=FIELD_FONT).grid(
            row=0, column=2, sticky="w", padx=(0, 6), pady=(0, 6)
        )
        ctk.CTkEntry(
            self.export_frame, textvariable=self.export_output_path, font=FIELD_FONT
        ).grid(row=0, column=3, sticky="ew", pady=(0, 6))

        ctk.CTkLabel(
            self.export_frame, text="Committees (comma):", font=FIELD_FONT
        ).grid(row=1, column=0, sticky="w", padx=(0, 6), pady=(0, 6))
        ctk.CTkEntry(
            self.export_frame, textvariable=self.export_committees, font=FIELD_FONT
        ).grid(row=1, column=1, sticky="ew", padx=(0, 16), pady=(0, 6))

        ctk.CTkLabel(
            self.export_frame, text="Document types (comma):", font=FIELD_FONT
        ).grid(row=1, column=2, sticky="w", padx=(0, 6), pady=(0, 6))
        ctk.CTkEntry(
            self.export_frame, textvariable=self.export_document_types, font=FIELD_FONT
        ).grid(row=1, column=3, sticky="ew", pady=(0, 6))

        ctk.CTkLabel(self.export_frame, text="Date from:", font=FIELD_FONT).grid(
            row=2, column=0, sticky="w", padx=(0, 6), pady=(0, 6)
        )
        ctk.CTkEntry(
            self.export_frame, textvariable=self.export_date_from, font=FIELD_FONT
        ).grid(row=2, column=1, sticky="ew", padx=(0, 16), pady=(0, 6))

        ctk.CTkLabel(self.export_frame, text="Date to:", font=FIELD_FONT).grid(
            row=2, column=2, sticky="w", padx=(0, 6), pady=(0, 6)
        )
        ctk.CTkEntry(
            self.export_frame, textvariable=self.export_date_to, font=FIELD_FONT
        ).grid(row=2, column=3, sticky="ew", pady=(0, 6))

        ctk.CTkCheckBox(
            self.export_frame,
            text="Require local path",
            variable=self.export_require_local_path,
            font=FIELD_FONT,
        ).grid(row=3, column=0, sticky="w", pady=(0, 2))
        ctk.CTkCheckBox(
            self.export_frame,
            text="Include text extraction",
            variable=self.export_include_text_extraction,
            font=FIELD_FONT,
        ).grid(row=3, column=1, sticky="w", pady=(0, 2))
        ctk.CTkLabel(
            self.export_frame, text="Max text chars:", font=FIELD_FONT
        ).grid(row=3, column=2, sticky="w", padx=(0, 6), pady=(0, 2))
        ctk.CTkEntry(
            self.export_frame, textvariable=self.export_max_text_chars, width=160
        ).grid(row=3, column=3, sticky="w", pady=(0, 2))

        self.validation_label = ctk.CTkLabel(
            frame,
            text="",
            font=FIELD_FONT,
            text_color="#DC2626",
            anchor="w",
        )
        self.validation_label.grid(
            row=4, column=0, columnspan=5, sticky="ew", pady=(8, 0)
        )

    def _build_status(self) -> None:
        self.status_label = ctk.CTkLabel(
            self.root, text="Ready", height=24, anchor="w", font=FIELD_FONT
        )
        self.status_label.pack(fill="x", padx=20, pady=(0, 6))

    def _build_log(self) -> None:
        self.output_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.output_frame.pack(fill="both", expand=True, padx=20, pady=10)
        self.output_frame.grid_columnconfigure(0, weight=3)
        self.output_frame.grid_columnconfigure(1, weight=2)
        self.output_frame.grid_rowconfigure(0, weight=1)

        self.log_text = ctk.CTkTextbox(
            self.output_frame,
            wrap="word",
            font=LOG_FONT,
            border_width=1,
            corner_radius=6,
        )
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.log_text.configure(state="disabled")

        textbox = self.log_text._textbox
        textbox.tag_configure("error", foreground="#ef4444")
        textbox.tag_configure("warning", foreground="#f59e0b")
        textbox.tag_configure("info", foreground="#22c55e")
        textbox.tag_configure(
            "normal",
            foreground="white" if ctk.get_appearance_mode() == "Dark" else "black",
        )

        right_panel = ctk.CTkFrame(self.output_frame, corner_radius=8)
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.grid_rowconfigure(1, weight=1)
        right_panel.grid_columnconfigure(0, weight=1)

        self.right_title = ctk.CTkLabel(
            right_panel, text="Details", font=LABEL_FONT, anchor="w"
        )
        self.right_title.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))

        self.right_content = ctk.CTkScrollableFrame(right_panel)
        self.right_content.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self._render_placeholder()

    def _build_footer(self) -> None:
        frame = ctk.CTkFrame(self.root, fg_color="transparent")
        frame.pack(fill="x", padx=20, pady=(0, 16))

        ctk.CTkButton(
            frame,
            text="Clear Log",
            command=self._clear_log,
            fg_color="#374151",
            hover_color="#4b5563",
            font=BUTTON_FONT,
            height=34,
        ).pack(side="right")

        ctk.CTkButton(
            frame,
            text="Open Output Folder",
            command=self._open_output_folder,
            fg_color="#1D4ED8",
            hover_color="#1E40AF",
            font=BUTTON_FONT,
            height=34,
        ).pack(side="right", padx=(0, 10))

    def _set_theme(self, mode: str) -> None:
        ctk.set_appearance_mode(mode)
        self._update_menubar_theme()
        if self.log_text:
            self.log_text._textbox.tag_configure(
                "normal", foreground="black" if mode == "Light" else "white"
            )

    def _update_menubar_theme(self) -> None:
        appearance = ctk.get_appearance_mode()
        color = "#f5f5f5" if appearance == "Light" else "#000000"
        if self.menubar:
            self.menubar.configure(bg_color=color)

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About",
            "Developer GUI for Ratsinfo Melle.\n"
            "Prototype for running scripts and inspecting collected data.",
        )

    def _clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _on_close(self) -> None:
        self._save_settings()
        self.root.destroy()

    def _bind_validation(self) -> None:
        self.selected_action.trace_add("write", lambda *_: self._on_action_changed())
        self.selected_preset.trace_add("write", lambda *_: self._update_run_state())
        for var in (
            self.year_value,
            self.months_value,
            self.export_db_path,
            self.export_output_path,
            self.export_committees,
            self.export_date_from,
            self.export_date_to,
            self.export_document_types,
            self.export_max_text_chars,
        ):
            var.trace_add("write", lambda *_: self._update_run_state())
        for var in (
            self.verbose_mode,
            self.export_require_local_path,
            self.export_include_text_extraction,
        ):
            var.trace_add("write", lambda *_: self._update_run_state())

    def _on_action_changed(self) -> None:
        self._update_dynamic_controls()
        self._update_run_state()

    def _update_dynamic_controls(self) -> None:
        if not self.export_frame:
            return
        is_export = self.selected_action.get() == "Export analysis batch (script)"
        if is_export:
            self.export_frame.grid()
        else:
            self.export_frame.grid_remove()

    def _update_run_state(self) -> None:
        if self.worker_running or self.current_process is not None:
            if self.run_button:
                self.run_button.configure(state="disabled")
            if self.run_preset_button:
                self.run_preset_button.configure(state="disabled")
            if self.cancel_button:
                self.cancel_button.configure(state="normal")
            return

        is_valid, message = self._validate_selected_action()
        preset_valid, _preset_message = self._validate_selected_preset()
        if self.validation_label:
            self.validation_label.configure(text=message if not is_valid else "")
        if self.run_button:
            self.run_button.configure(state="normal" if is_valid else "disabled")
        if self.run_preset_button:
            self.run_preset_button.configure(state="normal" if preset_valid else "disabled")
        if self.cancel_button:
            self.cancel_button.configure(state="disabled")

    def _validate_selected_action(self) -> tuple[bool, str]:
        return self._validate_action_name(self.selected_action.get())

    def _validate_selected_preset(self) -> tuple[bool, str]:
        preset_name = self.selected_preset.get()
        action_names = self.presets.get(preset_name, [])
        if not action_names:
            return False, "Preset has no actions."
        for action_name in action_names:
            valid, message = self._validate_action_name(action_name)
            if not valid:
                return False, f"{action_name}: {message}"
        return True, ""

    def _validate_action_name(self, action_name: str) -> tuple[bool, str]:
        if action_name in {
            "Download sessions (raw, script)",
            "Build online SQLite index (script)",
        }:
            year = self.year_value.get().strip()
            if not (year.isdigit() and len(year) == 4):
                return False, "Year must be a 4-digit number."
            months_valid, month_error = self._validate_months(self.months_value.get())
            if not months_valid:
                return False, month_error

        if action_name == "Export analysis batch (script)":
            db_path = self.export_db_path.get().strip()
            output_path = self.export_output_path.get().strip()
            if not db_path:
                return False, "DB path is required."
            if not output_path:
                return False, "Output path is required."
            valid_from, err_from = self._validate_iso_date(self.export_date_from.get().strip())
            if not valid_from:
                return False, f"Date from: {err_from}"
            valid_to, err_to = self._validate_iso_date(self.export_date_to.get().strip())
            if not valid_to:
                return False, f"Date to: {err_to}"
            max_chars = self.export_max_text_chars.get().strip()
            if max_chars and not (max_chars.isdigit() and int(max_chars) >= 1):
                return False, "Max text chars must be an integer >= 1."

        return True, ""

    def _validate_months(self, value: str) -> tuple[bool, str]:
        if not value.strip():
            return True, ""
        for token in value.split():
            if not token.isdigit():
                return False, "Months must contain numbers separated by spaces."
            month = int(token)
            if month < 1 or month > 12:
                return False, "Months must be between 1 and 12."
        return True, ""

    def _validate_iso_date(self, value: str) -> tuple[bool, str]:
        if not value:
            return True, ""
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return True, ""
        except ValueError:
            return False, "expected format YYYY-MM-DD"

    def _run_action(self) -> None:
        valid, message = self._validate_selected_action()
        if not valid:
            self._append_log(f"[ERROR] {message}")
            self._update_run_state()
            return
        action = self.actions.get(self.selected_action.get())
        if not action:
            return
        self.cancel_requested = False
        self.worker_running = True
        self._start_spinner()
        self._set_status("Running...")
        self._update_run_state()
        thread = threading.Thread(target=self._run_worker, args=(action,), daemon=True)
        thread.start()

    def _run_worker(self, action: "ActionConfig") -> None:
        try:
            result = action.handler()
            self.root.after(0, lambda: self._render_action_result(action, result))
            result_status = result.get("status")
            if result_status == "ok":
                self._set_status("Done")
            elif result_status == "cancelled":
                self._set_status("Cancelled")
            else:
                self._set_status("Failed")
        except Exception as exc:  # pragma: no cover - UI safety
            self._append_log(f"[ERROR] {exc}")
            self._set_status("Failed")
        finally:
            self.current_process = None
            self.worker_running = False
            self._stop_spinner()
            self.root.after(0, self._update_run_state)

    def _run_script_command(self, cmd: list[str]) -> dict:
        self._append_log(f"[INFO] Running: {' '.join(cmd)}")
        process = subprocess.Popen(
            cmd,
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self.current_process = process
        self.root.after(0, self._update_run_state)

        assert process.stdout is not None
        last_line = ""
        line_count = 0
        for line in process.stdout:
            if self.cancel_requested and process.poll() is None:
                process.terminate()
            stripped = line.rstrip()
            if stripped:
                last_line = stripped
            self._append_log(stripped)
            line_count += 1
        process.wait()

        cancelled = self.cancel_requested and process.returncode not in (0, None)
        if cancelled:
            self._append_log("[WARNING] Process cancelled by user.")
        elif process.returncode != 0:
            self._append_log(f"[ERROR] Script exited with {process.returncode}")

        return {
            "status": "cancelled" if cancelled else ("ok" if process.returncode == 0 else "error"),
            "command": " ".join(cmd),
            "exit_code": process.returncode,
            "lines": line_count,
            "summary": last_line,
            "cancelled": cancelled,
        }

    def _cancel_running_action(self) -> None:
        self.cancel_requested = True
        process = self.current_process
        if process is not None and process.poll() is None:
            self._append_log("[WARNING] Cancellation requested...")
            try:
                process.terminate()
            except OSError as exc:
                self._append_log(f"[ERROR] Could not terminate process: {exc}")

    def _run_selected_preset(self) -> None:
        preset_name = self.selected_preset.get()
        action_names = self.presets.get(preset_name, [])
        valid, message = self._validate_selected_preset()
        if not valid:
            self._append_log(f"[ERROR] Preset blocked: {message}")
            self._update_run_state()
            return

        self.cancel_requested = False
        self.worker_running = True
        self._start_spinner()
        self._set_status("Running preset...")
        self._update_run_state()
        self._render_preset_progress(
            preset_name,
            [{"name": name, "status": "pending"} for name in action_names],
        )
        thread = threading.Thread(
            target=self._run_preset_worker,
            args=(preset_name, action_names),
            daemon=True,
        )
        thread.start()

    def _run_preset_worker(self, preset_name: str, action_names: list[str]) -> None:
        progress = [{"name": name, "status": "pending"} for name in action_names]
        for index, action_name in enumerate(action_names):
            if self.cancel_requested:
                progress[index]["status"] = "cancelled"
                break

            action = self.actions.get(action_name)
            if not action:
                progress[index]["status"] = "error"
                self._append_log(f"[ERROR] Preset action not found: {action_name}")
                break

            progress[index]["status"] = "running"
            self.root.after(0, lambda p=progress: self._render_preset_progress(preset_name, p))
            result = action.handler()
            status = result.get("status")
            if status == "ok":
                progress[index]["status"] = "done"
            elif status == "cancelled":
                progress[index]["status"] = "cancelled"
                break
            else:
                progress[index]["status"] = "error"
                break
            self.root.after(0, lambda p=progress: self._render_preset_progress(preset_name, p))

        self.current_process = None
        self.worker_running = False
        self._stop_spinner()
        if self.cancel_requested:
            self._set_status("Preset cancelled")
        elif any(entry["status"] == "error" for entry in progress):
            self._set_status("Preset failed")
        else:
            self._set_status("Preset done")
        self.root.after(0, lambda p=progress: self._render_preset_progress(preset_name, p))
        self.root.after(0, self._update_run_state)

    def _open_output_folder(self) -> None:
        output_raw = self.export_output_path.get().strip() or "data/processed/analysis_batch.json"
        output_path = Path(output_raw)
        if not output_path.is_absolute():
            output_path = (REPO_ROOT / output_path).resolve()
        folder = output_path.parent
        folder.mkdir(parents=True, exist_ok=True)

        try:
            if sys.platform.startswith("win"):
                os.startfile(str(folder))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)], cwd=str(REPO_ROOT))
            else:
                subprocess.Popen(["xdg-open", str(folder)], cwd=str(REPO_ROOT))
            self._append_log(f"[INFO] Opened folder: {folder}")
        except Exception as exc:  # pragma: no cover - depends on desktop session
            self._append_log(f"[ERROR] Could not open folder: {exc}")

    def _load_settings(self) -> None:
        if not SETTINGS_PATH.exists():
            return
        try:
            payload = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(payload, dict):
            return

        self.selected_action.set(str(payload.get("selected_action", self.selected_action.get())))
        self.selected_preset.set(str(payload.get("selected_preset", self.selected_preset.get())))
        self.year_value.set(str(payload.get("year_value", self.year_value.get())))
        self.months_value.set(str(payload.get("months_value", self.months_value.get())))
        self.verbose_mode.set(bool(payload.get("verbose_mode", self.verbose_mode.get())))
        self.export_db_path.set(str(payload.get("export_db_path", self.export_db_path.get())))
        self.export_output_path.set(
            str(payload.get("export_output_path", self.export_output_path.get()))
        )
        self.export_committees.set(
            str(payload.get("export_committees", self.export_committees.get()))
        )
        self.export_date_from.set(
            str(payload.get("export_date_from", self.export_date_from.get()))
        )
        self.export_date_to.set(str(payload.get("export_date_to", self.export_date_to.get())))
        self.export_document_types.set(
            str(payload.get("export_document_types", self.export_document_types.get()))
        )
        self.export_require_local_path.set(
            bool(payload.get("export_require_local_path", self.export_require_local_path.get()))
        )
        self.export_include_text_extraction.set(
            bool(
                payload.get(
                    "export_include_text_extraction",
                    self.export_include_text_extraction.get(),
                )
            )
        )
        self.export_max_text_chars.set(
            str(payload.get("export_max_text_chars", self.export_max_text_chars.get()))
        )

    def _save_settings(self) -> None:
        payload = {
            "selected_action": self.selected_action.get(),
            "selected_preset": self.selected_preset.get(),
            "year_value": self.year_value.get(),
            "months_value": self.months_value.get(),
            "verbose_mode": bool(self.verbose_mode.get()),
            "export_db_path": self.export_db_path.get(),
            "export_output_path": self.export_output_path.get(),
            "export_committees": self.export_committees.get(),
            "export_date_from": self.export_date_from.get(),
            "export_date_to": self.export_date_to.get(),
            "export_document_types": self.export_document_types.get(),
            "export_require_local_path": bool(self.export_require_local_path.get()),
            "export_include_text_extraction": bool(
                self.export_include_text_extraction.get()
            ),
            "export_max_text_chars": self.export_max_text_chars.get(),
        }
        try:
            SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            SETTINGS_PATH.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as exc:
            self._append_log(f"[ERROR] Could not save settings: {exc}")

    def _run_fetch_sessions(self) -> dict:
        script_path = REPO_ROOT / "scripts" / "fetch_sessions.py"
        if not script_path.exists():
            self._append_log("[ERROR] scripts/fetch_sessions.py not found")
            return {"status": "error", "message": "Script not found"}

        year = self.year_value.get().strip()
        if not year.isdigit():
            self._append_log("[ERROR] Year must be a number")
            return {"status": "error", "message": "Year invalid"}

        months = [m for m in self.months_value.get().split() if m.isdigit()]

        cmd = [sys.executable, str(script_path), year]
        if months:
            cmd.extend(["--months", *months])
        if self.verbose_mode.get():
            cmd.extend(["--log-level", "DEBUG"])
        return self._run_script_command(cmd)

    def _run_build_index(self) -> dict:
        script_path = REPO_ROOT / "scripts" / "build_local_index.py"
        if not script_path.exists():
            self._append_log("[ERROR] scripts/build_local_index.py not found")
            return {"status": "error", "message": "Script not found"}

        cmd = [sys.executable, str(script_path)]
        return self._run_script_command(cmd)

    def _run_build_online_index(self) -> dict:
        script_path = REPO_ROOT / "scripts" / "build_online_index_db.py"
        if not script_path.exists():
            self._append_log("[ERROR] scripts/build_online_index_db.py not found")
            return {"status": "error", "message": "Script not found"}

        year = self.year_value.get().strip()
        if not year.isdigit():
            self._append_log("[ERROR] Year must be a number")
            return {"status": "error", "message": "Year invalid"}

        months = [m for m in self.months_value.get().split() if m.isdigit()]

        cmd = [sys.executable, str(script_path), year]
        if months:
            cmd.extend(["--months", *months])
        if self.verbose_mode.get():
            cmd.extend(["--log-level", "DEBUG"])
        return self._run_script_command(cmd)

    def _run_data_inventory(self) -> dict:
        root = DATA_ROOT_DEFAULT
        if not root.exists():
            self._append_log("[ERROR] Data root not found")
            return {"status": "error", "message": "Data root not found"}

        file_count = 0
        dir_count = 0
        total_size = 0
        for path in root.rglob("*"):
            if path.is_dir():
                dir_count += 1
            else:
                file_count += 1
                total_size += path.stat().st_size

        size_mb = total_size / (1024 * 1024)
        self._append_log(f"[INFO] Data root: {root}")
        self._append_log(f"[INFO] Directories: {dir_count}")
        self._append_log(f"[INFO] Files: {file_count}")
        self._append_log(f"[INFO] Size: {size_mb:.2f} MB")
        return {
            "status": "ok",
            "root": str(root),
            "directories": dir_count,
            "files": file_count,
            "size_mb": size_mb,
        }

    def _run_export_analysis_batch(self) -> dict:
        script_path = REPO_ROOT / "scripts" / "export_analysis_batch.py"
        if not script_path.exists():
            self._append_log("[ERROR] scripts/export_analysis_batch.py not found")
            return {"status": "error", "message": "Script not found"}

        db_path = self.export_db_path.get().strip()
        output_path = self.export_output_path.get().strip()
        date_from = self.export_date_from.get().strip()
        date_to = self.export_date_to.get().strip()
        committees = [entry.strip() for entry in self.export_committees.get().split(",") if entry.strip()]
        doc_types = [entry.strip() for entry in self.export_document_types.get().split(",") if entry.strip()]
        max_chars = self.export_max_text_chars.get().strip() or "12000"

        cmd = [
            sys.executable,
            str(script_path),
            "--db-path",
            db_path,
            "--output",
            output_path,
        ]
        for committee in committees:
            cmd.extend(["--committee", committee])
        for doc_type in doc_types:
            cmd.extend(["--document-type", doc_type])
        if date_from:
            cmd.extend(["--date-from", date_from])
        if date_to:
            cmd.extend(["--date-to", date_to])
        if self.export_require_local_path.get():
            cmd.append("--require-local-path")
        if self.export_include_text_extraction.get():
            cmd.append("--include-text-extraction")
            cmd.extend(["--max-text-chars", max_chars])

        result = self._run_script_command(cmd)
        output_resolved = (
            (REPO_ROOT / output_path).resolve()
            if not Path(output_path).is_absolute()
            else Path(output_path)
        )
        result["output"] = str(output_resolved)
        result["filter_summary"] = self._collect_export_filter_summary()
        result["document_count"] = self._count_export_documents(output_resolved)
        return result

    def _collect_export_filter_summary(self) -> str:
        parts: list[str] = []
        committees = [entry.strip() for entry in self.export_committees.get().split(",") if entry.strip()]
        doc_types = [entry.strip() for entry in self.export_document_types.get().split(",") if entry.strip()]
        if committees:
            parts.append(f"committee={','.join(committees)}")
        if doc_types:
            parts.append(f"type={','.join(doc_types)}")
        if self.export_date_from.get().strip():
            parts.append(f"from={self.export_date_from.get().strip()}")
        if self.export_date_to.get().strip():
            parts.append(f"to={self.export_date_to.get().strip()}")
        if self.export_require_local_path.get():
            parts.append("require_local_path=true")
        if self.export_include_text_extraction.get():
            parts.append(
                "text_extraction=true,max_text_chars="
                + (self.export_max_text_chars.get().strip() or "12000")
            )
        return "; ".join(parts) if parts else "none"

    def _count_export_documents(self, path: Path) -> int | None:
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        documents = payload.get("documents") if isinstance(payload, dict) else None
        if not isinstance(documents, list):
            return None
        return len(documents)

    def _run_list_committees(self) -> dict:
        db_path = REPO_ROOT / "data" / "processed" / "local_index.sqlite"
        if not db_path.exists():
            self._append_log("[ERROR] SQLite index not found. Run build_local_index.py first.")
            return {"status": "error", "message": "local_index.sqlite not found"}

        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.execute(
                    "SELECT DISTINCT committee FROM sessions WHERE committee IS NOT NULL "
                    "AND committee != '' ORDER BY committee"
                )
                committees = [row[0] for row in cursor.fetchall()]
        except sqlite3.Error as exc:
            self._append_log(f"[ERROR] SQLite error: {exc}")
            return {"status": "error", "message": str(exc)}

        self._append_log(f"[INFO] Committees found: {len(committees)}")
        return {"status": "ok", "count": len(committees), "committees": committees}

    def _run_data_structure(self) -> dict:
        root = DATA_ROOT_DEFAULT
        if not root.exists():
            self._append_log("[ERROR] Data root not found")
            return {"status": "error", "message": "Data root not found"}

        self._append_log("[INFO] Data structure loaded")
        return {"status": "ok", "root": str(root)}

    def _append_log(self, message: str) -> None:
        def append() -> None:
            timestamp = datetime.now().strftime("%H:%M:%S")
            line = f"[{timestamp}] {message}"

            self.log_text.configure(state="normal")
            tag = self._detect_tag(message)
            self.log_text.insert("end", line + "\n", tag)
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

        self.root.after(0, append)

    def _detect_tag(self, message: str) -> str:
        lowered = message.lower()
        if "[error]" in lowered or "error" in lowered:
            return "error"
        if "[warn" in lowered or "warning" in lowered:
            return "warning"
        if "[info]" in lowered:
            return "info"
        return "normal"

    def _set_status(self, message: str) -> None:
        self.status_label.after(0, lambda: self.status_label.configure(text=message))

    def _start_spinner(self) -> None:
        self.spinner_running = True
        self.spinner_index = 0
        self._animate_spinner()

    def _stop_spinner(self) -> None:
        self.spinner_running = False

    def _animate_spinner(self) -> None:
        if not self.spinner_running:
            return
        frame = SPINNER_FRAMES[self.spinner_index % len(SPINNER_FRAMES)]
        self.status_label.configure(text=f"{frame} Running")
        self.spinner_index += 1
        self.status_label.after(120, self._animate_spinner)

    def run(self) -> None:
        self.root.mainloop()

    def _render_action_result(self, action: "ActionConfig", result: dict | None) -> None:
        if action.renderer:
            action.renderer(result or {})
        else:
            self._render_placeholder()

    def _render_placeholder(self) -> None:
        self._clear_right_panel()
        ctk.CTkLabel(
            self.right_content,
            text="No details yet. Run an action to see results here.",
            font=FIELD_FONT,
            wraplength=360,
            justify="left",
        ).pack(anchor="w", pady=8)

    def _clear_right_panel(self) -> None:
        for child in self.right_content.winfo_children():
            child.destroy()

    def _render_fetch_summary(self, result: dict) -> None:
        self.right_title.configure(text="Fetch Summary")
        self._clear_right_panel()
        self._render_kv("Command", result.get("command", "-"))
        self._render_kv("Exit Code", result.get("exit_code", "-"))
        self._render_kv("Output Lines", result.get("lines", "-"))

    def _render_inventory(self, result: dict) -> None:
        self.right_title.configure(text="Data Inventory")
        self._clear_right_panel()
        self._render_kv("Root", result.get("root", "-"))
        self._render_kv("Directories", result.get("directories", "-"))
        self._render_kv("Files", result.get("files", "-"))
        size = result.get("size_mb")
        self._render_kv("Size (MB)", f"{size:.2f}" if isinstance(size, float) else "-")

    def _render_structure(self, result: dict) -> None:
        self.right_title.configure(text="Data Structure")
        self._clear_right_panel()
        root_value = result.get("root")
        if not root_value:
            self._render_kv("Root", "-")
            self._render_list(["(no data root found)"])
            return

        root = Path(root_value)
        self._render_kv("Root", root)
        if not root.exists():
            self._render_list(["(no data root found)"])
            return

        self._render_collapsible_tree(root, max_depth=3, max_entries=200)

    def _render_collapsible_tree(
        self, root: Path, max_depth: int, max_entries: int
    ) -> None:
        count = 0

        def add_node(parent: ctk.CTkFrame, path: Path, depth: int) -> None:
            nonlocal count
            if count >= max_entries or depth > max_depth:
                return
            if not path.is_dir():
                return

            node_frame = ctk.CTkFrame(parent, fg_color="transparent")
            node_frame.pack(fill="x", pady=2)

            row = ctk.CTkFrame(node_frame, fg_color="transparent")
            row.pack(fill="x")

            indent = 12 * depth
            toggle = ctk.CTkButton(
                row,
                text="+",
                width=28,
                height=24,
                fg_color="#334155",
                hover_color="#475569",
                corner_radius=6,
            )
            toggle.pack(side="left", padx=(indent, 6))

            label = ctk.CTkLabel(row, text=path.name, font=FIELD_FONT, anchor="w")
            label.pack(side="left", fill="x", expand=True)

            children_frame = ctk.CTkFrame(node_frame, fg_color="transparent")
            children_frame.pack(fill="x")
            children_frame.pack_forget()

            def toggle_children() -> None:
                nonlocal count
                if children_frame.winfo_ismapped():
                    children_frame.pack_forget()
                    toggle.configure(text="+")
                    return

                toggle.configure(text="-")
                if children_frame.winfo_children():
                    children_frame.pack(fill="x")
                    return

                try:
                    entries = sorted(
                        path.iterdir(), key=lambda p: (p.is_file(), p.name.lower())
                    )
                except PermissionError:
                    entries = []

                for entry in entries:
                    if count >= max_entries:
                        break
                    if entry.is_dir():
                        add_node(children_frame, entry, depth + 1)
                    else:
                        file_row = ctk.CTkFrame(children_frame, fg_color="transparent")
                        file_row.pack(fill="x", pady=1)
                        ctk.CTkLabel(
                            file_row,
                            text=entry.name,
                            font=FIELD_FONT,
                            anchor="w",
                        ).pack(side="left", padx=(12 * (depth + 1) + 34, 0))
                        count += 1

                if not children_frame.winfo_children():
                    empty_row = ctk.CTkLabel(
                        children_frame,
                        text="(leer)",
                        font=FIELD_FONT,
                        anchor="w",
                    )
                    empty_row.pack(anchor="w", padx=(12 * (depth + 1) + 34, 0))
                children_frame.pack(fill="x")

            toggle.configure(command=toggle_children)
            label.bind("<Button-1>", lambda _e: toggle_children())

            count += 1

        add_node(self.right_content, root, 0)
        if count >= max_entries:
            ctk.CTkLabel(
                self.right_content,
                text="... (truncated)",
                font=FIELD_FONT,
                anchor="w",
            ).pack(anchor="w", pady=6)

    def _render_index_summary(self, result: dict) -> None:
        self.right_title.configure(text="Index Summary")
        self._clear_right_panel()
        self._render_kv("Command", result.get("command", "-"))
        self._render_kv("Exit Code", result.get("exit_code", "-"))
        self._render_kv("Output Lines", result.get("lines", "-"))
        self._render_kv("Summary", result.get("summary", "-"))

    def _render_export_summary(self, result: dict) -> None:
        self.right_title.configure(text="Export Summary")
        self._clear_right_panel()
        self._render_kv("Command", result.get("command", "-"))
        self._render_kv("Exit Code", result.get("exit_code", "-"))
        self._render_kv("Output Lines", result.get("lines", "-"))
        self._render_kv("Summary", result.get("summary", "-"))
        self._render_kv("Document Count", result.get("document_count", "-"))
        self._render_kv("Filters", result.get("filter_summary", "none"))
        self._render_kv("Output File", result.get("output", "-"))

    def _render_preset_progress(self, preset_name: str, steps: list[dict[str, str]]) -> None:
        self.right_title.configure(text="Preset Progress")
        self._clear_right_panel()
        self._render_kv("Preset", preset_name)
        for step in steps:
            name = step.get("name", "-")
            status = step.get("status", "-")
            self._render_kv(name, status)

    def _render_committees(self, result: dict) -> None:
        self.right_title.configure(text="Committees")
        self._clear_right_panel()
        self._render_kv("Count", result.get("count", "-"))
        committees = result.get("committees", [])
        self._render_list(committees if isinstance(committees, list) else [])

    def _render_kv(self, label: str, value: object) -> None:
        row = ctk.CTkFrame(self.right_content, fg_color="transparent")
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(row, text=label, font=FIELD_FONT, anchor="w").pack(
            side="left"
        )
        ctk.CTkLabel(
            row, text=str(value), font=FIELD_FONT, anchor="e", justify="right"
        ).pack(side="right")

    def _render_list(self, items: list[str]) -> None:
        if not items:
            ctk.CTkLabel(
                self.right_content, text="(no entries)", font=FIELD_FONT
            ).pack(anchor="w", pady=6)
            return
        for item in items:
            ctk.CTkLabel(
                self.right_content, text=f"- {item}", font=FIELD_FONT, anchor="w"
            ).pack(anchor="w")


@dataclass(frozen=True)
class ActionConfig:
    name: str
    handler: Callable[[], dict]
    renderer: Callable[[dict], None] | None = None


def main() -> None:
    GuiLauncher().run()


if __name__ == "__main__":
    main()
