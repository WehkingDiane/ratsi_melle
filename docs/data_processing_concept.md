# Grundkonzept Datenverarbeitung

Dieses Dokument beschreibt die zentrale Datenverarbeitungskette des Projekts von der Datenerfassung im Ratsinformationssystem bis zur semantischen Suche. Es ist die gemeinsame Grundlagen-Datei fuer:

- Zielsystem und Abruflogik
- Rohdatenablage
- SQLite-Indizes
- Vektorindex und semantische Suche

## 1. Zielsystem und Dauerannahmen

Das Projekt arbeitet gegen eine oeffentliche **SessionNet**-Installation der Stadt Melle unter:

- `https://session.melle.info/bi/`

Wichtige angrenzende Quellen:

- Stadtportal Melle unter `https://www.melle.de/`
- Landkreis Osnabrueck unter `https://www.landkreis-osnabrueck.de/verwaltung/veroeffentlichungen/bekanntmachungen`
- Landkreis-Amtsblaetter unter `https://www.landkreis-osnabrueck.de/verwaltung/veroeffentlichungen/amtsblaetter`

### Dauerhafte Arbeitsannahmen

- Das Zielsystem ist oeffentlich zugaenglich, aber technisch und inhaltlich sorgfaeltig zu behandeln.
- Abrufe muessen robots.txt, oeffentliche Nutzungsbedingungen und allgemeine Datenschutzanforderungen respektieren.
- Personenbezogene Daten duerfen nicht unnötig massenhaft gesammelt oder unverarbeitet weiterveroeffentlicht werden.
- Abrufe sollen mit respektvoller Lastverteilung erfolgen, insbesondere ueber Rate-Limits, Retries und Caching.
- Wenn sich HTML-Strukturen, Endpunkte oder Regeln des Zielsystems aendern, muessen Fetch- und Parsinglogik zeitnah ueberprueft werden.

## 2. Verarbeitungs-Pipeline im Ueberblick

```text
SessionNet / Stadt Melle
    ↓
fetch_sessions.py
    ↓
data/raw/YYYY/MM/<session>/
    ↓
build_local_index.py
    ↓
data/db/local_index.sqlite
    ↓
build_vector_index.py
    ↓
Qdrant-Vektorindex unter data/db/qdrant/
    ↓
Recherche, Analyse und semantische Suche in den Oberflächen
```

Landkreis-Veröffentlichungen laufen als getrennte Pipeline:

```text
Landkreis Osnabrueck Bekanntmachungen / Amtsblaetter
    ↓
fetch_landkreis_publications.py
    ↓
data/raw/landkreis/ oder RATSI_LANDKREIS_DATA_DIR
    ↓
build_landkreis_publications_db.py
    ↓
data/db/landkreis_publications.sqlite
    ↓
search_landkreis_publications.py oder build_landkreis_vector_index.py
    ↓
SQLite-FTS oder getrennte Qdrant-Collection landkreis_publications
```

## 3. Datenerfassung aus SessionNet

### Relevante Seiten

| Seite | Zweck | Parameter |
| --- | --- | --- |
| `si0040.asp` | Monatsübersicht aller öffentlichen Sitzungen | `month`, `year` |
| `si0057.asp` | Detailansicht einer Sitzung mit Tagesordnung und Dokumenten | `__ksinr` |
| `do*.asp` | Dokumentdownloads | variabel |

### HTML-Merkmale

- Monatsübersicht:
  - Tabelle `table#smc_page_si0040_contenttable1`
  - Datum über `td.siday`
  - Sitzung/Gremium/Details in `td.silink`
- Sitzungsdetail:
  - Tagesordnung in einer Tabelle mit Klasse/ID/`summary` mit Bezug zu „Tagesordnung“
- Dokumente:
  - Download-Links mit `do` oder `getfile.asp`
  - zusaetzliche sitzungsweite Dokumente in `div.smc-documents`

### Abruflogik

