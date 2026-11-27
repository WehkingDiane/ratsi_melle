# Plan: Prüfartefakte und Hilfsskripte aufräumen

Stand: 17.11.2026. Status: geplant, noch nicht umgesetzt.

## Ziel und Kontext

Temporäre Diagnose- und Testdaten sollen unter `tmp/` liegen. Dauerhaft benötigte
abgeleitete Projektdaten können weiterhin unter `data/processed/` liegen.
Hilfsskripte für manuelle Diagnosen sollen einen eigenen Unterordner erhalten.

Derzeit enthält `data/processed/` vor allem ältere Downloadprüfungen,
Bestandsvergleiche, Modelltests und Windows-Kompatibilitätsberichte. Das reguläre
Modellverzeichnis ist `data/models/`; abweichende Einstellungen sind vor dem
Aufräumen auf beiden Betriebssystemen zu prüfen. Einige Berichte dienen noch als
Nachweis in der [Kompatibilitätsdokumentation](../suche/kompatibilitaet.md).

`scripts/evaluate_bi_search.py` prüft bekannte PDF-Belege und die Qualität der
öffentlichen Suche anhand vorbereiteter Testfragen. Seine Ergebnisse landen
standardmäßig unter `data/processed/search_evaluation/`. Das Skript wird bei Bedarf
manuell gestartet und gehört fachlich zu den Diagnosewerkzeugen.

Diese Planung ergänzt die [RI-Aufgabenliste](project_tasks.md) als separates,
zurückgestelltes Aufräumvorhaben. Dort bleiben ausschließlich RI-Arbeiten stehen.

## Offene Aufgaben

### Bestand und Nutzung prüfen

- [ ] Inhalt von `data/processed/` nach Zweck, Erzeuger, aktuellen Aufrufern und benötigter Aufbewahrung erfassen.
- [ ] Unter Windows und WSL prüfen, ob `RATSI_MODELS_DIR`, Startkonfigurationen oder gespeicherte Jobparameter noch auf alte Testmodelle zeigen. Den aktiven Modellbestand samt Manifest unter `data/models/` bestätigen.
- [ ] Für vorhandene Berichte festlegen, welche als Nachweis erhalten bleiben und welche nach Abschluss ihrer Aufbewahrung entfallen können. Dokumentierte Kompatibilitätsnachweise dabei erhalten.

### Temporäre Daten neu ablegen

- [ ] Nach bestätigter Nutzung die nachfolgende Zielzuordnung umsetzen. Vorhandene gleichnamige Ziele prüfen und Zusammenführungen anhand des Inhalts entscheiden.

| Bisheriger Inhalt | Vorgeschlagenes Ziel |
| --- | --- |
| `data/processed/download_checks/` | `tmp/download_checks/` |
| `data/processed/session_inventory_20261004/` | `tmp/session_inventory_20261004/` |
| `data/processed/embedding_acceptance_20261004/` | `tmp/embedding_acceptance_20261004/` |
| `data/processed/vector_compatibility_windows_*.json` | `tmp/vector_compatibility/` |
| Künftige Suchauswertungen | `tmp/search_evaluation/` |

- [ ] Bei Verschiebungen Dateiinhalte per SHA-256 vergleichen und bisherige Ablagen erst nach erfolgreicher Prüfung auflösen. Obsolete oder ersetzte Dateien gemäß [Archivierungsregeln](../../AGENTS.md#regeln-zu-entfernen--refactoring-verpflichtend) sichern.
- [ ] Alten Modell-Testbestand nach Prüfung auf aktive Nutzung und gewünschte Aufbewahrung gezielt entfernen; benötigte Nachweise vorher erhalten.
- [ ] Dokumentationsverweise auf verschobene Berichte aktualisieren. Die temporäre Ablage ersetzt keine dauerhafte Sicherung benötigter Nachweise.
- [ ] Prüfen, welche dauerhaften Ergebnisse `data/processed/` künftig tatsächlich benötigt. Pfadkonstanten und die bestehende Migration alter SQLite-Dateien bei einer späteren Strukturänderung berücksichtigen.

### Diagnoseskripte einordnen

- [ ] Zielordner für manuelle Diagnosewerkzeuge festlegen. Vorschlag: `scripts/diagnostics/`; `scripts/service/` als alternative Bezeichnung prüfen.
- [ ] `scripts/evaluate_bi_search.py` nach der Entscheidung in diesen Unterordner verschieben und bei mehreren Werkzeugen einen kurzen Einstieg mit Zweck und Aufrufen ergänzen.
- [ ] Vor dem Entfernen des bisherigen versionierten Python-Pfads eine bytegleiche Archivkopie mit relativer Pfadstruktur anlegen und prüfen.
- [ ] Repository-Wurzelermittlung, Imports, Tests und sämtliche Aufrufer an den neuen Skriptpfad anpassen. Vorhandene CLI-Optionen einschließlich `--validate-only` und `--output` erhalten.
- [ ] Standard-Ausgabepfad der Suchauswertung auf `tmp/search_evaluation/` ändern. Explizite `--output`-Pfade weiterhin unterstützen.
- [ ] Weitere Skripte im Stamm von `scripts/` nach tatsächlichem Zweck prüfen; Diagnosewerkzeuge und reguläre Datenjobs nachvollziehbar zuordnen.

### Dokumentation und Prüfung

- [ ] Betroffene Anleitungen und Dateipfadverweise nachziehen; die Abgrenzung zwischen `tmp/` und `data/processed/` in der [Datenpflege](../betrieb/datenpflege.md) festhalten.
- [ ] Für die Suchauswertung die betroffenen Tests in `tests/test_embedding_offline_acceptance.py` und `tests/test_qdrant_connection.py` anpassen. Standard-Ausgabe, explizite Ausgabe und reine Belegprüfung gezielt testen.
- [ ] CLI-Hilfe am neuen Pfad sowie relative Dokumentationslinks prüfen. Für den Testlauf temporäre Verzeichnisse und simulierte Abhängigkeiten verwenden.
- [ ] Verhalten von Suche, Downloads und Indexaufbau nach der Einordnung gezielt prüfen. Den vollständigen PR-Testlauf führt der Nutzer gemäß [Testregeln](../entwicklung/tests.md) aus.
- [ ] Versionsänderung anhand des endgültigen Umsetzungspakets prüfen und sichtbare Änderungen gemeinsam mit dem Changelog committen. Diese reine Planung erhält keine neue Anwendungsversion.

## Abschlusskriterien

Die temporären Prüfartefakte liegen an den vereinbarten Orten und die aktiven
Modellpfade sind geprüft. Benötigte Nachweise bleiben auffindbar. Das Suchprüfskript
ist über seinen dokumentierten neuen Pfad nutzbar und schreibt standardmäßig nach
`tmp/search_evaluation/`. Imports, gezielte Tests und Dokumentationsverweise passen
zur Struktur. Die Datenbestände für BI und RI bleiben beim Aufräumen erhalten.
