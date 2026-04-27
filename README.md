# Ratsinformations-Analysetool Melle

Dieses Projekt sammelt oeffentliche Sitzungs- und Dokumentdaten aus dem Ratsinformationssystem der Stadt Melle, bereitet sie strukturiert auf und stellt sie fuer Recherche, KI-Analysen und semantische Suche bereit.

## Zweck

- Sitzungen, Tagesordnungspunkte und Dokumente aus SessionNet erfassen
- lokale und online-basierte Indizes fuer Recherche aufbauen
- Dokumente fuer KI-gestuetzte Analysen vorbereiten
- semantische Suche ueber einen lokalen Qdrant-Index bereitstellen

## Oberflaechen

- **Developer-UI (Streamlit)** fuer schnelle interne Workflows und Skriptsteuerung
- **Django-Hauptoberflaeche (geplant)** fuer die spaetere produktartige Recherche- und Analyseoberflaeche
- **Desktop-GUI (Legacy)** bleibt vorerst im Repository, ist aber kein aktiver Hauptpfad mehr

## Voraussetzungen

- Python 3.11+
- `pip`
- `git`
- optional fuer die alte Desktop-GUI: `customtkinter`, `CTkMenuBar`, unter WSL zusaetzlich `python3-tk`

## Installation

```bash
pip install -r requirements.txt
```

`torch` wird weiterhin separat installiert, passend zur Zielumgebung.

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

`fetch_session_from_index.py` nutzt `data/db/online_session_index.sqlite` als Auswahlquelle. Damit kann eine einzelne Sitzung anhand ihrer `session_id` nach `data/raw/` geladen werden, ohne die Monatsuebersicht erneut komplett abzuarbeiten.

## Daten und Suche

- Lokaler SQLite-Index: `data/db/local_index.sqlite`
- Online-Index: `data/db/online_session_index.sqlite`
- Lokaler Vektorindex: `data/db/qdrant/`
- Analyse-Workflow und v2-Ausgaben: [docs/analysis_outputs.md](/mnt/c/users/diane/git/ratsi_melle/docs/analysis_outputs.md:1)

## Sicherheitsgrenzen

- Lokale Dokumentpfade werden nur akzeptiert, wenn sie unter einer zulaessigen `data/raw/`-Wurzel liegen.
- `manifest.json`-Pfade bleiben auf das jeweilige Sitzungspaket begrenzt; Traversal per `../` wird verworfen.
- Dokumentdownloads und lokale Text-/PDF-Extraktion sind aktuell auf 25 MiB pro Datei begrenzt, um Speicher- und Plattenplatz-DoS zu begrenzen.

Die gemeinsame Grundlagen-Doku fuer Zielsystem, Fetching, Datenhaltung, Vektorindex und semantische Suche steht in [docs/data_processing_concept.md](/mnt/c/users/diane/git/ratsi_melle/docs/data_processing_concept.md:1).

## Weitere Dokumentation

- Projekt- und Arbeitsregeln: [AGENTS.md](/mnt/c/users/diane/git/ratsi_melle/AGENTS.md:1)
- Repository-Regeln: [docs/repository_guidelines.md](/mnt/c/users/diane/git/ratsi_melle/docs/repository_guidelines.md:1)
- Django-Konzept: [docs/django_ui_concept.md](/mnt/c/users/diane/git/ratsi_melle/docs/django_ui_concept.md:1)
- Offene Aufgaben und Ausbaupfade: [docs/project_tasks.md](/mnt/c/users/diane/git/ratsi_melle/docs/project_tasks.md:1)
