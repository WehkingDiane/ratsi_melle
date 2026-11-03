# Bestehenden Ratsinfo-Index weiterverwenden

Stand: 03.11.2026, Version 0.5.67.

Der vorhandene Index `ratsi_passages` wird weiterverwendet. Nach dem Windows/XPU-Vergleich hat der Nutzer die kleinen numerischen Unterschiede akzeptiert, um einen mehrtägigen Neuaufbau zu vermeiden. Das ist eine konkrete Betriebsentscheidung für zwei Modellmanifeste, keine allgemeine Freigabe beliebiger Bibliothekswechsel.

## Akzeptierte Bestände

| Bestand | Manifest-SHA-256 |
| --- | --- |
| Bisheriger Index | `478077ff73fbf75e6e4e1660de2c9c6d8cbbbab6d9864c7ffe06ee87d34314c9` |
| Neuer Windows-Modellbestand | `b126904ecc150d7c7a72490a8cb0fcee969ad925db0d21f75d8b6bd67261176d` |

Die vollständigen akzeptierten Verträge stehen in `src/config/index_compatibility.py`. Harrier- und Tokenizer-Revision bleiben `f9b9dc8d367d443f2479d27aa5d8d2850c0774ee`, BM25 bleibt `22b8d2af71a76161e18dd432d2cee0eefa66e412`, die Dimension 1024 und die Pipeline `passages-1`. Die Ausnahme gilt ausschließlich für `ratsi_passages`. Andere Collections behalten die exakte Vertragsprüfung. Unbekannte Manifeststände sowie andere Modelle, Revisionen, Dimensionen oder Pipeline-Versionen bleiben gesperrt.

Der akzeptierte Windows-Bestand verwendet `transformers 5.20.2`, `sentence-transformers 5.7.0`, `fastembed 0.9.0` und `huggingface-hub 1.33.0`. Die installierten Bibliotheken müssen weiterhin exakt zum ausgewählten Modellmanifest passen. Insbesondere ist der abweichende WSL-Bibliotheksstand damit nicht freigegeben.

## Unter Windows weiterarbeiten

Der vorbereitete neue Bestand liegt am Standardpfad `data/models`. Der alte Bestand wurde bytegleich unter `archive/data/models` gesichert; der temporäre Kandidatenordner wurde aufgelöst. Die Manifestdatei und ihre relativen Bestandspfade bleiben unverändert. Ein erneuter Download oder Indexneuaufbau ist dafür nicht nötig.

Falls in der bisherigen PowerShell noch der Kandidatenpfad gesetzt ist, die Variable vor dem nächsten Aufruf entfernen:

```powershell
Remove-Item Env:RATSI_MODELS_DIR -ErrorAction SilentlyContinue
& .\.venv\Scripts\python.exe .\scripts\build_bi_vector_index.py --limit 10
```

Für die Weboberfläche:

```powershell
& .\.venv\Scripts\python.exe .\scripts\run_web.py
```

Ohne `RATSI_MODELS_DIR` verwenden neue Prozesse automatisch `data/models`. Bereits laufende Webprozesse mit der alten Einstellung neu starten. Falls der Kandidatenpfad zusätzlich dauerhaft in einer Startkonfiguration oder Benutzer-Umgebungsvariable hinterlegt wurde, diesen Eintrag ebenfalls entfernen. Der bisherige Qdrant-Server und dessen lokale Freigabemarker bleiben die Ziele; sie müssen nicht manuell geändert werden.

Der unveränderte Build-Ablauf überspringt vollständig indexierte Dokumente und ergänzt fehlende oder unvollständige. Alte Punkte behalten ihren ursprünglichen Herkunftsvertrag; neue Punkte erhalten den aktuellen Vertrag. Bei einer neuen Freigabe wird der gemischte Bestand geprüft und der Marker auf den verwendeten aktiven Vertrag geschrieben. Bestehende Inhaltsprüfsummen, Schema-, Vollständigkeits- und Freigabeprüfungen bleiben wirksam. Auch die Suche akzeptiert beide Herkunftsverträge. Eine neue Auswahlfunktion zur gezielten Neuberechnung alter Dokumente wurde nicht ergänzt.

## Grundlage und Grenzen der Entscheidung

Der lokale Bericht `data/processed/vector_compatibility_windows_03.json` enthält den Windows/XPU-Test mit 128 Passagen und drei Anfragen. Vier Vektoren bestanden den strengen Vergleich; 124 wichen numerisch ab. Die minimale Dense-Kosinusähnlichkeit betrug 0,9998963656. Alle BM25-Token-IDs stimmten überein; die größte Gewichtsdifferenz lag bei etwa `2,1e-7`. Bei allen drei Anfragen waren dieselben zehn Stichprobentreffer vorhanden; nur bei „Schulsanierung“ tauschten die Plätze 7 und 8.

Die Stichprobe beweist keine vollständige Gleichheit. Die Suchprüfung verglich Kandidaten-Anfragevektoren gegen alte und neue Stichprobenvektoren, ohne alte Anfrage-Baseline und ohne vollständige Produktionssuche. Die kleinen Unterschiede werden für diesen Bestand bewusst akzeptiert. Die langsame Suche wurde damit nicht untersucht oder optimiert.

Das temporäre Diagnose-Skript, sein Berechnungsmodul, seine Tests und die Diagnoseanleitung wurden entfernt. Bytegleiche lokale Sicherungen liegen unter `archive/`; diese sind nicht Teil von Git. Der Bericht und die Modellbestände bleiben als lokale Laufzeitdaten erhalten. Der abgeschlossene Planvermerk wurde in diese Betriebsdokumentation überführt und unter `archive/docs/plans/vector_index_vertragskonflikt.md` bytegleich gesichert. Modelle, Bericht und Archiv sind bereits durch `.gitignore` abgedeckt; nur `data/models/.gitkeep` bleibt versioniert.
