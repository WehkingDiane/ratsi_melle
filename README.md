# Ratsinformations-Analysetool Melle

Dieses Projekt sammelt öffentliche Sitzungs- und Dokumentdaten aus dem Ratsinformationssystem der Stadt Melle, bereitet sie strukturiert auf und stellt sie für Recherche, KI-Analysen und semantische Suche bereit.

## Zweck

- Sitzungen, Tagesordnungspunkte und Dokumente aus SessionNet erfassen
- lokale und online-basierte Indizes für Recherche aufbauen
- Dokumente für KI-gestützte Analysen vorbereiten
- semantische Suche über einen lokalen Qdrant-Index bereitstellen

## Oberflächen

- **Django-Weboberflaeche** unter `web/` ist der aktive und primaere UI-Pfad fuer Recherche, Analyse, Prompt-Vorlagen und Datenpflege.
- **Streamlit-Weboberflaeche (deprecated)** bleibt nur als Legacy-Kompatibilitaet im Repository und wird nicht mehr als Hauptpfad dokumentiert.
- **Desktop-GUI (deprecated)** bleibt vorerst im Repository, ist aber kein aktiver Navigations- oder Entwicklungs-Pfad mehr.

## Voraussetzungen

- Python 3.11+
- `pip`
- `git`
- optional fuer deprecated Legacy-Pfade: `customtkinter`, `CTkMenuBar`, unter WSL zusaetzlich `python3-tk`

## Installation

```bash
pip install -r requirements.txt
```

`torch` wird weiterhin separat installiert, passend zur Zielumgebung.

Deprecated UI-Pfade sind nicht Teil der Kernabhaengigkeiten. Fuer Wartung oder lokalen Betrieb von Streamlit/Desktop-Legacy-UI:

```bash
pip install -r requirements-legacy-ui.txt
```

## Wichtige Befehle

```bash
python scripts/fetch_sessions.py 2024 --months 5 6
python scripts/fetch_session_from_index.py --list --from-date 2026-04-01 --to-date 2026-04-30
python scripts/fetch_session_from_index.py --session-id 7128
python scripts/build_local_index.py
python scripts/build_online_index_db.py 2024 --months 5 6
python scripts/build_vector_index.py
python scripts/run_web.py
python -m pytest
```

`fetch_session_from_index.py` nutzt `data/db/online_session_index.sqlite` als Auswahlquelle. Damit kann eine einzelne Sitzung anhand ihrer `session_id` nach `data/raw/` geladen werden, ohne die Monatsübersicht erneut komplett abzuarbeiten.

Die Django-Weboberfläche startet lokal mit:

```bash
python scripts/run_web.py
```

Sie ist danach standardmäßig unter `http://127.0.0.1:8000/` erreichbar. Details stehen in [docs/web_ui.md](/mnt/c/users/diane/git/ratsi_melle/docs/web_ui.md:1).

`scripts/run_web.py` ist der primaere UI-Startpunkt. `src/interfaces/web/streamlit_app.py` ist deprecated und nur noch fuer Legacy-Kompatibilitaet vorgesehen.
Die Streamlit-Abhaengigkeit liegt deshalb in `requirements-legacy-ui.txt`, nicht in `requirements.txt`.

## Daten und Suche

- Lokaler SQLite-Index: `data/db/local_index.sqlite`
- Online-Index: `data/db/online_session_index.sqlite`
- Lokaler Vektorindex: `data/db/qdrant/`
- Analyse-Workflow und v2-Ausgaben: [docs/analysis_outputs.md](/mnt/c/users/diane/git/ratsi_melle/docs/analysis_outputs.md:1)
- Private Prompt-Vorlagen: `data/private/prompt_templates.json`
- Private Prompt-Artefakte und gerenderte Snapshots: `data/private/analysis_prompts/` und `data/private/prompt_snapshots/`
- Optionaler Hugging-Face-Token: sichere Ablage ueber `/einstellungen/` im OS-Schluesselring; Fallback ueber `HF_TOKEN` oder `HUGGING_FACE_HUB_TOKEN`

Echte Prompt-Vorlagen und gerenderte Prompt-Snapshots gehören nicht ins Repository. Die privaten Pfade unter `data/private/` sind durch `.gitignore` geschützt.

## Sicherheitsgrenzen

- Lokale Dokumentpfade werden nur akzeptiert, wenn sie unter einer zulässigen `data/raw/`-Wurzel liegen.
- `manifest.json`-Pfade bleiben auf das jeweilige Sitzungspaket begrenzt; Traversal per `../` wird verworfen.
- Dokumentdownloads und lokale Text-/PDF-Extraktion sind aktuell auf 25 MiB pro Datei begrenzt, um Speicher- und Plattenplatz-DoS zu begrenzen.
- API-Keys und der optionale Hugging-Face-Token werden ueber den OS-Schluesselring gespeichert; Secrets gehoeren nicht in Repository-Dateien.

Die gemeinsame Grundlagen-Doku für Zielsystem, Fetching, Datenhaltung, Vektorindex und semantische Suche steht in [docs/data_processing_concept.md](/mnt/c/users/diane/git/ratsi_melle/docs/data_processing_concept.md:1).

## Weitere Dokumentation

- Projekt- und Arbeitsregeln: [AGENTS.md](/mnt/c/users/diane/git/ratsi_melle/AGENTS.md:1)
- Repository-Regeln: [docs/repository_guidelines.md](/mnt/c/users/diane/git/ratsi_melle/docs/repository_guidelines.md:1)
- Aktueller Stand der Django-Weboberfläche: [docs/web_ui.md](/mnt/c/users/diane/git/ratsi_melle/docs/web_ui.md:1)
- Django-Zielkonzept: [docs/django_ui_concept.md](/mnt/c/users/diane/git/ratsi_melle/docs/django_ui_concept.md:1)
- Offene Aufgaben und Ausbaupfade: [docs/project_tasks.md](/mnt/c/users/diane/git/ratsi_melle/docs/project_tasks.md:1)
