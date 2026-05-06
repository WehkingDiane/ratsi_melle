# Desktop-GUI-Dokumentation

Diese Datei beschreibt die verbleibende Desktop-GUI unter `src/interfaces/gui/`.

> Status: Deprecated. Neue UI-Funktionsarbeit soll in die Django-Weboberflaeche unter `web/` fliessen. Die Desktop-GUI bleibt vorerst fuer bestehende lokale Workflows erhalten, ist aber nicht mehr die primaere Oberflaeche.
>
> Installationshinweis: Die Legacy-GUI ist nicht mehr Teil des Standard-Setups aus `requirements.txt`. Fuer die Nutzung `pip install -r requirements-legacy-ui.txt` verwenden.

> Hinweis: Die GUI ist noch nicht fertig. Die Oberflaeche und die zugrunde liegende Architektur werden kontinuierlich erweitert und iterativ verbessert.

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
    - `export_view.py`
    - `analysis_view.py`
    - `settings_view.py`
    - `service_view.py`
- `src/interfaces/gui/services/`
  - Fach-/Infrastruktur-Logik:
    - `script_runner.py` (Subprocess + Cancel)
    - `analysis_store.py` (Kompatibilitaets-Wrapper fuer die frueher GUI-lokale Analyse-Store-API)
- `src/interfaces/shared/analysis_store.py`
  - Gemeinsame SQLite-Zugriffe fuer Analyse- und Filter-Workflows in Desktop- und Web-Oberflaeche.
 - `src/analysis/`
   - Analyse-API fuer GUI-unabhaengige Workflows (`AnalysisService`, Batch-Export, Schemas).

## Seiten

### Daten-Tools

- Script-Actions:
  - `fetch_sessions.py`
  - `build_local_index.py`
  - `build_online_index_db.py`
- Presets fuer Mehrschrittablaeufe.
- Live-Validierung, Logbereich, Detailpanel, Cancel laufender Prozesse.

### Analyse-Batch Export

- Eigene Developer-Seite fuer reproduzierbare Analyse-Eingaben.
- Klarere Zweckbeschreibung fuer reproduzierbare Analyse-JSONs.
- Exportprofile, Zeitraum-Presets, Gremienauswahl aus der DB und Dokumentprofile.
- Standardziel getrennt von den DB-Dateien unter `data/analysis_requests/`.
- Vorschau des erzeugten JSON-Inhalts direkt in der GUI.
- Umsetzung nutzt die Analyse-API (`src/analysis/batch_exporter.py`) statt direktem Skriptaufruf.

### KI-Analyse Vorbereitung

- Filter: Zeitraum-Presets, manuelle Datumsgrenzen, Gremium, Suche, Sitzungsstatus (`vergangen`, `heute`, `kommend`).
- Sitzungsliste aus `sessions`.
- TOP-Auswahl aus `agenda_items`.
- Scope:
  - ganze Sitzung
  - ausgewaehlte TOPs
- Analyse-Job-Workflow fuer eine lokale Analysegrundlage mit Speicherung in:
  - `analysis_jobs`
  - `analysis_outputs`
- Die aktive Ausgabe enthaelt Quellenliste und Scope-Kontext, aber keine lokale PDF-/Text-Inhaltsanalyse.
- Artefakt-Export nach `data/analysis_outputs/YYYY/MM/session-ordner/` (spiegelt `data/raw/`-Struktur) und Prompt-Ablage unter `data/analysis_outputs/prompts/`.

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
