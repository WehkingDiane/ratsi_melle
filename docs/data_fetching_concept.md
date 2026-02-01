# Konzept für die Datenerfassung

Dieses Dokument beschreibt die Ergebnisse aus Task 2 der Projekt-Roadmap. Es fasst die recherchierten Strukturen des Ratsinformationssystems der Stadt Melle zusammen, leitet daraus eine Abruflogik ab und definiert das Speicherkonzept für die Rohdaten.

## 1. Quellen und HTML-Strukturen

Die Stadt Melle betreibt eine eigene **SessionNet**-Installation unter `https://session.melle.info/bi/`. Wichtige Seiten:

| Seite | Zweck | Parameter |
| --- | --- | --- |
| `si0040.asp` | Monatsübersicht aller öffentlichen Sitzungen. Zeilen enthalten den Sitzungsnamen, optional das Gremium sowie Zeit- und Ortsangaben. | `month` (zweistellig), `year` (vierstellig) |
| `si0057.asp` | Detailansicht einer einzelnen Sitzung inkl. Tagesordnung und Dokumentverweisen. | `__ksinr` (Sitzungs-ID) |
| `do*.asp` | Dokumentdownloads (z. B. `do0050.asp`) aus den Tagesordnungseinträgen. Der Client übernimmt die Parameter unverändert aus den Links. | variabel |

### HTML-Merkmale

- **Übersicht (`si0040.asp`)**: `table#smc_page_si0040_contenttable1` enthält Zeilen mit `td.siday` (Tageszahl in `span.weekday`) und `td.silink`. Innerhalb von `td.silink` finden sich ein optionaler Gremiums-Header (`div.smc-el-h`), der Sitzungslink (`a.smc-link-normal`) sowie eine Liste `ul.smc-detail-list`, deren Einträge Zeit und Ort enthalten.
- **Tagesordnung**: In der Detailansicht wird eine Tabelle gerendert, deren Klasse, ID oder `summary`-Attribut das Wort „Tagesordnung“ enthält. Spalten: TOP-Nummer, Betreff/Beschreibung, optional Status sowie ein Container mit Dokumentlinks.
- **Dokumente**: Download-Links besitzen `href`-Attribute mit `do` im Pfad (z. B. `getfile.asp?id=...&type=do`). Über den Tagesordnungspunkten befindet sich zusätzlich ein Panel `div.smc-documents`, das allgemeine Dokumente der Sitzung (z. B. Bekanntmachungen, Beschlussübersichten) bereitstellt.
- **Dateiendung**: Der Linktext liefert nur selten die Dateiendung. Diese wird daher aus `Content-Type`, Dateipfad oder – falls nötig – aus dem Dokumenttitel abgeleitet.

## 2. Abruflogik

1. **Monatsweise Abfrage**: Für jeden Monat wird `si0040.asp?month=..&year=..` geladen und unverändert abgespeichert. Daraus entstehen Sitzungsreferenzen mit Gremium, Titel, Datum, Startzeit, Ort und Detail-Link.
2. **Detailabfrage**: Für jede Sitzung wird die Detailseite (`si0057.asp`) geladen. Die Tagesordnungstabelle wird geparst und zu einer strukturierten Liste von TOPs inklusive der verlinkten Dokumente transformiert.
3. **Dokumentdownloads**: Alle in der Tagesordnung sowie im Sitzungs-Dokumentenpanel gefundenen Links mit `do*.asp` werden heruntergeladen. Innerhalb eines Prozesslaufs werden identische URLs nur einmal vom Server angefragt (lokaler Cache); Fehler (z. B. 404) werden geloggt, führen aber nicht zum Abbruch der gesamten Sitzungserfassung.
4. **Request-Drosselung & Retries**: Jeder HTTP-Request wird standardmäßig auf 1 Anfrage/Sekunde begrenzt. Bei Fehlern greift eine exponentielle Retry-Strategie (Backoff), sodass auch größere Zeiträume ohne unnötig viele Doppelanfragen abgearbeitet werden können.
5. **Wiederholungsstrategien**: HTTP-Fehler werden durch Exception-Handling abgefangen; der Client kann erneut aufgerufen werden. Die CLI unterstützt Wiederholungen über erneutes Ausführen.

