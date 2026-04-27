# Analyse-UI-Workflow

Die Analyse-UI bildet den lokalen Arbeitsfluss fuer Auswahl, Analyse, Review und vorbereitete Publikation ab.

## Neuer Workflow

1. Sitzung aus der lokalen Datenbank waehlen.
2. Ganze Sitzung oder einzelne TOPs auswaehlen.
3. Analysezweck festlegen.
4. Quellencheck vor dem Start pruefen.
5. Prompt-Template, Provider und Modell waehlen.
6. Analyse starten.
7. Strukturierte Ergebnisse, Quellen und Rohdaten getrennt pruefen.
8. Optional vorhandene Publikationsentwuerfe mit lokalem Review- und Publication-Status versehen.

## Analysezwecke

- `journalistic_publication`
- `session_preparation`
- `content_analysis`
- `fact_extraction`

Die UI zeigt die deutschen Labels an und mappt sie intern auf diese stabilen Werte.

## Output-Typen

- `raw_analysis`
- `structured_analysis`
- `journalistic_article`
- `publication_draft`
- `meeting_briefing`

Die Ergebnisansicht trennt Uebersicht, strukturierte Analyse, Quellen, Publikationsentwurf und Rohdaten.

## Review-Status

Fuer Publikationsentwuerfe werden lokal vorbereitete Review-Felder unterstuetzt:

- `required`
- `pending`
- `needs_changes`
- `approved`
- `rejected`

Review-Notizen, Review-Person und Review-Zeitpunkt werden lokal gespeichert. Eine Freigabe loest keine Veroeffentlichung aus.

## Publication-Status

Die UI zeigt vorbereitete Publikationsfelder an:

- `publication.target`
- `publication.status`
- `publication.published_url`
- `publication.published_at`

Moegliche Statuswerte:

- `not_published`
- `draft_created`
- `scheduled`
- `published`
- `failed`

Die UI speichert nur lokalen Status. Echte Veroeffentlichung ist in dieser Version nicht aktiv.

## Alte v1-Ausgaben

Alte Analyseausgaben bleiben lesbar. `normalize_analysis_output(data)` normalisiert v1-Dateien fuer die UI, zeigt alte Felder wie `ki_response`, `markdown` und `prompt_text` weiter unter Rohdaten an und blendet einen Hinweis ein, wenn strukturierte Felder fehlen.

## Workflow-DB und Fallback

Wenn `data/db/analysis_workflow.sqlite` vorhanden ist, liest die UI Jobs, Output-Pfade sowie Review-/Publication-Status aus der Workflow-DB. Falls die DB noch nicht existiert, faellt die Historie auf einen Dateiscan unter `data/analysis_outputs/` zurueck.

## Bekannte Grenzen

- Der Modus `Nur Publikationsentwurf aus vorhandener Struktur` ist aktuell vor allem als vorbereitete UI-Option und Lesepfad vorhanden; ein separater Erzeugungsworkflow ohne neue Analyse ist noch nicht komplett ausgebaut.
- Die strukturierte Analyse nutzt vorhandene v2-Schemas. Inhalte haengen weiterhin davon ab, welche Daten die jeweiligen Analyse-Pipelines bereits fuellen.
- PDF-Oeffnen und URL-Oeffnen bleiben lokale Komfortfunktionen; eine Publikation nach aussen findet nicht statt.
