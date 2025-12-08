"""Streamlit prototype UI for downloading raw data.

This app is intentionally self-contained and does not rely on the
existing project code. It lets users fetch remote files into the
``data/raw`` directory and lists the downloaded artifacts.
"""

from __future__ import annotations

import datetime
import pathlib
import sys
from typing import Iterable

import requests
import streamlit as st

RAW_DIR = pathlib.Path(__file__).resolve().parent / "data" / "raw"


def ensure_raw_dir() -> pathlib.Path:
    """Make sure the raw data directory exists and return it."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    return RAW_DIR


def human_size(num_bytes: int) -> str:
    """Return a human-readable file size string."""
    step_unit = 1024.0
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    for unit in units:
        if size < step_unit:
            return f"{size:0.1f} {unit}"
        size /= step_unit
    return f"{size:0.1f} PB"


def list_raw_files() -> Iterable[tuple[str, int, datetime.datetime]]:
    """Yield tuples of (name, size, mtime) for files in the raw folder."""
    raw_dir = ensure_raw_dir()
    for path in sorted(raw_dir.iterdir()):
        if path.is_file():
            stat = path.stat()
            yield (
                path.name,
                stat.st_size,
                datetime.datetime.fromtimestamp(stat.st_mtime),
            )


def download_file(url: str, filename: str | None = None) -> pathlib.Path:
    """Download *url* into the raw directory and return the saved path."""
    raw_dir = ensure_raw_dir()
    response = requests.get(url, stream=True, timeout=30)
    response.raise_for_status()

    target_name = filename or url.split("/")[-1] or "download.bin"
    target_path = raw_dir / target_name

    with target_path.open("wb") as file_handle:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                file_handle.write(chunk)

    return target_path


def render_download_section() -> None:
    st.header("Daten herunterladen")
    url = st.text_input("Quelle (URL)")
    custom_name = st.text_input("Dateiname im raw-Ordner (optional)")

    if st.button("Fetch ausführen", type="primary"):
        if not url:
            st.error("Bitte eine gültige URL angeben.")
            return

        with st.spinner("Lade Daten herunter..."):
            try:
                saved_path = download_file(url.strip(), filename=custom_name.strip() or None)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Fehler beim Herunterladen: {exc}")
            else:
                size = saved_path.stat().st_size
                st.success(
                    f"Download abgeschlossen: `{saved_path}` ({human_size(size)})"
                )

                st.info(
                    "Die Datei wurde im Projektverzeichnis unter `data/raw` abgelegt."
                )


def render_inventory_section() -> None:
    st.header("Ablage im raw-Ordner")
    files = list(list_raw_files())

    if not files:
        st.write("Es wurden noch keine Dateien heruntergeladen.")
        return

    st.write("Übersicht der vorhandenen Dateien:")
    for name, size, mtime in files:
        st.write(
            f"- `{name}` — {human_size(size)} (zuletzt geändert: {mtime:%Y-%m-%d %H:%M:%S})"
        )


def main() -> None:
    st.set_page_config(page_title="Prototyp: Daten-Fetch UI", page_icon="📥")
    st.title("Prototypische Download-UI")
    st.write(
        "Diese Oberfläche ist eigenständig und ermöglicht den Download von Daten "
        "in den `data/raw`-Ordner."
    )

    render_download_section()
    st.divider()
    render_inventory_section()


if __name__ == "__main__":
    sys.exit(main())
