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

## Softwareversion

- Aktuelle Projektversion: `0.1.0`
- Versionsstrategie: `docs/software_versioning.md`

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

- `data/raw/<Jahr>/<Monat>/<Datum>_<Gremium>_<Sitzungs-ID>/` bildet den Sitzungsordner. Beispiel: `data/raw/2025/10/2025-10-08_Rat-der-Stadt-Melle_6770/`.
- Jeder Sitzungsordner enthält:
  - `session_detail.html` als unveränderte Detailseite.
  - `session-documents/` für Bekanntmachungen, Protokolle etc., die auf Sitzungsebene veröffentlicht werden.
  - `agenda/<TOP-Nummer>_<Kurzname>/` mit den Dokumenten je Tagesordnungspunkt (Suffixe wie „Berichterstatter …“ werden beim Ordnernamen entfernt).
  - `manifest.json` mit Pfad, URL, Titel, Kategorie, TOP-Zuordnung, SHA1-Hash sowie HTTP-Metadaten (`content_type`, `content_disposition`, `content_length`) sämtlicher Dateien.
  - `agenda_summary.json` mit einer Liste aller TOPs inkl. Reporter:in, Roh-Status aus SessionNet sowie einem abgeleiteten Entscheidungsfeld (`accepted`, `rejected`, `null`) und einem Flag, ob bereits Dokumente vorliegen.
- Monatsübersichten werden als `data/raw/<Jahr>/<Monat>/<Jahr>-<Monat>_overview.html` gespeichert.
- Die tatsächlichen Dateien liegen zwar im Repository-Verzeichnis, werden aber per `.gitignore` von Commits ausgeschlossen, damit lokale Crawls das Repo nicht aufblähen.
- Downloads werden pro Prozesslauf gecacht und durch eine einstellbare Rate-Limit-/Retry-Logik (Default: 1 Anfrage/Sekunde, exponentieller Backoff) automatisch gedrosselt. Damit werden identische Dokument-URLs innerhalb eines Runs nur einmal vom Ratsinformationssystem geholt.
- Für zukünftige Sitzungen fehlen erfahrungsgemäß Status, Dokumente oder Reporter:innen-Angaben – `agenda_summary.json` kennzeichnet solche Fälle durch `decision = null` bzw. `documents_present = false`, bis ein erneuter Crawl die Angaben nachliefert.

## Taskliste auf dem Weg zum Ziel

1. **Grundlagen schaffen**
   - ✅ Projektstruktur und Repository-Regeln sind in `docs/repository_guidelines.md` dokumentiert.
   - ✅ Erste Prüfung von Anforderungen, Datenschutz- und Nutzungsbedingungen inklusive weiterer To-dos in `docs/data_access_review.md` festgehalten.
   - ✅ Softwareversionierung eingeführt.
     - ✅ Ein konsistentes Schema nach `Major.Minor.Patch` ist festgelegt und dokumentiert (`VERSION`, `docs/software_versioning.md`).
     - ✅ Für die Entwicklungsphase ist eine Vor-1.0-Strategie definiert; aktuelle Basisversion ist `0.1.0`.
2. **Datenerfassung konzipieren und implementieren**
   - ✅ **Quellen und Strukturen erfassen:** Regelmäßige Übersichts-, Detail- und Downloadseiten identifizieren, Navigations- und Paginationspfade festhalten sowie Parameter (z. B. Zeitraum, Gremium, Dokumenttyp) und wiederkehrende HTML-Elemente dokumentieren.
   - ✅ **Abruflogik konzipieren:** Datenflüsse, Fehlerfälle und Wiederholungsstrategien modellieren, inklusive Zeitplanung für Abrufe, Latenzanforderungen und Grenzen der Zielsysteme.
   - ✅ **Abrufkomponente implementieren:** Skript- oder Service-Module entwickeln, die Termine und Dokumente laden, Netzwerkfehler protokollieren, Wiederholungen auslösen und anhand repräsentativer Testfälle mit Mock- oder Live-Daten verifiziert werden.
     - ✅ `fetch_sessions.py` bzw. `sessionnet_client.py` führen einen Änderungsabgleich durch, damit nur neue oder aktualisierte Dateien erneut heruntergeladen werden.
     - ✅ Vorhandene Dateien werden vor dem Download verglichen; identische Dateien werden übersprungen, um Netzwerk- und Speicherressourcen zu sparen.
   - ✅ **Speicherkonzept ausarbeiten:** Dateiformate, Verzeichnis- bzw. Datenbankschemata, Versionierung sowie Aufbewahrungsfristen der Rohdaten definieren und in einem Architektur- oder Betriebshandbuch dokumentieren.
     - ✅ Ablagestruktur unter `data/raw/YYYY/MM/` um einen zusätzlichen Monats-Unterordner erweitert.
     - ✅ Bestehende Rohdaten werden bei Nutzung des Fetch-Clients einmalig in die neue Monatsstruktur migriert.

