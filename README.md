# Ratsi Melle

Die Anwendung sammelt **öffentliche** Sitzungs- und Dokumentdaten aus dem Bürgerinformationssystem der Stadt Melle (`/bi/`) und Veröffentlichungen des Landkreises Osnabrück. Sie erstellt lokale SQLite-Indizes, bietet semantische Suche und eine Django-Oberfläche für Datenpflege und Analyse. Der geschützte Ratsbereich (`/ri/`) ist derzeit geplant und noch nicht implementiert.

Der [Ist-Stand](docs/ist_stand.md) beschreibt Quellen, Datenhaltung, Suche und Oberfläche. Der [RI-Plan](docs/ri_ratsbereich_plan.md) ist das einzige aktuelle Ausbauvorhaben.

## Voraussetzungen und Start

Python 3.14, pip und Git werden empfohlen. Für die Oberfläche wird Tkinter nicht benötigt. Unter WSL kann `.venv-wsl` verwendet werden; falls `python` fehlt, `python3` beziehungsweise `.venv-wsl/bin/python` nutzen.

```bash
pip install -r requirements.txt
python scripts/run_web.py
```

Die lokale Django-Oberfläche ist danach unter `http://127.0.0.1:8000/` erreichbar. Sie ist aktuell für lokale Entwicklung konfiguriert und besitzt keine Benutzeranmeldung.

## Daten aufbauen

```bash
# Öffentliche SessionNet-Daten und Indizes
python scripts/fetch_sessions.py 2024 --months 5 6
python scripts/build_online_index_db.py 2024 --months 5 6
python scripts/fetch_session_from_index.py --list --from-date 2026-04-01 --to-date 2026-04-30
python scripts/fetch_session_from_index.py --session-id 7128
python scripts/build_local_index.py

# Lokale Suchmodelle und Ratsinfo-Vektorindex
python scripts/prepare_embedding_models.py --download
python scripts/build_vector_index.py

# Landkreis-Veröffentlichungen
python scripts/fetch_landkreis_publications.py --source all
python scripts/build_landkreis_publications_db.py
python scripts/build_landkreis_vector_index.py
```

Die Befehle sind Beispiele. Fetch-Jahr, Monate und Sitzungs-ID müssen zum gewünschten Datenbestand passen. Die Weboberfläche bietet die entsprechenden Datenjobs unter `/daten/`. Die Suche liegt unter `/suche/`; die SQLite-Suche für Landkreis-Daten ist außerdem mit `python scripts/search_landkreis_publications.py "Melle Genehmigung"` nutzbar.

Standardmäßig verwendet die Suche Qdrant unter `http://127.0.0.1:6333`. Ein anderer Server kann mit `RATSI_QDRANT_URL` gewählt werden. Für lokalen Speicher ohne Server `RATSI_QDRANT_MODE=local` setzen und `RATSI_QDRANT_URL` frei lassen. Vor dem Vektorbuild müssen die lokalen Modelle vorbereitet sein.

## Lokale Daten

Öffentliche SessionNet-Rohdaten liegen unter `data/raw/YYYY/MM/`, Landkreis-Rohdaten unter `data/raw/landkreis/`. SQLite-Dateien liegen unter `data/db/`, private Prompt-Dateien unter `data/private/`, Analyseausgaben unter `data/analysis_outputs/`. Diese Laufzeitdaten und Geheimnisse werden nicht versioniert. Die Struktur der Analyseartefakte steht in [Analyseausgaben](docs/analysis_outputs.md).

## Tests gezielt ausfuehren

Die Marker `integration` und `live` sind in `pyproject.toml` registriert. `integration` prüft das Zusammenspiel mehrerer Komponenten mit lokalen oder simulierten Abhängigkeiten. `live` benötigt echte Dienste, Modelle oder nicht versionierte Quelldaten und ist im normalen Lauf ausgeschlossen.

```bash
python -m pytest -m "not integration and not live"
python -m pytest -m "integration and not live"
python -m pytest
```

## Dokumentation

- [Ist-Stand](docs/ist_stand.md): vorhandene Datenflüsse, Speicherorte, Suche und Oberfläche
- [RI-Plan](docs/ri_ratsbereich_plan.md): einziges aktuelles Ausbauvorhaben
- [Aktuelle Aufgaben](docs/project_tasks.md): Arbeitspakete des RI-Vorhabens
- [Repository-Regeln](docs/repository_guidelines.md) und [Agentenregeln](AGENTS.md)
- [UI-Regeln](docs/ui_guidelines.md) und [Analyseausgaben](docs/analysis_outputs.md)
