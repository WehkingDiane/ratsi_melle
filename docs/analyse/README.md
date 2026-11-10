# Analysen durchführen

[Dokumentation](../README.md)

- Unter Erweiterungen (weiterhin `/analyse/`) gibt es Sitzungsansichten, Vorlagen für Prompts, vorbereitete Analysejobs, die Provider-Ausführung und eine Antwort-Leseansicht. Workflow-Zustand liegt in `data/db/analysis_workflow.sqlite`, Ausgabedateien in `data/analysis_outputs/`, private Prompt-Dateien in `data/private/`. Der vorhandene Analysepfad wird im RI-Vorhaben zunächst nicht erweitert.

## Ablauf

Unter Erweiterungen eine Sitzung auswählen, eine Prompt-Vorlage verwenden und einen Analysejob vorbereiten. Nach Konfiguration des Providers kann der Job ausgeführt und die Antwort unter `/analyse/antworten/` gelesen werden.

Der [Ausgabevertrag](ausgabeformat.md) beschreibt Schema und Artefakte. Es erfolgt keine automatische externe Veröffentlichung.
