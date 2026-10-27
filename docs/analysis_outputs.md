# Analyseausgaben: aktueller Vertrag

Stand: 27.10.2026. Dieser Abschnitt beschreibt den vorhandenen öffentlichen Analysepfad. Der RI-Ausbau umfasst ihn derzeit nicht.

Analysejobs werden in `data/db/analysis_workflow.sqlite` verwaltet. Große Inhalte bleiben als JSON- oder Markdown-Dateien unter `data/analysis_outputs/YYYY/MM/<sitzung>/`. Gerenderte Prompts und Snapshots liegen unter `data/private/analysis_prompts/` beziehungsweise `data/private/prompt_snapshots/`.

Das Schema `2.0` trennt `raw_analysis`, `structured_analysis`, `publication_draft` und `journalistic_article`. Vorhandene Dateien mit Schema `1.0` bleiben über die Normalisierung lesbar. Ausgaben erhalten bei Namenskollisionen einen numerischen Suffix, damit bestehende Dateien nicht überschrieben werden. Die öffentliche Jobnummer stammt aus `analysis_jobs.job_id`.

Die Weboberfläche kann Analysen vorbereiten, an einen konfigurierten Provider absenden und Ergebnisse unter `/analyse/antworten/` lesen. Publikationsentwürfe werden lokal abgelegt und über `/veroeffentlichung/` angezeigt; es erfolgt keine automatische externe Veröffentlichung. Private Prompt-Vorlagen liegen in `data/private/prompt_templates.json`; das versionierte Formatbeispiel steht unter `docs/examples/prompt_templates.example.json`.
