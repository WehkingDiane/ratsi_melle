# Repository-Grundlagen

Stand: 27.10.2026. Die verbindlichen Agenten- und Branchregeln stehen in [AGENTS.md](../../AGENTS.md). Der [Ist-Stand](../ist_stand.md) fasst den aktuellen Funktionsumfang zusammen; der [RI-Plan](../plans/ri_ratsbereich_plan.md) ist das einzige aktuelle Ausbauvorhaben.

## Struktur und Ablage

- `src/` enthält Fetching, Parsing, Analyse, Indexierung und gemeinsam genutzte Dienste. `scripts/` enthält CLI-Einstiege. `web/` enthält die aktive Django-Oberfläche. `tests/` enthält pytest-Tests und Fixtures.
- `docs/` enthält den Ist-Stand, Betriebsdokumentation und Regeln. Pläne, Ideen und Aufgaben liegen unter `docs/plans/`; versionierte Beispiele liegen unter `docs/examples/`. `docs/plans/project_tasks.md` enthält nur aktuelle Aufgaben. Historische Fassungen liegen in Git; lokal archivierte Kopien entfernter Dateien liegen unter `archive/`.
- Rohdaten liegen unter `data/raw/`, abgeleitete Dateien unter `data/processed/`, SQLite-Datenbanken unter `data/db/`. Analyse-Eingaben liegen unter `data/analysis_requests/`, Ausgaben unter `data/analysis_outputs/`, private Prompt-Dateien unter `data/private/`.
- Laufzeitdaten, Modelle, Logs, Geheimnisse und das lokale Archiv werden nicht eingecheckt. Echte Zugangsdaten gehören in einen geeigneten Secret-Speicher. Dokumente und Suchtreffer dürfen nur auf erlaubte Datenwurzeln verweisen.
- Python-Module heißen `snake_case.py`. Sitzungsordner folgen dem vorhandenen Schema unter `data/raw/YYYY/MM/`; SessionNet-Dokumente und Manifeste behalten ihre ursprünglichen Rohdaten.

## Entwicklung und Dokumentation

- Anwendungsänderungen erhalten passende Tests und eine Aktualisierung der betroffenen Dokumentation. Für Web-Änderungen gelten die [UI-Regeln](ui_guidelines.md); Datenformate und Nutzerwege werden in den Fachbereichen des [Dokumentationswegweisers](../README.md) beschrieben.
- Die normale Entwicklung prüft `python -m pytest -m "not integration and not live"`; für betroffene Abläufe kommen Integrationstests hinzu. Den vollständigen PR-Testlauf führt der Nutzer aus; `live` ist standardmäßig ausgeschlossen. Die verbindliche Agentenregel steht in [AGENTS.md](../../AGENTS.md).
- Die kanonische Version steht in `VERSION`. Pro zusammenhängendem Änderungspaket die Einordnung nach den [Versionsregeln](../../AGENTS.md#versionspflege) prüfen: Patch für kleinere funktionale Änderungen, Minor für größere Funktionsausbauten oder inkompatible Daten-/Konfigurationsänderungen. Reine Dokumentations-, Test- und verhaltensneutrale Refactoring-Änderungen benötigen keine neue Anwendungsversion. Versionsänderung und Changelog-Eintrag gemeinsam committen; noch nicht zugeordnete Änderungen unter „Unveröffentlicht“ sammeln.
- Branches verwenden das Agentenpräfix, Codex also `codex/`. Auf `main` wird nicht gearbeitet. Commits sind klein und zusammenhängend.
- Bei Entfernen oder Ablösen einer Datei zuerst eine bytegleiche Kopie unter `archive/<ursprünglicher-pfad>` anlegen und per SHA-256 prüfen. `archive/` wird von Git ignoriert und muss außerhalb von Git gesichert werden, wenn die lokale Kopie dauerhaft benötigt wird. Frühere Versionen bleiben außerdem in Git erreichbar.

## Laufzeitgrenzen

- Der öffentliche SessionNet-Client begrenzt Anfragerate, Wiederholungen und Downloads. Dokumente über 100 MiB werden abgebrochen; ab 25 MiB wird gewarnt. Landkreis-Downloads brechen über 25 MiB ab.
- Öffentliche und künftige interne RI-Daten müssen über den gesamten Weg getrennt bleiben: Download, Rohdaten, SQLite, Suchindex, Dateiauslieferung und Jobs. Der RI-Plan beschreibt die noch ausstehende Umsetzung.

## Dokumentationsstruktur

Fachbereiche liegen unter `docs/datenabruf/`, `docs/suche/`, `docs/oberflaeche/`, `docs/analyse/` und `docs/ri/`. Betrieb und Entwicklung haben eigene Ordner. Der [Wegweiser](../README.md) legt Einstieg und Pflegekonventionen fest. Testaufrufe stehen unter [Tests](tests.md).
