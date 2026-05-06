"""Deprecated Streamlit interface kept for legacy compatibility.

Active UI development happens in the Django application under ``web/``.
Use ``scripts/run_web.py`` as the primary UI start command.
"""

from __future__ import annotations

import importlib
import sqlite3
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
from src.fetching.storage_layout import resolve_local_file_path
from src.interfaces.shared.analysis_store import AnalysisStore, SessionFilters
from src.paths import (
    DB_DIR,
    LOCAL_INDEX_DB,
    ONLINE_INDEX_DB,
    PROMPT_TEMPLATES_PATH,
    QDRANT_DIR,
    RAW_DATA_DIR,
    REPO_ROOT,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_PROMPT_TEMPLATES_PATH = PROMPT_TEMPLATES_PATH
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
        "provider_label": "Kein Provider (nur Grundlage)",
        "model_name": "",
        "prompt_text": "",
        "selected_template_id": None,
        "analysis_result": "",
        "analysis_error": "",
        "analysis_record": None,
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
            st.caption(
                "✅ lokal nutzbar, ⚠️ lokal blockiert oder nicht vorhanden. "
                f"{_local_document_policy_text()}"
            )
            for doc in documents:
                top_nr = doc.get("agenda_item") or "–"
                title = doc.get("title") or "(kein Titel)"
                resolved_local = _existing_local_document_path(
                    session_path=str(doc.get("session_path") or ""),
                    local_path=str(doc.get("local_path") or ""),
                )
                available = "✅" if resolved_local is not None else "⚠️"
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
    local_pdfs: list[Path] = []
    for doc in documents:
        resolved_path = _existing_local_document_path(
            session_path=str(doc.get("session_path") or ""),
            local_path=str(doc.get("local_path") or ""),
        )
        if resolved_path and resolved_path.suffix.lower() == ".pdf":
            local_pdfs.append(resolved_path)
    send_pdfs = False
    if local_pdfs and provider_id != "none":
        send_pdfs = st.checkbox(
            f"PDFs direkt senden ({len(local_pdfs)} PDF(s) verfügbar)",
            value=False,
            help=(
                "Nur lokal aufloesbare Dateien unter data/raw werden angeboten. "
                "Claude/OpenAI: native Base64-Uebertragung. Ollama: Text-Extraktion."
            ),
        )
        st.caption(_local_document_policy_text())

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