3. **Dokumentenverarbeitung ausbauen**
   - ✅ Parser für priorisierte Dokumenttypen entwickeln (Vorlage, Beschlussvorlage, Protokoll-Auszug).
     - ✅ Relevante Inhalte je Dokumenttyp werden als strukturierte Felder extrahiert (`beschlusstext`, `begruendung`, `finanzbezug`, `zustaendigkeit`, `entscheidung`).
     - ✅ Parser-Ausgaben sind mit Fixtures pro Dokumenttyp abgesichert (`tests/fixtures/` + Edge-Cases).
   - ✅ Normalisierte Datenstruktur mit Metadaten entwerfen und implementieren.
     - ✅ Einheitliches Schema für zentrale Filterfelder ist umgesetzt (`session_id`, `date`, `committee`, `document_type`, `top_number`; `status` aktuell über `agenda_items`).
     - ✅ Felder für Analyse-Übergabe sind standardisiert (Quell-URL, lokaler Pfad, Hash, Extraktionszeitpunkt, Extraktions- und Parser-Qualität).
   - ✅ Analyse-Export liefert strukturierte Dokumentkontexte für priorisierte Typen.
     - ✅ `scripts/export_analysis_batch.py` kann Text-Extraktion und `structured_fields` für Analyse-Batches ausgeben.
     - ✅ Der Analyse-Workflow in der GUI nutzt strukturierte Dokumentfelder als Kontext im generierten Markdown.
   - ✅ Erweiterte PDF-Robustheit für Analyse-Export weiter ausgebaut.
     - ✅ Basis-Extraktion und Qualitätskennzeichnung (inkl. OCR-Hinweis) sind vorhanden.
     - ✅ Seitenbezogene PDF-Texte und Abschnittsanker werden in der Extraktionspipeline erkannt und fuer Export/Analyse bereitgestellt.
     - 🚧 Vollwertiger OCR-Workflow fuer gescannte/problematische PDFs bleibt als nachgelagerte Betriebsarbeit offen.
   - ✅ Metadaten-Mapping für spätere Suche/Filterung konkretisiert.
     - ✅ Filterlogik für UI ist vorbereitet: Zeitraum-Presets, vergangen/heute/kommend, Gremium, Sitzungsstatus.
     - ✅ Exportformat für Analyse-Batches ist definiert, damit ausgewählte Sitzungen reproduzierbar weitergegeben werden können.
4. **Analysemodul entwickeln**
   - 🚧 Analyseziele, Qualitätskriterien und Ausgabeformate festlegen.
   - 🚧 Mehrere Analysemodi für Dokumente, TOPs und ganze Sitzungen unterstützen.
   - 🚧 KI- und regelbasierte Verfahren kombinierbar machen und über austauschbare Schnittstellen anbinden.
   - 🚧 Reproduzierbarkeit, Quellenbezug und menschliche Nachprüfung sicherstellen.
   - Details und Ausbaupfade stehen in `README_TASK4.md`.
5. **Benutzerzugang gestalten**
   - 🚧 **Developer-GUI weiterentwickeln**
     - 🚧 Anforderungen an die interne Developer-GUI definieren (Arbeitsabläufe, Eingabefelder, Schnellaktionen, Exportpfade).
     - 🚧 Prototypen und Verbesserungen für die Developer-GUI mit Testdaten umsetzen und iterativ schärfen.
     - 🚧 In der GUI-Action-Ansicht `Export Analysis` ein Dropdown für `Committee` statt eines reinen Texteingabefelds ergänzen.
     - 🚧 In der GUI Eingabeelemente ausblenden, die für die aktuell ausgewählte Action nicht benötigt werden.
   - 🚧 **Finale User-Oberfläche konzipieren und ausbauen**
     - 🚧 Anforderungen an UI oder API für Endnutzer definieren (Zielgruppen, Filter, Exportformate).
     - 🚧 Prototyp für Darstellung/Interaktion der finalen User-Oberfläche umsetzen und mit Testdaten befüllen.
     - 🚧 Anforderungen, Navigation und Darstellung für eine Endnutzer-Oberfläche von der Developer-GUI abgrenzen.
     - 🚧 In der finalen Oberfläche einen PDF-Viewer für Dokumente integrieren.
6. **Betrieb & Qualitätssicherung sicherstellen**
   - Logging, Monitoring und Alarmierung einrichten.
   - Automatisierung (Zeitpläne, Deployments) definieren und testen.
   - Dokumentation, Tests und Onboarding-Unterlagen pflegen.
   - 🚧 Verbesserte Download-Strategie ergänzen: optionaler inkrementeller Modus, der nur fehlende oder geänderte Dokumente lädt statt Sitzungsordner pro Lauf vollständig neu aufzubauen (Abgleich über URL/Hash/Metadaten).
7. **Evaluation & Erweiterung**
   - Feedback von Pilotnutzer:innen einholen und Verbesserungen priorisieren.
   - Erweiterungen für zusätzliche Kommunen, Visualisierungen oder Schnittstellen planen.
8. **Wartung, Tests & Up-to-date-Prüfung**
   - Regelmäßig automatisierte Tests ausführen und erweitern (Parser, Index, GUI-nahe Kernflüsse).
   - Python-Abhängigkeiten sowie Build-/Dev-Tools auf aktuelle, kompatible Versionen prüfen und aktualisieren.
   - In festem Rhythmus prüfen, ob sich SessionNet/Ratsinformationssystem (HTML-Struktur, Parameter, Endpunkte, Dokumenttypen) geändert hat.
   - Bei Änderungen am Ratsinformationssystem Parser und Mapping zeitnah anpassen und durch Fixtures/Regressionstests absichern.

Diese Taskliste kann iterativ abgearbeitet werden. Ergebnisse und Learnings jedes Schritts sollten dokumentiert werden, um spätere Anpassungen zu erleichtern und Transparenz gegenüber allen Stakeholdern zu gewährleisten.