Zusätzlich kann der Abruf ohne Dokumentdownloads erfolgen: `scripts/build_online_index_db.py` lädt Monats- und Detailseiten, erzeugt daraus eine Online-Indexdatenbank unter `data/processed/online_session_index.sqlite` und speichert dabei nur Metadaten (Session, TOPs, Dokument-URLs). Mit `--refresh-existing` werden vorhandene Sitzungen aktualisiert, mit `--only-refresh` werden ausschließlich bestehende Sitzungen erneuert.

## 3. Speicherkonzept für Rohdaten

- **Verzeichnisstruktur**: `data/raw/<Jahr>/<Datum>_<Gremium>_<Sitzungs-ID>/`.
  - Beispiel: `data/raw/2024/2024-05-14_Ausschuss-fuer-Umwelt_12345/`.
  - Unterordner:
    - `session_detail.html` mit dem Original-HTML.
    - `session-documents/` für alle dokumente, die auf Sitzungsebene bereitgestellt werden.
    - `agenda/<TOP-Nummer>_<Kurzname>/` für Dokumente je Tagesordnungspunkt – der Kurzname enthält ausschließlich die offizielle TOP-Bezeichnung; Zusätze wie „Berichterstatter …“ werden entfernt.
    - `manifest.json` als Metadatenindex aller abgelegten Dateien.
    - `agenda_summary.json` mit einer strukturierten Liste der TOPs (Nummer, Titel, Reporter:in, Status, abgeleiteter Beschluss sowie ein Flag, ob bereits Dokumente vorliegen), sodass spätere Verarbeitungsschritte nicht erneut das HTML parsen müssen.
- **Gespeicherte Artefakte**:
  - `YYYY-MM_overview.html` pro Monat im Jahresordner.
  - Einzelne Dokumente mit sprechendem Slug, laufender Nummer und entdeckter Dateiendung (z. B. `.pdf`), ergänzt um einen Hash-Anteil zur Entschärfung von Duplikaten.
- **Metadaten**: Agenda und Dokumente werden programmatisch zu Python-Objekten (`SessionDetail`, `AgendaItem`, `DocumentReference`) verarbeitet. Zusätzlich enthält `manifest.json` Dateipfad, Titel, Kategorie, TOP-Zuordnung, Ursprungs-URL, SHA1-Fingerprint sowie HTTP-Header (`content_type`, `content_disposition`, `content_length`), sodass spätere Verarbeitungsschritte ohne erneutes HTML-Parsen oder wiederholte Downloads auskommen.
- **Unvollständige Informationen**: Für zukünftige oder frisch nachgepflegte Sitzungen liegen Reporter:innen- und Beschlussangaben teilweise nicht vor. Die Summary-Datei markiert solche Einträge mit `decision = null` bzw. `documents_present = false`, bis ein erneuter Crawl die Werte anreichert.
- **Versionierung**: Alle Rohdaten liegen innerhalb des Git-Repositories, werden aber über `.gitignore` von produktiven Downloads ausgeschlossen. Tests können mit Mock-Daten arbeiten.

## 4. Offene Punkte

- Authentifizierung ist aktuell nicht erforderlich, jedoch sollte mittelfristig ein Request-Rate-Limit implementiert werden (z. B. 1 Anfrage/Sekunde), um die Server zu schonen.
- Für Dokumentdownloads muss der finale Dateiname zukünftig über die HTTP-Header (`Content-Disposition`) bestimmt werden.
- Bei dauerhaft nicht erreichbaren Seiten (z. B. Wartung) sollte die CLI einen non-zero Exit-Code liefern, um Scheduler-Läufe sichtbar scheitern zu lassen.
