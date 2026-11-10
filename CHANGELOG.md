# Changelog

Die neuesten Änderungen stehen oben. Einträge sind rückwirkend aus Git-Historie und vorhandener Dokumentation zusammengefasst; sie bilden keine vollständige Liste aller Commits. Versionsdaten bezeichnen das Datum des zugehörigen Versionscommits, nicht einen gesondert belegten Veröffentlichungstermin. Commit-Kürzel ermöglichen die Prüfung mit `git show <kürzel>`. Der aktuelle Funktionsumfang steht im [Ist-Stand](docs/ist_stand.md).

## Unveröffentlicht

### Testdaten – 10.11.2026

- Namen und geschäftliche Kontaktangaben in der Windkraft-Testfixture durch Platzhalter ersetzt; Quellenhinweis entsprechend ergänzt.

### Entwicklungsworkflow – 10.11.2026

- Repository-Hooks an die aktuelle Aufgabenstruktur angepasst; gestagte Versionsänderungen auf Format, Steigerung und passenden Changelog-Abschnitt geprüft. Changelog als Dokumentation anerkannt.

### Dokumentation – 10.11.2026

- Vorläufigen RI-Umfang als temporären Arbeitsbestand ohne Volltext-/Vektorindexierung festgehalten; Zeitgrenzen, Nachlauf, Bereinigung und Verwaltungsausschuss-Stichprobe als offene Entscheidungen dokumentiert.

- Veraltete Verweise und Statusformulierungen bei einer Nachprüfung der Markdown-Dateien korrigiert; Live- und PDF-Belastungstest-Aufrufe in der Testdokumentation ergänzt.

- Dokumentation nach Funktionen in Unterordner gegliedert und einen zentralen [Wegweiser](docs/README.md) angelegt (`1adfd81`).
- README und Ist-Stand gekürzt; Glossar, Betriebshilfen und Changelog ergänzt.
- Agentenregeln auf die neue Dokumentationsstruktur abgestimmt und veraltete Hinweise korrigiert (`a23d853`).
- Ältere Änderungen als Stichpunkte nachgetragen und absteigend geordnet. Die Anwendungsversion bleibt bei 0.5.76.
- Versionsregeln präzisiert: Versionen pro Änderungspaket, Minor für größere Funktionsausbauten, kein Versionswechsel für reine Dokumentationsänderungen. Historische Nummern bleiben erhalten.

## 0.6.0 – 10.11.2026

- RI-Token aus der lokalen Datei `.env/ri_token.txt` lesen; gesamter Ordner von Git ausgeschlossen. Die unverschlüsselte Datei ersetzt die bisherige RI-Tokenablage im Betriebssystemspeicher.
- Proton- und RI-Check verwenden temporäre CLI-Dateisitzungen ohne Keyring-Passwort. Windows-CLI auch am offiziellen Benutzer-Installationsort finden.
- Separate Eintragsbindung und `--configure` abgelöst; vor jedem Passwortabruf genau einen freigegebenen Tresor mit genau einem aktiven Login prüfen.
- Alte RI-Speicherhilfen und ihre Tests nach bytegleicher lokaler Archivierung entfernt. Vorhandene OS-Geheimnisse und Referenzdateien bleiben unverändert und werden nicht mehr verwendet.
- Anleitung und RI-Plan angepasst; synthetische Checks bestehen, echte Abnahme des Dateiflusses unter Windows und WSL steht aus.

## 0.5.76 – 2026-11-06

- Beobachtete RI-Anmeldeschritte berücksichtigt und echten RI-Zugriff unter Windows und WSL bestätigt. (`1272464`).
- RI-Dokumentabruf, Datenhaltung, Index und geschützter Webzugang bleiben ausstehend. Unter Windows bleibt ein Hinweis zur nachfolgenden Proton-Abmeldung; die RI-Abmeldung ist bestätigt.

## 0.5.75 – 2026-11-06

- RI-Zugang an einen freigegebenen Tresor-/Eintragsverweis gebunden und manuellen RI-Anmeldetest ohne Downloads ergänzt. (`96cd3e4`).

## 0.5.74 – 2026-11-06

- Proton-Einrichtungsskripte unter `scripts/setup/` gebündelt. (`1d08ff6`).

## 0.5.73 – 2026-11-06

- Sichtbare Tresore angezeigt und nur lokal bestätigte Proton-Abmeldung gekennzeichnet. (`74dc89d`).

## 0.5.72 – 2026-11-06

- RI-Proton-Anmeldung in einer eigenen temporären CLI-Sitzung geprüft. (`8613af6`).

## 0.5.71 – 2026-11-06

