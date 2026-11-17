# Öffentliche SessionNet-Daten abrufen

[Dokumentation](../README.md)

- SessionNet `/bi/` liefert öffentliche Sitzungen, Tagesordnungspunkte und Dokumente. `scripts/fetch_bi_sessions.py` lädt nach Jahr und Monaten; `scripts/fetch_bi_session_from_index.py` lädt einzelne Sitzungen anhand des gespeicherten Online-Index. Beide nutzen `src/fetching/sessionnet_client.py`.
- `scripts/build_bi_online_index_db.py` baut den Kalender- und Metadatenindex in `data/db/online_session_index.sqlite`. Angekündigte Termine ohne Detailseite werden über die Kalender-ID erfasst.
- SessionNet-Rohdaten liegen unter `data/raw/YYYY/MM/`. Gespeicherte HTML-Seiten und Dokumente bleiben beim Indexaufbau unverändert. Ein Sitzungsmanifest und eine Tagesordnungsübersicht halten Metadaten zum Download fest.

## Ablauf

```bash
python scripts/fetch_bi_sessions.py 2024 --months 5 6
python scripts/build_bi_online_index_db.py 2024 --months 5 6
python scripts/fetch_bi_session_from_index.py --list --from-date 2026-04-01 --to-date 2026-04-30
python scripts/fetch_bi_session_from_index.py --session-id 7128
```

Jahr, Monate und Sitzungs-ID sind Beispiele und müssen zum gewünschten Bestand passen. Der Online-Index ermöglicht die Auswahl einzelner Sitzungen; der direkte Monatsabruf ist ein weiterer Einstieg. Anschließend die [lokalen Indizes](../suche/indizes.md) aufbauen. Die Datenjobs sind auch in der [Weboberfläche](../oberflaeche/README.md) erreichbar.

## Dokument-ID im Manifest

Dokumenteinträge in `manifest.json` enthalten neben `url` die `document_id` als Zeichenfolge, beispielsweise `"document_id": "145474"`. Sie stammt aus dem Parameter `id` des `getfile.asp`-Links. Fehlt eine eindeutige numerische ID, steht dort `null`.

Neue und beim erneuten Abruf geschriebene Manifeste erhalten das Feld auch für wiederverwendete Dateien. Bestehende Manifeste werden nicht automatisch im gesamten Datenbestand umgeschrieben; ein Löschen vorhandener Dokumente ist nicht erforderlich.

Die Downloadmeldung zeigt ebenfalls die Dokument-ID, etwa `Downloading document 145474`; ohne eindeutige ID erscheint `Downloading document unbekannt`. Die vollständige URL bleibt für den Abruf und im Manifest erhalten.