1. Monatsweise Sitzungsliste laden
2. Sitzungsdetailseiten laden
3. TOPs und Dokumentverweise extrahieren
4. Dokumente herunterladen
5. Fehler robust behandeln, ohne ganze Laeufe unnötig abzubrechen

Alternativ kann eine einzelne Sitzung aus dem Online-Index ausgewaehlt werden:

```bash
python scripts/fetch_session_from_index.py --list --from-date 2026-04-01 --to-date 2026-04-30
python scripts/fetch_session_from_index.py --session-id 7128
```

Dieser Einzelsitzungs-Abruf liest `session_id`, Datum, Gremium und `detail_url` aus `data/db/online_session_index.sqlite`, ruft direkt die Detailseite ab und laedt nur die Dokumente dieser Sitzung nach `data/raw/`. Die Monatsuebersicht wird dabei nicht erneut heruntergeladen.

### Abrufschutz

- Standardmaessig begrenzte Anfragefrequenz
- exponentielle Retries bei Fehlern
- Caching identischer Dokument-URLs innerhalb eines Laufs
- SessionNet-Dokumentdownloads geben oberhalb von 25 MiB einen Hinweis aus und brechen oberhalb von 100 MiB pro Dokument ab
- Ist eine verwertbare `Content-Length` vorhanden, wird ein zu grosses SessionNet-Dokument vor dem Body-Download abgewiesen; andernfalls wird die Groesse beim Streaming in 64-KiB-Bloecken geprueft
- Ein wegen seiner Groesse abgebrochenes Dokument wird nicht gespeichert; weitere Dokumente und Sitzungen des Laufs werden weiterverarbeitet

Die Dateigroessenlimits sind je Verarbeitungspfad getrennt:

| Verarbeitungspfad | Warnung | Harte Grenze | Verhalten bei Ueberschreitung |
| --- | ---: | ---: | --- |
| SessionNet-Download | mehr als 25 MiB | mehr als 100 MiB | Dokument ueberspringen, Lauf fortsetzen |
| Landkreis-Dokumentdownload | keine separate Warnschwelle | mehr als 25 MiB | Download mit Fehler abbrechen |
| Lokale Extraktionspipeline | keine separate Warnschwelle | mehr als 25 MiB | Ergebnisstatus `file_too_large`, kein extrahierter Text |

Das 25-MiB-Limit der lokalen Extraktionspipeline ist kein nachtraegliches
Downloadlimit. Eine SessionNet-Datei zwischen 25 und 100 MiB kann daher lokal
gespeichert werden, wird aber von Verarbeitungspfaden, die diese Pipeline nutzen,
nicht extrahiert.

## 4. Rohdatenablage

### Verzeichnisstruktur

```text
data/raw/<Jahr>/<Monat>/<Datum>_<Gremium>_<Sitzungs-ID>/
```

Typischer Inhalt eines Sitzungsordners:

- `session_detail.html`
- `session-documents/` fuer Dokumente ausserhalb der Tagesordnungstabelle
- `agenda/<TOP-Nummer>_<Kurzname>/`
- `manifest.json`
- `agenda_summary.json`

`session_detail.html` ist die kanonische Quelle fuer Tagesordnung und Dokumentlinks. Ist sie
neuer als `agenda_summary.json` oder `manifest.json` oder stimmt ein vorhandener
`source_html_sha1` nicht ueberein, parst `build_local_index.py` die HTML-Datei erneut. Die
daraus erzeugten TOP- und Dokumentmetadaten werden nur in den SQLite-Index geschrieben;
die Rohdaten und ihre JSON-Ableitungen bleiben unveraendert. Bereits vorhandene Dateien
werden im Index ueber den stabilen URL-Hash im Dateinamen wieder zugeordnet. Dokumentlinks
ohne lokale Datei bleiben als Metadaten erhalten, damit Dokumentanzahl und lokaler
Verfuegbarkeitsstatus getrennt korrekt dargestellt werden. Neue Fetches speichern in beiden
JSON-Ableitungen `source_html_sha1`, um Inhaltsabweichungen unabhaengig vom Dateizeitstempel
zu erkennen.

