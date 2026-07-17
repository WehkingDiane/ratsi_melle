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
build_local_index.py / build_online_index_db.py
    ↓
SQLite-Indizes unter data/db/
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
search_landkreis_publications.py
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
- Dokumentdownloads geben ab 25 MiB einen Hinweis aus und sind standardmaessig auf 100 MiB pro Dokument begrenzt

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

### Online-Index

- Skript: `scripts/build_online_index_db.py`
- Quelle: SessionNet ohne Dokumentdownloads
- Ziel: `data/db/online_session_index.sqlite`

### Zweck der Indizes

- schnelle UI- und Analysezugriffe
- Sitzungen, TOPs und Dokumentmetadaten strukturiert abfragen
- Grundlage fuer Filter, Gremienlisten und Synchronisationslogik

### Landkreis-Veröffentlichungen

- Skript: `scripts/fetch_landkreis_publications.py`
- Build-Skript: `scripts/build_landkreis_publications_db.py`
- Suchskript: `scripts/search_landkreis_publications.py`
- Ziel: `data/db/landkreis_publications.sqlite`
- Rohdaten: standardmaessig `data/raw/landkreis/`, alternativ `RATSI_LANDKREIS_DATA_DIR` oder `--data-dir`

Diese Datenbank ist absichtlich vom SessionNet-Index getrennt. Sie enthaelt `publications`, `documents`, `extracted_texts`, `crawl_runs` und eine SQLite-FTS-Tabelle fuer Begriffe wie `Melle`, `Genehmigung`, `UVP` oder `BImSchG`. Lokale Dokumentpfade werden relativ zur Landkreis-Datenwurzel gespeichert, damit grosse Downloads ausserhalb des Projektverzeichnisses abgelegt werden koennen.

Der Import arbeitet quellenorientiert:

1. Listen-HTML fuer Bekanntmachungen oder Amtsblaetter abrufen und unter der Landkreis-Datenwurzel archivieren.
2. Listeneintraege mit Datum, Titel, Detail-URL und stabiler `publication_id` extrahieren.
3. Detailseite laden, Original-HTML speichern und PDF-/Dateilinks erfassen.
4. Bekanntmachungs-PDFs nicht herunterladen; Amtsblaetter vollstaendig herunterladen, aber bei spaeteren Laeufen vorhandene Amtsblaetter mit lokalem `manifest.json` ueberspringen.
5. Mit `build_landkreis_publications_db.py` die SQLite-DB aus Manifests und lokalen Amtsblatt-Dateien neu aufbauen.
6. Text mit der bestehenden Extraktionspipeline ableiten und in `extracted_texts` sowie der FTS-Tabelle auffindbar machen.

Wichtige CLI-Optionen:

```bash
python scripts/fetch_landkreis_publications.py --source all
python scripts/build_landkreis_publications_db.py
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

Alternativ akzeptieren Fetch- und Build-Skript `--data-dir`. Die Datenbank kann separat mit `RATSI_LANDKREIS_DB` oder `--db` gesetzt werden.

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
| Index-CLI | `scripts/build_vector_index.py` | SQLite lesen, PDF-Text extrahieren, Qdrant befuellen |
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
PDF-Text / Fallback-Metadaten
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
- Collection: `ratsi_documents`

### Stabile IDs und Reconciliation

- Qdrant-Punkte werden nicht ueber SQLite-Autoincrement, sondern ueber einen stabilen Hash aus `session_id`, `url` und `agenda_item` identifiziert.
- Bei vollständigen Läufen werden verwaiste Punkte entfernt.
- Bei `--limit`-Läufen wird die Anzahl der neu zu bauenden fehlenden Dokumentvektoren begrenzt, nicht die Menge der geprueften SQLite-Dokumente.
- Bei `--limit`-Läufen ist Orphan-Reconciliation bewusst deaktiviert.
- Ein optionaler Hugging-Face-Token kann sicher im OS-Schlüsselring hinterlegt werden und wird beim Laden des Embedding-Modells als `HF_TOKEN` bereitgestellt.

## 8. Textextraktion fuer Suche und Analyse

Reihenfolge fuer Suchindexierung:

1. lokale PDF-Datei aufloesen
2. PDF-Text per `pypdf` extrahieren, begrenzt auf die ersten Seiten
3. wenn kein brauchbarer Text vorliegt:
   - Fallback auf `Titel + Dokumenttyp`

Wichtige Konsequenzen:

- Scan-PDFs ohne Textebene fallen auf Fallbacks zurueck
- OCR ist perspektivisch moeglich, aber aktuell kein Standardpfad

## 9. Semantische Suche in der Oberfläche

Die semantische Suche:

- arbeitet derzeit auf dem lokalen Index
- nutzt Hybrid-Retrieval
- zeigt Treffer mit Metadaten, TOP-Bezug und Dokumentlink
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

### `scripts/build_online_index_db.py`
- baut einen metadatenbasierten Online-Index ohne Dokumentdownloads

### `scripts/build_vector_index.py`
- baut oder aktualisiert den Qdrant-Vektorindex
- `--limit N` baut hoechstens die naechsten `N` fehlenden Dokumentvektoren

## 11. Abhängigkeiten

### Grundlegende Datenverarbeitung

- `beautifulsoup4`
- `requests`
- `pypdf`

### Semantische Suche

- `sentence-transformers`
- `qdrant-client`
- `fastembed`
- `torch` separat fuer CPU oder XPU

## 12. Betriebsregeln

- Bei Änderungen an Fetch-/Parsinglogik Rohdaten- und Indexpfade mitdenken
- Bei Änderungen an Textextraktion, Embedding-Modell oder Stable-ID-Schema den Vektorindex vollständig neu aufbauen
- Zielsystem regelmäßig auf Änderungen an HTML, Parametern und Dokumenttypen prüfen
- Aktive Oberflächen sollen diese Pipeline nutzen, nicht neu erfinden

## 13. Offene Punkte

- OCR fuer Scan-PDFs ist noch kein Standardbestandteil
- Dateibenennung ueber HTTP-Header kann noch verbessert werden
- bei dauerhaft nicht erreichbaren Quellen sollten Scheduler-faehige Fehlerpfade weiter geschaerft werden
