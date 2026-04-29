# Django-Weboberfläche

## Zweck

Die Weboberfläche unter `web/` ist die lokale Arbeitsoberfläche für Ratsi Melle. Sie bündelt die bestehenden Analyseansichten und schafft eine klare Struktur für spätere Bereiche wie Datenpflege, Suche, Veröffentlichung und Einstellungen.

Die Anwendung ist für den lokalen Betrieb auf dem Entwicklungsrechner gedacht. Sie ist nicht für öffentlichen Betrieb, Mehrbenutzerbetrieb oder Deployment ausgelegt und enthält keine Benutzerverwaltung.

## Start

```bash
python scripts/run_web.py
```

Danach ist das Dashboard erreichbar:

```text
http://127.0.0.1:8000/
```

Alternativ kann ein anderer Host oder Port übergeben werden:

```bash
python scripts/run_web.py 127.0.0.1:8001
```

## Warum `web/`

Die Django-Anwendung liegt bewusst unter `web/`, damit sie als lokale Oberfläche neben den bestehenden CLI-, Daten- und Analysemodulen entwickelt werden kann. Fachlogik aus `src/` wird nicht kopiert, sondern von den Web-Services genutzt. So bleibt die Weboberfläche ein separater Einstiegspunkt, ohne die bestehenden Skripte und Module zu ersetzen.

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

`core` enthält das gemeinsame Layout, das Dashboard, zentrale CSS-Dateien und gemeinsam genutzte Services. `web/core/views.py` enthält nur die Dashboard-View. Die Services sind unter `web/core/services/` fachlich aufgeteilt: `sessions.py` lädt Sitzungseinträge, `outputs.py` liest Analyseausgaben, `source_check.py` prüft lokale Quellen, `prompts.py` lädt Prompt-Vorlagen, `status.py` liefert Status- und Übersichtsangaben. `analysis` enthält die Analyse-Navigation und vorhandene Views für Sitzungen und Analysejobs. `data_tools` enthält die Views für technische Fetch-, Build- und Servicejob-Funktionen. `publishing`, `search` und `settings_ui` sind als eigene Bereiche angelegt und enthalten derzeit Platzhalterseiten.

Analyse-Seitentemplates und fachliche Analyse-Partials liegen ausschließlich unter `web/analysis/templates/analysis/`. Daten-Templates liegen ausschließlich unter `web/data_tools/templates/data_tools/`. `web/core/templates/` bleibt auf `base.html`, das Dashboard und gemeinsam nutzbare Core-Partials beschränkt.

## Navigation

Das gemeinsame Layout in `web/core/templates/base.html` stellt Header, Hauptnavigation, Inhaltsbereich und Footer bereit. Die Hauptpunkte sind als Dropdown-Menüs aufgebaut. Die Navigation zeigt:

- Dashboard
- Analyse mit Unterpunkten für Übersicht, Analyse starten, Sitzungen und Analysejobs
- Daten mit Unterpunkten für Fetch und Build
- Veröffentlichung
- Suche
- Einstellungen

Der Header zeigt den Projektnamen "Ratsi Melle" und die Unterzeile "Lokale Arbeitsoberfläche". Der Footer markiert die Anwendung als lokale Entwicklungsoberfläche. Die CSS-Dateien liegen zentral unter `web/core/static/core/css/`:

- `base.css` für Grundvariablen und Basiselemente
- `layout.css` für Seitenstruktur
- `navigation.css` für Hauptnavigation und mobiles Menü
- `components.css` für Panels, Buttons, Tabellen und Formulare
- `status.css` für Status- und Hinweisfarben

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
- `/daten/jobs/<job_id>/status/` liefert den aktuellen Datenjobstatus als JSON für die automatische Logaktualisierung.
- `/veroeffentlichung/` ist ein Platzhalter für Publikations- und Reviewfunktionen.
- `/suche/` ist ein Platzhalter für spätere Suche.
- `/einstellungen/` ist ein Platzhalter für lokale Einstellungen.

Alte Service-URLs unter `/analyse/service/` werden auf den Datenbereich umgeleitet, damit technische Datenpflege nicht mehr im Analysebereich hängt.

## Analyse Starten

Der Startfluss unter `/analyse/starten/` nutzt den bestehenden `AnalysisService` aus `src.analysis.service`.

Bei einer Analyse der ganzen Sitzung werden alle lokal verfügbaren Dokumente dieser Sitzung in die Analysegrundlage aufgenommen und an den KI-Provider übergeben. Die Analyse-Startseite weist darauf ausdrücklich hin und zeigt, wie viele lokale Dokumente verfügbar sind.

Bei einer TOP-Analyse sind nur Tagesordnungspunkte auswählbar, für die lokal vorhandene Dokumente aufgelöst werden können. Die Analyse-Startseite zeigt pro TOP, ob analysierbare Dokumente vorhanden sind. TOPs ohne lokale Dokumentquelle bleiben deaktiviert, weil die KI sonst nur Metadaten ohne belastbare Analysegrundlage hätte.

Die Analysegrundlage enthält zusätzlich:

- ob die Sitzung vergangen, heute oder zukünftig ist
- Datum, Gremium und Sitzungsname
- Status und Beschluss-/Abstimmungsinformationen der ausgewählten TOPs, soweit im lokalen Index vorhanden
- die Dokumentliste im Scope
- die Art der KI-Übergabe je Dokument: Textauszug, PDF-Anhang oder nur Metadaten

Textdateien wie `.txt`, `.md` und `.html` werden als Auszug in die Analysegrundlage aufgenommen. PDF-Dateien werden als PDF-Pfade an Provider weitergegeben, die PDF-Anhänge oder PDF-Textextraktion unterstützen.

Mit Provider `none` wird nur die Analysegrundlage erzeugt. Ein echter KI-Aufruf erfolgt erst bei Auswahl eines KI-Providers. Eigene Prompt-Vorlagen können direkt im Analyseformular gespeichert werden. Sie werden in `configs/prompt_templates.json` abgelegt und danach in der Vorlagenauswahl angeboten.

## Bereits funktionsfähig

- Dashboard mit Datenstatus und Schnelleinstiegen
- Analyse-Startseite
- Analyse starten mit bestehendem `AnalysisService`
- Sitzungsliste und Sitzungsdetails aus `data/db/local_index.sqlite`
- Analysejobliste und Analysejobdetails aus `data/analysis_outputs/`
- Anzeige alter v1-Analyseoutputs
- Fetch- und Build-Servicefunktionen unter `/daten/`
- Statusanzeige für laufende Datenjobs im Header; ohne laufenden Job bleibt sie ausgeblendet.
- Automatische Aktualisierung der Logausgabe auf Datenjob-Detailseiten.

## Platzhalter

- Veröffentlichung und Review
- Suche über Sitzungen, Dokumente und Analyseoutputs
- UI-Einstellungen
- Produktives Deployment
- Authentifizierung, Rollen und Benutzerverwaltung

## Datenquellen

- `data/db/local_index.sqlite` für Sitzungen, TOPs, Dokumente und einfache Analyse-Tabellen
- `data/db/analysis_workflow.sqlite` für neuere Analyse-Workflow-Metadaten, falls vorhanden
- `data/analysis_outputs/` für JSON-, Markdown- und Prompt-Dateien

Fehlende Datenquellen führen nicht zu Fehlern. Die Oberfläche zeigt stattdessen leere Listen oder Hinweise.
