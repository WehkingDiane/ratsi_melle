# Status: Fortschritt zu Taskliste Punkt 3 (Dokumentenverarbeitung)

Stand: 2026-02-08
Branch: `codex/feature/document-type-and-analysis-export`
Hinweis: Diese Datei dokumentiert den aktuellen Implementierungsstand inklusive Codeaenderungen.

## Zusammenfassung

- Bereits stark umgesetzt sind Datenerfassung, Normalisierung ins SQLite-Schema und Testabdeckung.
- Metadaten fuer Filterung und Analyse-Weitergabe wurden deutlich ausgebaut.
- Wesentliche Luecken bestehen aktuell vor allem bei PDF-Inhaltsextraktion und Parsing-Qualitaetsklassifikation.

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
  - Zusatztests fuer Index/Export/Migration vorhanden:
    - `tests/test_index_schema_parity.py`
    - `tests/test_export_analysis_batch.py`
    - `tests/test_document_type_backfill.py`
  - Testlauf: `13 passed`.

3. Normalisierte Datenstruktur mit Metadaten
- Status: **erledigt (fuer aktuellen Scope)**
- Nachweis:
  - Konsistentes Schema in local/online DB:
    - `scripts/build_local_index.py`
    - `scripts/build_online_index_db.py`
  - Vorhandene Filterfelder: `date`, `year`, `month`, `committee`, `status`, TOP-Nummer, `document_type`.
  - Dokument-Metadaten in `documents`: `document_type`, `sha1`, `retrieved_at`.
  - Legacy-Migration vorhanden (`niederschrift` -> `protokoll`, Backfill leerer `document_type`-Werte).

4. Analyse-Uebergabe-Metadaten standardisieren
- Status: **weitgehend erledigt**
- Nachweis:
  - `manifest.json` enthaelt `url`, `path`, `sha1`, `content_type`, `content_length`, `retrieved_at`.
  - Analyse-Export vorhanden: `scripts/export_analysis_batch.py`.
  - Export enthaelt reproduzierbare Kernfelder je Dokument (`session_id`, `date`, `committee`, `top_number`, `title`, `document_type`, `url`, `local_path`, `sha1`, `retrieved_at`).
  - Offen: keine explizite Parsing-Qualitaetsklassifikation.

5. HTML-Parser fuer weitere Dokumenttypen/Beschluesse
- Status: **teilweise erledigt**
- Nachweis:
  - Mehrere Fallbacks fuer variierende Tabellen/Layouts in SessionNet.
  - Dokumenttyp-Mapping fuer Index/Export ist vorhanden, basiert aber auf Kategorien/Heuristiken und nicht auf inhaltsspezifischen Dokumentparsern.
  - Offen: priorisierte Dokumenttyp-spezifische Parserlogik fuer Inhalte bleibt ausstehend.

6. PDF-Extraktion/Normalisierung
- Status: **offen**
- Nachweis:
  - Download und Dateityp-Erkennung sind vorhanden.
  - Keine PDF-Text-/Struktur-Extraktion in Datenmodell/Index.

7. Metadaten-Mapping fuer Suche/Filterung + Export fuer Analyse-Batches
- Status: **weitgehend erledigt**
- Nachweis:
  - Indexe fuer Zeit/Gremium vorhanden.
  - `document_type` als zusaetzliches Filterfeld vorhanden.
  - Reproduzierbarer Batch-Export implementiert: `scripts/export_analysis_batch.py`.
  - GUI kann aktuell u. a. Gremienlisten ausgeben.
  - Offen: UI-Filterflow fuer Sitzungsauswahl und Analyse-Workflow in der Oberflaeche.

## Priorisierte naechste Schritte

1. PDF-Extraktionspipeline festlegen und implementieren (inkl. Fehler-/Qualitaetskennzeichnung).
2. Parsing-Qualitaetsklassifikation fuer Dokumentextraktion definieren und in Datenmodell/Export aufnehmen.
3. Dokumenttyp-spezifische Inhaltsparser fuer priorisierte Typen (Vorlage, Beschlussvorlage, Protokoll-Auszug) ergaenzen.
4. UI-Filter fuer Zeitraum/Sitzung/Gremium plus Auswahl-Workflow fuer Analyse integrieren.