- Verdeckte Ablage und Ersetzung des RI-Proton-Tokens im expliziten Betriebssystem-Schlüsselspeicher ergänzt. (`4e9aacd`).

## 0.5.70 – 2026-11-06

- Diagnose des RI-Schlüsselspeichers und Übernahme des Steuerpfads verbessert. (`ebc5aa3`).

## 0.5.69 – 2026-11-06

- Geführte lokale Prüfung des RI-Schlüsselspeichers für Windows und WSL eingeführt. (`97d35ad`).

## 0.5.68 – 2026-11-03

- Dokumentabdeckung im Vektorstatus angezeigt; Statuszahlen separat speicherbar gemacht. (`916ceb3`).
- Leere SQLite-WAL-Dateien bei der Statusgültigkeit wie fehlende WAL-Dateien behandelt (`74a2277`).

## 0.5.67 – 2026-11-03

- Weiterverwendung des geprüften Ratsinfo-Index mit zwei akzeptierten Modellverträgen ermöglicht. (`59a6a51`).
- Windows-Modellbibliotheken und Torch-Version festgelegt; Modellablage vereinheitlicht (`7a37e01`, `b1371c2`).

## 0.5.66 – 2026-11-03

- Bibliothekswechsel anhand einer unveränderten Indexstichprobe geprüft; Diagnosewerkzeuge später wieder entfernt. (`97ef020`).

## 0.5.65 – 2026-10-30

- Abweichende Gremienschreibweisen im Sitzungsfilter zusammengeführt. (`1d6f88c`).

## 0.5.64 – 2026-10-30

- Bereichsnavigation und informative RI-Platzhalter eingeführt. (`ac5fa17`).

## 0.5.63 – 2026-10-30

- Öffentliche SessionNet-Skripte nach der BI-Namenskonvention umbenannt. (`2a9862c`).
- Eigene Automatisierungen müssen die neuen Namen verwenden; gespeicherte Job-Aktionskennungen bleiben erhalten. Landkreis-Skripte und gemeinsame Werkzeuge behalten ihre Namen.

| Bisher | Neu |
| --- | --- |
| `fetch_sessions.py` | `fetch_bi_sessions.py` |
| `fetch_session_from_index.py` | `fetch_bi_session_from_index.py` |
| `build_online_index_db.py` | `build_bi_online_index_db.py` |
| `build_local_index.py` | `build_bi_local_index.py` |
| `build_vector_index.py` | `build_bi_vector_index.py` |
| `check_vector_index.py` | `check_bi_vector_index.py` |
| `update_vector_index.py` | `update_bi_vector_index.py` |
| `evaluate_search.py` | `evaluate_bi_search.py` |


## 0.5.62 – 2026-10-20

- Sitzungsdateien nach erkanntem Abschluss einmalig geprüft. (`aadb6a8`).

## 0.5.61 – 2026-10-20

- Abgeschlossene Sitzungsdateien wiederverwendet und Beschlusserkennung verbessert. (`d54c8b6`).

## 0.5.60 – 2026-10-20

- Wartungsjobs und Einstellungen im Service-Bereich gebündelt. (`df8f2e0`).

## 0.5.59 – 2026-10-20

- Normalen Vektoraufbau auf fehlende oder unvollständige Dokumente begrenzt. (`b2f70af`).

## 0.5.58 – 2026-10-20

- Gemeinsame Layout- und Rückmeldungsbausteine in den Arbeitsbereichen eingeführt. (`eeec05f`).

## 0.5.57 – 2026-10-20

- Abstände auf Vektor- und Jahresstatusseiten vereinheitlicht. (`8ddfd38`).

## 0.5.56 – 2026-10-20

- Vektoraufbau vor Statusanzeigen angeordnet und Abstände vereinheitlicht. (`86ec7b3`).

## 0.5.55 – 2026-10-16

- Desktop-Dashboard auf kommende und vergangene Sitzungstermine ausgerichtet. (`97b3822`).

## 0.5.54 – 2026-10-16

- Auch nur im Kalender angekündigte Sitzungen in den Online-Index aufgenommen. (`f0c13c3`).

## 0.5.53 – 2026-10-06

- Textextraktion für die Suche aus PDFs bis 128 MiB ermöglicht. (`4b460c4`).

## 0.5.52 – 2026-10-04

- Modellverwaltung mit dem UI-Branch zusammengeführt; Jahresstatus und kommende Dashboard-Termine aufgenommen. (`bbcdfd4`).
- Der parallele UI-Commit `aecdaf7` verwendete erneut 0.5.10. Seine Änderungen sind hier beim Zusammenführen dokumentiert; die ursprüngliche 0.5.10 bleibt dem 28.09.2026 zugeordnet.

