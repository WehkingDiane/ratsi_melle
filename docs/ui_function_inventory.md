# Funktionsinventar fuer die UI-Neuplanung

Stand: Commit `edec87aa86fe2eb4058ccc83d916f0eb54dc5ae5`

Ziel dieser Datei:
- alle aktuell vorhandenen Funktionen aus Skripten und UIs gesammelt sichtbar machen
- Redundanzen und Ueberlappungen zwischen Web-UI und Desktop-GUI offenlegen
- eine sinnvolle Gruppierung fuer eine spaetere Web-UI-Neuplanung vorbereiten

## 1. Datenabruf und Rohdatenaufbau

### Skripte

#### `scripts/fetch_sessions.py`
- Zweck: Sitzungen und Dokumente aus SessionNet herunterladen
- Hauptparameter:
  - `year`
  - `--months`
  - `--base-url`
  - `--log-level`
- Ergebnis:
  - Rohdaten unter `data/raw/`
  - HTML, Dokumente, Manifeste, Agenda-Zusammenfassungen

#### `scripts/build_online_index_db.py`
- Zweck: Online-Index als SQLite aufbauen, ohne Dokumente herunterzuladen
- Hauptparameter:
  - `year`
  - `--months`
  - `--base-url`
  - `--log-level`
  - `--output`
  - `--migrate-from`
  - `--refresh-existing`
  - `--only-refresh`
- Ergebnis:
  - SQLite-Datenbank fuer einen leichteren, metadata-only Zugriff

### Bisher in den UIs verwendet

#### Desktop-GUI
- Daten-Tools:
  - `Download sessions (raw, script)`
  - `Build online SQLite index (script)`
- Presets:
  - `Fetch + Build Local`
  - `Build Online Index`
- Zusatzfunktionen:
  - Validierung von Jahr/Monaten
  - Live-Log
  - Cancel laufender Prozesse
  - Statusanzeige

#### Web-UI
- Tab `Datenabruf`
  - `fetch_sessions`
  - `build_online_index_db`
- Eingaben:
  - Jahr
  - Monate
- Ausgabe:
  - reiner Prozess-Output im Textbereich

### Sinnvolle Produktgruppe
- `Daten laden`
- optional unterteilen in:
  - `Rohdaten abrufen`
  - `Online-Metadaten aktualisieren`

## 2. Lokale Indizes und Datenbanken

### Skripte

#### `scripts/build_local_index.py`
- Zweck: lokalen SQLite-Index aus `data/raw/` aufbauen
- Hauptparameter:
  - `--data-root`
  - `--output`
  - `--refresh-existing`
  - `--only-refresh`
- Ergebnis:
  - `data/db/local_index.sqlite`

### Bisher in den UIs verwendet

#### Desktop-GUI
- Daten-Tools:
  - `Build local SQLite index (script)`
- Teil des Presets:
  - `Fetch + Build Local`
  - `Build Local`

#### Web-UI
- Tab `Datenabruf`
  - `build_local_index`

### Sinnvolle Produktgruppe
- `Indizes aufbauen`
- optional unterteilen in:
  - `Lokaler Inhaltsindex`
  - `Online-Metadatenindex`

## 3. Semantische Suche und Vektorindex

### Skripte

#### `scripts/build_vector_index.py`
- Zweck: Qdrant-Vektorindex fuer semantische Suche aufbauen oder aktualisieren
- Hauptparameter:
  - `--db`
  - `--qdrant-dir`
  - `--limit`
- Ergebnis:
  - lokaler Qdrant-Index unter `data/db/qdrant/`

### Bisher in den UIs verwendet

#### Web-UI
- eigener Tab `Semantische Suche`
- Funktionen:
  - Query-Eingabe
  - Trefferanzahl einstellen
  - optional auf aktuelle Sitzung eingrenzen
  - Ergebnisliste mit:
    - Rang
    - RRF-Score
    - Titel
    - Dokumenttyp
    - Datum
    - Gremium
    - TOP
    - Link zu lokaler PDF oder Online-Quelle
- technische Schutzmechanismen:
  - Dependency-Check fuer `qdrant-client`, `sentence-transformers`, `fastembed`
  - nur fuer lokalen Index aktiviert
  - Hinweis, wenn Qdrant noch nicht gebaut wurde

