# Abschnittsindex und Recherchequalitaet

Seit Version 0.5.0 baut `scripts/build_vector_index.py` fuer Ratsinfo die Collection
`ratsi_passages` auf. Modell bleibt `microsoft/harrier-oss-v1-0.6b`, kombiniert
mit `Qdrant/bm25`. Es werden keine Online-Embeddings oder Reranker verwendet.
Der Landkreis-Builder bleibt ein eigener Dokumentindex.

## Vollstaendige Quellen und Fundstellen

- PDF-Text wird auf allen Seiten mit `pypdf` gelesen, bis zu einer Dateigroesse von
  einschliesslich 100 MiB. Diese Suchpipeline ist unabhaengig von der aelteren
  Extraktionspipeline mit 25-MiB-Grenze.
- Fuer einzelne Seiten ohne Text wird automatisch OCR versucht, auch bei
  gemischten Text-/Scan-PDFs. Erforderlich sind `pdftoppm` und `tesseract` mit
  `deu+eng`. Pro Werkzeugaufruf gilt ein Timeout von 120 Sekunden.
- Fehlende OCR oder unlesbare Seiten werden als `unreadable_pages` gespeichert
  und im Build ausgegeben. Eine erfolgreiche Indexierung garantiert daher nicht,
  dass jede Seite Text geliefert hat. `--refresh` wiederholt die Extraktion.
- Text-, Markdown-, HTML- und CSV-Dateien werden ebenfalls verarbeitet.
- Fehlende Dateien oder vollstaendig leere Extraktionen erhalten einen expliziten
  Metadaten-Fallback; fehlerhafte PDFs werden als Buildfehler gemeldet.
- Abschnitte haben standardmaessig maximal 768 Harrier-Tokens und 96 Tokens
  Ueberlappung. Seiten bleiben getrennt; innerhalb einer Seite werden bevorzugt
  Absatzgrenzen genutzt. Kurze Seiten ergeben kuerzere Abschnitte.
- Payloads enthalten Dokument-ID, URL, Sitzung, TOP-Zuordnung aus dem Index,
  Seitenzahl, Text, Zeichenpositionen, Extraktionsmethode und Modell-/Pipelineversion.
  Eine neue TOP-Zuordnung innerhalb sitzungsweiter Protokolle wird nicht abgeleitet.
- Die Suche zeigt einzelne Fundstellen mit Seitenzahl und einem Link zur lokalen
  PDF-Seite. Mehrere relevante Abschnitte eines Dokuments koennen erscheinen.

## Aufbau und Migration

```bash
python scripts/build_vector_index.py
python scripts/build_vector_index.py --limit 25
python scripts/build_vector_index.py --chunk-tokens 768 --overlap-tokens 96 --batch-size 4
python scripts/build_vector_index.py --refresh
```

`--limit` begrenzt geaenderte Dokumente, nicht Abschnitte. Weitere Laeufe setzen den
Aufbau fort. `--no-ocr` deaktiviert die optionale OCR. Aenderungen von Dateiinhalten,
Metadaten oder Chunk-Konfiguration loesen eine erneute Verarbeitung aus. Fuer
unveraenderte Quellen werden vorhandene Vektoren wiederverwendet.

Neue Abschnitte werden vor dem Entfernen der alten Generation geschrieben und
erst nach vollstaendigem Schreiben des Dokuments fuer die Suche freigeschaltet.
Abgebrochene Generationen lassen sich beim naechsten Lauf vervollstaendigen.
Verwaiste Dokumente werden nur nach einem vollstaendigen fehlerfreien Lauf
bereinigt; bei `--limit` bleibt diese Bereinigung aus.

Der bisherige Index `ratsi_documents` bleibt erhalten. Erst wenn alle im SQLite-Index
enthaltenen Dokumente vollstaendig als Abschnitte oder Metadaten-Fallback vorliegen,
schreibt der Builder `data/db/qdrant/ratsi_passages.ready.json`. Die Websuche nutzt
anschliessend die neue Collection. Vorher greift sie auf den bisherigen Index zu.
Der Status verwendet dieselbe Collection-Auswahl wie die Suche und meldet einen
noch nicht freigegebenen Abschnittsindex als unvollständig. Bei aktivem
Abschnittsindex sind Vektoranzahl und Dokumentanzahl unterschiedliche Größen. Lokale Qdrant-Zugriffe
muessen zeitlich koordiniert werden, da der eingebettete Store einen Dateilock nutzt.

