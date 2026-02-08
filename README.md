# Ratsinformations-Analysetool Melle

## Projektvision

Das Ziel dieses Projekts bleibt unverändert: **Kommunalpolitische Informationen aus dem Ratsinformationssystem der Stadt Melle automatisch einsammeln, analysieren und verständlich aufbereiten.** Vergangene Sitzungen sollen journalistisch zusammengefasst und kommende Sitzungen strukturiert vorbereitet werden um einen Überblick zuerhalten.

## Leitprinzipien für die Umsetzung

- **Technologieoffenheit:** Programmiersprache, Frameworks und Infrastruktur sind frei wählbar. Bewährt haben sich Skriptsprachen (z. B. Python, JavaScript/TypeScript) ebenso wie kompilierte Sprachen (z. B. Go, Rust), solange sie Webzugriffe, Datenhaltung und optionale KI-Anbindungen unterstützen.
- **Modularer Aufbau:** Funktionen wie Datenerfassung, Analyse, Speicherung und Darstellung sollen klar getrennt sein, damit einzelne Module unabhängig weiterentwickelt oder ausgetauscht werden können.
- **Nachvollziehbarkeit & Transparenz:** Alle gewonnenen Daten, Zwischenschritte und Analyseergebnisse müssen dauerhaft nachvollziehbar, versionierbar und für Dritte überprüfbar sein.
- **Erweiterbarkeit:** Die Lösung soll sich leicht auf andere Kommunen oder Informationsquellen übertragen lassen und Platz für zusätzliche Auswertungen oder Visualisierungen bieten.

## Voraussetzungen (lokale Entwicklung)

- **Python 3.11+** für die Skripte und Tests.
- **pip** für die Paketinstallation (`pip install -r requirements.txt`).
- **Git** für Versionskontrolle und Mitarbeit.
- **(Optional) Tkinter** für eine spätere UI; unter WSL via `sudo apt-get install python3-tk`.
- **Projektstruktur** siehe `docs/repository_guidelines.md`.

## Wichtige Skripte

- `python scripts/fetch_sessions.py 2024 --months 5 6` laedt Sitzungen und Dokumente nach `data/raw/`.
- `python scripts/build_local_index.py` baut den lokalen SQLite-Index unter `data/processed/local_index.sqlite`.
- `python scripts/build_online_index_db.py 2024 --months 5 6` baut den Online-Index unter `data/processed/online_session_index.sqlite` ohne Downloads.
- `python scripts/export_analysis_batch.py --db-path data/processed/local_index.sqlite --output data/processed/analysis_batch.json` exportiert einen reproduzierbaren Analyse-Batch (optional filterbar nach Sitzung, Zeitraum, Gremium, `document_type`).

## GUI (modular)

- Einstiegspunkt: `python -m src.interfaces.gui.gui_launcher`
- Architektur und Erweiterungshinweise: `docs/gui.md`
- GUI-Quellcode liegt unter `src/interfaces/gui/` und ist in `app.py`, `views/`, `services/` und `config.py` aufgeteilt.

## Zeilenenden (Windows/Linux)

- Das Repository nutzt fuer Quell- und Konfigurationsdateien konsistent `LF` (verwaltet ueber `.gitattributes` und `.editorconfig`).
- Windows-native Skripte (`*.bat`, `*.cmd`, `*.ps1`) bleiben `CRLF`.
- Dadurch funktioniert die Zusammenarbeit zwischen Windows- und Linux-Umgebungen ohne unnötige Diff-Rauschen.

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
  - `agenda/<TOP-Nummer>_<Kurzname>/` mit den Dokumenten je Tagesordnungspunkt (Suffixe wie „Berichterstatter …“ werden beim Ordnernamen entfernt).
  - `manifest.json` mit Pfad, URL, Titel, Kategorie, TOP-Zuordnung, SHA1-Hash sowie HTTP-Metadaten (`content_type`, `content_disposition`, `content_length`) sämtlicher Dateien.
  - `agenda_summary.json` mit einer Liste aller TOPs inkl. Reporter:in, Roh-Status aus SessionNet sowie einem abgeleiteten Entscheidungsfeld (`accepted`, `rejected`, `null`) und einem Flag, ob bereits Dokumente vorliegen.
- Monatsübersichten werden als `data/raw/<Jahr>/<Jahr>-<Monat>_overview.html` gespeichert.
- Die tatsächlichen Dateien liegen zwar im Repository-Verzeichnis, werden aber per `.gitignore` von Commits ausgeschlossen, damit lokale Crawls das Repo nicht aufblähen.
- Downloads werden pro Prozesslauf gecacht und durch eine einstellbare Rate-Limit-/Retry-Logik (Default: 1 Anfrage/Sekunde, exponentieller Backoff) automatisch gedrosselt. Damit werden identische Dokument-URLs innerhalb eines Runs nur einmal vom Ratsinformationssystem geholt.
- Für zukünftige Sitzungen fehlen erfahrungsgemäß Status, Dokumente oder Reporter:innen-Angaben – `agenda_summary.json` kennzeichnet solche Fälle durch `decision = null` bzw. `documents_present = false`, bis ein erneuter Crawl die Angaben nachliefert.

