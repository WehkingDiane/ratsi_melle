# GUI-Dokumentation

Diese Datei beschreibt die aktuelle Desktop-GUI unter `src/interfaces/gui/`.

## Ziel

- Daten-Workflows (Fetch/Index/Export) direkt aus der Oberflaeche ausfuehren.
- Vergangene Sitzungen fuer journalistische KI-Aufbereitung auswaehlbar machen.
- Die GUI so strukturieren, dass weitere Seiten (`Settings`, `Service`, spaeter weitere) einfach ergaenzt werden koennen.

## Starten

- Empfohlen aus dem Repo-Root:
  - `python -m src.interfaces.gui.gui_launcher`

Hinweis:
- Unter WSL kann fuer die Darstellung ein funktionierendes Tk/GUI-Setup noetig sein (`python3-tk`).

## Aufbau

Die GUI ist modular aufgeteilt:

- `src/interfaces/gui/gui_launcher.py`
  - Schlanker, rueckwaertskompatibler Einstiegspunkt.
- `src/interfaces/gui/app.py`
  - Hauptklasse `GuiLauncher`, Navigation, State, Events und Orchestrierung.
- `src/interfaces/gui/config.py`
  - Pfade, Farben, Fonts, Theme-Konfiguration.
- `src/interfaces/gui/views/`
  - Seiten-/Layoutmodule:
    - `data_tools_view.py`
    - `analysis_view.py`
    - `settings_view.py`
    - `service_view.py`
- `src/interfaces/gui/services/`
  - Fach-/Infrastruktur-Logik:
    - `script_runner.py` (Subprocess + Cancel)
    - `analysis_store.py` (SQLite-Zugriffe fuer Analyse-Ansicht)

## Seiten

### Daten-Tools

- Script-Actions:
  - `fetch_sessions.py`
  - `build_local_index.py`
  - `build_online_index_db.py`
  - `export_analysis_batch.py`
- Presets fuer Mehrschrittablaeufe.
- Live-Validierung, Logbereich, Detailpanel, Cancel laufender Prozesse.

### Journalistische Analyse

- Filter: Zeitraum, Gremium, Suche, vergangene Sitzungen.
- Sitzungsliste aus `sessions`.
- TOP-Auswahl aus `agenda_items`.
- Scope:
  - ganze Sitzung
  - ausgewaehlte TOPs
- Analyse-Job-Workflow (aktuell lokaler/mockbarer Ablauf) mit Speicherung in:
  - `analysis_jobs`
  - `analysis_outputs`
- Markdown-Export.

### Settings / Service

- Als Erweiterungspunkte vorhanden.
- Dienen als stabile Einhaengepunkte fuer spaetere Konfigurationen und Betriebsfunktionen.

## Persistenz

- GUI-Einstellungen werden in `configs/gui_settings.json` gespeichert.
- Die Datei ist lokal und in `.gitignore` eingetragen.

## Erweiterung: Neue Seite

1. Neues View-Modul in `src/interfaces/gui/views/` anlegen.
2. Builder-Funktion implementieren.
3. In `app.py` in der View-Registry (`_register_views`) eintragen.
4. Falls noetig, passende Service-Funktionen in `src/interfaces/gui/services/` ergaenzen.

## Erweiterung: Neue Action

1. Handler-Methode in `app.py` ergaenzen.
2. Action im `self.actions`-Mapping registrieren.
3. Optional Renderer fuer Detailpanel hinzufuegen.
4. Optional in Presets aufnehmen.