## 30 Recherchefragen mit Belegen

Der versionierte Katalog [search_benchmark.json](examples/search_benchmark.json)
enthaelt 30 aus oeffentlichen lokalen Vorlagen abgeleitete Fragen samt Original-URL,
PDF-Seite und kurzem Beleg. Themen sind Finanzen, Feuerwehr, Mobilitaet,
Wasserversorgung, Gebaeude und Bauleitplanung. Neun Fragen betreffen Seiten nach
Seite 10. Der Ausgangskatalog konzentriert sich auf Vorlagen aus Juni 2025;
er ist kein Protokoll echter Nutzereingaben und keine repraesentative Vollbewertung.

Alle Belege werden vor einer Messung gegen die lokal vorhandenen PDFs geprueft.
Fehlende oder geaenderte Quellen fuehren zum Abbruch statt zu stillen Auslassungen.

```bash
python scripts/evaluate_search.py --validate-only
python scripts/evaluate_search.py --collection ratsi_documents
python scripts/evaluate_search.py --collection ratsi_passages
```

Optional: `--benchmark DATEI`, `--db DATEI`, `--qdrant-dir ORDNER`, `--k 10`,
`--output DATEI`. Vorhandene Reportdateien werden nicht ueberschrieben.
Ergebnisse liegen standardmaessig unter `data/processed/search_evaluation/`.
Die Modellinitialisierung wird getrennt von den Suchzeiten gemessen.

Ausgewertet werden:

- `hit_at_k`: Anteil der Fragen, bei denen eine bekannte Quelle gefunden wird.
- `reciprocal_rank`: Kehrwert des ersten passenden Quellenrangs, ueber Fragen gemittelt.
- `known_source_recall_at_k`: Anteil gefundener annotierter Quellen, kein Recall
  ueber alle potentiell relevanten Dokumente im Bestand.
- `evidence_hit_at_k`: Treffer mit passender URL, Seite und Belegtext im Abschnitt.
  Der Legacy-Index besitzt diese Fundstellen nicht und erreicht hier keinen Treffer.
- `seconds`: mittlere Suchdauer inklusive Anfrage-Vektorisierung, ohne Modellstart.

Die Quellenmetriken zaehlen wiederholte URLs nur einmal innerhalb der abgerufenen
Treffer. Vergleiche sollten dieselben Fragen, denselben Dokumentbestand, dasselbe
`k` und dieselbe Hardware nutzen. Reports enthalten Einzelresultate, Benchmark-Hash,
Collection und Modell. Ein fehlender Modellcache erfordert zunaechst den Download
der lokalen Modellgewichte. Aus den Unit-Tests lassen sich keine realen
Qualitaetsgewinne oder Laufzeiten ableiten.

## Qdrant-Serverbetrieb

`src/config/settings.py` liest und validiert Modus, URL und Statuspfad.
Ohne zusätzliche Einstellung wird der Server `http://127.0.0.1:6333` genutzt.
Eine nicht leere `RATSI_QDRANT_URL` (HTTP oder HTTPS) wählt einen anderen Server. Das gilt auch für
`--legacy-document-index`, den Landkreis-Build und `evaluate_search.py`, damit
Build und Suche dasselbe Ziel sehen. Für den bisherigen lokalen Pfad
`RATSI_QDRANT_URL` entfernen und `RATSI_QDRANT_MODE=local` setzen. `--qdrant-dir`
wirkt ausschließlich im lokalen Modus; im Servermodus werden dort keine
Qdrant-Dateien angelegt. Der
REST-Client verwendet 10 Sekunden Timeout je Anfrage. Verbindungs- und Lesefehler
brechen den Vorgang ab und werden nicht als leerer Index ausgegeben.

```powershell
python scripts/build_vector_index.py
python scripts/build_landkreis_vector_index.py
python scripts/evaluate_search.py --collection ratsi_passages
```

Diese Befehle erst nach der gesonderten Datenmigration auf dem echten Server
verwenden: Der Standardserver war bei der letzten Prüfung leer. Unter WSL ist
für die Standardadresse keine Umgebungsvariable nötig. Die Adresse muss aus der
jeweiligen Python-Laufzeit erreichbar sein. Django und seine Build-Unterprozesse
erben die Umgebung; nach Änderungen Django neu starten.

