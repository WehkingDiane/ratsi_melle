# Abschnittsindex und Recherchequalitaet

Seit Version 0.5.0 baut `scripts/build_vector_index.py` fuer Ratsinfo die Collection
`ratsi_passages` auf. Modell bleibt `microsoft/harrier-oss-v1-0.6b`, kombiniert
mit `Qdrant/bm25`. Es werden keine Online-Embeddings oder Reranker verwendet.
Der Landkreis-Builder bleibt ein eigener Dokumentindex.

## Vollstaendige Quellen und Fundstellen

- PDF-Text wird auf allen Seiten mit `pypdf` gelesen, bis zu einer Dateigroesse von
  einschliesslich 128 MiB. Diese Suchpipeline ist unabhaengig von der aelteren
  Extraktionspipeline mit 25-MiB-Grenze. Die Grenze von 128 MiB erlaubt auch
  den vollstaendigen Abschlussbericht Radverkehrskonzept (etwa 102,5 MiB).
  Das automatische SessionNet-Downloadlimit liegt weiterhin bei 100 MiB;
  groessere Originaldateien muessen manuell am hinterlegten Quellpfad abgelegt werden.
- Fuer einzelne Seiten ohne Text wird automatisch OCR versucht, auch bei
  gemischten Text-/Scan-PDFs. Erforderlich sind `pdftoppm` und `tesseract` mit
  `deu+eng`. Pro Werkzeugaufruf gilt ein Timeout von 120 Sekunden.
- Fehlende OCR oder unlesbare Seiten werden als `unreadable_pages` gespeichert
  und im Build ausgegeben. Eine erfolgreiche Indexierung garantiert daher nicht,
  dass jede Seite Text geliefert hat. `scripts/update_vector_index.py --refresh`
  wiederholt die Extraktion als ausdrueckliche Wartungsaufgabe.
- Text-, Markdown-, HTML- und CSV-Dateien werden ebenfalls verarbeitet.
- Fehlende Dateien oder vollstaendig leere Extraktionen erhalten einen expliziten
  Metadaten-Fallback; fehlerhafte PDFs werden als Buildfehler gemeldet.
- Abschnitte haben standardmaessig maximal 768 Harrier-Tokens und 96 Tokens
  Ueberlappung. Seiten bleiben getrennt; innerhalb einer Seite werden bevorzugt
  Absatzgrenzen genutzt. Kurze Seiten ergeben kuerzere Abschnitte.
- Payloads enthalten Dokument-ID, URL, Sitzung, TOP-Zuordnung aus dem Index,
  Seitenzahl, Text, Zeichenpositionen, Extraktionsmethode und bei neu
  berechneten Vektoren den vollstaendigen Modell-/Pipelinevertrag im Feld
  `index_compatibility`.
  Eine neue TOP-Zuordnung innerhalb sitzungsweiter Protokolle wird nicht abgeleitet.
- Die Suche zeigt einzelne Fundstellen mit Seitenzahl und einem Link zur lokalen
  PDF-Seite. Mehrere relevante Abschnitte eines Dokuments koennen erscheinen.

## Aufbau und Migration

Qdrant muss erreichbar und der lokale Modellbestand vorbereitet sein. Vor dem
ersten Build oder bei `local_models_unavailable` diese Schritte ausfuehren:

```bash
python scripts/prepare_embedding_models.py --download
python scripts/prepare_embedding_models.py --check
python scripts/build_vector_index.py --limit 10
```