Monatsordner enthalten zusaetzlich:

- `YYYY-MM_overview.html`

### Wichtige Grundsaetze

- Rohdaten bleiben unveraendert
- Dateinamen und Metadaten werden nachvollziehbar gespeichert
- Zusätze wie „Berichterstatter …“ werden aus TOP-Ordnernamen entfernt
- unvollständige künftige Sitzungen bleiben markiert und koennen spaeter angereichert werden

## 5. SQLite-Indizes

Es gibt zwei gleich strukturierte Indexdatenbanken:

### Lokaler Index

- Skript: `scripts/build_local_index.py`
- Quelle: bereits geladene Daten unter `data/raw/`
- Ziel: `data/db/local_index.sqlite`
- beruecksichtigt nur Sitzungsordner direkt unter `data/raw/YYYY/MM/`; die getrennte
  Landkreis-Datenwurzel wird nicht als SessionNet-Bestand interpretiert

### Online-Index

- Skript: `scripts/build_online_index_db.py`
- Quelle: SessionNet ohne Dokumentdownloads
- Ziel: `data/db/online_session_index.sqlite`
- schreibt weder Sitzungs-HTML noch andere Dateien nach `data/raw/`

### Zweck der Indizes

- schnelle UI- und Analysezugriffe
- Sitzungen, TOPs und Dokumentmetadaten strukturiert abfragen
- Grundlage fuer Filter, Gremienlisten und Synchronisationslogik

### Landkreis-Veröffentlichungen

- Skript: `scripts/fetch_landkreis_publications.py`
- Build-Skript: `scripts/build_landkreis_publications_db.py`
- Vektor-Build-Skript: `scripts/build_landkreis_vector_index.py`
- Suchskript: `scripts/search_landkreis_publications.py`
- Ziel: `data/db/landkreis_publications.sqlite`
- Rohdaten: standardmaessig `data/raw/landkreis/`, alternativ `RATSI_LANDKREIS_DATA_DIR` oder `--data-dir`

Diese Datenbank ist absichtlich vom SessionNet-Index getrennt. Sie enthaelt `publications`, `documents`, `extracted_texts`, `crawl_runs` und eine SQLite-FTS-Tabelle fuer Begriffe wie `Melle`, `Genehmigung`, `UVP` oder `BImSchG`. Lokale Dokumentpfade werden relativ zur Landkreis-Datenwurzel gespeichert, damit grosse Downloads ausserhalb des Projektverzeichnisses abgelegt werden koennen.

Der Import arbeitet quellenorientiert:

1. Listen-HTML fuer Bekanntmachungen oder Amtsblaetter abrufen und unter der Landkreis-Datenwurzel archivieren.
2. Listeneintraege mit Datum, Titel, Detail-URL und stabiler `publication_id` extrahieren.
3. Detailseite laden, Original-HTML speichern und PDF-/Dateilinks erfassen.
4. Vorhandene Landkreis-Veröffentlichungen mit lokalem `manifest.json` bei spaeteren Laeufen ueberspringen; neue Bekanntmachungs-PDFs nicht herunterladen; neue Amtsblaetter vollstaendig herunterladen.
5. Mit `build_landkreis_publications_db.py` die SQLite-DB aus Manifests und lokalen Amtsblatt-Dateien neu aufbauen.
6. Text mit der bestehenden Extraktionspipeline ableiten und in `extracted_texts` sowie der FTS-Tabelle auffindbar machen.
7. Optional mit `build_landkreis_vector_index.py` lokal vorhandene Dokumente in die Qdrant-Collection `landkreis_publications` schreiben.

Wichtige CLI-Optionen:

