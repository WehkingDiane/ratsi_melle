# Öffentliche SessionNet-Daten abrufen

[Dokumentation](../README.md)

- SessionNet `/bi/` liefert öffentliche Sitzungen, Tagesordnungspunkte und Dokumente. `scripts/fetch_bi_sessions.py` lädt nach Jahr und Monaten; `scripts/fetch_bi_session_from_index.py` lädt einzelne Sitzungen anhand des gespeicherten Online-Index. Beide nutzen `src/fetching/sessionnet_client.py`.
- `scripts/build_bi_online_index_db.py` baut den Kalender- und Metadatenindex in `data/db/online_session_index.sqlite`. Angekündigte Termine ohne Detailseite werden über die Kalender-ID erfasst. Bei abgesagten oder verschobenen Terminen werden zunächst nur Kalenderdaten übernommen. Werden sie später wieder als geplant geführt, lädt ein normaler Build die verfügbaren Details nach; `--refresh-existing` ist dafür nicht erforderlich. Fehlt zunächst noch der Detaillink, bleibt der Eintrag für dessen spätere Veröffentlichung aktualisierbar. Vorhandene TOPs und Dokumentmetadaten bleiben bis zum erfolgreichen Detailabruf erhalten.
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

### Abgeschlossene lokale Nachpflege am 17.11.2026

Im lokalen BI-Arbeitsbestand wurden 493 Manifeste geprüft und 488 davon um insgesamt 7.993 Dokument-IDs ergänzt. Zuerst wurde Sitzung 5184 vom 30.08.2021 mit 29 Dokumenten geprüft. Für alle ergänzten Einträge konnte die ID eindeutig aus der vorhandenen URL ermittelt werden; die übrigen Manifestdaten und Dokumentdateien blieben unverändert.

Die Originalmanifeste wurden bytegleich unter `archive/manifest_document_ids_20261117/data/raw/` mit ihrer bisherigen Unterstruktur gesichert. Das temporäre Hilfsskript wurde nach der erfolgreichen Prüfung gelöscht. Landkreis-Manifeste wurden nicht verändert.

Diese Nachpflege betrifft den lokalen Datenbestand; sie wird beim Auschecken des Branches nicht automatisch auf anderen Rechnern ausgeführt. Laufzeitdaten und Sicherungen sind nicht Teil des Commits.