## 0.5.51 – 2026-10-04

- Routinemäßige HTTP-Protokolle aus der Terminalausgabe entfernt. (`bdc82b1`).

## 0.5.50 – 2026-10-04

- Dense-Vektoren bestehender Indizes nach Kosinusnormalisierung verglichen. (`0f253b6`).

## 0.5.49 – 2026-10-04

- Offline-Abnahme der Modellverwaltung abgeschlossen und Downloadfehler erhalten. (`641f520`).

## 0.5.48 – 2026-10-02

- OCR-Verarbeitung gemischter Analyse-PDFs korrigiert. (`4257954`).

## 0.5.47 – 2026-10-02

- PDF-Extraktion korrigiert und Regressionen mit realitätsnahen PDF-Fixtures abgesichert. (`f26ceb0`).

## 0.5.46 – 2026-10-02

- Prozesskoordination und Wiederaufnahme nach Unterbrechungen vervollständigt. (`088022b`).

## 0.5.45 – 2026-10-02

- Gebundene Modelljob-Historie und Fortschrittsanzeige ergänzt. (`c47ead8`).

## 0.5.44 – 2026-10-02

- Bestätigte Übernahme von Altindizes mit gebundenen Berichtsprüfsummen und erneuter Prüfung unter Sperre ergänzt. (`149c3d1`).

## 0.5.43 – 2026-10-02

- Schreibfreie, an den Server gebundene Altindexprüfung und validierte Jobberichte ergänzt. (`59ef28a`).

## 0.5.42 – 2026-10-02

- Validierung der Parameter für Modellaktionen verschärft. (`3f3790b`).

## 0.5.41 – 2026-10-02

- Bestätigte Modellvorbereitung mit gemeinsamen Prozesssperren und dauerhaften Jobreservierungen eingeführt. (`1167a1e`).

## 0.5.40 – 2026-10-01

- Offline-Modellprüfung auf der Vektorseite ergänzt. (`0f3da8e`).

## 0.5.39 – 2026-10-01

- Status lokaler Embedding-Modelle auf der Vektorseite ergänzt. (`d54e02d`).

## 0.5.38 – 2026-10-01

- Geprüften lokalen Modellbestand im Datenservice-Status angezeigt. (`0b521f9`).

## 0.5.37 – 2026-10-01

- Ausgewählte Quelle in Migrationsvorprüfungen beibehalten. (`8ce651f`).

## 0.5.36 – 2026-10-01

- Altindexberichte an die Quelldatenbank gebunden; Neuaufbau für Landkreis-Indizes verlangt. (`93f4084`).

## 0.5.35 – 2026-10-01

- Zwischengespeicherte Suchfreigaben erneut geprüft und Migrationsausfälle behandelt. (`ceedebf`).

## 0.5.34 – 2026-09-30

- Collection-Aufbauten bis zur Veröffentlichung der Suchbereitschaft serialisiert. (`8e4e720`).

## 0.5.33 – 2026-09-30

- Präzision von Dense-Vektoren geprüft und Übertragungsfehler der Indexprüfung gemeldet. (`89b249f`).

## 0.5.32 – 2026-09-30

- Sparse-Vektoren und tatsächliche Collection-Schemata vor Freigaben validiert. (`5db162e`).

## 0.5.31 – 2026-09-30

- Erfassten Freigabestand vor zwischengespeicherten Suchzugriffen erneut geprüft. (`330cbee`).

## 0.5.30 – 2026-09-30

- Suchvalidierung zwischengespeichert und Textlimit für Landkreis-Dokumente festgelegt. (`d1dccc6`).

## 0.5.29 – 2026-09-30

- Lokale Migrationsspeicher abgesichert und Verbindungsfehler verständlich gemeldet. (`6e415db`).

## 0.5.28 – 2026-09-30

- Freigegebene Vektoren validiert und Fortsetzung ausstehender Builds ermöglicht. (`ec8b2e9`).

## 0.5.27 – 2026-09-30

- Freigabemarker an die Verträge der Qdrant-Punkte gebunden. (`d95ea6b`).

## 0.5.26 – 2026-09-30

- Weitere Review-Korrekturen zur Indexkompatibilität umgesetzt. (`48e591a`).

## 0.5.25 – 2026-09-30

- Kompatibilitätsprüfung in Suche und Indexaufbau durchgesetzt. (`76aa5fa`).

## 0.5.24 – 2026-09-30

- Unverträgliche Indexaufbauten mit verständlicher Meldung statt Traceback abgebrochen. (`d208ad5`).

