# Grundkonzept Datenverarbeitung

Dieses Dokument beschreibt die zentrale Datenverarbeitungskette des Projekts von der Datenerfassung im Ratsinformationssystem bis zur semantischen Suche. Es ist die gemeinsame Grundlagen-Datei fuer:

- Zielsystem und Abruflogik
- Rohdatenablage
- SQLite-Indizes
- Vektorindex und semantische Suche

## 1. Zielsystem und Dauerannahmen

Das Projekt arbeitet gegen eine oeffentliche **SessionNet**-Installation der Stadt Melle unter:

- `https://session.melle.info/bi/`

Wichtige angrenzende Quelle:

- Stadtportal Melle unter `https://www.melle.de/`

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
| Indexierung | `scripts/build_vector_index.py` | SQLite lesen, PDF-Text extrahieren, Qdrant befuellen |

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

### Speicherort

- Qdrant lokal unter `data/db/qdrant/`
- Collection: `ratsi_documents`

### Stabile IDs und Reconciliation

- Qdrant-Punkte werden nicht ueber SQLite-Autoincrement, sondern ueber einen stabilen Hash aus `session_id`, `url` und `agenda_item` identifiziert.
- Bei vollständigen Läufen werden verwaiste Punkte entfernt.
- Bei `--limit`-Läufen ist Orphan-Reconciliation bewusst deaktiviert.

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
