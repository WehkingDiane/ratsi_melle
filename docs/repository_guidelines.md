# Repository-Grundlagen

Dieses Dokument definiert die Grundstruktur und Arbeitsweisen für das Ratsinformations-Analysetool. Es richtet sich an alle Beitragenden und dient als Referenz für neue Dateien, Module und Dokumentationen.

## Verzeichnisstruktur

```.
├── configs/                # Konfigurationsdateien (JSON, YAML, ENV-Beispiele)
├── data/
│   ├── raw/               # Unveränderte Quelldaten aus Zielsystemen
│   ├── db/                # SQLite-Infrastrukturdatenbanken
│   ├── analysis_requests/ # Reproduzierbare Analyse-Eingabebatches (JSON)
│   ├── analysis_outputs/  # Analyse-Ergebnisse (Markdown/JSON/Prompts)
│   └── processed/         # Interne Normalisierungen/Ableitungen (ohne DBs)
├── docs/                  # Projektweite Dokumentation und Recherchen
├── logs/                  # Laufzeit- und Zugriffprotokolle
├── scripts/               # CLI-Werkzeuge für Betrieb, Wartung und Automatisierung
├── src/
│   ├── fetching/          # Module für Datenerfassung aus Zielsystemen
│   ├── parsing/           # Normalisierung, Parser und Metadaten-Anreicherung
│   ├── analysis/          # Auswertungs- und Scoring-Komponenten
│   └── interfaces/        # UI-, API- oder Integrationsschichten
│       └── gui/           # GUI-Dateien (app.py, views/, services/, config.py)
└── tests/                 # Unit-, Integrations- und End-to-End-Tests
```

- Leere Verzeichnisse werden mit `.gitkeep` vorgehalten.
- Temporäre Dateien und große Artefakte gehören nicht in das Repository. Sie werden über `.gitignore` ausgeschlossen, sobald diese Datei erstellt ist.

## Namenskonventionen

- Python-Module verwenden `snake_case.py`. Andere Sprachen sollen sich an idiomatische Konventionen halten (z. B. `kebab-case` für JavaScript-Dateien, `UpperCamelCase` für Klassen).
- Verzeichnisse nutzen konsequent `snake_case`.
- Datenordner verwenden das Muster `YYYY-MM-DD_gremium/` für Sitzungspakete und `NN_kurztitel/` für Vorlagenunterordner.
- Konfigurationsdateien enthalten sprechende Präfixe, z. B. `config.production.json`, `secrets.template.env`.

## Dokumentationsstandards

- Projektweite Dokumente entstehen im Ordner `docs/` als Markdown (`.md`).
- Jede funktionale Änderung benötigt eine begleitende Notiz (z. B. Architekturentscheidungen, Datenquellen, Compliance-Ergebnisse).
- README-Dateien in Unterordnern dienen als Einstieg und listen relevante Skripte oder Module auf.

## Code-Richtlinien

- Ein Modul pro Verantwortlichkeit; umfangreiche Komponenten werden in Unterpakete zerlegt.
- Öffentliche Funktionen dokumentieren Eingabeparameter, Rückgabewerte und Ausnahmen mittels Docstrings oder vergleichbarer Mechanismen.
- Logging verwendet spätere zentrale Logger-Hilfen unter `src/` und schreibt ausschließlich in `logs/`.
- GUI-spezifisch: Layouts in `src/interfaces/gui/views/`, fachliche GUI-Helfer in `src/interfaces/gui/services/`, zentrale Orchestrierung in `src/interfaces/gui/app.py`.

## Datenhaltung

