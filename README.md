# Ratsinformations-Analysetool Melle

## Projektvision
Das Ziel dieses Projekts bleibt unverändert: **Kommunalpolitische Informationen aus dem Ratsinformationssystem der Stadt Melle automatisch einsammeln, analysieren und verständlich aufbereiten.** Vergangene Sitzungen sollen journalistisch zusammengefasst und kommende Sitzungen strukturiert vorbereitet werden um einen Überblick zuerhalten.

## Leitprinzipien für die Umsetzung
- **Technologieoffenheit:** Programmiersprache, Frameworks und Infrastruktur sind frei wählbar. Bewährt haben sich Skriptsprachen (z. B. Python, JavaScript/TypeScript) ebenso wie kompilierte Sprachen (z. B. Go, Rust), solange sie Webzugriffe, Datenhaltung und optionale KI-Anbindungen unterstützen.
- **Modularer Aufbau:** Funktionen wie Datenerfassung, Analyse, Speicherung und Darstellung sollen klar getrennt sein, damit einzelne Module unabhängig weiterentwickelt oder ausgetauscht werden können.
- **Nachvollziehbarkeit & Transparenz:** Alle gewonnenen Daten, Zwischenschritte und Analyseergebnisse müssen dauerhaft nachvollziehbar, versionierbar und für Dritte überprüfbar sein.
- **Erweiterbarkeit:** Die Lösung soll sich leicht auf andere Kommunen oder Informationsquellen übertragen lassen und Platz für zusätzliche Auswertungen oder Visualisierungen bieten.

## Kernfunktionen (geplant)
1. **Datengewinnung aus dem Ratsinformationssystem**
   - Regelmäßiger Abruf von Sitzungsterminen samt Metadaten (Gremium, Datum, Links).
   - Sammeln der zugehörigen Vorlagen, Beschlussdokumente und Protokolle.
2. **Dokumentenaufbereitung**
   - Normalisieren von Dateiformaten (HTML, PDF, Text) und Extrahieren relevanter Inhalte.
   - Strukturierte Ablage in einer revisionssicheren Ordner- oder Datenbankstruktur.
3. **Analyse & Zusammenfassung**
   - Einbindung eines Analysemoduls (z. B. regelbasiert oder KI-gestützt), das Texte bewertet, verdichtet und thematisch einordnet.
   - Ausgabe verständlicher Kurzfassungen, Schlagworte und möglicher Auswirkungen.
4. **Darstellung & Zugriff**
   - Benutzeroberfläche oder API für Recherche, Filterung und Export der Daten.
   - Optionale Dashboards für Trends, Themencluster oder Zeitleisten.
5. **Qualitätssicherung & Betrieb**
   - Logging, Monitoring und Fehlerbehandlung für stabile Abläufe.
   - Werkzeuge zum Aufräumen veralteter Daten und zum Planen automatischer Läufe.

## Mögliche Architekturbausteine
- **Crawler- oder Fetch-Komponente:** Holt Termine und Dokumente. Umsetzung möglich als CLI-Skript, Serverless-Funktion oder Microservice.
- **Speicherschicht:** Wahlweise Dateien, relationale Datenbank, Dokumentenspeicher oder Data Lake – je nach Skalierungsbedarf.
- **Analyse-Service:** Kann lokal laufen (Open-Source-Modelle) oder über externe KI-APIs angebunden werden. Schnittstellen sollten austauschbar gestaltet sein.
- **Darstellungs-Frontend:** Web-Anwendung (z. B. React, Vue, Svelte, Streamlit, Django, Flask, FastAPI, Next.js) oder native App. Auch reine API-Ausgaben sind möglich, wenn andere Systeme die Visualisierung übernehmen.
- **Automatisierung:** Zeitgesteuerte Jobs (Cron, Cloud Scheduler, GitHub Actions) oder Event-Trigger, die neue Sitzungen und Analysen anstoßen.

## Datenhaltung & Transparenz
- Alle Eingänge (Rohdaten, Metadaten, Analyseergebnisse) sollten versioniert werden, z. B. über Git, Datenbankrevisionen oder unveränderbare Log-Dateien.
- Verlinkungen auf Originaldokumente erleichtern die Überprüfung.
- Klare Namenskonventionen und Metadaten helfen bei der späteren Suche nach Sitzungen, Gremien oder Themenfeldern.

