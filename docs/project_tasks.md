# Architektur und Projektaufgaben

Diese Datei beschreibt die wesentlichen Systemschichten, ihre Beziehungen und die offenen Arbeiten. Die Aufgaben sind nach den Architekturkomponenten geordnet, damit sichtbar wird, wo Änderungen an Schnittstellen oder Zuständigkeiten nötig werden könnten.

## Aktuelle GPT-Modellreihe

Stand: **23.09.2026**. Diese Übersicht wird einmal im Monat anhand der [offiziellen OpenAI-Modellübersicht](https://developers.openai.com/api/docs/models) und der [Modellauswahl-Empfehlungen](https://developers.openai.com/api/docs/guides/model-selection) geprüft. Nächste Prüfung: **bis 23.10.2026**.

| Modell | Orientierung für Aufgaben in dieser Liste | Typischer Reasoning-Aufwand |
| --- | --- | --- |
| GPT-6 Luna (`gpt-6-luna`) | Kleine, klar abgegrenzte Änderungen und einfache Wartungsaufgaben | Medium |
| GPT-6 Sol (`gpt-6-sol`) | Alltägliche Coding-Aufgaben mit Abwägungen und normalem Integrationsumfang | Low–Medium |
| GPT-6 Astra (`gpt-6-astra`) | Komplexe, mehrschichtige Änderungen und anspruchsvolle Analyse | Medium–High |

Die Modellverfügbarkeit und Nutzungslimits können sich je nach Codex-/ChatGPT-Produkt unterscheiden. Die Zuordnung ist eine Orientierung, keine Garantie für Ergebnisqualität oder Verbrauch.

## 1. Architekturüberblick

Der Datenfluss verläuft von externen Quellen bis zu den Analyseergebnissen und ihrer Darstellung:

```text
SessionNet / Landkreis-Angebote
        │
        ▼
Fetch-Clients ──► unveränderte Rohdaten unter data/raw/
        │
        ▼
Build-Skripte ──► lokale SQLite-Datenbanken und Metadaten
        │
        ├──► Extraktion und OCR ──► Vektorindizes und Suche
        │
        └──► Analyse-Service ──► versionierte Analyseartefakte
                                      │
                                      ▼
                              Django-Oberfläche
```

| Schicht | Verantwortlichkeit | Zentrale Bereiche |
| --- | --- | --- |
| Datenzufuhr | Externe Angebote abrufen und Rohdaten lokal ablegen | `src/fetching/`, `scripts/fetch_*.py`, `data/raw/` |
| Datenhaltung | Rohdaten in lokale Datenbanken überführen und Metadaten konsistent halten | `scripts/build_*db.py`, `data/db/` |
| Extraktion und Suche | PDF-Text und OCR gewinnen, Dokumente aufteilen und durchsuchbar machen | `src/analysis/extraction_pipeline.py`, `src/indexing/`, Qdrant |
| Analyse | Dokumente, TOPs und Sitzungen analysieren und Ergebnisse nachvollziehbar speichern | `src/analysis/`, `data/analysis_outputs/` |
| Oberfläche | Analyse-, Such- und Datenpflege-Workflows bereitstellen | `web/` |
| Betrieb und Qualität | Laufzeit, Fehler, Verhalten und Datenqualität über alle Schichten nachvollziehbar halten | Logging, Tests, Jobs und Dokumentation |

SQLite-Datenbanken und Qdrant-Indizes sind abgeleitete lokale Daten. `data/raw/` bleibt die Quelle für reproduzierbare Builds und wird von den Build-Schritten nicht verändert.

## 2. Architekturfragen bei Änderungen

Vor größeren Umbauten sollte für die betroffene Schicht geklärt werden:

- Bleiben Rohdaten, lokale Datenbank und Suchindex klar getrennte Zuständigkeiten?
- Ist das Datenformat an einer dokumentierten Schnittstelle versioniert, und können abgeleitete Daten reproduzierbar neu aufgebaut werden?
- Ändert sich ein Vertrag zwischen Fetching, Speicherung, Extraktion, Analyse oder Oberfläche?
- Können Fehler und Fortschritt auf der betroffenen Schicht erkannt werden, ohne Geheimnisse oder unnötige Dokumentinhalte zu protokollieren?
- Sind Auswirkungen auf lokale Daten, Indizes, bestehende Analyseartefakte und Nutzerabläufe dokumentiert?

## 3. Offene Aufgaben nach Architekturschicht

Jeder offene Punkt kann eine grobe Aufwandseinstufung und eine Modell-Empfehlung enthalten. `Low`, `Medium` oder `High` bezeichnet den Reasoning-Aufwand. Die Empfehlungen sind eine Orientierung für Diane und keine Vorgabe für den Agenten. Die Modellübersicht am Anfang dieser Datei wird monatlich aktualisiert; zwischen den Prüfungen muss nicht für jede einzelne Aufgabe erneut recherchiert werden. Der Pre-Commit-Hook erinnert bei neu ergänzten Aufgaben ohne Einstufung lediglich daran; ein Commit wird dadurch nicht verhindert.

### 3.1 Datenzufuhr

#### Konkrete Aufgaben

- Fetch-Workflows bei Änderungen an SessionNet robust halten und anpassen `[Mittel · GPT-6 Sol / Medium]`
- Inkrementelle Downloads geänderter oder fehlender Dokumente weiter verbessern `[Mittel · GPT-6 Sol / Medium]`
- Landkreis-PDFs, Detailseiten und Manifeste atomar schreiben und vorhandene Dateien auf Vollständigkeit prüfen, damit abgebrochene Downloads nicht als erfolgreich gelten `[Mittel · GPT-6 Sol / Medium]`

### 3.2 Datenhaltung und Builds

### 3.2 Datenhaltung und Builds

#### Konkrete Aufgaben

- Speicher- und Datenbankzugriffe auf Entkopplung prüfen: Repository auf fest codierte Datenbankpfade, Qdrant-Pfade/-URLs und sonstige Speicherorte untersuchen; feststellen, ob fachlicher Code physische Speicherorte oder konkrete Speichertechnologien direkt kennt. Problemstellen dokumentieren und prüfen, ob Verbindungen und Pfade zentral konfigurierbar bzw. über klar definierte Storage-/Service-Schnittstellen gekapselt sind. Zunächst keine Implementierungsänderungen vornehmen. `[Mittel · GPT-6 Sol / Medium]`
- Datenqualität und Metadatenkonsistenz mit Regressionstests absichern `[Mittel · GPT-6 Sol / Low]`
- Build-Workflows robust halten und Änderungen am Quellformat kontrolliert übernehmen `[Mittel · GPT-6 Sol / Medium]`
- Vorschau-Modus für Build-Skripte ergänzen, der geplante Änderungen, fehlende Quelldateien und mögliche Bereinigungen vor dem Schreiben ausgibt `[Mittel · GPT-6 Sol / Medium]`

### 3.3 Extraktion, OCR und Suche

#### Konkrete Aufgaben

- Volltext-, PDF- und OCR-Randfälle im Analyse- und Suchpfad robuster behandeln `[Schwer · GPT-6 Astra / Medium]`
- Optionale OCR-Werkzeuge und das Verhalten bei großen Dateien betrieblich absichern `[Mittel · GPT-6 Sol / Low]`
- Standardlauf von `scripts/build_vector_index.py` auf 100 Dokumente begrenzen; einen vollständigen Durchlauf nur mit einem ausdrücklichen Parameter wie `--all` starten `[Leicht · GPT-6 Luna / Medium]`
- Fortschrittsanzeige für `scripts/build_vector_index.py` ergänzen: Gesamtzahl, bereits indexierte und noch ausstehende Dokumente sowie laufender Fortschritt `[Mittel · GPT-6 Sol / Low]`
- Datei-Logging für Build-Skripte ergänzen, insbesondere für `scripts/build_vector_index.py`, damit Dokument-ID, Fehlerdetails und Stacktrace nach einem langen Lauf ausgewertet werden können `[Leicht · GPT-6 Luna / Medium]`
- Dauerhaften Zwischenstand für lange Indexläufe speichern, einschließlich erledigter, offener und fehlgeschlagener Dokumente, damit Abbrüche nachvollziehbar sind und Läufe gezielt fortgesetzt werden können `[Schwer · GPT-6 Astra / Medium]`
- Qdrant-Local-Modus für große Collections durch einen lokalen Docker-Server ersetzen: Windows-/WSL-Voraussetzungen und Volume dokumentieren, alle Build-, Such- und Statuspfade auf eine konfigurierbare Verbindung umstellen, vorhandene Collections sicher migrieren und Rückweg prüfen `[Schwer · GPT-6 Astra / Medium]`
- Recherchekatalog über weitere Zeiträume, Protokolle und echte Nutzerfragen erweitern; Abschnitts- und Legacy-Index mit `scripts/evaluate_search.py` vergleichen `[Mittel · GPT-6 Sol / Medium]`

### 3.4 Analyse und Artefakte

#### Konkrete Aufgaben

- Analyseziele, Ausgabeformate und Qualitätskriterien verbindlich festlegen `[Mittel · GPT-6 Sol / Medium]`
- Dokumentzentrierten Analyseablauf in der Weboberfläche als End-to-End-Pfad ergänzen; lokale PDFs können bereits in der Vorschau geöffnet werden `[Schwer · GPT-6 Astra / Medium]`
- Quellenbezug, Unsicherheit, Review und Reproduzierbarkeit in Analyseartefakten und Oberfläche sichtbar machen `[Schwer · GPT-6 Astra / Medium]`
- Gemeinsames Antwortschema weiter validieren und bei neuen Analysezwecken versionieren `[Mittel · GPT-6 Sol / Medium]`
- Providerfehler und Kontextgrenzen robuster behandeln `[Mittel · GPT-6 Sol / Medium]`

#### Kontext und Zielbild

Das fachliche Zielbild umfasst Analysen auf drei Ebenen:

- **Dokument:** Kernaussagen, Beschluss- und Finanzierungsbezug sowie Extraktionsqualität
- **Tagesordnungspunkt:** zugeordnete Dokumente zusammenführen, Aussagen belegen und offene Fragen kenntlich machen
- **Sitzung:** Ergebnisse einzelner TOPs zu einer nachvollziehbaren Sitzungsübersicht verdichten

Analyseartefakte sollen Eingabekontext, verwendete Dokumente und Hashes, Prompt-Version, Provider und Modell sowie Parameter und Zeitstempel festhalten. Markdown und strukturiertes JSON sollen Quellenangaben und sichtbare Unsicherheit unterstützen. Draft- und Review-Status sollen unterscheidbar bleiben.

### 3.5 Oberfläche und Anwendungsworkflows

#### Konkrete Aufgaben

- Django-Anwendungen unter `web/` entlang fachlicher Zuständigkeiten modular weiterentwickeln `[Schwer · GPT-6 Astra / Medium]`
- Dokumentauswahl, Analyse, Quellenprüfung und Review als zusammenhängenden Arbeitsablauf gestalten `[Schwer · GPT-6 Astra / Medium]`
- Bestehende Fetch-, Build-, Such- und Analysefunktionen über stabile Service-Schnittstellen einbinden `[Schwer · GPT-6 Astra / Medium]`

### 3.6 Betrieb und Qualität (schichtübergreifend)

#### Konkrete Aufgaben

- Logging, Monitoring und Fehlerdiagnose schichtübergreifend vereinheitlichen `[Mittel · GPT-6 Sol / Medium]`
- Parallele Builds derselben lokalen Qdrant-Collection erkennen und mit einer verständlichen Meldung verhindern `[Mittel · GPT-6 Sol / Medium]`
- Testabdeckung für Datenpipeline, Analyseflüsse und Suchpfade erweitern `[Mittel · GPT-6 Sol / Low]`
- Dokumentation regelmäßig gegen Implementierung, Datenformate und tatsächliche Abläufe prüfen `[Leicht · GPT-6 Luna / Medium]`
- Aufgabenliste nach Architektur- oder Funktionsänderungen aktualisieren und erledigte Punkte entfernen `[Leicht · GPT-6 Luna / Medium]`

## 4. Abhängigkeiten und sinnvolle Reihenfolge

1. Speicher- und Datenbankzugriffe auf Entkopplung prüfen und bestehende Abhängigkeiten zwischen den Schichten dokumentieren.
2. Datenverträge und Metadaten zwischen Fetching, SQLite-Builds und Extraktion stabilisieren.
3. Extraktion, OCR und Suchindex mit Fortschritt, Fehlerdiagnose und Regressionstests absichern.
4. Analyseartefakte und Quellenverweise konsistent versionieren.
5. Dokumentzentrierten Analyse- und Review-Ablauf darauf aufbauend in der Oberfläche vervollständigen.
6. Recherchequalität mit erweitertem Katalog messen und die Dokumentation nachführen.