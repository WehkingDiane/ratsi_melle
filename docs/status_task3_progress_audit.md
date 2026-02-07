# Status: Fortschritt zu Taskliste Punkt 3 (Dokumentenverarbeitung)

Stand: 2026-02-07
Branch: `codex/chore/task3-progress-audit`
Hinweis: Diese Datei dokumentiert nur den Analyse-Stand, ohne Codeaenderungen.

## Zusammenfassung

- Bereits stark umgesetzt sind Datenerfassung, Normalisierung ins SQLite-Schema und Testabdeckung.
- Teilweise umgesetzt sind Metadaten fuer Filterung und Analyse-Weitergabe.
- Wesentliche Luecken bestehen bei PDF-Inhaltsextraktion und einem expliziten Analyse-Batch-Export.

## Bewertung je Unterpunkt aus README Punkt 3

1. Parser fuer Vorlagen/Beschluesse entwickeln
- Status: **teilweise erledigt**
- Nachweis:
  - Parsing von Sitzung, TOPs und Dokument-Referenzen: `src/fetching/sessionnet_client.py`
  - Noch kein inhaltliches Parsing von Beschlusstext/Begruendung/Finanzbezug als strukturierte Felder.

2. Parser-Ausgaben mit Fixtures absichern
- Status: **erledigt**
- Nachweis:
  - Parser-/Download-/Retry-Tests vorhanden:
    - `tests/test_sessionnet_detail_parser.py`
    - `tests/test_sessionnet_month_parser.py`
    - `tests/test_sessionnet_client_documents.py`
    - `tests/test_sessionnet_client_retries.py`
  - Testlauf: `10 passed`.

3. Normalisierte Datenstruktur mit Metadaten
- Status: **weitgehend erledigt**
- Nachweis:
  - Konsistentes Schema in local/online DB:
    - `scripts/build_local_index.py`
    - `scripts/build_online_index_db.py`
  - Vorhandene Filterfelder: `date`, `year`, `month`, `committee`, `status`, TOP-Nummer.
  - Offen: kein dediziertes Feld `document_type` (aktuell v. a. `category`), kein Analyse-Batch-Modell.

4. Analyse-Uebergabe-Metadaten standardisieren
- Status: **teilweise erledigt**
- Nachweis:
  - `manifest.json` enthaelt bereits `url`, `path`, `sha1`, `content_type`, `content_length`, `retrieved_at`.
  - Offen: keine explizite Parsing-Qualitaetsklassifikation.

5. HTML-Parser fuer weitere Dokumenttypen/Beschluesse
- Status: **teilweise erledigt**
- Nachweis:
  - Mehrere Fallbacks fuer variierende Tabellen/Layouts in SessionNet.
  - Offen: priorisierte Dokumenttyp-spezifische Parserlogik noch nicht sichtbar.

6. PDF-Extraktion/Normalisierung
- Status: **offen**
- Nachweis:
  - Download und Dateityp-Erkennung sind vorhanden.
  - Keine PDF-Text-/Struktur-Extraktion in Datenmodell/Index.

7. Metadaten-Mapping fuer Suche/Filterung + Export fuer Analyse-Batches
- Status: **teilweise erledigt**
- Nachweis:
  - Indexe fuer Zeit/Gremium vorhanden.
  - GUI kann aktuell u. a. Gremienlisten ausgeben.
  - Offen: UI-Filterflow fuer Sitzungsauswahl und reproduzierbarer Batch-Export.

## Priorisierte naechste Schritte

1. PDF-Extraktionspipeline festlegen und implementieren (inkl. Fehler-/Qualitaetskennzeichnung).
2. Dokumenttyp-Mapping konkretisieren (`document_type`) und in den Index aufnehmen.
3. Analyse-Batch-Exportformat einfuehren (selektionierte Sitzungen + stabile Metadaten).
4. UI-Filter fuer Zeitraum/Sitzung/Gremium plus Auswahl-Workflow fuer Analyse integrieren.
