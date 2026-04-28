# Django-Weboberflaeche

## Zweck

Die neue Weboberflaeche unter `web/` ist der Startpunkt fuer eine zentrale Arbeitsoberflaeche. Sie soll perspektivisch Sitzungen, Quellen, Analyseergebnisse, Textableitungen, Bewertung und Freigabe zusammenfuehren.

Der erste Stand ist bewusst lesend und klein gehalten: vorhandene Sitzungen und Analyseausgaben werden angezeigt, ohne bestehende UI- oder `src/`-Strukturen zu ersetzen.

## Start

```bash
python scripts/run_web.py
```

Danach ist die Analyse-Startseite unter dieser Adresse erreichbar:

```text
http://127.0.0.1:8000/analyse/
```

Alternativ kann ein anderer Port uebergeben werden:

```bash
python scripts/run_web.py 127.0.0.1:8001
```

## Seiten

- `/analyse/` zeigt den Einstieg, Datenstatus und kurze Listen.
- `/analyse/sitzungen/` listet Sitzungen aus dem lokalen Index.
- `/analyse/sitzungen/<session_id>/` zeigt Sitzungsmetadaten, TOPs, Dokumente und Quellenstatus.
- `/analyse/jobs/` listet vorhandene Analysejobs und Ausgabedateien.
- `/analyse/jobs/<job_id>/` zeigt Markdown, `ki_response`, `prompt_text` und strukturierte JSON-Ausgaben, soweit vorhanden.

## Datenquellen

- `data/db/local_index.sqlite` fuer Sitzungen, TOPs, Dokumente und optional einfache Analyse-Tabellen.
- `data/db/analysis_workflow.sqlite` fuer neuere Analyse-Workflow-Metadaten, falls vorhanden.
- `data/analysis_outputs/` fuer JSON-, Markdown- und Prompt-Dateien.

Fehlende Datenquellen fuehren nicht zu Fehlern. Die Oberflaeche zeigt stattdessen leere Listen oder Hinweise.

## Architektur

- `web/core/views.py` enthaelt nur View-Zusammenstellung.
- `web/core/services.py` enthaelt den read-only Datenzugriff.
- `web/core/templates/base.html` stellt das gemeinsame Layout bereit.
- `web/core/static/core/css/` enthaelt zentrale CSS-Dateien fuer Layout, Komponenten und Status.

Die bestehende Fachlogik aus `src/` wird nicht kopiert. Fuer Analyseausgaben wird die vorhandene Normalisierung aus `src.analysis.schemas` genutzt.

## Was noch fehlt

- Filter, Suche und Paginierung fuer groessere Datenmengen.
- Benutzerfuehrung fuer neue Analyseauftraege.
- Review- und Freigabeworkflows.
- Authentifizierung und Rollen.
- Anzeige oder Vorschau lokaler Quelldokumente.
- Produktives Deployment-Setup.