## Taskliste auf dem Weg zum Ziel

1. **Grundlagen schaffen**
   - ✅ Projektstruktur und Repository-Regeln sind in `docs/repository_guidelines.md` dokumentiert.
   - ✅ Erste Prüfung von Anforderungen, Datenschutz- und Nutzungsbedingungen inklusive weiterer To-dos in `docs/data_access_review.md` festgehalten.
2. **Datenerfassung konzipieren und implementieren**
   - ✅ **Quellen und Strukturen erfassen:** Regelmäßige Übersichts-, Detail- und Downloadseiten identifizieren, Navigations- und Paginationspfade festhalten sowie Parameter (z. B. Zeitraum, Gremium, Dokumenttyp) und wiederkehrende HTML-Elemente dokumentieren.
   - ✅ **Abruflogik konzipieren:** Datenflüsse, Fehlerfälle und Wiederholungsstrategien modellieren, inklusive Zeitplanung für Abrufe, Latenzanforderungen und Grenzen der Zielsysteme.
   - ✅ **Abrufkomponente implementieren:** Skript- oder Service-Module entwickeln, die Termine und Dokumente laden, Netzwerkfehler protokollieren, Wiederholungen auslösen und anhand repräsentativer Testfälle mit Mock- oder Live-Daten verifiziert werden.
   - ✅ **Speicherkonzept ausarbeiten:** Dateiformate, Verzeichnis- bzw. Datenbankschemata, Versionierung sowie Aufbewahrungsfristen der Rohdaten definieren und in einem Architektur- oder Betriebshandbuch dokumentieren.

3. **Dokumentenverarbeitung ausbauen**
   - Parser für Vorlagen und Beschlüsse entwickeln (HTML, PDF, ggf. weitere Formate).
     - Relevante Inhalte je Dokumenttyp extrahieren (Beschlusstext, Begründung, Finanzbezug, Zuständigkeit).
     - Parser-Ausgaben mit Fixtures pro Dokumenttyp absichern (`tests/fixtures/` + Edge-Cases).
   - Normalisierte Datenstruktur mit Metadaten entwerfen und implementieren.
     - Einheitliches Schema für Filterfelder definieren (`session_id`, `date`, `committee`, `status`, `document_type`, `top_number`).
     - Felder für Analyse-Übergabe standardisieren (Quell-URL, lokaler Pfad, Hash, Extraktionszeitpunkt, Parsing-Qualität).
   - 🚧 HTML-Parser für weitere Dokumenttypen und Beschlüsse ergänzen.
     - Priorität auf häufige und politisch relevante Typen setzen (Vorlage, Beschlussvorlage, Niederschrift-Auszug).
     - Fallback-Regeln für variierende SessionNet-Layouts ergänzen und dokumentieren.
   - 🚧 PDF-Extraktion/Normalisierung definieren (z. B. Textextraktion, Seitenstruktur).
     - Entscheidung für Extraktionspipeline treffen (reiner Text vs. strukturierte Blöcke pro Seite/Abschnitt).
     - Qualitätskriterien und Fehlerkennzeichnung festlegen (z. B. OCR nötig, unlesbar, unvollständig).
   - 🚧 Metadaten-Mapping für spätere Suche/Filterung konkretisieren.
     - Filterlogik für UI vorbereiten: Zeitraum-Presets, vergangen/kommend, Gremium, Sitzungsstatus.
     - Exportformat für Analyse-Batches definieren, damit ausgewählte Sitzungen reproduzierbar weitergegeben werden können.
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
8. **Wartung, Tests & Up-to-date-Prüfung**
   - Regelmäßig automatisierte Tests ausführen und erweitern (Parser, Index, GUI-nahe Kernflüsse).
   - Python-Abhängigkeiten sowie Build-/Dev-Tools auf aktuelle, kompatible Versionen prüfen und aktualisieren.
   - In festem Rhythmus prüfen, ob sich SessionNet/Ratsinformationssystem (HTML-Struktur, Parameter, Endpunkte, Dokumenttypen) geändert hat.
   - Bei Änderungen am Ratsinformationssystem Parser und Mapping zeitnah anpassen und durch Fixtures/Regressionstests absichern.

Diese Taskliste kann iterativ abgearbeitet werden. Ergebnisse und Learnings jedes Schritts sollten dokumentiert werden, um spätere Anpassungen zu erleichtern und Transparenz gegenüber allen Stakeholdern zu gewährleisten.
