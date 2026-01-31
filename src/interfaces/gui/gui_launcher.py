"""GUI launcher prototype for local data workflows."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

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
        self.status_label = None
        self.run_button = None

        self.selected_root = ctk.StringVar(
            value=str(DATA_ROOT_DEFAULT if DATA_ROOT_DEFAULT.exists() else REPO_ROOT)
        )
        self.selected_action = ctk.StringVar(value="Fetch Sessions (Script)")
        self.year_value = ctk.StringVar(value=str(datetime.now().year))
        self.months_value = ctk.StringVar(value="")
        self.verbose_mode = ctk.BooleanVar(value=False)

        self.spinner_running = False
        self.spinner_index = 0

        self.actions = {
            "Fetch Sessions (Script)": self._run_fetch_sessions,
            "Show Data Inventory": self._run_data_inventory,
            "Show Data Structure": self._run_data_structure,
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
        file_dropdown.add_option("Select data root", self._browse_root)
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

        ctk.CTkLabel(frame, text="Data root:", font=LABEL_FONT).grid(
            row=0, column=0, sticky="w"
        )
        entry = ctk.CTkEntry(
            frame, textvariable=self.selected_root, font=FIELD_FONT, width=900
        )
        entry.grid(row=1, column=0, sticky="ew", padx=(0, 10), pady=(0, 8))
        entry.bind("<Double-Button-1>", lambda _e: self._browse_root())

        browse_btn = ctk.CTkButton(
            frame,
            text="Browse",
            command=self._browse_root,
            fg_color=B_R_BLUE,
            hover_color=HOVER_BLUE,
            font=BUTTON_FONT,
            width=120,
            height=36,
        )
        browse_btn.grid(row=1, column=1, pady=(0, 8))

        ctk.CTkLabel(frame, text="Action:", font=LABEL_FONT).grid(
            row=2, column=0, sticky="w"
        )
        action_box = ctk.CTkComboBox(
            frame,
            variable=self.selected_action,
            values=list(self.actions.keys()),
            width=300,
            font=FIELD_FONT,
        )
        action_box.grid(row=3, column=0, sticky="w", pady=(0, 8))

        params_frame = ctk.CTkFrame(frame, fg_color="transparent")
        params_frame.grid(row=3, column=1, sticky="w", padx=(20, 0))

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
        ).grid(row=3, column=2, sticky="w", padx=(20, 0))

        self.run_button = ctk.CTkButton(
            frame,
            text="Run",
            command=self._run_action,
            fg_color=B_R_BLUE,
            hover_color=HOVER_BLUE,
            font=BUTTON_FONT,
            height=36,
        )
        self.run_button.grid(row=3, column=3, sticky="w", padx=(20, 0))

    def _build_status(self) -> None:
        self.status_label = ctk.CTkLabel(
            self.root, text="Ready", height=24, anchor="w", font=FIELD_FONT
        )
        self.status_label.pack(fill="x", padx=20, pady=(0, 6))

    def _build_log(self) -> None:
        self.log_text = ctk.CTkTextbox(
            self.root, wrap="word", font=LOG_FONT, border_width=1, corner_radius=6
        )
        self.log_text.pack(fill="both", expand=True, padx=20, pady=10)
        self.log_text.configure(state="disabled")

        textbox = self.log_text._textbox
        textbox.tag_configure("error", foreground="#ef4444")
        textbox.tag_configure("warning", foreground="#f59e0b")
        textbox.tag_configure("info", foreground="#22c55e")
        textbox.tag_configure(
            "normal",
            foreground="white" if ctk.get_appearance_mode() == "Dark" else "black",
        )

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

    def _browse_root(self) -> None:
        folder = filedialog.askdirectory()
        if folder:
            self.selected_root.set(folder)

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

    def _run_worker(self, action) -> None:
        try:
            action()
            self._set_status("Done")
        except Exception as exc:  # pragma: no cover - UI safety
            self._append_log(f"[ERROR] {exc}")
            self._set_status("Failed")
        finally:
            self._stop_spinner()

    def _run_fetch_sessions(self) -> None:
        script_path = REPO_ROOT / "scripts" / "fetch_sessions.py"
        if not script_path.exists():
            self._append_log("[ERROR] scripts/fetch_sessions.py not found")
            return

        year = self.year_value.get().strip()
        if not year.isdigit():
            self._append_log("[ERROR] Year must be a number")
            return

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
        for line in process.stdout:
            self._append_log(line.rstrip())
        process.wait()
        if process.returncode != 0:
            self._append_log(f"[ERROR] Script exited with {process.returncode}")

    def _run_data_inventory(self) -> None:
        root = Path(self.selected_root.get())
        if not root.exists():
            self._append_log("[ERROR] Data root not found")
            return

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

    def _run_data_structure(self) -> None:
        root = Path(self.selected_root.get())
        if not root.exists():
            self._append_log("[ERROR] Data root not found")
            return

        lines = self._build_tree(root, max_depth=4, max_entries=80)
        self._append_log("[INFO] Data structure:")
        for line in lines:
            self._append_log(line)

    def _build_tree(
        self, root: Path, max_depth: int = 3, max_entries: int = 50
    ) -> list[str]:
        lines = []
        count = 0

        def walk(current: Path, depth: int) -> None:
            nonlocal count
            if depth > max_depth or count >= max_entries:
                return
            entries = sorted(current.iterdir())
            for entry in entries:
                if count >= max_entries:
                    return
                prefix = "  " * depth + ("- " if depth else "")
                lines.append(f"{prefix}{entry.name}")
                count += 1
                if entry.is_dir():
                    walk(entry, depth + 1)

        walk(root, 0)
        if count >= max_entries:
            lines.append("... (truncated)")
        return lines

    def _append_log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}"

        self.log_text.configure(state="normal")
        tag = self._detect_tag(message)
        self.log_text.insert("end", line + "\n", tag)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

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


def main() -> None:
    GuiLauncher().run()


if __name__ == "__main__":
    main()