#### Desktop-GUI
- keine direkte semantische Suche

### Sinnvolle Produktgruppe
- `Suche & Recherche`
- Untergruppen:
  - `Semantische Suche`
  - spaeter optional `klassische Filter-/Dokumentsuche`

## 4. Analysevorbereitung und KI-Auswertung

### Fachlogik im Projekt

- Auswahl von Sitzungen
- Auswahl von TOPs
- Scope:
  - ganze Sitzung
  - ausgewaehlte TOPs
- Prompt-Vorlagen laden, filtern, speichern
- Provider:
  - `none`
  - `claude`
  - `codex`
  - `ollama`
- Modellname optional
- direkte PDF-Uebergabe an Provider, wenn lokal verfuegbar
- Ergebnis als Markdown/JSON

### Bisher in den UIs verwendet

#### Desktop-GUI
- View `KI-Analyse Vorbereitung`
- Funktionen:
  - Zeitraum-Presets
  - manuelle Datumsgrenzen
  - Gremium
  - Suchfeld
  - Sitzungsstatus
  - Sitzungsliste
  - TOP-Auswahl
  - Analysegrundlage erzeugen
  - Ergebnis anzeigen
  - Markdown exportieren
- Settings:
  - API-Key-Verwaltung ueber separaten Dialog und Settings-View

#### Web-UI
- Tab `Analyse`
- Funktionen:
  - dieselben Grundfilter ueber Sidebar
  - Sitzungsauswahl
  - TOP-Scope
  - Dokumentliste
  - Prompt-Vorlagen
  - Providerwahl
  - Modellname
  - optional PDFs direkt senden
  - Analyse starten
  - Ergebnis anzeigen
  - Markdown/JSON herunterladen

### Sinnvolle Produktgruppe
- `Analyse`
- Untergruppen:
  - `Sitzung vorbereiten`
  - `TOP-Auswahl`
  - `Prompt & Provider`
  - `Analyse-Ergebnis`

## 5. Export und Weitergabe

Status:
- Dieser Bereich ist kein bevorzugter Produktworkflow mehr.
- Der fruehere CLI-Einstiegspunkt liegt archiviert unter `old/scripts/export_analysis_batch.py`.

### Skripte

#### `old/scripts/export_analysis_batch.py`
- Zweck: reproduzierbaren Analyse-Batch aus SQLite-Daten exportieren
- Hauptparameter:
  - `--db-path`
  - `--output`
  - `--session-id`
  - `--committee`
  - `--date-from`
  - `--date-to`
  - `--document-type`
  - `--require-local-path`
- Ergebnis:
  - JSON-Datei unter `data/analysis_requests/`

### Bisher in den UIs verwendet

#### Desktop-GUI
- eigene View `Analyse-Batch Export`
- Funktionen:
  - Exportprofile
  - Zeitraum-Presets
  - Gremienauswahl aus DB
  - Dokumentprofile
  - manuelle Feinsteuerung
  - JSON-Vorschau
  - Export starten
  - Exportdatei oeffnen

#### Web-UI
- Tab `Export`
- Funktionen:
  - Gremienwahl
  - Datumsbereich
  - Export starten
  - letzte Ausgaben anzeigen
- Unterschied zur Desktop-GUI:
  - deutlich weniger Feinsteuerung
  - keine Exportprofile
  - keine Vorschau des JSON-Inhalts

### Sinnvolle Produktgruppe
- `Export & Artefakte`
- Untergruppen:
  - `Analyse-Batch erzeugen`
  - `Vorhandene Ausgaben`

## 6. Dateninspektion und Betriebsfunktionen

### Nur in der Desktop-GUI vorhanden

#### Daten-Tools / lokale Hilfsfunktionen
- `List committees (local index)`
- `Show Data Inventory (local)`
- `Show Data Structure (local)`

#### Service / Settings
- Service-View als Platzhalter fuer Betriebsfunktionen
- Settings-View fuer API-Key-Status und Verwaltung
- Theme-Umschaltung Light/Dark
- Menue mit:
  - Log loeschen
  - API-Keys verwalten
  - About