## Rohdatenablage
- `data/raw/<Jahr>/<Datum>_<Gremium>_<Sitzungs-ID>/` bildet den Sitzungsordner. Beispiel: `data/raw/2025/2025-10-08_Rat-der-Stadt-Melle_6770/`.
- Jeder Sitzungsordner enthält:
  - `session_detail.html` als unveränderte Detailseite.
  - `session-documents/` für Bekanntmachungen, Protokolle etc., die auf Sitzungsebene veröffentlicht werden.
  - `agenda/<TOP-Nummer>_<Kurzname>/` mit den Dokumenten je Tagesordnungspunkt.
  - `manifest.json` mit Pfad, URL, Titel, Kategorie, TOP-Zuordnung und SHA1-Hash sämtlicher Dateien.
- Monatsübersichten werden als `data/raw/<Jahr>/<Jahr>-<Monat>_overview.html` gespeichert.
- Die tatsächlichen Dateien liegen zwar im Repository-Verzeichnis, werden aber per `.gitignore` von Commits ausgeschlossen, damit lokale Crawls das Repo nicht aufblähen.

## Taskliste auf dem Weg zum Ziel
1. **Grundlagen schaffen**
   - ✅ Projektstruktur und Repository-Regeln sind in `docs/repository_guidelines.md` dokumentiert.
   - ✅ Erste Prüfung von Anforderungen, Datenschutz- und Nutzungsbedingungen inklusive weiterer To-dos in `docs/data_access_review.md` festgehalten.
2. **Datenerfassung konzipieren und implementieren**
   - **Quellen und Strukturen erfassen:** Regelmäßige Übersichts-, Detail- und Downloadseiten identifizieren, Navigations- und Paginationspfade festhalten sowie Parameter (z. B. Zeitraum, Gremium, Dokumenttyp) und wiederkehrende HTML-Elemente dokumentieren.
   - **Abruflogik konzipieren:** Datenflüsse, Fehlerfälle und Wiederholungsstrategien modellieren, inklusive Zeitplanung für Abrufe, Latenzanforderungen und Grenzen der Zielsysteme.
   - **Abrufkomponente implementieren:** Skript- oder Service-Module entwickeln, die Termine und Dokumente laden, Netzwerkfehler protokollieren, Wiederholungen auslösen und anhand repräsentativer Testfälle mit Mock- oder Live-Daten verifiziert werden.
   - **Speicherkonzept ausarbeiten:** Dateiformate, Verzeichnis- bzw. Datenbankschemata, Versionierung sowie Aufbewahrungsfristen der Rohdaten definieren und in einem Architektur- oder Betriebshandbuch dokumentieren.

   **Stand Task 2 (aktuell):**

   - Die recherchierten Seiten und Parameter sind in `docs/data_fetching_concept.md` dokumentiert.
   - Der `SessionNetClient` unter `src/fetching/` lädt Monatsübersichten, Sitzungsdetails und verknüpfte Dokumente und legt Rohdaten unter `data/raw/` ab.
   - Das CLI-Skript `scripts/fetch_sessions.py` kapselt die Abruflogik. Beispielaufruf: `python scripts/fetch_sessions.py 2024 --months 5 6`.
3. **Dokumentenverarbeitung ausbauen**
   - Parser für Vorlagen und Beschlüsse entwickeln (HTML, PDF, ggf. weitere Formate).
   - Normalisierte Datenstruktur mit Metadaten entwerfen und implementieren.
4. **Analysemodul entwickeln**
   - Kriterien für Zusammenfassungen, Tonalität und Bewertung festlegen.
   - KI- oder regelbasierte Analyse integrieren; Schnittstellen so gestalten, dass verschiedene Modelle getestet werden können.
5. **Benutzerzugang gestalten**
   - Anforderungen an UI oder API definieren (Zielgruppen, Filter, Exportformate).
   - Prototyp für Darstellung/Interaktion umsetzen und mit Testdaten befüllen.
6. **Betrieb & Qualitätssicherung sicherstellen**
   - Logging, Monitoring und Alarmierung einrichten.
   - Automatisierung (Zeitpläne, Deployments) definieren und testen.
   - Dokumentation, Tests und Onboarding-Unterlagen pflegen.
7. **Evaluation & Erweiterung**
   - Feedback von Pilotnutzer:innen einholen und Verbesserungen priorisieren.
   - Erweiterungen für zusätzliche Kommunen, Visualisierungen oder Schnittstellen planen.

Diese Taskliste kann iterativ abgearbeitet werden. Ergebnisse und Learnings jedes Schritts sollten dokumentiert werden, um spätere Anpassungen zu erleichtern und Transparenz gegenüber allen Stakeholdern zu gewährleisten.
