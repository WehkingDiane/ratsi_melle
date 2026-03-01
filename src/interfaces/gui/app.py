"""GUI launcher for data workflows and analysis preparation."""

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

from src.analysis.analysis_context import build_analysis_markdown, enrich_documents_for_analysis
from src.version import __version__

from .config import (
    BUTTON_FONT,
    DATA_ROOT_DEFAULT,
    FIELD_FONT,
    LABEL_FONT,
    REPO_ROOT,
    SETTINGS_PATH,
    SPINNER_FRAMES,
    configure_theme,
)
from .services.analysis_store import AnalysisStore, SessionFilters
from .services.script_runner import ScriptRunner
from .views import analysis_view, data_tools_view, service_view, settings_view


configure_theme()


@dataclass(frozen=True)
class ActionConfig:
    name: str
    handler: Callable[[], dict]
    renderer: Callable[[dict], None] | None = None


@dataclass(frozen=True)
class ViewConfig:
    key: str
    label: str
    builder: Callable[[ctk.CTkFrame], None]


class GuiLauncher:
    def __init__(self) -> None:
        self.root = ctk.CTk()
        self.root.title("Ratsinfo Melle - Developer GUI")
        self.root.geometry("1500x900")

        self.menubar: CTkMenuBar | None = None

        self.selected_action = ctk.StringVar(value="Download sessions (raw, script)")
        self.selected_preset = ctk.StringVar(value="Fetch + Build Local + Export")
        self.year_value = ctk.StringVar(value=str(datetime.now().year))
        self.months_value = ctk.StringVar(value="")
        self.verbose_mode = ctk.BooleanVar(value=False)

        self.export_db_path = ctk.StringVar(value="data/processed/local_index.sqlite")
        self.export_output_path = ctk.StringVar(value="data/processed/analysis_batch.json")
        self.export_committees = ctk.StringVar(value="")
        self.export_date_from = ctk.StringVar(value="")
        self.export_date_to = ctk.StringVar(value="")
        self.export_document_types = ctk.StringVar(value="")
        self.export_require_local_path = ctk.BooleanVar(value=False)
        self.export_include_text_extraction = ctk.BooleanVar(value=False)
        self.export_max_text_chars = ctk.StringVar(value="12000")
        self.export_field_defaults = {
            "db_path": "data/processed/local_index.sqlite",
            "output_path": "data/processed/analysis_batch.json",
            "committees": "Rat, Ausschuss fuer Finanzen",
            "date_from": "2026-01-01",
            "date_to": "2026-12-31",
            "document_types": "vorlage, beschlussvorlage, protokoll",
            "max_text_chars": "12000",
        }

        self.current_view_key = "data_tools"
        self.sidebar_visible = True
        self.sidebar_frame: ctk.CTkFrame | None = None
        self.content_host: ctk.CTkFrame | None = None
        self.top_title_label: ctk.CTkLabel | None = None
        self.view_buttons: dict[str, ctk.CTkButton] = {}
        self.view_frames: dict[str, ctk.CTkFrame] = {}
        self.view_registry: dict[str, ViewConfig] = {}

        self.log_text: ctk.CTkTextbox | None = None
        self.output_frame: ctk.CTkFrame | None = None
        self.right_title: ctk.CTkLabel | None = None
        self.right_content: ctk.CTkScrollableFrame | None = None
        self.status_label: ctk.CTkLabel | None = None
        self.run_button: ctk.CTkButton | None = None
        self.cancel_button: ctk.CTkButton | None = None
        self.run_preset_button: ctk.CTkButton | None = None
        self.validation_label: ctk.CTkLabel | None = None
        self.export_frame: ctk.CTkFrame | None = None

        self.analysis_session_list_frame: ctk.CTkScrollableFrame | None = None
        self.analysis_tops_frame: ctk.CTkScrollableFrame | None = None
        self.analysis_result_text: ctk.CTkTextbox | None = None
        self.analysis_status_label: ctk.CTkLabel | None = None
        self.analysis_selected_session_label: ctk.CTkLabel | None = None
        self.analysis_prompt_box: ctk.CTkTextbox | None = None
        self.analysis_committee_box: ctk.CTkComboBox | None = None

        self.analysis_date_from = ctk.StringVar(value="")
        self.analysis_date_to = ctk.StringVar(value="")
        self.analysis_committee = ctk.StringVar(value="")
        self.analysis_search = ctk.StringVar(value="")
        self.analysis_past_only = ctk.BooleanVar(value=True)
        self.analysis_scope = ctk.StringVar(value="session")
        self.analysis_prompt_value = (
            "Erstelle eine journalistische, neutrale Zusammenfassung. "
            "Nenne Kernthemen, Entscheidungen und offene Punkte."
        )

        self.analysis_sessions: list[dict] = []
        self.analysis_top_vars: dict[str, ctk.BooleanVar] = {}
        self.analysis_current_session: dict | None = None

        self.spinner_running = False
        self.spinner_index = 0
        self.current_process: subprocess.Popen | None = None
        self.cancel_requested = False
        self.worker_running = False
        self.script_runner = ScriptRunner(REPO_ROOT)
        self.analysis_store = AnalysisStore()

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
        self._build_menubar()

        topbar = ctk.CTkFrame(self.root, corner_radius=0)
        topbar.pack(fill="x")
        ctk.CTkButton(
            topbar,
            text="Menu",
            width=38,
            command=self._toggle_sidebar,
            fg_color="#334155",
            hover_color="#475569",
            font=BUTTON_FONT,
        ).pack(side="left", padx=12, pady=10)
        self.top_title_label = ctk.CTkLabel(topbar, text="", font=LABEL_FONT, anchor="w")
        self.top_title_label.pack(side="left", padx=(2, 8), pady=10)

        body = ctk.CTkFrame(self.root, fg_color="transparent")
        body.pack(fill="both", expand=True)

        self.sidebar_frame = ctk.CTkFrame(body, width=260, corner_radius=0)
        self.sidebar_frame.pack(side="left", fill="y")
        self.sidebar_frame.pack_propagate(False)

        self.content_host = ctk.CTkFrame(body, fg_color="transparent")
        self.content_host.pack(side="left", fill="both", expand=True)

        self._register_views()
        self._build_sidebar()
        self._switch_view(self.current_view_key)

    def _build_menubar(self) -> None:
        self.menubar = CTkMenuBar(master=self.root)

        file_btn = self.menubar.add_cascade("File")
        file_dropdown = CustomDropdownMenu(widget=file_btn)
        file_dropdown.add_option("Clear log", self._clear_log)
        file_dropdown.add_separator()
        file_dropdown.add_option("Exit", self._on_close)

        theme_btn = self.menubar.add_cascade("Theme")
        theme_dropdown = CustomDropdownMenu(widget=theme_btn)
        theme_dropdown.add_option("Light Mode", lambda: self._set_theme("Light"))
        theme_dropdown.add_option("Dark Mode", lambda: self._set_theme("Dark"))

        self.menubar.add_cascade("About", command=self._show_about)
        self.menubar.pack(fill="x")

    def _register_views(self) -> None:
        self.view_registry = {
            "data_tools": ViewConfig(
                key="data_tools",
                label="Daten-Tools",
                builder=self._build_data_tools_view,
            ),
            "analysis": ViewConfig(
                key="analysis",
                label="Journalistische Analyse",
                builder=self._build_analysis_view,
            ),
            "settings": ViewConfig(
                key="settings",
                label="Settings",
                builder=self._build_settings_view,
            ),
            "service": ViewConfig(
                key="service",
                label="Service",
                builder=self._build_service_view,
            ),
        }
        if self.current_view_key not in self.view_registry:
            self.current_view_key = "data_tools"

    def _build_sidebar(self) -> None:
        if not self.sidebar_frame:
            return
        for child in self.sidebar_frame.winfo_children():
            child.destroy()

        ctk.CTkLabel(self.sidebar_frame, text="Views", font=LABEL_FONT).pack(
            anchor="w", padx=14, pady=(14, 10)
        )

        self.view_buttons.clear()
        for key, view in self.view_registry.items():
            btn = ctk.CTkButton(
                self.sidebar_frame,
                text=view.label,
                anchor="w",
                fg_color="#1F2937",
                hover_color="#374151",
                font=FIELD_FONT,
                command=lambda item=key: self._switch_view(item),
            )
            btn.pack(fill="x", padx=10, pady=4)
            self.view_buttons[key] = btn

    def _switch_view(self, view_key: str) -> None:
        if view_key not in self.view_registry or not self.content_host:
            return

        if view_key not in self.view_frames:
            frame = ctk.CTkFrame(self.content_host, fg_color="transparent")
            self.view_frames[view_key] = frame
            self.view_registry[view_key].builder(frame)

        for key, frame in self.view_frames.items():
            if key == view_key:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()

        self.current_view_key = view_key
        if self.top_title_label:
            self.top_title_label.configure(text=self.view_registry[view_key].label)

        for key, btn in self.view_buttons.items():
            if key == view_key:
                btn.configure(fg_color="#0F766E", hover_color="#115E59")
            else:
                btn.configure(fg_color="#1F2937", hover_color="#374151")

        if view_key == "analysis":
            self._refresh_analysis_committee_options()
            self._refresh_analysis_sessions()

    def _toggle_sidebar(self) -> None:
        if not self.sidebar_frame:
            return
        self.sidebar_visible = not self.sidebar_visible
        if self.sidebar_visible:
            self.sidebar_frame.pack(side="left", fill="y")
        else:
            self.sidebar_frame.pack_forget()

    def _build_data_tools_view(self, parent: ctk.CTkFrame) -> None:
        data_tools_view.build_data_tools_view(self, parent)

    def _build_controls(self, parent: ctk.CTkFrame) -> None:
        data_tools_view.build_controls(self, parent)

    def _build_status(self, parent: ctk.CTkFrame) -> None:
        data_tools_view.build_status(self, parent)

    def _build_log(self, parent: ctk.CTkFrame) -> None:
        data_tools_view.build_log(self, parent)

    def _build_footer(self, parent: ctk.CTkFrame) -> None:
        data_tools_view.build_footer(self, parent)

    def _build_analysis_view(self, parent: ctk.CTkFrame) -> None:
        analysis_view.build_analysis_view(self, parent)

    def _build_settings_view(self, parent: ctk.CTkFrame) -> None:
        settings_view.build_settings_view(self, parent)

    def _build_service_view(self, parent: ctk.CTkFrame) -> None:
        service_view.build_service_view(self, parent)

    def _set_theme(self, mode: str) -> None:
        ctk.set_appearance_mode(mode)
        self._update_menubar_theme()
        if self.log_text:
            self.log_text._textbox.tag_configure("normal", foreground="black" if mode == "Light" else "white")

    def _update_menubar_theme(self) -> None:
        appearance = ctk.get_appearance_mode()
        color = "#f5f5f5" if appearance == "Light" else "#000000"
        if self.menubar:
            self.menubar.configure(bg_color=color)

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About",
            "Developer GUI for Ratsinfo Melle.\n"
            f"Version: {__version__}\n"
            "Includes data tooling and analysis preparation view.",
        )

    def _clear_log(self) -> None:
        if not self.log_text:
            return
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
            self.analysis_date_from,
            self.analysis_date_to,
            self.analysis_search,
        ):
            var.trace_add("write", lambda *_: self._update_run_state())
        for var in (
            self.verbose_mode,
            self.export_require_local_path,
            self.export_include_text_extraction,
            self.analysis_past_only,
        ):
            var.trace_add("write", lambda *_: self._update_run_state())

    def _on_action_changed(self) -> None:
        self._apply_export_field_defaults()
        self._update_dynamic_controls()
        self._update_run_state()

    def _apply_export_field_defaults(self) -> None:
        if self.selected_action.get() != "Export analysis batch (script)":
            return

        if not self.export_db_path.get().strip():
            self.export_db_path.set(self.export_field_defaults["db_path"])
        if not self.export_output_path.get().strip():
            self.export_output_path.set(self.export_field_defaults["output_path"])
        if not self.export_committees.get().strip():
            self.export_committees.set(self.export_field_defaults["committees"])
        if not self.export_date_from.get().strip():
            self.export_date_from.set(self.export_field_defaults["date_from"])
        if not self.export_date_to.get().strip():
            self.export_date_to.set(self.export_field_defaults["date_to"])
        if not self.export_document_types.get().strip():
            self.export_document_types.set(self.export_field_defaults["document_types"])
        if not self.export_max_text_chars.get().strip():
            self.export_max_text_chars.set(self.export_field_defaults["max_text_chars"])

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
        if action_name in {"Download sessions (raw, script)", "Build online SQLite index (script)"}:
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

    def _run_worker(self, action: ActionConfig) -> None:
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
        except Exception as exc:  # pragma: no cover
            self._append_log(f"[ERROR] {exc}")
            self._set_status("Failed")
        finally:
            self.current_process = None
            self.worker_running = False
            self._stop_spinner()
            self.root.after(0, self._update_run_state)

    def _run_script_command(self, cmd: list[str]) -> dict:
        self._append_log(f"[INFO] Running: {' '.join(cmd)}")
        result = self.script_runner.run(
            cmd,
            on_line=self._append_log,
            is_cancel_requested=lambda: self.cancel_requested,
            on_process_start=self._on_process_started,
            on_process_done=self._on_process_done,
        )
        cancelled = bool(result.cancelled)
        if cancelled:
            self._append_log("[WARNING] Process cancelled by user.")
        elif result.exit_code != 0:
            self._append_log(f"[ERROR] Script exited with {result.exit_code}")
        return result.to_dict()

    def _on_process_started(self, process: subprocess.Popen) -> None:
        self.current_process = process
        self.root.after(0, self._update_run_state)

    def _on_process_done(self) -> None:
        self.current_process = None

    def _cancel_running_action(self) -> None:
        self.cancel_requested = True
        if self.current_process is not None and self.current_process.poll() is None:
            self._append_log("[WARNING] Cancellation requested...")
            try:
                self.script_runner.cancel()
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
        self._render_preset_progress(preset_name, [{"name": name, "status": "pending"} for name in action_names])

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

    def _run_fetch_sessions(self) -> dict:
        script_path = REPO_ROOT / "scripts" / "fetch_sessions.py"
        if not script_path.exists():
            self._append_log("[ERROR] scripts/fetch_sessions.py not found")
            return {"status": "error", "message": "Script not found"}

        year = self.year_value.get().strip()
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
        output_resolved = (REPO_ROOT / output_path).resolve() if not Path(output_path).is_absolute() else Path(output_path)
        result["output"] = str(output_resolved)
        result["filter_summary"] = self._collect_export_filter_summary()
        result["document_count"] = self._count_export_documents(output_resolved)
        return result

    def _run_list_committees(self) -> dict:
        db_path = self._resolve_db_path(self.export_db_path.get().strip())
        if not db_path.exists():
            self._append_log("[ERROR] SQLite index not found.")
            return {"status": "error", "message": "local_index.sqlite not found"}

        try:
            committees = self.analysis_store.list_committees(db_path)
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
            parts.append("text_extraction=true,max_text_chars=" + (self.export_max_text_chars.get().strip() or "12000"))
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

    def _open_output_folder(self) -> None:
        output_raw = self.export_output_path.get().strip() or "data/processed/analysis_batch.json"
        output_path = self._resolve_db_path(output_raw)
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
        except Exception as exc:  # pragma: no cover
            self._append_log(f"[ERROR] Could not open folder: {exc}")

    def _resolve_db_path(self, value: str) -> Path:
        raw = value.strip()
        path = Path(raw)
        if path.is_absolute():
            return path
        return (REPO_ROOT / path).resolve()

    def _load_settings(self) -> None:
        if not SETTINGS_PATH.exists():
            return
        try:
            payload = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(payload, dict):
            return

        self.current_view_key = str(payload.get("current_view_key", self.current_view_key))
        self.selected_action.set(str(payload.get("selected_action", self.selected_action.get())))
        self.selected_preset.set(str(payload.get("selected_preset", self.selected_preset.get())))
        self.year_value.set(str(payload.get("year_value", self.year_value.get())))
        self.months_value.set(str(payload.get("months_value", self.months_value.get())))
        self.verbose_mode.set(bool(payload.get("verbose_mode", self.verbose_mode.get())))
        self.export_db_path.set(str(payload.get("export_db_path", self.export_db_path.get())))
        self.export_output_path.set(str(payload.get("export_output_path", self.export_output_path.get())))
        self.export_committees.set(str(payload.get("export_committees", self.export_committees.get())))
        self.export_date_from.set(str(payload.get("export_date_from", self.export_date_from.get())))
        self.export_date_to.set(str(payload.get("export_date_to", self.export_date_to.get())))
        self.export_document_types.set(str(payload.get("export_document_types", self.export_document_types.get())))
        self.export_require_local_path.set(bool(payload.get("export_require_local_path", self.export_require_local_path.get())))
        self.export_include_text_extraction.set(
            bool(payload.get("export_include_text_extraction", self.export_include_text_extraction.get()))
        )
        self.export_max_text_chars.set(str(payload.get("export_max_text_chars", self.export_max_text_chars.get())))

        self.analysis_date_from.set(str(payload.get("analysis_date_from", self.analysis_date_from.get())))
        self.analysis_date_to.set(str(payload.get("analysis_date_to", self.analysis_date_to.get())))
        self.analysis_committee.set(str(payload.get("analysis_committee", self.analysis_committee.get())))
        self.analysis_search.set(str(payload.get("analysis_search", self.analysis_search.get())))
        self.analysis_past_only.set(bool(payload.get("analysis_past_only", self.analysis_past_only.get())))
        self.analysis_scope.set(str(payload.get("analysis_scope", self.analysis_scope.get())))
        self.analysis_prompt_value = str(payload.get("analysis_prompt", self.analysis_prompt_value))

    def _save_settings(self) -> None:
        prompt_text = ""
        if self.analysis_prompt_box:
            prompt_text = self.analysis_prompt_box.get("1.0", "end").strip()

        payload = {
            "current_view_key": self.current_view_key,
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
            "export_include_text_extraction": bool(self.export_include_text_extraction.get()),
            "export_max_text_chars": self.export_max_text_chars.get(),
            "analysis_date_from": self.analysis_date_from.get(),
            "analysis_date_to": self.analysis_date_to.get(),
            "analysis_committee": self.analysis_committee.get(),
            "analysis_search": self.analysis_search.get(),
            "analysis_past_only": bool(self.analysis_past_only.get()),
            "analysis_scope": self.analysis_scope.get(),
            "analysis_prompt": prompt_text,
        }
        try:
            SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            SETTINGS_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            self._append_log(f"[ERROR] Could not save settings: {exc}")

    def _append_log(self, message: str) -> None:
        if not self.log_text:
            return

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
        if self.status_label:
            self.status_label.after(0, lambda: self.status_label.configure(text=message))

    def _start_spinner(self) -> None:
        self.spinner_running = True
        self.spinner_index = 0
        self._animate_spinner()

    def _stop_spinner(self) -> None:
        self.spinner_running = False

    def _animate_spinner(self) -> None:
        if not self.spinner_running or not self.status_label:
            return
        frame = SPINNER_FRAMES[self.spinner_index % len(SPINNER_FRAMES)]
        self.status_label.configure(text=f"{frame} Running")
        self.spinner_index += 1
        self.status_label.after(120, self._animate_spinner)

    def _render_action_result(self, action: ActionConfig, result: dict | None) -> None:
        if action.renderer:
            action.renderer(result or {})
        else:
            self._render_placeholder()

    def _render_placeholder(self) -> None:
        if not self.right_content:
            return
        self._clear_right_panel()
        ctk.CTkLabel(
            self.right_content,
            text="No details yet. Run an action to see results here.",
            font=FIELD_FONT,
            wraplength=360,
            justify="left",
        ).pack(anchor="w", pady=8)

    def _clear_right_panel(self) -> None:
        if not self.right_content:
            return
        for child in self.right_content.winfo_children():
            child.destroy()

    def _render_fetch_summary(self, result: dict) -> None:
        if not self.right_title:
            return
        self.right_title.configure(text="Fetch Summary")
        self._clear_right_panel()
        self._render_kv("Command", result.get("command", "-"))
        self._render_kv("Exit Code", result.get("exit_code", "-"))
        self._render_kv("Output Lines", result.get("lines", "-"))

    def _render_inventory(self, result: dict) -> None:
        if not self.right_title:
            return
        self.right_title.configure(text="Data Inventory")
        self._clear_right_panel()
        self._render_kv("Root", result.get("root", "-"))
        self._render_kv("Directories", result.get("directories", "-"))
        self._render_kv("Files", result.get("files", "-"))
        size = result.get("size_mb")
        self._render_kv("Size (MB)", f"{size:.2f}" if isinstance(size, float) else "-")

    def _render_structure(self, result: dict) -> None:
        if not self.right_title:
            return
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

    def _render_collapsible_tree(self, root: Path, max_depth: int, max_entries: int) -> None:
        if not self.right_content:
            return
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
                    entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
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
                        ctk.CTkLabel(file_row, text=entry.name, font=FIELD_FONT, anchor="w").pack(
                            side="left", padx=(12 * (depth + 1) + 34, 0)
                        )
                        count += 1

                if not children_frame.winfo_children():
                    ctk.CTkLabel(
                        children_frame,
                        text="(leer)",
                        font=FIELD_FONT,
                        anchor="w",
                    ).pack(anchor="w", padx=(12 * (depth + 1) + 34, 0))
                children_frame.pack(fill="x")

            toggle.configure(command=toggle_children)
            label.bind("<Button-1>", lambda _e: toggle_children())
            count += 1

        add_node(self.right_content, root, 0)
        if count >= max_entries:
            ctk.CTkLabel(self.right_content, text="... (truncated)", font=FIELD_FONT, anchor="w").pack(
                anchor="w", pady=6
            )

    def _render_index_summary(self, result: dict) -> None:
        if not self.right_title:
            return
        self.right_title.configure(text="Index Summary")
        self._clear_right_panel()
        self._render_kv("Command", result.get("command", "-"))
        self._render_kv("Exit Code", result.get("exit_code", "-"))
        self._render_kv("Output Lines", result.get("lines", "-"))
        self._render_kv("Summary", result.get("summary", "-"))

    def _render_export_summary(self, result: dict) -> None:
        if not self.right_title:
            return
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
        if not self.right_title:
            return
        self.right_title.configure(text="Preset Progress")
        self._clear_right_panel()
        self._render_kv("Preset", preset_name)
        for step in steps:
            self._render_kv(step.get("name", "-"), step.get("status", "-"))

    def _render_committees(self, result: dict) -> None:
        if not self.right_title:
            return
        self.right_title.configure(text="Committees")
        self._clear_right_panel()
        self._render_kv("Count", result.get("count", "-"))
        committees = result.get("committees", [])
        self._render_list(committees if isinstance(committees, list) else [])

    def _render_kv(self, label: str, value: object) -> None:
        if not self.right_content:
            return
        row = ctk.CTkFrame(self.right_content, fg_color="transparent")
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(row, text=label, font=FIELD_FONT, anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=str(value), font=FIELD_FONT, anchor="e", justify="right").pack(side="right")

    def _render_list(self, items: list[str]) -> None:
        if not self.right_content:
            return
        if not items:
            ctk.CTkLabel(self.right_content, text="(no entries)", font=FIELD_FONT).pack(anchor="w", pady=6)
            return
        for item in items:
            ctk.CTkLabel(self.right_content, text=f"- {item}", font=FIELD_FONT, anchor="w").pack(anchor="w")

    def _refresh_analysis_committee_options(self) -> None:
        if not self.view_frames.get("analysis"):
            return
        db_path = self._resolve_db_path(self.export_db_path.get())
        if not db_path.exists():
            return
        try:
            committees = ["", *self.analysis_store.list_committees(db_path)]
        except sqlite3.Error:
            return

        if self.analysis_committee_box:
            self.analysis_committee_box.configure(values=committees)

    def _refresh_analysis_sessions(self) -> None:
        if not self.analysis_session_list_frame:
            return

        db_path = self._resolve_db_path(self.export_db_path.get())
        self.analysis_sessions = []
        if not db_path.exists():
            self._render_analysis_session_list()
            return

        try:
            self.analysis_sessions = self.analysis_store.list_sessions(
                db_path,
                SessionFilters(
                    date_from=self.analysis_date_from.get().strip(),
                    date_to=self.analysis_date_to.get().strip(),
                    committee=self.analysis_committee.get().strip(),
                    search=self.analysis_search.get().strip(),
                    past_only=bool(self.analysis_past_only.get()),
                ),
            )
        except sqlite3.Error as exc:
            self._set_analysis_status(f"DB error: {exc}")
            self.analysis_sessions = []

        self._render_analysis_session_list()

    def _render_analysis_session_list(self) -> None:
        if not self.analysis_session_list_frame:
            return
        for child in self.analysis_session_list_frame.winfo_children():
            child.destroy()

        if not self.analysis_sessions:
            ctk.CTkLabel(
                self.analysis_session_list_frame,
                text="Keine Sitzungen mit den aktuellen Filtern.",
                font=FIELD_FONT,
                anchor="w",
                justify="left",
            ).pack(fill="x", padx=6, pady=6)
            return

        for row in self.analysis_sessions:
            title = f"{row.get('date', '')} | {row.get('committee', '-') } | {row.get('meeting_name', '-') }"
            subtitle = f"TOPs: {row.get('top_count', 0)} | Session-ID: {row.get('session_id', '-') }"
            text = f"{title}\n{subtitle}"
            ctk.CTkButton(
                self.analysis_session_list_frame,
                text=text,
                command=lambda session_id=row.get("session_id"): self._load_analysis_session_detail(str(session_id)),
                anchor="w",
                height=58,
                fg_color="#1F2937",
                hover_color="#374151",
                font=FIELD_FONT,
            ).pack(fill="x", padx=6, pady=4)

    def _load_analysis_session_detail(self, session_id: str) -> None:
        db_path = self._resolve_db_path(self.export_db_path.get())
        if not db_path.exists() or not self.analysis_tops_frame:
            return

        try:
            session_row, agenda_rows = self.analysis_store.load_session_and_agenda(
                db_path, session_id
            )
        except sqlite3.Error as exc:
            self._set_analysis_status(f"DB error: {exc}")
            return

        if session_row is None:
            self._set_analysis_status("Session nicht gefunden.")
            return

        self.analysis_current_session = session_row
        if self.analysis_selected_session_label:
            self.analysis_selected_session_label.configure(
                text=(
                    f"{session_row['date']} | {session_row['committee'] or '-'} | "
                    f"{session_row['meeting_name'] or '-'}"
                )
            )

        self.analysis_top_vars.clear()
        for child in self.analysis_tops_frame.winfo_children():
            child.destroy()

        if not agenda_rows:
            ctk.CTkLabel(self.analysis_tops_frame, text="Keine TOPs vorhanden.", font=FIELD_FONT).pack(
                anchor="w", padx=6, pady=6
            )
            return

        for row in agenda_rows:
            number = str(row["number"] or "")
            title = str(row["title"] or "")
            info = f"{number} - {title}"
            var = ctk.BooleanVar(value=False)
            self.analysis_top_vars[number] = var
            ctk.CTkCheckBox(
                self.analysis_tops_frame,
                text=info,
                variable=var,
                font=FIELD_FONT,
            ).pack(anchor="w", padx=6, pady=3)

        self._set_analysis_status("Sitzung geladen.")

    def _start_analysis_job(self) -> None:
        if not self.analysis_current_session:
            self._set_analysis_status("Bitte zuerst eine Sitzung waehlen.")
            return

        if self.analysis_scope.get() == "tops" and not self._selected_top_numbers():
            self._set_analysis_status("Bitte mindestens einen TOP waehlen.")
            return

        prompt = ""
        if self.analysis_prompt_box:
            prompt = self.analysis_prompt_box.get("1.0", "end").strip()

        payload = self._build_analysis_payload()
        if payload is None:
            self._set_analysis_status("Keine Daten fuer die Analyse gefunden.")
            return

        self._set_analysis_status("Analyse laeuft...")
        thread = threading.Thread(target=self._run_analysis_job_worker, args=(payload, prompt), daemon=True)
        thread.start()

    def _build_analysis_payload(self) -> dict | None:
        session = self.analysis_current_session
        if not session:
            return None

        db_path = self._resolve_db_path(self.export_db_path.get())
        if not db_path.exists():
            return None

        selected_tops = self._selected_top_numbers()
        scope = self.analysis_scope.get()
        try:
            documents = self.analysis_store.load_documents(
                db_path, str(session["session_id"]), scope, selected_tops
            )
        except sqlite3.Error:
            documents = []
        documents = enrich_documents_for_analysis(documents)

        return {
            "session": session,
            "scope": scope,
            "selected_tops": selected_tops,
            "documents": documents,
            "db_path": str(db_path),
        }

    def _run_analysis_job_worker(self, payload: dict, prompt: str) -> None:
        db_path = Path(payload["db_path"])
        session = payload["session"]
        scope = payload["scope"]
        selected_tops = payload["selected_tops"]
        documents = payload["documents"]

        created_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        job_id: int | None = None
        result_markdown = ""

        try:
            with sqlite3.connect(db_path) as conn:
                self._ensure_analysis_tables(conn)
                cur = conn.execute(
                    "INSERT INTO analysis_jobs (created_at, session_id, scope, top_numbers_json, model_name, prompt_version, status, error_message) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        created_at,
                        session["session_id"],
                        scope,
                        json.dumps(selected_tops, ensure_ascii=False),
                        "mock-journalism-v1",
                        "local-template-1",
                        "running",
                        None,
                    ),
                )
                job_id = int(cur.lastrowid)

                result_markdown = build_analysis_markdown(
                    session=session,
                    scope=scope,
                    selected_tops=selected_tops,
                    documents=documents,
                    prompt=prompt,
                )

                conn.execute(
                    "INSERT INTO analysis_outputs (job_id, output_format, content, created_at) VALUES (?, ?, ?, ?)",
                    (job_id, "markdown", result_markdown, created_at),
                )
                conn.execute("UPDATE analysis_jobs SET status = ? WHERE id = ?", ("done", job_id))
                conn.commit()

            self.root.after(0, lambda: self._set_analysis_result(result_markdown))
            self.root.after(0, lambda: self._set_analysis_status(f"Analyse abgeschlossen (Job {job_id})."))
        except Exception as exc:
            try:
                if job_id is not None:
                    with sqlite3.connect(db_path) as conn:
                        self._ensure_analysis_tables(conn)
                        conn.execute(
                            "UPDATE analysis_jobs SET status = ?, error_message = ? WHERE id = ?",
                            ("failed", str(exc), job_id),
                        )
                        conn.commit()
            except Exception:
                pass
            self.root.after(0, lambda: self._set_analysis_status(f"Analyse fehlgeschlagen: {exc}"))

    def _ensure_analysis_tables(self, conn: sqlite3.Connection) -> None:
        self.analysis_store.ensure_analysis_tables(conn)

    def _selected_top_numbers(self) -> list[str]:
        selected: list[str] = []
        for number, var in self.analysis_top_vars.items():
            if var.get():
                selected.append(number)
        return selected

    def _set_analysis_status(self, text: str) -> None:
        if self.analysis_status_label:
            self.analysis_status_label.configure(text=text)

    def _set_analysis_result(self, text: str) -> None:
        if not self.analysis_result_text:
            return
        self.analysis_result_text.delete("1.0", "end")
        self.analysis_result_text.insert("1.0", text)

    def _reset_analysis_prompt(self) -> None:
        if not self.analysis_prompt_box:
            return
        self.analysis_prompt_box.delete("1.0", "end")
        self.analysis_prompt_box.insert(
            "1.0",
            "Erstelle eine journalistische, neutrale Zusammenfassung. Nenne Kernthemen, Entscheidungen und offene Punkte.",
        )

    def _export_analysis_markdown(self) -> None:
        if not self.analysis_result_text:
            return
        content = self.analysis_result_text.get("1.0", "end").strip()
        if not content:
            self._set_analysis_status("Kein Analyseergebnis zum Exportieren vorhanden.")
            return

        target = self._resolve_db_path("data/processed/analysis_latest.md")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content + "\n", encoding="utf-8")
        self._set_analysis_status(f"Markdown exportiert: {target}")

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    GuiLauncher().run()


if __name__ == "__main__":
    main()