- Rohdaten bleiben unverändert in `data/raw/`. Eine Reproduzierbarkeit der Verarbeitungsschritte ist sicherzustellen.
- Verarbeitete Daten in `data/processed/` enthalten nur interne Normalisierungen/Ableitungen ohne SQLite-Infrastruktur.
- SQLite-Datenbanken liegen unter `data/db/`.
- Analyse-Eingaben liegen unter `data/analysis_requests/`, Analyse-Ausgaben unter `data/analysis_outputs/`.
- Sensible Inhalte (personenbezogene Daten, API-Schlüssel) werden nicht eingecheckt. Für Beispiele wird auf `*.template`-Dateien zurückgegriffen.
- Unterordner unter `data/raw/.../agenda/` bestehen ausschließlich aus der TOP-Nummer und dem offiziellen Titel; Zusätze wie „Berichterstatter …“ werden beim Sluggen entfernt, damit identische Punkte unabhängig vom Reporter gleich heißen.
- Jede Sitzung erzeugt zusätzlich zur Dokumenten-`manifest.json` eine `agenda_summary.json`, die Nummer, Titel, Reporter:in, Status, abgeleiteten Beschluss (`accepted`/`rejected`/`null`) sowie ein Flag für vorhandene Dokumente enthält. So lassen sich auch zukünftige Sitzungen mit noch unvollständigen Angaben nachträglich aktualisieren.

## Zielsystem-Hinweise

- Das Projekt arbeitet gegen eine öffentliche SessionNet-Installation der Stadt Melle.
- Abrufe müssen robots.txt, öffentliche Nutzungsbedingungen und Datenschutzanforderungen respektieren.
- Abruflogik soll immer mit Rate-Limits, Retries und Caching umgesetzt werden, um die Zielinfrastruktur nicht unnötig zu belasten.
- Fachliche und technische Details zum Zielsystem und zur Datenverarbeitung stehen in `docs/data_processing_concept.md`; ältere Vorprüfungen liegen im Archiv unter `docs/archive/`.

## Workflow-Erwartungen

1. Issues oder Tasks im README/todo.md verlinken.
2. Umsetzung in einem Feature-Branch mit klaren Commits.
3. Code-Review einplanen und Ergebnisse dokumentieren.
4. Deployment- oder Betriebsskripte unter `scripts/` ablegen.

Diese Regeln bilden das Fundament für den weiteren Projektverlauf und können bei Bedarf erweitert werden.

## CLI-Indexdatenbanken

- `scripts/build_local_index.py` erzeugt einen lokalen Index aus bereits heruntergeladenen Rohdaten (`data/raw/`) und schreibt standardmäßig nach `data/db/local_index.sqlite`.
- `scripts/build_online_index_db.py` erzeugt einen Online-Index ohne Dokumentdownloads und schreibt standardmäßig nach `data/db/online_session_index.sqlite`. Mit `--refresh-existing` werden vorhandene Sitzungen neu eingelesen; `--only-refresh` aktualisiert ausschließlich bestehende Sitzungen.
- Beide Indexe enthalten in `documents` ein normalisiertes Feld `document_type` (`vorlage`, `beschlussvorlage`, `protokoll`, `bekanntmachung`, `sonstiges`) sowie Metadatenfelder `sha1` und `retrieved_at`.
- Der fruehere Export-CLI-Pfad wurde archiviert und liegt unter `old/scripts/export_analysis_batch.py`.

## WSL-Setup (kurz)

- Wenn `python` fehlt, `python3` verwenden.
- Unter WSL die virtuelle Umgebung `.venv-wsl` verwenden.
- Unter Windows die virtuelle Umgebung `.venv` verwenden.
- Empfehlung unter WSL: `python3 -m venv .venv-wsl` und `source .venv-wsl/bin/activate`.
- Abhängigkeiten mit `python -m pip install -r requirements.txt` installieren.

## Versionspflege

- Das Projekt verwendet `Major.Minor.Patch`; die kanonische Versionsnummer liegt in `VERSION`.
- Solange das Projekt noch vor `1.0.0` liegt, gelten pragmatisch:
  - `0.x.0` fuer groessere Entwicklungsschritte oder inkompatiblere Meilensteine
  - `0.x.y` fuer Bugfixes, kleinere Erweiterungen und inkrementelle Verbesserungen
- Sichtbare funktionale Aenderungen, Meilensteine und Releases sollen bewusst eine Pruefung von `VERSION` ausloesen.

## .gitignore & lokale Daten

- Lokale venvs, Caches und Logs werden ueber `.gitignore` ausgeschlossen.
- Rohdaten verbleiben unter `data/raw/`; DBs, Analyse-Requests und Analyse-Outputs liegen unter `data/db/`, `data/analysis_requests/` und `data/analysis_outputs/` und werden nicht committet.
