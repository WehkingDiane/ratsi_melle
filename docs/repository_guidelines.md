# Repository-Grundlagen

Dieses Dokument definiert die Grundstruktur und Arbeitsweisen für das Ratsinformations-Analysetool. Es richtet sich an alle Beitragenden und dient als Referenz für neue Dateien, Module und Dokumentationen.

## Verzeichnisstruktur

```
.
├── configs/                # Konfigurationsdateien (JSON, YAML, ENV-Beispiele)
├── data/
│   ├── raw/               # Unveränderte Quelldaten aus Zielsystemen
│   └── processed/         # Aufbereitete Daten (normalisiert, analysiert)
├── docs/                  # Projektweite Dokumentation und Recherchen
├── logs/                  # Laufzeit- und Zugriffprotokolle
├── scripts/               # CLI-Werkzeuge für Betrieb, Wartung und Automatisierung
├── src/
│   ├── fetching/          # Module für Datenerfassung aus Zielsystemen
│   ├── parsing/           # Normalisierung, Parser und Metadaten-Anreicherung
│   ├── analysis/          # Auswertungs- und Scoring-Komponenten
│   └── interfaces/        # UI-, API- oder Integrationsschichten
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

## Datenhaltung

- Rohdaten bleiben unverändert in `data/raw/`. Eine Reproduzierbarkeit der Verarbeitungsschritte ist sicherzustellen.
- Verarbeitete Daten in `data/processed/` enthalten Metadaten zur Herkunft (Sitzung, Quelle, Abrufzeit).
- Sensible Inhalte (personenbezogene Daten, API-Schlüssel) werden nicht eingecheckt. Für Beispiele wird auf `*.template`-Dateien zurückgegriffen.
- Unterordner unter `data/raw/.../agenda/` bestehen ausschließlich aus der TOP-Nummer und dem offiziellen Titel; Zusätze wie „Berichterstatter …“ werden beim Sluggen entfernt, damit identische Punkte unabhängig vom Reporter gleich heißen.
- Jede Sitzung erzeugt zusätzlich zur Dokumenten-`manifest.json` eine `agenda_summary.json`, die Nummer, Titel, Reporter:in, Status, abgeleiteten Beschluss (`accepted`/`rejected`/`null`) sowie ein Flag für vorhandene Dokumente enthält. So lassen sich auch zukünftige Sitzungen mit noch unvollständigen Angaben nachträglich aktualisieren.

## Workflow-Erwartungen

1. Issues oder Tasks im README/todo.md verlinken.
2. Umsetzung in einem Feature-Branch mit klaren Commits.
3. Code-Review einplanen und Ergebnisse dokumentieren.
4. Deployment- oder Betriebsskripte unter `scripts/` ablegen.

Diese Regeln bilden das Fundament für den weiteren Projektverlauf und können bei Bedarf erweitert werden.
