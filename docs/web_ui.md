# Web-UI (Streamlit)

Diese Datei beschreibt die browserbasierte Oberfläche unter `src/interfaces/web/streamlit_app.py`.

## Ziel

- Lokale Datenbanken im Browser durchsuchen und filtern
- semantische Suche über den Qdrant-Vektorindex ausführen
- Analyse-Workflows und Exporte ohne Desktop-GUI bedienen

## Starten

Empfohlen aus dem Repository-Root:

```bash
python scripts/run_web.py
```

Optional mit abweichendem Port:

```bash
python scripts/run_web.py --server.port 8502
```

Danach ist die Oberfläche typischerweise unter `http://localhost:8501` erreichbar.

## Voraussetzungen

- Python 3.11+
- Projektabhängigkeiten installiert:
  - `pip install -r requirements.txt`
- Für die semantische Suche zusätzlich:
  - `pip install torch --index-url https://download.pytorch.org/whl/cpu`
  - alternativ bei Intel-XPU:
    - `pip install torch torchaudio torchvision --index-url https://download.pytorch.org/whl/xpu`
- Ein lokaler SQLite-Index unter `data/db/local_index.sqlite`
- Für semantische Suche zusätzlich ein aufgebauter Vektorindex unter `data/db/qdrant/`

## Wichtige Bereiche

### Sidebar

- Auswahl der aktiven SQLite-Datenbank
- Datumsfilter, Gremienfilter, Statusfilter und Freitextsuche
- Sitzungsnavigation

### Analyse

- Auswahl einzelner Sitzungen und TOPs
- lokale Analysegrundlage für nachgelagerte KI-Workflows
- Provider-/Modellauswahl

### Semantische Suche

- nutzt den lokalen Qdrant-Index
- arbeitet mit Hybrid-Retrieval aus Harrier-Dense-Embeddings und BM25-Sparse-Vektoren
- die Treffer sind nach **RRF-Rangfusion** sortiert; der angezeigte Score ist kein Prozentwert

### Daten- und Exportfunktionen

- Skriptnahe Datenaufgaben direkt aus der Oberfläche
- Export vorhandener Analyse-Artefakte

## Hinweise

- Die semantische Suche ist aktuell nur für den **lokalen Index** vorgesehen.
- Wenn `data/db/qdrant/` fehlt, muss der Vektorindex zuerst aufgebaut werden:

```bash
python scripts/build_vector_index.py
```

- Nach Änderungen am Stable-ID-Schema oder an der Indexierungslogik ist ein vollständiger Neuaufbau des Vektorindex nötig:

```bash
rm -rf data/db/qdrant
python scripts/build_vector_index.py
```

## Zugehörige Dateien

- Architektur und Suchdetails: `docs/vector_search.md`
- Desktop-GUI: `docs/gui.md`
- Desktop-GUI-Nutzung: `docs/gui_usage.md`
