"""GUI launcher prototype for local data workflows."""

from __future__ import annotations

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

        self.selected_action = ctk.StringVar(
            value="Download sessions from the Melle SessionNet (script)"
        )
        self.year_value = ctk.StringVar(value=str(datetime.now().year))
        self.months_value = ctk.StringVar(value="")
        self.verbose_mode = ctk.BooleanVar(value=False)

        self.spinner_running = False
        self.spinner_index = 0

        self.actions = {
            "Download sessions from the Melle SessionNet (script)": ActionConfig(
                name="Download sessions from the Melle SessionNet (script)",
                handler=self._run_fetch_sessions,
                renderer=self._render_fetch_summary,
            ),
            "Build SQLite Index (script)": ActionConfig(
                name="Build SQLite Index (script)",
                handler=self._run_build_index,
                renderer=self._render_index_summary,
            ),
            "List Committees (sqlite)": ActionConfig(
                name="List Committees (sqlite)",
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

        self._build_ui()
        self._update_menubar_theme()

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

    def _run_action(self) -> None:
        action = self.actions.get(self.selected_action.get())
        if not action:
            return
        self._start_spinner()
        self._set_status("Running...")
        thread = threading.Thread(target=self._run_worker, args=(action,), daemon=True)
        thread.start()

    def _run_worker(self, action: "ActionConfig") -> None:
        try:
            result = action.handler()
            self.root.after(0, lambda: self._render_action_result(action, result))
            self._set_status("Done")
        except Exception as exc:  # pragma: no cover - UI safety
            self._append_log(f"[ERROR] {exc}")
            self._set_status("Failed")
        finally:
            self._stop_spinner()

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

        self._append_log(f"[INFO] Running: {' '.join(cmd)}")

        process = subprocess.Popen(
            cmd,
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        assert process.stdout is not None
        line_count = 0
        for line in process.stdout:
            self._append_log(line.rstrip())
            line_count += 1
        process.wait()
        if process.returncode != 0:
            self._append_log(f"[ERROR] Script exited with {process.returncode}")
        return {
            "status": "ok" if process.returncode == 0 else "error",
            "command": " ".join(cmd),
            "exit_code": process.returncode,
            "lines": line_count,
        }

    def _run_build_index(self) -> dict:
        script_path = REPO_ROOT / "scripts" / "build_index.py"
        if not script_path.exists():
            self._append_log("[ERROR] scripts/build_index.py not found")
            return {"status": "error", "message": "Script not found"}

        cmd = [sys.executable, str(script_path)]
        self._append_log(f"[INFO] Running: {' '.join(cmd)}")

        process = subprocess.Popen(
            cmd,
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        assert process.stdout is not None
        last_line = ""
        line_count = 0
        for line in process.stdout:
            stripped = line.rstrip()
            if stripped:
                last_line = stripped
            self._append_log(stripped)
            line_count += 1
        process.wait()
        if process.returncode != 0:
            self._append_log(f"[ERROR] Script exited with {process.returncode}")
        return {
            "status": "ok" if process.returncode == 0 else "error",
            "command": " ".join(cmd),
            "exit_code": process.returncode,
            "lines": line_count,
            "summary": last_line,
        }

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

    def _run_list_committees(self) -> dict:
        db_path = REPO_ROOT / "data" / "processed" / "index.sqlite"
        if not db_path.exists():
            self._append_log("[ERROR] SQLite index not found. Run build_index.py first.")
            return {"status": "error", "message": "index.sqlite not found"}

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
        root = Path(result.get("root", ""))
        self._render_kv("Root", root if root else "-")
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
