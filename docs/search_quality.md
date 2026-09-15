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
Der Status zeigt bereits den Aufbaufortschritt des neuen Index; Vektoranzahl und
Dokumentanzahl sind deshalb unterschiedliche Groessen. Lokale Qdrant-Zugriffe
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