## 0.5.23 – 2026-09-30

- Kompatibilität vor schreibenden Indexaufbauten geprüft. (`1812773`).

## 0.5.22 – 2026-09-30

- Freigabe geprüfter Altindizes mit Ergänzung fehlender Payload-Angaben ermöglicht. (`fb168af`).

## 0.5.21 – 2026-09-30

- Prüfbericht und Abbruchgründe für bestehende Indizes definiert. (`d134d93`).

## 0.5.20 – 2026-09-29

- Schreibfreie Prüfung bestehender Vektorindizes ergänzt. (`257b97d`).

## 0.5.19 – 2026-09-29

- Kompatibilitätsangaben in Vektor-Payloads aufgenommen. (`4ef1146`).

## 0.5.18 – 2026-09-29

- Modell- und Indexkompatibilität in Qdrant-Freigabemarkern erfasst. (`5a917cf`).

## 0.5.17 – 2026-09-29

- Meldungen zu nicht verfügbaren lokalen Modellen ergänzt. (`1162dcd`).

## 0.5.16 – 2026-09-28

- Fehler durch symbolische Verweisschleifen bei der Modellvorbereitung behandelt. (`cd7e345`).

## 0.5.15 – 2026-09-28

- Zugangsdaten beim Modelldownload und Provider-Ausgaben geschützt. (`f76892a`).

## 0.5.14 – 2026-09-28

- Erwartete Fehler der Modellvorbereitung mit kontrollierten Meldungen behandelt. (`fd25bce`).

## 0.5.13 – 2026-09-28

- Wiederverwendung und Fortsetzung der Modellvorbereitung abgesichert. (`5bb21af`).

## 0.5.12 – 2026-09-28

- Validierung und atomare Bereitstellung von Embedding-Modellen eingeführt. (`037ca53`).

## 0.5.11 – 2026-09-28

- Download festgelegter Embedding-Modellkandidaten ergänzt. (`723dcbe`).

## 0.5.10 – 2026-09-28

- CLI zur Offline-Prüfung lokaler Embedding-Modelle ergänzt. (`9747dda`).

## 0.5.9 – 2026-09-27

- Sauberen Abbruch von Vektorbuilds ohne erreichbares Qdrant ermöglicht. (`68fee02`).

## 0.5.8 – 2026-09-26

- Laufzeitdiagnose vereinheitlicht. (`260f32f`).

## 0.5.7 – 2026-09-26

- Speicherpfade für CLI und Web vereinheitlicht. (`29fa8c9`).

## 0.5.6 – 2026-09-25

- Prüfung des Inhalts umbenannter Python-Dateien im Repository-Hook ergänzt. (`178f46c`).

## 0.5.5 – 2026-09-25

- Fehlermeldungen der Suche und Hinweise zum Qdrant-Start verbessert. (`801ec0b`).

## 0.5.4 – 2026-09-25

- Validierung und Schutz der Qdrant-Konfiguration ergänzt. (`8ea4764`).

## 0.5.3 – 2026-09-25

- Qdrant-Server als Standard für Vektor-Workflows eingeführt. (`3d7b27b`).

## 0.5.2 – 2026-09-25

- Qdrant-Serverstatus in Web-Workflows aufgenommen und Konfiguration dokumentiert. (`751b062`).

## 0.5.1 – 2026-09-23

- Protokollierung nach Review überarbeitet. (`a632182`).

## 0.5.0 – 2026-09-15

- Abschnittsweise Indexierung von Ratsdokumenten und Recherche-Benchmark ergänzt. (`072eb16`).

## 0.4.8 – 2026-08-28

- Lokale Tagesordnungsübersichten synchronisiert. (`ff800a5`).

## 0.4.7 – 2026-08-23

- Weitere Review-Korrekturen umgesetzt. (`b19a67c`).

## 0.4.6 – 2026-08-22

- Analysefortschritt und Antwort-Leseansicht verbessert. (`747d75b`).

## 0.4.5 – 2026-08-22

- Provider-Aufruf und Verarbeitung AES-verschlüsselter PDFs korrigiert. (`97b26e3`).

## 0.4.4 – 2026-08-22

- Analysejobs und erneuten Start vereinfacht. (`0cab2ca`).

## 0.4.3 – 2026-08-21

- Status älterer Analysen normalisiert. (`40e3ceb`).

## 0.4.2 – 2026-08-21

- Sichere Markdown-Vorschau ergänzt. (`be2c3ce`).

## 0.4.1 – 2026-08-21

- Zusammenfassung großer Analysequellen ergänzt. (`a1928e8`).