Ein bereiter Bestand wird spaeter ohne erneute Vorbereitung verwendet.
Vorbereitung und Build muessen dieselbe Python-Umgebung und denselben
Modellstamm (`data/models/` oder `RATSI_MODELS_DIR`) nutzen. Bei bestehenden
Collections ohne Kompatibilitaetsmarker zuerst die
[Legacy-Pruefung und Uebernahme](embedding_model_management.md#einmalige-uebernahme-bestehender-collections)
durchfuehren; nur `result: verified` erlaubt die Uebernahme.

Weitere Build-Aufrufe:

```bash
python scripts/build_vector_index.py
python scripts/build_vector_index.py --limit 25
python scripts/build_vector_index.py --batch-size 4
```

Seit 0.5.59 ergaenzt der normale Build ausschliesslich fehlende oder unvollstaendige
Dokumente. Ein Dokument gilt als vorhanden, wenn mindestens eine vollstaendig
bestaetigte Generation mit allen Abschnittspositionen vorliegt. Vollstaendige
Dokumente werden vor Dateizugriff und Fingerprint-Berechnung uebersprungen.
Ein veraenderter SQLite-Zeilenschluessel, Dateiinhalt oder Metadatensatz fuehrt
dadurch nicht mehr zu einem unbeabsichtigten Neuaufbau.

`--limit` begrenzt fehlende Dokumente, nicht Abschnitte. Weitere Laeufe setzen den
Aufbau fort. Ein erfolgreicher Testlauf kann `ready: false` liefern:
`pending_documents` nennt die noch ausstehenden Dokumente; die vollstaendige
Freigabe erfolgt erst nach Abschluss des Aufbaus. Ohne `--limit` werden alle
ausstehenden Dokumente verarbeitet. Der normale Build gleicht nur kompakte
Abschnittsmetadaten mit SQLite ab, prueft den Modellvertrag und das Qdrant-Schema
und laedt keine numerischen Bestandsvektoren. Wenn nichts fehlt und der Index
bereits freigegeben ist, bleiben Marker und Index unveraendert; Tokenizer und
Embedding-Modell werden nicht geladen.

Service-Befehle sind bewusst getrennt:

```bash
python scripts/check_vector_index.py
python scripts/update_vector_index.py
python scripts/update_vector_index.py --refresh
python scripts/update_vector_index.py --chunk-tokens 768 --overlap-tokens 96 --no-ocr
python scripts/update_vector_index.py --cleanup-orphans
```

Die Pruefung liest Modellartefakte tief, kontrolliert Vertrag und vorhandene
Vektoren und meldet Vollstaendigkeit, verwaiste Dokumente und unbestaetigte
Abschnitte. Sie schreibt weder Vektoren noch Freigabemarker und berechnet keine
Embeddings zum Vergleich neu. Eine Inhaltsaktualisierung vergleicht dagegen die
Datei-/Metadaten-Fingerprints und ersetzt geaenderte Generationen. `--refresh`
erzwingt die Neuberechnung auch ohne Aenderung. Abweichende Modellvertraege
werden weiterhin abgelehnt; diese Skripte sind keine automatische Modellmigration.

Neue Abschnitte werden vor dem Entfernen der alten Generation geschrieben und
erst nach vollstaendigem Schreiben des Dokuments fuer die Suche freigeschaltet.
Abgebrochene Generationen lassen sich beim naechsten Lauf vervollstaendigen.
Verwaiste Dokumente bleiben beim normalen Build erhalten. Nur die ausdrueckliche
Service-Aktualisierung mit `--cleanup-orphans` bereinigt sie nach einem
vollstaendigen fehlerfreien Lauf; bei `--limit` bleibt diese Bereinigung aus.

Der bisherige Index `ratsi_documents` bleibt erhalten. Erst wenn alle im SQLite-Index
enthaltenen Dokumente vollstaendig als Abschnitte oder Metadaten-Fallback vorliegen,
schreibt der Builder `data/db/qdrant/ratsi_passages.ready.json`. Die Websuche nutzt
anschliessend die neue Collection. Vorher greift sie auf den bisherigen Index zu.
Die Vektorseite zeigt den Aufbaufortschritt immer aus `ratsi_passages`, auch wenn
die Suche noch `ratsi_documents` verwendet. Vollstaendige und fehlende Dokumente,
Abschnitte und Abdeckung sind vom aktiven Suchindex und seiner Freigabe getrennt.
Ein abgebrochener Build laesst die Anzeige dadurch nicht mehr auf die geringere
Abdeckung des alten Suchindexes zurueckfallen. Modellverwaltung und Legacy-Pruefung
stehen unter „Service → Wartung“ auf `/service/wartung/`. Lokale Qdrant-Zugriffe
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
Collection und Modell. Ein fehlender oder inkompatibler Modellbestand erfordert
zunaechst `python scripts/prepare_embedding_models.py --download`; Evaluation
und Suche beschaffen selbst keine Modellgewichte. Aus den Unit-Tests lassen sich keine realen
Qualitaetsgewinne oder Laufzeiten ableiten.

Die [Phase-7-Abnahme](embedding_model_management.md#abschlusspruefung-phase-7-2026-10-04)
prueft einen vollstaendigen separaten Offline-Build mit echten Harrier-/BM25-
Modellen, die anschliessende Websuche und eine Evaluation mit PDF-Beleg. Der
Opt-in-Aufruf steht im [README](../README.md#lokalen-embedding-modellbestand-pruefen).
Zwei Test-PDFs und eine Abnahmefrage ersetzen keinen Vergleich der 30
Recherchefragen am vollstaendigen produktiven Bestand. Melle-Legacy-Uebernahme
und Landkreis-Neuaufbau bleiben bewusste separate Betriebsaktionen.

## Qdrant-Serverbetrieb

Die Befehle zum Starten und Prüfen des lokalen Servers stehen im
[README](../README.md#qdrant-lokaler-speicher-oder-server).

`src/config/settings.py` liest und validiert Modus, URL und Statuspfad.
Ohne zusätzliche Einstellung wird der Server `http://127.0.0.1:6333` genutzt.
Eine nicht leere `RATSI_QDRANT_URL` (HTTP oder HTTPS) wählt einen anderen Server. Das gilt auch für
`--legacy-document-index`, den Landkreis-Build und `evaluate_search.py`, damit
Build und Suche dasselbe Ziel sehen. Für den bisherigen lokalen Pfad
`RATSI_QDRANT_URL` entfernen und `RATSI_QDRANT_MODE=local` setzen. `--qdrant-dir`
wirkt ausschließlich im lokalen Modus; im Servermodus werden dort keine
Qdrant-Dateien angelegt. Der
REST-Client verwendet 10 Sekunden Timeout je Anfrage. Verbindungs- und Lesefehler
brechen den Vorgang ab und werden nicht als leerer Index ausgegeben. Die
Vektor-Builds pruefen die Verbindung vor dem Modellstart; ist der Server nicht
erreichbar, enden sie mit Exitcode 1 und einer kurzen Fehlermeldung ohne
Python-Traceback. Der Freigabemarker bleibt bei diesem Startfehler unveraendert.

```powershell
python scripts/prepare_embedding_models.py --download
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

Vor einem Passage-Build mit Schreibbedarf wird dessen Freigabe zurückgenommen.
Ein Build ohne fehlende Dokumente belaesst eine bestehende Freigabe unveraendert.
Erst ein fehlerfreier
Lauf mit vollständigen, bestätigten Generationen aller aktuellen Dokumente und
ohne unbestaetigte Abschnitte schreibt den Marker atomar. Der normale Build
vergleicht keine Fingerprints vollstaendiger Dokumente; das gehoert zur
Service-Aktualisierung. Der Servermarker enthält den SHA-256-Hash der URL, die exakte Punktzahl,
den Collection-Namen und den vollstaendigen Kompatibilitaetsdatensatz aus
Modell-IDs und Revisionen, Manifest-Hash, Vektordimension und Pipeline-Version.
Der lokale Marker enthaelt denselben Kompatibilitaetsdatensatz und
Collection-Namen.
Normale Builds speichern `validation_mode: payload` mit `payload_sha256`: einen
stabilen Hash aus Punkt-IDs, Modellvertraegen und kompakten Abschnittsmetadaten.
Numerische Bestandsvektoren sind darin bewusst nicht enthalten. Die Suche
beruecksichtigt diesen Modus; strikte bestehende Marker und Service-Builds nutzen
weiterhin `vectors_sha256`. Eine solche Bestandspruefung ist keine Garantie fuer
inhaltlich richtige Embeddings; fuer gezielte Diagnose gibt es den separaten
Pruefbefehl. Bei einem unterbrochenen Build darf die Punktzahl vom letzten
Zwischenmarker abweichen, damit fehlende Dokumente fortgesetzt werden koennen.
Baut ein Indexer eine vorhandene Collection fort, muss auch deren Qdrant-Schema
mit Vektornamen, Dense-Dimension und Cosine-Distanz passen; das gilt selbst fuer
eine leere Collection. Die Websuche vergleicht den Marker der ausgewaehlten
Collection vor der Query-Kodierung mit dem aktiven Modellvertrag. Die Evaluation
prueft ihre ausdruecklich gewaehlte Collection ebenso; `ready=false` sperrt
beide Pfade bis zur Freigabe.
Bisherige Marker mit Klartext-URL werden nicht mehr akzeptiert; ein vollständiger
Passage-Build schreibt einen neuen Marker. Die
Suche prüft, dass Punktzahl und Anzahl der `committed`-Punkte dazu passen.
Ein kopierter lokaler Marker oder die bloße Existenz einer migrierten Collection
aktiviert die Passage-Suche nicht. Beim Ersetzen oder Wiederherstellen einer
Server-Collection ist eine gezielte Service-Pruefung beziehungsweise verifizierte
Uebernahme erforderlich; ein normaler Build ist kein Wiederherstellungswerkzeug.
Der Marker ist kein Backup des Index.

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
