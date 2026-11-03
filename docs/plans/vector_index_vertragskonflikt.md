# Vertragskonflikt beim Aufbau des Vektorindex

Stand: 03.11.2026. Priorität: **Wichtig**. Status: **Weiterverwendung beschlossen und implementiert; Windows-Betriebsprüfung ausstehend**.

## Problem und Entscheidung

Am 30.10.2026 brach `python scripts/build_bi_vector_index.py --limit 10` mit einem abweichenden Modell- oder Pipelinevertrag für `ratsi_passages` ab (Run-ID `ed7b2bfdbc43`). Zusätzlich waren die installierten Modellbibliotheken neuer als die im ursprünglichen Modellmanifest verzeichneten Versionen. Welcher Vertragswert im historischen Lauf abwich, ist aus dessen Log nicht rekonstruierbar.

Der Windows/XPU-Vergleich vom 03.11.2026 ist im lokalen Bericht `data/processed/vector_compatibility_windows_03.json` festgehalten: 128 Passagen, minimale Dense-Kosinusähnlichkeit 0,9998963656, identische BM25-Token-IDs und bei drei Anfragen identische Top-10-Treffermengen. Bei einer Anfrage tauschten die Plätze 7 und 8. 124 Vektoren überschritten die strenge numerische Toleranz, ohne einen grundlegenden Wechsel des Vektorraums zu belegen.

Der Nutzer hat entschieden, diesen Bestand mit den neueren Windows-Bibliotheken weiterzuverwenden. Ein mehrtägiger vollständiger Neuaufbau steht für die unterstützende Suchfunktion nicht im Verhältnis zum Nutzen. Weitere Stichprobentests wurden nicht gewünscht.

## Umsetzung

Seit 0.5.67 akzeptieren Aufbau und Suche für `ratsi_passages` die beiden vollständigen, konkret verglichenen Modellverträge. Unbekannte Verträge und andere Modelle bleiben gesperrt. Alte Punkte behalten ihren ursprünglichen Herkunftsvertrag. Neue Punkte dürfen mit dem akzeptierten neueren Bibliotheksstand erstellt werden. Der normale Build-Ablauf bleibt erhalten; eine neue Funktion zur gezielten Aktualisierung alter Dokumente wurde nicht ergänzt.

Der [Betriebsablauf und die Grenzen der Freigabe](../index_compatibility.md) enthalten die Manifeststände und Windows-Befehle. Die temporären Diagnosewerkzeuge wurden auf Nutzerwunsch entfernt; bytegleiche lokale Archivkopien und der lokale Ergebnisbericht bleiben erhalten.

Die automatisierten Prüfungen müssen den gemischten Aufbau und die Suche sowie die fortbestehende Ablehnung unbekannter Verträge abdecken. Die anschließende Ausführung des normalen Builds und der Suche unter Windows bleibt als Betriebsprüfung ausstehend.
