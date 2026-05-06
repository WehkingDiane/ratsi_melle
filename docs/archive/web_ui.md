# Deprecated Web-UI (Streamlit)

Diese Datei beschreibt die browserbasierte Oberfläche unter `src/interfaces/web/streamlit_app.py`.

> Status: Deprecated. Die aktive und primaere Weboberflaeche liegt unter `web/` und wird mit `python scripts/run_web.py` gestartet. Diese Streamlit-Beschreibung bleibt nur fuer Legacy-Kompatibilitaet archiviert.

## Ziel

- Lokale Datenbanken im Browser durchsuchen und filtern
- semantische Suche über den Qdrant-Vektorindex ausführen
- Analyse-Workflows und Exporte ohne Desktop-GUI bedienen

## Starten

Legacy-Start aus dem Repository-Root:

```bash
python -m streamlit run src/interfaces/web/streamlit_app.py
```

Optional mit abweichendem Port:

```bash
python -m streamlit run src/interfaces/web/streamlit_app.py --server.port 8502
```

Danach ist die Oberfläche typischerweise unter `http://localhost:8501` erreichbar.

## Voraussetzungen

- Python 3.11+
- Legacy-UI-Abhaengigkeiten installiert:
  - `pip install -r requirements-legacy-ui.txt`
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

- Architektur und Suchdetails: `docs/data_processing_concept.md`
- Gemeinsame Analyse-/Filterlogik: `src/interfaces/shared/analysis_store.py`
- Desktop-GUI (Legacy): `docs/archive/gui.md`
- Desktop-GUI-Nutzung (Legacy): `docs/archive/gui_usage.md`