## 0.4.0 – 2026-08-21

- Lebenszyklus der Analysejobs präzisiert. (`fa401a5`).

## 0.3.6 – 2026-08-21

- Datenservice-Jobs dauerhaft gespeichert. (`e8cacff`).

## 0.3.5 – 2026-08-21

- Darstellung semantischer Suchergebnisse verbessert. (`59ac601`).

## 0.3.4 – 2026-08-21

- Filter für Analyselisten ergänzt. (`45eb3d2`).

## 0.3.3 – 2026-08-21

- Barrierefreiheit und Formulare der Weboberfläche verbessert. (`be7eb7e`).

## 0.3.2 – 2026-08-21

- Rückmeldung zum Abschluss von Service-Jobs verbessert. (`12f49bb`).

## 0.3.1 – 2026-08-21

- Manuelle Aktualisierung des Service-Status ergänzt. (`43f0657`).

## 0.3.0 – 2026-07-21

- KI-Analyseworkflow erweitert. (`df89004`).

## 0.2.9 – 2026-07-21

- Pushes mit Ziel `main` durch Repository-Hook blockiert. (`3b4e8e9`).

## 0.2.8 – 2026-07-17

- Review-Korrekturen am Landkreis-Workflow umgesetzt. (`af5fb3c`).

## 0.2.7 – 2026-07-17

- Vektorstatus für Landkreis-Daten ergänzt. (`8ae1423`).

## 0.2.6 – 2026-07-17

- Speicherbedarf der Landkreis-Vektorindexierung reduziert. (`a61876b`).

## 0.2.5 – 2026-07-17

- Landkreis-Datenjobs in die Oberfläche integriert. (`d7c1125`).

## 0.2.4 – 2026-07-17

- Vektorsuche für Landkreis-Veröffentlichungen ergänzt. (`665ea20`).

## 0.2.3 – 2026-07-17

- Direkte PDF-Links auf Amtsblätter unterstützt. (`f3bedbd`).

## 0.2.2 – 2026-07-17

- Bereits vorhandene Landkreis-Veröffentlichungen beim Abruf übersprungen. (`76e4cab`).

## 0.2.1 – 2026-07-17

- Landkreis-Abruf und Datenbankaufbau getrennt. (`847238f`).

## 0.2.0 – 2026-07-17

- Import von Landkreis-Veröffentlichungen eingeführt. (`4922a59`).

## 0.1.6 – 2026-06-28

- Abgelöste Oberflächenpfade entfernt; Django als aktive Oberfläche beibehalten. (`8590444`).

## 0.1.5 – 2026-06-20

- Qdrant-Sperren nach Web-Suchzugriffen freigegeben. (`6effe2e`).

## 0.1.4 – 2026-06-16

- Vektorsuche in die Django-Oberfläche integriert. (`8ceebaf`).

## 0.1.3 – 2026-05-07

- Geschützte Ablage des Hugging-Face-Tokens ergänzt. (`950ce51`).

## 0.1.2 – 2026-05-07

- Dokumentsuchseite ergänzt. (`63bef8e`).

## 0.1.1 – 2026-04-24

- Behandlung lokaler Dokumentpfade abgesichert. (`a89fa96`).

## 0.1.0 – 2026-03-01

- Projektweite Softwareversionierung mit kanonischer Datei `VERSION` eingeführt. (`03375d7`).

## Vor der Versionierung – 2025 bis Februar 2026

Die folgenden Meilensteine entstanden vor Einführung von `VERSION` und erhalten rückwirkend keine Versionsnummer.

- **28.02.2026:** Workflow zur Verarbeitung von Dokumentinhalten, sichtbare GUI-Vorgaben und Korrektur der Datumsanzeige ergänzt.
- **08.02.2026:** PDF-Extraktion und Analyseexport erweitert; modulare GUI mit Analysebereich, Parametervorgaben, Abbruch und Einstellungen aufgebaut.
- **07.02.2026:** Einheitliche Zeilenenden über Git- und Editor-Konfiguration festgelegt.
- **31.01.–01.02.2026:** SQLite-Indexierung von Sitzungen, Tagesordnungspunkten und Dokumenten sowie erste Entwickler-GUI eingeführt.
- **07.11.2025:** Strukturierte Dokumentdownloads, Anfrageratenbegrenzung, Caching und Tagesordnungsübersichten ergänzt.
- **01.–02.11.2025:** SessionNet-Abrufpipeline aufgebaut, an die Sitzungsübersicht angepasst und eindeutige Download-Dateinamen eingeführt.
- **18.–30.10.2025:** Projekt und Repository-Grundstruktur angelegt.
