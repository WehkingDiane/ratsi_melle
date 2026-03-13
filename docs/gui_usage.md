# GUI-Anleitung

Diese Anleitung beschreibt die Nutzung der Desktop-GUI unter `src/interfaces/gui/`.

## Voraussetzungen

- Python 3.11+ ist installiert.
- Die Projektabhaengigkeiten sind installiert:
  - `pip install -r requirements.txt`
- Unter WSL ist fuer Tkinter ggf. `python3-tk` erforderlich.
- Fuer datenbezogene Funktionen sollte eine lokale SQLite-DB vorhanden sein, typischerweise `data/db/local_index.sqlite`.

## GUI starten

Start aus dem Repository-Root:

```bash
python -m src.interfaces.gui.gui_launcher
```

## Aufbau der GUI

Die GUI ist in mehrere Bereiche gegliedert:

- `Data Tools`: Skriptnahe Funktionen wie Download und Index-Build
- `Analyse-Batch Export`: Developer-Werkzeug fuer reproduzierbare JSON-Exports inkl. Vorschau
- `Analysis`: Auswahl von Sitzungen und Erzeugung einer lokalen Analysegrundlage
- weitere technische Bereiche wie Service- und Einstellungsansichten

Leere Eingabefelder enthalten Beispiel-Platzhalter, damit das erwartete Format direkt sichtbar ist, etwa fuer Monate (`5 6 7`) oder Datumswerte (`2026-01-01`).
Auf der Seite `Analyse-Batch Export` werden zusaetzlich Profile, Zeitraum-Presets und Dokumentprofile angeboten, damit typische Exporte ohne manuelles Ausfuellen startklar sind.

## Typischer Ablauf

### 1. Rohdaten laden

Falls noch keine Daten vorhanden sind:

```bash
python scripts/fetch_sessions.py 2024 --months 5 6
```

Alternativ ueber die GUI in `Data Tools` die Download-Funktion ausfuehren.

### 2. Lokalen Index erzeugen

Falls noch keine lokale DB existiert:

```bash
python scripts/build_local_index.py
```

Standardziel ist `data/db/local_index.sqlite`.

### 3. Analyse-Batch exportieren

In `Analyse-Batch Export`:

- `Exportprofil` waehlen, z. B. `Standardbatch (empfohlen)` oder `Rat (nur Quellenpaket)`
- optional `Zeitraum`, `Gremium aus DB` und `Dokumentprofil` nutzen
- falls noetig Feinsteuerung ueber:
  - `DB-Pfad`
  - `Output-Datei`, standardmaessig `data/analysis_requests/analysis_batch.json`
  - `Gremien (kommagetrennt)`
  - `Dokumenttypen (kommagetrennt)`
  - `Von` / `Bis`
  - `Nur lokale Dateien`
- `Analyse-Batch als JSON erzeugen` klicken

Nach erfolgreichem Lauf zeigt die rechte Seite:

- Exportdetails
- Anzahl der exportierten Dokumente
- verwendete Filter
- eine Vorschau des erzeugten JSON-Inhalts

Die Exportdatei liegt damit getrennt von den SQLite-Datenbanken und kann spaeter direkt als KI-/Analyse-Eingang weiterverwendet werden.

Relevante Exportfelder:

- `session_id`
- `top_number`
- `top_title`
- `document_type`
- `url`
- `local_path`
- `resolved_local_path`
- `sha1`

## Analyse-Ansicht verwenden

In `Analysis`:

### 1. Sitzungen filtern

- `Zeitraum` als Preset waehlen oder `Von` und `Bis` manuell setzen
- `Gremium` auswaehlen
- `Status` waehlen (`alle`, `vergangen`, `heute`, `kommend`)
- optional Textsuche verwenden
- `Filtern` klicken

### 2. Sitzung auswaehlen

- links eine Sitzung anklicken
- danach werden die TOPs der Sitzung geladen

### 3. Scope festlegen

- `Ganze Sitzung` analysiert alle Dokumente der Sitzung
- `Ausgewaehlte TOPs` analysiert nur die markierten TOPs

### 4. Prompt anpassen

Im Prompt-Feld kann die Auswertung gesteuert werden, z. B.:

```text
Erstelle spaeter ueber einen KI-Provider eine neutrale TOP-Analyse. Nenne Kernthemen, Entscheidungen, Unsicherheiten und Quellenbezug.
```

### 5. Analyse starten

Mit `Analyse starten` wird eine lokale Analysegrundlage als Markdown erzeugt.

Diese Ausgabe enthaelt bewusst keine lokale PDF- oder Text-Inhaltsanalyse mehr. Sie dient nur als vorbereitender Kontext fuer eine spaetere KI-Analyse und listet insbesondere:

- Scope und TOP-Auswahl
- Dokumente im Scope
- Quellenpfade und Quell-URLs

### 6. Ergebnis exportieren

Mit `Markdown exportieren` wird das aktuelle Analyseergebnis nach
`data/analysis_outputs/summaries/analysis_latest.md` geschrieben.

## Typische Fehlerbilder

### Keine Sitzungen sichtbar

Pruefen:

- existiert die DB unter dem eingestellten Pfad
- wurde `python scripts/build_local_index.py` bereits ausgefuehrt
- sind die gesetzten Filter zu restriktiv

### Im Export fehlen lokale Quelldateien

Pruefen:

- das Dokument hat einen lokalen Pfad
- `Nur lokale Dateien` ist passend gesetzt

### GUI startet unter WSL nicht

Pruefen:

- Tkinter-Unterstuetzung installiert (`python3-tk`)
- grafische Ausgabe in der WSL-Umgebung verfuegbar

## Zugehoerige Dateien

- GUI-Architektur: `docs/gui.md`
- Analyse-Kontext: `src/analysis/analysis_context.py`
- Batch-Export: `scripts/export_analysis_batch.py`
