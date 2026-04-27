# Analyseausgaben

Die Analyseausgaben sind ab Schema v2 nach Zweck, Struktur und Workflow-Status getrennt. Das Ziel ist, lokale Analysen weiter automatisierbar zu machen, ohne grosse Inhalte in SQLite zu speichern.

## v1 und v2

`schema_version: "1.0"` war ein einzelner gemischter Output. Er enthielt unter anderem Prompt, Markdown, KI-Rohantwort, Status und Sitzungsbezug in einer Datei.

`schema_version: "2.0"` trennt diese Ebenen:

- `raw_analysis`: Quellen- und Rohinformationen zur Sitzung, zu TOPs und Dokumenten.
- `structured_analysis`: maschinenlesbare Analyse mit Fakten, Entscheidungen, finanziellen Effekten, betroffenen Gruppen und offenen Fragen.
- `publication_draft`: journalistischer Entwurf mit Review- und Publikationsstatus.
- `journalistic_article`: Markdown-Artefakt fuer den lesbaren Artikel- oder Analyseentwurf.

Alte v1-Dateien bleiben lesbar. `normalize_analysis_output(data)` bildet sie auf ein kompatibles Normalformat ab und setzt fehlende Zwecke auf `content_analysis`.

## Analysezweck

Jeder neue Analyseauftrag kann ein `purpose` enthalten. Der Default ist:

```text
content_analysis
```

Unterstuetzte Werte:

- `journalistic_publication`
- `session_preparation`
- `content_analysis`
- `fact_extraction`

Journalistische Entwuerfe sollen explizit `journalistic_publication` verwenden. Dadurch koennen spaetere Workflows Review, Freigabe und Veroeffentlichung separat behandeln.

## Dateistruktur

Neue Artefakte werden sitzungsorientiert abgelegt:

```text
data/analysis_outputs/YYYY/MM/session-folder/
  job_1.raw.json
  job_1.structured.json
  job_1.publication.json
  job_1.article.md
```

Bestehende Dateien werden nicht ueberschrieben. Falls ein Zielname bereits existiert, wird ein numerischer Suffix ergaenzt, zum Beispiel `job_1.raw.1.json`.

## Workflow-DB

Die Workflow-Datenbank liegt unter:

```text
data/db/analysis_workflow.sqlite
```

Sie dient als Index und Statussystem. Grosse Inhalte bleiben in JSON- und Markdown-Dateien. Die wichtigsten Tabellen sind:

- `analysis_jobs`: Analyseauftrag mit Sitzung, Scope, TOPs, Zweck, Modell, Prompt-Version und Status.
- `analysis_outputs`: Verweise auf JSON- und Markdown-Artefakte mit Output-Typ und Schema-Version.
- `publication_jobs`: vorbereiteter Review- und Veroeffentlichungsstatus fuer Publikationsentwuerfe.

Eine echte Veroeffentlichung findet noch nicht statt. `publication_jobs` bereitet nur spaetere Ziele wie lokale statische Webseiten, CMS, WordPress oder Workflow-Systeme vor.

## Beispiel

Ein Publikationsentwurf enthaelt mindestens:

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
-> spaeter automatisiert veroeffentlichen
```
