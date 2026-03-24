"""Streamlit web interface for the ratsi_melle analysis tool."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Project root on sys.path (needed when run via `streamlit run` directly)
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.analysis.prompt_registry import filter_by_scope, load_templates, save_templates
from src.analysis.service import AnalysisRequest, AnalysisService
from src.interfaces.gui.services.analysis_store import AnalysisStore, SessionFilters
from src.paths import (
    ANALYSIS_OUTPUTS_DIR,
    LOCAL_INDEX_DB,
    ONLINE_INDEX_DB,
    REPO_ROOT,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_PROMPT_TEMPLATES_PATH = REPO_ROOT / "configs" / "prompt_templates.json"
_PROVIDER_OPTIONS = {
    "Kein Provider (nur Grundlage)": "none",
    "Claude (Anthropic)": "claude",
    "Codex (OpenAI)": "codex",
    "Ollama (lokal, ≤8B)": "ollama",
}
_DB_OPTIONS = {
    "Lokaler Index": str(LOCAL_INDEX_DB),
    "Online-Index": str(ONLINE_INDEX_DB),
    "Anderen Pfad eingeben …": "__custom__",
}

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Ratsinformations-Analyse Melle",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Session-state helpers
# ---------------------------------------------------------------------------
def _init_state() -> None:
    defaults: dict = {
        "db_path": str(LOCAL_INDEX_DB),
        "date_preset": "Letzte 30 Tage",
        "date_from": "",
        "date_to": "",
        "committee": "",
        "session_status": "alle",
        "search": "",
        "selected_session": None,
        "selected_tops": [],
        "analysis_scope": "session",
        "provider_label": "Kein Provider (nur Grundlage)",
        "model_name": "",
        "prompt_text": "",
        "selected_template_id": None,
        "analysis_result": "",
        "analysis_error": "",
        "analysis_record": None,
        "script_output": "",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


_store = AnalysisStore()
_service = AnalysisService()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
def _render_sidebar() -> Path:
    st.sidebar.title("🏛️ Ratsinformationen")
    st.sidebar.markdown("---")

    # DB selection
    db_choice = st.sidebar.selectbox(
        "Datenbank",
        list(_DB_OPTIONS.keys()),
        index=list(_DB_OPTIONS.values()).index(
            st.session_state["db_path"]
            if st.session_state["db_path"] in _DB_OPTIONS.values()
            else "__custom__"
        )
        if st.session_state["db_path"] not in list(_DB_OPTIONS.values())[:-1]
        else list(_DB_OPTIONS.values()).index(st.session_state["db_path"]),
    )
    if _DB_OPTIONS[db_choice] == "__custom__":
        custom_path = st.sidebar.text_input(
            "Pfad zur SQLite-DB", value=st.session_state["db_path"]
        )
        st.session_state["db_path"] = custom_path
    else:
        st.session_state["db_path"] = _DB_OPTIONS[db_choice]

    db_path = Path(st.session_state["db_path"])
    if not db_path.exists():
        st.sidebar.warning(f"Datenbankdatei nicht gefunden:\n`{db_path}`")
    else:
        st.sidebar.success(f"DB: `{db_path.name}`")

    st.sidebar.markdown("---")

    # Date filter
    preset = st.sidebar.selectbox(
        "Zeitraum",
        list(AnalysisStore.DATE_PRESET_LABELS),
        index=list(AnalysisStore.DATE_PRESET_LABELS).index(
            st.session_state["date_preset"]
        )
        if st.session_state["date_preset"] in AnalysisStore.DATE_PRESET_LABELS
        else 0,
    )
    st.session_state["date_preset"] = preset

    if preset == "Benutzerdefiniert":
        col_from, col_to = st.sidebar.columns(2)
        st.session_state["date_from"] = col_from.text_input(
            "Von", value=st.session_state["date_from"], placeholder="2026-01-01"
        )
        st.session_state["date_to"] = col_to.text_input(
            "Bis", value=st.session_state["date_to"], placeholder="2026-12-31"
        )

    # Committee filter
    committees = [""] + _store.list_committees(db_path)
    committee_idx = (
        committees.index(st.session_state["committee"])
        if st.session_state["committee"] in committees
        else 0
    )
    st.session_state["committee"] = st.sidebar.selectbox(
        "Gremium", committees, index=committee_idx
    )

    # Status filter
    status_options = list(AnalysisStore.SESSION_STATUS_LABELS)
    status_idx = (
        status_options.index(st.session_state["session_status"])
        if st.session_state["session_status"] in status_options
        else 0
    )
    st.session_state["session_status"] = st.sidebar.selectbox(
        "Status", status_options, index=status_idx
    )

    # Search
    st.session_state["search"] = st.sidebar.text_input(
        "Suche", value=st.session_state["search"], placeholder="z. B. Haushalt"
    )

    return db_path


# ---------------------------------------------------------------------------
# Tab: Analyse
# ---------------------------------------------------------------------------
def _tab_analyse(db_path: Path) -> None:
    st.header("🔍 Analyse")

    # --- Session list ---
    filters = SessionFilters(
        date_from=st.session_state["date_from"],
        date_to=st.session_state["date_to"],
        date_preset=st.session_state["date_preset"],
        committee=st.session_state["committee"],
        search=st.session_state["search"],
        session_status=st.session_state["session_status"],
    )
    sessions = _store.list_sessions(db_path, filters)

    if not sessions:
        st.info("Keine Sitzungen gefunden. Bitte Filter anpassen oder Datenbank prüfen.")
        return

    session_labels = [
        f"{s['date']} – {s['committee']} ({s.get('top_count', 0)} TOPs)"
        for s in sessions
    ]
    session_map = {label: s for label, s in zip(session_labels, sessions)}

    current_label = None
    if st.session_state["selected_session"]:
        for label, s in session_map.items():
            if s["session_id"] == st.session_state["selected_session"].get("session_id"):
                current_label = label
                break

    chosen_label = st.selectbox(
        "Sitzung auswählen",
        session_labels,
        index=session_labels.index(current_label) if current_label in session_labels else 0,
    )
    chosen_session = session_map[chosen_label]
    st.session_state["selected_session"] = chosen_session

    # --- Load full session + agenda ---
    session, agenda_items = _store.load_session_and_agenda(
        db_path, str(chosen_session["session_id"])
    )
    if not session:
        st.warning("Sitzungsdaten konnten nicht geladen werden.")
        return

    st.markdown(
        f"**{session.get('meeting_name', '')}** | {session.get('date', '')} | {session.get('committee', '')}"
    )

    # --- Scope ---
    col_scope1, col_scope2 = st.columns([1, 3])
    with col_scope1:
        scope = st.radio(
            "Analyseumfang",
            ["Ganze Sitzung", "Ausgewählte TOPs"],
            index=0 if st.session_state["analysis_scope"] == "session" else 1,
        )
        st.session_state["analysis_scope"] = "session" if scope == "Ganze Sitzung" else "tops"

    selected_tops: list[str] = []
    if st.session_state["analysis_scope"] == "tops" and agenda_items:
        top_options = [
            f"{item.get('number', '')} – {item.get('title', '')}"
            for item in agenda_items
        ]
        top_number_map = {
            f"{item.get('number', '')} – {item.get('title', '')}": str(item.get("number", ""))
            for item in agenda_items
        }
        chosen_tops = st.multiselect("Tagesordnungspunkte", top_options)
        selected_tops = [top_number_map[t] for t in chosen_tops if t in top_number_map]
        st.session_state["selected_tops"] = selected_tops
    else:
        st.session_state["selected_tops"] = []

    # --- Documents ---
    documents = _store.load_documents(
        db_path,
        str(chosen_session["session_id"]),
        st.session_state["analysis_scope"],
        selected_tops,
    )

    with st.expander(f"Dokumente ({len(documents)})"):
        if documents:
            for doc in documents:
                top_nr = doc.get("agenda_item") or "–"
                title = doc.get("title") or "(kein Titel)"
                local = doc.get("local_path") or ""
                available = "✅" if local and Path(local).exists() else "⚠️"
                st.markdown(f"- {available} TOP {top_nr}: **{title}**")
        else:
            st.info("Keine Dokumente für diese Auswahl gefunden.")

    # --- Prompt templates ---
    st.markdown("---")
    st.subheader("Prompt")
    templates = load_templates(_PROMPT_TEMPLATES_PATH)
    scope_key = st.session_state["analysis_scope"]
    filtered_templates = filter_by_scope(templates, scope_key)

    template_labels = [t["label"] for t in filtered_templates]
    template_map = {t["label"]: t for t in filtered_templates}

    if template_labels:
        col_tmpl, col_save = st.columns([4, 1])
        with col_tmpl:
            chosen_template_label = st.selectbox(
                "Vorlage wählen",
                ["– Benutzerdefiniert –"] + template_labels,
            )
        with col_save:
            st.markdown("<br>", unsafe_allow_html=True)  # vertical align
            if st.button("💾 Speichern") and chosen_template_label != "– Benutzerdefiniert –":
                tmpl = template_map[chosen_template_label]
                tmpl["text"] = st.session_state.get("_prompt_edit", tmpl["text"])
                save_templates(templates, _PROMPT_TEMPLATES_PATH)
                st.success("Vorlage gespeichert.")

        if chosen_template_label != "– Benutzerdefiniert –":
            default_text = template_map[chosen_template_label]["text"]
        else:
            default_text = st.session_state.get("prompt_text", "")
    else:
        default_text = st.session_state.get("prompt_text", "")
        chosen_template_label = "– Benutzerdefiniert –"

    prompt_text = st.text_area(
        "Prompt (bearbeitbar)",
        value=default_text,
        height=120,
        key="_prompt_edit",
    )
    st.session_state["prompt_text"] = prompt_text

    # --- Provider ---
    st.markdown("---")
    st.subheader("KI-Provider")
    col_prov, col_model = st.columns(2)
    with col_prov:
        provider_label = st.selectbox(
            "Provider",
            list(_PROVIDER_OPTIONS.keys()),
            index=list(_PROVIDER_OPTIONS.keys()).index(st.session_state["provider_label"])
            if st.session_state["provider_label"] in _PROVIDER_OPTIONS
            else 0,
        )
        st.session_state["provider_label"] = provider_label
    with col_model:
        model_name = st.text_input(
            "Modell (leer = Provider-Standard)",
            value=st.session_state["model_name"],
            placeholder="z. B. claude-sonnet-4-5",
        )
        st.session_state["model_name"] = model_name

    provider_id = _PROVIDER_OPTIONS[provider_label]

    # PDF sending checkbox
    local_pdfs: list[Path] = [
        Path(doc["local_path"])
        for doc in documents
        if doc.get("local_path") and Path(doc["local_path"]).exists()
        and str(doc.get("local_path", "")).lower().endswith(".pdf")
    ]
    send_pdfs = False
    if local_pdfs and provider_id != "none":
        send_pdfs = st.checkbox(
            f"PDFs direkt senden ({len(local_pdfs)} PDF(s) verfügbar)",
            value=False,
            help="Claude/OpenAI: native Base64-Übertragung. Ollama: Text-Extraktion.",
        )

    # --- Run ---
    st.markdown("---")
    if st.button("▶ Analyse starten", type="primary", disabled=not prompt_text.strip()):
        _run_analysis(
            db_path=db_path,
            session=session,
            scope=st.session_state["analysis_scope"],
            selected_tops=selected_tops,
            prompt=prompt_text,
            provider_id=provider_id,
            model_name=model_name,
            pdf_paths=local_pdfs if send_pdfs else [],
        )

    # --- Result ---
    if st.session_state["analysis_error"]:
        st.error(st.session_state["analysis_error"])

    if st.session_state["analysis_result"]:
        st.markdown("---")
        st.subheader("Ergebnis")
        st.markdown(st.session_state["analysis_result"])

        record = st.session_state.get("analysis_record")
        if record:
            _offer_downloads(record)


def _run_analysis(
    *,
    db_path: Path,
    session: dict,
    scope: str,
    selected_tops: list[str],
    prompt: str,
    provider_id: str,
    model_name: str,
    pdf_paths: list[Path],
) -> None:
    st.session_state["analysis_result"] = ""
    st.session_state["analysis_error"] = ""
    st.session_state["analysis_record"] = None

    request = AnalysisRequest(
        db_path=db_path,
        session=session,
        scope=scope,
        selected_tops=selected_tops,
        prompt=prompt,
        provider_id=provider_id,
        model_name=model_name,
        pdf_paths=pdf_paths,
    )

    with st.spinner("Analyse läuft …"):
        try:
            record = _service.run_journalistic_analysis(request)
            result_text = record.ki_response or record.markdown
            st.session_state["analysis_result"] = result_text
            st.session_state["analysis_record"] = record
        except Exception as exc:  # noqa: BLE001
            st.session_state["analysis_error"] = f"Fehler bei der Analyse: {exc}"

    st.rerun()


def _offer_downloads(record) -> None:  # type: ignore[no-untyped-def]
    col_md, col_json = st.columns(2)
    with col_md:
        st.download_button(
            "⬇ Markdown herunterladen",
            data=record.markdown.encode("utf-8"),
            file_name=f"analyse_job_{record.job_id}.md",
            mime="text/markdown",
        )
    with col_json:
        import json

        st.download_button(
            "⬇ JSON herunterladen",
            data=json.dumps(record.to_dict(), indent=2, ensure_ascii=False).encode("utf-8"),
            file_name=f"analyse_job_{record.job_id}.json",
            mime="application/json",
        )


# ---------------------------------------------------------------------------
# Tab: Datenabruf
# ---------------------------------------------------------------------------
def _tab_datenabruf() -> None:
    st.header("📥 Datenabruf")

    script_options = {
        "Sitzungen abrufen (fetch_sessions)": "fetch_sessions",
        "Lokalen Index aufbauen (build_local_index)": "build_local_index",
        "Online-Index aufbauen (build_online_index_db)": "build_online_index_db",
    }
    chosen_script_label = st.selectbox("Script auswählen", list(script_options.keys()))
    script_name = script_options[chosen_script_label]

    extra_args: list[str] = []
    if script_name in {"fetch_sessions", "build_online_index_db"}:
        col_year, col_months = st.columns(2)
        with col_year:
            year = st.number_input("Jahr", min_value=2000, max_value=2050, value=2024, step=1)
        with col_months:
            month_options = [str(m) for m in range(1, 13)]
            months = st.multiselect("Monate (leer = alle)", month_options)
        extra_args = [str(year)]
        if months:
            extra_args += ["--months"] + months

    if st.button("▶ Ausführen"):
        script_path = REPO_ROOT / "scripts" / f"{script_name}.py"
        cmd = [sys.executable, str(script_path)] + extra_args

        output_lines: list[str] = []
        with st.spinner(f"Führe `{script_name}` aus …"):
            try:
                proc = subprocess.Popen(
                    cmd,
                    cwd=str(REPO_ROOT),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                assert proc.stdout is not None
                for line in proc.stdout:
                    output_lines.append(line.rstrip())
                proc.wait()
                exit_code = proc.returncode
            except Exception as exc:  # noqa: BLE001
                output_lines = [f"Fehler beim Starten: {exc}"]
                exit_code = -1

        output_text = "\n".join(output_lines)
        st.session_state["script_output"] = output_text

        if exit_code == 0:
            st.success(f"Abgeschlossen (Exit-Code {exit_code})")
        else:
            st.error(f"Fehler (Exit-Code {exit_code})")

    if st.session_state["script_output"]:
        st.text_area("Ausgabe", value=st.session_state["script_output"], height=300)


# ---------------------------------------------------------------------------
# Tab: Export
# ---------------------------------------------------------------------------
def _tab_export(db_path: Path) -> None:
    st.header("📤 Export")

    committees = [""] + _store.list_committees(db_path)
    selected_committees = st.multiselect("Gremien", committees[1:])

    col_from, col_to = st.columns(2)
    with col_from:
        export_from = st.text_input("Von (YYYY-MM-DD)", placeholder="2026-01-01")
    with col_to:
        export_to = st.text_input("Bis (YYYY-MM-DD)", placeholder="2026-12-31")

    if st.button("▶ Export starten"):
        script_path = REPO_ROOT / "scripts" / "export_analysis_batch.py"
        cmd = [sys.executable, str(script_path), "--db", str(db_path)]
        if selected_committees:
            cmd += ["--committees"] + selected_committees
        if export_from:
            cmd += ["--date-from", export_from]
        if export_to:
            cmd += ["--date-to", export_to]

        with st.spinner("Export läuft …"):
            try:
                result = subprocess.run(
                    cmd,
                    cwd=str(REPO_ROOT),
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode == 0:
                    st.success("Export abgeschlossen.")
                    st.text_area("Ausgabe", value=result.stdout, height=200)
                else:
                    st.error("Export fehlgeschlagen.")
                    st.text_area("Fehler", value=result.stderr or result.stdout, height=200)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Fehler: {exc}")

    # Quick overview of existing output files
    st.markdown("---")
    st.subheader("Vorhandene Analyse-Ausgaben")
    if ANALYSIS_OUTPUTS_DIR.exists():
        md_files = sorted(ANALYSIS_OUTPUTS_DIR.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:10]
        if md_files:
            for f in md_files:
                rel = f.relative_to(ANALYSIS_OUTPUTS_DIR)
                st.markdown(f"- `{rel}`")
        else:
            st.info("Noch keine Ausgaben vorhanden.")
    else:
        st.info("Ausgabe-Verzeichnis existiert noch nicht.")


# ---------------------------------------------------------------------------
# Tab: Einstellungen
# ---------------------------------------------------------------------------
def _tab_einstellungen() -> None:
    st.header("⚙️ Einstellungen")

    st.subheader("API-Keys")
    st.info(
        "API-Keys werden im OS-Schlüsselbund (Windows Credential Manager) gespeichert. "
        "Alternativ können Umgebungsvariablen `ANTHROPIC_API_KEY` und `OPENAI_API_KEY` gesetzt werden."
    )

    with st.form("api_keys_form"):
        claude_key = st.text_input("Anthropic API-Key (Claude)", type="password", placeholder="sk-ant-…")
        openai_key = st.text_input("OpenAI API-Key (Codex)", type="password", placeholder="sk-…")
        submitted = st.form_submit_button("Speichern")

    if submitted:
        _save_api_keys(claude_key, openai_key)

    st.markdown("---")
    st.subheader("Prompt-Vorlagen")
    templates = load_templates(_PROMPT_TEMPLATES_PATH)
    st.markdown(f"Geladen aus: `{_PROMPT_TEMPLATES_PATH}`")
    st.markdown(f"**{len(templates)} Vorlage(n)** verfügbar:")
    for tmpl in templates:
        with st.expander(f"{tmpl['label']} (`{tmpl['id']}`, Scope: {', '.join(tmpl.get('scope', []))})"):
            new_text = st.text_area(
                "Text", value=tmpl["text"], key=f"settings_tmpl_{tmpl['id']}", height=80
            )
            if st.button("Speichern", key=f"save_tmpl_{tmpl['id']}"):
                tmpl["text"] = new_text
                save_templates(templates, _PROMPT_TEMPLATES_PATH)
                st.success(f"Vorlage '{tmpl['label']}' gespeichert.")
                st.rerun()


def _save_api_keys(claude_key: str, openai_key: str) -> None:
    saved: list[str] = []
    errors: list[str] = []
    try:
        import keyring

        if claude_key.strip():
            keyring.set_password("ratsi_melle", "claude_api_key", claude_key.strip())
            saved.append("Claude")
        if openai_key.strip():
            keyring.set_password("ratsi_melle", "codex_api_key", openai_key.strip())
            saved.append("OpenAI")
    except Exception as exc:  # noqa: BLE001
        errors.append(str(exc))

    if saved:
        st.success(f"Gespeichert: {', '.join(saved)}")
    if errors:
        st.error(f"Fehler: {'; '.join(errors)}")
    if not saved and not errors:
        st.info("Keine Änderungen – beide Felder waren leer.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    _init_state()
    db_path = _render_sidebar()

    tab_analyse, tab_data, tab_export, tab_settings = st.tabs(
        ["🔍 Analyse", "📥 Datenabruf", "📤 Export", "⚙️ Einstellungen"]
    )

    with tab_analyse:
        _tab_analyse(db_path)
    with tab_data:
        _tab_datenabruf()
    with tab_export:
        _tab_export(db_path)
    with tab_settings:
        _tab_einstellungen()


if __name__ == "__main__":
    main()