```bash
python scripts/fetch_landkreis_publications.py --source all
python scripts/build_landkreis_publications_db.py
python scripts/build_landkreis_vector_index.py
python scripts/fetch_landkreis_publications.py --source bekanntmachungen --query Melle
python scripts/fetch_landkreis_publications.py --source amtsblaetter --from-date 2026-01-01
python scripts/search_landkreis_publications.py "Melle Genehmigung"
```

Externe Ablage grosser Rohdaten:

```bash
RATSI_LANDKREIS_DATA_DIR=/mnt/d/landkreis_osnabrueck \
python scripts/fetch_landkreis_publications.py --source all
RATSI_LANDKREIS_DATA_DIR=/mnt/d/landkreis_osnabrueck \
python scripts/build_landkreis_publications_db.py
```

Alternativ akzeptieren Fetch-, DB-Build- und Vektor-Build-Skript `--data-dir`; alle drei sollten dieselbe Landkreis-Datenwurzel verwenden, weil `local_path` relativ dazu gespeichert wird. Die Datenbank kann separat mit `RATSI_LANDKREIS_DB` oder `--db` gesetzt werden.

Der Landkreis-Vektorindex bleibt von `ratsi_documents` getrennt. `build_landkreis_vector_index.py` liest `data/db/landkreis_publications.sqlite`, verwendet `extracted_texts.extracted_text` als Primaertext und faellt bei fehlendem Text auf Veroeffentlichungs- und Dokumenttitel zurueck. Indexiert werden nur Dokumentzeilen mit lokalem Pfad. Stabile Qdrant-IDs entstehen aus `landkreis`, `publication_id` und Dokument-URL. Regulaere Laeufe ergaenzen fehlende `snippet`-Payloads bestehender Punkte direkt, ohne deren Vektoren neu zu berechnen. Vollstaendige Laeufe entfernen zudem verwaiste Punkte; bei `--limit` ist diese Bereinigung deaktiviert. Lokale Payload-Pfade werden gegen `RATSI_LANDKREIS_DATA_DIR` oder `--data-dir` aufgeloest. Fuer den Embedding-Schritt werden standardmaessig hoechstens 6000 Zeichen pro Dokument verwendet; bei knappem XPU/GPU-Speicher kann `--max-text-chars` niedriger gesetzt werden.

### Wichtige Metadaten

- `session_id`
- `date`
- `committee`
- `document_type`
- `agenda_item`
- `url`
- `local_path`
- `sha1`
- `retrieved_at`

## 6. Analysevorbereitung

Die Oberflächen und Services arbeiten fuer KI-Analysen typischerweise auf diesen Objekten:

- Gremium
- Sitzung
- TOP
- Dokument

Typischer Analysefluss:

1. Gremium / Zeitraum / Status filtern
2. Sitzung auswaehlen
3. optional TOPs oder Dokumente eingrenzen
4. Prompt und Provider waehlen
5. Analyse durch KI starten

Die eigentliche Analyse liegt fachlich im Analyse-Service und ist von der Datenverarbeitung entkoppelt.

## 7. Vektorindex und semantische Suche

### Ziel

Dokumente sollen nicht nur ueber exakte Schlagwoerter, sondern auch inhaltlich auffindbar sein.

### Komponenten

| Komponente | Datei | Aufgabe |
| --- | --- | --- |
| Embedding-Service | `src/analysis/embeddings.py` | Harrier laden, Dense-Vektoren erzeugen |
| Sparse-Encoder | `src/analysis/bm25_sparse.py` | BM25-Sparse-Vektoren ueber `fastembed` |
| Vector Store | `src/analysis/vector_store.py` | Qdrant-Wrapper |
| Index-CLI | `scripts/build_vector_index.py` | Vollstaendigen Ratsinfo-Abschnittsindex aufbauen |
| Abschnittsaufbau | `src/indexing/passage_builder.py` | Quellen-Hashes, inkrementelle Generationen und Umschaltung |
| Extraktion und Aufteilung | `src/indexing/passages.py` | Alle PDF-Seiten, optionale OCR und tokenbegrenzte Abschnitte |
| ID-Strategie | `src/indexing/id_strategy.py` | stabile Qdrant-IDs aus Dokumentmetadaten erzeugen |
| Payload-Building | `src/indexing/payload_builder.py` | Qdrant-Payloads und absolute lokale Pfade bauen |
| Hybrid-Vectorizer | `src/indexing/vectorizer.py` | Dense- und Sparse-Vektoren je Dokument koordinieren |
| Reconciliation | `src/indexing/reconciliation.py` | verwaiste Qdrant-IDs erkennen |