### In der Web-UI teilweise vorhanden
- Tab `Einstellungen`
  - API-Keys speichern
  - Prompt-Vorlagen verwalten
- kein eigenes Dateninventar
- keine Datenstrukturansicht
- keine Committees-Liste als separate Werkzeugseite

### Sinnvolle Produktgruppe
- `Betrieb & Konfiguration`
- Untergruppen:
  - `API-Keys`
  - `Prompt-Vorlagen`
  - `Systemstatus`
  - `Dateninventar`

## 7. Gemeinsame Filter- und Navigationslogik

### Bereits gemeinsam genutzt

#### `src/interfaces/shared/analysis_store.py`
- `list_committees`
- `list_sessions`
- `resolve_date_range`
- `load_session_and_agenda`
- `load_documents`
- `ensure_analysis_tables`

### Aktuelle gemeinsame Filterdimensionen
- Datenbankpfad
- Zeitraum / Preset
- Gremium
- Freitextsuche
- Sitzungsstatus
- Sitzung
- TOPs

### Sinnvolle Produktgruppe
- `Navigation & Filter`

## 8. Was die Web-UI aktuell bereits abbildet

- globale Filter ueber Sidebar
- Analysevorbereitung
- semantische Suche
- Datenabruf-Skripte
- Einstellungen fuer API-Keys und Prompt-Vorlagen

## 9. Was aktuell nur in der Desktop-GUI vorhanden ist

- Presets fuer Mehrschritt-Datenlaeufe
- Cancel/Live-Log fuer Scriptprozesse
- Dateninventar
- Datenstrukturansicht
- separate Ausschuss-/Gremienliste als Tool
- deutlich umfangreicherer Analyse-Batch-Export
- Theme-/Menuefunktionen

## 10. Empfohlene Zielgruppen fuer eine neue Web-UI

### A. Recherche & Analyse
- Sitzungen finden
- Dokumente sichten
- semantisch suchen
- Analyse erzeugen

### B. Datenpflege
- Rohdaten abrufen
- lokale Indizes bauen
- Vektorindex bauen
- einfache Statuspruefung

### C. Export & Weitergabe
- aktuell eher Archiv-/Expertenfunktion
- nicht als Kernbereich fuer die neue Hauptnavigation einplanen

### D. Konfiguration
- API-Keys
- Prompt-Vorlagen
- spaeter evtl. Modell-/Provider-Defaults

## 11. Vorschlag fuer eine sinnvolle Hauptnavigation

### Variante mit klarer Produktlogik
- `Dashboard`
- `Recherche`
- `Analyse`
- `Datenpflege`
- `Export`
- `Einstellungen`

### Zuordnung der aktuellen Funktionen

#### `Dashboard`
- kuerzlich erzeugte Ausgaben
- Schnellzugriff auf Datenbasis
- Status von DB/Qdrant

#### `Recherche`
- Sitzungsfilter
- Sitzungsliste
- Dokumentliste
- semantische Suche

#### `Analyse`
- Scope waehlen
- Prompt-Vorlagen
- Provider/Modell
- Analyse starten
- Ergebnis und Downloads

#### `Datenpflege`
- `fetch_sessions.py`
- `build_local_index.py`
- `build_online_index_db.py`
- `build_vector_index.py`
- spaeter: Inventar / Struktur / letzte Laeufe

#### `Export`
- archivierter Analyse-Batch-Export
- vorhandene Analyse-Artefakte nur falls spaeter wieder benoetigt

#### `Einstellungen`
- API-Keys
- Prompt-Vorlagen

## 12. Offene Entscheidungen vor dem naechsten UI-Entwurf

- Soll die neue Web-UI eher ein Recherche-Werkzeug oder ein Developer-Tool sein?
- Sollen Datenpflege-Funktionen prominent in der Hauptnavigation stehen oder in einen Admin-Bereich wandern?
- Soll der archivierte Analyse-Batch-Export spaeter ganz entfallen oder als versteckte Expertenfunktion erhalten bleiben?
- Welche Desktop-GUI-Extrafunktionen muessen wirklich in die Web-UI uebernommen werden:
  - Dateninventar
  - Datenstruktur
  - Script-Presets
  - Live-Logs
  - Service-View
