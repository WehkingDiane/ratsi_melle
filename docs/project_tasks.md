# Architektur und Projektaufgaben

Diese Datei beschreibt die wesentlichen Systemschichten, ihre Beziehungen und die offenen Arbeiten. Die Aufgaben sind nach den Architekturkomponenten geordnet, damit sichtbar wird, wo Änderungen an Schnittstellen oder Zuständigkeiten nötig werden könnten.

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

### 3.1 Datenzufuhr

- Fetch-Workflows bei Änderungen an SessionNet robust halten und anpassen
- Inkrementelle Downloads geänderter oder fehlender Dokumente weiter verbessern
- Datei-Logging in Fetch-Skripten um Laufzeit, Fortschritt und Fehler ergänzen

### 3.2 Datenhaltung und Builds

- Datenqualität und Metadatenkonsistenz mit Regressionstests absichern
- Build-Workflows robust halten und Änderungen am Quellformat kontrolliert übernehmen
- Datei-Logging für Datenbank-Builds ausbauen

### 3.3 Extraktion, OCR und Suche

- Volltext-, PDF- und OCR-Randfälle im Analyse- und Suchpfad robuster behandeln
- Optionale OCR-Werkzeuge und das Verhalten bei großen Dateien betrieblich absichern
- Fortschrittsanzeige für `scripts/build_vector_index.py` ergänzen: Gesamtzahl, bereits indexierte und noch ausstehende Dokumente sowie laufender Fortschritt
- Recherchekatalog über weitere Zeiträume, Protokolle und echte Nutzerfragen erweitern; Abschnitts- und Legacy-Index mit `scripts/evaluate_search.py` vergleichen

### 3.4 Analyse und Artefakte

- Analyseziele, Ausgabeformate und Qualitätskriterien verbindlich festlegen
- Dokumentzentrierten Analyseablauf in der Weboberfläche als End-to-End-Pfad ergänzen; lokale PDFs können bereits in der Vorschau geöffnet werden
- Quellenbezug, Unsicherheit, Review und Reproduzierbarkeit in Analyseartefakten und Oberfläche sichtbar machen
- Gemeinsames Antwortschema weiter validieren und bei neuen Analysezwecken versionieren
- Providerfehler und Kontextgrenzen robuster behandeln

Das fachliche Zielbild umfasst Analysen auf drei Ebenen:

- **Dokument:** Kernaussagen, Beschluss- und Finanzierungsbezug sowie Extraktionsqualität
- **Tagesordnungspunkt:** zugeordnete Dokumente zusammenführen, Aussagen belegen und offene Fragen kenntlich machen
- **Sitzung:** Ergebnisse einzelner TOPs zu einer nachvollziehbaren Sitzungsübersicht verdichten

Analyseartefakte sollen Eingabekontext, verwendete Dokumente und Hashes, Prompt-Version, Provider und Modell sowie Parameter und Zeitstempel festhalten. Markdown und strukturiertes JSON sollen Quellenangaben und sichtbare Unsicherheit unterstützen. Draft- und Review-Status sollen unterscheidbar bleiben.

### 3.5 Oberfläche und Anwendungsworkflows

- Django-Anwendungen unter `web/` entlang fachlicher Zuständigkeiten modular weiterentwickeln
- Dokumentauswahl, Analyse, Quellenprüfung und Review als zusammenhängenden Arbeitsablauf gestalten
- Bestehende Fetch-, Build-, Such- und Analysefunktionen über stabile Service-Schnittstellen einbinden

### 3.6 Betrieb und Qualität (schichtübergreifend)

- Logging, Monitoring und Fehlerdiagnose schichtübergreifend vereinheitlichen
- Testabdeckung für Datenpipeline, Analyseflüsse und Suchpfade erweitern
- Dokumentation regelmäßig gegen Implementierung, Datenformate und tatsächliche Abläufe prüfen
- Aufgabenliste nach Architektur- oder Funktionsänderungen aktualisieren und erledigte Punkte entfernen

## 4. Abhängigkeiten und sinnvolle Reihenfolge

1. Datenverträge und Metadaten zwischen Fetching, SQLite-Builds und Extraktion stabilisieren.
2. Extraktion, OCR und Suchindex mit Fortschritt, Fehlerdiagnose und Regressionstests absichern.
3. Analyseartefakte und Quellenverweise konsistent versionieren.
4. Dokumentzentrierten Analyse- und Review-Ablauf darauf aufbauend in der Oberfläche vervollständigen.
5. Recherchequalität mit erweitertem Katalog messen und die Dokumentation nachführen.
