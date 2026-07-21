# Ratsinformations-Analysetool Melle

Dieses Projekt sammelt öffentliche Sitzungs- und Dokumentdaten aus dem Ratsinformationssystem der Stadt Melle, bereitet sie strukturiert auf und stellt sie für Recherche, KI-Analysen und semantische Suche bereit.

## Zweck

- Sitzungen, Tagesordnungspunkte und Dokumente aus SessionNet erfassen
- lokale und online-basierte Indizes für Recherche aufbauen
- Dokumente für KI-gestützte Sitzungsbriefings und TOP-Analysen vorbereiten
- semantische Suche über einen lokalen Qdrant-Index bereitstellen

## Oberflächen

- **Django-Weboberflaeche** unter `web/` ist der aktive und primaere UI-Pfad fuer Recherche, Analyse, Prompt-Vorlagen und Datenpflege.

## Voraussetzungen

- Python 3.11+
- `pip`
- `git`

## Installation

```bash
pip install -r requirements.txt
```

`torch` wird weiterhin separat installiert, passend zur Zielumgebung.
Unter WSL sollte die virtuelle Umgebung `.venv-wsl` verwendet werden; wenn `python`
in der Shell fehlt, funktionieren die Projektbefehle nach Aktivierung oder direkt
mit `.venv-wsl/bin/python`.

## Wichtige Befehle

```bash
python scripts/fetch_sessions.py 2024 --months 5 6
python scripts/fetch_session_from_index.py --list --from-date 2026-04-01 --to-date 2026-04-30
python scripts/fetch_session_from_index.py --session-id 7128
python scripts/build_local_index.py
python scripts/build_online_index_db.py 2024 --months 5 6
python scripts/build_vector_index.py
python scripts/fetch_landkreis_publications.py --source all
python scripts/build_landkreis_publications_db.py
python scripts/build_landkreis_vector_index.py
python scripts/search_landkreis_publications.py "Melle Genehmigung"
python scripts/run_web.py
python -m pytest
```

Repository-Hooks werden lokal mit folgendem Befehl aktiviert:

```bash
git config core.hooksPath .githooks
```

`fetch_session_from_index.py` nutzt `data/db/online_session_index.sqlite` als Auswahlquelle. Damit kann eine einzelne Sitzung anhand ihrer `session_id` nach `data/raw/` geladen werden, ohne die Monatsübersicht erneut komplett abzuarbeiten.

Die Django-Weboberfläche startet lokal mit:

```bash
python scripts/run_web.py
```

Sie ist danach standardmäßig unter `http://127.0.0.1:8000/` erreichbar. Details stehen in [docs/web_ui.md](/mnt/c/users/diane/git/ratsi_melle/docs/web_ui.md:1).

## Daten und Suche

- Lokaler SQLite-Index: `data/db/local_index.sqlite`
- Online-Index: `data/db/online_session_index.sqlite`
- Landkreis-Veröffentlichungen: `data/db/landkreis_publications.sqlite`
- Lokaler Vektorindex: `data/db/qdrant/` mit getrennten Collections fuer Ratsinfo (`ratsi_documents`) und Landkreis (`landkreis_publications`)
- Django-Datenpflege unter `/daten/`: SessionNet- und Landkreis-Fetch-, SQLite-Build- und Vektorindex-Jobs starten; die Vektorseite zeigt Status fuer Ratsinfo und Landkreis
- Django-Suche unter `/suche/`: semantische Dokumentensuche ueber den lokalen Qdrant-Vektorindex; Standard ist Ratsinfo. Fuer Landkreis-Treffer zuerst `python scripts/build_landkreis_vector_index.py` oder `/daten/vektor/` nutzen; fuer Ratsinfo `python scripts/build_vector_index.py` oder `/daten/vektor/`
- Analyse-Workflow und v2-Ausgaben: [docs/analysis_outputs.md](/mnt/c/users/diane/git/ratsi_melle/docs/analysis_outputs.md:1)
- Analyse-Start unter `/analyse/starten/`: Sitzung vorbereiten, TOPs kritisch analysieren oder Prompt/Grundlage für manuelle ChatGPT-Nutzung erzeugen
- Private Prompt-Vorlagen: `data/private/prompt_templates.json`
- Private Prompt-Artefakte und gerenderte Snapshots: `data/private/analysis_prompts/` und `data/private/prompt_snapshots/`
- Optionaler Hugging-Face-Token: sichere Ablage ueber `/einstellungen/` im OS-Schluesselring; Fallback ueber `HF_TOKEN` oder `HUGGING_FACE_HUB_TOKEN`

