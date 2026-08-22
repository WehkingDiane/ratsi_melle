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

- `meeting_briefing`: nutzerorientierter Überblick über alle TOPs einer Sitzung.
- `top_deep_dive`: Detailanalyse einzelner Tagesordnungspunkte mit kritischen Rückfragen.
- `journalistic_publication`
- `session_preparation`
- `content_analysis`
- `fact_extraction`

Für die Vorbereitung eines Termins ist `meeting_briefing` der UI-Default bei ganzen Sitzungen. Für einzelne Tagesordnungspunkte ist `top_deep_dive` der UI-Default. Journalistische Entwürfe sollen explizit `journalistic_publication` verwenden. Dadurch können spätere Workflows Review, Freigabe und Veröffentlichung separat behandeln.

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

- `analysis_jobs`: kanonischer Analyseauftrag mit öffentlicher Jobnummer, verständlichem Titel, Sitzung, Scope, TOPs, Zweck, Modell, Prompt-Version, Prompt-Vorlagen-Metadaten und Status.
- `analysis_outputs`: Verweise auf JSON- und Markdown-Artefakte mit Output-Typ und Schema-Version.
- `publication_jobs`: vorbereiteter Review- und Veröffentlichungsstatus für Publikationsentwürfe.

Eine echte Veröffentlichung findet noch nicht statt. `publication_jobs` bereitet nur spätere Ziele wie lokale statische Webseiten, CMS, WordPress oder Workflow-Systeme vor.

Prompt-bezogene Felder in `analysis_jobs`:

- `prompt_template_id`: ID der ausgewählten Prompt-Vorlage zum Zeitpunkt des Analysejobs.
- `prompt_template_revision`: Revision der Vorlage zum Zeitpunkt des Analysejobs.
- `prompt_template_label`: Anzeigename der verwendeten Vorlage.
- `rendered_prompt_snapshot_path`: privater Pfad zum gerenderten Prompt-Snapshot.

Alte Analysejobs ohne diese Felder bleiben lesbar. Wenn eine Vorlage später geändert wird, bleiben ID, Revision, Label und Snapshot des alten Jobs unverändert nachvollziehbar.

Die Weboberfläche verwendet ausschließlich `analysis_jobs.job_id` aus dieser Workflow-Datenbank als öffentliche Nummer. `source_job_id` und Präfixe wie `local:` oder `workflow:` sind interne Alt- beziehungsweise Verknüpfungsdaten und werden Nutzern nicht mehr als getrennte Jobs angezeigt. Vorbereitete Markdown-Artefakte besitzen einen zunächst leeren Abschnitt `## KI-Analyse`; eine spätere Provider-Ausführung aktualisiert denselben Datensatz und dasselbe Markdown-Artefakt. Strukturierte Antworten werden für dieses Markdown regelbasiert in lesbare Überschriften, Absätze, Listen und Quellenlinks übertragen. Das ursprüngliche JSON bleibt unverändert im KI-Antwortartefakt gespeichert.

Die Leseansicht unter `/analyse/antworten/` übernimmt nur gefüllte Abschnitte `## KI-Analyse`. Sie orientiert sich am vorhandenen Antwortinhalt und zeigt dadurch auch nachträglich aufbereitete Antworten, deren ältere Statusmetadaten noch nicht konsistent sind. Analysegrundlage, Prompt und technische Artefakte werden dort ausgeblendet und bleiben über die Jobdetailseite erreichbar.

Bei einem nachträglich ausgeführten Job mit dem Zweck `journalistic_publication` werden neben den bestehenden Analyseartefakten auch der Publikationsentwurf, der zugehörige Workflow-Output und der Publikationsjob im selben Workflow-Datensatz ergänzt. Das Platzhaltermodell `none` vorbereiteter Jobs wird beim Absenden nicht als Modellname übernommen; ein leeres Modellfeld verwendet das Standardmodell des ausgewählten Providers.

Automatisch ausgeführte Webanalysen ergänzen den gespeicherten Fachprompt um einen verbindlichen JSON-Ausgabevertrag. Dieser verwendet dieselben Felder wie die regelbasierte Markdown-Aufbereitung. Der Vertrag wird auch beim Nachstart älterer vorbereiteter Jobs ergänzt. Ein Workflow-Job wird vor dem Provideraufruf atomar von `prepared` oder `error` nach `running` übernommen; nur der erfolgreiche Claim darf den kostenpflichtigen Aufruf ausführen.

Schlägt die Ausführung nach diesem Claim unerwartet fehl, wird der Job wieder als `error` und damit wiederholbar gespeichert. Provider-IDs werden ebenso wie `none` nicht als Modellvorgabe in das Wiederholungsformular übernommen. Bei Workflow-Jobs mit `response_status=valid_json` bleibt der Status `done` auch dann erhalten, wenn die Rohantwort nicht als eigener Workflow-Output indexiert wurde.

Beim Nachstart werden sowohl die regulären Artefaktnamen als auch kollisionsbedingt nummerierte Varianten wie `job_1.article.1.md`, `job_1.raw.1.json` und `job_1.structured.1.json` erkannt. Dadurch bleiben vorbereitete Jobs auch nach einem Indexneuaufbau oder einer wiederverwendeten lokalen Job-ID ausführbar.

Abgeleitete KI-Antwort- und Publikationsdateien behalten denselben Kollisionssuffix, beispielsweise `job_1.ki_response.1.json` und `job_1.publication.1.json`. Das nummerierte Rohartefakt wird dadurch nicht überschrieben.

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
