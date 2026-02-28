# Status: Fortschritt zu Taskliste Punkt 3 (Dokumentenverarbeitung)

Stand: 2026-02-28
Branch: `codex/feature/complete-task-3-document-processing`
Hinweis: Diese Datei dokumentiert den aktuellen Implementierungsstand inklusive Codeaenderungen.

## Zusammenfassung

- Datenerfassung, Normalisierung ins SQLite-Schema und Testabdeckung sind fuer den aktuellen Scope umgesetzt.
- Analyse-Export und lokaler Analyse-Workflow enthalten jetzt strukturierte Dokumentfelder fuer priorisierte Dokumenttypen.
- Offen bleibt vor allem die Robustheit der PDF-Struktur-/OCR-Pipeline fuer schwierigere Dokumente.

## Bewertung je Unterpunkt aus README Punkt 3

1. Parser fuer Vorlagen/Beschluesse entwickeln
- Status: **erledigt (fuer priorisierte Typen)**
- Nachweis:
  - Parsing von Sitzung, TOPs und Dokument-Referenzen: `src/fetching/sessionnet_client.py`
  - Inhaltliches Parsing fuer `vorlage`, `beschlussvorlage` und `protokoll`: `src/parsing/document_content.py`
  - Strukturierte Kernfelder: `beschlusstext`, `begruendung`, `finanzbezug`, `zustaendigkeit`, `entscheidung`

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
    - `tests/test_document_content_parser.py`
    - `tests/test_analysis_context.py`
  - Fixture-Dateien fuer dokumentinhaltliche Parser:
    - `tests/fixtures/document_beschlussvorlage_sessionnet.txt`
    - `tests/fixtures/document_protokoll_sessionnet.txt`
  - Testlauf der betroffenen Pfade: Parser, Export, Analyse-Kontext und Extraktion grün.

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
- Status: **erledigt (fuer aktuellen Scope)**
- Nachweis:
  - `manifest.json` enthaelt `url`, `path`, `sha1`, `content_type`, `content_length`, `retrieved_at`.
  - Analyse-Export vorhanden: `scripts/export_analysis_batch.py`.
  - Export enthaelt reproduzierbare Kernfelder je Dokument (`session_id`, `date`, `committee`, `top_number`, `title`, `document_type`, `url`, `local_path`, `sha1`, `retrieved_at`).
  - Zusaetzliche Qualitaets- und Strukturfelder im Export: `extraction_status`, `parsing_quality`, `content_parser_status`, `content_parser_quality`, `structured_fields`, `matched_sections`.

5. HTML-Parser fuer weitere Dokumenttypen/Beschluesse
- Status: **erledigt (fuer priorisierte Typen), Erweiterungen offen**
- Nachweis:
  - Mehrere Fallbacks fuer variierende Tabellen/Layouts in SessionNet.
  - Dokumenttyp-Mapping fuer Index/Export ist vorhanden.
  - Priorisierte dokumenttyp-spezifische Parserlogik fuer Inhalte ist vorhanden: `src/parsing/document_content.py`
  - Erweiterungen auf weitere Typen bleiben moeglich, sind aber kein Blocker fuer Taskliste Punkt 3.

6. PDF-Extraktion/Normalisierung
- Status: **teilweise erledigt**
- Nachweis:
  - Download und Dateityp-Erkennung sind vorhanden.
  - Basis-PDF-Text-Extraktion und OCR-Hinweis sind vorhanden: `src/analysis/extraction_pipeline.py`
  - Qualitaetskennzeichnung ist vorhanden und wird im Analyse-Export genutzt.
  - Offen bleibt eine robustere Seiten-/Abschnittsstruktur und ein vollwertiger OCR-Workflow.

7. Metadaten-Mapping fuer Suche/Filterung + Export fuer Analyse-Batches
- Status: **weitgehend erledigt**
- Nachweis:
  - Indexe fuer Zeit/Gremium vorhanden.
  - `document_type` als zusaetzliches Filterfeld vorhanden.
  - Reproduzierbarer Batch-Export implementiert: `scripts/export_analysis_batch.py`.
  - GUI-Analyse-Workflow nutzt strukturierte Dokumentfelder als Kontext: `src/interfaces/gui/app.py`, `src/analysis/analysis_context.py`
  - GUI kann aktuell u. a. Gremienlisten ausgeben und Analyse-Markdown mit Dokumentkontext erzeugen.
  - Offen: weiterer UI-Filterflow fuer Zeitraum-Presets und feinere Sitzungs-/Dokumentauswahl.

## Priorisierte naechste Schritte

1. PDF-Extraktionspipeline fuer schwierige/gescannte Dokumente robuster machen (Seitenstruktur, OCR-Workflow).
2. Dokumentparser auf weitere Typen ausdehnen, falls reale Daten das rechtfertigen.
3. UI-Filter fuer Zeitraum/Sitzung/Gremium plus Auswahl-Workflow fuer Analyse weiter verfeinern.
