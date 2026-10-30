# Ratsi Melle

Die Anwendung sammelt **öffentliche** Sitzungs- und Dokumentdaten aus dem Bürgerinformationssystem der Stadt Melle (`/bi/`) und Veröffentlichungen des Landkreises Osnabrück. Sie erstellt lokale SQLite-Indizes, bietet semantische Suche und eine Django-Oberfläche für Datenpflege und Analyse. Der geschützte Ratsbereich (`/ri/`) ist derzeit geplant und noch nicht implementiert.

Der [Ist-Stand](docs/ist_stand.md) beschreibt Quellen, Datenhaltung, Suche und Oberfläche. Der [RI-Plan](docs/plans/ri_ratsbereich_plan.md) ist das einzige aktuelle Ausbauvorhaben.

## Voraussetzungen und Start

Python 3.14, pip und Git werden empfohlen. Für die Oberfläche wird Tkinter nicht benötigt. Unter WSL kann `.venv-wsl` verwendet werden; falls `python` fehlt, `python3` beziehungsweise `.venv-wsl/bin/python` nutzen.

```bash
pip install -r requirements.txt
python scripts/run_web.py
```

Die lokale Django-Oberfläche ist danach unter `http://127.0.0.1:8000/` erreichbar. Sie ist aktuell für lokale Entwicklung konfiguriert und besitzt keine Benutzeranmeldung.

## Daten aufbauen

Die SessionNet-Skripte für den öffentlichen Bürgerinformationsbereich tragen `bi` im Namen. Eigene RI-Skripte sind noch nicht vorhanden. Seit Version 0.5.63 gelten folgende Umbenennungen; eigene Automatisierungen müssen die neuen Namen verwenden:

| Bisher | Neu |
| --- | --- |
| `fetch_sessions.py` | `fetch_bi_sessions.py` |
| `fetch_session_from_index.py` | `fetch_bi_session_from_index.py` |
| `build_online_index_db.py` | `build_bi_online_index_db.py` |
| `build_local_index.py` | `build_bi_local_index.py` |
| `build_vector_index.py` | `build_bi_vector_index.py` |
| `check_vector_index.py` | `check_bi_vector_index.py` |
| `update_vector_index.py` | `update_bi_vector_index.py` |
| `evaluate_search.py` | `evaluate_bi_search.py` |

Landkreis-Skripte behalten ihre eindeutigen Namen. Gemeinsame Werkzeuge wie `prepare_embedding_models.py`, `migrate_legacy_index.py` und `run_web.py` bleiben neutral benannt. Die Weboberfläche verwendet die neuen Skriptpfade; bestehende Job-Aktionskennungen bleiben erhalten.

```bash
# Öffentliche SessionNet-Daten und Indizes
python scripts/fetch_bi_sessions.py 2024 --months 5 6
python scripts/build_bi_online_index_db.py 2024 --months 5 6
python scripts/fetch_bi_session_from_index.py --list --from-date 2026-04-01 --to-date 2026-04-30
python scripts/fetch_bi_session_from_index.py --session-id 7128
python scripts/build_bi_local_index.py

# Lokale Suchmodelle und Ratsinfo-Vektorindex
python scripts/prepare_embedding_models.py --download
python scripts/build_bi_vector_index.py

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
- [RI-Plan](docs/plans/ri_ratsbereich_plan.md): einziges aktuelles Ausbauvorhaben
- [Aktuelle Aufgaben](docs/plans/project_tasks.md): Arbeitspakete des RI-Vorhabens
- [Repository-Regeln](docs/repository_guidelines.md) und [Agentenregeln](AGENTS.md)
- [UI-Regeln](docs/ui_guidelines.md) und [Analyseausgaben](docs/analysis_outputs.md)

## Navigation der Weboberfläche

Seit 0.5.64 gliedert sich die Oberfläche in Übersicht, Bürgerinformation, Ratsbereich,
Landkreis, Erweiterungen und Einstellungen. Bürgerinformation und Landkreis haben
getrennte Einstiege für Suche und Datenpflege. Bestehende URLs bleiben erreichbar.
Analyse liegt unter Erweiterungen; Wartung und Konfiguration unter Einstellungen.
Der Ratsbereich zeigt vorerst informative Platzhalter und verarbeitet keine
Zugangsdaten oder internen Unterlagen. Hauptbereiche stehen wie im Dashboard
untereinander.