### Architektur

```text
SQLite (local_index.sqlite)
    ↓
session_path + local_path → absoluter Dokumentpfad
    ↓
Alle PDF-Seiten / optionale OCR / Fallback-Metadaten
    ↓
Seitenbezogene Abschnitte mit maximal 768 Tokens
    ↓
Dense Embeddings (Harrier)
    + Sparse BM25-Vektoren
    ↓
Qdrant Local Store
    ↓
Hybrid-Suche mit RRF-Rangfusion
```

Die fachlichen Indexing-Schritte fuer stabile IDs, Payload-Aufbau, Hybrid-Vektorisierung und Reconciliation liegen in `src/indexing/`. Das CLI-Skript bleibt damit der Orchestrator fuer Datenladen, Batching und Qdrant-Upsert.

### Speicherort

- Qdrant lokal unter `data/db/qdrant/`
- Collections: `ratsi_passages` fuer Ratsinfo-Abschnitte, `ratsi_documents` als erhaltener Legacy-Index, `landkreis_publications` fuer Landkreis-Veröffentlichungen

### Stabile IDs und Reconciliation

- Dokumente werden ueber einen stabilen Hash aus `session_id`, `url` und `agenda_item` identifiziert. Abschnitts-IDs beziehen zusaetzlich den Quellen-/Konfigurationsfingerprint und die Abschnittsnummer ein.
- Nach vollstaendigen fehlerfreien Laeufen werden verwaiste Dokumentabschnitte entfernt.
- Bei `--limit`-Laeufen wird die Anzahl geaenderter oder fehlender Dokumente begrenzt; alle Abschnitte eines ausgewaehlten Dokuments werden verarbeitet.
- Bei `--limit`-Läufen ist Orphan-Reconciliation bewusst deaktiviert.
- Ein optionaler Hugging-Face-Token kann sicher im OS-Schlüsselring hinterlegt werden und wird beim Laden des Embedding-Modells als `HF_TOKEN` bereitgestellt.

## 8. Textextraktion fuer Suche und Analyse

Reihenfolge fuer Ratsinfo-Suchindexierung:

1. lokale PDF-Datei aufloesen
2. PDF-Text per `pypdf` auf allen Seiten extrahieren, bei leeren Seiten optional OCR versuchen
3. Text seitenweise in ueberlappende Abschnitte zerlegen
4. wenn kein brauchbarer Text vorliegt:
   - Fallback auf `Titel + Dokumenttyp`

Wichtige Konsequenzen:

- Scan-PDFs ohne Textebene fallen auf Fallbacks zurueck
- Der neue Ratsinfo-Abschnittsindex liest alle Seiten von Dateien bis einschliesslich 100 MiB. Nur der explizite Legacy-Build mit `--legacy-document-index` bleibt auf zehn Seiten begrenzt
- Die lokale Extraktionspipeline verarbeitet nur Dateien bis einschliesslich 25 MiB und kennzeichnet groessere Dateien als `file_too_large`
- Die lokale Extraktionspipeline versucht bei PDFs ohne lesbare Textebene optional OCR, wenn `pdftoppm` und `tesseract` mit den Sprachdaten `deu` und `eng` installiert sind; andernfalls lautet der Status `ocr_needed`
- Provider koennen PDF-Anhaenge nativ verarbeiten oder Text ueber `pypdf` auslesen; diese Pfade verwenden nicht die 25-MiB-Grenze der lokalen Extraktionspipeline