### Freigabe und Status

Der lokale Marker bleibt `data/db/qdrant/ratsi_passages.ready.json`. Servermarker
liegen unabhängig davon unter
`data/db/qdrant_server_state/<SHA-256 der URL>/ratsi_passages.ready.json`.
`RATSI_QDRANT_STATE_DIR` kann diese Statuswurzel verlegen; Build und Web müssen
für dieselbe Serveradresse dieselbe Statuswurzel sehen. Ein abschließender Slash
der URL wird entfernt. Andere URL-Schreibweisen erhalten getrennte Marker.

Vor jedem Passage-Build wird dessen Freigabe zurückgenommen. Erst ein fehlerfreier
Lauf mit vollständigen, bestätigten Generationen aller aktuellen Dokumente und
ohne ausstehende Änderungen schreibt den Marker atomar. Auch `--limit` prüft die
Fingerprints aller Dokumente; die Grenze beschränkt nur die neu aufgebauten
Dokumente. Der Servermarker enthält nur den SHA-256-Hash der URL und die exakte Punktzahl.
Bisherige Marker mit Klartext-URL werden nicht mehr akzeptiert; ein vollständiger
Passage-Build schreibt einen neuen Marker. Die
Suche prüft, dass Punktzahl und Anzahl der `committed`-Punkte dazu passen.
Ein kopierter lokaler Marker oder die bloße Existenz einer migrierten Collection
aktiviert die Passage-Suche nicht. Beim Ersetzen oder Wiederherstellen einer
Server-Collection muss deren Marker entfernt und ein vollständiger Build zur
erneuten Prüfung ausgeführt werden; der Marker ist kein Backup des Index.

Während des Builds bleibt ein vorhandener `ratsi_documents`-Index als Rückweg
für die Suche verfügbar. Fehlt er ebenfalls, meldet die Suche den unvollständigen
Index. Nur einen Passage-Build je Ziel gleichzeitig ausführen. Das gilt auch im
Servermodus, obwohl parallele Suchanfragen dort keinen lokalen Dateilock brauchen.

Dashboard und Vektorseite unterscheiden „Server nicht erreichbar“, „Collection
fehlt“, „Index unvollständig“ und „bereit“. Die Vektorseite zeigt außerdem das
konfigurierte Ziel und die Abdeckung gegenüber SQLite. Die Evaluation respektiert
eine ausdrücklich gewählte Collection, auch wenn der Passage-Index bereit ist.
Collection-Namen, IDs, `harrier`-/`bm25`-Vektoren, Filter und Suchergebnisfelder
bleiben unverändert; bestätigte Schreiboperationen werden abgewartet.

### Rückweg und Prüfung

Projektprozesse stoppen, die URL-Variable entfernen und den lokalen Modus
setzen. In PowerShell:

```powershell
Remove-Item Env:RATSI_QDRANT_URL -ErrorAction SilentlyContinue
$env:RATSI_QDRANT_MODE = "local"
```

Unter WSL: `unset RATSI_QDRANT_URL; export RATSI_QDRANT_MODE=local`. Danach die
Prozesse neu starten; nun wird wieder der lokale Index genutzt. Neuere Serverdaten werden dabei nicht automatisch
zurückkopiert; vor einem dauerhaften Rückwechsel die Datenstände abgleichen.

Die automatisierten Tests entfernen eine geerbte Server-URL und sperren Zugriffe
auf produktive Qdrant-Verzeichnisse. Migration und Rückmigration werden mit
kleinen temporären Collections geprüft. Abschnitt B überträgt oder aktiviert
keine vorhandenen Produktivdaten; die echte Migration gehört zu Abschnitt C.

Prüfstand 25.09.2026: Die kleine HTTP-Probe mit Qdrant-Server 1.19.1 und
Python-Client 1.17.1 bestand einschließlich Rückmigration. Beide vorhandenen
Python-Umgebungen (Windows und WSL) verwenden Client 1.17.1. Dieser warnt vor dem
Versionsabstand zum Server (mehr als eine Minor-Version); vor der produktiven
Migration Client und Server auf kompatible Versionen abstimmen und erneut prüfen.
Die Kompatibilitätsprüfung bleibt eingeschaltet. Der Produktivserver wurde bei
dieser Implementierung nur lesend geprüft und enthielt keine Collections.
