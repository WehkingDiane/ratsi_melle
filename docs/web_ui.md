# Django-Weboberflaeche

## Zweck

Die Weboberflaeche unter `web/` ist die lokale Arbeitsoberflaeche fuer Ratsi Melle. Sie buendelt die bestehenden Analyseansichten und schafft eine klare Struktur fuer spaetere Bereiche wie Datenpflege, Suche, Veroeffentlichung und Einstellungen.

Die Anwendung ist fuer den lokalen Betrieb auf dem Entwicklungsrechner gedacht. Sie ist nicht fuer oeffentlichen Betrieb, Mehrbenutzerbetrieb oder Deployment ausgelegt und enthaelt keine Benutzerverwaltung.

## Start

```bash
python scripts/run_web.py
```

Danach ist das Dashboard erreichbar:

```text
http://127.0.0.1:8000/
```

Alternativ kann ein anderer Host oder Port uebergeben werden:

```bash
python scripts/run_web.py 127.0.0.1:8001
```

## Warum `web/`

Die Django-Anwendung liegt bewusst unter `web/`, damit sie als lokale Oberflaeche neben den bestehenden CLI-, Daten- und Analysemodulen entwickelt werden kann. Fachlogik aus `src/` wird nicht kopiert, sondern von den Web-Services genutzt. So bleibt die Weboberflaeche ein separater Einstiegspunkt, ohne die bestehenden Skripte und Module zu ersetzen.

## Grundstruktur

```text
web/
  manage.py
  web/
    settings.py
    urls.py
  core/
    templates/base.html
    templates/core/dashboard.html
    static/core/css/
  analysis/
    urls.py
    views.py
    templates/analysis/
  data_tools/
    urls.py
    views.py
    templates/data_tools/
  publishing/
    urls.py
    views.py
    templates/publishing/
  search/
    urls.py
    views.py
    templates/search/
  settings_ui/
    urls.py
    views.py
    templates/settings_ui/
```

`core` enthaelt das gemeinsame Layout, das Dashboard, zentrale CSS-Dateien und gemeinsam genutzte Services. `analysis` enthaelt die Analyse-Navigation und vorhandene Ansichten fuer Sitzungen und Analysejobs. `data_tools` enthaelt technische Fetch-, Build- und Index-Funktionen. `publishing`, `search` und `settings_ui` sind als eigene Bereiche angelegt und enthalten derzeit Platzhalterseiten.

## Navigation

Das gemeinsame Layout in `web/core/templates/base.html` stellt Header, Hauptnavigation, Inhaltsbereich und Footer bereit. Die Navigation zeigt:

- Dashboard
- Analyse
- Daten
- Veroeffentlichung
- Suche
- Einstellungen

Der Header zeigt den Projektnamen "Ratsi Melle" und die Unterzeile "Lokale Arbeitsoberflaeche". Der Footer markiert die Anwendung als lokale Entwicklungsoverflaeche. Die CSS-Dateien liegen zentral unter `web/core/static/core/css/`:

- `base.css` fuer Grundvariablen und Basiselemente
- `layout.css` fuer Seitenstruktur
- `navigation.css` fuer Hauptnavigation und mobiles Menue
- `components.css` fuer Panels, Buttons, Tabellen und Formulare
- `status.css` fuer Status- und Hinweisfarben

## URLs

- `/` zeigt das Dashboard.
- `/analyse/` zeigt den Analyse-Einstieg.
- `/analyse/starten/` bietet den Formularfluss zum Starten einer Analyse.
- `/analyse/sitzungen/` listet Sitzungen aus dem lokalen Index.
- `/analyse/sitzungen/<session_id>/` zeigt Sitzungsdetails.
- `/analyse/jobs/` listet Analysejobs und Ausgabedateien.
- `/analyse/jobs/<job_id>/` zeigt Analyseoutputs, einschliesslich alter v1-Ausgaben.
- `/daten/` zeigt den Daten- und Servicebereich.
- `/daten/fetch/` startet vorhandene Fetch-Skripte.
- `/daten/build/` startet vorhandene Build-Skripte.
- `/daten/jobs/<job_id>/` zeigt Status und Ausgabe eines gestarteten Datenjobs.
- `/veroeffentlichung/` ist ein Platzhalter fuer Publikations- und Reviewfunktionen.
- `/suche/` ist ein Platzhalter fuer spaetere Suche.
- `/einstellungen/` ist ein Platzhalter fuer lokale Einstellungen.

Alte Service-URLs unter `/analyse/service/` werden auf den Datenbereich umgeleitet, damit technische Datenpflege nicht mehr im Analysebereich haengt.

## Bereits funktionsfaehig

- Dashboard mit Datenstatus und Schnelleinstiegen
- Analyse-Startseite
- Analyse starten mit bestehendem `AnalysisService`
- Sitzungsliste und Sitzungsdetails aus `data/db/local_index.sqlite`
- Analysejobliste und Analysejobdetails aus `data/analysis_outputs/`
- Anzeige alter v1-Analyseoutputs
- Fetch- und Build-Servicefunktionen unter `/daten/`
- Statusanzeige fuer laufende Datenjobs im Header

## Platzhalter

- Veroeffentlichung und Review
- Suche ueber Sitzungen, Dokumente und Analyseoutputs
- UI-Einstellungen
- Produktives Deployment
- Authentifizierung, Rollen und Benutzerverwaltung

## Datenquellen

- `data/db/local_index.sqlite` fuer Sitzungen, TOPs, Dokumente und einfache Analyse-Tabellen
- `data/db/analysis_workflow.sqlite` fuer neuere Analyse-Workflow-Metadaten, falls vorhanden
- `data/analysis_outputs/` fuer JSON-, Markdown- und Prompt-Dateien

Fehlende Datenquellen fuehren nicht zu Fehlern. Die Oberflaeche zeigt stattdessen leere Listen oder Hinweise.
