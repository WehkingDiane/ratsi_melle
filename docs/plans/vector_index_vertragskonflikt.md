# Wichtig: Vertragskonflikt beim Aufbau des Vektorindex

Stand: 30.10.2026. Priorität: **Wichtig**. Status: **Offen**.

## Problem

Der Aufruf `python .\scripts\build_bi_vector_index.py --limit 10` bricht beim vorhandenen Index `ratsi_passages` ab:

```text
ERROR: Index ratsi_passages inkompatibel: Bestehende Collection hat einen anderen Modell- oder Pipelinevertrag. Vollstaendiger Neuaufbau oder getrennte Aufbau-Collection erforderlich.
```

Beobachtet am 30.10.2026 um 16:51:41 UTC, Run-ID `ed7b2bfdbc43`, Exit-Code 1. Logdatei: `logs/build_bi_vector_index.log`.

Der gespeicherte Kompatibilitätsvertrag stimmt nicht mit dem aktuell ermittelten Vertrag überein. Welche Felder abweichen und wodurch die Abweichung entstanden ist, muss noch ermittelt werden. Die Schutzprüfung verhindert das Vermischen inkompatibler Vektoren. `--limit` begrenzt nur die Anzahl der zu indexierenden Dokumente; auch ein Aufruf ohne Limit löst den Vertragskonflikt nicht.

## Offene Klärung und Behebung

### Diagnose vom 03.11.2026

Untersuchungsbranch: `codex/fix/vector-index-vertragskonflikt`. Die Untersuchung hat keine Indexdaten, Modellbestände oder Bibliotheken verändert.

**Nachgewiesener aktueller Blocker:** Die installierten Modellbibliotheken entsprechen nicht dem vorbereiteten Bestand. `check_embedding_model_status(Path("data/models"))` liefert unter `.venv-wsl` den Status `inkompatibel` mit der Meldung „Die installierten Modellbibliotheken entsprechen nicht dem vorbereiteten Bestand.“ Die Versionsmetadaten in `.venv/Lib/site-packages` zeigen auch für Windows Abweichungen:

| Bibliothek | Modellmanifest | WSL `.venv-wsl` | Windows `.venv` |
| --- | --- | --- | --- |
| fastembed | 0.8.0 | 0.9.1 | 0.9.0 |
| huggingface_hub | 1.10.1 | 1.33.0 | 1.33.0 |
| sentence_transformers | 5.4.0 | 5.7.0 | 5.7.0 |
| transformers | 5.5.3 | 5.22.1 | 5.20.2 |

Die Prüfung in `src/config/embedding_model_status.py` verlangt exakte Versionsgleichheit. Der Manifesthash umfasst auch Bibliotheksversionen und relative Bestandspfade; nur Erstellzeitpunkt und das Hashfeld selbst werden aus der Hashberechnung ausgeschlossen. Eine erneute Modellvorbereitung mit anderen Bibliotheksversionen kann deshalb einen neuen Indexvertrag erzeugen, auch bei gleichen Modellrevisionen.

**Ursprüngliche Vertragsabweichung noch nicht rekonstruiert:** Der vorhandene Marker `data/db/qdrant_server_state/bf6ad011a2118addbb320eb8bafcb902d99f757cd7fb8ccec8b6b0a77d0f4e5e/ratsi_passages.ready.json` und das heutige Standardmanifest `data/models/manifest.json` enthalten denselben Manifesthash `478077ff73fbf75e6e4e1660de2c9c6d8cbbbab6d9864c7ffe06ee87d34314c9`. Auch alle acht übrigen Vertragsfelder stimmen mit den aktuellen Modellkonstanten überein. Das ist ein statischer Feldvergleich, keine erfolgreiche Laufzeitfreigabe oder Prüfung der Qdrant-Punkte.

Die Fehlermeldung entsteht in `src/indexing/build_compatibility.py` beim Vergleich des gelesenen Vertrags mit `current_index_compatibility()`. Das Log des ursprünglichen Laufs enthält weder die verglichenen Vertragswerte noch den aktiven Modellpfad. Daher ist aus den vorhandenen Belegen nicht bestimmbar, welcher Vertrag damals abwich. Ein abweichender Laufzeitbestand, etwa über `RATSI_MODELS_DIR`, bleibt eine unbestätigte Möglichkeit. Die heutigen Bibliotheksabweichungen allein erklären diese konkrete historische Meldung nicht: Die Modellbereitschaft wird vor dem Vertragsvergleich geprüft.

Nächster Diagnoseschritt: Im tatsächlich betroffenen Windows-Prozess Interpreterpfad, aktiven Modellpfad und beide Verträge mit Feldabweichungen erfassen. Vor einer erneuten Modellvorbereitung zunächst den bestehenden Modellbestand und Freigabemarker sichern und entscheiden, ob die ursprüngliche Bibliotheksumgebung wiederhergestellt oder ein neuer Index aufgebaut werden soll.

### Aufgaben

- [ ] Gespeicherten und aktuellen Vertrag vergleichen und abweichende Felder sowie Ursache dokumentieren: Modell- und Tokenizer-IDs, Revisionen, Manifest-SHA-256, Vektordimension und Pipeline-Version.
- [ ] Einen sicheren Wiederanlauf festlegen: ursprünglichen Vertrag wiederherstellen oder den Index mit dem aktuellen Vertrag vollständig neu aufbauen. Bestehenden Index bis zur geprüften Ablösung erhalten.
- [ ] Einen nachvollziehbaren Ablauf für getrennten Aufbau, Prüfung und anschließende Aktivierung dokumentieren; benötigte CLI-Unterstützung prüfen.
- [ ] Fehlermeldung um konkrete Vertragsabweichungen und einen umsetzbaren nächsten Schritt ergänzen.
- [ ] Erfolgreichen Aufbau und anschließende Suche prüfen; die Ablehnung tatsächlich inkompatibler Bestände muss erhalten bleiben.

## Abnahme

Die Ursache ist anhand der Vertragsfelder nachvollziehbar. Ein dokumentierter Wiederanlauf baut einen kompatiblen Index auf, ohne den bisherigen Bestand vor erfolgreicher Prüfung zu verlieren. Der Index ist anschließend für die Suche freigegeben und nutzbar.