Landkreis-Veröffentlichungen aus Bekanntmachungen und Amtsblättern werden bewusst getrennt vom SessionNet-Index verarbeitet. Rohdateien liegen standardmaessig unter `data/raw/landkreis/`; alternativ kann ein externer Speicherort per `RATSI_LANDKREIS_DATA_DIR` oder `--data-dir` gesetzt werden. Die interne Ordnerstruktur bleibt dabei gleich, und die SQLite-DB speichert relative Pfade innerhalb dieser Landkreis-Datenwurzel.

### Landkreis-Veröffentlichungen

Der Landkreis-Import ist als eigenstaendige Datenquelle umgesetzt und veraendert weder `data/db/local_index.sqlite` noch die SessionNet-Rohdaten. Er verarbeitet derzeit:

- Bekanntmachungen: `https://www.landkreis-osnabrueck.de/verwaltung/veroeffentlichungen/bekanntmachungen`
- Amtsblaetter: `https://www.landkreis-osnabrueck.de/verwaltung/veroeffentlichungen/amtsblaetter`

Typische Nutzung:

```bash
python scripts/fetch_landkreis_publications.py --source all
python scripts/build_landkreis_publications_db.py
python scripts/build_landkreis_vector_index.py
python scripts/fetch_landkreis_publications.py --source bekanntmachungen --query Melle
python scripts/search_landkreis_publications.py "Melle Genehmigung"
```

`fetch_landkreis_publications.py` speichert nur Rohdaten aus dem Online-Angebot. Bereits vorhandene Landkreis-Veröffentlichungen mit lokalem `manifest.json` werden bei spaeteren Laeufen uebersprungen. Fuer neue Bekanntmachungen werden Detailseiten und Dokument-Metadaten erfasst, aber keine PDF-Dateien heruntergeladen. Neue Amtsblaetter werden vollstaendig geladen. Die SQLite-Datenbank wird danach mit `build_landkreis_publications_db.py` aus den gespeicherten Manifests und lokalen Dateien aufgebaut. `build_landkreis_vector_index.py` indexiert lokal vorhandene Landkreis-Dokumente in die getrennte Qdrant-Collection `landkreis_publications`, loest lokale Pfade gegen dieselbe Landkreis-Datenwurzel (`RATSI_LANDKREIS_DATA_DIR` oder `--data-dir`) auf und begrenzt den Embedding-Text standardmaessig auf 6000 Zeichen pro Dokument; bei knappem XPU/GPU-Speicher kann `--max-text-chars` weiter reduziert werden.

Fuer grosse Downloads kann die Rohdatenablage ausserhalb des Projekts liegen:

```bash
RATSI_LANDKREIS_DATA_DIR=/mnt/d/landkreis_osnabrueck \
python scripts/fetch_landkreis_publications.py --source all
RATSI_LANDKREIS_DATA_DIR=/mnt/d/landkreis_osnabrueck \
python scripts/build_landkreis_publications_db.py
```

Alternativ kann der Speicherort pro Lauf mit `--data-dir` gesetzt werden; Fetch, DB-Build und Vektor-Build sollten dabei dieselbe Datenwurzel verwenden. Die Datenbank bleibt standardmaessig unter `data/db/landkreis_publications.sqlite`; mit `RATSI_LANDKREIS_DB` oder `--db` kann auch dieser Pfad ueberschrieben werden.

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
- Architekturdiagramm: [docs/architecture_overview.puml](/mnt/c/users/diane/git/ratsi_melle/docs/architecture_overview.puml:1)
- Aktueller Stand der Django-Weboberfläche: [docs/web_ui.md](/mnt/c/users/diane/git/ratsi_melle/docs/web_ui.md:1)
- Django-Zielkonzept: [docs/django_ui_concept.md](/mnt/c/users/diane/git/ratsi_melle/docs/django_ui_concept.md:1)
- Offene Aufgaben und Ausbaupfade: [docs/project_tasks.md](/mnt/c/users/diane/git/ratsi_melle/docs/project_tasks.md:1)