Aufbau, Umschaltung, OCR-Grenzen und Recherche-Benchmark sind in
[search_quality.md](search_quality.md) beschrieben.

## 9. Semantische Suche in der Oberfläche

Die semantische Suche:

- arbeitet derzeit auf dem lokalen Index
- nutzt Hybrid-Retrieval
- zeigt Treffer mit Metadaten, TOP-Bezug und Textausschnitt; der Abschnittsindex liefert zusaetzlich PDF-Seite und direkten Fundstellenlink
- filtert die aktuelle Trefferliste nach Datum sowie bei Ratsinfo nach Gremium und Dokumenttyp
- verwendet **RRF-Rangfusion**

Der angezeigte Score ist:

- kein Prozentwert
- keine direkte Cosine-Similarity
- vor allem als relativer Rang-/Debug-Wert zu verstehen

## 10. Wichtige Skripte in der Datenverarbeitung

### `scripts/fetch_sessions.py`
- lädt Sitzungen und Dokumente nach `data/raw/`

### `scripts/fetch_session_from_index.py`
- laedt eine einzelne Sitzung ausgehend von `data/db/online_session_index.sqlite`
- unterstuetzt `--list` zur Auswahl und `--session-id` zum gezielten Download

### `scripts/build_local_index.py`
- baut den lokalen SQLite-Index aus vorhandenen Rohdaten
- uebernimmt veraltete Agenda- und Dokumentmetadaten aus einer neueren `session_detail.html` nur in den Index
- veraendert dabei keine Dateien unter `data/raw/`

### `scripts/build_online_index_db.py`
- baut einen metadatenbasierten Online-Index ohne Dokumentdownloads
- veraendert den lokalen Rohdatenbestand nicht

### `scripts/build_vector_index.py`
- baut oder aktualisiert `ratsi_passages` mit Harrier und BM25
- erkennt geaenderte Quellen und Konfigurationen per Fingerprint
- `--limit N` verarbeitet hoechstens die naechsten `N` geaenderten Dokumente
- aktiviert den Abschnittsindex erst nach vollstaendigem Erstaufbau

### `scripts/evaluate_search.py`
- validiert 30 Recherchefragen mit Original-URL, PDF-Seite und Beleg
- misst bekannte Quellentreffer, Fundstellentreffer und Suchdauer fuer Legacy- oder Abschnittsindex

## 11. Abhängigkeiten

### Grundlegende Datenverarbeitung

- `beautifulsoup4`
- `requests`
- `pypdf`
- optional fuer OCR: `pdftoppm` aus Poppler sowie `tesseract` mit den Sprachdaten `deu` und `eng`

### Semantische Suche

- `sentence-transformers` 5.x und `transformers` 5.x fuer das Harrier-Qwen3-Modell
- `qdrant-client`
- `fastembed`
- `torch` separat fuer CPU oder XPU

## 12. Betriebsregeln

- Bei Änderungen an Fetch-/Parsinglogik Rohdaten- und Indexpfade mitdenken
- Bei Änderungen an Textextraktion, Embedding-Modell oder Stable-ID-Schema den Vektorindex vollständig neu aufbauen
- Regulaere Ratsinfo-Builds aktualisieren geaenderte Quellen und Abschnittskonfigurationen; beim Landkreis-Dokumentindex werden fehlende Treffertext-Payloads weiterhin ohne erneutes Embedding ergaenzt
- Zielsystem regelmäßig auf Änderungen an HTML, Parametern und Dokumenttypen prüfen
- Aktive Oberflächen sollen diese Pipeline nutzen, nicht neu erfinden

## 13. Offene Punkte

- Die optionale OCR fuer Scan-PDFs benoetigt externe Systemwerkzeuge und ist noch nicht als verpflichtender Installationsbestandteil abgesichert
- Dateibenennung ueber HTTP-Header kann noch verbessert werden
- bei dauerhaft nicht erreichbaren Quellen sollten Scheduler-faehige Fehlerpfade weiter geschaerft werden
