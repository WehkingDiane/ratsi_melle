# Analyseausgaben

Die Analyseausgaben sind ab Schema v2 nach Zweck, Struktur und Workflow-Status getrennt. Das Ziel ist, lokale Analysen weiter automatisierbar zu machen, ohne große Inhalte in SQLite zu speichern.

## v1 und v2

`schema_version: "1.0"` war ein einzelner gemischter Output. Er enthielt unter anderem Prompt, Markdown, KI-Rohantwort, Status und Sitzungsbezug in einer Datei.

`schema_version: "2.0"` trennt diese Ebenen:

- `raw_analysis`: Quellen- und Rohinformationen zur Sitzung, zu TOPs und Dokumenten.
- `structured_analysis`: maschinenlesbare Analyse mit Fakten, Entscheidungen, finanziellen Effekten, betroffenen Gruppen und offenen Fragen.
- `publication_draft`: journalistischer Entwurf mit Review- und Publikationsstatus.
- `journalistic_article`: Markdown-Artefakt für den lesbaren Artikel- oder Analyseentwurf.

Alte v1-Dateien bleiben lesbar. `normalize_analysis_output(data)` bildet sie auf ein kompatibles Normalformat ab und setzt fehlende Zwecke auf `content_analysis`.

## Analysezweck

Jeder neue Analyseauftrag kann ein `purpose` enthalten. Der Default ist:

```text
content_analysis
```

Unterstützte Werte:

- `journalistic_publication`
- `session_preparation`
- `content_analysis`
- `fact_extraction`

Journalistische Entwürfe sollen explizit `journalistic_publication` verwenden. Dadurch können spätere Workflows Review, Freigabe und Veröffentlichung separat behandeln.

## Dateistruktur

Neue JSON- und Markdown-Artefakte werden sitzungsorientiert abgelegt:

```text
data/analysis_outputs/YYYY/MM/session-folder/
  job_1.raw.json
  job_1.structured.json
  job_1.publication.json
  job_1.article.md
```

Bestehende Dateien werden nicht überschrieben. Falls ein Zielname bereits existiert, wird ein numerischer Suffix ergänzt, zum Beispiel `job_1.raw.1.json`.

Gerenderte Prompt-Snapshots und private Prompt-Artefakte liegen nicht unter `data/analysis_outputs/`, sondern im privaten Datenbereich:

```text
data/private/analysis_prompts/
data/private/prompt_snapshots/
```

Diese privaten Prompt-Dateien werden nicht als normale Quellen oder Ausgabedateien in der Job-Detailansicht angezeigt.

## Workflow-DB

Die Workflow-Datenbank liegt unter:

```text
data/db/analysis_workflow.sqlite
```

Sie dient als Index und Statussystem. Große Inhalte bleiben in JSON- und Markdown-Dateien. Die wichtigsten Tabellen sind:

- `analysis_jobs`: Analyseauftrag mit Sitzung, Scope, TOPs, Zweck, Modell, Prompt-Version, Prompt-Vorlagen-Metadaten und Status.
- `analysis_outputs`: Verweise auf JSON- und Markdown-Artefakte mit Output-Typ und Schema-Version.
- `publication_jobs`: vorbereiteter Review- und Veröffentlichungsstatus für Publikationsentwürfe.

Eine echte Veröffentlichung findet noch nicht statt. `publication_jobs` bereitet nur spätere Ziele wie lokale statische Webseiten, CMS, WordPress oder Workflow-Systeme vor.

Prompt-bezogene Felder in `analysis_jobs`:

- `prompt_template_id`: ID der ausgewählten Prompt-Vorlage zum Zeitpunkt des Analysejobs.
- `prompt_template_revision`: Revision der Vorlage zum Zeitpunkt des Analysejobs.
- `prompt_template_label`: Anzeigename der verwendeten Vorlage.
- `rendered_prompt_snapshot_path`: privater Pfad zum gerenderten Prompt-Snapshot.

Alte Analysejobs ohne diese Felder bleiben lesbar. Wenn eine Vorlage später geändert wird, bleiben ID, Revision, Label und Snapshot des alten Jobs unverändert nachvollziehbar.

## Beispiel

Ein Publikationsentwurf enthält mindestens:

```json
{
  "schema_version": "2.0",
  "output_type": "publication_draft",
  "purpose": "journalistic_publication",
  "status": "draft",
  "review": {
    "required": true,
    "status": "pending"
  },
  "publication": {
    "target": "local_static_site",
    "status": "not_published"
  }
}
```

Der geplante Ablauf ist:

```text
Analyseauftrag anlegen
-> Rohdaten und Quellen speichern
-> strukturierte Analyse erzeugen
-> optional Publikationsentwurf erzeugen
-> Review/Freigabe nachverfolgen
-> später automatisiert veröffentlichen
```
