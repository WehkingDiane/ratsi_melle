# Repository Guidelines

## Projektstruktur & Modulorganisation

- `src/` enthaelt die Python-Pakete: `fetching/` (SessionNet-Client + Modelle), `parsing/`, `analysis/`, `interfaces/` (inkl. `interfaces/gui/` fuer GUI-Dateien).
- `scripts/` enthaelt CLI-Einstiegspunkte wie `scripts/fetch_sessions.py`.
- `tests/` enthaelt pytest-Testmodule sowie HTML-Fixtures in `tests/fixtures/`.
- `data/` speichert Laufzeitdaten: `data/raw/` fuer unveraenderte Downloads und `data/processed/` fuer normalisierte Ausgaben.
- `docs/` enthaelt Projektdokumentation und Recherchen; `configs/` fuer Konfigurationsdateien; `logs/` fuer Laufzeitlogs.

## Build-, Test- und Entwicklungsbefehle

- `pip install -r requirements.txt` installiert die Abhaengigkeiten.
- `python scripts/fetch_sessions.py 2024 --months 5 6` laedt Sitzungen fuer Jahr/Monate nach `data/raw/`.
- `python -m pytest` fuehrt die Tests in `tests/` aus.

## Coding-Style & Namenskonventionen

- Python-Code nutzt 4 Leerzeichen Einrueckung und `snake_case.py` fuer Module.
- Klassennamen folgen `UpperCamelCase`; oeffentliche Funktionen sollen kurze Docstrings haben.
- Verzeichnisse nutzen `snake_case`.
- Datenordner folgen `YYYY-MM-DD_Gremium_ID/`, Tagesordnungspunkte `NN_kurztitel/`.
- Bevorzuge strukturiertes Logging und halte Laufzeitlogs unter `logs/`.

## Test-Richtlinien

- Tests liegen in `tests/` und heissen `test_*.py`.
- Nutze Fixtures aus `tests/fixtures/` beim Parsen von HTML.
- Fuege Tests fuer neue Parsing- oder Download-Edge-Cases hinzu; vor PRs `python -m pytest` laufen lassen.

## Commit- & Pull-Request-Richtlinien

- Commit-Messages sind kurz, im Imperativ und in Satzform; Englisch und Deutsch kommen vor.
- PRs sollten die Aenderung, die Testschritte und Auswirkungen auf Daten/Schemata beschreiben.
- Verlinke zugehoerige Issues/Tasks, wenn verfuegbar, und nenne neue Skripte oder Konfigurationsupdates.

## Daten, Sicherheit & Konfiguration

- Keine Secrets, API-Keys oder grosse Download-Daten einchecken; stattdessen `*.template`-Beispiele.
- Rohdaten bleiben unveraendert unter `data/raw/`, abgeleitete Daten unter `data/processed/`.
- Aktualisiere `docs/`, wenn sich Datenformate oder Crawl-Verhalten aendern.

## Voraussetzungen

- Python 3.11+ und pip sind fuer Skripte und Tests erforderlich.
- Git ist fuer Versionskontrolle und Zusammenarbeit erforderlich.
- Fuer optionale UI-Arbeiten wird Tkinter benoetigt; unter WSL `python3-tk` installieren.

## Agent-spezifische Anweisungen (verpflichtend)

### Branch-Sicherheit

- NIEMALS auf Branch `main` arbeiten.
- Wenn der aktuelle Branch `main` ist, STOPPEN und zuerst einen neuen Branch erstellen.
- Jeder vom Agent erstellte Branch MUSS mit `codex/` beginnen.
- Bevorzugte Muster:
  - codex/feature/*kurze-beschreibung*
  - codex/fix/*kurze-beschreibung*
  - codex/security/*kurze-beschreibung*
  - codex/refactor/*kurze-beschreibung*
  - codex/chore/*kurze-beschreibung*

### Aenderungsdisziplin

- Vermeide "nur-Format"-Commits (z. B. Zeilenenden/Whitespace), ausser auf Anfrage.
- Dateien unter `old/` nicht aendern, ausser explizit angefordert.

## Regeln zu Entfernen & Refactoring (verpflichtend)

- Python-Dateien (`*.py`) duerfen NICHT geloescht werden.
- Wenn eine Datei ungenutzt/obsolet wird oder beim Refactoring ersetzt wird:
  - Datei in `/old` verschieben statt loeschen.
  - Originaldateiname bleibt erhalten.
  - Inhalte der nach `/old` verschobenen Datei nicht aendern, ausser explizit angefordert.

- Typische Faelle:
  - Aufteilen einer grossen Datei in mehrere kleinere Module
  - Ersetzen einer Implementierung durch neue Architektur
  - Ablosen von Legacy-Logik

- Loeschen von Python-Dateien ist nur erlaubt, wenn der User explizit danach fragt.

## WSL-spezifische Python-Umgebung (optional)

- Wenn `python` fehlt, `python3` und `pip3` verwenden.
- Empfohlenes Setup (vom Repo-Root):
  - `python3 -m venv .venv`
  - `source .venv/bin/activate`
  - `python -m pip install -r requirements.txt`
- Tests mit `python -m pytest` ausfuehren (nach Aktivieren der venv).
- Tkinter ist Teil der Standardbibliothek, benoetigt unter WSL aber das Paket: `sudo apt-get install python3-tk`.
