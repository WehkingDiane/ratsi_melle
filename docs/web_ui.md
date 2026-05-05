# Django-Weboberfläche

## Zweck

Die Weboberfläche unter `web/` ist die lokale Arbeitsoberfläche für Ratsi Melle. Sie bündelt die bestehenden Analyseansichten, Datenpflegepfade und Servicefunktionen in einer klaren Django-Struktur.

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
    services.py
    templates/analysis/
  data_tools/
    urls.py
    views.py
    services.py
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

`core` enthält das gemeinsame Layout, das Dashboard, zentrale CSS-Dateien und gemeinsam genutzte Helfer. `analysis` enthält die Analyse-Navigation, Views und Service-Fassade für Sitzungen, Analysejobs, Prompt-Vorlagen und den Analyse-Start. `data_tools` enthält die Views und Service-Fassade für technische Fetch-, Build- und Servicejob-Funktionen. `publishing`, `search` und `settings_ui` sind als eigene Bereiche angelegt und enthalten derzeit Platzhalterseiten.

Analyse-Seitentemplates und fachliche Analyse-Partials liegen ausschließlich unter `web/analysis/templates/analysis/`. Daten-Templates liegen ausschließlich unter `web/data_tools/templates/data_tools/`. `web/core/templates/` bleibt auf `base.html`, das Dashboard und gemeinsam nutzbare Core-Partials beschränkt.

## Navigation

Das gemeinsame Layout in `web/core/templates/base.html` stellt Header, Hauptnavigation, Inhaltsbereich und Footer bereit. Die Hauptpunkte sind als Dropdown-Menüs aufgebaut. Die Navigation zeigt:

- Dashboard
- Analyse mit Unterpunkten für Übersicht, Analyse starten, Prompt-Vorlagen, Sitzungen und Analysejobs
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
- `/analyse/prompts/` listet private Prompt-Vorlagen und bietet Scope-Filter.
- `/analyse/prompts/neu/` zeigt das Formular zum Anlegen einer Prompt-Vorlage.
- `/analyse/prompts/<template_id>/` zeigt das Formular zum Bearbeiten einer Prompt-Vorlage.
- `/analyse/prompts/<template_id>/duplizieren/` dupliziert eine Vorlage per POST.
- `/analyse/prompts/<template_id>/deaktivieren/` deaktiviert eine Vorlage per POST.
- `/analyse/sitzungen/` listet Sitzungen aus dem lokalen Index.
- `/analyse/sitzungen/<session_id>/` zeigt Sitzungsdetails.
- `/analyse/jobs/` listet Analysejobs und Ausgabedateien.
- `/analyse/jobs/<job_id>/` zeigt Analyseoutputs, einschließlich alter v1-Ausgaben.
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

Mit Provider `none` wird nur die Analysegrundlage erzeugt. Ein echter KI-Aufruf erfolgt erst bei Auswahl eines KI-Providers. Prompt-Vorlagen werden unter `/analyse/prompts/` verwaltet und privat gespeichert. Das Analyseformular bietet nur aktive Vorlagen an, die zum gewählten Scope passen.

## Bereits funktionsfähig

- Dashboard mit Datenstatus und Schnelleinstiegen
- Analyse-Startseite
- Analyse starten mit bestehendem `AnalysisService`
- private Prompt-Vorlagenverwaltung unter `/analyse/prompts/`
- Sitzungsliste und Sitzungsdetails aus `data/db/local_index.sqlite`
- Analysejobliste und Analysejobdetails aus `data/analysis_outputs/`
- Anzeige alter v1-Analyseoutputs
- Fetch- und Build-Servicefunktionen unter `/daten/`
- Statusanzeige für laufende Datenjobs im Header; ohne laufenden Job bleibt sie ausgeblendet
- automatische Aktualisierung der Logausgabe auf Datenjob-Detailseiten

## Platzhalter

- Veröffentlichung und Review
- Suche über Sitzungen, Dokumente und Analyseoutputs
- UI-Einstellungen
- Produktives Deployment
- Authentifizierung, Rollen und Benutzerverwaltung

## Private Prompt-Vorlagen

Produktive Prompt-Vorlagen werden nicht im Repository gespeichert. Der Standardpfad liegt im privaten Datenbereich:

```text
data/private/prompt_templates.json
```

Der Pfad kann über Environment-Variablen angepasst werden:

- `RATSI_PRIVATE_DATA_DIR` für den privaten Datenbereich
- `RATSI_PROMPT_TEMPLATES_PATH` für die konkrete JSON-Datei

Beim ersten Zugriff kann die private Datei aus `configs/prompt_templates.example.json` initialisiert werden. Diese Beispiel-Datei enthält nur harmlose Demo-Prompts. Echte Vorlagen werden über die Django-Seite `/analyse/prompts/` erstellt und bleiben durch `.gitignore` außerhalb des Repository-Inhalts geschützt.

Prompt-Vorlagen haben einen primären Scope (`session`, `tops` oder `document`). Intern können geladene Legacy-Vorlagen mehrere Scopes behalten, damit bestehende private JSON-Dateien weiter in allen vorgesehenen Analysekontexten auswählbar bleiben.

## Prompt-Snapshots

Neue Analysejobs speichern Template-ID, Revision und Label. Der gerenderte Prompt-Snapshot wird im privaten Datenbereich abgelegt, damit alte Jobs nachvollziehbar bleiben, auch wenn eine Vorlage später geändert wird.

Gerenderte Prompt-Snapshots und private Prompt-Artefakte werden nicht als normale Quellen oder Dateien in der Job-Detailansicht angezeigt. Die UI kann Metadaten wie Vorlage, Revision und Zeitpunkt anzeigen, ohne private Prompt-Pfade als öffentliche Artefaktquellen auszugeben.

## Datenquellen

- `data/db/local_index.sqlite` für Sitzungen, TOPs, Dokumente und einfache Analyse-Tabellen
- `data/db/analysis_workflow.sqlite` für neuere Analyse-Workflow-Metadaten, falls vorhanden
- `data/analysis_outputs/` nur für JSON- und Markdown-Analyseartefakte
- `data/private/prompt_templates.json` für private Prompt-Vorlagen
- `data/private/analysis_prompts/` für private Prompt-Artefakte
- `data/private/prompt_snapshots/` für gerenderte Prompt-Snapshots

Fehlende Datenquellen führen nicht zu Fehlern. Die Oberfläche zeigt stattdessen leere Listen oder Hinweise. Eine fehlerhafte private Prompt-Vorlagen-Datei blockiert die Analyse- und Vorlagenseiten nicht; die UI zeigt dann keine Vorlagen an, bis die private Datei repariert ist.
