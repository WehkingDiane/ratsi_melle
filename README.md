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

Die lokale Extraktionspipeline kann Scan-PDFs optional per OCR verarbeiten. Dafuer
muessen `pdftoppm` (Poppler) und `tesseract` mit den Sprachdaten `deu` und `eng`
als Systemwerkzeuge verfuegbar sein. Ohne diese Werkzeuge bleiben Scan-PDFs mit
dem Status `ocr_needed` gekennzeichnet.

## Wichtige Befehle

```bash
python scripts/fetch_sessions.py 2024 --months 5 6
python scripts/fetch_session_from_index.py --list --from-date 2026-04-01 --to-date 2026-04-30
python scripts/fetch_session_from_index.py --session-id 7128
python scripts/build_local_index.py
python scripts/build_online_index_db.py 2024 --months 5 6
python scripts/build_vector_index.py
python scripts/evaluate_search.py --validate-only
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

Der lokale Index-Build behandelt `session_detail.html` als kanonische Quelle und übernimmt daraus abweichende TOP- und Dokumentmetadaten direkt in den SQLite-Index. `agenda_summary.json`, `manifest.json` und andere Rohdaten bleiben dabei unverändert; bereits vorhandene Dateien werden im Index wieder ihren Dokumentlinks zugeordnet. Berücksichtigt werden nur SessionNet-Sitzungsordner unter `data/raw/YYYY/MM/`; Landkreis-Rohdaten bleiben getrennt. Auch der Online-Index-Build verändert keine Dateien unter `data/raw/`.

Die Django-Weboberfläche startet lokal mit:

```bash
python scripts/run_web.py
```

Sie ist danach standardmäßig unter `http://127.0.0.1:8000/` erreichbar. Details stehen in [docs/web_ui.md](docs/web_ui.md).

## Daten und Suche

- Lokaler SQLite-Index: `data/db/local_index.sqlite`
- Online-Index: `data/db/online_session_index.sqlite`
- Landkreis-Veröffentlichungen: `data/db/landkreis_publications.sqlite`
- Lokaler Vektorindex: `data/db/qdrant/`; Ratsinfo verwendet den neuen Abschnittsindex `ratsi_passages` mit Harrier und BM25. Der bisherige Index `ratsi_documents` bleibt bis zum vollstaendigen Erstaufbau aktiv. Landkreis nutzt weiterhin `landkreis_publications`.
- Django-Datenpflege unter `/daten/`: SessionNet- und Landkreis-Fetch-, SQLite-Build- und Vektorindex-Jobs starten; die Vektorseite zeigt Status fuer Ratsinfo und Landkreis
- Django-Suche unter `/suche/`: semantische Dokumentensuche ueber den lokalen Qdrant-Vektorindex; Standard ist Ratsinfo. Fuer Landkreis-Treffer zuerst `python scripts/build_landkreis_vector_index.py` oder `/daten/vektor/` nutzen; fuer Ratsinfo `python scripts/build_vector_index.py` oder `/daten/vektor/`
- Analyse-Workflow und v2-Ausgaben: [docs/analysis_outputs.md](docs/analysis_outputs.md)
- Analyse-Start unter `/analyse/starten/`: Sitzung vorbereiten, TOPs kritisch analysieren oder Prompt/Grundlage für manuelle ChatGPT-Nutzung erzeugen; vorbereitete Jobs lassen sich anschließend auf derselben Jobseite an einen API-Provider absenden
- Antwort-Leseansicht unter `/analyse/antworten/`: fertig ausgeführte Analysen ohne technische Job- und Promptdetails lesen
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

`fetch_landkreis_publications.py` speichert nur Rohdaten aus dem Online-Angebot. Bereits vorhandene Landkreis-Veröffentlichungen mit lokalem `manifest.json` werden bei spaeteren Laeufen uebersprungen. Fuer neue Bekanntmachungen werden Detailseiten und Dokument-Metadaten erfasst, aber keine PDF-Dateien heruntergeladen. Neue Amtsblaetter werden vollstaendig geladen. Die SQLite-Datenbank wird danach mit `build_landkreis_publications_db.py` aus den gespeicherten Manifests und lokalen Dateien aufgebaut. `build_landkreis_vector_index.py` indexiert lokal vorhandene Landkreis-Dokumente in die getrennte Qdrant-Collection `landkreis_publications`, ergaenzt fehlende Treffertexte in bereits indexierten Punkten ohne erneutes Embedding, loest lokale Pfade gegen dieselbe Landkreis-Datenwurzel (`RATSI_LANDKREIS_DATA_DIR` oder `--data-dir`) auf und begrenzt den Embedding-Text standardmaessig auf 6000 Zeichen pro Dokument; bei knappem XPU/GPU-Speicher kann `--max-text-chars` weiter reduziert werden.

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
- SessionNet-Dokumentdownloads warnen bei mehr als 25 MiB und werden bei mehr als 100 MiB abgebrochen. Liefert der Server keine verwertbare `Content-Length`, erfolgt die Pruefung waehrend des Streamings; das betroffene Dokument wird nicht gespeichert, der restliche Sitzungslauf wird fortgesetzt.
- Downloads von Landkreis-Amtsblaettern sowie Dateien in der lokalen Extraktionspipeline sind auf jeweils 25 MiB begrenzt. Das Extraktionslimit ist vom SessionNet-Downloadlimit unabhaengig.
- Provider-Keys werden aus dem OS-Schluesselring oder aus `OPENAI_API_KEY` beziehungsweise `ANTHROPIC_API_KEY` gelesen. Der optionale Hugging-Face-Token kann unter `/einstellungen/` im OS-Schluesselring verwaltet werden; `HF_TOKEN` und `HUGGING_FACE_HUB_TOKEN` bleiben als Fallback moeglich. Secrets gehoeren nicht in Repository-Dateien.

Die gemeinsame Grundlagen-Doku für Zielsystem, Fetching, Datenhaltung, Vektorindex und semantische Suche steht in [docs/data_processing_concept.md](docs/data_processing_concept.md).

## Weitere Dokumentation

- Abschnittsindex und Recherche-Benchmark: [docs/search_quality.md](docs/search_quality.md)
- Projekt- und Arbeitsregeln: [AGENTS.md](AGENTS.md)
- Repository-Regeln: [docs/repository_guidelines.md](docs/repository_guidelines.md)
- Architekturdiagramm: [docs/architecture_overview.puml](docs/architecture_overview.puml)
- Aktueller Stand der Django-Weboberfläche: [docs/web_ui.md](docs/web_ui.md)
- Django-Zielkonzept: [docs/django_ui_concept.md](docs/django_ui_concept.md)
- Offene Aufgaben und Ausbaupfade: [docs/project_tasks.md](docs/project_tasks.md)
