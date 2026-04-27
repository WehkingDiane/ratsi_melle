"""Streamlit web interface for the ratsi_melle analysis tool."""

from __future__ import annotations

import importlib
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

if os.environ.get("RATSI_USE_STREAMLIT") == "1" or "streamlit" in Path(sys.argv[0]).name.lower():
    import streamlit as st
else:
    class _StreamlitStub:
        def __init__(self) -> None:
            self.session_state: dict = {}
            self.sidebar = self

        def __enter__(self) -> "_StreamlitStub":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def cache_data(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            def decorator(func):  # type: ignore[no-untyped-def]
                func.clear = lambda: None  # type: ignore[attr-defined]
                return func
            return decorator

        def cache_resource(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            def decorator(func):  # type: ignore[no-untyped-def]
                return func
            return decorator

        def columns(self, spec, **kwargs):  # type: ignore[no-untyped-def]
            count = spec if isinstance(spec, int) else len(spec)
            return [self for _ in range(count)]

        def tabs(self, labels):  # type: ignore[no-untyped-def]
            return [self for _ in labels]

        def expander(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            return self

        def spinner(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            return self

        def __getattr__(self, name: str):  # type: ignore[no-untyped-def]
            def method(*args, **kwargs):  # type: ignore[no-untyped-def]
                if name in {"selectbox", "radio"} and len(args) >= 2:
                    options = args[1]
                    return options[0] if options else ""
                if name == "multiselect":
                    return []
                if name == "checkbox":
                    return False
                if name == "button":
                    return False
                if name == "text_input":
                    return kwargs.get("value", "")
                if name == "text_area":
                    return kwargs.get("value", "")
                if name == "number_input":
                    return kwargs.get("value", 0)
                if name == "slider":
                    return kwargs.get("value", 0)
                return self
            return method

    st = _StreamlitStub()

# ---------------------------------------------------------------------------
# Project root on sys.path (needed when run via `streamlit run` directly)
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.analysis.prompt_registry import filter_by_scope, load_templates, save_templates
from src.analysis.service import AnalysisRequest, AnalysisService
from src.analysis.workflow_db import list_analysis_jobs_with_outputs, update_publication_job
from src.fetching.storage_layout import resolve_local_file_path
from src.interfaces.shared.analysis_store import AnalysisStore, SessionFilters
from src.interfaces.web.analysis_ui import (
    apply_publication_state,
    build_source_check,
    ensure_required_templates,
    filter_history_rows,
    get_allowed_output_types,
    get_analysis_mode_options,
    get_purpose_options,
    get_suggested_template_ids,
    load_json_file,
    map_analysis_mode_label_to_key,
    map_purpose_label_to_key,
    normalize_analysis_for_ui,
    scan_analysis_outputs,
    select_default_template_id,
    validate_publication_status,
    validate_review_status,
)
from src.paths import (
    ANALYSIS_WORKFLOW_DB,
    DB_DIR,
    LOCAL_INDEX_DB,
    ONLINE_INDEX_DB,
    QDRANT_DIR,
    RAW_DATA_DIR,
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
_LOCAL_DOCUMENT_POLICY_TEXT = (
    "Lokale Dateien werden nur genutzt, wenn ihr Pfad innerhalb einer zulaessigen "
    "`data/raw/`-Struktur aufgeloest werden kann. Die lokale Text-/PDF-Extraktion "
    "ist auf 25 MiB pro Datei begrenzt."
)

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
        "analysis_purpose_label": "Inhaltliche Analyse",
        "analysis_mode_label": "Nur strukturierte Analyse",
        "provider_label": "Kein Provider (nur Grundlage)",
        "model_name": "",
        "prompt_text": "",
        "selected_template_id": None,
        "analysis_result": "",
        "analysis_error": "",
        "analysis_record": None,
        "analysis_payloads": {},
        "selected_history_job_id": 0,
        "script_output": "",
        "search_results": [],
        "search_error": "",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


_store = AnalysisStore()
_service = AnalysisService()


def _existing_local_document_path(
    *,
    session_path: str | None = None,
    local_path: str | None = None,
) -> Path | None:
    """Return an existing local document path when it can be resolved."""
    resolved = resolve_local_file_path(session_path=session_path, local_path=local_path)
    if resolved is None or not resolved.is_file():
        return None
    return resolved


def _local_document_policy_text() -> str:
    """Return the user-facing policy for local document access."""
    return _LOCAL_DOCUMENT_POLICY_TEXT


def _semantic_search_dependency_error() -> str | None:
    """Return an actionable install hint when search dependencies are missing."""
    requirements: list[tuple[str, str]] = [
        ("qdrant-client", "qdrant_client"),
        ("sentence-transformers", "sentence_transformers"),
        ("fastembed", "fastembed"),
    ]
    missing = []
    for package_name, module_name in requirements:
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(package_name)

    if not missing:
        return None

    missing_text = ", ".join(f"`{name}`" for name in missing)
    return (
        f"Die Bibliotheken {missing_text} sind nicht installiert.\n\n"
        "Bitte installieren mit:\n"
        "```\n"
        "pip install qdrant-client sentence-transformers fastembed\n"
        "pip install torch --index-url https://download.pytorch.org/whl/cpu\n"
        "```"
    )


def _semantic_search_vector_dir(db_path: Path) -> Path | None:
    """Return the matching vector-store directory for supported databases."""
    if db_path.resolve() == LOCAL_INDEX_DB.resolve():
        return QDRANT_DIR
    return None


def _format_rrf_score(score: float) -> str:
    """Format rank-fusion scores without implying percentage relevance."""
    return f"{score:.4f}"


def _developer_script_options() -> dict[str, str]:
    return {
        "Sitzungen abrufen (fetch_sessions)": "fetch_sessions",
        "Lokalen Index aufbauen (build_local_index)": "build_local_index",
        "Online-Index aufbauen (build_online_index_db)": "build_online_index_db",
        "Vektorindex aufbauen (build_vector_index)": "build_vector_index",
    }


def _run_script_command(cmd: list[str]) -> tuple[int, str]:
    output_lines: list[str] = []
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
    return exit_code, "\n".join(output_lines)


def _count_files(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(1 for path in root.rglob("*") if path.is_file())


def _count_session_dirs(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(1 for path in root.rglob("session_detail.html") if path.is_file())


def _db_session_count(db_path: Path) -> int | None:
    if not db_path.exists():
        return None
    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
    except sqlite3.Error:
        return None
    return int(row[0]) if row else 0


@st.cache_data(ttl=60, show_spinner=False)
def _collect_data_status_cached(db_path_str: str) -> dict[str, int | bool | str | None]:
    db_path = Path(db_path_str)
    return {
        "selected_db_name": db_path.name,
        "selected_db_exists": db_path.exists(),
        "selected_db_sessions": _db_session_count(db_path),
        "raw_session_count": _count_session_dirs(RAW_DATA_DIR),
        "raw_file_count": _count_files(RAW_DATA_DIR),
        "local_index_exists": LOCAL_INDEX_DB.exists(),
        "local_index_sessions": _db_session_count(LOCAL_INDEX_DB),
        "online_index_exists": ONLINE_INDEX_DB.exists(),
        "online_index_sessions": _db_session_count(ONLINE_INDEX_DB),
        "vector_index_exists": QDRANT_DIR.exists(),
        "vector_index_file_count": _count_files(QDRANT_DIR),
    }


def _collect_data_status(db_path: Path) -> dict[str, int | bool | str | None]:
    return _collect_data_status_cached(str(db_path.resolve()))


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
    st.header("Analyse")

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
        st.info("Keine Sitzungen gefunden. Bitte Filter anpassen oder Datenbank pruefen.")
        return

    workflow_rows = _load_analysis_history()

    left_col, right_col = st.columns([1, 1.35], gap="large")

    with left_col:
        session_labels = [
            (
                f"{s['date']} | {s['committee'] or '-'} | ID {s['session_id']} | "
                f"{s.get('document_count', 0)} Dokumente | {s.get('top_count', 0)} TOPs"
            )
            for s in sessions
        ]
        session_map = {label: session for label, session in zip(session_labels, sessions, strict=False)}
        current_label = next(
            (
                label
                for label, session_row in session_map.items()
                if st.session_state["selected_session"]
                and session_row["session_id"] == st.session_state["selected_session"].get("session_id")
            ),
            session_labels[0],
        )
        chosen_label = st.selectbox(
            "Sitzung auswaehlen",
            session_labels,
            index=session_labels.index(current_label) if current_label in session_labels else 0,
        )
        chosen_session = session_map[chosen_label]
        st.session_state["selected_session"] = chosen_session

        session, agenda_items = _store.load_session_and_agenda(db_path, str(chosen_session["session_id"]))
        if not session:
            st.warning("Sitzungsdaten konnten nicht geladen werden.")
            return

        st.caption(
            f"{session.get('meeting_name') or '-'} | {session.get('date') or '-'} | "
            f"{session.get('committee') or '-'}"
        )

        scope_label = st.radio(
            "Auswahlumfang",
            ["Ganze Sitzung", "Ausgewaehlte TOPs"],
            index=0 if st.session_state["analysis_scope"] == "session" else 1,
        )
        st.session_state["analysis_scope"] = "session" if scope_label == "Ganze Sitzung" else "tops"

        selected_tops: list[str] = []
        top_labels = []
        top_map: dict[str, str] = {}
        for item in agenda_items:
            label = (
                f"{item.get('number') or '-'} | {item.get('title') or '-'} | "
                f"{item.get('document_count', 0)} Dokumente | "
                f"{', '.join(item.get('document_types') or ['-'])} | "
                f"lokale Quellen: {'ja' if item.get('has_local_source') else 'nein'}"
            )
            top_labels.append(label)
            top_map[label] = str(item.get("number") or "")
        if st.session_state["analysis_scope"] == "tops" and top_labels:
            chosen_tops = st.multiselect("TOPs auswaehlen", top_labels)
            selected_tops = [top_map[label] for label in chosen_tops if label in top_map]
        st.session_state["selected_tops"] = selected_tops

        purpose_options = get_purpose_options()
        st.session_state["analysis_purpose_label"] = st.radio(
            "Analysezweck",
            purpose_options,
            index=purpose_options.index(st.session_state["analysis_purpose_label"])
            if st.session_state["analysis_purpose_label"] in purpose_options
            else 2,
        )
        purpose_key = map_purpose_label_to_key(st.session_state["analysis_purpose_label"])

        mode_options = get_analysis_mode_options()
        st.session_state["analysis_mode_label"] = st.radio(
            "Analysemodus",
            mode_options,
            index=mode_options.index(st.session_state["analysis_mode_label"])
            if st.session_state["analysis_mode_label"] in mode_options
            else 0,
        )
        analysis_mode = map_analysis_mode_label_to_key(st.session_state["analysis_mode_label"])

        documents = _store.load_documents(
            db_path,
            str(chosen_session["session_id"]),
            st.session_state["analysis_scope"],
            selected_tops,
        )
        source_check = build_source_check(documents)

        st.markdown("---")
        st.subheader("Prompt und Provider")
        templates = ensure_required_templates(load_templates(_PROMPT_TEMPLATES_PATH))
        filtered_templates = filter_by_scope(templates, st.session_state["analysis_scope"])
        suggested_ids = get_suggested_template_ids(purpose_key)
        if analysis_mode == "publication_only":
            filtered_templates = [
                template
                for template in filtered_templates
                if str(template.get("id") or "") in {"journalistic_publication_draft"}
            ] or filtered_templates
        default_template_id = st.session_state.get("selected_template_id") or select_default_template_id(
            filtered_templates,
            purpose_key,
        )
        template_map = {str(template.get("id") or ""): template for template in filtered_templates}
        template_ids = ["custom"] + list(template_map.keys())
        default_template_index = template_ids.index(default_template_id) if default_template_id in template_ids else 0
        chosen_template_id = st.selectbox(
            "Prompt-Template",
            template_ids,
            index=default_template_index,
            format_func=lambda value: "Benutzerdefiniert" if value == "custom" else template_map[value]["label"],
        )
        st.session_state["selected_template_id"] = chosen_template_id

        if chosen_template_id != "custom":
            template_text = str(template_map[chosen_template_id].get("text") or "")
            prompt_version = chosen_template_id
        else:
            template_text = st.session_state.get("prompt_text", "")
            prompt_version = "custom"
        if not st.session_state.get("prompt_text"):
            st.session_state["prompt_text"] = template_text

        st.caption(f"Prompt-Version: `{prompt_version}` | Vorschlag fuer `{purpose_key}`: {', '.join(suggested_ids)}")
        prompt_text = st.text_area(
            "Prompt-Text",
            value=template_text,
            height=180,
            key="_prompt_edit",
        )
        st.session_state["prompt_text"] = prompt_text

        if chosen_template_id != "custom" and st.button("Vorlage speichern"):
            template_map[chosen_template_id]["text"] = prompt_text
            save_templates(templates, _PROMPT_TEMPLATES_PATH)
            st.success("Vorlage gespeichert.")

        provider_label = st.selectbox(
            "Provider",
            list(_PROVIDER_OPTIONS.keys()),
            index=list(_PROVIDER_OPTIONS.keys()).index(st.session_state["provider_label"])
            if st.session_state["provider_label"] in _PROVIDER_OPTIONS
            else 0,
        )
        st.session_state["provider_label"] = provider_label
        provider_id = _PROVIDER_OPTIONS[provider_label]
        st.session_state["model_name"] = st.text_input(
            "Modell",
            value=st.session_state["model_name"],
            placeholder="leer = Provider-Standard",
        )
        if provider_id == "none":
            st.info("Kein Provider gewaehlt. Es wird nur die lokale Analysegrundlage mit strukturierten Platzhalter-Ausgaben erzeugt.")

        local_pdfs: list[Path] = []
        for document in documents:
            resolved = _existing_local_document_path(
                session_path=str(document.get("session_path") or ""),
                local_path=str(document.get("local_path") or ""),
            )
            if resolved and resolved.suffix.lower() == ".pdf":
                local_pdfs.append(resolved)
        send_pdfs = False
        if local_pdfs and provider_id != "none":
            send_pdfs = st.checkbox(f"Lokale PDFs direkt mitsenden ({len(local_pdfs)})", value=False)
            st.caption(_local_document_policy_text())

        allowed_outputs = ", ".join(get_allowed_output_types(purpose_key))
        st.caption(f"Erwartete Output-Typen: {allowed_outputs}")

        run_disabled = not prompt_text.strip() and analysis_mode != "publication_only"
        if st.button("Analyse starten", type="primary", disabled=run_disabled):
            _run_analysis(
                db_path=db_path,
                session=session,
                scope=st.session_state["analysis_scope"],
                selected_tops=selected_tops,
                prompt=prompt_text,
                provider_id=provider_id,
                model_name=st.session_state["model_name"],
                pdf_paths=local_pdfs if send_pdfs else [],
                purpose=purpose_key,
                prompt_version=prompt_version,
                analysis_mode=analysis_mode,
                source_check=source_check,
            )

    with right_col:
        _render_source_check_panel(source_check)
        if st.session_state["analysis_error"]:
            st.error(st.session_state["analysis_error"])

        result_payloads = st.session_state.get("analysis_payloads") or {}
        selected_job = _find_selected_history_job(workflow_rows)

        if result_payloads:
            st.markdown("---")
            st.subheader("Aktuelles Ergebnis")
            _render_result_tabs(
                payloads=result_payloads,
                source_check=source_check,
                job_meta=_build_current_job_meta(st.session_state.get("analysis_record")),
                publication_output_ref=None,
                allow_status_update=False,
            )

        st.markdown("---")
        st.subheader("Vorhandene Analysejobs")
        filtered_rows = _render_history_filters(workflow_rows, chosen_session_id=str(chosen_session["session_id"]))
        if filtered_rows:
            job_labels = [
                (
                    f"Job {row['job_id']} | Sitzung {row.get('session_id') or '-'} | "
                    f"Zweck {row.get('purpose') or '-'} | "
                    f"Output {row.get('last_output_type') or '-'} | "
                    f"Status {row.get('status') or '-'}"
                )
                for row in filtered_rows
            ]
            label_map = {label: row for label, row in zip(job_labels, filtered_rows, strict=False)}
            selected_label = st.selectbox("Job-Details", job_labels)
            selected_job = label_map[selected_label]
            st.session_state["selected_history_job_id"] = int(selected_job["job_id"])
            _render_history_job_detail(selected_job, source_check)
        else:
            st.info("Keine passenden Analysejobs gefunden.")


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
    purpose: str,
    prompt_version: str,
    analysis_mode: str,
    source_check: dict,
) -> None:
    st.session_state["analysis_result"] = ""
    st.session_state["analysis_error"] = ""
    st.session_state["analysis_record"] = None
    st.session_state["analysis_payloads"] = {}

    if analysis_mode == "publication_only":
        st.session_state["analysis_error"] = (
            "Der Modus `Nur Publikationsentwurf aus vorhandener Struktur` ist in dieser Version "
            "nur ueber bereits vorhandene Analysejobs lesend verfuegbar."
        )
        st.rerun()
        return

    request = AnalysisRequest(
        db_path=db_path,
        session=session,
        scope=scope,
        selected_tops=selected_tops,
        prompt=prompt,
        provider_id=provider_id,
        model_name=model_name,
        prompt_version=prompt_version,
        purpose=purpose,
        pdf_paths=pdf_paths,
    )

    with st.spinner("Analyse laeuft ..."):
        try:
            record = _service.run_journalistic_analysis(request)
            result_text = record.ki_response or record.markdown
            st.session_state["analysis_result"] = result_text
            st.session_state["analysis_record"] = record
            st.session_state["analysis_payloads"] = _load_current_result_payloads(record, source_check)
            latest_workflow = _find_workflow_job_for_source(record.job_id, str(db_path))
            if latest_workflow:
                st.session_state["selected_history_job_id"] = int(latest_workflow["job_id"])
        except Exception as exc:  # noqa: BLE001
            st.session_state["analysis_error"] = f"Fehler bei der Analyse: {exc}"

    st.rerun()


def _load_analysis_history() -> list[dict]:
    rows = list_analysis_jobs_with_outputs(ANALYSIS_WORKFLOW_DB)
    if rows:
        return rows

    fallback_outputs = scan_analysis_outputs()
    grouped: dict[int, dict] = {}
    for row in fallback_outputs:
        job_id = int(row.get("job_id") or 0)
        if job_id not in grouped:
            grouped[job_id] = {
                "job_id": job_id,
                "session_id": str(row.get("session_id") or ""),
                "scope": str(row["normalized"].get("scope") or ""),
                "top_numbers": list(row["normalized"].get("top_numbers") or []),
                "purpose": str(row.get("purpose") or ""),
                "model_name": str(row["normalized"].get("model_name") or ""),
                "prompt_version": str(row["normalized"].get("prompt_version") or ""),
                "status": str(row.get("status") or ""),
                "created_at": str(row.get("created_at") or ""),
                "outputs": [],
                "last_output_type": "",
                "last_output_path": "",
                "review_status": "",
                "publication_status": "",
            }
        grouped[job_id]["outputs"].append(
            {
                "output_id": 0,
                "output_type": row["output_type"],
                "schema_version": row["normalized"].get("schema_version", ""),
                "json_path": row["json_path"],
                "markdown_path": "",
                "status": row.get("status", ""),
                "created_at": row.get("created_at", ""),
                "publication": None,
            }
        )
        if not grouped[job_id]["last_output_type"]:
            grouped[job_id]["last_output_type"] = row["output_type"]
            grouped[job_id]["last_output_path"] = row["json_path"]
    return list(grouped.values())


def _find_workflow_job_for_source(source_job_id: int, source_db: str) -> dict | None:
    rows = list_analysis_jobs_with_outputs(ANALYSIS_WORKFLOW_DB)
    for row in rows:
        if row.get("source_job_id") == source_job_id and str(row.get("source_db") or "") == source_db:
            return row
    return None


def _find_selected_history_job(rows: list[dict]) -> dict | None:
    selected_job_id = int(st.session_state.get("selected_history_job_id") or 0)
    for row in rows:
        if int(row.get("job_id") or 0) == selected_job_id:
            return row
    return rows[0] if rows else None


def _build_current_job_meta(record) -> dict | None:  # type: ignore[no-untyped-def]
    if not record:
        return None
    return {
        "job_id": record.job_id,
        "purpose": record.purpose,
        "status": record.status,
        "session_id": record.session_id,
        "top_numbers": record.top_numbers,
        "model_name": record.model_name,
        "prompt_version": record.prompt_version,
        "created_at": record.created_at,
        "document_count": record.document_count,
        "error_message": record.error_message,
    }


def _load_current_result_payloads(record, source_check: dict) -> dict[str, dict]:  # type: ignore[no-untyped-def]
    publication_payload = None
    if record.purpose == "journalistic_publication":
        publication_payload = {
            "schema_version": "2.0",
            "output_type": "publication_draft",
            "job_id": record.job_id,
            "session_id": record.session_id,
            "purpose": record.purpose,
            "title": "",
            "summary_short": "",
            "summary_long": "",
            "body_markdown": record.markdown,
            "hashtags": [],
            "seo_keywords": [],
            "slug": "",
            "status": "draft",
            "review": {
                "required": True,
                "status": "pending",
                "notes": "",
                "reviewed_at": "",
                "reviewed_by": "",
            },
            "publication": {
                "target": "local_static_site",
                "status": "not_published",
                "published_url": "",
                "published_at": "",
            },
        }
    return {
        "raw_analysis": normalize_analysis_for_ui(
            {
                "schema_version": "2.0",
                "output_type": "raw_analysis",
                "job_id": record.job_id,
                "session_id": record.session_id,
                "scope": record.scope,
                "top_numbers": record.top_numbers,
                "documents": source_check.get("rows", []),
                "created_at": record.created_at,
            }
        ),
        "structured_analysis": normalize_analysis_for_ui(
            {
                "schema_version": "2.0",
                "output_type": "structured_analysis",
                "job_id": record.job_id,
                "session_id": record.session_id,
                "purpose": record.purpose,
                "topic": {"title": "", "category": [], "location": []},
                "open_questions": [],
                "risks_or_uncertainties": [record.error_message] if record.error_message else [],
                "created_at": record.created_at,
            }
        ),
        "publication_draft": normalize_analysis_for_ui(publication_payload) if publication_payload else {},
        "article_markdown": {
            "markdown": record.markdown,
            "ki_response": record.ki_response,
            "prompt_text": record.prompt_text,
        },
    }


def _render_source_check_panel(source_check: dict) -> None:
    st.subheader("Quellencheck")
    metric_cols = st.columns(4)
    metric_cols[0].metric("Dokumente", str(source_check.get("document_count", 0)))
    metric_cols[1].metric("Lokale Dateien", str(source_check.get("local_available_count", 0)))
    metric_cols[2].metric("URLs", str(source_check.get("url_available_count", 0)))
    metric_cols[3].metric("PDF verfuegbar", str(source_check.get("pdf_available_count", 0)))
    if source_check.get("document_types"):
        st.caption(f"Dokumenttypen: {', '.join(source_check['document_types'])}")
    for message in source_check.get("messages", []):
        if "ohne" in message:
            st.warning(message)
        else:
            st.info(message)
    if not source_check.get("document_count"):
        st.info("Keine Dokumente fuer diese Auswahl gefunden. Die Analyse ist trotzdem startbar.")


def _render_history_filters(rows: list[dict], chosen_session_id: str) -> list[dict]:
    filter_cols = st.columns(6)
    session_filter = filter_cols[0].selectbox(
        "Sitzung",
        [""] + sorted({str(row.get("session_id") or "") for row in rows}),
        index=([""] + sorted({str(row.get("session_id") or "") for row in rows})).index(chosen_session_id)
        if chosen_session_id in {str(row.get("session_id") or "") for row in rows}
        else 0,
    )
    purpose_filter = filter_cols[1].selectbox("Zweck", [""] + sorted({str(row.get("purpose") or "") for row in rows}))
    output_filter = filter_cols[2].selectbox("Output-Typ", [""] + sorted({str(row.get("last_output_type") or "") for row in rows}))
    status_filter = filter_cols[3].selectbox("Status", [""] + sorted({str(row.get("status") or "") for row in rows}))
    review_filter = filter_cols[4].selectbox("Review", [""] + sorted({str(row.get("review_status") or "") for row in rows if row.get("review_status")}))
    publication_filter = filter_cols[5].selectbox("Publication", [""] + sorted({str(row.get("publication_status") or "") for row in rows if row.get("publication_status")}))
    return filter_history_rows(
        rows,
        session_id=session_filter,
        purpose=purpose_filter,
        output_type=output_filter,
        status=status_filter,
        review_status=review_filter,
        publication_status=publication_filter,
    )


def _render_history_job_detail(job: dict, source_check: dict) -> None:
    payloads = _load_job_payloads(job)
    publication_output_ref = _find_publication_output(job)
    st.caption("Veroeffentlichung ist vorbereitet, aber in dieser Version noch nicht aktiv.")
    _render_result_tabs(
        payloads=payloads,
        source_check=source_check,
        job_meta=job,
        publication_output_ref=publication_output_ref,
        allow_status_update=publication_output_ref is not None and publication_output_ref.get("output_id"),
    )


def _load_job_payloads(job: dict) -> dict[str, dict]:
    payloads: dict[str, dict] = {"article_markdown": {"markdown": "", "ki_response": "", "prompt_text": ""}}
    for output in job.get("outputs", []):
        output_type = str(output.get("output_type") or "")
        json_payload = load_json_file(str(output.get("json_path") or ""))
        if json_payload:
            payloads[output_type] = normalize_analysis_for_ui(json_payload)
        markdown_path = str(output.get("markdown_path") or "")
        if markdown_path:
            path = Path(markdown_path)
            if path.exists():
                payloads["article_markdown"] = {
                    "markdown": path.read_text(encoding="utf-8"),
                    "ki_response": "",
                    "prompt_text": "",
                }
    return payloads


def _find_publication_output(job: dict) -> dict | None:
    for output in job.get("outputs", []):
        if output.get("output_type") == "publication_draft":
            return output
    return None


def _render_result_tabs(
    *,
    payloads: dict[str, dict],
    source_check: dict,
    job_meta: dict | None,
    publication_output_ref: dict | None,
    allow_status_update: bool,
) -> None:
    overview_tab, structured_tab, sources_tab, publication_tab, raw_tab = st.tabs(
        ["Uebersicht", "Strukturierte Analyse", "Quellen", "Publikationsentwurf", "Rohdaten"]
    )
    with overview_tab:
        if job_meta:
            st.markdown(f"- Job-ID: `{job_meta.get('job_id', '-')}`")
            st.markdown(f"- Zweck: `{job_meta.get('purpose', '-')}`")
            st.markdown(f"- Status: `{job_meta.get('status', '-')}`")
            st.markdown(f"- Session-ID: `{job_meta.get('session_id', '-')}`")
            st.markdown(f"- TOPs: {', '.join(job_meta.get('top_numbers') or []) or '-'}")
            st.markdown(f"- Modell: `{job_meta.get('model_name', '-')}`")
            st.markdown(f"- Prompt-Version: `{job_meta.get('prompt_version', '-')}`")
            st.markdown(f"- Erstellt: `{job_meta.get('created_at', '-')}`")
            if "document_count" in job_meta:
                st.markdown(f"- Dokumentanzahl: `{job_meta.get('document_count', 0)}`")
            if job_meta.get("error_message"):
                st.warning(str(job_meta["error_message"]))

    with structured_tab:
        structured_payload = payloads.get("structured_analysis") or {}
        if structured_payload.get("legacy_notice"):
            st.warning(structured_payload["legacy_notice"])
        structured = structured_payload.get("structured") or {}
        topic = structured.get("topic") or {}
        st.markdown(f"**Thema:** {topic.get('title') or '-'}")
        st.markdown(f"**Kategorien:** {', '.join(topic.get('category') or []) or '-'}")
        st.markdown(f"**Ortsteile:** {', '.join(topic.get('location') or []) or '-'}")
        st.markdown(f"**Kernaussagen:** {json.dumps(structured.get('facts') or [], ensure_ascii=False, indent=2)}")
        st.markdown(f"**Entscheidungen:** {json.dumps(structured.get('decisions') or [], ensure_ascii=False, indent=2)}")
        st.markdown(
            f"**Finanzielle Auswirkungen:** {json.dumps(structured.get('financial_effects') or [], ensure_ascii=False, indent=2)}"
        )
        st.markdown(f"**Betroffene Gruppen:** {', '.join(structured.get('affected_groups') or []) or '-'}")
        relevance = structured.get("citizen_relevance") or {}
        st.markdown(f"**Buergerrelevanz:** Score {relevance.get('score', 0)}")
        st.markdown(f"**Offene Fragen:** {json.dumps(structured.get('open_questions') or [], ensure_ascii=False, indent=2)}")
        st.markdown(
            f"**Unsicherheiten:** {json.dumps(structured.get('risks_or_uncertainties') or [], ensure_ascii=False, indent=2)}"
        )

    with sources_tab:
        raw_payload = payloads.get("raw_analysis") or {}
        documents = list((raw_payload.get("sources") or {}).get("documents") or raw_payload.get("documents") or [])
        if not documents:
            documents = source_check.get("rows", [])
        for document in documents:
            st.markdown(
                f"- {document.get('title') or '-'} | TOP {document.get('agenda_item') or document.get('top') or '-'} | "
                f"{document.get('document_type') or '-'} | "
                f"lokal: {'ja' if document.get('source_available') or document.get('local_exists') else 'nein'} | "
                f"URL: {document.get('url') or '-'}"
            )
            if document.get("local_path"):
                st.code(str(document["local_path"]))
            if document.get("url"):
                st.link_button("URL oeffnen", str(document["url"]))

    with publication_tab:
        publication_payload = payloads.get("publication_draft") or {}
        if not publication_payload:
            st.info("Kein Publikationsentwurf fuer diesen Job vorhanden.")
        else:
            publication_data = publication_payload.get("publication_draft") or {}
            publication_state = apply_publication_state(
                publication_payload,
                (publication_output_ref or {}).get("publication"),
            )
            st.markdown(f"**Titel:** {publication_state.get('title') or '-'}")
            st.markdown(f"**Kurzfassung:** {publication_state.get('summary_short') or '-'}")
            st.markdown(f"**Langfassung:** {publication_state.get('summary_long') or '-'}")
            st.markdown("**Artikeltext:**")
            st.text_area("Entwurf", value=publication_state.get("body_markdown") or "", height=220, key=f"publication_body_{job_meta.get('job_id') if job_meta else 'current'}")
            st.markdown(f"**Hashtags:** {', '.join(publication_state.get('hashtags') or []) or '-'}")
            st.markdown(f"**SEO-Schluesselwoerter:** {', '.join(publication_state.get('seo_keywords') or []) or '-'}")
            st.markdown(f"**Slug:** `{publication_state.get('slug') or '-'}`")
            st.markdown(f"**Status:** `{publication_data.get('status') or publication_state.get('status') or '-'}`")
            st.markdown(f"**Review-Status:** `{publication_state.get('review', {}).get('status', '-')}`")
            st.markdown(f"**Publication-Status:** `{publication_state.get('publication', {}).get('status', '-')}`")
            st.caption("Veroeffentlichung ist vorbereitet, aber in dieser Version noch nicht aktiv.")
            _render_review_editor(
                publication_state=publication_state,
                publication_output_ref=publication_output_ref,
                allow_status_update=allow_status_update,
            )

    with raw_tab:
        st.subheader("JSON-Ausgabe")
        for output_type in ("raw_analysis", "structured_analysis", "publication_draft"):
            if payloads.get(output_type):
                st.code(
                    json.dumps(payloads[output_type], indent=2, ensure_ascii=False),
                    language="json",
                )
        article = payloads.get("article_markdown") or {}
        if article.get("markdown"):
            st.subheader("Markdown-Ausgabe")
            st.text_area("Markdown", value=article["markdown"], height=220, key=f"raw_markdown_{job_meta.get('job_id') if job_meta else 'current'}")
        if article.get("ki_response"):
            st.subheader("KI-Rohantwort")
            st.text_area("KI", value=article["ki_response"], height=160, key=f"raw_ki_{job_meta.get('job_id') if job_meta else 'current'}")
        if article.get("prompt_text"):
            st.subheader("Prompt")
            st.text_area("Prompt", value=article["prompt_text"], height=120, key=f"raw_prompt_{job_meta.get('job_id') if job_meta else 'current'}")


def _render_review_editor(
    *,
    publication_state: dict,
    publication_output_ref: dict | None,
    allow_status_update: bool,
) -> None:
    review = publication_state.get("review") or {}
    publication = publication_state.get("publication") or {}
    st.markdown("---")
    st.subheader("Review und Publication")
    if not allow_status_update:
        st.info("Status ist fuer dieses Ergebnis nur lesend verfuegbar.")
        return

    output_id = int(publication_output_ref.get("output_id") or 0)
    review_required = st.checkbox(
        "Review erforderlich",
        value=bool(review.get("required", True)),
        key=f"review_required_{output_id}",
    )
    review_status = st.selectbox(
        "Review-Status",
        ["pending", "needs_changes", "approved", "rejected"],
        index=["pending", "needs_changes", "approved", "rejected"].index(str(review.get("status") or "pending")),
        key=f"review_status_{output_id}",
    )
    review_notes = st.text_area(
        "Review-Notizen",
        value=str(review.get("notes") or ""),
        height=120,
        key=f"review_notes_{output_id}",
    )
    reviewed_by = st.text_input(
        "Review-Person",
        value=str(review.get("reviewed_by") or ""),
        key=f"reviewed_by_{output_id}",
    )
    reviewed_at = st.text_input(
        "Review-Zeitpunkt",
        value=str(review.get("reviewed_at") or ""),
        placeholder="2026-04-27T12:00:00Z",
        key=f"reviewed_at_{output_id}",
    )
    publication_status = st.selectbox(
        "Publication-Status",
        ["not_published", "draft_created", "scheduled", "published", "failed"],
        index=["not_published", "draft_created", "scheduled", "published", "failed"].index(
            str(publication.get("status") or "not_published")
        ),
        key=f"publication_status_{output_id}",
    )
    published_url = st.text_input(
        "Published URL",
        value=str(publication.get("published_url") or ""),
        key=f"published_url_{output_id}",
    )
    published_at = st.text_input(
        "Published at",
        value=str(publication.get("published_at") or ""),
        placeholder="2026-04-27T12:00:00Z",
        key=f"published_at_{output_id}",
    )
    if st.button("Status lokal speichern", key=f"save_publication_status_{output_id}"):
        try:
            update_publication_job(
                output_id=output_id,
                review_required=review_required,
                review_status=validate_review_status(review_status),
                review_notes=review_notes,
                reviewed_by=reviewed_by,
                reviewed_at=reviewed_at or datetime.utcnow().isoformat() + "Z",
                publication_status=validate_publication_status(publication_status),
                published_url=published_url,
                published_at=published_at,
                target=str(publication.get("target") or "local_static_site"),
                title=str(publication_state.get("title") or ""),
                slug=str(publication_state.get("slug") or ""),
            )
            st.success("Status lokal gespeichert.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))


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
# Tab: Semantische Suche
# ---------------------------------------------------------------------------

def _tab_semantic_search(db_path: Path) -> None:
    st.header("🔍 Semantische Suche")

    dependency_error = _semantic_search_dependency_error()
    if dependency_error:
        st.warning(dependency_error)
        return

    vector_dir = _semantic_search_vector_dir(db_path)
    if vector_dir is None:
        st.info(
            "Die semantische Suche ist derzeit nur für den lokalen Index verfügbar. "
            "Bitte in der Sidebar `Lokaler Index` wählen."
        )
        return

    # Check that the Qdrant index has been built
    if not vector_dir.exists():
        st.info(
            "Der Vektor-Index wurde noch nicht erstellt. "
            "Bitte zuerst folgenden Befehl ausführen:\n\n"
            "```\n"
            "python scripts/build_vector_index.py\n"
            "```"
        )
        return

    # Search form
    query_text = st.text_input(
        "Suchanfrage",
        placeholder="z. B. Beschluss Haushalt Schulen",
    )

    st.caption("Ergebnisse sind nach RRF-Rangfusion sortiert; der angezeigte Score ist kein Prozentwert.")

    col_limit, col_filter = st.columns([1, 2])
    with col_limit:
        result_limit = st.slider("Anzahl Ergebnisse", min_value=5, max_value=20, value=10)

    # Optional session filter
    session_filter_id: int | None = None
    with col_filter:
        selected_session = st.session_state.get("selected_session")
        if selected_session:
            use_session_filter = st.checkbox(
                f"Nur aktuelle Sitzung ({selected_session.get('date', '')} – {selected_session.get('committee', '')})"
            )
            if use_session_filter:
                session_filter_id = selected_session.get("session_id")

    if st.button("Suchen", type="primary", disabled=not query_text.strip()):
        _run_semantic_search(
            query=query_text.strip(),
            limit=result_limit,
            session_id=session_filter_id,
            qdrant_dir=vector_dir,
        )

    # Display results stored in session state
    all_results: list[dict] = st.session_state.get("search_results", [])
    search_error: str = st.session_state.get("search_error", "")

    if search_error:
        st.error(search_error)

    if all_results:
        st.markdown(f"**{len(all_results)} Ergebnis(se) gefunden**")
        st.markdown("---")
        for rank, hit in enumerate(all_results, start=1):
            title = hit.get("title") or "(kein Titel)"
            date_str = hit.get("date") or ""
            committee_str = hit.get("committee") or ""
            agenda_item = hit.get("agenda_item") or ""
            doc_type = hit.get("document_type") or ""
            url = hit.get("url") or ""
            local_path = hit.get("local_path") or ""

            with st.container():
                col_score, col_info = st.columns([1, 5])
                with col_score:
                    st.metric("Rang", f"#{rank}")
                    st.caption(f"RRF: {_format_rrf_score(hit['score'])}")
                with col_info:
                    st.markdown(f"**{title}**")
                    if doc_type:
                        st.caption(f"Typ: {doc_type}")
                    if date_str or committee_str:
                        st.caption(f"📅 {date_str}  |  🏛 {committee_str}")
                    if agenda_item:
                        st.caption(f"📋 TOP: {agenda_item}")
                    btn_cols = st.columns([1, 1, 4])
                    resolved_path = _existing_local_document_path(local_path=local_path)
                    if resolved_path:
                        file_url = resolved_path.resolve().as_uri()
                        btn_cols[0].link_button("PDF öffnen", file_url)
                    elif url:
                        btn_cols[0].link_button("Online öffnen", url)
            st.markdown("---")


@st.cache_resource
def _get_search_resources(qdrant_dir: str):
    """Load and cache embedders and DocumentVectorStore across reruns."""
    from src.analysis.embeddings import HarrierEmbedder
    from src.analysis.bm25_sparse import BM25Encoder
    from src.analysis.vector_store import DocumentVectorStore

    embedder = HarrierEmbedder()
    bm25 = BM25Encoder()
    store = DocumentVectorStore(Path(qdrant_dir))
    return embedder, bm25, store


def _run_semantic_search(
    *,
    query: str,
    limit: int,
    session_id: int | None,
    qdrant_dir: Path,
) -> None:
    """Execute hybrid search (Harrier dense + BM25 sparse, RRF fusion)."""
    st.session_state["search_results"] = []
    st.session_state["search_error"] = ""

    try:
        with st.spinner("Berechne Embedding und durchsuche Index …"):
            embedder, bm25, store = _get_search_resources(str(qdrant_dir))
            query_dense = embedder.embed_query(query)
            query_sparse = bm25.encode_query(query)
            results = store.search(
                query_dense=query_dense,
                query_sparse=query_sparse,
                limit=limit,
                session_id=session_id,
            )

        st.session_state["search_results"] = results
    except Exception as exc:  # noqa: BLE001
        st.session_state["search_error"] = f"Fehler bei der Suche: {exc}"

    st.rerun()


# ---------------------------------------------------------------------------
# Tab: Developer
# ---------------------------------------------------------------------------
def _tab_developer(db_path: Path) -> None:
    st.header("🛠️ Developer-Tools")
    st.caption(
        "Interne Arbeitsoberfläche für Fetch-, Build- und Diagnosepfade. "
        "Die große Nutzeroberfläche wird separat über Django konzipiert."
    )

    tool_scripts, tool_status, tool_committees = st.tabs(
        ["📥 Skripte", "📊 Status", "🏛️ Gremien"]
    )

    with tool_scripts:
        _tab_developer_scripts(db_path)
    with tool_status:
        _tab_developer_status(db_path)
    with tool_committees:
        _tab_developer_committees(db_path)


def _tab_developer_scripts(db_path: Path) -> None:
    st.subheader("Skripte und Build-Pfade")

    col_year, col_months = st.columns(2)
    with col_year:
        year = st.number_input("Jahr", min_value=2000, max_value=2050, value=2024, step=1, key="developer_year")
    with col_months:
        month_options = [str(m) for m in range(1, 13)]
        months = st.multiselect("Monate (leer = alle)", month_options, key="developer_months")

    preset_year = int(year)
    preset_months = [str(month) for month in months]

    st.caption("Die Preset-Buttons verwenden das aktuell gewählte Jahr und die aktuell gewählten Monate.")
    st.markdown("---")

    preset_col1, preset_col2, preset_col3 = st.columns(3)
    preset_actions = [
        (label, _developer_preset_commands(label, year=preset_year, months=preset_months))
        for label in ("Fetch + Build Local", "Build Local + Vector", "Build Online Index")
    ]
    for col, (label, commands) in zip(
        (preset_col1, preset_col2, preset_col3), preset_actions, strict=False
    ):
        with col:
            if st.button(label, use_container_width=True):
                _run_script_preset(label, commands)

    st.markdown("---")

    script_options = _developer_script_options()
    chosen_script_label = st.selectbox("Script auswählen", list(script_options.keys()))
    script_name = script_options[chosen_script_label]

    extra_args: list[str] = []
    if script_name in {"fetch_sessions", "build_online_index_db"}:
        extra_args = [str(year)]
        if months:
            extra_args += ["--months"] + months
    elif script_name == "build_vector_index":
        st.caption(f"SQLite-Quelle: `{LOCAL_INDEX_DB}` | Qdrant: `{QDRANT_DIR}`")
        vector_limit = st.number_input(
            "Limit (0 = kein Limit)", min_value=0, max_value=100000, value=0, step=100
        )
        extra_args = ["--db", str(LOCAL_INDEX_DB), "--qdrant-dir", str(QDRANT_DIR)]
        if vector_limit:
            extra_args += ["--limit", str(vector_limit)]
    else:
        st.caption(f"SQLite-Quelle: `{db_path}`")

    if st.button("▶ Ausführen", type="primary"):
        script_path = REPO_ROOT / "scripts" / f"{script_name}.py"
        cmd = [sys.executable, str(script_path)] + extra_args
        with st.spinner(f"Führe `{script_name}` aus …"):
            exit_code, output_text = _run_script_command(cmd)
        st.session_state["script_output"] = output_text

        if exit_code == 0:
            st.success(f"Abgeschlossen (Exit-Code {exit_code})")
        else:
            st.error(f"Fehler (Exit-Code {exit_code})")

    if st.session_state["script_output"]:
        st.text_area("Ausgabe", value=st.session_state["script_output"], height=320)


def _developer_preset_commands(label: str, *, year: int, months: list[str]) -> list[list[str]]:
    """Return the preset command sequence using the currently selected date filters."""
    date_args = [str(year)]
    if months:
        date_args += ["--months", *months]

    if label == "Fetch + Build Local":
        return [
            [sys.executable, str(REPO_ROOT / "scripts" / "fetch_sessions.py"), *date_args],
            [sys.executable, str(REPO_ROOT / "scripts" / "build_local_index.py")],
        ]
    if label == "Build Local + Vector":
        return [
            [sys.executable, str(REPO_ROOT / "scripts" / "build_local_index.py")],
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "build_vector_index.py"),
                "--db",
                str(LOCAL_INDEX_DB),
                "--qdrant-dir",
                str(QDRANT_DIR),
            ],
        ]
    if label == "Build Online Index":
        return [
            [sys.executable, str(REPO_ROOT / "scripts" / "build_online_index_db.py"), *date_args],
        ]
    raise ValueError(f"Unknown preset label: {label}")


def _run_script_preset(label: str, commands: list[list[str]]) -> None:
    output_blocks: list[str] = []
    failed = False
    with st.spinner(f"Führe Preset `{label}` aus …"):
        for cmd in commands:
            exit_code, output_text = _run_script_command(cmd)
            output_blocks.append(f"$ {' '.join(cmd)}\n{output_text}".strip())
            if exit_code != 0:
                failed = True
                break

    st.session_state["script_output"] = "\n\n".join(output_blocks)
    if failed:
        st.error(f"Preset `{label}` ist fehlgeschlagen.")
    else:
        st.success(f"Preset `{label}` abgeschlossen.")


def _tab_developer_status(db_path: Path) -> None:
    st.subheader("Projektstatus")
    if st.button("Status aktualisieren", key="refresh_project_status"):
        _collect_data_status_cached.clear()

    snapshot = _collect_data_status(db_path)
    metric_cols = st.columns(5)
    metric_cols[0].metric("Rohsitzungen", str(snapshot["raw_session_count"]))
    metric_cols[1].metric("Rohdateien", str(snapshot["raw_file_count"]))
    metric_cols[2].metric(
        "Lokaler Index",
        "vorhanden" if snapshot["local_index_exists"] else "fehlt",
        None if snapshot["local_index_sessions"] is None else f"{snapshot['local_index_sessions']} Sitzungen",
    )
    metric_cols[3].metric(
        "Online-Index",
        "vorhanden" if snapshot["online_index_exists"] else "fehlt",
        None if snapshot["online_index_sessions"] is None else f"{snapshot['online_index_sessions']} Sitzungen",
    )
    metric_cols[4].metric(
        "Vektorindex",
        "vorhanden" if snapshot["vector_index_exists"] else "fehlt",
        f"{snapshot['vector_index_file_count']} Dateien",
    )

    st.markdown("---")
    st.subheader("Datenpfade")
    st.markdown(f"- `data/raw`: `{RAW_DATA_DIR}`")
    st.markdown(f"- `data/db`: `{DB_DIR}`")
    st.markdown(f"- `Lokaler Index`: `{LOCAL_INDEX_DB}`")
    st.markdown(f"- `Online-Index`: `{ONLINE_INDEX_DB}`")
    st.markdown(f"- `Qdrant`: `{QDRANT_DIR}`")

    st.markdown("---")
    st.subheader("Aktive Datenbank")
    if snapshot["selected_db_exists"]:
        session_count_text = (
            "unbekannt"
            if snapshot["selected_db_sessions"] is None
            else str(snapshot["selected_db_sessions"])
        )
        st.success(
            f"`{snapshot['selected_db_name']}` ist vorhanden und enthaelt {session_count_text} Sitzung(en)."
        )
    else:
        st.warning(f"`{snapshot['selected_db_name']}` wurde nicht gefunden.")


def _tab_developer_committees(db_path: Path) -> None:
    st.subheader("Gremienübersicht")
    committees = _store.list_committees(db_path)

    if not db_path.exists():
        st.warning(f"SQLite-Datenbank nicht gefunden: `{db_path}`")
        return

    if not committees:
        st.info("Keine Gremien in der aktuell gewählten Datenbank gefunden.")
        return

    st.markdown(f"**{len(committees)} Gremium/Gremien gefunden**")
    for committee in committees:
        st.markdown(f"- {committee}")


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

    tab_analyse, tab_search, tab_dev, tab_settings = st.tabs(
        ["🔍 Analyse", "🔍 Semantische Suche", "🛠️ Developer", "⚙️ Einstellungen"]
    )

    with tab_analyse:
        _tab_analyse(db_path)
    with tab_search:
        _tab_semantic_search(db_path)
    with tab_dev:
        _tab_developer(db_path)
    with tab_settings:
        _tab_einstellungen()


if __name__ == "__main__":
    main()
