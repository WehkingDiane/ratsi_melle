# Ratsinformations-Analysetool Melle

## Projektvision
Das Ziel dieses Projekts bleibt unverändert: **Kommunalpolitische Informationen aus dem Ratsinformationssystem der Stadt Melle automatisch einsammeln, analysieren und verständlich aufbereiten.** Vergangene Sitzungen sollen journalistisch zusammengefasst und kommende Sitzungen strukturiert vorbereitet werden, damit Politik, Verwaltung und Öffentlichkeit einen schnellen, transparenten Überblick erhalten.

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

## Taskliste auf dem Weg zum Ziel
1. **Grundlagen schaffen**
   - ✅ Projektstruktur und Repository-Regeln sind in `docs/repository_guidelines.md` dokumentiert.
   - ✅ Erste Prüfung von Anforderungen, Datenschutz- und Nutzungsbedingungen inklusive weiterer To-dos in `docs/data_access_review.md` festgehalten.
2. **Datenerfassung konzipieren und implementieren**
   - Zielseiten analysieren (HTML-Strukturen, Pagination, Detail-Links).
   - Crawler/Fetch-Logik umsetzen, inklusive Fehlerbehandlung und Tests mit Beispielterminen.
   - Strategie zur Speicherung der Rohdaten definieren.
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
