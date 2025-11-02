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
- **Dokumente**: Download-Links besitzen `href`-Attribute mit `do` im Pfad (z. B. `do0050.asp?...`). Der Linktext ist der Dokumenttitel; die finale Dateiendung ergibt sich aus dem HTTP-Header.

## 2. Abruflogik

1. **Monatsweise Abfrage**: Für jeden Monat wird `si0040.asp?month=..&year=..` geladen und unverändert abgespeichert. Daraus entstehen Sitzungsreferenzen mit Gremium, Titel, Datum, Startzeit, Ort und Detail-Link.
2. **Detailabfrage**: Für jede Sitzung wird die Detailseite (`si0057.asp`) geladen. Die Tagesordnungstabelle wird geparst und zu einer strukturierten Liste von TOPs inklusive der verlinkten Dokumente transformiert.
3. **Dokumentdownloads**: Alle in der Tagesordnung gefundenen Links mit `do*.asp` werden heruntergeladen. Fehler (z. B. 404) werden geloggt, führen aber nicht zum Abbruch der gesamten Sitzungserfassung.
4. **Wiederholungsstrategien**: HTTP-Fehler werden durch Exception-Handling abgefangen; der Client kann erneut aufgerufen werden. Die CLI unterstützt Wiederholungen über erneutes Ausführen.

## 3. Speicherkonzept für Rohdaten

- **Verzeichnisstruktur**: `data/raw/<Jahr>/<Datum>_<Gremium>_<Sitzungs-ID>/`.
  - Beispiel: `data/raw/2024/2024-05-14_Ausschuss-fuer-Umwelt_12345/`.
  - Sonderzeichen werden bei der Ablage in Dateinamen durch Bindestriche ersetzt.
- **Gespeicherte Artefakte**:
  - `YYYY-MM_overview.html` pro Monat im Jahresordner.
  - `session_detail.html` innerhalb des Sitzungsordners.
  - Heruntergeladene Dokumente als `*.bin`. Die binäre Endung wird beibehalten, bis Metadaten (z. B. `Content-Type`) für eine genaue Dateiendung ausgewertet werden können.
- **Metadaten**: Agenda und Dokumente werden programmatisch zu Python-Objekten (`SessionDetail`, `AgendaItem`, `DocumentReference`) verarbeitet. Persistente Serialisierung (z. B. JSON) erfolgt erst in späteren Tasks.
- **Versionierung**: Alle Rohdaten liegen innerhalb des Git-Repositories, werden aber über `.gitignore` von produktiven Downloads ausgeschlossen. Tests können mit Mock-Daten arbeiten.

## 4. Offene Punkte

- Authentifizierung ist aktuell nicht erforderlich, jedoch sollte mittelfristig ein Request-Rate-Limit implementiert werden (z. B. 1 Anfrage/Sekunde), um die Server zu schonen.
- Für Dokumentdownloads muss der finale Dateiname zukünftig über die HTTP-Header (`Content-Disposition`) bestimmt werden.
- Bei dauerhaft nicht erreichbaren Seiten (z. B. Wartung) sollte die CLI einen non-zero Exit-Code liefern, um Scheduler-Läufe sichtbar scheitern zu lassen.

