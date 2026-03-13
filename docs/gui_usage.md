# GUI-Anleitung

Diese Anleitung beschreibt die Nutzung der Desktop-GUI unter `src/interfaces/gui/`.
Der aktuelle Stand ist eine Developer-GUI fuer interne Arbeitsablaeufe. Eine finale Endnutzer-GUI ist noch nicht begonnen beziehungsweise nicht fertig.

> Hinweis: Die langfristige Code- bzw. Technologiesprache des Gesamtprojekts ist weiterhin offen und noch nicht festgelegt.

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
- `Analysis`: Auswahl von Sitzungen und Erzeugung eines Analyse-Markdowns
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

- `Exportprofil` waehlen, z. B. `Standardbatch (empfohlen)` oder `Rat mit Text-Extraktion`
- optional `Zeitraum`, `Gremium aus DB` und `Dokumentprofil` nutzen
- falls noetig Feinsteuerung ueber:
  - `DB-Pfad`
  - `Output-Datei`, standardmaessig `data/analysis_requests/analysis_batch.json`
  - `Gremien (kommagetrennt)`
  - `Dokumenttypen (kommagetrennt)`
  - `Von` / `Bis`
  - `Nur lokale Dateien`
  - `Text-Extraktion einbeziehen`
- `Analyse-Batch als JSON erzeugen` klicken

Nach erfolgreichem Lauf zeigt die rechte Seite:

- Exportdetails
- Anzahl der exportierten Dokumente
- verwendete Filter
- eine Vorschau des erzeugten JSON-Inhalts

Die Exportdatei liegt damit getrennt von den SQLite-Datenbanken und kann spaeter direkt als KI-/Analyse-Eingang weiterverwendet werden.

Wichtige Wirkung von `Include text extraction`:

- lokale Dokumente werden gelesen
- Text wird extrahiert
- fuer `vorlage`, `beschlussvorlage` und `protokoll` werden strukturierte Felder erzeugt

Relevante Exportfelder:

- `extraction_status`
- `parsing_quality`
- `content_parser_status`
- `content_parser_quality`
- `structured_fields`
- `matched_sections`

Beispiele fuer `structured_fields`:

- `beschlusstext`
- `begruendung`
- `finanzbezug`
- `zustaendigkeit`
- `entscheidung`

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
Erstelle eine neutrale Zusammenfassung. Nenne Kernthemen, Entscheidungen, Kosten und offene Punkte.
```

Zusaetzlich kann ueber `Analysemodus` gesteuert werden, welche Ausgabe erzeugt wird:

- `summary`
- `decision_brief`
- `financial_impact`
- `journalistic_brief`
- `citizen_explainer`
- `topic_classifier`

### 5. Analyse starten

Mit `Analyse starten` wird ein lokaler Markdown-Text erzeugt.

Die Analyse nutzt jetzt nicht nur Metadaten, sondern auch Dokumentkontext aus lokalen Dateien:

- Dokumenttyp
- Extraktionsstatus
- Parser-Qualitaet
- erkannte PDF-Abschnitte und Seitenkontext
- strukturierte Felder aus Beschlussvorlagen und Protokollen
- Unsicherheitsmarker, Plausibilitaetsflags, Bias-Metriken und Audit-Metadaten
  (Modus, Prompt-Version, Dokument-Hashes)

Der erzeugte Markdown-Text enthaelt einen Abschnitt `Dokumentkontext`, in dem erkannte Inhalte kompakt aufgefuehrt werden.
Im Modus `journalistic_brief` wird zusaetzlich eine `Sitzungsanalyse` mit Konfliktlinien, offenen Fragen und priorisierten Folgeaufgaben ausgegeben.
Bei TOP-Scope wird zusaetzlich eine `TOP-Analyse` mit Dokumentmix, Themenhinweisen und Inkonsistenz-Markierungen erzeugt.
Ergebnisse werden zunaechst als Entwurf (`draft_status = draft`) gespeichert.

### 6. Review freigeben

Im unteren Bereich der Analyseansicht wird die Job-Historie der aktuell gewaehlten Sitzung angezeigt.
Ein Klick auf einen Job laedt Ergebnis und Review-Status.

Fuer die Freigabe:

- `Reviewer` ausfuellen
- Review-Status waehlen (`approved`, `changes_requested`, `rejected`)
- optional Notizen hinterlegen
- `Review speichern`

Die CLI bleibt fuer denselben Schritt weiterhin verfuegbar:
`python scripts/review_analysis_job.py <job_id> --reviewer <kennung> --status approved --notes "..."`.

### 7. Ergebnis exportieren

Mit `Markdown exportieren` wird das aktuelle Analyseergebnis nach
`data/analysis_outputs/summaries/analysis_latest.md` geschrieben.

## Typische Fehlerbilder

### Keine Sitzungen sichtbar

Pruefen:

- existiert die DB unter dem eingestellten Pfad
- wurde `python scripts/build_local_index.py` bereits ausgefuehrt
- sind die gesetzten Filter zu restriktiv

### Keine strukturierten Dokumentfelder im Export

Pruefen:

- `Include text extraction` ist aktiviert
- das Dokument hat einen lokalen Pfad
- der Dokumenttyp ist einer der priorisierten Typen:
  - `vorlage`
  - `beschlussvorlage`
  - `protokoll`

### GUI startet unter WSL nicht

Pruefen:

- Tkinter-Unterstuetzung installiert (`python3-tk`)
- grafische Ausgabe in der WSL-Umgebung verfuegbar

## Zugehoerige Dateien

- GUI-Architektur: `docs/gui.md`
- Analyse-Kontext: `src/analysis/analysis_context.py`
- Inhaltsparser: `src/parsing/document_content.py`
- Batch-Export: `scripts/export_analysis_batch.py`
